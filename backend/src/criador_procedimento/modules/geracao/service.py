"""O motor: duas chamadas ao Gemini por tecnologia e os arquivos que saem delas.

Camada sem HTTP. Recebe a configuração pronta e devolve o que produziu —
quem transforma isso em job e em resposta é o módulo `jobs`.
"""

import json
import logging
import threading
from typing import List, Optional, Tuple

from pydantic import ValidationError

from criador_procedimento.core.config import FORMATOS_SAIDA, ConfiguracaoGeracao
from criador_procedimento.modules.geracao import docx, prompts, repository
from criador_procedimento.modules.geracao.models import ResultadoExecucao, ResultadoTecnologia
from criador_procedimento.modules.geracao.schemas import ConteudoDoProcedimento
from criador_procedimento.shared.exceptions import ErroDeConfiguracao, ErroDeGeracao
from criador_procedimento.shared import paths

# O cancelamento só é checado entre tecnologias — não há como abortar uma
# chamada ao Gemini no meio. Esta pausa é também o ponto onde ele é visto.
PAUSA_ENTRE_TECNOLOGIAS = 15


def pdf_disponivel(config: ConfiguracaoGeracao) -> bool:
    return bool(docx.localizar_libreoffice(config.libreoffice or None))


def validar(config: ConfiguracaoGeracao, formato_saida: str) -> List[str]:
    """Erros que impedem a execução começar. Lista vazia significa que pode rodar."""
    erros = []

    if not config.api_key:
        erros.append(
            f"API key do Gemini não configurada no servidor. Defina a chave API_KEY em '{paths.ARQUIVO_CONFIG}' "
            "ou a variável de ambiente CRIADOR_API_KEY."
        )
    if not config.modelos:
        erros.append(f"Nenhum modelo do Gemini configurado. Preencha MODELOS em '{paths.ARQUIVO_CONFIG}'.")
    if formato_saida not in FORMATOS_SAIDA:
        erros.append(f"Formato de saída deve ser um destes: {', '.join(FORMATOS_SAIDA)}.")
    if not config.modelo_docx.is_file():
        erros.append(f"Modelo Word '{config.modelo_docx}' não encontrado no servidor.")
    if formato_saida == "pdf" and not pdf_disponivel(config):
        erros.append("LibreOffice não encontrado no servidor: necessário para gerar em PDF.")

    return erros


def separar_catalogo(resposta: str) -> Tuple[str, Optional[str]]:
    """Parte o levantamento no marcador. Sem ele, tenta o título da seção 6."""
    if prompts.SEPARADOR_CATALOGO in resposta:
        levantamento, catalogo = resposta.split(prompts.SEPARADOR_CATALOGO, 1)
        return levantamento, catalogo.replace(prompts.MARCADOR_CATALOGO, "").strip()

    if prompts.MARCADOR_CATALOGO in resposta:
        levantamento, catalogo = resposta.split(prompts.MARCADOR_CATALOGO, 1)
        return levantamento, f"{prompts.MARCADOR_CATALOGO}\n{catalogo.strip()}"

    return resposta, None


def extrair_conteudo(resposta: str) -> ConteudoDoProcedimento:
    texto = resposta.strip()
    if texto.startswith("```"):
        texto = texto.split("\n", 1)[1].rsplit("```", 1)[0]
    return ConteudoDoProcedimento.model_validate(json.loads(texto))


