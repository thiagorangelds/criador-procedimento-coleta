from google import genai
from google.genai.errors import APIError
import json
import logging
import logging.handlers
import os

CONFIG_FILE = "config.json"

def setup_logger(log_file: str) -> logging.Logger:
    logger = logging.getLogger("HalcyonLogger")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    # Configuração para Stream (Console)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(stream_handler)
    
    # Configuração para Arquivo de Log
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1024 * 1024 * 10, backupCount=2
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(file_handler)

    return logger

def carregar_configuracao():
    """Carrega as configurações do arquivo config.json."""
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
        return config
    
def gerar_resposta_gemini_direto(prompt: str, api_key: str) -> str:
    """Chama a API do Gemini e retorna o texto da resposta."""
    client = genai.Client(api_key=api_key)
    model_name = 'gemini-2.5-flash'
    
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    
    return response.text

def main():
    logger = setup_logger("execucao.log")
    logger.info("Iniciando a execução.")
    
    try:
        config = carregar_configuracao()
        logger.info(f"Arquivo de configuração '{CONFIG_FILE}' encontrado com sucesso.")
    except FileNotFoundError:
        logger.error(f"Erro: Arquivo '{CONFIG_FILE}' não encontrado. Abortando.")
        return
    except json.JSONDecodeError:
        logger.error(f"Erro: Formato JSON inválido no arquivo '{CONFIG_FILE}'. Abortando.")
        return
    
    try:
        API_KEY = config["API_KEY"]
        TECNOLOGIAS = config["TECNOLOGIAS"]
    except KeyError as e:
        logger.error(f"Erro: Chave '{e.args[0]}' ausente no arquivo de configuração. Abortando.")
        return

    for tecnologia in TECNOLOGIAS:
        nome_base = tecnologia.replace(' ', '_').lower().replace('-', '_')
        nome_arquivo = f"procedimentos/procedimento_{nome_base}.txt"
        
        prompt = f'''Criação de Procedimento de Configuração de Coleta de Logs para a {tecnologia} que eu preciso Integrar no meu SIEM próprio. Com as seguintes requisitos:

Qual versão tem suporte para coleta via TCP/UDP (preferencialmente) ou API ou Disponibilidade de instalação de filebeat em diretório específico que gerar o arquivo de log pela ferramenta e como é configurado?
Quais versões e qual custo com licença de cada versão?
Quais eventos referente a segurança são relevantes?
Adicione logs de exemplo relevantes para segurança;
Adicione catalogo de dados desses logos relevantes para segurança;
'''
        
        logger.info(f"Gerando procedimento para '{tecnologia}'...")

        try:
            
            resposta = gerar_resposta_gemini_direto(prompt, API_KEY)
            
        
            with open(nome_arquivo, 'w', encoding='utf-8') as f:
                f.write(resposta)
            
            logger.info(f"Procedimento de '{tecnologia}' salvo com sucesso em: {nome_arquivo}")
            
        except APIError as e:
            logger.error(f"Erro na API ao processar '{tecnologia}'. Detalhe: {e}")
        except Exception as e:
            logger.error(f"Ocorreu um erro inesperado ao processar '{tecnologia}': {e}")
            
    logger.info("Execução concluída.")

if __name__ == "__main__":
    main()