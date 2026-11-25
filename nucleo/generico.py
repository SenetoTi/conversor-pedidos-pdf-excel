"""Qualquer PDF -> Excel: uma linha por linha do PDF, colunas pelas faixas em branco."""

from .motores import *  # noqa: F401,F403
from .ocr import agrupar_caixas_em_linhas, caixas_rapidocr, renderizar_pagina_para_imagens
from .pdf_texto import caixas_texto_nativo


# ==============================================================================
# SEÇÃO 4B: CONVERSOR GENÉRICO (QUALQUER PDF -> EXCEL)
# ==============================================================================

def detectar_colunas(linhas):
    """
    Descobre as colunas da página pelas faixas verticais em branco: uma posição X pertence
    a uma coluna quando há texto nela em mais de 20% das linhas com mais de um trecho.
    Devolve a lista de faixas (x_inicio, x_fim), da esquerda para a direita.
    """
    # ponytail: uma grade de colunas por página; tabelas diferentes na mesma página dividem
    # a mesma grade. Se precisar, detectar colunas por bloco de linhas consecutivas.
    tabela = [l for l in linhas if len(l) > 1]
    if not tabela:
        return [(0, 1)]
    largura = int(max(b['x_max'] for l in tabela for b in l)) + 2
    ocupacao = [0] * largura
    for l in tabela:
        coberto = bytearray(largura)
        for b in l:
            x0 = max(int(b['x_min']), 0)
            coberto[x0:int(b['x_max']) + 1] = b'\x01' * (int(b['x_max']) + 1 - x0)
        for x in range(largura):
            ocupacao[x] += coberto[x]

    limite = 0.2 * len(tabela)
    alturas = sorted(b['height'] for l in tabela for b in l)
    vao_minimo = 0.6 * alturas[len(alturas) // 2]

    colunas, inicio, fim = [], None, 0
    for x in range(largura):
        if ocupacao[x] > limite:
            if inicio is not None and x - fim > vao_minimo:
                colunas.append((inicio, fim))
                inicio = None
            if inicio is None:
                inicio = x
            fim = x
    if inicio is not None:
        colunas.append((inicio, fim))
    return colunas or [(0, largura)]


def coluna_da_caixa(b, colunas):
    """Índice da coluna da caixa: a primeira que cobre 25% dela, senão a de maior sobreposição."""
    largura = max(b['x_max'] - b['x_min'], 1.0)
    sobre = [max(0.0, min(b['x_max'], c1) - max(b['x_min'], c0)) for c0, c1 in colunas]
    for i, s in enumerate(sobre):
        if s >= 0.25 * largura:
            return i
    if max(sobre) > 0:
        return sobre.index(max(sobre))
    # Caixa fora de todas as faixas: coluna mais próxima
    centro = (b['x_min'] + b['x_max']) / 2.0
    return min(range(len(colunas)), key=lambda i: abs((colunas[i][0] + colunas[i][1]) / 2.0 - centro))


def valor_celula(txt):
    """Número no formato brasileiro com vírgula (1.245,60) vira número; o resto fica texto."""
    # O OCR costuma soltar espaços dentro do número ("15, 10")
    limpo = re.sub(r'\s', '', txt) if re.fullmatch(r'-?[\d.,\s]+', txt) else txt
    if re.fullmatch(r'-?(\d{1,3}(\.\d{3})+|\d+),\d+', limpo):
        return float(limpo.replace('.', '').replace(',', '.'))
    return txt


def converter_pdf_generico(caminho_pdf, caminho_excel, forcar_ocr=False, aba_por_pagina=True, callback_log=None):
    """
    Converte qualquer PDF em Excel mantendo a disposição visual: cada linha do PDF vira uma
    linha da planilha e as colunas são detectadas pelos espaços em branco da página.
    Páginas com texto são lidas direto; páginas em imagem passam pelo OCR.
    """
    def log(msg):
        if callback_log:
            callback_log(msg)
        print(f"[PDF Genérico] {msg}")

    if not HAS_PYMUPDF:
        raise RuntimeError("A conversão genérica precisa do PyMuPDF:\npip install pymupdf")

    doc = fitz.open(caminho_pdf)
    total_paginas = len(doc)
    doc.close()
    log(f"Arquivo selecionado: '{os.path.basename(caminho_pdf)}' ({total_paginas} páginas)")
    if RAPIDOCR_ERRO:
        log(f"Aviso: o RapidOCR falhou ao iniciar: {RAPIDOCR_ERRO}")

    wb = Workbook()
    ws = wb.active
    ws.title = "Pág 1" if aba_por_pagina else "PDF"
    fonte = Font(name="Calibri", size=10)
    num_linha = 1
    paginas_com_conteudo = 0

    for i in range(total_paginas):
        boxes = [] if forcar_ocr else caixas_texto_nativo(caminho_pdf, i)
        modo = "texto"
        if sum(len(b['text']) for b in boxes) < 40:
            modo = "OCR"
            if HAS_RAPIDOCR and rapid_ocr_engine:
                imagens = renderizar_pagina_para_imagens(caminho_pdf, i)
                boxes = caixas_rapidocr(imagens[0]) if imagens else []
            elif not boxes:
                log(f"Pág. {i+1}: sem texto e sem motor de OCR disponível.")

        if aba_por_pagina and i > 0:
            ws = wb.create_sheet(f"Pág {i+1}")
            num_linha = 1

        linhas = agrupar_caixas_em_linhas(boxes)
        if not linhas:
            log(f"Pág. {i+1}: nada encontrado.")
            continue
        paginas_com_conteudo += 1
        colunas = detectar_colunas(linhas)
        log(f"Pág. {i+1}: {len(linhas)} linhas e {len(colunas)} colunas via {modo}.")

        for linha in linhas:
            celulas = {}
            for b in linha:
                celulas.setdefault(coluna_da_caixa(b, colunas), []).append(b['text'])
            for col, textos in celulas.items():
                ws.cell(row=num_linha, column=col + 1, value=valor_celula(' '.join(textos))).font = fonte
            num_linha += 1
        num_linha += 1  # linha em branco entre páginas quando tudo vai na mesma aba

    if paginas_com_conteudo == 0:
        raise RuntimeError("Nenhum conteúdo pôde ser lido do PDF (sem texto e sem OCR disponível).")

    for aba in wb.worksheets:
        for col in aba.columns:
            maior = max((len(str(c.value)) for c in col if c.value is not None), default=0)
            aba.column_dimensions[get_column_letter(col[0].column)].width = min(max(maior + 2, 6), 60)

    wb.save(caminho_excel)
    log(f"Sucesso! {paginas_com_conteudo} página(s) convertida(s) em: {caminho_excel}")
    return paginas_com_conteudo


