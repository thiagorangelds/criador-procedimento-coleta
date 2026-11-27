#!/usr/bin/env bash
# Instalador do Criador de Procedimento de Coleta (Linux/macOS).
#
# A aplicação roda SEMPRE em container. Antes havia dois caminhos — Python na
# máquina ou container — e o da máquina não gerava PDF, porque o LibreOffice
# não estava lá. Agora existe um só, e ele traz o LibreOffice dentro.
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

# Guardados porque baixar_codigo pode precisar reexecutar este script.
ARGS=("$@")

# Shell aberto numa pasta que depois foi apagada: o pip estoura com
# FileNotFoundError em os.getcwd() e a atualização morre no meio. Só saímos de
# lá quando o diretório atual realmente sumiu, para não atrapalhar quem passa
# CRIADOR_REPO ou CRIADOR_DIR como caminho relativo.
if ! pwd -P >/dev/null 2>&1; then
    cd "$HOME" 2>/dev/null || cd /
fi

REPO="${CRIADOR_REPO:-https://github.com/thiagorangelds/criador-procedimento-coleta.git}"
BRANCH="${CRIADOR_BRANCH:-main}"
DIR="${CRIADOR_DIR:-$HOME/.local/share/criador-procedimento-coleta}"
INSTALADOR="$DIR/instalar.sh"
BACK="$DIR/backend"
BIN_DIR="${CRIADOR_BIN:-$HOME/.local/bin}"
# Quem escolheu a pasta do comando escolheu de propósito: nesse caso o
# instalador não planta atalho em pasta global, que sobrescreveria o comando
# de uma instalação diferente na mesma máquina.
BIN_ESCOLHIDO="${CRIADOR_BIN:+1}"
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
    if [ -f "$DIR/docker-compose.yml" ] && docker compose version >/dev/null 2>&1; then
        if [ -n "$(docker compose -f "$DIR/docker-compose.yml" ps -q 2>/dev/null)" ]; then
            docker compose -f "$DIR/docker-compose.yml" down >/dev/null 2>&1 || true
            info "Container em execução encerrado."
        fi
    fi

    # Sobras das versões que rodavam Python direto na máquina.
    command -v pkill >/dev/null 2>&1 || return 0
    local alvo
    for alvo in "$DIR/interface.py" "$DIR/app/interface.py" "$BACK/servidor.py" "criador_procedimento.server"; do
        if pgrep -f "$alvo" >/dev/null 2>&1; then
            pkill -f "$alvo" || true
            info "Servidor em execução encerrado ($alvo)."
        fi
    done
}

