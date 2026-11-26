"""Busca dos dados de cada item do pedido na base.

Regra: primeiro pelo código de barras, depois pelo código. Cada tabela (fiscal e preços) é buscada separadamente.
`origem_fiscal` e `origem_precos` dizem como o item foi achado ('barras' ou 'codigo'); None = não achou.
"""
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .normalizar import normalizar_barras


@dataclass
class Produto:
    barras: str = ""   # como veio do pedido (normalizado)
    codigo: str = ""
    origem_fiscal: Optional[str] = None
    origem_precos: Optional[str] = None
    ncm: str = ""
    cest: str = ""
    aliquota_ipi: Optional[Decimal] = None  # None = NCM sem alíquota na TIPI (vira CONFERIR)
    embalagem: Optional[Decimal] = None
    custo: Optional[Decimal] = None
    compra: Optional[Decimal] = None
    venda: Optional[Decimal] = None

    @property
    def achou_fiscal(self):
        return self.origem_fiscal is not None

    @property
    def achou_precos(self):
        return self.origem_precos is not None


def aliquota_do_ncm(conn, ncm):
    """Alíquota de IPI do NCM. Primeiro o NCM inteiro (8 dígitos).

    Se ele não está na TIPI, tenta os 7, 6, 5 e 4 primeiros dígitos: só vale se todos os NCMs da TIPI
    que começam assim têm a mesma alíquota. Se forem diferentes, não chuta: devolve None.
    """
    digitos = re.sub(r"\D", "", str(ncm or ""))
    if len(digitos) < 4:
        return None
    if len(digitos) >= 8:
        linha = conn.execute("select aliquota from tipi where ncm = %s", (digitos[:8],)).fetchone()
        if linha:
            return linha[0]
    for tamanho in (7, 6, 5, 4):
        if len(digitos) < tamanho:
            continue
        linhas = conn.execute(
            "select distinct aliquota from tipi where ncm like %s limit 2", (digitos[:tamanho] + "%",)
        ).fetchall()
        if len(linhas) == 1:
            return linhas[0][0]
        if len(linhas) > 1:
            return None
    return None


def _indexar(linhas):
    """{barras: linha} e {codigo: linha}; se a base tiver barras repetido, vale o menor código."""
    por_barras, por_codigo = {}, {}
    for linha in sorted(linhas, key=lambda l: l[0]):
        por_codigo[linha[0]] = linha
        if linha[1]:
            por_barras.setdefault(linha[1], linha)
    return por_barras, por_codigo


def _achar(por_barras, por_codigo, barras, codigo):
    if barras and barras in por_barras:
        return por_barras[barras], "barras"
    if codigo and codigo in por_codigo:
        return por_codigo[codigo], "codigo"
    return None, None


def buscar_produtos(conn, itens):
    """`itens`: lista de (código de barras, código) do pedido. Devolve uma lista de Produto, na mesma ordem."""
    pedidos = [(normalizar_barras(b), str(c or "").strip()) for b, c in itens]
    lista_barras = sorted({b for b, _ in pedidos if b})
    lista_codigos = sorted({c for _, c in pedidos if c})

    fiscal = conn.execute(
        "select codigo, barras, ncm, cest from produtos_fiscal where barras = any(%s) or codigo = any(%s)",
        (lista_barras, lista_codigos),
    ).fetchall()
    precos = conn.execute(
        "select codigo, barras, embalagem, custo, compra, venda from produtos_precos "
        "where barras = any(%s) or codigo = any(%s)",
        (lista_barras, lista_codigos),
    ).fetchall()
    fiscal_barras, fiscal_codigo = _indexar(fiscal)
    precos_barras, precos_codigo = _indexar(precos)

    aliquotas = {}
    resultado = []
    for barras, codigo in pedidos:
        p = Produto(barras=barras, codigo=codigo)
        linha, p.origem_fiscal = _achar(fiscal_barras, fiscal_codigo, barras, codigo)
        if linha:
            p.ncm, p.cest = linha[2], linha[3]
            if p.ncm not in aliquotas:
                aliquotas[p.ncm] = aliquota_do_ncm(conn, p.ncm)
            p.aliquota_ipi = aliquotas[p.ncm]
        linha, p.origem_precos = _achar(precos_barras, precos_codigo, barras, codigo)
        if linha:
            p.embalagem, p.custo, p.compra, p.venda = linha[2:6]
        resultado.append(p)
    return resultado
