# Conversor PDF → Excel

Aplicativo para Windows que transforma PDFs em planilhas Excel (`.xlsx`). Funciona com PDFs que têm texto e também com PDFs que são só imagem (escaneados ou exportados como foto por sistemas na nuvem), usando OCR.

O app tem duas abas:

| Aba | Para que serve |
| --- | --- |
| **Qualquer PDF** | Converte qualquer PDF mantendo a disposição da página: cada linha do PDF vira uma linha da planilha e as colunas são detectadas pelos espaços em branco. Ideal para relatórios, extratos e tabelas. |
| **Pedido de Compra** | Lê pedidos de compra emitidos por ERP e monta uma planilha organizada por filial, com cabeçalho do pedido e tabela de produtos (código, código de barras, descrição, UM, quantidade, preço e total). Confere os valores e marca em vermelho o que precisa de revisão. |

## Como usar

1. Baixe o `Conversor_de_Pedidos.exe` na página de **Releases** deste repositório (não precisa instalar Python).
2. Abra o programa, escolha a aba, selecione o PDF e clique em converter.
3. A planilha é salva ao lado do PDF (ou no local que você escolher).

> Como o `.exe` não tem assinatura digital, o Windows pode mostrar "O Windows protegeu o computador". Clique em **Mais informações** → **Executar assim mesmo**.

PDFs em imagem passam pelo OCR e demoram mais (cerca de 15 a 25 segundos por página).

### Sem abrir a janela

O mesmo `.exe` converte pela linha de comando, gravando um `.log` ao lado da planilha:

```powershell
Conversor_de_Pedidos.exe --qualquer arquivo.pdf [saida.xlsx]   # aba Qualquer PDF
Conversor_de_Pedidos.exe pedido.pdf [saida.xlsx]               # aba Pedido de Compra
```

## Conferência automática (aba Pedido de Compra)

- Em cada linha, **quantidade × preço** tem que bater com o total lido do PDF.
- Em cada filial, a **soma das linhas** tem que bater com o **Total Geral** impresso no pedido.
- O que não bate fica em vermelho com a indicação `CONFERIR`, e a janela final informa quantos pontos revisar.

## Rodando pelo código

Requer Python 3.10 ou mais recente.

```powershell
pip install pymupdf pdfplumber pypdf openpyxl pillow numpy rapidocr-onnxruntime
python app_gui.py
```

### Organização do código

| Arquivo | Para que serve |
| --- | --- |
| `app_gui.py` | Só a janela (Tkinter) e a linha de comando. Usa o motor da pasta `nucleo/`. |
| `nucleo/motores.py` | Bibliotecas opcionais (PyMuPDF, pdfplumber, pypdf, PIL, RapidOCR, Tesseract) e se cada uma está disponível. |
| `nucleo/ocr.py` | Tratamento de imagem e OCR com reconstrução das linhas pela posição das caixas. |
| `nucleo/pdf_texto.py` | Leitura de PDF de texto (PyMuPDF por trechos; pdfplumber e pypdf de reserva). |
| `nucleo/pedido.py` | Pedido de compra: cabeçalho, produtos e a planilha por filial. |
| `nucleo/generico.py` | Aba "Qualquer PDF". |
| `base/` | Base de produtos no PostgreSQL (banco `conversor`): NCM, CEST, IPI, embalagem, custo, compra e venda. Veja abaixo. |

O motor não depende do Tkinter: o mesmo código serve ao `.exe` e ao site.

### Base de produtos (PostgreSQL)

Guarda no PC os dados que completam o pedido, para ninguém precisar enviar planilha a cada conversão. Não faz parte do `.exe`: serve ao site na Central de Gestão.

```powershell
pip install "psycopg[binary]" python-docx openpyxl
$env:CONVERSOR_DATABASE_URL = "postgresql://USUARIO:SENHA@localhost:5432/conversor"   # banco "conversor", separado do Conciliador
python -m base criar-schema
python -m base validar fiscal AtualiProdutos.csv      # só lê e mostra avisos, sem banco
python -m base fiscal AtualiProdutos.csv --email voce@empresa
python -m base precos "todos os produtos.xlsx" --email voce@empresa
python -m base tipi tipi.docx --email voce@empresa
python -m base resumo
```

| Arquivo | Tabela | O que lê |
| --- | --- | --- |
| `AtualiProdutos.csv` | `produtos_fiscal` | Código interno, código de barras, NCM e CEST. CSV em Latin-1, com o bloco PIS/COFINS no topo. O %IPI deste arquivo não é usado. |
| `todos_os_produtos.xlsx` | `produtos_precos` | Colunas fixas: G embalagem, J custo, K compra, L venda (o cabeçalho da planilha é desalinhado). |
| `tipi.docx` | `tipi` | Alíquota de IPI por NCM de 8 dígitos; "NT" vale 0. |

