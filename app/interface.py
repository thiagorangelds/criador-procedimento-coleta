import argparse
import json
import logging
import mimetypes
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import urlopen

PASTA_APP = os.path.dirname(os.path.abspath(__file__))
os.chdir(PASTA_APP)

import script

PORTA_PADRAO = 8765
ARQUIVO_HTML = "interface.html"
MODELOS_FREE_TIER_PADRAO = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.0-flash"]
TERMOS_FORA_DE_TEXTO = ("image", "tts", "audio", "live", "embedding", "robotics", "computer-use", "-exp")
CONFIG_PADRAO = {
    "API_KEY": "",
    "RETRY": 5,
    "MODELOS": ["gemini-2.5-flash", "gemini-2.0-flash"],
    "TECNOLOGIAS": [],
    "FORMATO_SAIDA": script.FORMATO_SAIDA_PADRAO,
    "LIBREOFFICE": "",
    "MODELO_DOCX": "",
}


class Execucao:
    def __init__(self):
        self.lock = threading.Lock()
        self.linhas = []
        self.thread = None
        self.cancelar = threading.Event()

    @property
    def executando(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def registrar(self, linha: str) -> None:
        with self.lock:
            self.linhas.append(linha)

    def ler(self, desde: int):
        with self.lock:
            return self.linhas[desde:], len(self.linhas)

    def iniciar(self, config: dict, logger: logging.Logger) -> bool:
        with self.lock:
            if self.executando:
                return False
            self.linhas = []
            self.cancelar = threading.Event()
            self.thread = threading.Thread(target=self._rodar, args=(config, logger, self.cancelar), daemon=True)
            self.thread.start()
            return True

    @staticmethod
    def _rodar(config, logger, cancelar):
        logger.info("Iniciando a execução pela interface.")
        try:
            script.executar(config, logger, cancelar)
        except Exception as e:
            logger.error(f"Erro inesperado na execução: {e}")


class HandlerInterface(logging.Handler):
    def __init__(self, execucao: Execucao):
        super().__init__()
        self.execucao = execucao
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))

    def emit(self, record):
        self.execucao.registrar(self.format(record))


def _lista_texto(valor) -> list:
    if isinstance(valor, str):
        valor = valor.splitlines()
    return [str(item).strip() for item in (valor or []) if str(item or "").strip()]


def normalizar_configuracao(dados: dict, para_execucao: bool = False) -> dict:
    erros = []

    try:
        retry = int(dados.get("RETRY", CONFIG_PADRAO["RETRY"]))
        if not 1 <= retry <= 20:
            raise ValueError
    except (TypeError, ValueError):
        erros.append("Tentativas (RETRY) deve ser um número entre 1 e 20.")
        retry = CONFIG_PADRAO["RETRY"]

    formato = str(dados.get("FORMATO_SAIDA", script.FORMATO_SAIDA_PADRAO)).strip().lower()
    if formato not in script.FORMATOS_SAIDA:
        erros.append(f"Formato de saída deve ser um destes: {', '.join(script.FORMATOS_SAIDA)}.")

    config = {
        "API_KEY": str(dados.get("API_KEY") or "").strip(),
        "RETRY": retry,
        "MODELOS": _lista_texto(dados.get("MODELOS")),
        "TECNOLOGIAS": _lista_texto(dados.get("TECNOLOGIAS")),
        "FORMATO_SAIDA": formato,
        "LIBREOFFICE": str(dados.get("LIBREOFFICE") or "").strip(),
        "MODELO_DOCX": str(dados.get("MODELO_DOCX") or "").strip(),
    }

    if not config["MODELOS"]:
        erros.append("Informe ao menos um modelo do Gemini.")
    if config["MODELO_DOCX"] and not os.path.isfile(config["MODELO_DOCX"]):
        erros.append(f"Modelo DOCX '{config['MODELO_DOCX']}' não encontrado.")

    if para_execucao:
        if not config["API_KEY"]:
            erros.append("Informe a API Key do Gemini.")
        if not config["TECNOLOGIAS"]:
            erros.append("Informe ao menos uma tecnologia.")
        if formato == "pdf" and not script.localizar_libreoffice(config["LIBREOFFICE"] or None):
            erros.append("LibreOffice não encontrado: instale-o ou informe o caminho do executável para gerar em PDF.")

    if erros:
        raise ValueError(erros)
    return config


