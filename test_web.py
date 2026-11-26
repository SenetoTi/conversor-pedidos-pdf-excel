"""
Testes do site (Etapa 4): python test_web.py

PDFs e arquivos da base são inventados aqui mesmo. Os testes da tela Atualizar base precisam de TEST_DATABASE_URL
(schema temporário, apagado no fim), por exemplo:
  TEST_DATABASE_URL=postgresql://postgres@localhost:5432/conversor_teste python test_web.py
"""
import os
import tempfile
import time
import uuid

import fitz
from fastapi.testclient import TestClient
from openpyxl import load_workbook

os.environ["ADMIN_EMAILS"] = "chefe@empresa.com, outro@empresa.com"
os.environ.pop("CONVERSOR_DATABASE_URL", None)

import test_base
from web import app as site

USUARIO = {"X-Usuario-Email": "ana@empresa.com"}
ADMIN = {"X-Usuario-Email": "Chefe@empresa.com"}  # maiúscula de propósito


def pdf_de_texto(linhas):
    caminho = os.path.join(tempfile.gettempdir(), f"web_{uuid.uuid4().hex[:8]}.pdf")
    doc = fitz.open()
    pagina = doc.new_page()
    y = 60
    for linha in linhas:
        pagina.insert_text((40, y), linha, fontsize=8)
        y += 14
    doc.save(caminho)
    doc.close()
    return caminho


def esperar(cliente, trabalho_url, cab):
    for _ in range(120):
        e = cliente.get(trabalho_url + "/estado", headers=cab).json()
        if e["estado"] in ("pronto", "erro"):
            return e
        time.sleep(0.5)
    raise AssertionError("não terminou")


def enviar_pdf(cliente, rota, pdf, cab, **campos):
    with open(pdf, "rb") as f:
        r = cliente.post(rota, headers=cab, files={"pdf": ("meu pedido.pdf", f, "application/pdf")}, data=campos, follow_redirects=False)
    return r


def test_sem_cabecalho_403(c):
    for rota in ("/conversor/", "/conversor/base", "/conversor/trabalho/x", "/conversor/trabalho/x/estado"):
        assert c.get(rota).status_code == 403, rota
    assert c.post("/conversor/generico", files={"pdf": ("a.pdf", b"x", "application/pdf")}).status_code == 403
    r = c.get("/conversor/", headers={"Accept": "text/html"})
    assert r.status_code == 403 and "Central de Gestão" in r.text


def test_telas(c):
    r = c.get("/conversor/", headers=USUARIO)
    assert r.status_code == 200 and "Pedido de compra" in r.text and "Fidelidade da NF" in r.text
    assert "Atualizar base" not in r.text  # o link só aparece para admin
    assert 'src="data:image/png;base64,' in r.text  # ícone do Conversor no cabeçalho
    r = c.get("/conversor/?aba=generico", headers=USUARIO)
    assert "Qualquer PDF" in r.text and "Fidelidade" not in r.text
    assert "Atualizar base" in c.get("/conversor/", headers=ADMIN).text
    assert c.get("/conversor/status").json() == {"ok": True}


def test_converter_generico(c):
    pdf = pdf_de_texto(["Relatorio de teste", "linha 1   10,00   20,00", "linha 2   30,00   40,00"])
    r = enviar_pdf(c, "/conversor/generico", pdf, USUARIO)
    assert r.status_code == 303, r.status_code
    url = r.headers["location"]
    assert url.startswith("/conversor/trabalho/")
    # outra pessoa não vê o trabalho
    assert c.get(url, headers={"X-Usuario-Email": "bia@empresa.com"}).status_code == 404
    assert "meu pedido.pdf" in c.get(url, headers=USUARIO).text
    e = esperar(c, url, USUARIO)
    assert e["estado"] == "pronto", e
    r = c.get(url + "/baixar", headers=USUARIO)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    caminho = os.path.join(tempfile.gettempdir(), "web_baixado.xlsx")
    with open(caminho, "wb") as f:
        f.write(r.content)
    assert load_workbook(caminho).sheetnames
    os.remove(caminho)
    # depois de baixar o temporário some
    assert c.get(url + "/estado", headers=USUARIO).status_code == 404
    os.remove(pdf)


def test_converter_pedido(c):
    """Pedido sintético sem base configurada: a planilha sai sem as colunas da base e o log avisa."""
    pdf = pdf_de_texto([
        "PEDIDO DE COMPRA",
        "EMPRESA TESTE LTDA CNPJ: 11.111.111/0001-11",
        "Cod. Forn. Codigo Codigo de Barras Descricao UM Quant. Preco Unit. Total",
        "ABC-1 100001 7890000000011 ITEM TESTE UN 1 10,000 5,00 50,00",
        "ABC-2 100002 7890000000028 OUTRO ITEM UN 1 2,000 3,00 6,00",
        "Total Geral: 56,00",
    ])
    r = enviar_pdf(c, "/conversor/pedido", pdf, USUARIO, fidelidade="NF 1")
    assert r.status_code == 303
    url = r.headers["location"]
    e = esperar(c, url, USUARIO)
    if e["estado"] == "pronto":
        assert any("Base de produtos indisponível" in m for m in e["log"]), e["log"]
    else:  # PDF sintético simples demais para o leitor de pedidos: o erro aparece na tela, sem derrubar o site
        assert e["erro"], e
    assert c.get(url, headers=USUARIO).status_code == 200
    os.remove(pdf)


