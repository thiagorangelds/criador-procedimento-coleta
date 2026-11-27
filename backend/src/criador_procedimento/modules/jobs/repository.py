"""Onde os jobs ficam guardados.

**Memória do processo, não banco.** Reiniciar perde o histórico (os arquivos
gerados ficam no disco); mais de uma réplica exige trocar isto por algo
compartilhado antes.
"""

import threading
from typing import List, Optional

from criador_procedimento.modules.jobs.models import EstadoDoJob, Job

HISTORICO_MAXIMO = 100


class RepositorioDeJobs:
    def __init__(self, historico_maximo: int = HISTORICO_MAXIMO):
        self._jobs = {}
        self._ordem = []
        self._historico_maximo = historico_maximo
        self._lock = threading.Lock()

    def guardar(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.id] = job
            self._ordem.append(job.id)
            self._podar()
        return job

    def obter(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def listar(self, limite: int = 50) -> List[Job]:
        with self._lock:
            ids = list(reversed(self._ordem))[:limite]
            return [self._jobs[i] for i in ids if i in self._jobs]

    def primeiro_na_fila(self) -> Optional[Job]:
        with self._lock:
            for job_id in self._ordem:
                job = self._jobs.get(job_id)
                if job is not None and job.estado == EstadoDoJob.NA_FILA:
                    return job
        return None

    def _podar(self) -> None:
        """Descarta o histórico antigo. Job não finalizado nunca é descartado."""
        while len(self._ordem) > self._historico_maximo:
            antigo = self._ordem[0]
            job = self._jobs.get(antigo)
            if job is not None and not job.finalizado:
                break
            self._ordem.pop(0)
            self._jobs.pop(antigo, None)