- Cada importação troca só a sua tabela, numa transação: se algo falhar ou o arquivo estiver errado, a base antiga fica como está. O histórico (quem, quando, avisos) fica em `importacoes`.
- Busca (`base.buscar_produtos`): primeiro pelo código de barras, depois pelo código. A alíquota vem do NCM inteiro; se ele não está na TIPI, tenta os 7, 6, 5 e 4 primeiros dígitos, mas só quando todos os NCMs da TIPI com esse início têm a mesma alíquota. Sem alíquota, o campo fica vazio (vira `CONFERIR` na planilha).
- Os arquivos reais têm dados da empresa: ficam só no PC (`.gitignore` bloqueia `*.csv`, `*.xlsx`, `*.docx` e a pasta `Base de dados de teste/`).

### Testes

```powershell
python test_conversor.py
python test_base.py
```

`test_base.py` cria os próprios arquivos de exemplo, com dados inventados. As leituras rodam sempre; os testes com banco só rodam com `TEST_DATABASE_URL` (ex.: `postgresql://postgres:SENHA@localhost:5432/conversor_teste`), num schema temporário que é apagado no fim.


### Planilha do pedido com os dados da base

Com a base (conexão PostgreSQL) a planilha ganha, depois do Total: Preço de venda, NCM, CEST, IPI (%), Qtd. embalagem, Valor Tabela comprado e Fidelidade da NF, e a coluna Conferência. A busca é por código de barras e, se não achar, pelo Código ERP. Produto fora da base e NCM sem alíquota saem como CONFERIR em vermelho; compra R$ 0,00 sai em vermelho. A Fidelidade é um texto livre (vazio sai vazio). Sem conexão, a planilha sai como antes e o log avisa.

```
python test_pedido_base.py   # com TEST_DATABASE_URL para o teste com base
```

Os testes que dependem de pedidos reais usam PDFs na pasta `exemplos/` (`pedido_texto.pdf` e `pedido_imagem.pdf`). Essa pasta não vai para o GitHub porque os pedidos têm dados de clientes; sem ela, esses testes são pulados.

### Gerando o `.exe`

```powershell
pip install pyinstaller
python -m PyInstaller Conversor_de_Pedidos.spec --noconfirm
```

O executável sai em `dist/`.

Atalhos no Windows (clique duas vezes; a janela só fecha quando você aperta uma tecla):
- `atualizar.bat`: baixa as últimas correções do GitHub (precisa de uma pasta clonada com `git clone`).
- `gerar_exe.bat`: instala as dependências e gera o `dist\Conversor_de_Pedidos.exe`. O arquivo `.spec` já inclui o ícone, os modelos do OCR e as dependências que o PyInstaller não encontra sozinho.

## Como funciona

- **PDF com texto:** o texto é lido com PyMuPDF trecho a trecho, respeitando o recorte das células. Alguns ERPs escrevem a descrição inteira e escondem o excesso; outros leitores misturam esse texto escondido com a coluna seguinte.
- **PDF em imagem:** o OCR (RapidOCR) roda sobre a imagem embutida na **resolução original**. Ampliar a imagem antes do OCR borra as letras e piora a leitura.
- **Linhas e colunas:** os trechos são agrupados pela posição vertical (linhas) e, na aba genérica, distribuídos em colunas pelas faixas em branco da página.

## Limitações

- No OCR, descrições podem ter pequenos erros de letras (ex.: `O` no lugar de `0`), e palavras muito próximas às vezes vêm juntas na mesma célula.
- Na aba genérica, duas tabelas com colunas diferentes na mesma página compartilham a mesma grade de colunas.
- A aba de pedidos foi feita para o layout de pedido de compra com colunas de código, código de barras, descrição, UM, quantidade, preço e total.

## Privacidade

PDFs, planilhas e logs são ignorados pelo git (veja `.gitignore`). Nenhum dado de cliente faz parte do código.

## Site (pasta `web/`)

Roda dentro da Central de Gestão, atrás do Caddy do Conciliador. Não tem login próprio: o Caddy faz o login e manda o e-mail em `X-Usuario-Email`; sem esse cabeçalho o site responde 403. Por isso ele só escuta em `127.0.0.1`.

```
pip install -r requirements-web.txt
set CONVERSOR_DATABASE_URL=postgresql://USUARIO:SENHA@localhost:5432/conversor
set ADMIN_EMAILS=guilherme@empresa.com,outro@empresa.com
python -m uvicorn web.app:app --host 127.0.0.1 --port 8225 --proxy-headers
```

- `/conversor/`: Converter, com as abas Pedido de compra (campo Fidelidade da NF, forçar OCR) e Qualquer PDF. Mostra o andamento e entrega o Excel; PDF e Excel temporários são apagados depois do download (ou em 1 hora) e na subida do site. Uma conversão por vez.
- `/conversor/base`: Atualizar base, só para e-mails em `ADMIN_EMAILS`. Três envios (`AtualiProdutos.csv`, `tipi.docx`, `todos_os_produtos.xlsx`), quadro com linhas e data da última atualização e histórico.
- Sem `CONVERSOR_DATABASE_URL`, o pedido sai sem as colunas da base e a tela avisa.

```
python test_web.py   # com TEST_DATABASE_URL para a parte da base
```

Instalação no Windows (banco, tarefa do Agendador, cadastro na tela Aplicativos): veja `docs/INSTALACAO-WEB.md` (não verificado no Windows).
