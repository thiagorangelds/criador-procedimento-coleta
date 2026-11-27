"""Monta o FastAPI: middlewares, handlers de erro e os routers dos módulos.

    uvicorn criador_procedimento.main:app --host 0.0.0.0 --port 8765
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from criador_procedimento import __version__
from criador_procedimento.core import config
from criador_procedimento.core.logging import obter_logger
from criador_procedimento.modules.artefatos.router import router as artefatos
from criador_procedimento.modules.jobs.router import router as jobs
from criador_procedimento.modules.sistema.router import router as sistema
from criador_procedimento.shared.exceptions import erro_http, registrar_handlers
from criador_procedimento.shared.paths import ARQUIVO_INDEX

DESCRICAO = (
    "Gera, via Gemini, o levantamento de coleta de logs de uma tecnologia, o catálogo de dados ECS "
    "e o Procedimento de Coleta em DOCX/PDF.\n\n"
    "A geração leva minutos, então é assíncrona: `POST /api/jobs` devolve 202 com o id, "
    "`GET /api/jobs/{id}` dá o estado e `GET /api/artefatos/...` baixa cada documento.\n\n"
    "Quando o servidor tem `API_TOKEN` configurado, todas as rotas `/api` exigem "
    "`Authorization: Bearer <token>` ou `X-API-Token: <token>` — menos `/api/saude`."
)


def criar_app() -> FastAPI:
    obter_logger()
    servidor = config.servidor()

    app = FastAPI(title="Criador de Procedimento de Coleta", version=__version__, description=DESCRICAO)

    if servidor.cors_origens:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=servidor.cors_origens,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "X-API-Token"],
        )

    registrar_handlers(app)

    for router in (sistema, jobs, artefatos):
        app.include_router(router)

    # A interface é um arquivo só, fora de src/: servi-la é composição da
    # aplicação, não uma feature — por isso mora aqui e não em modules/.
    @app.get("/", include_in_schema=False)
    def interface():
        if not ARQUIVO_INDEX.is_file():
            raise erro_http(404, f"Interface não encontrada em '{ARQUIVO_INDEX}'.")
        return FileResponse(ARQUIVO_INDEX, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-store"})

    return app


app = criar_app()
