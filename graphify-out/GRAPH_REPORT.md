# Graph Report - conversor-pedidos-pdf-excel  (2026-11-26)

## Corpus Check
- 23 files · ~19,016 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: .bat 7, (none) 1, .spec 1)

## Summary
- 301 nodes · 601 edges · 10 communities (9 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 21 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f8461c90`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- generico.py
- importadores.py
- Instalação do site do Conversor (Windows)
- motores.py
- ConversorApp
- pedido.py
- app.py
- test_web.py
- Conversor PDF → Excel
- busca.py

## God Nodes (most connected - your core abstractions)
1. `converter_pdf_generico()` - 15 edges
2. `Instalação do site do Conversor (Windows)` - 14 edges
3. `ConversorApp` - 14 edges
4. `extrair_pdf_para_excel()` - 12 edges
5. `ler_fiscal()` - 11 edges
6. `normalizar_barras()` - 11 edges
7. `arquivos()` - 11 edges
8. `extrair_texto_pagina()` - 10 edges
9. `buscar_produtos()` - 10 edges
10. `ler_precos()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `Base de produtos (PostgreSQL)` --references--> `buscar_produtos()`  [INFERRED]
  README.md → base/busca.py
- `_dados_da_base()` --calls--> `buscar_produtos()`  [INFERRED]
  nucleo/pedido.py → base/busca.py
- `rodar_trabalho()` --calls--> `converter_pdf_generico()`  [EXTRACTED]
  web/app.py → nucleo/generico.py
- `rodar_trabalho()` --calls--> `extrair_pdf_para_excel()`  [EXTRACTED]
  web/app.py → nucleo/pedido.py
- `task()` --calls--> `converter_pdf_generico()`  [EXTRACTED]
  app_gui.py → nucleo/generico.py

## Import Cycles
- None detected.

## Communities (10 total, 1 thin omitted)

### Community 0 - "generico.py"
Cohesion: 0.09
Nodes (15): coluna_da_caixa(), converter_pdf_generico(), detectar_colunas(), valor_celula(), agrupar_caixas_em_linhas(), caixas_rapidocr(), executar_ocr_com_reconstrucao(), _ocr_caixas() (+7 more)

### Community 1 - "importadores.py"
Cohesion: 0.07
Nodes (31): conectar(), criar_schema(), url_do_banco(), _aviso_contagem(), ErroImportacao, _gravar(), importar_fiscal(), importar_precos() (+23 more)

### Community 2 - "Instalação do site do Conversor (Windows)"
Cohesion: 0.13
Nodes (14): 10. Testar de ponta a ponta, 11. Atualizar e reiniciar, 12. Desligar o .exe, 1. Programas, 2. Banco, 3. Código, 4. Variáveis de ambiente (nunca no repositório), 5. Testar o site (+6 more)

### Community 4 - "ConversorApp"
Cohesion: 0.15
Nodes (6): ConversorApp, task(), sucesso(), task(), task(), main()

### Community 5 - "pedido.py"
Cohesion: 0.09
Nodes (20): analisar_codigos_prefixo(), _dados_da_base(), extrair_dados_cabecalho_rodape(), extrair_pdf_para_excel(), extrair_produtos_inteligente(), gerar_planilha(), limpar_numero(), _linha_da_base() (+12 more)

### Community 6 - "app.py"
Cohesion: 0.10
Nodes (24): abrir_banco(), admins(), atualizar_base(), baixar(), ciclo(), converter(), dados_da_base(), enviar_base() (+16 more)

### Community 7 - "test_web.py"
Cohesion: 0.13
Nodes (17): produtos(), test_generico_tabela(), test_generico_texto_corrido(), test_pedido_imagem(), test_pedido_texto(), enviar_pdf(), esperar(), main() (+9 more)

### Community 8 - "Conversor PDF → Excel"
Cohesion: 0.13
Nodes (14): Base de produtos (PostgreSQL), Como funciona, Como usar, Conferência automática (aba Pedido de Compra), Conversor PDF → Excel, Gerando o `.exe`, Limitações, Organização do código (+6 more)

### Community 9 - "busca.py"
Cohesion: 0.19
Nodes (5): _achar(), aliquota_do_ncm(), buscar_produtos(), _indexar(), Produto

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `buscar_produtos()` connect `busca.py` to `Conversor PDF → Excel`, `importadores.py`, `pedido.py`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Should `generico.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08961593172119488 - nodes in this community are weakly interconnected._
- **Why does `Base de produtos (PostgreSQL)` connect `Conversor PDF → Excel` to `busca.py`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Should `importadores.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07373271889400922 - nodes in this community are weakly interconnected._
- **Should `Instalação do site do Conversor (Windows)` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Should `motores.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12121212121212122 - nodes in this community are weakly interconnected._
- **Should `ConversorApp` be split into smaller, more focused modules?**
  _Cohesion score 0.1471861471861472 - nodes in this community are weakly interconnected._