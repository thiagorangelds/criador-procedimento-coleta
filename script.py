from google import genai
from google.genai.errors import APIError
import json
import logging
import logging.handlers
import os
import time


CONFIG_FILE = "config.json"
SEPARADOR_CATALOGO = "\n\n--- INICIO_CATALOGO ---\n\n" 
MARCADOR_TOPICO_5 = "5. Catálogo de Dados de Logs de Segurança (Padronização ECS)"
OUTPUT_DIR = "procedimentos"

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
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
        return config
    
def gerar_resposta_gemini_direto(prompt: str, api_key: str) -> str:
    client = genai.Client(api_key=api_key)
    model_name = 'gemini-2.5-pro' 
    
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
        
        
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

        if not os.path.exists(f"{OUTPUT_DIR}/{nome_base}"):
            os.makedirs(f"{OUTPUT_DIR}/{nome_base}")

        nome_arquivo_procedimento = f"{OUTPUT_DIR}/{nome_base}/procedimento_{nome_base}.txt"
        nome_arquivo_catalogo = f"{OUTPUT_DIR}/{nome_base}/catalogo_{nome_base}.txt"
        
        prompt = f'''
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

Documentação de Coleta/Exportação de Logs.

Documentação de Eventos de Segurança/Auditoria.

{SEPARADOR_CATALOGO}{MARCADOR_TOPICO_5}
Gere uma tabela com o Catálogo de Dados para os campos mais importantes dos logs de segurança, usando a padronização Elastic Common Schema (ECS) como recomendação.
Campos do catálogo de dados: Nome do Campo Original (na ferramenta), Nome do campo ECS, Descrição, Tipo de dados, Exemplo de valor, Tipo de dado ECS.

'''
        
        logger.info(f"Gerando procedimento para '{tecnologia}'...")

        try:
            
            resposta_completa = gerar_resposta_gemini_direto(prompt, API_KEY)
            
            if not os.path.exists("procedimentos"):
                os.makedirs("procedimentos")
        
            
            if SEPARADOR_CATALOGO in resposta_completa:
                procedimento, catalogo_com_marcador = resposta_completa.split(SEPARADOR_CATALOGO, 1)
                catalogo = catalogo_com_marcador.replace(MARCADOR_TOPICO_5, "").strip()
                
            elif MARCADOR_TOPICO_5 in resposta_completa:
                partes = resposta_completa.split(MARCADOR_TOPICO_5, 1)
                procedimento = partes[0]
                catalogo = f"{MARCADOR_TOPICO_5}\n{partes[1].strip()}"
                
            else:
                procedimento = resposta_completa
                catalogo = "ERRO: Não foi possível extrair o Catálogo de Dados."
                logger.warning(f"Não foi possível separar o Catálogo de Dados para '{tecnologia}'. Todo o conteúdo salvo em: {nome_arquivo_procedimento}")
            
            with open(nome_arquivo_procedimento, 'w', encoding='utf-8') as f:
                f.write(procedimento.strip())
            logger.info(f"Procedimento de '{tecnologia}' salvo com sucesso em: {nome_arquivo_procedimento}")

            with open(nome_arquivo_catalogo, 'w', encoding='utf-8') as f:
                f.write(catalogo.strip())
            logger.info(f"Catálogo de Dados de '{tecnologia}' salvo com sucesso em: {nome_arquivo_catalogo}")
            
        except APIError as e:
            logger.error(f"Erro na API ao processar '{tecnologia}'. Detalhe: {e}")
        except Exception as e:
            logger.error(f"Ocorreu um erro inesperado ao processar '{tecnologia}': {e}")
        
        
        time.sleep(15)
            
    logger.info("Execução concluída.")

if __name__ == "__main__":
    main()