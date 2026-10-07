from google import genai
from google.genai.errors import APIError
from gerador_docx import gerar_docx_procedimento, gerar_pdf_procedimento, localizar_libreoffice
import json
import logging
import logging.handlers
import os
import time
import random
import yaml

CONFIG_FILE = "config.yml"
SEPARADOR_CATALOGO = "\n\n--- INICIO_CATALOGO ---\n\n"
MARCADOR_CATALOGO = "6. Catálogo de Dados de Logs de Segurança (Padronização ECS)"
OUTPUT_DIR = "procedimentos"
MODELO_DOCX_PADRAO = "templates/modelo_procedimento_coleta.docx"
# "docx" ou "pdf". Para gerar em "pdf" é necessário ter o LibreOffice instalado (ou o executável informado na chave LIBREOFFICE do config.yml).
FORMATO_SAIDA_PADRAO = "docx"
FORMATOS_SAIDA = ("docx", "pdf")

def setup_logger(log_file: str) -> logging.Logger:
    logger = logging.getLogger("GeradorDeProcedimentoLogger")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(stream_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1024 * 1024 * 10, backupCount=2
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(file_handler)

    return logger

def carregar_configuracao():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def gerar_resposta_gemini_com_fallback(prompt: str, api_key: str, modelos: list, max_retries: int, logger: logging.Logger, config_geracao: dict = None) -> str:
    client = genai.Client(api_key=api_key)

    for modelo in modelos:
        for tentativa in range(1, max_retries + 1):
            try:
                logger.info(f"Gerando conteúdo usando o modelo '{modelo}' (Tentativa {tentativa}/{max_retries}).")
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt,
                    config=config_geracao,
                )
                return response.text

            except APIError as e:
                erro_str = str(e).lower()

                if any(termo in erro_str for termo in ["429", "rate limit", "quota", "503", "unavailable"]):
                    logger.warning(f"Limite de taxa ou alta demanda no modelo '{modelo}'.")

                    if tentativa < max_retries:
                        tempo_espera = (5 * (2 ** tentativa)) + random.uniform(0, 3)

                        logger.info(f"Aplicando backoff exponencial. Aguardando {tempo_espera:.2f} segundos...")
                        time.sleep(tempo_espera)
                        continue
                    else:
                        logger.warning(f"Máximo de tentativas ({max_retries}) esgotado para o modelo '{modelo}'.")
                else:
                    logger.error(f"Erro fatal na API com o modelo '{modelo}': {e}")
                    break

            except Exception as e:
                logger.error(f"Erro inesperado com o modelo '{modelo}': {e}")
                break

    raise RuntimeError("Falha ao gerar conteúdo: todos os modelos e tentativas foram esgotados.")

def montar_prompt_documento_completo(tecnologia: str) -> str:
    return f'''
Tecnologia-Alvo: {tecnologia}

1. Requisitos e Métodos de Coleta de Logs
1.1. Suporte a Protocolos de Coleta:
Qual é a versão/edição da tecnologia que oferece suporte para coleta de logs via TCP/UDP? (Preferencialmente)
Se não for TCP/UDP, qual é a versão/edição que oferece suporte à coleta via API?

1.2. Configuração de Coleta:
Detalhe como é configurada a coleta de logs para o método preferencial (TCP/UDP, ou API, se for a única opção). Inclua comandos ou passos chave.
Alternativa Filebeat (se aplicável): Qual é a versão/edição que permite a instalação do Filebeat em um diretório específico onde o arquivo de log é gerado? Descreva brevemente a configuração necessária (ex: arquivo de configuração, input path).

2. Versões e Custos de Licenciamento
Quais são as principais versões/edições da tecnologia?
Para cada versão relevante para a coleta de logs de segurança, qual é o custo com licença (ou modelo de licenciamento)? (Ex: Gratuita, Paga - Enterprise, por usuário, etc.)

3. Eventos de Segurança Relevantes e Exemplos
Quais são os 5 a 10 eventos de segurança mais relevantes que devem ser monitorados? (Ex: Falha de Login, Criação de Usuário Privilegiado, Mudança de Configuração Crítica, etc.)
Forneça logs de exemplo (cerca de 3 a 5 logs) que sejam relevantes para a segurança.

4. Links de Referência
Adicione links de documentação oficiais da tecnologia para os seguintes tópicos:
- Documentação de Coleta/Exportação de Logs.
- Documentação de Eventos de Segurança/Auditoria.

5. Estimativa de Volumetria
Com base em um ambiente corporativo de médio a grande porte, forneça uma estimativa de volumetria dos dados de logs gerados por esta tecnologia (exemplo: GB/dia, quantidade de Eventos por Segundo - EPS médio). Inclua breves fatores que podem aumentar ou diminuir consideravelmente esse volume.

{SEPARADOR_CATALOGO}{MARCADOR_CATALOGO}
Gere uma tabela com o Catálogo de Dados para os campos mais importantes dos logs de segurança, usando a padronização Elastic Common Schema (ECS) como recomendação.
Campos do catálogo de dados: Nome do Campo Original (na ferramenta), Nome do campo ECS, Descrição, Tipo de dados, Exemplo de valor, Tipo de dado ECS.
'''

