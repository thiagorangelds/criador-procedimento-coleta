"""Autenticação da API.

Token opcional: sem `API_TOKEN` configurado, nada é exigido — é o caso da
instalação local, presa a `127.0.0.1`. Com token, toda rota `/api` passa por
aqui, menos `/api/saude`, que é o health check do balanceador.

O token vai em cabeçalho, nunca em query string: query string vaza em log de
proxy e no histórico do navegador.
"""

import secrets
from typing import Optional

from fastapi import Depends, Header

from criador_procedimento.core import config
from criador_procedimento.shared.exceptions import erro_http

CABECALHO_ALTERNATIVO = "X-API-Token"


def verificar_token(
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None, alias=CABECALHO_ALTERNATIVO),
) -> None:
    esperado = config.servidor().api_token
    if not esperado:
        return

    enviado = ""
    if authorization and authorization.strip().lower().startswith("bearer "):
        enviado = authorization.strip()[7:].strip()
    elif x_api_token:
        enviado = x_api_token.strip()

    if not secrets.compare_digest(enviado, esperado):
        raise erro_http(
            401,
            f"Token ausente ou inválido. Envie 'Authorization: Bearer <token>' ou '{CABECALHO_ALTERNATIVO}: <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Usado como `dependencies=PROTEGIDO` na declaração de cada rota.
PROTEGIDO = [Depends(verificar_token)]
