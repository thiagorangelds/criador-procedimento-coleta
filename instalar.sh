#!/usr/bin/env bash
# Instalador do Criador de Procedimento de Coleta (Linux/macOS).
#
# Uso:
#   bash instalar.sh               instala ou atualiza
#   bash instalar.sh --desinstalar remove a instalação e o comando
#
# Variáveis opcionais:
#   CRIADOR_REPO   repositório git      (padrão: https://github.com/thiagorangelds/criador-procedimento-coleta.git)
#   CRIADOR_BRANCH branch a instalar    (padrão: main)
#   CRIADOR_DIR    pasta de instalação  (padrão: ~/.local/share/criador-procedimento-coleta)
#   CRIADOR_BIN    pasta do comando     (padrão: ~/.local/bin)

set -euo pipefail

REPO="${CRIADOR_REPO:-https://github.com/thiagorangelds/criador-procedimento-coleta.git}"
BRANCH="${CRIADOR_BRANCH:-main}"
DIR="${CRIADOR_DIR:-$HOME/.local/share/criador-procedimento-coleta}"
BACK="$DIR/backend"
BIN_DIR="${CRIADOR_BIN:-$HOME/.local/bin}"
COMANDO="criador-procedimento"
MARCADOR_PATH="# criador-procedimento-coleta"
PASTAS_ATALHO="$HOME/bin /opt/homebrew/bin /usr/local/bin"
COMANDO_NO_PATH=""
RC_ALTERADO=""
CONFIG_BACKUP=""
CONFIG_ORIGEM=""

info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
aviso() { printf '\033[1;33mAviso:\033[0m %s\n' "$*" >&2; }
erro() { printf '\033[1;31mErro:\033[0m %s\n' "$*" >&2; exit 1; }

arquivo_shell() {
    case "$(basename "${SHELL:-}")" in
        zsh) echo "$HOME/.zshrc" ;;
        bash) [ "$(uname -s)" = "Darwin" ] && echo "$HOME/.bash_profile" || echo "$HOME/.bashrc" ;;
        *) echo "$HOME/.profile" ;;
    esac
}

parar_interface() {
    command -v pkill >/dev/null 2>&1 || return 0
    local alvo
    # os dois primeiros são os caminhos das versões anteriores a backend/
    for alvo in "$DIR/interface.py" "$DIR/app/interface.py" "$BACK/servidor.py" "criador_procedimento.server"; do
        if pgrep -f "$alvo" >/dev/null 2>&1; then
            pkill -f "$alvo" || true
            info "Servidor em execução encerrado ($alvo)."
        fi
    done
}

desinstalar() {
    parar_interface
    info "Removendo $DIR"
    rm -rf "$DIR"
    info "Removendo $BIN_DIR/$COMANDO"
    rm -f "$BIN_DIR/$COMANDO"
    local pasta
    for pasta in $PASTAS_ATALHO; do
        if [ -L "$pasta/$COMANDO" ] && [ "$(readlink "$pasta/$COMANDO")" = "$BIN_DIR/$COMANDO" ]; then
            info "Removendo atalho $pasta/$COMANDO"
            rm -f "$pasta/$COMANDO"
        fi
    done
    info "Desinstalação concluída. Se quiser, remova a linha '$MARCADOR_PATH' de $(arquivo_shell)."
}

verificar_python() {
    command -v git >/dev/null 2>&1 || erro "git não encontrado. Instale-o (Linux: sudo apt-get install git | macOS: xcode-select --install)."
    command -v python3 >/dev/null 2>&1 || erro "python3 não encontrado. Instale o Python 3.9 ou superior."
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
        || erro "Python 3.9 ou superior é necessário (encontrado: $(python3 --version 2>&1))."
}

