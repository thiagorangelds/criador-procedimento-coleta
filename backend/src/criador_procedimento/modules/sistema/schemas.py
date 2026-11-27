from typing import List, Optional

from pydantic import BaseModel, Field


class Saude(BaseModel):
    ok: bool
    versao: str
    auth_requerida: bool
    api_key_definida: bool
    job_ativo: Optional[str] = Field(default=None, description="Id do job executando ou na fila, se houver.")


class AjustesDoServidor(BaseModel):
    """O que o servidor tem configurado. Somente leitura — a API não edita configuração."""

    formato_saida: str = Field(description="Formato padrão quando o job não informa um.")
    formatos_saida: List[str]
    modelos: List[str] = Field(description="Modelos do Gemini em ordem de fallback.")
    retry: int
    pdf_disponivel: bool = Field(description="Se o LibreOffice foi encontrado; sem ele, 'pdf' falha.")
    api_key_definida: bool
    api_key_origem: str = Field(description='"ambiente", "arquivo" ou "ausente".')
    arquivo_config: str = Field(description="Caminho do config.yml em uso, para quem precisar ajustar.")


class Erros(BaseModel):
    erros: List[str]
