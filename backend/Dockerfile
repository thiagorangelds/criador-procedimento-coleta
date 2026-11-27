# Build a partir da RAIZ do repositório, porque a imagem leva backend/ e frontend/:
#
#   docker build -f backend/Dockerfile -t criador-procedimento .
#   docker build -f backend/Dockerfile --build-arg COM_LIBREOFFICE=false -t criador-procedimento:docx .
#
# Ou, mais simples, pelo docker-compose.yml da raiz.

FROM python:3.12-slim

# O LibreOffice é o que converte o DOCX em PDF. Vem por padrão para a imagem
# servir sozinha nos dois formatos; passe --build-arg COM_LIBREOFFICE=false para
# uma imagem bem menor, onde um job com formato_saida "pdf" é recusado com 400.
ARG COM_LIBREOFFICE=true

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CRIADOR_HOST=0.0.0.0 \
    CRIADOR_PORTA=8765 \
    CRIADOR_PASTA_SAIDA=/dados

# As fontes não são enfeite: o modelo Word pede Roboto, Arial, Calibri, Georgia
# e Consolas. Sem elas o LibreOffice substitui por qualquer coisa e o PDF sai
# com outro espaçamento, sem erro nenhum para avisar.
RUN if [ "$COM_LIBREOFFICE" = "true" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends \
            libreoffice-writer \
            fonts-roboto \
            fonts-liberation \
            fonts-crosextra-carlito \
            fonts-crosextra-caladea \
            fonts-dejavu-core \
        && rm -rf /var/lib/apt/lists/*; \
    fi

# Consolas, a fonte do bloco de código, não é redistribuível e não existe aqui.
# Sem este alias o LibreOffice a trata como proporcional e substitui por uma
# fonte de texto corrido — o bloco de código sai desalinhado no PDF, sem erro
# nenhum para avisar. O fontTable.xml do DOCX não resolve: o LibreOffice deduz
# os atributos da fonte instalada, e ignora o que o documento declara.
RUN if [ "$COM_LIBREOFFICE" = "true" ]; then \
        printf '%s\n' \
            '<?xml version="1.0"?>' \
            '<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">' \
            '<fontconfig>' \
            '  <match target="pattern">' \
            '    <test name="family"><string>Consolas</string></test>' \
            '    <edit name="family" mode="assign" binding="same"><string>DejaVu Sans Mono</string></edit>' \
            '    <edit name="spacing" mode="assign"><const>mono</const></edit>' \
            '  </match>' \
            '</fontconfig>' \
            > /etc/fonts/conf.d/99-consolas.conf \
        && fc-cache -f >/dev/null; \
    fi

WORKDIR /app

# As dependências primeiro, numa camada só delas: mexer no código não reinstala
# o mundo. O __init__.py vem junto porque a versão do pyproject sai dele.
COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/src/criador_procedimento/__init__.py backend/src/criador_procedimento/__init__.py
RUN pip install -e ./backend

# Instalação editável e árvore espelhando o repositório porque os caminhos são
# derivados de __file__: config.yml, templates/ e o front precisam continuar
# ao lado do pacote. Instalado normal, eles cairiam dentro do site-packages.
# O .dockerignore barra backend/config.yml e backend/.env: o contexto de build
# pode ser uma instalação em uso, com a API key preenchida. A imagem roda com
# os padrões do código e recebe o que importa por CRIADOR_*.
COPY backend/ backend/
COPY frontend/ frontend/

# uid fixo para a permissão do volume não depender de quem buildou
RUN useradd --create-home --uid 10001 criador \
    && mkdir -p "$CRIADOR_PASTA_SAIDA" \
    && chown -R criador:criador "$CRIADOR_PASTA_SAIDA" /app

USER criador

# Os documentos gerados moram aqui. Sem volume, cada deploy perde o histórico.
VOLUME ["/dados"]
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/api/saude', timeout=3).status == 200 else 1)"

# Um worker só, de propósito: a fila de jobs e o histórico vivem na memória do
# processo. Com --workers 2 cada um teria a sua fila, e o GET do job cairia
# metade das vezes no processo que não o conhece.
CMD ["uvicorn", "criador_procedimento.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]