# Guarda a configuração do usuário antes do pull. app/config.yml e config.yml
# na raiz são os locais das versões anteriores a backend/.
preservar_config() {
    local candidato
    for candidato in backend/config.yml app/config.yml config.yml; do
        [ -f "$DIR/$candidato" ] || continue
        if git -C "$DIR" ls-files --error-unmatch "$candidato" >/dev/null 2>&1 \
            && git -C "$DIR" diff --quiet -- "$candidato" 2>/dev/null; then
            continue  # igual ao do repositório: nada de seu para preservar
        fi
        CONFIG_BACKUP="$(mktemp)"
        CONFIG_ORIGEM="$candidato"
        cp "$DIR/$candidato" "$CONFIG_BACKUP"
        git -C "$DIR" checkout -- "$candidato" 2>/dev/null || true
        return
    done
}

restaurar_config() {
    [ -n "$CONFIG_BACKUP" ] || return 0
    cp "$CONFIG_BACKUP" "$BACK/config.yml"
    rm -f "$CONFIG_BACKUP"
    if [ "$CONFIG_ORIGEM" = "backend/config.yml" ]; then
        info "Sua configuração (config.yml) foi preservada."
    else
        info "Sua configuração foi movida de $CONFIG_ORIGEM para backend/config.yml."
    fi
}

# Leva o que o usuário gerou (e o log) para backend/, e limpa a pasta app/ do
# layout antigo depois que nada mais de seu está lá.
migrar_layout_antigo() {
    local antigo
    for antigo in "$DIR/app/procedimentos" "$DIR/procedimentos"; do
        if [ -d "$antigo" ] && [ ! -d "$BACK/procedimentos" ]; then
            mv "$antigo" "$BACK/procedimentos"
            info "Documentos já gerados movidos para backend/procedimentos."
        fi
    done
    [ -d "$DIR/app" ] || return 0
    find "$DIR/app" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
    rm -f "$DIR/app/config.yml" "$DIR/app"/execucao.log*
    # -delete e bottom-up: tira as subpastas vazias e, por fim, a propria app/
    find "$DIR/app" -type d -empty -delete 2>/dev/null || true
    [ ! -d "$DIR/app" ] \
        || aviso "A pasta antiga $DIR/app ainda tem arquivos. Confira e remova quando quiser."
}

baixar_codigo() {
    if [ -d "$DIR/.git" ]; then
        info "Atualizando o código em $DIR"
        preservar_config
        git -C "$DIR" fetch --quiet origin "$BRANCH"
        git -C "$DIR" checkout --quiet "$BRANCH"
        git -C "$DIR" pull --quiet --ff-only origin "$BRANCH"
        restaurar_config
        migrar_layout_antigo
    else
        info "Clonando $REPO ($BRANCH) em $DIR"
        mkdir -p "$(dirname "$DIR")"
        git clone --quiet --branch "$BRANCH" "$REPO" "$DIR"
    fi
}

# Instalação editável de propósito: o "criador-procedimento --atualizar" faz
# git pull, e só no modo editável o código novo passa a valer sem reinstalar.
instalar_dependencias() {
    local venv="$DIR/.venv"
    if [ -x "$venv/bin/python" ] || python3 -m venv "$venv" >/dev/null 2>&1; then
        info "Instalando dependências no ambiente virtual ($venv)"
        "$venv/bin/python" -m pip install --quiet --upgrade pip setuptools
        "$venv/bin/python" -m pip install --quiet -e "$BACK"
        PYTHON_EXEC="$venv/bin/python"
        return
    fi

    rm -rf "$venv"
    aviso "Não foi possível criar o ambiente virtual (no Debian/Ubuntu: sudo apt-get install python3-venv). Tentando pip3/pip com --user."
    local pip_cmd
    if command -v pip3 >/dev/null 2>&1; then
        pip_cmd="pip3"
    elif command -v pip >/dev/null 2>&1; then
        pip_cmd="pip"
    else
        erro "pip/pip3 não encontrado. Instale o python3-venv ou o pip (Linux: sudo apt-get install python3-venv python3-pip)."
    fi
    info "Instalando dependências com $pip_cmd --user"
    "$pip_cmd" install --quiet --user -e "$BACK" \
        || erro "Falha ao instalar as dependências com $pip_cmd. Instale o python3-venv e rode o instalador novamente."
    PYTHON_EXEC="$(command -v python3)"
}