desinstalar() {
    parar_interface
    if docker image inspect criador-procedimento:latest >/dev/null 2>&1; then
        docker image rm criador-procedimento:latest >/dev/null 2>&1 \
            && info "Imagem criador-procedimento:latest removida." \
            || aviso "Não foi possível remover a imagem criador-procedimento:latest."
    fi
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

verificar_requisitos() {
    command -v git >/dev/null 2>&1 \
        || erro "git não encontrado. Instale-o (Linux: sudo apt-get install git | macOS: xcode-select --install)."
    command -v docker >/dev/null 2>&1 \
        || erro "docker não encontrado. Instale o Docker (macOS: https://docs.docker.com/desktop/install/mac-install/ | Linux: https://docs.docker.com/engine/install/)."
    docker compose version >/dev/null 2>&1 \
        || erro "'docker compose' não disponível. Atualize o Docker: o plugin Compose v2 é necessário."
    docker info >/dev/null 2>&1 \
        || erro "O Docker não está rodando. Abra o Docker Desktop (ou inicie o serviço no Linux) e rode de novo."
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
    mkdir -p "$BACK"
    cp "$CONFIG_BACKUP" "$BACK/config.yml"
    rm -f "$CONFIG_BACKUP"
    if [ "$CONFIG_ORIGEM" = "backend/config.yml" ]; then
        info "Sua configuração (config.yml) foi preservada."
        return 0
    fi
    info "Sua configuração foi movida de $CONFIG_ORIGEM para backend/config.yml."
    # O arquivo no lugar antigo não é mais lido por ninguém e carrega uma cópia
    # da API key. Só sai depois que a cópia nova já está em disco.
    if [ -f "$DIR/$CONFIG_ORIGEM" ] && [ -f "$BACK/config.yml" ]; then
        rm -f "$DIR/$CONFIG_ORIGEM"
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

# Impressão do instalador em disco, para saber se o pull trocou o próprio
# script. shasum existe no macOS, sha1sum no Linux; sem nenhum dos dois, o
# tamanho já denuncia a troca.
impressao_do_instalador() {
    [ -f "$INSTALADOR" ] || return 0
    if command -v shasum >/dev/null 2>&1; then
        shasum "$INSTALADOR" | cut -d" " -f1
    elif command -v sha1sum >/dev/null 2>&1; then
        sha1sum "$INSTALADOR" | cut -d" " -f1
    else
        wc -c < "$INSTALADOR" | tr -d " "
    fi
}

# O bash lê o script conforme executa, mas o fluxo que já está em memória é o
# da versão ANTIGA: depois de um pull que mude a estrutura do projeto, ele
# continuaria validando o layout velho contra a árvore nova e abortaria. Por
# isso, se o instalador mudou, passamos a bola para a versão nova.
#
# Vem depois de restaurar_config de propósito: até ali a configuração do
# usuário só existe num arquivo temporário que a versão nova não conheceria.
reexecutar_instalador_novo() {
    local antes="$1" depois
    depois="$(impressao_do_instalador)"
    [ -n "$antes" ] && [ -n "$depois" ] && [ "$antes" != "$depois" ] || return 0

    if [ -n "${CRIADOR_INSTALADOR_REEXECUTADO:-}" ]; then
        aviso "O instalador mudou de novo após reexecutar. Seguindo com o que está em memória."
        return 0
    fi

    info "O instalador mudou nesta atualização. Reexecutando a versão nova."
    exec env \
        CRIADOR_INSTALADOR_REEXECUTADO=1 \
        CRIADOR_REPO="$REPO" CRIADOR_BRANCH="$BRANCH" \
        CRIADOR_DIR="$DIR" CRIADOR_BIN="$BIN_DIR" \
        bash "$INSTALADOR" ${ARGS[@]+"${ARGS[@]}"}
}

baixar_codigo() {
    if [ -d "$DIR/.git" ]; then
        info "Atualizando o código em $DIR"
        local instalador_antes
        instalador_antes="$(impressao_do_instalador)"
        preservar_config
        git -C "$DIR" fetch --quiet origin "$BRANCH"
        git -C "$DIR" checkout --quiet "$BRANCH"
        git -C "$DIR" pull --quiet --ff-only origin "$BRANCH"
        restaurar_config
        reexecutar_instalador_novo "$instalador_antes"
        migrar_layout_antigo
    else
        info "Clonando $REPO ($BRANCH) em $DIR"
        mkdir -p "$(dirname "$DIR")"
        git clone --quiet --branch "$BRANCH" "$REPO" "$DIR"
    fi
}

construir_imagem() {
    # Os documentos são um bind mount: sem criar a pasta antes, o Docker a
    # criaria como root e o container não conseguiria escrever nela.
    mkdir -p "$BACK/procedimentos"

    info "Construindo a imagem (a primeira vez baixa o LibreOffice e demora alguns minutos)"
    CRIADOR_UID="$(id -u)" CRIADOR_GID="$(id -g)" \
        docker compose -f "$DIR/docker-compose.yml" build \
        || erro "Falha ao construir a imagem. Veja a saída acima."

    # O venv das versões que rodavam Python na máquina não serve mais para nada.
    if [ -d "$DIR/.venv" ]; then
        rm -rf "$DIR/.venv"
        info "Ambiente virtual antigo removido: a aplicação agora roda em container."
    fi
}

criar_comando() {
    mkdir -p "$BIN_DIR"
    cat > "$BIN_DIR/$COMANDO" <<EOF
#!/usr/bin/env bash
# Gerado por instalar.sh - sobe a API e a interface do Criador de Procedimento
# de Coleta, em container. O LibreOffice mora na imagem: e por isso que a
# geracao em PDF funciona sem instalar nada na maquina.
set -euo pipefail

DIR="$DIR"
PORTA="\${CRIADOR_PORTA_HOST:-8765}"
ENDERECO="http://127.0.0.1:\$PORTA/"

# O container escreve em backend/procedimentos pelo bind mount: rodar com o id
# de quem chamou evita arquivo que o dono da pasta nao consegue apagar depois.
export CRIADOR_UID="\$(id -u)" CRIADOR_GID="\$(id -g)"

compose() { docker compose -f "\$DIR/docker-compose.yml" "\$@"; }

abrir_navegador() {
    [ -z "\${CRIADOR_SEM_NAVEGADOR:-}" ] || return 0
    if command -v open >/dev/null 2>&1; then          # macOS
        open "\$1" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then    # Linux
        xdg-open "\$1" >/dev/null 2>&1 || true
    fi
}

exigir_docker() {
    command -v docker >/dev/null 2>&1 || {
        printf '\033[1;31mErro:\033[0m %s\n' "docker nao encontrado. Instale o Docker e rode: $COMANDO --atualizar" >&2
        exit 1
    }
    docker info >/dev/null 2>&1 || {
        printf '\033[1;31mErro:\033[0m %s\n' "O Docker nao esta rodando. Abra o Docker Desktop e tente de novo." >&2
        exit 1
    }
}

case "\${1:-}" in
    --atualizar)
        # Segunda camada da atualizacao. O instalar.sh ja se reexecuta sozinho
        # quando percebe que mudou, mas isso so vale se a versao instalada tiver
        # essa logica: numa instalacao antiga, o fluxo velho segue ate o fim
        # usando as regras velhas e termina "com sucesso" no estado errado.
        # Aqui a conferencia e por fora, entao nao depende do instalador.
        #
        # As variaveis vao junto: sem elas, uma instalacao em caminho
        # customizado se atualizaria por cima da instalacao padrao.
        rodar_instalador() {
            env CRIADOR_REPO="$REPO" CRIADOR_BRANCH="$BRANCH" CRIADOR_DIR="$DIR" CRIADOR_BIN="$BIN_DIR" \
                bash "$DIR/instalar.sh"
        }
        impressao() {
            [ -f "$DIR/instalar.sh" ] || return 0
            if command -v shasum >/dev/null 2>&1; then shasum "$DIR/instalar.sh" | cut -d" " -f1
            elif command -v sha1sum >/dev/null 2>&1; then sha1sum "$DIR/instalar.sh" | cut -d" " -f1
            else wc -c < "$DIR/instalar.sh" | tr -d " "; fi
        }

        antes="\$(impressao)"
        rodar_instalador || saiu_com_erro=1
        depois="\$(impressao)"

        # Se o proprio instalador trocou durante a execucao, o que acabou de
        # rodar foi a versao antiga. Roda a nova uma vez, e so uma: a guarda
        # vai no ambiente para a segunda execucao nao repetir isto.
        if [ -n "\$antes" ] && [ -n "\$depois" ] && [ "\$antes" != "\$depois" ]; then
            printf '\033[1;36m==>\033[0m %s\n' "O instalador mudou durante a atualizacao. Rodando a versao nova."
            exec env CRIADOR_INSTALADOR_REEXECUTADO=1 \
                CRIADOR_REPO="$REPO" CRIADOR_BRANCH="$BRANCH" CRIADOR_DIR="$DIR" CRIADOR_BIN="$BIN_DIR" \
                bash "$DIR/instalar.sh"
        fi
        exit "\${saiu_com_erro:-0}"
        ;;
    --parar)
        exigir_docker
        compose down
        exit 0
        ;;
    --logs)
        exigir_docker
        exec docker compose -f "\$DIR/docker-compose.yml" logs -f
        ;;
    --gerar)
        exigir_docker
        shift
        exec docker compose -f "\$DIR/docker-compose.yml" run --rm api criador-procedimento-gerar "\$@"
        ;;
    --ajuda|-h|--help)
        printf '%s\n' \
            "$COMANDO              sobe a API e abre a interface em \$ENDERECO" \
            "$COMANDO --parar      encerra o container" \
            "$COMANDO --logs       acompanha o log do container" \
            "$COMANDO --gerar ...  gera pela linha de comando, dentro do container" \
            "$COMANDO --atualizar  busca a versao nova e reconstroi a imagem"
        exit 0
        ;;
