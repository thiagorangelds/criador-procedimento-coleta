import json

import pytest
from pydantic import ValidationError

from criador_procedimento.core.config import ConfiguracaoGeracao
from criador_procedimento.modules.geracao import prompts, repository, service
from criador_procedimento.modules.geracao.schemas import ConteudoDoProcedimento


# ---- separação do levantamento e do catálogo ----

def test_separa_pelo_marcador_principal():
    resposta = f"levantamento{prompts.SEPARADOR_CATALOGO}{prompts.MARCADOR_CATALOGO}\ntabela"
    levantamento, catalogo = service.separar_catalogo(resposta)
    assert levantamento == "levantamento"
    assert catalogo == "tabela"


def test_cai_no_titulo_da_secao_quando_o_separador_some():
    resposta = f"levantamento\n{prompts.MARCADOR_CATALOGO}\ntabela"
    levantamento, catalogo = service.separar_catalogo(resposta)
    assert levantamento.strip() == "levantamento"
    assert catalogo.startswith(prompts.MARCADOR_CATALOGO)


def test_sem_catalogo_devolve_none():
    levantamento, catalogo = service.separar_catalogo("só o levantamento")
    assert catalogo is None


# ---- o JSON do procedimento ----

CONTEUDO = {
    "introducao": ["Parágrafo."],
    "pre_requisitos": ["Acesso."],
    "passos": [{"titulo": "Configurar", "descricao": "Faça.", "itens": ["a"], "codigo": ""}],
    "validacao": ["Confira."],
}


def test_extrai_json_puro():
    conteudo = service.extrair_conteudo(json.dumps(CONTEUDO))
    assert conteudo.passos[0].titulo == "Configurar"


def test_extrai_json_dentro_de_cerca_de_markdown():
    conteudo = service.extrair_conteudo("```json\n" + json.dumps(CONTEUDO) + "\n```")
    assert conteudo.passos[0].titulo == "Configurar"


def test_string_solta_onde_se_espera_lista_e_normalizada():
    conteudo = ConteudoDoProcedimento.model_validate({
        "introducao": "um parágrafo só",
        "passos": [{"titulo": "T", "descricao": "uma linha", "itens": "um item"}],
    })
    assert conteudo.introducao == ["um parágrafo só"]
    assert conteudo.passos[0].descricao == ["uma linha"]
    assert conteudo.passos[0].itens == ["um item"]


def test_sem_passos_e_recusado():
    with pytest.raises(ValidationError):
        ConteudoDoProcedimento.model_validate({"introducao": ["x"], "passos": []})


# ---- nome da pasta ----

def test_nome_base_nao_sanitiza_pontuacao():
    assert repository.nome_base_da_tecnologia("AWS GuardDuty via S3 + SQS") == "aws_guardduty_via_s3_+_sqs"
    assert repository.nome_base_da_tecnologia("Palo-Alto PAN-OS") == "palo_alto_pan_os"


# ---- validação ----

def test_validar_reclama_de_key_ausente():
    erros = service.validar(ConfiguracaoGeracao(api_key=""), "docx")
    assert any("API key" in e for e in erros)


def test_validar_reclama_de_formato_desconhecido():
    erros = service.validar(ConfiguracaoGeracao(api_key="k"), "odt")
    assert any("Formato de saída" in e for e in erros)


def test_validar_passa_com_o_modelo_word_do_repositorio():
    assert service.validar(ConfiguracaoGeracao(api_key="k"), "docx") == []

# ---- versão da API do Gemini ----

def test_cliente_fixa_a_versao_v1beta(monkeypatch):
    """JSON mode só existe na v1beta; na v1 a API responde 400 e o documento não sai."""
    from criador_procedimento.modules.geracao import repository

    capturado = {}

    class ClienteFalso:
        def __init__(self, **kwargs):
            capturado.update(kwargs)

    monkeypatch.setattr(repository.genai, "Client", ClienteFalso)
    repository._cliente("chave")
    assert capturado["http_options"] == {"api_version": "v1beta"}


# Aposentados pelo Google: respondem 404 e queimam a vez deles no fallback.
MODELOS_APOSENTADOS = ("gemini-2.0-flash", "gemini-2.5-flash-lite")


def test_modelo_padrao_nao_traz_modelo_aposentado():
    from criador_procedimento.core import config

    assert not set(config.MODELOS_PADRAO) & set(MODELOS_APOSENTADOS)


def test_config_versionado_nao_traz_modelo_aposentado():
    """O config.yml do repositório é o que uma instalação nova herda."""
    from criador_procedimento.core import config
    from criador_procedimento.shared import paths

    modelos = config.ler_arquivo(paths.PASTA_BACKEND / "config.yml").get("MODELOS") or []
    assert not set(modelos) & set(MODELOS_APOSENTADOS)
    assert modelos, "o config.yml versionado precisa trazer uma lista de modelos"
