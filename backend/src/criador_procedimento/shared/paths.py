"""Todo caminho do projeto, absoluto e derivado do próprio arquivo.

A versão anterior fazia `os.chdir()` no import e deixava tudo relativo ao
diretório da aplicação, o que quebrava assim que o processo subisse de outro
lugar. Aqui nada depende do diretório de trabalho.

A pasta de saída é a única que aceita ser movida por fora, com
`CRIADOR_PASTA_SAIDA`: num container ela precisa cair num volume, senão cada
deploy joga fora os documentos já gerados.
"""

import os
from pathlib import Path

PASTA_PACOTE = Path(__file__).resolve().parent.parent
PASTA_BACKEND = PASTA_PACOTE.parent.parent          # .../backend
PASTA_RAIZ = PASTA_BACKEND.parent                   # .../criador-procedimento-coleta

PASTA_FRONTEND = PASTA_RAIZ / "frontend"
ARQUIVO_INDEX = PASTA_FRONTEND / "index.html"

ARQUIVO_CONFIG = PASTA_BACKEND / "config.yml"
ARQUIVO_ENV = PASTA_BACKEND / ".env"
ARQUIVO_LOG = PASTA_BACKEND / "execucao.log"
PASTA_SAIDA = Path(os.environ.get("CRIADOR_PASTA_SAIDA") or (PASTA_BACKEND / "procedimentos"))
MODELO_DOCX_PADRAO = PASTA_BACKEND / "templates" / "modelo_procedimento_coleta.docx"


def do_backend(caminho) -> Path:
    """Resolve caminho vindo da configuração: absoluto passa direto, relativo vale a partir de backend/."""
    caminho = Path(caminho)
    return caminho if caminho.is_absolute() else PASTA_BACKEND / caminho
