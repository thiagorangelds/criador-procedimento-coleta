"""Fila de geração: um worker, em série.

Dois jobs em paralelo só dividiriam a mesma cota do Gemini e disputariam o
LibreOffice, então a fila tem **um consumidor só**. O `POST` responde na hora de
qualquer jeito, com o job em `na_fila`.

Cada job tem o seu próprio log: o logger `criador.job.<id>` propaga para o
logger `criador`, então o mesmo texto continua indo para o `execucao.log`.
"""

import logging
import queue
import threading
import time
from typing import List, Optional

from criador_procedimento.core.config import ConfiguracaoGeracao
from criador_procedimento.core.logging import NOME_LOGGER, obter_logger
from criador_procedimento.modules.geracao import service as geracao
from criador_procedimento.modules.jobs.models import EstadoDoJob, Job
from criador_procedimento.modules.jobs.repository import RepositorioDeJobs
from criador_procedimento.shared.exceptions import ErroDeConfiguracao


class _HandlerDeJob(logging.Handler):
    def __init__(self, job: Job):
        super().__init__()
        self.job = job
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))

    def emit(self, record):
        self.job.registrar(self.format(record))


class GerenciadorDeJobs:
    def __init__(self, logger: logging.Logger = None, repositorio: RepositorioDeJobs = None):
        self.logger = logger or obter_logger()
        self.repositorio = repositorio or RepositorioDeJobs()
        self._fila = queue.Queue()
        self._atual = None
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._consumir, name="worker-jobs", daemon=True)
        self._worker.start()

    # ---- consulta -------------------------------------------------------

    def obter(self, job_id: str) -> Optional[Job]:
        return self.repositorio.obter(job_id)

    def listar(self, limite: int = 50) -> List[Job]:
        return self.repositorio.listar(limite)

    def ativo(self) -> Optional[Job]:
        """O job executando ou, na falta dele, o primeiro da fila."""
        with self._lock:
            atual = self._atual
        if atual is not None and not atual.finalizado:
            return atual
        return self.repositorio.primeiro_na_fila()

    # ---- comandos -------------------------------------------------------

    def enfileirar(self, tecnologias: List[str], config: ConfiguracaoGeracao) -> Job:
        job = self.repositorio.guardar(Job(tecnologias=list(tecnologias), config=config))
        self._fila.put(job.id)
        self.logger.info(f"Job {job.id} na fila: {', '.join(job.tecnologias)}.")
        return job

    def cancelar(self, job: Job) -> bool:
        if job.finalizado:
            return False
        job.cancelar.set()
        if job.estado == EstadoDoJob.NA_FILA:
            job.encerrar(EstadoDoJob.CANCELADO)
        self.logger.warning(f"Cancelamento do job {job.id} solicitado; a geração para antes da próxima tecnologia.")
        return True

    # ---- worker ---------------------------------------------------------

    def _consumir(self) -> None:
        while True:
            job_id = self._fila.get()
            try:
                job = self.repositorio.obter(job_id)
                if job is not None and job.estado == EstadoDoJob.NA_FILA and not job.cancelar.is_set():
                    self._rodar(job)
            except Exception as e:  # o worker não pode morrer e levar a fila junto
                self.logger.error(f"Erro inesperado no worker do job {job_id}: {e}")
            finally:
                self._fila.task_done()

    def _rodar(self, job: Job) -> None:
        with self._lock:
            self._atual = job
        job.estado = EstadoDoJob.EXECUTANDO
        job.iniciado_em = time.time()

        logger = logging.getLogger(f"{NOME_LOGGER}.job.{job.id}")
        logger.setLevel(logging.INFO)
        handler = _HandlerDeJob(job)
        logger.addHandler(handler)

        try:
            logger.info(f"Iniciando a geração do job {job.id}.")
            resultado = geracao.executar(job.config, logger, job.cancelar)
            job.resultados = resultado.tecnologias
            if resultado.cancelado:
                job.encerrar(EstadoDoJob.CANCELADO)
            elif resultado.ok:
                job.encerrar(EstadoDoJob.CONCLUIDO)
            else:
                job.encerrar(EstadoDoJob.FALHOU, "; ".join(resultado.erros) or "Falha na geração.")
        except ErroDeConfiguracao as e:
            job.encerrar(EstadoDoJob.FALHOU, str(e))
            logger.error(f"Configuração inválida: {e}")
        except Exception as e:
            job.encerrar(EstadoDoJob.FALHOU, str(e))
            logger.error(f"Erro inesperado na execução: {e}")
        finally:
            logger.removeHandler(handler)
            handler.close()
            with self._lock:
                if self._atual is job:
                    self._atual = None


# O worker é uma thread por processo: a instância é criada na primeira vez em
# que alguém precisa dela, e não no import, para o módulo continuar importável
# em teste sem subir thread nenhuma.
_instancia = None
_lock_instancia = threading.Lock()


def gerenciador() -> GerenciadorDeJobs:
    global _instancia
    with _lock_instancia:
        if _instancia is None:
            _instancia = GerenciadorDeJobs()
        return _instancia


def definir_gerenciador(novo: Optional[GerenciadorDeJobs]) -> None:
    """Troca a instância em uso. Existe para o teste poder isolar a fila."""
    global _instancia
    with _lock_instancia:
        _instancia = novo
