# Criador de Procedimento de Coleta

Gera, via Gemini, a documentação de coleta de logs de uma tecnologia: o levantamento completo, o catálogo de dados ECS e o **Procedimento de Coleta** em DOCX/PDF no modelo Word da Clavis.

O projeto é dividido em três camadas:

| Camada | Onde | O que faz |
|---|---|---|
| **Front** | `frontend/index.html` | Página única, sem build e sem dependência externa. Só fala com a API. |
| **API** | `backend/src/criador_procedimento/` | FastAPI organizado por feature. Recebe o pedido, enfileira o job e serve os documentos. Contrato em `/docs`. |
| **Motor** | `modules/geracao/` | Prompts, chamadas ao Gemini e escrita dos arquivos. Não sabe o que é HTTP. |

A API existe para ser usada por fora da interface: qualquer integração faz um `POST` com o nome da tecnologia e busca os documentos gerados.

## Instalação

Requisitos: Linux ou macOS, `git` e **Docker** (com o plugin Compose v2). A aplicação roda em container — é o que faz a geração em PDF funcionar sem instalar mais nada.

```bash
curl -fsSL https://raw.githubusercontent.com/thiagorangelds/criador-procedimento-coleta/main/instalar.sh | bash
```

O instalador:

- clona o repositório em `~/.local/share/criador-procedimento-coleta`;
- constrói a imagem (a primeira vez baixa o LibreOffice e demora alguns minutos);
- cria o comando `criador-procedimento`. Se `~/.local/bin` não estiver no PATH, cria um atalho numa pasta que já esteja (`~/bin`, `/opt/homebrew/bin` ou `/usr/local/bin`) ou adiciona `~/.local/bin` ao PATH no `.zshrc`/`.bashrc`. Nesse último caso, o comando só é reconhecido num terminal novo.

Antes do primeiro uso, informe a API key do Gemini — ela é **do servidor**, não da interface:

```bash
# em ~/.local/share/criador-procedimento-coleta/backend/config.yml
API_KEY: "sua-chave-aqui"
```

Depois, para subir a API e abrir a interface:

```bash
criador-procedimento
```

Os documentos ficam em `~/.local/share/criador-procedimento-coleta/backend/procedimentos/`, na máquina, e também são baixados pela interface. O container escreve ali por um bind mount, com o seu próprio usuário — nada fica preso dentro dele.

Instalação manual, sem o instalador, dentro de um clone do repositório: `docker compose up -d --build`.

## O comando é o container

```bash
criador-procedimento              sobe a API e abre a interface
criador-procedimento --parar      encerra o container
criador-procedimento --logs       acompanha o log
criador-procedimento --gerar ...  gera pela linha de comando, dentro do container
criador-procedimento --atualizar  busca a versão nova e reconstrói a imagem
```

Houve uma época em que dava para rodar de dois jeitos — Python direto na máquina ou container. **O jeito da máquina não gerava PDF**, porque o LibreOffice não estava lá, e a opção simplesmente aparecia desabilitada sem explicação óbvia. Agora existe um caminho só, e ele traz o LibreOffice dentro.

O que fica **na sua máquina**, fora do container: o `backend/config.yml` (montado como somente leitura, para a API key não entrar na imagem) e a pasta `backend/procedimentos`.

## Atualização

Use qualquer uma das opções:

```bash
criador-procedimento --atualizar
```

```bash
curl -fsSL https://raw.githubusercontent.com/thiagorangelds/criador-procedimento-coleta/main/instalar.sh | bash
```

As duas encerram o container se ele estiver no ar, atualizam o código, **reconstroem a imagem** e preservam o seu `config.yml` e os documentos já gerados.

### Quando a própria atualização muda o instalador

O bash lê o script conforme executa, mas o fluxo que já está em memória é o da versão **antiga**. Depois de um `git pull` que mude a estrutura, ele seguiria validando o layout velho contra a árvore nova — abortando no meio, ou pior, terminando "com sucesso" no estado errado, com o código já atualizado e o comando apontando para arquivos que acabaram de sair do lugar.

A atualização se corrige sozinha, em duas camadas independentes:

