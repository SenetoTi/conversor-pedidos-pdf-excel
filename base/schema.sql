-- Banco "conversor" (PostgreSQL). Criado na subida por base.criar_schema(); pode rodar várias vezes.
-- Cada importação troca só a sua própria tabela (produtos_fiscal, produtos_precos ou tipi), numa transação.

-- AtualiProdutos.csv: código interno, código de barras (só dígitos, sem zeros à esquerda), NCM (8 dígitos) e CEST.
create table if not exists produtos_fiscal (
    codigo text primary key,
    barras text not null default '',
    ncm    text not null default '',
    cest   text not null default ''
);
create index if not exists produtos_fiscal_barras on produtos_fiscal (barras) where barras <> '';

-- todos_os_produtos.xlsx: embalagem (coluna G), custo (J), compra (K) e venda (L). Vazio na planilha fica NULL.
create table if not exists produtos_precos (
    codigo    text primary key,
    barras    text not null default '',
    embalagem numeric(14, 4),
    custo     numeric(14, 4),
    compra    numeric(14, 4),
    venda     numeric(14, 4)
);
create index if not exists produtos_precos_barras on produtos_precos (barras) where barras <> '';

-- tipi.docx: alíquota de IPI por NCM de 8 dígitos. "NT" (não tributado) entra como 0.
create table if not exists tipi (
    ncm      text primary key,
    aliquota numeric(7, 2) not null
);

-- Histórico: quem importou o quê e quando; avisos é uma lista de textos.
create table if not exists importacoes (
    id      bigserial primary key,
    data    timestamptz not null default now(),
    email   text not null default '',
    tipo    text not null,
    arquivo text not null,
    linhas  integer not null,
    avisos  text[] not null default '{}'
);
