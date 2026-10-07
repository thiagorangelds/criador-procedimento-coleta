# Criador de Procedimento de Coleta

Gera, via Gemini, a documentação de coleta de logs para cada tecnologia listada no `config.yml`.

## Instalação

Requisitos: Linux ou macOS, `git` e Python 3.9+.

```bash
curl -fsSL https://raw.githubusercontent.com/thiagorangelds/criador-procedimento-coleta/main/instalar.sh | bash
```

O instalador:

- clona o repositório em `~/.local/share/criador-procedimento-coleta`;
- instala os `requirements.txt` num ambiente virtual próprio (`.venv`). Se o venv não estiver disponível, usa `pip3`/`pip` com `--user`;
- cria o comando `criador-procedimento` em `~/.local/bin` e, se preciso, adiciona essa pasta ao PATH no `.zshrc`/`.bashrc`.

Depois, abra um novo terminal e rode:

```bash
criador-procedimento               # abre a interface no navegador
criador-procedimento --atualizar   # atualiza o código e as dependências (preserva o config.yml)
bash ~/.local/share/criador-procedimento-coleta/instalar.sh --desinstalar
```

Se o terminal disser que o comando não foi encontrado, abra um novo terminal (o PATH só é recarregado em uma nova sessão) ou rode direto `~/.local/bin/criador-procedimento`.

Os documentos gerados ficam em `~/.local/share/criador-procedimento-coleta/app/procedimentos/` e também podem ser baixados pela interface.

Instalação manual, sem o instalador: `pip install -r app/requirements.txt` dentro de um clone do repositório.

Somente se `FORMATO_SAIDA` for `pdf`: o PDF é gerado pelo LibreOffice (headless), que precisa estar instalado:

```bash
sudo apt-get install -y libreoffice-writer   # Linux (Debian/Ubuntu)
brew install --cask libreoffice              # macOS
```

O script procura o executável no PATH (`soffice`/`libreoffice`) e no caminho padrão do macOS (`/Applications/LibreOffice.app`).

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `instalar.sh` | Instalador e atualizador (Linux/macOS) |
| `app/interface.py`, `app/interface.html` | Interface web local |
| `app/script.py`, `app/gerador_docx.py` | Geração dos documentos |
| `app/config.yml` | Configuração (comentada) |
| `app/requirements.txt` | Dependências Python |
| `app/templates/` | Modelo Word do Procedimento de Coleta |

## Configuração

Edite o `app/config.yml` (cada chave está comentada no próprio arquivo):

- `API_KEY`: chave da API do Gemini.
- `TECNOLOGIAS`: lista de tecnologias para as quais os procedimentos serão gerados.
- `RETRY`: tentativas por modelo em caso de limite de taxa/indisponibilidade.
- `MODELOS`: modelos do Gemini, em ordem de preferência (fallback).
- `MODELO_DOCX` (opcional): caminho do modelo Word usado no documento de procedimento. Padrão: `templates/modelo_procedimento_coleta.docx`.
- `FORMATO_SAIDA` (opcional): `docx` (padrão) ou `pdf`. Para `pdf` é necessário ter o LibreOffice instalado.
- `LIBREOFFICE` (opcional, só para `pdf`): caminho do executável do LibreOffice (`soffice`), caso não esteja no PATH.

## Uso

### Interface gráfica

```bash
python app/interface.py
```

Abre no navegador (`http://127.0.0.1:8765/`) um formulário com todas as opções do `config.yml`. Lá é possível:

- **Gerar documentos:** salva a configuração e inicia a geração das tecnologias informadas, com o andamento em tempo real.
- **Parar geração:** interrompe a geração antes da próxima tecnologia.
- **Configuração:** API key, formato, modelos e demais opções; **Salvar configuração** grava no `config.yml`.
- **Modelos do Gemini:** escolha, entre os modelos Flash do free tier, quais usar e em que ordem (fallback). Com a API key informada, a lista vem da API do Gemini; sem ela, ou se a consulta falhar, é usada uma lista padrão.
- **Documentos gerados:** baixa os arquivos de `procedimentos/`.

Opções: `--porta <n>` para usar outra porta e `--sem-navegador` para não abrir o navegador automaticamente. A interface só aceita conexões da própria máquina e não precisa de nenhuma dependência além das do `requirements.txt`.

### Linha de comando

```bash
python app/script.py
```

Usa diretamente o que estiver no `config.yml`.

Para cada tecnologia são gerados, em `app/procedimentos/<tecnologia>/`:

| Arquivo | Conteúdo |
|---|---|
| `procedimento_<tecnologia>.txt` | Documento completo: métodos de coleta, licenciamento, eventos de segurança, links e volumetria. |
| `catalogo_<tecnologia>.txt` | Catálogo de dados (padronização ECS). |
| `procedimento_coleta_<tecnologia>.docx` ou `.pdf` | Somente o procedimento de coleta (Introdução + passo a passo), no formato do modelo Word, conforme `FORMATO_SAIDA`. |

Em `pdf`, o `.docx` intermediário é gerado em diretório temporário e removido após a conversão. Se o Gemini devolver um conteúdo inválido para o procedimento, a resposta bruta é salva em `procedimento_coleta_<tecnologia>.json` para análise.

O modelo Word precisa manter os placeholders `dd.mm.aaaa`, `<TECNOLOGIA>`, `<Introdução sobre a tecnologia e o tipo de coleta>` e `<Passo a passo do procedimento>`, que são substituídos pelo script.
