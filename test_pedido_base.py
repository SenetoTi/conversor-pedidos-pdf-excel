"""
Teste da planilha do pedido com os dados da base: python test_pedido_base.py

Pedido e base são inventados aqui mesmo (nenhum dado de cliente). Precisa de TEST_DATABASE_URL, por exemplo:
  TEST_DATABASE_URL=postgresql://postgres@localhost:5432/conversor_teste python test_pedido_base.py
Usa schema temporário, apagado no fim. Sem TEST_DATABASE_URL só roda o caso sem base.
"""
import os
import uuid

from openpyxl import load_workbook

import base
import test_base
from nucleo.pedido import COLUNAS_BASE, gerar_planilha


def produto(cod_erp, barras, quant, preco):
    return {"cod_forn": "F" + cod_erp, "codigo_erp": cod_erp, "cod_barras": barras, "descricao": "ITEM " + cod_erp,
            "um": "CX", "quant_num": quant, "preco_num": preco, "total_num": round(quant * preco, 2)}


def pedido():
    produtos = [
        produto("100001", "7890000000011", 2.0, 5.0),     # acha por barras
        produto("100002", "7899999999999", 1.0, 3.0),     # barras desconhecido: acha pelo código; compra zero
        produto("888888", "7898888888888", 1.0, 1.0),     # fora da base
        produto("100004", "", 4.0, 2.5),                  # NCM sem alíquota na TIPI
        produto("100002", "7890000000011", 1.0, 1.0),     # barras manda: vem do produto 100001
    ]
    total = sum(p["total_num"] for p in produtos)
    filial = {"filial_cod": "01", "razao_social": "LOJA TESTE", "ped_compra": "1", "data_pedido": "01/01/2026",
              "data_entrega": "05/01/2026", "cnpj": "00", "ie": "1", "endereco": "RUA X", "telefone": "1", "email": "a@b",
              "comprador": "ANA", "cond_pagamento": "30", "total_geral": f"{total:.2f}".replace(".", ","),
              "observacoes": "", "produtos": produtos}
    return {"01": filial}


def linhas_dos_produtos(caminho):
    ws = load_workbook(caminho)["Pedidos por Filial"]
    cabecalho = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Cód. Forn.")
    nomes = [c.value for c in ws[cabecalho] if c.value]
    linhas = []
    for r in range(cabecalho + 1, ws.max_row + 1):
        if not ws.cell(r, 1).value or not str(ws.cell(r, 1).value).startswith("F"):
            break
        linhas.append({n: ws.cell(r, i + 1) for i, n in enumerate(nomes)})
    return nomes, linhas


def vermelho(celula):
    return celula.font.color is not None and celula.font.color.rgb.endswith("9C0006")


def sem_base():
    saida = os.path.join(test_base.PASTA, "sem_base.xlsx")
    logs = []
    filiais, avisos = gerar_planilha(pedido(), saida, logs.append)
    nomes, linhas = linhas_dos_produtos(saida)
    assert nomes == ["Cód. Forn.", "Código ERP", "Código de Barras", "Descrição do Produto", "UM", "Quant.", "Preço Unit.", "Total"], nomes
    assert len(linhas) == 5 and filiais == 1 and avisos == 0, (filiais, avisos)
    assert any("Base de produtos não configurada" in m for m in logs), logs


def com_base(url):
    schema = "teste_" + uuid.uuid4().hex[:10]
    conn = base.conectar(url, schema=schema)
    try:
        base.criar_schema(conn)
        csv_, xlsx, docx_ = test_base.arquivos()
        base.importar_fiscal(conn, csv_)
        base.importar_precos(conn, xlsx)
        base.importar_tipi(conn, docx_)

        saida = os.path.join(test_base.PASTA, "com_base.xlsx")
        filiais, avisos = gerar_planilha(pedido(), saida, conexao=conn, fidelidade="  NF 123 fidelidade  ")
        nomes, linhas = linhas_dos_produtos(saida)
        assert nomes[:8] == ["Cód. Forn.", "Código ERP", "Código de Barras", "Descrição do Produto", "UM", "Quant.", "Preço Unit.", "Total"]
        assert nomes[8:] == COLUNAS_BASE + ["Conferência"], nomes
        assert len(linhas) == 5

        def valores(i):
            return [linhas[i][n].value for n in COLUNAS_BASE]

        # 1: achou por barras. venda, NCM, CEST, IPI, embalagem, compra, fidelidade (sem espaços nas pontas)
        assert valores(0) == [20, "70134100", "14.001.00", 10, 36, 8.22, "NF 123 fidelidade"], valores(0)
        assert not any(vermelho(linhas[0][n]) for n in COLUNAS_BASE)
        # 2: barras desconhecido, achou pelo código; compra zero em vermelho, sem ser CONFERIR
        assert valores(1)[:2] == [0, "95030099"] and valores(1)[5] == 0, valores(1)
        assert vermelho(linhas[1]["Valor Tabela comprado"]) and not vermelho(linhas[1]["NCM"])
        # 3: fora da base: tudo CONFERIR em vermelho, menos a Fidelidade
        assert valores(2)[:6] == ["CONFERIR"] * 6 and valores(2)[6] == "NF 123 fidelidade", valores(2)
        assert all(vermelho(linhas[2][n]) for n in COLUNAS_BASE[:6])
        # 4: achou, mas o NCM não tem alíquota: só o IPI vira CONFERIR
        assert valores(3)[3] == "CONFERIR" and valores(3)[1] == "12345678" and valores(3)[5] == 3, valores(3)
        assert vermelho(linhas[3]["IPI (%)"]) and not vermelho(linhas[3]["NCM"])
        # 5: barras antes do código: o barras é do produto 100001 mesmo com código 100002
        assert valores(4)[:2] == [20, "70134100"], valores(4)
        # um aviso por linha com problema: linhas 2, 3 e 4
        assert avisos == 3, avisos

        # Fidelidade vazia sai vazia
        saida2 = os.path.join(test_base.PASTA, "fidelidade_vazia.xlsx")
        gerar_planilha(pedido(), saida2, conexao=conn)
        _, linhas2 = linhas_dos_produtos(saida2)
        assert all(l["Fidelidade da NF"].value in (None, "") for l in linhas2)
    finally:
        conn.close()  # antes de apagar o schema, senão o drop espera esta conexão
        test_base.apagar_schema(url, schema)


def main():
    sem_base()
    print("Sem base OK")
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        print("Pulado (sem TEST_DATABASE_URL): teste com base")
        return
    com_base(url)
    print("Com base OK")


if __name__ == "__main__":
    main()
