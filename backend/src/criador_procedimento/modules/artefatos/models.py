"""Entidade de um arquivo gerado, do ponto de vista de quem o entrega."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Artefato:
    caminho: str      # relativo à pasta de saída, com "/" como separador
    tamanho: int
    modificado: float

    @property
    def pasta(self) -> str:
        return self.caminho.split("/", 1)[0] if "/" in self.caminho else ""

    @property
    def nome(self) -> str:
        return self.caminho.rsplit("/", 1)[-1]
