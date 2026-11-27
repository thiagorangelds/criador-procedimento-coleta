"""Exceções do domínio e a forma única de erro da API.

Toda resposta de erro sai como `{"erros": ["..."]}`, inclusive as que o próprio
FastAPI levantaria com outro formato — é o que o front e as integrações
esperam, sem ter que tratar dois contratos.
"""

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErroDeConfiguracao(ValueError):
    """Configuração que impede a execução começar (chave ausente, formato inválido)."""


class ErroDeGeracao(RuntimeError):
    """Falha ao gerar o conteúdo de uma tecnologia."""


def erro_http(status: int, *mensagens: str, headers: dict = None) -> HTTPException:
    return HTTPException(status_code=status, detail=list(mensagens), headers=headers)


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http(request, exc: HTTPException):
        detalhe = exc.detail if isinstance(exc.detail, list) else [str(exc.detail)]
        return JSONResponse(status_code=exc.status_code, content={"erros": detalhe}, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validacao(request, exc: RequestValidationError):
        erros = [f"{'.'.join(str(p) for p in e['loc'][1:]) or 'corpo'}: {e['msg']}" for e in exc.errors()]
        return JSONResponse(status_code=400, content={"erros": erros})
