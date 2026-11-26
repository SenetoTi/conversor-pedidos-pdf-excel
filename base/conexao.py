"""Conexão com o banco "conversor" e criação das tabelas."""
import os
from pathlib import Path

import psycopg
from psycopg import sql

SCHEMA_SQL = Path(__file__).with_name("schema.sql")


def url_do_banco():
    url = os.environ.get("CONVERSOR_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "Defina a variável de ambiente CONVERSOR_DATABASE_URL, por exemplo "
            "postgresql://USUARIO:SENHA@localhost:5432/conversor"
        )
    return url


def conectar(url=None, schema=None):
    """Abre a conexão. `schema` serve só para testes: usa um schema separado em vez do público."""
    conn = psycopg.connect(url or url_do_banco(), client_encoding="UTF8")  # fixo: o schema.sql tem acentos
    if schema:
        nome = sql.Identifier(schema)
        conn.execute(sql.SQL("create schema if not exists {}").format(nome))
        conn.execute(sql.SQL("set search_path to {}").format(nome))
        conn.commit()
    return conn


def criar_schema(conn):
    """Cria as tabelas que ainda não existem (nada é apagado)."""
    conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    conn.commit()
