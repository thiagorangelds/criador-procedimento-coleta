#!/usr/bin/env python3
"""Sobe a API e abre a interface. É o que o comando `criador-procedimento` chama.

Host e porta saem do config.yml (ou do ambiente) e podem ser sobrescritos aqui.
Num servidor, chame o uvicorn direto, sem este arquivo:

    uvicorn criador_procedimento.main:app --host 0.0.0.0 --port 8765
"""

import argparse
import json
import socket
import sys
import threading
import webbrowser
from urllib.request import urlopen

from criador_procedimento.core import config
from criador_procedimento.shared import paths


def porta_ocupada(host: str, porta: int) -> bool:
    familia = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(familia, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, porta))
            return False
        except OSError:
            return True


def instancia_na_porta(endereco: str):
    """Responde com o /api/saude de quem já está na porta, se for esta mesma API."""
    try:
        with urlopen(endereco + "api/saude", timeout=2) as resposta:
            dados = json.loads(resposta.read())
        return dados if "auth_requerida" in dados else None
    except Exception:
        return None


def main() -> int:
    servidor = config.servidor()
    parser = argparse.ArgumentParser(description="API e interface do Criador de Procedimento de Coleta.")
    parser.add_argument("--host", default=None, help=f"Endereço de escuta (padrão: {servidor.host}, do config.yml).")
    parser.add_argument("--porta", type=int, default=None, help=f"Porta (padrão: {servidor.porta}, do config.yml).")
    parser.add_argument("--sem-navegador", action="store_true", help="Não abre o navegador automaticamente.")
    args = parser.parse_args()

    host = args.host or servidor.host
    porta = args.porta or servidor.porta
    local = host in ("127.0.0.1", "localhost", "::1")
    endereco = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{porta}/"

    if not local and not servidor.exige_token:
        print(
            f"Aviso: a API vai escutar em {host} sem token. Qualquer um que alcance esta máquina pode gerar\n"
            f"       documentos e baixar os que já existem. Defina API_TOKEN em {paths.ARQUIVO_CONFIG}\n"
            f"       ou a variável {config.ENV['API_TOKEN']}.",
            file=sys.stderr,
        )

    if porta_ocupada(host, porta):
        if instancia_na_porta(endereco):
            print(f"A interface já está em execução em {endereco}")
            if local and not args.sem_navegador:
                webbrowser.open(endereco)
            return 0
        print(f"A porta {porta} está em uso por outro programa. Use --porta para escolher outra.", file=sys.stderr)
        return 1

    import uvicorn

    from criador_procedimento.main import app

    print(f"API e interface em {endereco} (documentação em {endereco}docs — Ctrl+C para encerrar)")
    if local and not args.sem_navegador:
        threading.Timer(0.5, webbrowser.open, args=(endereco,)).start()

    try:
        uvicorn.run(app, host=host, port=porta, log_level="warning")
    except KeyboardInterrupt:
        print("\nEncerrando.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
