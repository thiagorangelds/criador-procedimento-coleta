"""Entidades da geração — o que o motor produz, antes de virar resposta HTTP."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ArquivoGerado:
    caminho: str          # relativo à pasta de saída, com "/" como separador
    tamanho: int
    modificado: float


@dataclass
class ResultadoTecnologia:
    tecnologia: str
    nome_base: str
    erro: Optional[str] = None
    arquivos: List[ArquivoGerado] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.erro is None


@dataclass
class ResultadoExecucao:
    tecnologias: List[ResultadoTecnologia] = field(default_factory=list)
    cancelado: bool = False

    @property
    def ok(self) -> bool:
        return not self.cancelado and all(t.ok for t in self.tecnologias)

    @property
    def erros(self) -> List[str]:
        return [f"{t.tecnologia}: {t.erro}" for t in self.tecnologias if t.erro]


@dataclass(frozen=True)
class DestinoDaTecnologia:
    """Onde os arquivos de uma tecnologia são gravados."""

    tecnologia: str
    nome_base: str
    diretorio: Path

    def arquivo(self, nome: str) -> Path:
        return self.diretorio / nome
