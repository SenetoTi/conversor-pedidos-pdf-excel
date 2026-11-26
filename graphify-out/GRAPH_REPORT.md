# Graph Report - conversor-pedidos-pdf-excel  (2026-11-26)

## Corpus Check
- 19 files · ~15,094 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: .bat 2, (none) 1, .spec 1)

## Summary
- 225 nodes · 450 edges · 9 communities (8 shown, 1 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5ea7c6d4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- generico.py
- importadores.py
- test_base.py
- index.py
- ConversorApp
- test_pedido_base.py
- busca.py
- test_conversor.py
- Conversor PDF → Excel

## God Nodes (most connected - your core abstractions)
1. `ConversorApp` - 14 edges
2. `converter_pdf_generico()` - 13 edges
3. `ler_fiscal()` - 11 edges
4. `normalizar_barras()` - 11 edges
5. `extrair_pdf_para_excel()` - 10 edges
6. `extrair_texto_pagina()` - 10 edges
7. `ler_precos()` - 10 edges
8. `arquivos()` - 10 edges
9. `com_base()` - 10 edges
10. `buscar_produtos()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `Base de produtos (PostgreSQL)` --references--> `buscar_produtos()`  [INFERRED]
  README.md → base/busca.py
- `_dados_da_base()` --calls--> `buscar_produtos()`  [INFERRED]
  nucleo/pedido.py → base/busca.py
- `task()` --calls--> `extrair_dados_cabecalho_rodape()`  [EXTRACTED]
  app_gui.py → nucleo/pedido.py
- `task()` --calls--> `extrair_produtos_inteligente()`  [EXTRACTED]
  app_gui.py → nucleo/pedido.py
- `task()` --calls--> `extrair_pdf_para_excel()`  [EXTRACTED]
  app_gui.py → nucleo/pedido.py

## Import Cycles
- None detected.

## Communities (9 total, 1 thin omitted)

### Community 0 - "generico.py"
Cohesion: 0.06
Nodes (15): coluna_da_caixa(), converter_pdf_generico(), detectar_colunas(), valor_celula(), agrupar_caixas_em_linhas(), caixas_rapidocr(), executar_ocr_com_reconstrucao(), _ocr_caixas() (+7 more)

### Community 1 - "importadores.py"
Cohesion: 0.15
Nodes (14): conectar(), criar_schema(), url_do_banco(), _aviso_contagem(), ErroImportacao, _gravar(), importar_fiscal(), importar_precos() (+6 more)

### Community 2 - "test_base.py"
Cohesion: 0.17
Nodes (14): normalizar_cest(), numero(), apagar_schema(), arquivos(), com_banco(), criar_csv(), criar_docx(), criar_xlsx() (+6 more)

### Community 4 - "ConversorApp"
Cohesion: 0.15
Nodes (6): ConversorApp, task(), sucesso(), task(), task(), main()

### Community 5 - "test_pedido_base.py"
Cohesion: 0.18
Nodes (12): _dados_da_base(), gerar_planilha(), _linha_da_base(), num(), ou_conferir(), com_base(), linhas_dos_produtos(), main() (+4 more)

### Community 6 - "busca.py"
Cohesion: 0.13
Nodes (8): _achar(), aliquota_do_ncm(), buscar_produtos(), _indexar(), Produto, normalizar_barras(), normalizar_ncm(), sem_acento()

### Community 7 - "test_conversor.py"
Cohesion: 0.10
Nodes (13): analisar_codigos_prefixo(), extrair_dados_cabecalho_rodape(), extrair_pdf_para_excel(), extrair_produtos_inteligente(), limpar_numero(), normalizar_linha_ocr(), produtos(), test_erros_ocr() (+5 more)

### Community 8 - "Conversor PDF → Excel"
Cohesion: 0.14
Nodes (13): Base de produtos (PostgreSQL), Como funciona, Como usar, Conferência automática (aba Pedido de Compra), Conversor PDF → Excel, Gerando o `.exe`, Limitações, Organização do código (+5 more)

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `buscar_produtos()` connect `busca.py` to `Conversor PDF → Excel`, `importadores.py`, `test_pedido_base.py`?**
  _High betweenness centrality (0.145) - this node is a cross-community bridge._
- **Should `generico.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06219426974143955 - nodes in this community are weakly interconnected._
- **Why does `Base de produtos (PostgreSQL)` connect `Conversor PDF → Excel` to `busca.py`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Should `importadores.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14623655913978495 - nodes in this community are weakly interconnected._
- **Should `ConversorApp` be split into smaller, more focused modules?**
  _Cohesion score 0.1471861471861472 - nodes in this community are weakly interconnected._
- **Should `busca.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12681159420289856 - nodes in this community are weakly interconnected._
- **Should `test_conversor.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0989247311827957 - nodes in this community are weakly interconnected._