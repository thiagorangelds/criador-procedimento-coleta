"""Regras de entrega dos artefatos: a URL de download e a lista publicada."""

import urllib.parse
from typing import Iterable, List

from criador_procedimento.modules.artefatos import repository
from criador_procedimento.modules.artefatos.models import Artefato

PREFIXO_DOWNLOAD = "/api/artefatos/"


def url(caminho_relativo: str) -> str:
    return PREFIXO_DOWNLOAD + "/".join(urllib.parse.quote(p) for p in caminho_relativo.split("/"))


def publicar(artefatos: Iterable) -> List[dict]:
    """Converte entidades (daqui ou da geração) no formato com `url` que a API devolve."""
    return [
        {"caminho": a.caminho, "tamanho": a.tamanho, "modificado": a.modificado, "url": url(a.caminho)}
        for a in artefatos
    ]


def listar() -> List[dict]:
    return publicar(repository.listar())


def localizar(relativo: str):
    return repository.resolver(relativo)