| Camada | O que faz |
|---|---|
| `instalar.sh` | compara a própria impressão antes e depois do pull e, se mudou, `exec` na versão nova |
| `criador-procedimento --atualizar` | confere o mesmo **por fora**, depois que o instalador termina, e roda a versão nova se ela tiver chegado |

Duas porque a primeira só vale se a versão **já instalada** a tiver. Numa instalação anterior a ela, o fluxo velho vai até o fim com as regras velhas, e quem percebe é o comando. A guarda `CRIADOR_INSTALADOR_REEXECUTADO` garante no máximo uma repetição.

O limite é honesto: isso não alcança uma instalação em que **as duas** camadas são antigas. Nessa, a primeira atualização ainda precisa ser rodada duas vezes — ou pelo `curl` abaixo, que executa o instalador novo desde o começo. A partir daí, nunca mais.

**Vindo de uma versão que rodava Python na máquina:** o `.venv` da instalação é removido, porque não é mais usado. A configuração e os documentos continuam onde estão, e passam a ser montados dentro do container.

**Vindo de uma versão anterior à divisão front/back:** a configuração e os documentos já gerados são movidos de `app/` para `backend/` automaticamente, e a pasta `app/` é removida quando não sobra nada seu nela. Vindo de uma versão anterior ainda à pasta `app/`, prefira o `curl`, pelo motivo da seção acima.

## Desinstalação

```bash
bash ~/.local/share/criador-procedimento-coleta/instalar.sh --desinstalar
```

Remove a instalação, o comando e o atalho, se houver. A configuração e os documentos gerados também são apagados, então copie antes o que quiser guardar.

## Estrutura

```
criador-procedimento-coleta/
├── instalar.sh                 instalador e atualizador (Linux/macOS)
├── docker-compose.yml          é como o comando sobe a aplicação
├── frontend/index.html         interface web, sem build
└── backend/
    ├── pyproject.toml          dependências, versão e os comandos do pacote
    ├── Dockerfile              build a partir da raiz do repositório
    ├── .env.example            as variáveis de ambiente aceitas
    ├── config.yml              configuração do servidor (comentada)
    ├── templates/              modelo Word do Procedimento de Coleta
    ├── tests/                  unit/ e integration/
    └── src/criador_procedimento/
        ├── main.py             monta o FastAPI
        ├── server.py           sobe o uvicorn e abre a interface
        ├── cli.py              geração por linha de comando
        ├── core/               config.py, logging.py, security.py
        ├── shared/             paths.py, exceptions.py
        └── modules/
            ├── sistema/        /api/saude e /api/config
            ├── jobs/           fila, estado e log das gerações
            ├── artefatos/      listagem e download dos documentos
            └── geracao/        o motor: prompts, Gemini, DOCX/PDF
```

Cada módulo segue as mesmas camadas — `router.py`, `schemas.py`, `service.py`, `repository.py`, `models.py` —, com `router` na borda e `repository` no que está fora do processo (a API do Gemini, o disco, a memória). `geracao` não tem `router.py` nem `schemas.py` de HTTP porque não é exposto direto: quem o expõe é `jobs`.

A dependência anda num sentido só: `modules` conhece `shared` e `core`; `shared` e `core` não conhecem `modules`.

## Configuração

Toda a configuração é **do servidor**: fica no `backend/config.yml`, no `backend/.env` ou no ambiente. Nem a interface nem a API escrevem configuração — numa instalação compartilhada, uma requisição não pode trocar a configuração de todo mundo.

Precedência: variável de ambiente > `.env` > `config.yml` > padrão. O que vem do ambiente nunca é escrito de volta no arquivo.

Os ajustes de **geração** são relidos a cada pedido, então corrigir a API key no `config.yml` vale na hora. Os de **servidor** (`HOST`, `PORTA`, `API_TOKEN`, `CORS_ORIGENS`) são lidos uma vez na subida e exigem reinício.

### Geração

