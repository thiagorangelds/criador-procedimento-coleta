"""Logger da aplicação.

Um logger só, `criador`, com saída no terminal e no `execucao.log` rotativo.
Cada job cria um filho `criador.job.<id>`, que propaga para cá — por isso o log
de um job aparece no arquivo sem nenhum handler extra.
"""

import logging
import logging.handlers

from criador_procedimento.shared import paths

NOME_LOGGER = "criador"
FORMATO = "%(asctime)s [%(levelname)s] %(message)s"
TAMANHO_MAXIMO = 10 * 1024 * 1024


def obter_logger() -> logging.Logger:
    logger = logging.getLogger(NOME_LOGGER)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    terminal = logging.StreamHandler()
    terminal.setFormatter(logging.Formatter(FORMATO))
    logger.addHandler(terminal)

    try:
        arquivo = logging.handlers.RotatingFileHandler(paths.ARQUIVO_LOG, maxBytes=TAMANHO_MAXIMO, backupCount=2)
    except OSError as e:  # pasta somente leitura num container, por exemplo
        logger.warning(f"Sem log em arquivo ({paths.ARQUIVO_LOG}): {e}")
    else:
        arquivo.setFormatter(logging.Formatter(FORMATO))
        logger.addHandler(arquivo)

    return logger
