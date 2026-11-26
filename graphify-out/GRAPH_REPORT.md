# Graph Report - conversor-pedidos-pdf-excel  (2026-11-26)

## Corpus Check
- 18 files · ~13,776 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: .bat 2, (none) 1, .spec 1)

## Summary
- 204 nodes · 403 edges · 9 communities (8 shown, 1 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `08dc74b9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- generico.py
- importadores.py
- test_base.py
- motores.py
- ConversorApp
- pedido.py
- busca.py
- test_conversor.py
- Conversor PDF → Excel

## God Nodes (most connected - your core abstractions)
1. `ConversorApp` - 14 edges
2. `converter_pdf_generico()` - 13 edges
3. `ler_fiscal()` - 11 edges
4. `normalizar_barras()` - 11 edges
5. `ler_precos()` - 10 edges
6. `extrair_texto_pagina()` - 10 edges
7. `extrair_pdf_para_excel()` - 10 edges
8. `buscar_produtos()` - 9 edges
9. `ErroImportacao` - 9 edges
10. `arquivos()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `Base de produtos (PostgreSQL)` --references--> `buscar_produtos()`  [INFERRED]
  README.md → base/busca.py
- `task()` --calls--> `converter_pdf_generico()`  [EXTRACTED]
  app_gui.py → nucleo/generico.py
- `task()` --calls--> `extrair_texto_pagina()`  [EXTRACTED]
  app_gui.py → nucleo/pdf_texto.py
- `task()` --calls--> `extrair_pdf_para_excel()`  [EXTRACTED]
  app_gui.py → nucleo/pedido.py
- `test_normalizar()` --calls--> `normalizar_barras()`  [EXTRACTED]
  test_base.py → base/normalizar.py

## Import Cycles
- None detected.

## Communities (9 total, 1 thin omitted)

### Community 0 - "generico.py"
Cohesion: 0.09
Nodes (15): coluna_da_caixa(), converter_pdf_generico(), detectar_colunas(), valor_celula(), agrupar_caixas_em_linhas(), caixas_rapidocr(), executar_ocr_com_reconstrucao(), _ocr_caixas() (+7 more)

### Community 1 - "importadores.py"
Cohesion: 0.14
Nodes (15): conectar(), criar_schema(), url_do_banco(), _aviso_contagem(), ErroImportacao, _gravar(), importar_fiscal(), importar_precos() (+7 more)

### Community 2 - "test_base.py"
Cohesion: 0.12
Nodes (16): normalizar_cest(), normalizar_ncm(), numero(), sem_acento(), apagar_schema(), arquivos(), com_banco(), criar_csv() (+8 more)

### Community 4 - "ConversorApp"
Cohesion: 0.16
Nodes (5): ConversorApp, task(), sucesso(), task(), main()

### Community 5 - "pedido.py"
Cohesion: 0.15
Nodes (8): task(), analisar_codigos_prefixo(), extrair_dados_cabecalho_rodape(), extrair_pdf_para_excel(), extrair_produtos_inteligente(), limpar_numero(), normalizar_linha_ocr(), test_erros_ocr()

### Community 6 - "busca.py"
Cohesion: 0.19
Nodes (5): _achar(), aliquota_do_ncm(), buscar_produtos(), _indexar(), Produto

### Community 7 - "test_conversor.py"
Cohesion: 0.26
Nodes (5): produtos(), test_generico_tabela(), test_generico_texto_corrido(), test_pedido_imagem(), test_pedido_texto()

### Community 8 - "Conversor PDF → Excel"
Cohesion: 0.15
Nodes (12): Base de produtos (PostgreSQL), Como funciona, Como usar, Conferência automática (aba Pedido de Compra), Conversor PDF → Excel, Gerando o `.exe`, Limitações, Organização do código (+4 more)

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `buscar_produtos()` connect `busca.py` to `Conversor PDF → Excel`, `importadores.py`?**
  _High betweenness centrality (0.134) - this node is a cross-community bridge._
- **Should `generico.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08961593172119488 - nodes in this community are weakly interconnected._
- **Why does `ConversorApp` connect `ConversorApp` to `motores.py`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Should `importadores.py` be split into smaller, more focused modules?**
  _Cohesion score 0.13825757575757575 - nodes in this community are weakly interconnected._
- **Why does `Base de produtos (PostgreSQL)` connect `Conversor PDF → Excel` to `busca.py`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Should `test_base.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12473118279569892 - nodes in this community are weakly interconnected._
- **Should `motores.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12121212121212122 - nodes in this community are weakly interconnected._