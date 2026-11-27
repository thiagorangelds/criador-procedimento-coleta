"""Leitura da pasta de saída.

A resolução de caminho é o ponto sensível: o que chega na URL vem de fora, e só
pode sair daqui o que estiver **dentro** da pasta de saída depois de resolver
symlink e `..`.
"""

import os
from pathlib import Path
from typing import List, Optional

from criador_procedimento.modules.artefatos.models import Artefato
from criador_procedimento.shared import paths


def listar(pasta_saida=None) -> List[Artefato]:
    """Todos os arquivos gerados, do mais recente para o mais antigo."""
    pasta_saida = Path(pasta_saida or paths.PASTA_SAIDA)
    artefatos = []
    for raiz, _, nomes in os.walk(pasta_saida):
        for nome in nomes:
            caminho = Path(raiz) / nome
            artefatos.append(Artefato(
                caminho=str(caminho.relative_to(pasta_saida)).replace(os.sep, "/"),
                tamanho=caminho.stat().st_size,
                modificado=caminho.stat().st_mtime,
            ))
    return sorted(artefatos, key=lambda a: a.modificado, reverse=True)


def resolver(relativo: str, pasta_saida=None) -> Optional[Path]:
    """Caminho absoluto do artefato, ou None se escapar da pasta de saída ou não existir."""
    base = Path(pasta_saida or paths.PASTA_SAIDA).resolve()
    try:
        alvo = (base / relativo).resolve()
        alvo.relative_to(base)
    except (ValueError, OSError):
        return None
    return alvo if alvo.is_file() else None
