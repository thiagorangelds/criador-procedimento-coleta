#!/usr/bin/env python3
"""Geração pela linha de comando, sem subir a API.

    criador-procedimento-gerar                              usa TECNOLOGIAS do config.yml
    criador-procedimento-gerar "Fortinet Fortigate via syslog" "Cisco ASA"
    criador-procedimento-gerar --formato pdf "Imperva WAF"
"""

import argparse

from criador_procedimento.core import config
from criador_procedimento.core.logging import obter_logger
from criador_procedimento.modules.geracao import service as geracao
from criador_procedimento.shared import paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera os documentos de coleta pela linha de comando.")
    parser.add_argument("tecnologias", nargs="*", help='Ex.: "AWS GuardDuty via S3 + SQS". Sem argumento, usa TECNOLOGIAS do config.yml.')
    parser.add_argument("--formato", choices=config.FORMATOS_SAIDA, default=None, help="Sobrescreve FORMATO_SAIDA do config.yml.")
    args = parser.parse_args()

    logger = obter_logger()
    logger.info("Iniciando a execução.")

    ajustes = config.geracao()
    tecnologias = args.tecnologias or ajustes.tecnologias
    formato = (args.formato or ajustes.formato_saida).strip().lower()

    if not tecnologias:
        logger.error(f"Nenhuma tecnologia informada e TECNOLOGIAS está vazio em '{paths.ARQUIVO_CONFIG}'. Abortando.")
        return 1

    erros = geracao.validar(ajustes, formato)
    if erros:
        for erro in erros:
            logger.error(erro)
        return 1

    resultado = geracao.executar(ajustes.com(tecnologias=tecnologias, formato_saida=formato), logger)
    return 0 if resultado.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
