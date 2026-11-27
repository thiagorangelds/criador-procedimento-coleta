"""O contrato com o Gemini: o JSON que vira o documento de Procedimento.

Validar aqui é o que separa "o modelo devolveu alguma coisa" de "o modelo
devolveu o que o gerador de DOCX consegue montar". Os campos são tolerantes de
propósito — só `passos` é obrigatório, porque sem ele não há documento —, mas
uma string solta onde se espera lista é normalizada em vez de explodir.
"""

from typing import List

from pydantic import BaseModel, Field, field_validator


def _como_lista(valor) -> List[str]:
    if valor is None:
        return []
    if isinstance(valor, str):
        return [valor] if valor.strip() else []
    return [str(item) for item in valor if str(item or "").strip()]


class PassoDoProcedimento(BaseModel):
    titulo: str = ""
    descricao: List[str] = Field(default_factory=list)
    itens: List[str] = Field(default_factory=list)
    codigo: str = ""

    @field_validator("descricao", "itens", mode="before")
    @classmethod
    def _lista(cls, valor):
        return _como_lista(valor)

    @field_validator("titulo", "codigo", mode="before")
    @classmethod
    def _texto(cls, valor):
        return "" if valor is None else str(valor)


class ConteudoDoProcedimento(BaseModel):
    introducao: List[str] = Field(default_factory=list)
    pre_requisitos: List[str] = Field(default_factory=list)
    passos: List[PassoDoProcedimento] = Field(min_length=1)
    validacao: List[str] = Field(default_factory=list)

    @field_validator("introducao", "pre_requisitos", "validacao", mode="before")
    @classmethod
    def _lista(cls, valor):
        return _como_lista(valor)
