"""Exercita a API pelo HTTP, com o Gemini trocado por respostas prontas.

O único ponto dublado é a chamada ao modelo: o resto do caminho — fila, worker,
escrita em disco, montagem do DOCX sobre o modelo Word real e download — roda
de verdade.
"""

import json
import time

import pytest

from criador_procedimento.core import config
from criador_procedimento.modules.geracao import repository as geracao_repository
from criador_procedimento.modules.geracao import service as geracao_service
from criador_procedimento.modules.geracao.prompts import MARCADOR_CATALOGO, SEPARADOR_CATALOGO

LEVANTAMENTO = f"1. Requisitos\nTexto do levantamento.{SEPARADOR_CATALOGO}{MARCADOR_CATALOGO}\n| campo | ecs |"
PROCEDIMENTO = json.dumps({
    "introducao": ["O Fortigate exporta log por syslog."],
    "pre_requisitos": ["Acesso administrativo.", "Porta <PORTA> liberada."],
    "passos": [{
        "titulo": "Configurar o syslog",
        "descricao": "Aponte o appliance para o coletor.",
        "itens": ["Servidor: <IP_DO_COLETOR>"],
        "codigo": "config log syslogd setting\n    set status enable\nend",
    }],
    "validacao": ["Confirme a chegada dos eventos."],
}, ensure_ascii=False)


@pytest.fixture
def gemini_dublado(monkeypatch):
    chamadas = []

    def responder(prompt, api_key, modelos, tentativas, logger, config_geracao=None):
        chamadas.append(prompt)
        return PROCEDIMENTO if config_geracao else LEVANTAMENTO

    monkeypatch.setattr(geracao_repository, "gerar_conteudo", responder)
    monkeypatch.setattr(geracao_service, "PAUSA_ENTRE_TECNOLOGIAS", 0)
    return chamadas


def esperar_fim(cliente, job_id, cabecalhos=None, limite=30):
    for _ in range(limite * 10):
        resposta = cliente.get(f"/api/jobs/{job_id}", headers=cabecalhos or {})
        dados = resposta.json()
        if dados["estado"] in ("concluido", "falhou", "cancelado"):
            return dados
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} não terminou: {dados}")


# ---- saúde e ajustes --------------------------------------------------

def test_saude_nao_exige_token(cliente):
    dados = cliente.get("/api/saude").json()
    assert dados["ok"] and dados["api_key_definida"] and not dados["auth_requerida"]


def test_ajustes_do_servidor_nao_devolvem_a_key(cliente):
    dados = cliente.get("/api/config").json()
    assert dados["api_key_definida"] and dados["api_key_origem"] == "arquivo"
    assert "api_key" not in dados and "API_KEY" not in dados


def test_interface_e_servida_na_raiz(cliente):
    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert "Procedimento de Coleta" in resposta.text


# ---- token ------------------------------------------------------------

def test_com_token_as_rotas_exigem_cabecalho(ambiente, cliente):
    ambiente.escrever_config('API_KEY: "k"\nAPI_TOKEN: "segredo"\n')
    config.servidor.cache_clear()

    assert cliente.get("/api/saude").status_code == 200           # health check fica de fora
    assert cliente.get("/api/config").status_code == 401
    assert cliente.get("/api/config", headers={"Authorization": "Bearer errado"}).status_code == 401
    assert cliente.get("/api/config", headers={"Authorization": "Bearer segredo"}).status_code == 200
    assert cliente.get("/api/config", headers={"X-API-Token": "segredo"}).status_code == 200


def test_erro_sai_sempre_como_lista_de_erros(cliente):
    dados = cliente.get("/api/jobs/naoexiste").json()
    assert dados["erros"] == ["Job 'naoexiste' não encontrado."]

    dados = cliente.post("/api/jobs", json={"tecnologias": []}).json()
    assert isinstance(dados["erros"], list) and dados["erros"]


# ---- recusas antes de enfileirar --------------------------------------

def test_sem_api_key_o_job_e_recusado_com_o_caminho_do_config(ambiente, cliente):
    ambiente.escrever_config('API_KEY: ""\n')
    resposta = cliente.post("/api/jobs", json={"tecnologias": ["Fortinet Fortigate"]})
    assert resposta.status_code == 400
    assert str(ambiente.config) in resposta.json()["erros"][0]


def test_pdf_sem_libreoffice_e_recusado(ambiente, cliente, monkeypatch):
    monkeypatch.setattr(geracao_service.docx, "localizar_libreoffice", lambda _=None: None)
    resposta = cliente.post("/api/jobs", json={"tecnologias": ["X"], "formato_saida": "pdf"})
    assert resposta.status_code == 400
    assert any("LibreOffice" in e for e in resposta.json()["erros"])


