"""Backend do Criador de Procedimento de Coleta.

    core/     configuração, logs e autenticação
    shared/   o que atravessa os módulos: caminhos e exceções
    modules/  uma pasta por feature, em camadas
    main.py   monta o FastAPI
    server.py sobe o uvicorn e abre a interface
    cli.py    geração por linha de comando, sem subir a API

Dependência anda num sentido só: `modules` conhece `shared` e `core`;
`shared` e `core` não conhecem `modules`.
"""

__version__ = "2.0.0"
