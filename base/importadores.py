"""Importadores da base: leem o arquivo, validam e só então gravam (tudo ou nada).

Cada importação troca somente a sua tabela. Se o arquivo estiver errado, a base antiga fica como está.
  AtualiProdutos.csv      -> produtos_fiscal (código, barras, NCM, CEST)
  todos_os_produtos.xlsx  -> produtos_precos (embalagem G, custo J, compra K, venda L)
  tipi.docx               -> tipi (alíquota de IPI por NCM)
"""
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from .normalizar import normalizar_barras, normalizar_cest, normalizar_ncm, numero, sem_acento


class ErroImportacao(Exception):
    """Arquivo recusado. A mensagem diz o motivo, em português, para ir direto para a tela."""


@dataclass
class Leitura:
    linhas: list = field(default_factory=list)
    avisos: list = field(default_factory=list)


def _aviso_contagem(avisos, contagem, mensagens):
    for chave, texto in mensagens.items():
        if contagem[chave]:
            avisos.append(f"{contagem[chave]} {texto}")


# ---------------------------------------------------------------- AtualiProdutos.csv

def ler_fiscal(caminho):
    """CSV em Latin-1 com ';'. No topo há o bloco PIS/COFINS; o cabeçalho dos produtos começa com 'cod_interno'."""
    texto = Path(caminho).read_bytes().decode("latin-1")
    if texto.startswith("\xef\xbb\xbf"):  # BOM do UTF-8 lido como Latin-1
        texto = texto[3:]
    linhas = texto.splitlines()
    inicio = next((i for i, l in enumerate(linhas) if l.strip().lower().startswith("cod_interno;")), None)
    if inicio is None:
        raise ErroImportacao(
            "Este arquivo não parece o AtualiProdutos.csv: não achei a linha de cabeçalho que começa com 'cod_interno'."
        )
    cabecalho = [c.strip().lower() for c in linhas[inicio].split(";")]
    faltam = [c for c in ("cod_interno", "codbarra", "ncm", "cest") if c not in cabecalho]
    if faltam:
        raise ErroImportacao("O cabeçalho do AtualiProdutos.csv não tem as colunas: " + ", ".join(faltam) + ".")
    i_cod, i_bar, i_ncm, i_cest = (cabecalho.index(c) for c in ("cod_interno", "codbarra", "ncm", "cest"))
    maior = max(i_cod, i_bar, i_ncm, i_cest)

    saida = Leitura()
    vistos = set()
    c = Counter()
    for linha in linhas[inicio + 1:]:
        if not linha.strip():
            continue
        campos = linha.split(";")
        if len(campos) <= maior:
            c["curta"] += 1
            continue
        codigo = campos[i_cod].strip()
        if not codigo:
            c["sem_codigo"] += 1
            continue
        if codigo in vistos:
            c["repetido"] += 1
            continue
        vistos.add(codigo)
        barras = normalizar_barras(campos[i_bar])
        if not barras:
            c["sem_barras"] += 1
        ncm, problema_ncm = normalizar_ncm(campos[i_ncm])
        c["ncm_" + problema_ncm if problema_ncm else "ncm_ok"] += 1
        if not ncm and problema_ncm is None:
            c["ncm_vazio"] += 1
        cest, problema_cest = normalizar_cest(campos[i_cest])
        if problema_cest:
            c["cest_invalido"] += 1
        saida.linhas.append((codigo, barras, ncm, cest))

    if not saida.linhas:
        raise ErroImportacao("Não encontrei nenhum produto abaixo do cabeçalho do AtualiProdutos.csv.")
    _aviso_contagem(saida.avisos, c, {
        "curta": "linhas com poucas colunas foram ignoradas.",
        "sem_codigo": "linhas sem código interno foram ignoradas.",
        "repetido": "códigos internos repetidos: ficou o primeiro de cada um.",
        "sem_barras": "produtos sem código de barras (só serão achados pelo código).",
        "ncm_sufixo": "NCMs com sufixo depois do ponto (ex.: 09021000.1): usei os 8 primeiros dígitos.",
        "ncm_invalido": "NCMs inválidos: ficaram vazios.",
        "ncm_vazio": "produtos sem NCM.",
        "cest_invalido": "CESTs inválidos: ficaram vazios.",
    })
    return saida


# ---------------------------------------------------------------- todos_os_produtos.xlsx

# Posições fixas, porque o cabeçalho da planilha é desalinhado em relação aos dados:
# A código, B barras, G embalagem, J custo, K compra, L venda (confirmado pelo Guilherme).
_COL_CODIGO, _COL_BARRAS, _COL_EMBALAGEM, _COL_CUSTO, _COL_COMPRA, _COL_VENDA = 0, 1, 6, 9, 10, 11


