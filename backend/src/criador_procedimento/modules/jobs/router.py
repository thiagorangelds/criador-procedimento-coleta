from typing import List

from fastapi import APIRouter, Query

from criador_procedimento.core import config
from criador_procedimento.core.security import PROTEGIDO
from criador_procedimento.modules.artefatos import service as artefatos
from criador_procedimento.modules.geracao import service as geracao
from criador_procedimento.modules.jobs import service
from criador_procedimento.modules.jobs.models import Job
from criador_procedimento.modules.jobs.schemas import JobDetalhe, JobResumo, LogDoJob, NovoJob
from criador_procedimento.shared.exceptions import erro_http

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=PROTEGIDO)


def _resumo(job: Job) -> dict:
    return {
        "id": job.id,
        "estado": job.estado,
        "tecnologias": job.tecnologias,
        "erro": job.erro,
        "criado_em": job.criado_em,
        "iniciado_em": job.iniciado_em,
        "concluido_em": job.concluido_em,
        "total_log": job.log()[1],
    }


def _detalhe(job: Job) -> dict:
    return {**_resumo(job), "resultados": [
        {
            "tecnologia": r.tecnologia,
            "nome_base": r.nome_base,
            "erro": r.erro,
            "arquivos": artefatos.publicar(r.arquivos),
        }
        for r in job.resultados
    ]}


def _job_ou_404(job_id: str) -> Job:
    job = service.gerenciador().obter(job_id)
    if job is None:
        raise erro_http(404, f"Job '{job_id}' não encontrado.")
    return job


@router.post("", response_model=JobResumo, status_code=202,
             responses={400: {"description": "Configuração do servidor ou pedido inválido"}},
             summary="Enfileira a geração de uma ou mais tecnologias")
def criar_job(pedido: NovoJob):
    tecnologias = [t.strip() for t in pedido.tecnologias if t and t.strip()]
    if not tecnologias:
        raise erro_http(400, "Informe ao menos uma tecnologia.")

    ajustes = config.geracao()
    formato = (pedido.formato_saida or ajustes.formato_saida).strip().lower()

    erros = geracao.validar(ajustes, formato)
    if erros:
        raise erro_http(400, *erros)

    job = service.gerenciador().enfileirar(
        tecnologias, ajustes.com(tecnologias=tecnologias, formato_saida=formato)
    )
    return _resumo(job)


@router.get("", response_model=List[JobResumo], summary="Jobs recentes, do mais novo para o mais antigo")
def listar_jobs(limite: int = Query(default=50, ge=1, le=100)):
    return [_resumo(job) for job in service.gerenciador().listar(limite)]


@router.get("/{job_id}", response_model=JobDetalhe, responses={404: {"description": "Job não encontrado"}},
            summary="Estado do job e os arquivos que ele produziu")
def obter_job(job_id: str):
    return _detalhe(_job_ou_404(job_id))


@router.get("/{job_id}/log", response_model=LogDoJob, responses={404: {"description": "Job não encontrado"}},
            summary="Log do job a partir de uma linha")
def log_do_job(job_id: str, desde: int = Query(default=0, ge=0)):
    job = _job_ou_404(job_id)
    linhas, total = job.log(desde)
    return {"estado": job.estado, "linhas": linhas, "total": total}


@router.post("/{job_id}/cancelar", response_model=JobResumo,
             responses={404: {"description": "Job não encontrado"}, 409: {"description": "Job já terminou"}},
             summary="Cancela o job; a geração para antes da próxima tecnologia")
def cancelar_job(job_id: str):
    job = _job_ou_404(job_id)
    if not service.gerenciador().cancelar(job):
        raise erro_http(409, f"O job {job_id} já terminou ({job.estado.value}).")
    return _resumo(job)
