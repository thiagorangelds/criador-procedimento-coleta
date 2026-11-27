import os

from criador_procedimento.modules.artefatos import repository, service


def _criar(ambiente, caminho_relativo, conteudo="x"):
    alvo = ambiente.saida / caminho_relativo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(conteudo, encoding="utf-8")
    return alvo


def test_listar_do_mais_recente_para_o_mais_antigo(ambiente):
    antigo = _criar(ambiente, "tec_a/antigo.txt")
    novo = _criar(ambiente, "tec_b/novo.txt")
    os.utime(antigo, (1_000_000, 1_000_000))
    os.utime(novo, (2_000_000, 2_000_000))

    caminhos = [a.caminho for a in repository.listar()]
    assert caminhos == ["tec_b/novo.txt", "tec_a/antigo.txt"]


def test_resolver_aceita_arquivo_de_dentro(ambiente):
    _criar(ambiente, "tec_a/doc.txt")
    assert repository.resolver("tec_a/doc.txt") is not None


def test_resolver_recusa_sair_da_pasta(ambiente):
    (ambiente.saida.parent / "config.yml").write_text("segredo", encoding="utf-8")
    assert repository.resolver("../config.yml") is None
    assert repository.resolver("tec_a/../../config.yml") is None


def test_resolver_recusa_o_que_nao_existe(ambiente):
    assert repository.resolver("tec_a/nao_existe.txt") is None


def test_url_escapa_o_caminho():
    assert service.url("aws guardduty via s3 + sqs/doc.docx") == \
        "/api/artefatos/aws%20guardduty%20via%20s3%20%2B%20sqs/doc.docx"


def test_pasta_e_nome_do_artefato(ambiente):
    _criar(ambiente, "tec_a/doc.txt")
    artefato = repository.listar()[0]
    assert artefato.pasta == "tec_a" and artefato.nome == "doc.txt"