PEDIDO_SINTETICO = [
    "PEDIDO DE COMPRA",
    "EMPRESA TESTE LTDA CNPJ: 11.111.111/0001-11",
    "Cod. Forn. Codigo Codigo de Barras Descricao UM Quant. Preco Unit. Total",
    "ABC-1 100001 7890000000011 ITEM TESTE UN 1 10,000 5,00 50,00",
    "ABC-2 100002 7890000000028 OUTRO ITEM UN 1 2,000 3,00 6,00",
    "Total Geral: 56,00",
]


def test_pedido_com_base(c):
    """Com a base: as colunas novas e a Fidelidade chegam na planilha baixada."""
    pdf = pdf_de_texto(PEDIDO_SINTETICO)
    r = enviar_pdf(c, "/conversor/pedido", pdf, USUARIO, fidelidade="  NF 99  ")
    url = r.headers["location"]
    assert esperar(c, url, USUARIO)["estado"] == "pronto"
    caminho = os.path.join(tempfile.gettempdir(), "web_com_base.xlsx")
    with open(caminho, "wb") as f:
        f.write(c.get(url + "/baixar", headers=USUARIO).content)
    ws = load_workbook(caminho).active
    linhas = list(ws.iter_rows(values_only=True))
    cab = next(l for l in linhas if l[0] == "Cód. Forn.")
    assert cab[8:] == ("Preço de venda", "NCM", "CEST", "IPI (%)", "Qtd. embalagem", "Valor Tabela comprado", "Fidelidade da NF", "Conferência"), cab
    item = next(l for l in linhas if l[2] == "7890000000011")  # pelo código de barras (o código do fornecedor pode vir emendado ao cabeçalho)
    assert item[8:15] == (20, "70134100", "14.001.00", 10, 36, 8.22, "NF 99"), item
    os.remove(caminho)
    os.remove(pdf)


def test_pdf_invalido(c):
    r = c.post("/conversor/generico", headers=USUARIO, files={"pdf": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 400
    r = c.post("/conversor/generico", headers=USUARIO, files={"pdf": ("a.pdf", b"nao e pdf", "application/pdf")}, follow_redirects=False)
    url = r.headers["location"]
    e = esperar(c, url, USUARIO)
    assert e["estado"] == "erro" and e["erro"], e


def test_base_so_admin(c):
    assert c.get("/conversor/base", headers=USUARIO).status_code == 403
    r = c.post("/conversor/base/fiscal", headers=USUARIO, files={"arquivo": ("x.csv", b"x")})
    assert r.status_code == 403
    r = c.get("/conversor/base", headers=ADMIN)
    assert r.status_code == 200 and "AtualiProdutos.csv" in r.text and "não configurado" in r.text  # sem banco
    assert c.post("/conversor/base/outro", headers=ADMIN, files={"arquivo": ("x", b"x")}).status_code == 404


def test_base_com_banco(c, url):
    import base
    schema = "teste_" + uuid.uuid4().hex[:10]
    site.abrir_banco = lambda: base.conectar(url, schema=schema)
    try:
        csv_, xlsx, docx_ = test_base.arquivos()
        for tipo, caminho in [("fiscal", csv_), ("tipi", docx_), ("precos", xlsx)]:
            with open(caminho, "rb") as f:
                r = c.post(f"/conversor/base/{tipo}", headers=ADMIN, files={"arquivo": (os.path.basename(caminho), f)})
            assert r.status_code == 200 and "linhas importadas" in r.text, r.text[:300]
        r = c.get("/conversor/base", headers=ADMIN)
        for nome in ("AtualiProdutos.csv", "tipi.docx", "todos os produtos.xlsx"):
            assert nome in r.text, nome
        assert "chefe@empresa.com" in r.text.lower() and "Histórico" in r.text
        assert "nunca" not in r.text  # as três já têm data
        test_pedido_com_base(c)
        # arquivo errado: erro na tela e a base fica como estava
        with open(xlsx, "rb") as f:
            r = c.post("/conversor/base/fiscal", headers=ADMIN, files={"arquivo": ("errado.xlsx", f)})
        assert r.status_code == 200 and "aviso erro" in r.text
        conn = base.conectar(url, schema=schema)
        try:
            assert conn.execute("select count(*) from importacoes").fetchone()[0] == 3
            assert conn.execute("select count(*) from produtos_fiscal").fetchone()[0] == 6
        finally:
            conn.close()
    finally:
        conn = base.conectar(url)
        conn.execute(f'drop schema if exists "{schema}" cascade')
        conn.close()


def main():
    with TestClient(site.app) as c:
        test_sem_cabecalho_403(c)
        test_telas(c)
        test_converter_generico(c)
        test_converter_pedido(c)
        test_pdf_invalido(c)
        test_base_so_admin(c)
        print("Site OK")
        url = os.environ.get("TEST_DATABASE_URL")
        if not url:
            print("Pulado (sem TEST_DATABASE_URL): Atualizar base com banco")
            return
        test_base_com_banco(c, url)
        print("Base pelo site OK")


if __name__ == "__main__":
    main()
