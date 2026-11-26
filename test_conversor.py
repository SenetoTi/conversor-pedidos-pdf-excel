"""
Checagem rápida: python test_conversor.py

Os PDFs de exemplo têm dados de clientes e ficam só na sua máquina, na pasta exemplos/
(ignorada pelo git). Sem eles, os testes que dependem dos PDFs são pulados.
  exemplos/pedido_texto.pdf  -> pedido com camada de texto (5 filiais, 160 itens)
  exemplos/pedido_imagem.pdf -> pedido em imagem, lido por OCR (1 filial, 33 itens, soma = Total Geral)
"""
import os
import tempfile

import fitz
from openpyxl import load_workbook

from nucleo import generico, pedido

EXEMPLOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exemplos")
PEDIDO_TEXTO = os.path.join(EXEMPLOS, "pedido_texto.pdf")
PEDIDO_IMAGEM = os.path.join(EXEMPLOS, "pedido_imagem.pdf")


def produtos(caminho_xlsx):
    """Linhas de produto da planilha: as que têm código de barras de 13 dígitos na coluna C."""
    ws = load_workbook(caminho_xlsx).active
    return [r for r in ws.iter_rows(values_only=True) if r[2] and str(r[2]).isdigit() and len(str(r[2])) == 13]


def test_pedido_texto():
    saida = os.path.join(tempfile.gettempdir(), "test_pedido_texto.xlsx")
    filiais, avisos = pedido.extrair_pdf_para_excel(PEDIDO_TEXTO, saida)
    assert (filiais, avisos) == (5, 0), (filiais, avisos)  # avisos 0 = cada filial bate com o Total Geral
    prods = produtos(saida)
    assert len(prods) == 160, len(prods)
    assert all(r[4] == "CX" for r in prods), {r[4] for r in prods}
    assert all(r[5] < 10000 and abs(r[5] * r[6] - r[7]) <= 0.05 for r in prods)
    os.remove(saida)


def test_pedido_imagem():
    saida = os.path.join(tempfile.gettempdir(), "test_pedido_imagem.xlsx")
    filiais, avisos = pedido.extrair_pdf_para_excel(PEDIDO_IMAGEM, saida)
    assert (filiais, avisos) == (1, 0), (filiais, avisos)
    assert len(produtos(saida)) == 33
    os.remove(saida)


def test_generico_tabela():
    """Aba 'Qualquer PDF': cada campo da tabela vai para uma coluna e números viram números."""
    saida = os.path.join(tempfile.gettempdir(), "test_generico.xlsx")
    assert generico.converter_pdf_generico(PEDIDO_TEXTO, saida) == 10
    linhas = load_workbook(saida)["Pág 1"].iter_rows(values_only=True)
    item = [c for c in next(r for r in linhas if any(str(c).isdigit() and len(str(c)) == 13 for c in r)) if c is not None]
    assert item[3] == "CX  1" and all(isinstance(c, (int, float)) for c in item[4:]), item
    os.remove(saida)


def test_generico_texto_corrido():
    pdf = os.path.join(tempfile.gettempdir(), "test_texto.pdf")
    saida = os.path.join(tempfile.gettempdir(), "test_texto.xlsx")
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Relatorio mensal\nLinha de texto corrido sem tabela")
    doc.save(pdf)
    generico.converter_pdf_generico(pdf, saida)
    linhas = list(load_workbook(saida).active.iter_rows(values_only=True))
    assert linhas[:2] == [("Relatorio mensal",), ("Linha de texto corrido sem tabela",)], linhas
    os.remove(saida)
    os.remove(pdf)


def test_erros_ocr():
    """Erros de OCR vistos no pedido Mabel: espaço após o ponto de milhar e ':' colado nos códigos."""
    assert pedido.normalizar_linha_ocr("0,00 1. 800,00") == "0,00 1.800,00"
    assert pedido.normalizar_linha_ocr("544986:7908008824945") == "544986 7908008824945"
    linhas = ["ARUNA IMPORTADORA LTDA CNPJ:35.003.064/0002-01",
              "MABEL COMERCIO DE IMPORTADOS LTDA CNPJ: 00.527.682/0001-95",
              "Peso Total: 3.756,000 Total Geral: 43. 563,60"]
    info = pedido.extrair_dados_cabecalho_rodape(linhas)
    assert info["total_geral"] == "43.563,60", info["total_geral"]
    assert (info["razao_social"], info["fornecedor"]) == ("ARUNA IMPORTADORA LTDA", "MABEL COMERCIO DE IMPORTADOS LTDA"), info


def test_resumo_e_milhar_ocr():
    """Issue #12: 'Insc.Estad.:' colado no número não é produto, e '6,000,00' é 6.000,00 (dados inventados)."""
    assert pedido.normalizar_linha_ocr("25,0000 0,00 6,000,00") == "25,0000 0,00 6.000,00"
    assert pedido.normalizar_linha_ocr("240,000 25,00 6.000,00") == "240,000 25,00 6.000,00"
    assert pedido.normalizar_linha_ocr("1,234,567") == "1,234,567"
    linhas = ["EMPRESA TESTE LTDA CNPJ: 11.111.111/0001-11 Insc.Estad.:0012345678901 Pagina 2 de 2"]
    assert pedido.extrair_produtos_inteligente(linhas) == []
    item = ["ABC-1 100001 7890000000011 ITEM TESTE UN 1 240,000 25,00 0,00 25,0000 0,00 0,000 0,00 0,00 6,000,00"]
    (p,) = pedido.extrair_produtos_inteligente(item)
    assert (p["quant_num"], p["preco_num"], p["total_num"]) == (240.0, 25.0, 6000.0), p


if __name__ == "__main__":
    test_resumo_e_milhar_ocr()
    test_generico_texto_corrido()
    test_erros_ocr()
    for pdf, testes in [(PEDIDO_TEXTO, [test_pedido_texto, test_generico_tabela]), (PEDIDO_IMAGEM, [test_pedido_imagem])]:
        if not os.path.exists(pdf):
            print(f"Pulado (sem {os.path.relpath(pdf)}): {', '.join(t.__name__ for t in testes)}")
            continue
        for t in testes:
            t()
    print("OK")
