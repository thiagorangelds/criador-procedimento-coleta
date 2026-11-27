from typing import List

from pydantic import BaseModel, Field


class Arquivo(BaseModel):
    caminho: str = Field(description="Caminho relativo à pasta de saída, ex.: 'fortinet_fortigate/procedimento_coleta_fortinet_fortigate.docx'")
    tamanho: int = Field(description="Tamanho em bytes.")
    modificado: float = Field(description="Data de modificação, em epoch (segundos).")
    url: str = Field(description="Caminho para baixar o arquivo nesta API.")


class ListaDeArquivos(BaseModel):
    arquivos: List[Arquivo]
