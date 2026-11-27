from criador_procedimento.core.config import ConfiguracaoGeracao
from criador_procedimento.modules.jobs.models import EstadoDoJob, Job
from criador_procedimento.modules.jobs.repository import RepositorioDeJobs


def _job(**kwargs) -> Job:
    return Job(tecnologias=["X"], config=ConfiguracaoGeracao(), **kwargs)


def test_listar_devolve_do_mais_novo_para_o_mais_antigo():
    repo = RepositorioDeJobs()
    primeiro, segundo = repo.guardar(_job()), repo.guardar(_job())
    assert [j.id for j in repo.listar()] == [segundo.id, primeiro.id]


def test_poda_descarta_o_historico_antigo():
    repo = RepositorioDeJobs(historico_maximo=2)
    antigo = repo.guardar(_job(estado=EstadoDoJob.CONCLUIDO))
    repo.guardar(_job(estado=EstadoDoJob.CONCLUIDO))
    repo.guardar(_job(estado=EstadoDoJob.CONCLUIDO))
    assert repo.obter(antigo.id) is None
    assert len(repo.listar()) == 2


def test_poda_nao_descarta_job_em_andamento():
    repo = RepositorioDeJobs(historico_maximo=1)
    executando = repo.guardar(_job(estado=EstadoDoJob.EXECUTANDO))
    repo.guardar(_job(estado=EstadoDoJob.CONCLUIDO))
    repo.guardar(_job(estado=EstadoDoJob.CONCLUIDO))
    assert repo.obter(executando.id) is not None


def test_primeiro_na_fila_ignora_quem_ja_rodou():
    repo = RepositorioDeJobs()
    repo.guardar(_job(estado=EstadoDoJob.CONCLUIDO))
    na_fila = repo.guardar(_job())
    assert repo.primeiro_na_fila().id == na_fila.id


def test_log_continua_de_onde_parou():
    job = _job()
    job.registrar("um")
    job.registrar("dois")
    linhas, total = job.log(desde=1)
    assert linhas == ["dois"] and total == 2


def test_estado_final():
    assert EstadoDoJob.CONCLUIDO.final and EstadoDoJob.CANCELADO.final
    assert not EstadoDoJob.NA_FILA.final and not EstadoDoJob.EXECUTANDO.final
