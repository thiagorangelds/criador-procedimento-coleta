"""As fontes externas que o estado do servidor consulta: configuração e LibreOffice."""

from criador_procedimento.core import config
from criador_procedimento.modules.geracao import service as geracao
from criador_procedimento.shared import paths


def ajustes_de_geracao() -> config.ConfiguracaoGeracao:
    return config.geracao()


def ajustes_de_servidor() -> config.ConfiguracaoServidor:
    return config.servidor()


def origem_da_api_key() -> str:
    return config.origem_api_key()


def pdf_disponivel(ajustes: config.ConfiguracaoGeracao) -> bool:
    return geracao.pdf_disponivel(ajustes)


def caminho_do_config() -> str:
    return str(paths.ARQUIVO_CONFIG)
