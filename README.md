# Criador de Procedimento de Coleta

Gera, via Gemini, a documentação de coleta de logs para cada tecnologia listada no `config.yml`.

## Instalação

```bash
pip install -r requirements.txt
```

Somente se `FORMATO_SAIDA` for `pdf`: o PDF é gerado pelo LibreOffice (headless), que precisa estar instalado:

```bash
sudo apt-get install -y libreoffice-writer   # Linux (Debian/Ubuntu)
brew install --cask libreoffice              # macOS
```

O script procura o executável no PATH (`soffice`/`libreoffice`) e no caminho padrão do macOS (`/Applications/LibreOffice.app`).

## Configuração

Edite o `config.yml` (cada chave está comentada no próprio arquivo):

- `API_KEY`: chave da API do Gemini.
- `TECNOLOGIAS`: lista de tecnologias para as quais os procedimentos serão gerados.
- `RETRY`: tentativas por modelo em caso de limite de taxa/indisponibilidade.
- `MODELOS`: modelos do Gemini, em ordem de preferência (fallback).
- `MODELO_DOCX` (opcional): caminho do modelo Word usado no documento de procedimento. Padrão: `templates/modelo_procedimento_coleta.docx`.
- `FORMATO_SAIDA` (opcional): `docx` (padrão) ou `pdf`. Para `pdf` é necessário ter o LibreOffice instalado.
- `LIBREOFFICE` (opcional, só para `pdf`): caminho do executável do LibreOffice (`soffice`), caso não esteja no PATH.

## Uso

```bash
python script.py
```

Para cada tecnologia são gerados, em `procedimentos/<tecnologia>/`:

| Arquivo | Conteúdo |
|---|---|
| `procedimento_<tecnologia>.txt` | Documento completo: métodos de coleta, licenciamento, eventos de segurança, links e volumetria. |
| `catalogo_<tecnologia>.txt` | Catálogo de dados (padronização ECS). |
| `procedimento_coleta_<tecnologia>.docx` ou `.pdf` | Somente o procedimento de coleta (Introdução + passo a passo), no formato do modelo Word, conforme `FORMATO_SAIDA`. |

Em `pdf`, o `.docx` intermediário é gerado em diretório temporário e removido após a conversão. Se o Gemini devolver um conteúdo inválido para o procedimento, a resposta bruta é salva em `procedimento_coleta_<tecnologia>.json` para análise.

O modelo Word precisa manter os placeholders `dd.mm.aaaa`, `<TECNOLOGIA>`, `<Introdução sobre a tecnologia e o tipo de coleta>` e `<Passo a passo do procedimento>`, que são substituídos pelo script.