def ler_precos(caminho):
    from openpyxl import load_workbook

    try:
        livro = load_workbook(caminho, read_only=True, data_only=True)
    except Exception as erro:
        raise ErroImportacao(f"Não consegui abrir a planilha: {erro}") from erro
    try:
        folha = livro.worksheets[0]
        linhas = folha.iter_rows(min_row=1, max_col=_COL_VENDA + 1, values_only=True)
        primeira = next(linhas, None)
        if primeira is None:
            raise ErroImportacao("A planilha está vazia.")
        titulo_a = sem_acento(primeira[0]).lower()
        titulo_b = sem_acento(primeira[1] if len(primeira) > 1 else "").lower()
        if "codigo" not in titulo_a or "barra" not in titulo_b:
            raise ErroImportacao(
                "Esta planilha não parece a todos_os_produtos: a coluna A deve se chamar 'Código' e a B, 'Cód. Barra'."
            )

        saida = Leitura()
        vistos = set()
        c = Counter()
        for linha in linhas:
            linha = tuple(linha) + (None,) * (_COL_VENDA + 1 - len(linha))
            codigo = str(linha[_COL_CODIGO]).strip() if linha[_COL_CODIGO] is not None else ""
            if not codigo:
                if any(v not in (None, "") for v in linha):
                    c["sem_codigo"] += 1
                continue
            if codigo in vistos:
                c["repetido"] += 1
                continue
            vistos.add(codigo)
            barras = normalizar_barras(linha[_COL_BARRAS])
            if not barras:
                c["sem_barras"] += 1
            valores = []
            for pos in (_COL_EMBALAGEM, _COL_CUSTO, _COL_COMPRA, _COL_VENDA):
                try:
                    valores.append(numero(linha[pos]))
                except ValueError:
                    valores.append(None)
                    c["nao_numerico"] += 1
            if all(v is None for v in valores):
                c["sem_valores"] += 1
            if valores[2] == 0:
                c["compra_zero"] += 1
            saida.linhas.append((codigo, barras, *valores))
    finally:
        livro.close()

    if not saida.linhas:
        raise ErroImportacao("Não encontrei nenhum produto na planilha.")
    if all(all(v is None for v in l[2:]) for l in saida.linhas):
        raise ErroImportacao(
            "As colunas G, J, K e L não têm números. A planilha está diferente do esperado (G embalagem, J custo, K compra, L venda)."
        )
    _aviso_contagem(saida.avisos, c, {
        "sem_codigo": "linhas sem código foram ignoradas.",
        "repetido": "códigos repetidos: ficou o primeiro de cada um.",
        "sem_barras": "produtos sem código de barras (só serão achados pelo código).",
        "nao_numerico": "valores que não são número ficaram vazios.",
        "sem_valores": "produtos sem nenhum valor de embalagem, custo, compra ou venda.",
        "compra_zero": "produtos com compra igual a zero.",
    })
    return saida


# ---------------------------------------------------------------- tipi.docx

_NCM_8 = re.compile(r"\d{4}\.\d{2}\.\d{2}")
_NCM_EX = re.compile(r"\d{4}\.\d{2}\.\d{2}\s+Ex", re.IGNORECASE)


def ler_tipi(caminho):
    """Lê as tabelas de NCM (3 colunas, cabeçalho 'NCM'). Só linhas de 8 dígitos têm alíquota; 'NT' vale 0."""
    import docx

    try:
        documento = docx.Document(str(caminho))
    except Exception as erro:
        raise ErroImportacao(f"Não consegui abrir o documento: {erro}") from erro

    saida = Leitura()
    vistos = set()
    c = Counter()
    for tabela in documento.tables:
        if len(tabela.columns) != 3 or not tabela.rows:
            continue
        if tabela.rows[0].cells[0].text.strip().upper() != "NCM":
            continue
        c["tabelas"] += 1
        for linha in tabela.rows:
            celulas = linha.cells
            ncm = celulas[0].text.strip()
            if not _NCM_8.fullmatch(ncm):
                if _NCM_EX.match(ncm):
                    c["excecao"] += 1
                continue
            texto = celulas[2].text.replace("\xa0", " ").replace("%", "").strip()
            if texto.upper() == "NT":
                aliquota = Decimal(0)
            else:
                try:
                    aliquota = Decimal(texto.replace(".", "").replace(",", ".")) if texto else None
                except Exception:
                    aliquota = None
            if aliquota is None:
                c["sem_aliquota"] += 1
                continue
            chave = ncm.replace(".", "")
            if chave in vistos:
                c["repetido"] += 1
                continue
            vistos.add(chave)
            saida.linhas.append((chave, aliquota))

    if not c["tabelas"] or not saida.linhas:
        raise ErroImportacao(
            "Este documento não parece a TIPI: não achei tabelas com as colunas NCM, DESCRIÇÃO e ALÍQUOTA com NCMs de 8 dígitos."
        )
    _aviso_contagem(saida.avisos, c, {
        "excecao": "linhas de exceção (Ex) ignoradas.",
        "sem_aliquota": "NCMs de 8 dígitos sem alíquota legível foram ignorados.",
        "repetido": "NCMs repetidos: ficou o primeiro de cada um.",
    })
    return saida


# ---------------------------------------------------------------- gravação (tudo ou nada)

def _gravar(conn, tabela, colunas, leitura, tipo, arquivo, email):
    with conn.transaction():
        conn.execute(f"delete from {tabela}")
        with conn.cursor() as cur:
            with cur.copy(f"copy {tabela} ({', '.join(colunas)}) from stdin") as copia:
                for linha in leitura.linhas:
                    copia.write_row(linha)
        conn.execute(
            "insert into importacoes (email, tipo, arquivo, linhas, avisos) values (%s, %s, %s, %s, %s)",
            (email or "", tipo, os.path.basename(str(arquivo)), len(leitura.linhas), list(leitura.avisos)),
        )
    return {"tipo": tipo, "linhas": len(leitura.linhas), "avisos": leitura.avisos}


def importar_fiscal(conn, caminho, email=""):
    leitura = ler_fiscal(caminho)
    return _gravar(conn, "produtos_fiscal", ("codigo", "barras", "ncm", "cest"), leitura, "fiscal", caminho, email)


def importar_precos(conn, caminho, email=""):
    leitura = ler_precos(caminho)
    colunas = ("codigo", "barras", "embalagem", "custo", "compra", "venda")
    return _gravar(conn, "produtos_precos", colunas, leitura, "precos", caminho, email)


def importar_tipi(conn, caminho, email=""):
    leitura = ler_tipi(caminho)
    return _gravar(conn, "tipi", ("ncm", "aliquota"), leitura, "tipi", caminho, email)
