"""
Testes da base de produtos: python test_base.py

Os arquivos de exemplo são criados aqui mesmo, com dados inventados (nenhum dado de cliente).
As leituras dos arquivos rodam sempre. Os testes com banco só rodam com TEST_DATABASE_URL, por exemplo:
  TEST_DATABASE_URL=postgresql://postgres@localhost:5432/conversor_teste python test_base.py
Eles usam um schema temporário, que é apagado no fim.
"""
import os
import tempfile
import uuid
from decimal import Decimal

import psycopg
from openpyxl import Workbook
from psycopg import sql

import base
from base import ErroImportacao, normalizar_barras
from base.normalizar import normalizar_cest, normalizar_ncm, numero

PASTA = tempfile.mkdtemp(prefix="test_base_")


# ------------------------------------------------------------------ arquivos sintéticos

def criar_csv(caminho, extra_linhas=()):
    """Latin-1, ';', bloco PIS/COFINS em cima, cabeçalho 'cod_interno', barras entre apóstrofos com 14 dígitos."""
    topo = [
        "PISCOFINS;Descrição;Valor Alíquota(PIS);Valor Alíquota (COFINS)",
        "1;ISENTO;0;0",
        "2;TRIBUTACAO NORMAL REVENDA;0,65;3",
    ]
    cab = "cod_interno;codbarra;desc;%icms PDV;NCM;CEST;%IPI"
    dados = [
        "100001;'07890000000011'; PRODUTO TESTE A;18;70134100;14.001.00;0;",
        "100002;'07890000000028'; PRODUTO TESTE B;18;95030099;;0;",
        "100003;'07890000000035'; PRODUTO TESTE C;18;09021000.1;1400100;0;",   # NCM com sufixo, CEST sem pontos
        "100004;'07890000000042'; PRODUTO AÇÚCAR D;18;12345678;21.040.00;0;",   # NCM fora da TIPI; acento (Latin-1)
        "100001;'07890000000059'; PRODUTO REPETIDO;18;70134100;;0;",             # código repetido
        "100005;'';  PRODUTO SEM BARRAS;18;95030022;;0;",
        "100006;'07890000000066'; PRODUTO NCM RUIM;18;ABC;;0;",
        "",
        *extra_linhas,
    ]
    texto = "\r\n".join(topo + [cab] + dados) + "\r\n"
    with open(caminho, "wb") as f:
        f.write(texto.encode("latin-1"))