- `API_KEY`: chave da API do Gemini, usada por todas as gerações do servidor.
- `MODELOS`: modelos do Gemini, em ordem de preferência. Vem com **um só**: o mais novo responde mais rápido, mas entrega cerca de um terço do conteúdo, e cair nele produziria um documento pela metade sem ninguém perceber. O `RETRY` insiste no mesmo modelo com backoff; se não der, a geração falha e aparece no log. Antes de acrescentar modelo, meça — o `config.yml` explica o porquê e `models.list()` lista modelo que não funciona.
- `RETRY`: tentativas por modelo em caso de limite de taxa/indisponibilidade.
- `FORMATO_SAIDA`: `docx` (padrão) ou `pdf`. Cada job pode pedir outro.
- `MODELO_DOCX` (opcional): modelo Word do documento de procedimento. Padrão: `templates/modelo_procedimento_coleta.docx`.
- `LIBREOFFICE` (opcional, só para `pdf`): caminho do executável (`soffice`), caso não esteja no PATH.
- `TECNOLOGIAS`: lista padrão **só** da geração por linha de comando. A interface e a API mandam a lista em cada pedido e ignoram esta chave.

### Servidor

- `HOST`: endereço de escuta. `127.0.0.1` (padrão) só aceita conexões da própria máquina; `0.0.0.0` expõe na rede.
- `PORTA`: porta da API e da interface (padrão `8765`).
- `API_TOKEN` (opcional): exigido em todas as rotas `/api`, menos `/api/saude`. Vazio significa sem autenticação — aceitável apenas com `HOST` em `127.0.0.1`.
- `CORS_ORIGENS` (opcional): origens liberadas, para um front servido em outro endereço.

### Variáveis de ambiente

Para deploy, as chaves sensíveis ficam fora do arquivo. Copie o `backend/.env.example` para `backend/.env` ou exporte no ambiente do serviço:

| Variável | Sobrepõe |
|---|---|
| `CRIADOR_API_KEY` | `API_KEY` |
| `CRIADOR_API_TOKEN` | `API_TOKEN` |
| `CRIADOR_HOST` | `HOST` |
| `CRIADOR_PORTA` | `PORTA` |
| `CRIADOR_CORS_ORIGENS` | `CORS_ORIGENS` (separado por vírgula) |

Além dessas, `CRIADOR_PASTA_SAIDA` move a pasta dos documentos gerados. Só faz sentido em container, onde ela precisa cair num volume.

## Uso

### Interface

```bash
criador-procedimento
```

Abre `http://127.0.0.1:8765/`. A página tem as tecnologias, o formato do documento, o andamento em tempo real e os documentos gerados, agrupados por pasta.

Para usar outra porta no host: `CRIADOR_PORTA_HOST=9000 criador-procedimento`.

A lista de tecnologias é guardada **no navegador**, não no servidor. Quando o servidor exige token, a interface pede o token uma vez e o guarda no mesmo navegador.

**Parar geração** interrompe antes da próxima tecnologia: a que já começou vai até o fim, porque não há como abortar uma chamada ao Gemini no meio.

### API

Documentação interativa em `/docs`, contrato em `/openapi.json`.

A geração leva minutos, então é assíncrona: o `POST` devolve `202` com o id do job, e a integração acompanha o estado.

```bash
BASE=http://127.0.0.1:8765
TOKEN=...   # só se o servidor tiver API_TOKEN

# 1. pede a geração
curl -s -X POST "$BASE/api/jobs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tecnologias": ["Fortinet Fortigate via syslog"]}'
# {"id":"4c4d11246bce","estado":"executando",...}

# 2. acompanha até concluir
curl -s "$BASE/api/jobs/4c4d11246bce" -H "Authorization: Bearer $TOKEN"
# {"estado":"concluido","resultados":[{"tecnologia":"...","arquivos":[{"url":"/api/artefatos/...","...":...}]}]}

# 3. baixa cada arquivo de resultados[].arquivos[].url
curl -s -O -J "$BASE/api/artefatos/fortinet_fortigate_via_syslog/procedimento_coleta_fortinet_fortigate_via_syslog.docx" \
  -H "Authorization: Bearer $TOKEN"
```

| Rota | O que faz |
|---|---|
| `GET /api/saude` | Estado do servidor. **Não exige token** — serve de health check. |
| `GET /api/config` | Ajustes do servidor, somente leitura. A API key nunca é devolvida. |
| `POST /api/jobs` | Enfileira a geração. Corpo: `tecnologias` (obrigatório) e `formato_saida` (opcional). |
| `GET /api/jobs` | Jobs recentes, do mais novo para o mais antigo. |
| `GET /api/jobs/{id}` | Estado do job e os arquivos que ele produziu. |
| `GET /api/jobs/{id}/log?desde=N` | Log do job a partir da linha `N`. |
| `POST /api/jobs/{id}/cancelar` | Para antes da próxima tecnologia. |
| `GET /api/artefatos` | Todos os arquivos já gerados. |
| `GET /api/artefatos/{caminho}` | Baixa um arquivo. |

