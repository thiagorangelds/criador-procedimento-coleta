from typing import List, Optional

from pydantic import BaseModel, Field

from criador_procedimento.modules.artefatos.schemas import Arquivo
from criador_procedimento.modules.jobs.models import EstadoDoJob


class ResultadoTecnologia(BaseModel):
    tecnologia: str
    nome_base: str = Field(description="Nome da pasta gerada para a tecnologia.")
    erro: Optional[str] = Field(default=None, description="Preenchido quando esta tecnologia falhou; as outras do job seguem.")
    arquivos: List[Arquivo] = []


class JobResumo(BaseModel):
    id: str
    estado: EstadoDoJob
    tecnologias: List[str]
    erro: Optional[str] = None
    criado_em: float
    iniciado_em: Optional[float] = None
    concluido_em: Optional[float] = None
    total_log: int = Field(description="Quantidade de linhas de log já produzidas; use com /log?desde=.")


class JobDetalhe(JobResumo):
    resultados: List[ResultadoTecnologia] = []


class LogDoJob(BaseModel):
    estado: EstadoDoJob
    linhas: List[str]
    total: int = Field(description="Próximo valor a passar em 'desde' para continuar de onde parou.")


class NovoJob(BaseModel):
    """Pedido de geração. A API key do Gemini vem sempre da configuração do servidor."""

    tecnologias: List[str] = Field(
        min_length=1,
        description='Uma entrada por documento. A forma de coleta vai na mesma string, depois de " via ", ex.: "AWS GuardDuty via S3 + SQS". Sem o " via ", o modelo escolhe o método e justifica no documento.',
        examples=[["Fortinet Fortigate via syslog"]],
    )
    formato_saida: Optional[str] = Field(
        default=None,
        description='"docx" ou "pdf". Omitido, usa o formato padrão do servidor. "pdf" exige LibreOffice no servidor.',
        examples=["docx"],
    )
