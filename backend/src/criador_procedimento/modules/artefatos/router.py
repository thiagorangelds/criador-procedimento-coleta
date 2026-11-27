from typing import List

from fastapi import APIRouter
from fastapi.responses import FileResponse

from criador_procedimento.core.security import PROTEGIDO
from criador_procedimento.modules.artefatos import service
from criador_procedimento.modules.artefatos.schemas import Arquivo
from criador_procedimento.shared.exceptions import erro_http

router = APIRouter(prefix="/api/artefatos", tags=["artefatos"], dependencies=PROTEGIDO)


@router.get("", response_model=List[Arquivo], summary="Todos os arquivos já gerados")
def listar_artefatos():
    return service.listar()


@router.get("/{caminho:path}", responses={404: {"description": "Arquivo não encontrado"}}, summary="Baixa um arquivo gerado")
def baixar_artefato(caminho: str):
    alvo = service.localizar(caminho)
    if alvo is None:
        raise erro_http(404, "Arquivo não encontrado.")
    return FileResponse(alvo, filename=alvo.name)