def montar_prompt_procedimento_docx(tecnologia: str, procedimento: str) -> str:
    return f'''
Tecnologia-Alvo: {tecnologia}

Com base no levantamento abaixo, escreva o conteúdo de um documento formal de PROCEDIMENTO DE COLETA de logs dessa tecnologia, destinado à equipe do cliente que vai executar a configuração.
Use o método de coleta preferencial do levantamento (TCP/UDP; API somente se for a única opção; Filebeat se for o caso). Não inclua licenciamento, volumetria, catálogo de dados nem links.

Responda SOMENTE com um JSON válido, em português, no formato:
{{
  "introducao": ["1 a 3 parágrafos: o que é a tecnologia, qual o método de coleta escolhido e por quê"],
  "pre_requisitos": ["acessos, versões/edições, portas e informações necessárias antes de começar"],
  "passos": [
    {{
      "titulo": "título curto do passo",
      "descricao": "o que fazer neste passo",
      "itens": ["ações ou parâmetros a configurar neste passo (pode ser vazio)"],
      "codigo": "comandos ou trecho de configuração, um por linha (string vazia se não houver)"
    }}
  ],
  "validacao": ["como confirmar que os logs estão sendo recebidos"]
}}

Regras: texto puro, sem markdown (sem **, #, crases ou listas com hífen dentro das strings); não numere os títulos dos passos; onde houver valores do ambiente do cliente use marcadores como <IP_DO_COLETOR> e <PORTA>.

--- LEVANTAMENTO ---
{procedimento}
'''

def separar_procedimento_catalogo(resposta_completa: str):
    if SEPARADOR_CATALOGO in resposta_completa:
        procedimento, catalogo_com_marcador = resposta_completa.split(SEPARADOR_CATALOGO, 1)
        return procedimento, catalogo_com_marcador.replace(MARCADOR_CATALOGO, "").strip()

    if MARCADOR_CATALOGO in resposta_completa:
        procedimento, catalogo = resposta_completa.split(MARCADOR_CATALOGO, 1)
        return procedimento, f"{MARCADOR_CATALOGO}\n{catalogo.strip()}"

    return resposta_completa, None

def extrair_json(resposta: str) -> dict:
    texto = resposta.strip()
    if texto.startswith("```"):
        texto = texto.split("\n", 1)[1].rsplit("```", 1)[0]
    conteudo = json.loads(texto)
    if not isinstance(conteudo, dict) or not conteudo.get("passos"):
        raise ValueError("JSON sem a chave 'passos' preenchida.")
    return conteudo

def salvar_texto(caminho: str, conteudo: str) -> None:
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write(conteudo.strip())

def gerar_documento_completo(tecnologia, nome_base, diretorio, API_KEY, MODELOS, RETRY, logger) -> str:
    nome_arquivo_procedimento = f"{diretorio}/procedimento_{nome_base}.txt"
    nome_arquivo_catalogo = f"{diretorio}/catalogo_{nome_base}.txt"

    resposta_completa = gerar_resposta_gemini_com_fallback(montar_prompt_documento_completo(tecnologia), API_KEY, MODELOS, RETRY, logger)
    procedimento, catalogo = separar_procedimento_catalogo(resposta_completa)

    if catalogo is None:
        catalogo = "ERRO: Não foi possível extrair o Catálogo de Dados de forma estruturada."
        logger.warning(f"Não foi possível separar o Catálogo de Dados para '{tecnologia}'. Todo o conteúdo salvo em: {nome_arquivo_procedimento}")

    salvar_texto(nome_arquivo_procedimento, procedimento)
    logger.info(f"Procedimento de '{tecnologia}' salvo com sucesso em: {nome_arquivo_procedimento}")

    salvar_texto(nome_arquivo_catalogo, catalogo)
    logger.info(f"Catálogo de Dados de '{tecnologia}' salvo com sucesso em: {nome_arquivo_catalogo}")

    return procedimento

