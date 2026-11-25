"""Leitura de PDF de texto (PyMuPDF por trechos, pdfplumber e pypdf de reserva)."""

from .motores import *  # noqa: F401,F403
from .ocr import executar_ocr_com_reconstrucao, reconstruir_linhas_por_coordenadas, renderizar_pagina_para_imagens


# ==============================================================================
# SEÇÃO 2: RECONSTRUÇÃO NATIVA DE PDF (DOCUMENTOS DIGITAIS)
# ==============================================================================

def extrair_texto_pagina_2d(page):
    """
    Reconstrói as linhas visualmente agrupando pedaços de texto pela coordenada Y vertical
    no leitor nativo pypdf.
    """
    linhas_y = {}

    def visitor_body(text, cm, tm, fontDict, fontSize):
        if text and text.strip():
            try:
                x = round(tm[4], 1)
                y = round(tm[5], 1)
            except Exception:
                return

            matched_y = None
            for ey in linhas_y:
                if abs(ey - y) <= 3.5:
                    matched_y = ey
                    break
            if matched_y is None:
                matched_y = y
                linhas_y[matched_y] = []
            linhas_y[matched_y].append((x, text))

    try:
        page.extract_text(visitor_text=visitor_body)
        if linhas_y:
            sorted_ys = sorted(linhas_y.keys(), reverse=True)
            reconstruidas = []
            for y in sorted_ys:
                row_items = sorted(linhas_y[y], key=lambda item: item[0])
                row_text = ' '.join(item[1].strip() for item in row_items if item[1].strip())
                if row_text:
                    reconstruidas.append(row_text)
            resultado = '\n'.join(reconstruidas)
            if len(resultado.strip()) > 30:
                return resultado
    except Exception:
        pass
    return None


def caixas_texto_nativo(pdf_path, page_idx):
    """Devolve os trechos de texto nativo da página (PyMuPDF) como caixas com coordenadas."""
    doc = fitz.open(pdf_path)
    try:
        if page_idx >= len(doc):
            return []
        blocos = doc[page_idx].get_text("dict")["blocks"]
    finally:
        doc.close()

    # Converte pontos do PDF para a escala de 300 DPI esperada pela reconstrução 2D
    k = 300 / 72.0
    boxes = []
    for b in blocos:
        for l in b.get("lines", []):
            for s in l["spans"]:
                txt = s["text"].strip()
                if not txt:
                    continue
                x0, y0, x1, y1 = s["bbox"]
                boxes.append({
                    'x_min': x0 * k,
                    'x_max': x1 * k,
                    'y_center': (y0 + y1) / 2.0 * k,
                    'height': max((y1 - y0) * k, 10.0),
                    'text': txt
                })
    return boxes


def extrair_texto_pagina_trechos(pdf_path, page_idx):
    """
    Lê o texto nativo com PyMuPDF mantendo cada trecho (célula) inteiro.
    O PyMuPDF respeita o recorte das células: ERPs que escrevem a descrição completa
    e escondem o excesso não têm o texto escondido misturado com a coluna seguinte
    (ex: 'TIJUCAS 193411' + 'CX 1' virando 'TIJUCAS 1C93X3 411' no pdfplumber/pypdf).
    """
    try:
        resultado = "\n".join(reconstruir_linhas_por_coordenadas(caixas_texto_nativo(pdf_path, page_idx)))
        if len(resultado.strip()) > 40:
            return resultado
    except Exception as e:
        print(f"[PyMuPDF trechos warn] {e}")
    return None


def extrair_texto_pagina(page, pdf_path=None, page_idx=0, forcar_ocr=False, callback_log=None):
    """
    Extrai texto da página utilizando métodos nativos de layout e, se for escaneada
    ou se 'forcar_ocr' estiver ativo, aplica OCR com reconstrução espacial 2D.
    """
    def log(msg):
        if callback_log:
            callback_log(msg)

    # Se NÃO forçado a usar OCR, tenta extrações nativas digitais
    if not forcar_ocr:
        # 0. PyMuPDF por trechos (respeita o recorte das células)
        if HAS_PYMUPDF and pdf_path:
            t = extrair_texto_pagina_trechos(pdf_path, page_idx)
            if t:
                return t, "Nativo (PyMuPDF Trechos)"

        # 1. pdfplumber modo layout nativo
        if HAS_PDFPLUMBER and pdf_path:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    if page_idx < len(pdf.pages):
                        t = pdf.pages[page_idx].extract_text(layout=True)
                        if t and len(t.strip()) > 40:
                            return t, "Nativo (pdfplumber Layout)"
            except Exception:
                pass

        # 2. pypdf Reconstrução 2D
        if HAS_PYPDF and page:
            t_2d = extrair_texto_pagina_2d(page)
            if t_2d and len(t_2d.strip()) > 40:
                return t_2d, "Nativo (pypdf Reconstrução 2D)"

            # 3. pypdf modo layout
            try:
                t = page.extract_text(extraction_mode="layout")
                if t and len(t.strip()) > 40:
                    return t, "Nativo (pypdf Layout)"
            except Exception:
                pass

            # 4. pypdf padrão
            try:
                t = page.extract_text()
                if t and len(t.strip()) > 40:
                    return t, "Nativo (pypdf Padrão)"
            except Exception:
                pass

    # 5. Se chegou aqui, é um documento escaneado (ou forçado OCR)
    log(f"   [Página {page_idx+1}] Acionando Motor de OCR com Reconstrução 2D...")

    if not HAS_RAPIDOCR and not HAS_TESSERACT:
        log("   [Aviso OCR] Nenhum motor de OCR instalado para ler este documento escaneado.")
        return "", "Sem OCR instalado"

    imagens = renderizar_pagina_para_imagens(pdf_path, page_idx, page)
    if not imagens:
        log("   [Aviso OCR] Não foi possível renderizar a página em imagem.")
        return "", "Falha na renderização de imagem"

    textos_ocr = []
    for idx_img, img in enumerate(imagens):
        txt_ocr = executar_ocr_com_reconstrucao(img)
        if txt_ocr:
            textos_ocr.append(txt_ocr)

    texto_final = "\n".join(textos_ocr)
    if len(texto_final.strip()) > 30:
        log(f"   [OCR Concluído] {len(texto_final.strip())} caracteres reconstruídos espacialmente!")
        return texto_final, "OCR Inteligente (2D Reconstruído)"

    return "", "Falha no OCR"