Estados do job: `na_fila`, `executando`, `concluido`, `falhou`, `cancelado`. Um job com várias tecnologias segue para a próxima quando uma falha — o motivo fica em `resultados[].erro` da tecnologia que falhou.

Os jobs rodam **um de cada vez**, em fila: duas gerações em paralelo só dividiriam a mesma cota do Gemini. O `POST` responde na hora de qualquer jeito, com `estado: "na_fila"`.

A forma de coleta viaja dentro do nome da tecnologia, depois de `" via "` — `"AWS GuardDuty via S3 + SQS"`. Sem o `" via "`, o Gemini escolhe o método e justifica no documento.

Com `API_TOKEN` definido, mande `Authorization: Bearer <token>` ou `X-API-Token: <token>`. Erro vem sempre como `{"erros": ["..."]}`.

### Linha de comando

Sem subir a API, num container descartável:

```bash
criador-procedimento --gerar "Fortinet Fortigate via syslog"
criador-procedimento --gerar --formato pdf "Imperva WAF"
criador-procedimento --gerar                 # usa TECNOLOGIAS do config.yml
```

## Deploy em container

É o caminho recomendado para servidor, porque migrar vira copiar o `docker-compose.yml` e o `.env`.

```bash
cp backend/.env.example backend/.env   # preencha CRIADOR_API_KEY e CRIADOR_API_TOKEN
docker compose up -d --build
```

Sobe em `http://localhost:8765` com os documentos num volume nomeado (`procedimentos`). Para mudar a porta no host, `CRIADOR_PORTA_HOST=9000 docker compose up -d`.

Sem o compose, o build precisa ser feito a partir da **raiz** do repositório, porque a imagem leva `backend/` e `frontend/`:

```bash
docker build -f backend/Dockerfile -t criador-procedimento .
docker run -d -p 8765:8765 --env-file backend/.env -v procedimentos:/dados criador-procedimento
```

| Detalhe | Como está |
|---|---|
| Usuário | `criador`, uid 10001, não-root. O uid é fixo para a permissão do volume não depender de quem buildou |
| Documentos | `/dados`, declarado como `VOLUME`. **Sem volume, cada deploy perde o histórico** |
| Segredos | Só por `--env-file`/`env_file`. O `.dockerignore` barra `backend/.env` **e `backend/config.yml`**, porque o contexto de build pode ser uma instalação em uso com a API key preenchida. A imagem roda com os padrões do código; para ajustar `MODELOS` ou `RETRY`, monte o seu: `-v ./meu-config.yml:/app/backend/config.yml:ro` |
| Health check | `GET /api/saude`, que não exige token. Já embutido no `HEALTHCHECK` |
| DOCX e PDF | A imagem traz o LibreOffice e as fontes do modelo Word, então gera nos dois formatos sem nada a mais |
| Tamanho | ~900 MB; ~300 MB sem o LibreOffice |

**Para uma imagem bem menor, só com DOCX:**

```bash
COM_LIBREOFFICE=false docker compose up -d --build
docker build -f backend/Dockerfile --build-arg COM_LIBREOFFICE=false -t criador-procedimento:docx .
```

Aí a opção PDF aparece desabilitada na interface e um job com `formato_saida: "pdf"` é recusado com `400`.

### As fontes não são enfeite

O modelo Word pede Roboto, Arial, Calibri, Georgia e Consolas. Sem elas o LibreOffice substitui por qualquer coisa e o PDF sai com outro espaçamento, **sem erro nenhum para avisar**. A imagem instala Roboto de verdade, Carlito no lugar de Calibri e Liberation Sans no lugar de Arial.

