from criador_procedimento.core import config


def test_api_key_vem_do_arquivo(ambiente):
    assert config.geracao().api_key == "chave-de-teste"
    assert config.origem_api_key() == "arquivo"


def test_ambiente_vence_o_arquivo(ambiente, monkeypatch):
    monkeypatch.setenv("CRIADOR_API_KEY", "chave-do-ambiente")
    assert config.geracao().api_key == "chave-do-ambiente"
    assert config.origem_api_key() == "ambiente"


def test_sem_key_em_lugar_nenhum(ambiente):
    ambiente.escrever_config("API_KEY: \"\"\n")
    assert config.geracao().api_key == ""
    assert config.origem_api_key() == "ausente"


def test_porta_invalida_cai_no_padrao(ambiente):
    ambiente.escrever_config("PORTA: 99999\n")
    config.servidor.cache_clear()
    assert config.servidor().porta == config.PORTA_PADRAO


def test_cors_do_ambiente_separado_por_virgula(ambiente, monkeypatch):
    monkeypatch.setenv("CRIADOR_CORS_ORIGENS", "https://a.exemplo, https://b.exemplo ")
    config.servidor.cache_clear()
    assert config.servidor().cors_origens == ["https://a.exemplo", "https://b.exemplo"]


def test_token_define_se_exige_auth(ambiente):
    ambiente.escrever_config('API_TOKEN: "segredo"\nHOST: "0.0.0.0"\n')
    config.servidor.cache_clear()
    servidor = config.servidor()
    assert servidor.exige_token
    assert not servidor.apenas_local


def test_yaml_quebrado_nao_derruba_a_leitura(ambiente):
    ambiente.escrever_config("API_KEY: [nao fecha\n")
    assert config.geracao().api_key == ""


def test_com_troca_so_o_que_recebe(ambiente):
    original = config.geracao()
    novo = original.com(tecnologias=["X"], formato_saida="pdf")
    assert novo.tecnologias == ["X"] and novo.formato_saida == "pdf"
    assert novo.api_key == original.api_key
    assert original.tecnologias == []  # o original é imutável