# ---- o caminho completo -----------------------------------------------

def test_job_gera_os_tres_documentos_e_entrega_para_download(cliente, gemini_dublado):
    criado = cliente.post("/api/jobs", json={"tecnologias": ["Fortinet Fortigate via syslog"]})
    assert criado.status_code == 202
    job_id = criado.json()["id"]

    final = esperar_fim(cliente, job_id)
    assert final["estado"] == "concluido", final
    assert len(gemini_dublado) == 2  # levantamento e procedimento

    arquivos = {a["caminho"].rsplit("/", 1)[-1]: a for a in final["resultados"][0]["arquivos"]}
    assert set(arquivos) == {
        "procedimento_fortinet_fortigate_via_syslog.txt",
        "catalogo_fortinet_fortigate_via_syslog.txt",
        "procedimento_coleta_fortinet_fortigate_via_syslog.docx",
    }

    docx = arquivos["procedimento_coleta_fortinet_fortigate_via_syslog.docx"]
    baixado = cliente.get(docx["url"])
    assert baixado.status_code == 200
    assert baixado.content[:2] == b"PK"            # é mesmo um zip/docx
    assert baixado.headers["content-disposition"].endswith('.docx"')

    catalogo = cliente.get(arquivos["catalogo_fortinet_fortigate_via_syslog.txt"]["url"])
    assert "| campo | ecs |" in catalogo.text


def test_log_do_job_continua_de_onde_parou(cliente, gemini_dublado):
    job_id = cliente.post("/api/jobs", json={"tecnologias": ["Cisco ASA"]}).json()["id"]
    esperar_fim(cliente, job_id)

    tudo = cliente.get(f"/api/jobs/{job_id}/log").json()
    assert tudo["total"] > 1
    assert any("Cisco ASA" in linha for linha in tudo["linhas"])

    resto = cliente.get(f"/api/jobs/{job_id}/log?desde={tudo['total'] - 1}").json()
    assert resto["linhas"] == tudo["linhas"][-1:]


def test_falha_de_uma_tecnologia_nao_derruba_a_outra(cliente, monkeypatch):
    from criador_procedimento.shared.exceptions import ErroDeGeracao

    def responder(prompt, api_key, modelos, tentativas, logger, config_geracao=None):
        if "Quebrada" in prompt:
            raise ErroDeGeracao("modelo indisponível")
        return PROCEDIMENTO if config_geracao else LEVANTAMENTO

    monkeypatch.setattr(geracao_repository, "gerar_conteudo", responder)
    monkeypatch.setattr(geracao_service, "PAUSA_ENTRE_TECNOLOGIAS", 0)

    job_id = cliente.post("/api/jobs", json={"tecnologias": ["Quebrada", "Cisco ASA"]}).json()["id"]
    final = esperar_fim(cliente, job_id)

    assert final["estado"] == "falhou"
    por_tecnologia = {r["tecnologia"]: r for r in final["resultados"]}
    assert por_tecnologia["Quebrada"]["erro"] == "modelo indisponível"
    assert por_tecnologia["Cisco ASA"]["erro"] is None
    assert len(por_tecnologia["Cisco ASA"]["arquivos"]) == 3


def test_artefatos_lista_tudo_e_recusa_sair_da_pasta(cliente, gemini_dublado):
    esperar_fim(cliente, cliente.post("/api/jobs", json={"tecnologias": ["Cisco ASA"]}).json()["id"])

    listados = cliente.get("/api/artefatos").json()
    assert len(listados) == 3
    assert all(a["url"].startswith("/api/artefatos/") for a in listados)

    assert cliente.get("/api/artefatos/%2e%2e%2fconfig.yml").status_code == 404


def test_cancelar_job_que_ja_terminou_responde_409(cliente, gemini_dublado):
    job_id = cliente.post("/api/jobs", json={"tecnologias": ["Cisco ASA"]}).json()["id"]
    esperar_fim(cliente, job_id)
    assert cliente.post(f"/api/jobs/{job_id}/cancelar").status_code == 409


def test_jobs_sao_listados_do_mais_novo_para_o_mais_antigo(cliente, gemini_dublado):
    primeiro = cliente.post("/api/jobs", json={"tecnologias": ["Cisco ASA"]}).json()["id"]
    segundo = cliente.post("/api/jobs", json={"tecnologias": ["Palo Alto"]}).json()["id"]
    esperar_fim(cliente, segundo)

    assert [j["id"] for j in cliente.get("/api/jobs").json()] == [segundo, primeiro]