esac

exigir_docker
mkdir -p "\$DIR/backend/procedimentos"
compose up -d

# A imagem sobe em segundos, mas o uvicorn leva um instante: so abre o
# navegador quando a API responder, senao o usuario ve uma pagina de erro.
for _ in \$(seq 1 60); do
    if curl -fsS -m 2 "\${ENDERECO}api/saude" >/dev/null 2>&1; then
        printf '\033[1;36m==>\033[0m %s\n' "API e interface em \$ENDERECO (documentacao em \${ENDERECO}docs)"
        abrir_navegador "\$ENDERECO"
        printf '\033[1;36m==>\033[0m %s\n' "Para encerrar: $COMANDO --parar"
        exit 0
    fi
    sleep 1
done

printf '\033[1;31mErro:\033[0m %s\n' "O container subiu mas a API nao respondeu. Veja: $COMANDO --logs" >&2
exit 1
EOF
    chmod +x "$BIN_DIR/$COMANDO"
    info "Comando criado: $BIN_DIR/$COMANDO"

    case ":$PATH:" in
        *":$BIN_DIR:"*) COMANDO_NO_PATH=1; return ;;
    esac

    if [ -n "$BIN_ESCOLHIDO" ]; then
        aviso "$BIN_DIR não está no PATH. Chame por $BIN_DIR/$COMANDO ou acrescente a pasta ao PATH."
        return
    fi

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

    verificar_requisitos
    parar_interface
    baixar_codigo
    local arquivo
    for arquivo in docker-compose.yml backend/Dockerfile backend/config.yml backend/pyproject.toml backend/src/criador_procedimento/main.py frontend/index.html; do
        [ -f "$DIR/$arquivo" ] || erro "$arquivo não encontrado no branch '$BRANCH' de $REPO. Verifique o branch (variável CRIADOR_BRANCH)."
    done
    construir_imagem
    criar_comando

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
    info "Outras opções: $COMANDO --ajuda"
}

main "$@"
