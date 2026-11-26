"""Linha de comando da base. Precisa de CONVERSOR_DATABASE_URL (não é a DATABASE_URL do Conciliador).

    python -m base validar fiscal|precos|tipi ARQUIVO     (só lê e mostra os avisos; não usa o banco)
    python -m base criar-schema
    python -m base fiscal  AtualiProdutos.csv        [--email voce@empresa]
    python -m base precos  "todos os produtos.xlsx"  [--email voce@empresa]
    python -m base tipi    tipi.docx                 [--email voce@empresa]
    python -m base resumo
"""
import argparse
import sys

from . import (
    ErroImportacao, conectar, criar_schema, importar_fiscal, importar_precos, importar_tipi, ler_fiscal, ler_precos, ler_tipi,
)

IMPORTADORES = {"fiscal": importar_fiscal, "precos": importar_precos, "tipi": importar_tipi}
LEITORES = {"fiscal": ler_fiscal, "precos": ler_precos, "tipi": ler_tipi}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m base", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("criar-schema")
    sub.add_parser("resumo")
    v = sub.add_parser("validar")
    v.add_argument("tipo", choices=sorted(LEITORES))
    v.add_argument("arquivo")
    for nome in IMPORTADORES:
        s = sub.add_parser(nome)
        s.add_argument("arquivo")
        s.add_argument("--email", default="")
    args = ap.parse_args(argv)

    if args.comando == "validar":
        try:
            leitura = LEITORES[args.tipo](args.arquivo)
        except ErroImportacao as erro:
            print(f"RECUSADO: {erro}")
            return 1
        print(f"{args.tipo}: {len(leitura.linhas)} linhas lidas (nada foi gravado).")
        for aviso in leitura.avisos:
            print("  aviso:", aviso)
        return 0

    conn = conectar()
    try:
        criar_schema(conn)
        if args.comando == "criar-schema":
            print("Tabelas prontas.")
        elif args.comando == "resumo":
            for tabela in ("produtos_fiscal", "produtos_precos", "tipi"):
                print(f"{tabela}: {conn.execute(f'select count(*) from {tabela}').fetchone()[0]} linhas")
            for linha in conn.execute("select data, email, tipo, arquivo, linhas from importacoes order by id desc limit 5"):
                print("importação:", *linha)
        else:
            try:
                r = IMPORTADORES[args.comando](conn, args.arquivo, args.email)
            except ErroImportacao as erro:
                print(f"RECUSADO (a base não foi alterada): {erro}")
                return 1
            print(f"{r['tipo']}: {r['linhas']} linhas importadas.")
            for aviso in r["avisos"]:
                print("  aviso:", aviso)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
