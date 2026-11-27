"""Monta as duas visões do servidor: saúde e ajustes."""

from criador_procedimento import __version__
from criador_procedimento.core.config import FORMATOS_SAIDA
from criador_procedimento.modules.jobs import service as jobs
from criador_procedimento.modules.sistema import repository
from criador_procedimento.modules.sistema.models import Ajustes, Saude


def saude() -> Saude:
    ativo = jobs.gerenciador().ativo()
    return Saude(
        ok=True,
        versao=__version__,
        auth_requerida=repository.ajustes_de_servidor().exige_token,
        api_key_definida=bool(repository.ajustes_de_geracao().api_key),
        job_ativo=ativo.id if ativo else None,
    )


def ajustes() -> Ajustes:
    config = repository.ajustes_de_geracao()
    return Ajustes(
        formato_saida=config.formato_saida,
        formatos_saida=list(FORMATOS_SAIDA),
        modelos=config.modelos,
        retry=config.retry,
        pdf_disponivel=repository.pdf_disponivel(config),
        api_key_definida=bool(config.api_key),
        api_key_origem=repository.origem_da_api_key(),
        arquivo_config=repository.caminho_do_config(),
    )
