"""Entidades do job de geração."""

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from criador_procedimento.core.config import ConfiguracaoGeracao
from criador_procedimento.modules.geracao.models import ResultadoTecnologia


class EstadoDoJob(str, Enum):
    NA_FILA = "na_fila"
    EXECUTANDO = "executando"
    CONCLUIDO = "concluido"
    FALHOU = "falhou"
    CANCELADO = "cancelado"

    @property
    def final(self) -> bool:
        return self in (EstadoDoJob.CONCLUIDO, EstadoDoJob.FALHOU, EstadoDoJob.CANCELADO)


@dataclass
class Job:
    tecnologias: List[str]
    config: ConfiguracaoGeracao
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    estado: EstadoDoJob = EstadoDoJob.NA_FILA
    erro: Optional[str] = None
    resultados: List[ResultadoTecnologia] = field(default_factory=list)
    criado_em: float = field(default_factory=time.time)
    iniciado_em: Optional[float] = None
    concluido_em: Optional[float] = None
    cancelar: threading.Event = field(default_factory=threading.Event)
    _linhas: List[str] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def finalizado(self) -> bool:
        return self.estado.final

    def registrar(self, linha: str) -> None:
        with self._lock:
            self._linhas.append(linha)

    def log(self, desde: int = 0):
        with self._lock:
            return self._linhas[desde:], len(self._linhas)

    def encerrar(self, estado: EstadoDoJob, erro: str = None) -> None:
        self.estado = estado
        self.erro = erro
        self.concluido_em = time.time()
