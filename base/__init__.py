"""Base de produtos do Conversor (PostgreSQL): NCM, CEST, alíquota de IPI, embalagem, custo, compra e venda.

Uso rápido:
    from base import conectar, criar_schema, importar_fiscal, importar_precos, importar_tipi, buscar_produtos
"""
from .busca import Produto, aliquota_do_ncm, buscar_produtos
from .conexao import conectar, criar_schema
from .importadores import (
    ErroImportacao,
    importar_fiscal,
    importar_precos,
    importar_tipi,
    ler_fiscal,
    ler_precos,
    ler_tipi,
)
from .normalizar import normalizar_barras

__all__ = [
    "ErroImportacao",
    "Produto",
    "aliquota_do_ncm",
    "buscar_produtos",
    "conectar",
    "criar_schema",
    "importar_fiscal",
    "importar_precos",
    "importar_tipi",
    "ler_fiscal",
    "ler_precos",
    "ler_tipi",
    "normalizar_barras",
]