def carregar_configuracao_interface() -> dict:
    config = dict(CONFIG_PADRAO)
    if os.path.isfile(script.CONFIG_FILE):
        config.update({k: v for k, v in (script.carregar_configuracao() or {}).items() if v is not None})
    config["TECNOLOGIAS"] = _lista_texto(config.get("TECNOLOGIAS"))
    config["MODELOS"] = _lista_texto(config.get("MODELOS"))
    return config


def listar_modelos_free_tier(api_key: str) -> dict:
    padrao = {"modelos": MODELOS_FREE_TIER_PADRAO, "origem": "padrao"}
    if not api_key:
        return {**padrao, "aviso": "Lista padrão. Informe a API key para buscar a lista atual."}

    try:
        nomes = set()
        for modelo in script.genai.Client(api_key=api_key).models.list():
            nome = (getattr(modelo, "name", "") or "").removeprefix("models/")
            acoes = getattr(modelo, "supported_actions", None) or []
            if "generateContent" in acoes and "flash" in nome and not any(t in nome for t in TERMOS_FORA_DE_TEXTO):
                nomes.add(nome)
    except Exception as e:
        return {**padrao, "aviso": f"Não foi possível consultar a API do Gemini ({e}). Usando a lista padrão."}

    if not nomes:
        return {**padrao, "aviso": "A API não retornou modelos Flash para esta key. Usando a lista padrão."}
    return {"modelos": sorted(nomes, reverse=True), "origem": "api"}


def listar_arquivos_gerados() -> list:
    arquivos = []
    for raiz, _, nomes in os.walk(script.OUTPUT_DIR):
        for nome in nomes:
            caminho = os.path.join(raiz, nome)
            arquivos.append({
                "caminho": os.path.relpath(caminho, script.OUTPUT_DIR).replace(os.sep, "/"),
                "tamanho": os.path.getsize(caminho),
                "modificado": os.path.getmtime(caminho),
            })
    return sorted(arquivos, key=lambda a: a["modificado"], reverse=True)