def _gerar_levantamento(destino, config: ConfiguracaoGeracao, logger: logging.Logger) -> str:
    arquivo_levantamento = destino.arquivo(f"procedimento_{destino.nome_base}.txt")
    arquivo_catalogo = destino.arquivo(f"catalogo_{destino.nome_base}.txt")

    resposta = repository.gerar_conteudo(
        prompts.levantamento(destino.tecnologia), config.api_key, config.modelos, config.retry, logger
    )
    levantamento, catalogo = separar_catalogo(resposta)

    if catalogo is None:
        catalogo = "ERRO: Não foi possível extrair o Catálogo de Dados de forma estruturada."
        logger.warning(
            f"Não foi possível separar o Catálogo de Dados para '{destino.tecnologia}'. "
            f"Todo o conteúdo salvo em: {arquivo_levantamento}"
        )

    repository.salvar_texto(arquivo_levantamento, levantamento)
    logger.info(f"Procedimento de '{destino.tecnologia}' salvo com sucesso em: {arquivo_levantamento}")

    repository.salvar_texto(arquivo_catalogo, catalogo)
    logger.info(f"Catálogo de Dados de '{destino.tecnologia}' salvo com sucesso em: {arquivo_catalogo}")

    return levantamento


def _gerar_procedimento(destino, levantamento: str, config: ConfiguracaoGeracao, formato: str, logger: logging.Logger) -> None:
    arquivo_saida = destino.arquivo(f"procedimento_coleta_{destino.nome_base}.{formato}")
    arquivo_bruto = destino.arquivo(f"procedimento_coleta_{destino.nome_base}.json")

    resposta = repository.gerar_conteudo(
        prompts.procedimento(destino.tecnologia, levantamento),
        config.api_key, config.modelos, config.retry, logger,
        config_geracao={"response_mime_type": "application/json"},
    )

    try:
        conteudo = extrair_conteudo(resposta)
    except (json.JSONDecodeError, ValidationError, IndexError) as e:
        repository.salvar_texto(arquivo_bruto, resposta)
        raise ErroDeGeracao(
            f"Resposta inválida para o documento de procedimento ({e}). Resposta bruta salva em: {arquivo_bruto}"
        )

    if formato == "pdf":
        docx.gerar_pdf(config.modelo_docx, arquivo_saida, destino.tecnologia, conteudo,
                       docx.localizar_libreoffice(config.libreoffice or None))
    else:
        docx.gerar_docx(config.modelo_docx, arquivo_saida, destino.tecnologia, conteudo)

    logger.info(f"Documento de Procedimento de Coleta de '{destino.tecnologia}' salvo com sucesso em: {arquivo_saida}")


def executar(config: ConfiguracaoGeracao, logger: logging.Logger, cancelar: threading.Event = None) -> ResultadoExecucao:
    """Gera os documentos de cada tecnologia da configuração.

    Uma tecnologia que falha não derruba as outras: o motivo fica no
    `ResultadoTecnologia` dela e a execução segue.
    """
    cancelar = cancelar or threading.Event()

    erros = validar(config, config.formato_saida)
    if erros:
        raise ErroDeConfiguracao(" ".join(erros))

    resultado = ResultadoExecucao()

    for tecnologia in [t.strip() for t in config.tecnologias if t and t.strip()]:
        if cancelar.is_set():
            logger.warning("Execução cancelada pelo usuário.")
            resultado.cancelado = True
            break

        destino = repository.preparar_destino(tecnologia)
        logger.info(f"Processando a tecnologia '{tecnologia}'...")
        erro = None

        try:
            levantamento = _gerar_levantamento(destino, config, logger)
            _gerar_procedimento(destino, levantamento, config, config.formato_saida, logger)
        except ErroDeGeracao as e:
            erro = str(e)
            logger.error(f"Não foi possível processar '{tecnologia}'. Motivo: {e}")
        except Exception as e:
            erro = str(e)
            logger.error(f"Ocorreu um erro inesperado ao processar '{tecnologia}': {e}")

        resultado.tecnologias.append(ResultadoTecnologia(
            tecnologia=tecnologia,
            nome_base=destino.nome_base,
            erro=erro,
            arquivos=repository.listar_arquivos(destino.diretorio),
        ))

        cancelar.wait(PAUSA_ENTRE_TECNOLOGIAS)

    logger.info("Execução concluída.")
    return resultado
