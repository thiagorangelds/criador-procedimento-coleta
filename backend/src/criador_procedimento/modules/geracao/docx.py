"""Monta o `.docx` por cirurgia de XML cru sobre o modelo Word.

Não usa `python-docx`: abre o zip do modelo, edita `word/document.xml` como
string e grava o zip de volta. Três consequências para quem mexer aqui:

- os placeholders são procurados **já escapados** (`&lt;TECNOLOGIA&gt;`);
- marcador de lista exige um `abstractNum`/`num` com `numId=900` injetado em
  `word/numbering.xml`, e o `abstractNum` **tem que vir antes** de qualquer
  `w:num` existente;
- trocar o modelo Word quebra tudo se os placeholders `dd.mm.aaaa`,
  `<TECNOLOGIA>`, `<Introdução sobre a tecnologia e o tipo de coleta>` e
  `<Passo a passo do procedimento>` não forem preservados, cada um no seu
  próprio parágrafo.
"""

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from criador_procedimento.modules.geracao.schemas import ConteudoDoProcedimento

CAMINHOS_LIBREOFFICE = [
    "soffice",
    "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]
TIMEOUT_CONVERSAO_PDF = 180

PLACEHOLDER_DATA = "dd.mm.aaaa"
PLACEHOLDER_TECNOLOGIA = "&lt;TECNOLOGIA&gt;"
PLACEHOLDER_INTRODUCAO = "&lt;Introdução sobre a tecnologia e o tipo de coleta&gt;"
PLACEHOLDER_PROCEDIMENTO = "&lt;Passo a passo do procedimento&gt;"

NUM_ID_MARCADOR = 900

ABSTRACT_NUM_MARCADOR = f'''<w:abstractNum w:abstractNumId="{NUM_ID_MARCADOR}"><w:multiLevelType w:val="hybridMultilevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="●"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr><w:rPr><w:u w:val="none"/></w:rPr></w:lvl><w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="○"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="1440" w:hanging="360"/></w:pPr><w:rPr><w:u w:val="none"/></w:rPr></w:lvl></w:abstractNum><w:num w:numId="{NUM_ID_MARCADOR}"><w:abstractNumId w:val="{NUM_ID_MARCADOR}"/></w:num>'''

CARACTERES_INVALIDOS_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _texto(valor) -> str:
    return escape(CARACTERES_INVALIDOS_XML.sub("", str(valor or "")).strip())


def _run(texto: str, rpr: str = "") -> str:
    return f'<w:r>{f"<w:rPr>{rpr}</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{texto}</w:t></w:r>'


def _paragrafo(texto: str) -> str:
    return f'<w:p><w:pPr><w:jc w:val="both"/></w:pPr>{_run(_texto(texto))}</w:p>'


def _titulo(texto: str, nivel: int) -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="Heading{nivel}"/></w:pPr>{_run(_texto(texto))}</w:p>'


def _marcador(texto: str, nivel: int = 0) -> str:
    return (
        f'<w:p><w:pPr><w:numPr><w:ilvl w:val="{nivel}"/><w:numId w:val="{NUM_ID_MARCADOR}"/></w:numPr>'
        f'<w:spacing w:after="60"/></w:pPr>{_run(_texto(texto))}</w:p>'
    )


def _bloco_codigo(codigo: str) -> list:
    rpr = '<w:rFonts w:ascii="Consolas" w:cs="Consolas" w:eastAsia="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/><w:szCs w:val="18"/>'
    linhas = str(codigo).expandtabs(4).rstrip().splitlines()
    paragrafos = []
    for i, linha in enumerate(linhas):
        espaco_depois = "160" if i == len(linhas) - 1 else "0"
        texto = escape(CARACTERES_INVALIDOS_XML.sub("", linha))
        paragrafos.append(
            f'<w:p><w:pPr><w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>'
            f'<w:spacing w:after="{espaco_depois}" w:line="240" w:lineRule="auto"/><w:ind w:left="284" w:right="284"/></w:pPr>'
            f'{_run(texto, rpr)}</w:p>'
        )
    return paragrafos


def montar_introducao(conteudo: ConteudoDoProcedimento) -> list:
    return [_paragrafo(p) for p in conteudo.introducao]


def montar_procedimento(conteudo: ConteudoDoProcedimento) -> list:
    elementos = []

    if conteudo.pre_requisitos:
        elementos.append(_titulo("Pré-requisitos", 2))
        elementos += [_marcador(item) for item in conteudo.pre_requisitos]

    if conteudo.passos:
        elementos.append(_titulo("Passo a passo", 2))
    for numero, passo in enumerate(conteudo.passos, start=1):
        elementos.append(_titulo(f"Passo {numero} - {passo.titulo}", 3))
        elementos += [_paragrafo(p) for p in passo.descricao]
        elementos += [_marcador(item) for item in passo.itens]
        if passo.codigo.strip():
            elementos += _bloco_codigo(passo.codigo)

    if conteudo.validacao:
        elementos.append(_titulo("Validação da coleta", 2))
        elementos += [_marcador(item) for item in conteudo.validacao]

    return elementos


def _substituir_paragrafo(document_xml: str, placeholder: str, elementos: list) -> str:
    posicao = document_xml.find(placeholder)
    if posicao == -1:
        raise ValueError(f"Placeholder '{placeholder}' não encontrado no modelo DOCX.")
    inicio = document_xml.rfind("<w:p ", 0, posicao)
    fim = document_xml.find("</w:p>", posicao) + len("</w:p>")
    return document_xml[:inicio] + "".join(elementos) + document_xml[fim:]


def _adicionar_numeracao(numbering_xml: str) -> str:
    if f'w:abstractNumId="{NUM_ID_MARCADOR}"' in numbering_xml:
        return numbering_xml
    if numbering_xml.rstrip().endswith("/>") and "</w:numbering>" not in numbering_xml:
        return numbering_xml.rstrip()[:-2] + ">" + ABSTRACT_NUM_MARCADOR + "</w:numbering>"
    # abstractNum precisa vir antes de qualquer w:num existente
    primeiro_num = numbering_xml.find("<w:num ")
    if primeiro_num == -1:
        return numbering_xml.replace("</w:numbering>", ABSTRACT_NUM_MARCADOR + "</w:numbering>")
    abstract, num = ABSTRACT_NUM_MARCADOR.split("<w:num ", 1)
    numbering_xml = numbering_xml[:primeiro_num] + abstract + numbering_xml[primeiro_num:]
    return numbering_xml.replace("</w:numbering>", "<w:num " + num + "</w:numbering>")


def gerar_docx(caminho_modelo, caminho_saida, tecnologia: str, conteudo: ConteudoDoProcedimento, data_documento: date = None) -> None:
    data_documento = data_documento or date.today()

    with zipfile.ZipFile(caminho_modelo) as modelo:
        arquivos = {item: modelo.read(item.filename) for item in modelo.infolist()}

    for item in arquivos:
        if item.filename == "word/document.xml":
            xml = arquivos[item].decode("utf-8")
            xml = xml.replace(PLACEHOLDER_DATA, data_documento.strftime("%d.%m.%Y"))
            xml = xml.replace(PLACEHOLDER_TECNOLOGIA, _texto(tecnologia))
            xml = _substituir_paragrafo(xml, PLACEHOLDER_INTRODUCAO, montar_introducao(conteudo))
            xml = _substituir_paragrafo(xml, PLACEHOLDER_PROCEDIMENTO, montar_procedimento(conteudo))
            arquivos[item] = xml.encode("utf-8")
        elif item.filename == "word/numbering.xml":
            arquivos[item] = _adicionar_numeracao(arquivos[item].decode("utf-8")).encode("utf-8")

    with zipfile.ZipFile(caminho_saida, "w", zipfile.ZIP_DEFLATED) as saida:
        for item, dados in arquivos.items():
            saida.writestr(item, dados)


def localizar_libreoffice(caminho_configurado: str = None) -> str:
    for candidato in ([caminho_configurado] if caminho_configurado else CAMINHOS_LIBREOFFICE):
        executavel = shutil.which(candidato) or (candidato if os.path.isfile(candidato) else None)
        if executavel:
            return executavel
    return None


def converter_docx_para_pdf(libreoffice: str, caminho_docx, diretorio_saida) -> str:
    caminho_pdf = os.path.join(diretorio_saida, Path(caminho_docx).stem + ".pdf")
    if os.path.isfile(caminho_pdf):
        os.remove(caminho_pdf)

    with tempfile.TemporaryDirectory() as perfil:
        resultado = subprocess.run(
            [
                libreoffice,
                f"-env:UserInstallation={Path(perfil).as_uri()}",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(diretorio_saida),
                str(caminho_docx),
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_CONVERSAO_PDF,
        )

    if resultado.returncode != 0 or not os.path.isfile(caminho_pdf):
        raise RuntimeError(f"Falha na conversão para PDF via LibreOffice: {(resultado.stderr or resultado.stdout).strip()}")
    return caminho_pdf


def gerar_pdf(caminho_modelo, caminho_pdf, tecnologia: str, conteudo: ConteudoDoProcedimento, libreoffice: str) -> None:
    diretorio_saida = os.path.dirname(os.path.abspath(caminho_pdf))
    nome_base = Path(caminho_pdf).stem

    with tempfile.TemporaryDirectory() as diretorio_temporario:
        caminho_docx = os.path.join(diretorio_temporario, f"{nome_base}.docx")
        gerar_docx(caminho_modelo, caminho_docx, tecnologia, conteudo)
        converter_docx_para_pdf(libreoffice, caminho_docx, diretorio_saida)
