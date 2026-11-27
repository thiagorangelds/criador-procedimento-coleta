from dataclasses import asdict

from fastapi import APIRouter

from criador_procedimento.core.security import PROTEGIDO
from criador_procedimento.modules.sistema import service
from criador_procedimento.modules.sistema.schemas import AjustesDoServidor, Saude

router = APIRouter(prefix="/api", tags=["servidor"])


# Fora do token de propósito: é o health check do balanceador, e é por ele que
# a interface descobre que precisa pedir um token antes de mais nada.
@router.get("/saude", response_model=Saude, summary="Estado do servidor (não exige token)")
def saude():
    return asdict(service.saude())


@router.get("/config", response_model=AjustesDoServidor, dependencies=PROTEGIDO,
            summary="Ajustes do servidor (somente leitura)")
def ajustes():
    return asdict(service.ajustes())
