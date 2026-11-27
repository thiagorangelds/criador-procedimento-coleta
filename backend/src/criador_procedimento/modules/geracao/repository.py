"""Acesso ao que está fora do processo: a API do Gemini e o disco."""

import logging
import os
import random
import time
from pathlib import Path
from typing import List

from google import genai
from google.genai.errors import APIError

from criador_procedimento.modules.geracao.models import ArquivoGerado, DestinoDaTecnologia
from criador_procedimento.shared.exceptions import ErroDeGeracao
from criador_procedimento.shared import paths

# Erro do Gemini que vale repetir com espera; o resto é falha de verdade.
TERMOS_TEMPORARIOS = ("429", "rate limit", "quota", "503", "unavailable")

# O segundo prompt pede JSON estrito (response_mime_type), e isso só existe na
# v1beta: na v1 a API responde 400 "JSON mode is not enabled for api version v1".
# Versões antigas do google-genai usavam v1beta por padrão e escondiam isso; a
# partir da 2.x o padrão virou v1 e o documento parava de ser gerado — o
# levantamento saía, o procedimento não.
VERSAO_API = "v1beta"


def _cliente(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key, http_options={"api_version": VERSAO_API})


def gerar_conteudo(
    prompt: str,
    api_key: str,
    modelos: List[str],
    tentativas: int,
    logger: logging.Logger,
    config_geracao: dict = None,
) -> str:
    """Chama o Gemini percorrendo os modelos em ordem, com backoff entre tentativas."""
    cliente = _cliente(api_key)

    for modelo in modelos:
        for tentativa in range(1, tentativas + 1):
            try:
                logger.info(f"Gerando conteúdo usando o modelo '{modelo}' (Tentativa {tentativa}/{tentativas}).")
                resposta = cliente.models.generate_content(model=modelo, contents=prompt, config=config_geracao)
                return resposta.text

            except APIError as e:
                if not any(termo in str(e).lower() for termo in TERMOS_TEMPORARIOS):
                    logger.error(f"Erro fatal na API com o modelo '{modelo}': {e}")
                    break

                logger.warning(f"Limite de taxa ou alta demanda no modelo '{modelo}'.")
                if tentativa >= tentativas:
                    logger.warning(f"Máximo de tentativas ({tentativas}) esgotado para o modelo '{modelo}'.")
                    break

                espera = (5 * (2 ** tentativa)) + random.uniform(0, 3)
                logger.info(f"Aplicando backoff exponencial. Aguardando {espera:.2f} segundos...")
                time.sleep(espera)

            except Exception as e:
                logger.error(f"Erro inesperado com o modelo '{modelo}': {e}")
                break

    raise ErroDeGeracao("Falha ao gerar conteúdo: todos os modelos e tentativas foram esgotados.")


# ---------------------------------------------------------------------------
# Disco
# ---------------------------------------------------------------------------

def nome_base_da_tecnologia(tecnologia: str) -> str:
    """Não sanitiza pontuação de propósito: "S3 + SQS" vira a pasta "..._s3_+_sqs"."""
    return tecnologia.replace(" ", "_").lower().replace("-", "_")


def preparar_destino(tecnologia: str, pasta_saida=None) -> DestinoDaTecnologia:
    nome_base = nome_base_da_tecnologia(tecnologia)
    diretorio = Path(pasta_saida or paths.PASTA_SAIDA) / nome_base
    diretorio.mkdir(parents=True, exist_ok=True)
    return DestinoDaTecnologia(tecnologia=tecnologia, nome_base=nome_base, diretorio=diretorio)


def salvar_texto(caminho, conteudo: str) -> None:
    Path(caminho).write_text(conteudo.strip(), encoding="utf-8")


def listar_arquivos(diretorio, pasta_saida=None) -> List[ArquivoGerado]:
    pasta_saida = Path(pasta_saida or paths.PASTA_SAIDA)
    diretorio = Path(diretorio)
    if not diretorio.is_dir():
        return []
    arquivos = []
    for caminho in sorted(diretorio.iterdir()):
        if caminho.is_file():
            arquivos.append(ArquivoGerado(
                caminho=str(caminho.relative_to(pasta_saida)).replace(os.sep, "/"),
                tamanho=caminho.stat().st_size,
                modificado=caminho.stat().st_mtime,
            ))
    return arquivos