def criar_handler(execucao: Execucao, logger: logging.Logger, porta: int):
    hosts_permitidos = {f"127.0.0.1:{porta}", f"localhost:{porta}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, formato, *args):
            pass

        def _responder(self, status: int, corpo: bytes, tipo: str, extras: dict = None):
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            for chave, valor in (extras or {}).items():
                self.send_header(chave, valor)
            self.end_headers()
            self.wfile.write(corpo)

        def _json(self, status: int, dados) -> None:
            self._responder(status, json.dumps(dados, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _origem_valida(self) -> bool:
            if self.headers.get("Host") not in hosts_permitidos:
                return False
            origem = self.headers.get("Origin")
            return origem is None or urlparse(origem).netloc in hosts_permitidos

        def _ler_json(self):
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return None
            tamanho = int(self.headers.get("Content-Length") or 0)
            try:
                dados = json.loads(self.rfile.read(tamanho) or b"{}")
            except json.JSONDecodeError:
                return None
            return dados if isinstance(dados, dict) else None

        def _com_tratamento(self, metodo):
            try:
                metodo()
            except Exception as e:
                logger.error(f"Erro na interface ao atender {self.command} {self.path}: {e}")
                mensagem = f"Erro interno da interface: {e}"
                try:
                    if self.path.startswith("/api/"):
                        self._json(500, {"erro": mensagem, "erros": [mensagem]})
                    else:
                        self._responder(500, mensagem.encode("utf-8"), "text/plain; charset=utf-8")
                except Exception:
                    pass

        def do_GET(self):
            self._com_tratamento(self._get)

        def do_POST(self):
            self._com_tratamento(self._post)

        def _get(self):
            if not self._origem_valida():
                return self._json(403, {"erro": "Origem não permitida."})

            url = urlparse(self.path)
            if url.path == "/":
                with open(ARQUIVO_HTML, "rb") as f:
                    return self._responder(200, f.read(), "text/html; charset=utf-8")
            if url.path == "/api/config":
                try:
                    config = carregar_configuracao_interface()
                except Exception as e:
                    return self._json(500, {"erro": f"Não foi possível ler '{script.CONFIG_FILE}': {e}"})
                return self._json(200, {"config": config, "modelo_docx_padrao": script.MODELO_DOCX_PADRAO})
            if url.path == "/api/status":
                try:
                    desde = max(0, int(parse_qs(url.query).get("desde", ["0"])[0]))
                except ValueError:
                    desde = 0
                linhas, total = execucao.ler(desde)
                return self._json(200, {"executando": execucao.executando, "linhas": linhas, "total": total, "pasta": PASTA_APP})
            if url.path == "/api/arquivos":
                return self._json(200, {"arquivos": listar_arquivos_gerados()})
            if url.path.startswith("/arquivos/"):
                return self._servir_arquivo(unquote(url.path[len("/arquivos/"):]))
            return self._json(404, {"erro": "Não encontrado."})

        def _servir_arquivo(self, relativo: str):
            base = os.path.realpath(script.OUTPUT_DIR)
            caminho = os.path.realpath(os.path.join(base, relativo))
            if not caminho.startswith(base + os.sep) or not os.path.isfile(caminho):
                return self._json(404, {"erro": "Arquivo não encontrado."})
            tipo = mimetypes.guess_type(caminho)[0] or "application/octet-stream"
            nome = os.path.basename(caminho).replace('"', "")
            with open(caminho, "rb") as f:
                self._responder(200, f.read(), tipo, {"Content-Disposition": f'attachment; filename="{nome}"'})

        def _post(self):
            if not self._origem_valida():
                return self._json(403, {"erro": "Origem não permitida."})

            url = urlparse(self.path)
            if url.path == "/api/cancelar":
                execucao.cancelar.set()
                logger.warning("Cancelamento solicitado; a execução para antes da próxima tecnologia.")
                return self._json(200, {"ok": True})

            if url.path not in ("/api/config", "/api/gerar", "/api/modelos"):
                return self._json(404, {"erro": "Não encontrado."})

            dados = self._ler_json()
            if dados is None:
                return self._json(400, {"erros": ["Requisição inválida."]})

            if url.path == "/api/modelos":
                return self._json(200, listar_modelos_free_tier(str(dados.get("API_KEY") or "").strip()))

            para_execucao = url.path == "/api/gerar"
            if para_execucao and execucao.executando:
                return self._json(409, {"erros": ["Já existe uma execução em andamento."]})

            try:
                config = normalizar_configuracao(dados, para_execucao)
            except ValueError as e:
                return self._json(400, {"erros": e.args[0]})

            script.salvar_configuracao(config)
            if para_execucao and not execucao.iniciar(config, logger):
                return self._json(409, {"erros": ["Já existe uma execução em andamento."]})
            return self._json(200, {"ok": True})

    return Handler


def consultar_interface_aberta(endereco: str):
    try:
        with urlopen(endereco + "api/status", timeout=2) as resposta:
            dados = json.loads(resposta.read())
        return dados if "executando" in dados else None
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Interface gráfica do Criador de Procedimento de Coleta.")
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO, help=f"Porta local da interface (padrão: {PORTA_PADRAO}).")
    parser.add_argument("--sem-navegador", action="store_true", help="Não abre o navegador automaticamente.")
    args = parser.parse_args()

    endereco = f"http://127.0.0.1:{args.porta}/"
    execucao = Execucao()
    logger = script.setup_logger("execucao.log")
    logger.addHandler(HandlerInterface(execucao))

    try:
        servidor = ThreadingHTTPServer(("127.0.0.1", args.porta), criar_handler(execucao, logger, args.porta))
    except OSError:
        aberta = consultar_interface_aberta(endereco)
        if aberta and aberta.get("pasta") == PASTA_APP:
            print(f"A interface já está em execução em {endereco}")
            if not args.sem_navegador:
                webbrowser.open(endereco)
            return
        if aberta:
            raise SystemExit(
                f"Uma versão anterior da interface ainda está rodando na porta {args.porta}.\n"
                "Encerre-a com: pkill -f interface.py\n"
                "e rode o comando de novo."
            )
        raise SystemExit(f"A porta {args.porta} está em uso por outro programa. Use --porta para escolher outra.")

    print(f"Interface disponível em {endereco} (Ctrl+C para encerrar)")
    if not args.sem_navegador:
        threading.Timer(0.5, webbrowser.open, args=(endereco,)).start()

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando a interface.")
    finally:
        execucao.cancelar.set()
        servidor.server_close()


if __name__ == "__main__":
    main()