criar_comando() {
    mkdir -p "$BIN_DIR"
    cat > "$BIN_DIR/$COMANDO" <<EOF
#!/usr/bin/env bash
# Gerado por instalar.sh - sobe a API e abre a interface do Criador de Procedimento de Coleta.
if [ "\${1:-}" = "--atualizar" ]; then
    exec bash "$DIR/instalar.sh"
fi
exec "$PYTHON_EXEC" -m criador_procedimento.server "\$@"
EOF
    chmod +x "$BIN_DIR/$COMANDO"
    info "Comando criado: $BIN_DIR/$COMANDO"

    case ":$PATH:" in
        *":$BIN_DIR:"*) COMANDO_NO_PATH=1; return ;;
    esac

    local pasta
    for pasta in $PASTAS_ATALHO; do
        case ":$PATH:" in
            *":$pasta:"*)
                if [ -d "$pasta" ] && [ -w "$pasta" ] && { [ ! -e "$pasta/$COMANDO" ] || [ -L "$pasta/$COMANDO" ]; }; then
                    ln -sf "$BIN_DIR/$COMANDO" "$pasta/$COMANDO"
                    info "Atalho criado em $pasta/$COMANDO (pasta que já está no PATH)"
                    COMANDO_NO_PATH=1
                    return
                fi
                ;;
        esac
    done

    RC_ALTERADO="$(arquivo_shell)"
    if ! grep -qF "$MARCADOR_PATH" "$RC_ALTERADO" 2>/dev/null; then
        printf '\nexport PATH="%s:$PATH" %s\n' "$BIN_DIR" "$MARCADOR_PATH" >> "$RC_ALTERADO"
        info "$BIN_DIR adicionado ao PATH em $RC_ALTERADO"
    fi
}

main() {
    if [ "${1:-}" = "--desinstalar" ]; then
        desinstalar
        return
    fi

    verificar_python
    parar_interface
    baixar_codigo
    local arquivo
    for arquivo in backend/config.yml backend/pyproject.toml backend/src/criador_procedimento/main.py backend/src/criador_procedimento/server.py frontend/index.html; do
        [ -f "$DIR/$arquivo" ] || erro "$arquivo não encontrado no branch '$BRANCH' de $REPO. Verifique o branch (variável CRIADOR_BRANCH)."
    done
    instalar_dependencias
    criar_comando

    command -v soffice >/dev/null 2>&1 || command -v libreoffice >/dev/null 2>&1 \
        || [ -x /Applications/LibreOffice.app/Contents/MacOS/soffice ] \
        || aviso "LibreOffice não encontrado: necessário apenas para gerar em PDF (Linux: sudo apt-get install libreoffice-writer | macOS: brew install --cask libreoffice)."

    # \042 e \047 sao aspa dupla e simples: o valor e comparado sem elas e sem espaco
    local api_key
    api_key="$(sed -n 's/^API_KEY:[[:space:]]*//p' "$BACK/config.yml" 2>/dev/null | head -1 | tr -d '\042\047[:space:]')"
    if [ -z "$api_key" ] && [ -z "${CRIADOR_API_KEY:-}" ]; then
        aviso "Falta a API key do Gemini: preencha API_KEY em $BACK/config.yml (ou defina CRIADOR_API_KEY) antes de gerar."
    fi

    info "Instalação concluída."
    if [ -n "$COMANDO_NO_PATH" ]; then
        info "Para abrir a interface, rode: $COMANDO"
    else
        printf '\n\033[1;33m%s\033[0m\n' "IMPORTANTE: o comando '$COMANDO' só será reconhecido em um NOVO terminal."
        printf '%s\n' "Para usar neste terminal agora, rode um destes:"
        printf '    %s\n' "source $RC_ALTERADO && $COMANDO" "$BIN_DIR/$COMANDO"
        printf '\n'
    fi
    info "Para atualizar depois: $COMANDO --atualizar"
}

main "$@"
