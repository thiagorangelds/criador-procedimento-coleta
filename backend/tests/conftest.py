"""Isolamento: cada teste roda com config.yml e pasta de saída próprios.

O `ambiente` é `autouse` porque esquecer dele faria o teste ler o `config.yml`
de verdade — e, no caso do de integração, escrever na pasta de documentos de
quem está rodando.
"""

import pytest
from fastapi.testclient import TestClient

from criador_procedimento.core import config
from criador_procedimento.modules.jobs import service as jobs_service
from criador_procedimento.shared import paths

CONFIG_MINIMO = '''\
API_KEY: "chave-de-teste"
RETRY: 1
MODELOS:
  - "gemini-2.5-flash"
TECNOLOGIAS: []
FORMATO_SAIDA: docx
HOST: "127.0.0.1"
PORTA: 8765
'''


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    arquivo_config = tmp_path / "config.yml"
    arquivo_config.write_text(CONFIG_MINIMO, encoding="utf-8")
    pasta_saida = tmp_path / "procedimentos"
    pasta_saida.mkdir()

    monkeypatch.setattr(paths, "ARQUIVO_CONFIG", arquivo_config)
    monkeypatch.setattr(paths, "PASTA_SAIDA", pasta_saida)
    monkeypatch.setattr(paths, "ARQUIVO_ENV", tmp_path / ".env")
    for variavel in config.ENV.values():
        monkeypatch.delenv(variavel, raising=False)

    config.servidor.cache_clear()
    jobs_service.definir_gerenciador(None)
    try:
        yield type("Ambiente", (), {
            "config": arquivo_config,
            "saida": pasta_saida,
            "escrever_config": lambda self, texto: arquivo_config.write_text(texto, encoding="utf-8"),
        })()
    finally:
        config.servidor.cache_clear()
        jobs_service.definir_gerenciador(None)


@pytest.fixture
def cliente():
    """Criado depois do `ambiente`, para o app ler a configuração do teste."""
    from criador_procedimento.main import criar_app

    with TestClient(criar_app()) as c:
        yield c