Consolas, a fonte do bloco de código, não é redistribuível. Sem tratamento o LibreOffice a lê como proporcional e troca por uma fonte de texto corrido — o bloco de código perde o alinhamento. A imagem resolve com um alias de fontconfig para DejaVu Sans Mono. Declarar a fonte no `fontTable.xml` do DOCX **não** funciona: o LibreOffice deduz os atributos da fonte instalada e ignora o que o documento declara.

### Pontos de atenção

- **Defina `API_TOKEN`.** Sem ele, qualquer um que alcance a máquina gera documentos com a sua cota do Gemini e baixa tudo o que já foi gerado. O `server.py` avisa na subida quando escuta fora do loopback sem token; o uvicorn direto não avisa.
- Num servidor, o `docker-compose.yml` monta `backend/config.yml` e `backend/procedimentos` do próprio clone. `CRIADOR_UID`/`CRIADOR_GID` definem com que usuário o container escreve — o instalador preenche com o de quem instalou; num serviço, aponte para o dono da pasta.
- **Um worker só.** A fila de jobs e o histórico vivem na memória do processo: com `--workers 2`, cada um teria a sua fila e o `GET` do job cairia metade das vezes no processo que não o conhece. Para escalar de verdade, trocar `modules/jobs/repository.py` por algo compartilhado vem primeiro.
- Reiniciar o processo perde o histórico de jobs. Os arquivos já gravados ficam.

## Testes

Os testes rodam em Python na máquina, **não** no container: é o único lugar onde ainda se usa um venv, e só para desenvolver. Num clone, uma vez:

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -e "./backend[dev]"
```

Depois, a cada rodada:

```bash
cd backend && pytest
```

`tests/unit/` cobre configuração, resolução de caminho dos artefatos, a fila de jobs e o parsing da resposta do Gemini. `tests/integration/` sobe a API com o `TestClient` e exercita o caminho completo — fila, worker, escrita em disco, montagem do DOCX sobre o modelo Word real e download. O único ponto dublado é a chamada ao Gemini.

## Solução de problemas

| Sintoma | O que fazer |
|---|---|
| `command not found: criador-procedimento` | Abra um novo terminal, porque o PATH só é recarregado numa nova sessão, ou rode direto `~/.local/bin/criador-procedimento`. |
| Aviso na interface de que falta a API key | Preencha `API_KEY` no `backend/config.yml` (o caminho exato aparece no aviso) ou defina `CRIADOR_API_KEY`, e reinicie. |
| `401` nas chamadas da API | O servidor tem `API_TOKEN`. Mande `Authorization: Bearer <token>`; na interface, o cadeado na barra de cima guarda o token. |
| `O Docker não está rodando` | Abra o Docker Desktop (macOS) ou inicie o serviço (Linux) e rode de novo. |
| `O container subiu mas a API não respondeu` | `criador-procedimento --logs` mostra o que aconteceu lá dentro. |
| Porta 8765 ocupada | `CRIADOR_PORTA_HOST=9000 criador-procedimento`. |
| Algo ficou rodando de uma versão antiga, em Python | `pkill -f criador_procedimento.server`. O instalador já faz isso sozinho. |

## Geração em PDF

Funciona sem instalar nada: o LibreOffice (headless) vem na imagem, junto com as fontes do modelo Word. Para uma imagem bem menor, sem PDF, veja [Deploy em container](#deploy-em-container).

## O que é gerado

Para cada tecnologia, em `backend/procedimentos/<tecnologia>/`:

| Arquivo | Conteúdo |
|---|---|
| `procedimento_<tecnologia>.txt` | Documento completo: métodos de coleta, licenciamento, eventos de segurança, links e volumetria. |
| `catalogo_<tecnologia>.txt` | Catálogo de dados (padronização ECS). |
| `procedimento_coleta_<tecnologia>.docx` ou `.pdf` | Somente o procedimento de coleta (Introdução + passo a passo), no formato do modelo Word. |

Em `pdf`, o `.docx` intermediário é gerado em diretório temporário e removido após a conversão. Se o Gemini devolver um conteúdo inválido para o procedimento, a resposta bruta é salva em `procedimento_coleta_<tecnologia>.json` para análise.

O modelo Word precisa manter os placeholders `dd.mm.aaaa`, `<TECNOLOGIA>`, `<Introdução sobre a tecnologia e o tipo de coleta>` e `<Passo a passo do procedimento>`, que são substituídos na geração.