def gerar_documento_procedimento_coleta(tecnologia, nome_base, diretorio, procedimento, MODELO_DOCX, FORMATO_SAIDA, LIBREOFFICE, API_KEY, MODELOS, RETRY, logger) -> None:
    nome_arquivo_saida = f"{diretorio}/procedimento_coleta_{nome_base}.{FORMATO_SAIDA}"
    nome_arquivo_json = f"{diretorio}/procedimento_coleta_{nome_base}.json"

    resposta = gerar_resposta_gemini_com_fallback(
        montar_prompt_procedimento_docx(tecnologia, procedimento), API_KEY, MODELOS, RETRY, logger,
        config_geracao={"response_mime_type": "application/json"},
    )

    try:
        conteudo = extrair_json(resposta)
    except (json.JSONDecodeError, ValueError, IndexError) as e:
        salvar_texto(nome_arquivo_json, resposta)
        raise RuntimeError(f"Resposta inválida para o documento de procedimento ({e}). Resposta bruta salva em: {nome_arquivo_json}")

    if FORMATO_SAIDA == "pdf":
        gerar_pdf_procedimento(MODELO_DOCX, nome_arquivo_saida, tecnologia, conteudo, LIBREOFFICE)
    else:
        gerar_docx_procedimento(MODELO_DOCX, nome_arquivo_saida, tecnologia, conteudo)
    logger.info(f"Documento de Procedimento de Coleta de '{tecnologia}' salvo com sucesso em: {nome_arquivo_saida}")

def main():
    logger = setup_logger("execucao.log")
    logger.info("Iniciando a execução.")

    try:
        config = carregar_configuracao()
        logger.info(f"Arquivo de configuração '{CONFIG_FILE}' encontrado com sucesso.")
    except FileNotFoundError:
        logger.error(f"Erro: Arquivo '{CONFIG_FILE}' não encontrado. Abortando.")
        return
    except yaml.YAMLError as e:
        logger.error(f"Erro: Formato YAML inválido no arquivo '{CONFIG_FILE}': {e}. Abortando.")
        return

    try:
        API_KEY = config["API_KEY"]
        TECNOLOGIAS = config["TECNOLOGIAS"] or []
        RETRY = config.get("RETRY", 2)
        MODELOS = config.get("MODELOS", ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"])
        MODELO_DOCX = config.get("MODELO_DOCX", MODELO_DOCX_PADRAO)
        FORMATO_SAIDA = str(config.get("FORMATO_SAIDA", FORMATO_SAIDA_PADRAO)).strip().lower()
    except KeyError as e:
        logger.error(f"Erro: Chave '{e.args[0]}' ausente no arquivo de configuração. Abortando.")
        return

    if not os.path.isfile(MODELO_DOCX):
        logger.error(f"Erro: Modelo DOCX '{MODELO_DOCX}' não encontrado. Abortando.")
        return

    if FORMATO_SAIDA not in FORMATOS_SAIDA:
        logger.error(f"Erro: FORMATO_SAIDA '{FORMATO_SAIDA}' inválido. Use um destes: {', '.join(FORMATOS_SAIDA)}. Abortando.")
        return

    LIBREOFFICE = localizar_libreoffice(config.get("LIBREOFFICE")) if FORMATO_SAIDA == "pdf" else None
    if FORMATO_SAIDA == "pdf" and not LIBREOFFICE:
        logger.error("Erro: LibreOffice não encontrado (necessário para gerar o PDF). Instale-o ou informe o executável na chave 'LIBREOFFICE' do config. Abortando.")
        return

    for tecnologia in [t.strip() for t in TECNOLOGIAS if t and t.strip()]:
        nome_base = tecnologia.replace(' ', '_').lower().replace('-', '_')
        diretorio = f"{OUTPUT_DIR}/{nome_base}"
        os.makedirs(diretorio, exist_ok=True)

        logger.info(f"Processando a tecnologia '{tecnologia}'...")

        try:
            procedimento = gerar_documento_completo(tecnologia, nome_base, diretorio, API_KEY, MODELOS, RETRY, logger)
            gerar_documento_procedimento_coleta(tecnologia, nome_base, diretorio, procedimento, MODELO_DOCX, FORMATO_SAIDA, LIBREOFFICE, API_KEY, MODELOS, RETRY, logger)
        except RuntimeError as e:
            logger.error(f"Não foi possível processar '{tecnologia}'. Motivo: {e}")
        except Exception as e:
            logger.error(f"Ocorreu um erro inesperado ao processar '{tecnologia}': {e}")

        time.sleep(15)

    logger.info("Execução concluída.")

if __name__ == "__main__":
    main()