def criar_xlsx(caminho):
    """Cabeçalho desalinhado, como o real: títulos em A..I, dados com G=embalagem, J=custo, K=compra, L=venda."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Código", "Cód. Barra", "Descrição", "UM", "Emb", None, "Custo", "Compra", "Venda"])
    ws.append(["100001", "7890000000011", " PRODUTO TESTE A", None, "CX", None, 36, None, None, 4.21, 8.22, 20])
    ws.append(["100002", "7890000000028", " PRODUTO TESTE B", None, "CX", None, 12, None, None, 0, 0, 0])
    ws.append(["100003", "7890000000035", " PRODUTO TESTE C", None, "PC", None, 6, None, None, 1.5, 2.5, 9.9])
    ws.append(["100004", 7890000000042, " PRODUTO AÇÚCAR D", None, "CX", None, 24, None, None, 2, 3, 5])
    ws.append(["100002", "7890000000099", " REPETIDO", None, "CX", None, 1, None, None, 1, 1, 1])
    ws.append(["200001", "7890000000103", " SO NA PLANILHA", None, "CX", None, 10, None, None, 3, 4, 8])
    ws.append([None, None, None])
    wb.save(caminho)


def criar_docx(caminho):
    import docx

    d = docx.Document()
    unidades = d.add_table(rows=2, cols=2)
    unidades.rows[0].cells[0].text, unidades.rows[0].cells[1].text = "A", "ampere(s)"
    unidades.rows[1].cells[0].text, unidades.rows[1].cells[1].text = "Bq", "becquerel"
    linhas = [
        ("NCM", "DESCRIÇÃO", "ALÍQUOTA (%)"),
        ("70.13", "Objetos de vidro.", ""),
        ("7013.41", "-\tDe vitroceramica", ""),
        ("7013.41.00", "Copos", "10"),
        ("9503.00", "Brinquedos", ""),
        ("9503.00.22", "Bonecas", "NT"),
        ("9503.00.99", "Outros", "0"),
        ("0902.10.00", "Cha verde", "3,25"),
        ("8528.72.00", "Televisores", "15"),
        ("8528.72.10", "Televisores X", "15"),
        ("8528.72.90", "Televisores Y", "20"),
        ("8528.72.90 Ex 01", "Excecao", "5"),
        ("", "", ""),
    ]
    t = d.add_table(rows=len(linhas), cols=3)
    for i, (a, b, c) in enumerate(linhas):
        t.rows[i].cells[0].text, t.rows[i].cells[1].text, t.rows[i].cells[2].text = a, b, c
    # segunda tabela com o cabeçalho repetido e NCM duplicado
    t2 = d.add_table(rows=3, cols=3)
    for i, (a, b, c) in enumerate([("NCM", "DESCRIÇÃO", "ALÍQUOTA (%)"), ("7013.41.00", "Copos de novo", "99"), ("1101.00.10", "Trigo", "NT")]):
        t2.rows[i].cells[0].text, t2.rows[i].cells[1].text, t2.rows[i].cells[2].text = a, b, c
    d.save(caminho)


def arquivos():
    csv_, xlsx, docx_ = (os.path.join(PASTA, n) for n in ("AtualiProdutos.csv", "todos os produtos.xlsx", "tipi.docx"))
    criar_csv(csv_)
    criar_xlsx(xlsx)
    criar_docx(docx_)
    return csv_, xlsx, docx_


# ------------------------------------------------------------------ normalização e leitura (sem banco)

def test_normalizar():
    assert normalizar_barras("'07890000000011'") == "7890000000011"
    assert normalizar_barras(7890000000011) == "7890000000011"
    assert normalizar_barras(7.890000000011e12) == "7890000000011"
    assert normalizar_barras(None) == "" and normalizar_barras("'0'") == ""
    assert normalizar_ncm("70134100") == ("70134100", None)
    assert normalizar_ncm("9503.00.99") == ("95030099", None)
    assert normalizar_ncm("09021000.1") == ("09021000", "sufixo")
    assert normalizar_ncm("ABC") == ("", "invalido") and normalizar_ncm("") == ("", None)
    assert normalizar_cest("14.001.00") == ("14.001.00", None) and normalizar_cest("1400100") == ("14.001.00", None)
    assert normalizar_cest("x") == ("", "invalido")
    assert numero(None) is None and numero("") is None
    assert numero(4.21) == Decimal("4.21") and numero("1.234,50") == Decimal("1234.50") and numero("3,25") == Decimal("3.25")


def test_ler_fiscal():
    csv_, _, _ = arquivos()
    r = base.ler_fiscal(csv_)
    por_codigo = {l[0]: l for l in r.linhas}
    assert len(r.linhas) == 6, r.linhas  # o código repetido (100001) fica uma vez só
    assert por_codigo["100001"] == ("100001", "7890000000011", "70134100", "14.001.00")
    assert por_codigo["100003"] == ("100003", "7890000000035", "09021000", "14.001.00")  # sufixo cortado, CEST formatado
    assert por_codigo["100005"][1] == "" and por_codigo["100006"][2] == ""
    texto = " | ".join(r.avisos)
    for trecho in ("repetidos", "sem código de barras", "sufixo", "NCMs inválidos"):
        assert trecho in texto, (trecho, r.avisos)


def test_ler_precos():
    _, xlsx, _ = arquivos()
    r = base.ler_precos(xlsx)
    por_codigo = {l[0]: l for l in r.linhas}
    assert len(r.linhas) == 5, r.linhas  # 100002 repetido e linha vazia ficam de fora
    # G = embalagem, J = custo, K = compra, L = venda
    assert por_codigo["100001"] == ("100001", "7890000000011", Decimal("36"), Decimal("4.21"), Decimal("8.22"), Decimal("20"))
    assert por_codigo["100004"][1] == "7890000000042"  # barras que veio como número
    assert any("compra igual a zero" in a for a in r.avisos), r.avisos


def test_ler_tipi():
    _, _, docx_ = arquivos()
    r = base.ler_tipi(docx_)
    d = dict(r.linhas)
    assert d["70134100"] == Decimal("10") and d["95030022"] == Decimal("0") and d["09021000"] == Decimal("3.25")  # NT = 0
    assert "70130000" not in d and len(d) == 8, d  # títulos de grupo, exceção e duplicado não entram
    assert any("exceção" in a for a in r.avisos) and any("repetidos" in a for a in r.avisos), r.avisos


def test_arquivo_errado_recusado():
    csv_, xlsx, docx_ = arquivos()
    for func, errado in [(base.ler_fiscal, xlsx), (base.ler_fiscal, docx_), (base.ler_precos, csv_), (base.ler_precos, docx_),
                         (base.ler_tipi, csv_), (base.ler_tipi, xlsx)]:
        try:
            func(errado)
        except ErroImportacao:
            continue
        raise AssertionError(f"{func.__name__} aceitou {os.path.basename(errado)}")
    # planilha com a estrutura certa de títulos, mas sem números em G, J, K e L
    vazia = os.path.join(PASTA, "sem_numeros.xlsx")
    wb = Workbook()
    wb.active.append(["Código", "Cód. Barra", "Descrição"])
    wb.active.append(["1", "7890000000011", "X"])
    wb.save(vazia)
    try:
        base.ler_precos(vazia)
    except ErroImportacao as e:
        assert "G, J, K e L" in str(e)
    else:
        raise AssertionError("aceitou planilha sem números")


# ------------------------------------------------------------------ com banco

def com_banco(url):
    schema = "teste_" + uuid.uuid4().hex[:10]
    conn = base.conectar(url, schema=schema)
    try:
        base.criar_schema(conn)
        base.criar_schema(conn)  # pode rodar duas vezes
        csv_, xlsx, docx_ = arquivos()

        def total(tabela):
            return conn.execute(f"select count(*) from {tabela}").fetchone()[0]

        assert base.importar_fiscal(conn, csv_, "ana@empresa")["linhas"] == 6
        assert base.importar_precos(conn, xlsx, "ana@empresa")["linhas"] == 5
        assert base.importar_tipi(conn, docx_, "ana@empresa")["linhas"] == 8
        hist = conn.execute("select tipo, email, arquivo, linhas from importacoes order by id").fetchall()
        assert hist == [("fiscal", "ana@empresa", "AtualiProdutos.csv", 6), ("precos", "ana@empresa", "todos os produtos.xlsx", 5),
                        ("tipi", "ana@empresa", "tipi.docx", 8)], hist

        # busca: barras com zero à esquerda, vindo do pedido
        p = base.buscar_produtos(conn, [("07890000000011", "999999")])[0]
        assert (p.origem_fiscal, p.origem_precos) == ("barras", "barras"), p
        assert (p.ncm, p.cest, p.aliquota_ipi) == ("70134100", "14.001.00", Decimal("10.00")), p
        assert (p.embalagem, p.custo, p.compra, p.venda) == (Decimal("36"), Decimal("4.21"), Decimal("8.22"), Decimal("20")), p

        # barras primeiro, código depois: se o barras acha um produto, o código de outro é ignorado
        p = base.buscar_produtos(conn, [("7890000000011", "100002")])[0]
        assert p.codigo == "100002" and p.ncm == "70134100" and p.compra == Decimal("8.22"), p  # veio do produto 100001
        # sem barras no pedido (ou barras desconhecido): acha pelo código
        p = base.buscar_produtos(conn, [("", "100002")])[0]
        assert (p.origem_fiscal, p.origem_precos, p.ncm) == ("codigo", "codigo", "95030099"), p
        p = base.buscar_produtos(conn, [("7899999999999", "100002")])[0]
        assert p.origem_fiscal == "codigo" and p.ncm == "95030099", p
        # fora da base
        p = base.buscar_produtos(conn, [("7899999999999", "888888")])[0]
        assert not p.achou_fiscal and not p.achou_precos and p.aliquota_ipi is None, p
        # só em uma das tabelas
        p = base.buscar_produtos(conn, [("7890000000103", "")])[0]
        assert not p.achou_fiscal and p.achou_precos and p.venda == Decimal("8"), p
        # ordem e quantidade preservadas
        achados = base.buscar_produtos(conn, [("7890000000042", ""), ("", "100001"), ("1", "2")])
        assert [x.achou_fiscal for x in achados] == [True, True, False]

        # alíquota: NCM inteiro; NT = 0; NCM fora da TIPI sem alíquota; prefixo só se todos concordam
        assert base.aliquota_do_ncm(conn, "95030022") == Decimal("0")
        assert base.aliquota_do_ncm(conn, "12345678") is None  # produto 100004: NCM fora da TIPI
        assert base.aliquota_do_ncm(conn, "95030011") == Decimal("0")    # fora da TIPI; 9503.00.xx são todos 0
        assert base.aliquota_do_ncm(conn, "85287299") == Decimal("20")   # fora da TIPI; 7 dígitos (8528729) só tem 20
        assert base.aliquota_do_ncm(conn, "85287199") is None            # 8528.7 mistura 15 e 20: não chuta
        assert base.aliquota_do_ncm(conn, "99999999") is None and base.aliquota_do_ncm(conn, "12") is None

        # arquivo errado é recusado e a base fica como estava
        antes = (total("produtos_fiscal"), total("produtos_precos"), total("tipi"), total("importacoes"))
        for func, errado in [(base.importar_fiscal, xlsx), (base.importar_precos, csv_), (base.importar_tipi, xlsx)]:
            try:
                func(conn, errado, "ana@empresa")
            except ErroImportacao:
                pass
            else:
                raise AssertionError("aceitou arquivo errado")
        assert (total("produtos_fiscal"), total("produtos_precos"), total("tipi"), total("importacoes")) == antes

        # falha no meio da gravação desfaz tudo (a tabela antiga não é apagada)
        leitura = base.importadores.Leitura(linhas=[("500001", "789", "70134100", ""), (None, "789", "70134100", "")])
        try:
            base.importadores._gravar(conn, "produtos_fiscal", ("codigo", "barras", "ncm", "cest"), leitura, "fiscal", "x.csv", "")
        except psycopg.Error:
            pass
        else:
            raise AssertionError("devia ter falhado")
        assert (total("produtos_fiscal"), total("produtos_precos"), total("tipi"), total("importacoes")) == antes

        # nova importação troca só a sua tabela
        menor = os.path.join(PASTA, "menor.csv")
        criar_csv(menor)
        with open(menor, "rb") as f:
            linhas = f.read().decode("latin-1").splitlines()
        with open(menor, "wb") as f:
            f.write("\r\n".join(linhas[:6]).encode("latin-1"))  # bloco PIS/COFINS (3) + cabeçalho + 2 produtos
        assert base.importar_fiscal(conn, menor, "bia@empresa")["linhas"] == 2
        assert (total("produtos_fiscal"), total("produtos_precos"), total("tipi")) == (2, 5, 8)
        assert conn.execute("select email from importacoes order by id desc limit 1").fetchone()[0] == "bia@empresa"
    finally:
        conn.close()
        apagar_schema(url, schema)


def apagar_schema(url, schema):
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("drop schema if exists {} cascade").format(sql.Identifier(schema)))


def main():
    test_normalizar()
    test_ler_fiscal()
    test_ler_precos()
    test_ler_tipi()
    test_arquivo_errado_recusado()
    print("Leituras OK")
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        print("Pulado (sem TEST_DATABASE_URL): testes com banco")
        return
    com_banco(url)
    print("Banco OK")


if __name__ == "__main__":
    main()
