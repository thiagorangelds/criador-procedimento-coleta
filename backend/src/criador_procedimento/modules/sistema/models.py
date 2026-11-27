"""O que o servidor sabe sobre si mesmo."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Saude:
    ok: bool
    versao: str
    auth_requerida: bool
    api_key_definida: bool
    job_ativo: Optional[str] = None


@dataclass(frozen=True)
class Ajustes:
    formato_saida: str
    formatos_saida: List[str]
    modelos: List[str]
    retry: int
    pdf_disponivel: bool
    api_key_definida: bool
    api_key_origem: str
    arquivo_config: str
