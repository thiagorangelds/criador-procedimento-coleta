"""Configuração do servidor: `config.yml`, `.env` e variáveis de ambiente.

Única camada que lê o arquivo. Os módulos recebem os objetos prontos.

**Nada escreve configuração.** API key do Gemini, modelos, retry, formato
padrão e modelo Word são ajustes de quem opera o servidor. Numa instalação
compartilhada, uma requisição não pode trocar a configuração de todo mundo.

Precedência: variável de ambiente > `.env` > `config.yml` > padrão. O ambiente
nunca é escrito de volta no arquivo.

Os ajustes de **geração** são relidos a cada pedido — corrigir a API key no
`config.yml` vale na hora. Os de **servidor** (host, porta, token, CORS) são
lidos uma vez na subida e exigem reinício.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List

import yaml

from criador_procedimento.shared import paths
from criador_procedimento.shared.paths import do_backend

FORMATO_SAIDA_PADRAO = "docx"
FORMATOS_SAIDA = ("docx", "pdf")

# A forma de coleta viaja dentro do nome da tecnologia, depois deste separador:
# "AWS GuardDuty via S3 + SQS". Mudar isto quebra todo pedido já salvo por aí.
SEPARADOR_COLETA = " via "

HOST_PADRAO = "127.0.0.1"
PORTA_PADRAO = 8765
MODELOS_PADRAO = ["gemini-2.5-flash", "gemini-3.6-flash"]
RETRY_PADRAO = 5

# Variável de ambiente que sobrepõe a chave do arquivo.
ENV = {
    "API_KEY": "CRIADOR_API_KEY",
    "API_TOKEN": "CRIADOR_API_TOKEN",
    "HOST": "CRIADOR_HOST",
    "PORTA": "CRIADOR_PORTA",
    "CORS_ORIGENS": "CRIADOR_CORS_ORIGENS",
}


@dataclass(frozen=True)
class ConfiguracaoGeracao:
    api_key: str = ""
    modelos: List[str] = field(default_factory=lambda: list(MODELOS_PADRAO))
    retry: int = RETRY_PADRAO
    formato_saida: str = FORMATO_SAIDA_PADRAO
    libreoffice: str = ""
    modelo_docx: Path = paths.MODELO_DOCX_PADRAO
    # Só a CLI usa: a interface e a API mandam a lista em cada pedido.
    tecnologias: List[str] = field(default_factory=list)

    def com(self, **mudancas) -> "ConfiguracaoGeracao":
        return ConfiguracaoGeracao(**{**self.__dict__, **mudancas})


@dataclass(frozen=True)
class ConfiguracaoServidor:
    host: str = HOST_PADRAO
    porta: int = PORTA_PADRAO
    api_token: str = ""
    cors_origens: List[str] = field(default_factory=list)

    @property
    def exige_token(self) -> bool:
        return bool(self.api_token)

    @property
    def apenas_local(self) -> bool:
        return self.host in ("127.0.0.1", "localhost", "::1")


def carregar_env() -> None:
    """Lê o `.env` ao lado do config.yml, sem sobrescrever o que já veio do ambiente."""
    if not paths.ARQUIVO_ENV.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(paths.ARQUIVO_ENV, override=False)


def _lista(valor) -> list:
    if isinstance(valor, str):
        valor = valor.splitlines()
    return [str(item).strip() for item in (valor or []) if str(item or "").strip()]


def _do_ambiente(chave: str):
    valor = os.environ.get(ENV.get(chave, ""), "").strip()
    if not valor:
        return None
    return [p.strip() for p in valor.split(",") if p.strip()] if chave == "CORS_ORIGENS" else valor


def ler_arquivo(caminho=None) -> dict:
    """O conteúdo cru do config.yml. Dicionário vazio se o arquivo não existir ou estiver quebrado."""
    caminho = Path(caminho or paths.ARQUIVO_CONFIG)
    if not caminho.is_file():
        return {}
    try:
        with caminho.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return {}


def geracao(caminho=None) -> ConfiguracaoGeracao:
    bruto = ler_arquivo(caminho)

    try:
        retry = int(bruto.get("RETRY", RETRY_PADRAO))
    except (TypeError, ValueError):
        retry = RETRY_PADRAO

    modelo_docx = str(bruto.get("MODELO_DOCX") or "").strip()

    return ConfiguracaoGeracao(
        api_key=_do_ambiente("API_KEY") or str(bruto.get("API_KEY") or "").strip(),
        modelos=_lista(bruto.get("MODELOS")) or list(MODELOS_PADRAO),
        retry=retry,
        formato_saida=str(bruto.get("FORMATO_SAIDA") or FORMATO_SAIDA_PADRAO).strip().lower(),
        libreoffice=str(bruto.get("LIBREOFFICE") or "").strip(),
        modelo_docx=do_backend(modelo_docx) if modelo_docx else paths.MODELO_DOCX_PADRAO,
        tecnologias=_lista(bruto.get("TECNOLOGIAS")),
    )


@lru_cache(maxsize=1)
def servidor(caminho=None) -> ConfiguracaoServidor:
    """Lido uma vez só: host, porta, token e CORS valem a partir do próximo início."""
    bruto = ler_arquivo(caminho)

    host = _do_ambiente("HOST") or str(bruto.get("HOST") or "").strip() or HOST_PADRAO

    try:
        porta = int(_do_ambiente("PORTA") or bruto.get("PORTA", PORTA_PADRAO))
        if not 1 <= porta <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        porta = PORTA_PADRAO

    return ConfiguracaoServidor(
        host=host,
        porta=porta,
        api_token=_do_ambiente("API_TOKEN") or str(bruto.get("API_TOKEN") or "").strip(),
        cors_origens=_do_ambiente("CORS_ORIGENS") or _lista(bruto.get("CORS_ORIGENS")),
    )


def origem_api_key(caminho=None) -> str:
    """De onde sai a API key em uso: "ambiente", "arquivo" ou "ausente"."""
    if _do_ambiente("API_KEY"):
        return "ambiente"
    return "arquivo" if str(ler_arquivo(caminho).get("API_KEY") or "").strip() else "ausente"


carregar_env()
