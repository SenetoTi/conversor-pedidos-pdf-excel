"""Tratamento de imagem e OCR com reconstrução espacial 2D."""

from .motores import *  # noqa: F401,F403


# ==============================================================================
# SEÇÃO 1: TRATAMENTO DE IMAGEM E EXTRAÇÃO DE OCR COM RECONSTRUÇÃO ESPACIAL 2D
# ==============================================================================

def preprocessar_imagem_ocr(pil_img):
    """
    Otimiza a imagem escaneada para OCR:
    - Escala de cinza
    - Aumento de contraste (destaca texto contra fundo)
    - Filtro de nitidez (aguça caracteres numéricos finos)
    """
    if not HAS_PIL or not pil_img:
        return pil_img
    try:
        img = pil_img.convert('L')
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)
        return img
    except Exception:
        return pil_img


def renderizar_pagina_para_imagens(caminho_pdf, page_idx, page_obj=None):
    """
    Renderiza ou extrai a imagem da página do PDF em alta resolução (300 DPI).
    """
    imagens = []

    # 1. PyMuPDF (fitz) - Renderizador de máxima nitidez e velocidade
    if HAS_PYMUPDF and caminho_pdf:
        try:
            doc = fitz.open(caminho_pdf)
            if page_idx < len(doc):
                pg = doc[page_idx]
                # Página que é uma única imagem (ERP em nuvem / scanner): usa a imagem embutida
                # na resolução original. Reamostrar para 300 DPI borra as letras e piora o OCR.
                infos = pg.get_image_info(xrefs=True)
                if len(infos) == 1 and pg.rotation == 0 and infos[0].get("xref"):
                    a, b, c, d = infos[0]["transform"][:4]
                    cobre = abs(fitz.Rect(infos[0]["bbox"])) >= 0.8 * abs(pg.rect)
                    if cobre and a > 0 and d > 0 and abs(b) < 1e-3 and abs(c) < 1e-3:
                        try:
                            dados = doc.extract_image(infos[0]["xref"])["image"]
                            img = Image.open(io.BytesIO(dados)).convert("RGB")
                            doc.close()
                            return [img]
                        except Exception as e:
                            print(f"[PyMuPDF imagem embutida warn] {e}")
                pix = pg.get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                imagens.append(img)
                doc.close()
                return imagens
        except Exception as e:
            print(f"[PyMuPDF render warn] {e}")

    # 2. pdfplumber to_image()
    if HAS_PDFPLUMBER and caminho_pdf:
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                if page_idx < len(pdf.pages):
                    im_obj = pdf.pages[page_idx].to_image(resolution=300)
                    imagens.append(im_obj.original)
                    return imagens
        except Exception as e:
            print(f"[pdfplumber render warn] {e}")

    # 3. pypdf imagens embutidas (se for PDF envelopando imagem crua)
    if HAS_PIL and page_obj and hasattr(page_obj, "images"):
        try:
            for img_file in page_obj.images:
                pil_img = Image.open(io.BytesIO(img_file.data))
                imagens.append(pil_img)
        except Exception as e:
            print(f"[pypdf images warn] {e}")

    return imagens


def agrupar_caixas_em_linhas(boxes):
    """
    Agrupa as caixas {'x_min', 'x_max', 'y_center', 'height', 'text'} que compartilham a mesma
    faixa horizontal (linha Y). Devolve as linhas do topo ao rodapé, cada uma ordenada por X.
    """
    # Ordena inicialmente por Y
    boxes.sort(key=lambda b: (b['y_center'], b['x_min']))
    rows = []

    for b in boxes:
        placed = False
        for row in rows:
            row_y_center = sum(item['y_center'] for item in row) / len(row)
            avg_h = sum(item['height'] for item in row) / len(row)
            threshold = max(9.0, avg_h * 0.55)
            if abs(b['y_center'] - row_y_center) <= threshold:
                row.append(b)
                placed = True
                break
        if not placed:
            rows.append([b])

    # Ordena linhas verticalmente
    rows.sort(key=lambda r: sum(item['y_center'] for item in r) / len(r))

    # Dentro de cada linha, ordena da esquerda para a direita (X)
    for r in rows:
        r.sort(key=lambda item: item['x_min'])
    return rows


def reconstruir_linhas_por_coordenadas(boxes):
    """
    Reconstrói as linhas de texto físicas ordenadas no espaço visual 2D:
    Recebe caixas com {'x_min', 'x_max', 'y_center', 'height', 'text'}.
    1. Agrupa palavras que compartilham a mesma faixa horizontal (linha Y).
    2. Ordena as linhas do topo até o rodapé da página.
    3. Em cada linha, ordena os termos rigorosamente da esquerda para a direita (X).
    Isso impede que colunas ou blocos sejam lidos misturados!
    """
    linhas_texto = []
    for r in agrupar_caixas_em_linhas(boxes):
        linha_str = ' '.join(item['text'] for item in r if item['text'])
        if linha_str.strip():
            linhas_texto.append(linha_str.strip())

    return linhas_texto


def caixas_rapidocr(pil_img):
    """
    Executa o RapidOCR e devolve as caixas de texto com suas coordenadas.
    Página deitada (relatório impresso girado 90°): a maioria das caixas sai mais alta que larga.
    Nesse caso gira a imagem nos dois sentidos e fica com o de melhor leitura, senão as colunas
    viram linhas e nenhum produto é reconhecido.
    """
    boxes = _ocr_caixas(pil_img)
    verticais = sum(1 for b in boxes if (b['y_max'] - b['y_min']) > (b['x_max'] - b['x_min']))
    if not boxes or verticais <= len(boxes) / 2:
        return boxes

    # Sem o classificador de ângulo, o sentido errado (texto de cabeça para baixo) lê mal
    # e tem pontuação bem menor. ponytail: atributo interno do rapidocr 1.x; sem ele compara com o classificador ligado.
    cls_antes = getattr(rapid_ocr_engine, 'use_angle_cls', None)
    try:
        if cls_antes is not None:
            rapid_ocr_engine.use_angle_cls = False
        pontuacao = {g: sum(b['score'] for b in _ocr_caixas(pil_img.rotate(g, expand=True))) for g in (-90, 90)}
    finally:
        if cls_antes is not None:
            rapid_ocr_engine.use_angle_cls = cls_antes
    return _ocr_caixas(pil_img.rotate(max(pontuacao, key=pontuacao.get), expand=True))


def _ocr_caixas(pil_img):
    import numpy as np
    result, _ = rapid_ocr_engine(np.array(pil_img))
    boxes = []
    for item in result or []:
        poly = item[0]
        txt = str(item[1]).strip()
        if not txt:
            continue
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x_min = min(xs)
        x_max = max(xs)
        y_min = min(ys)
        y_max = max(ys)
        boxes.append({
            'x_min': x_min,
            'x_max': x_max,
            'y_min': y_min,
            'y_max': y_max,
            'y_center': (y_min + y_max) / 2.0,
            'height': max(y_max - y_min, 10.0),
            'score': float(item[2]) if len(item) > 2 else 0.0,
            'text': txt
        })
    return boxes


def executar_ocr_com_reconstrucao(pil_img):
    """
    Executa OCR em uma imagem PIL e reconstrói as linhas visualmente
    evitando que os dados fiquem misturados.
    """
    # 1. Tenta RapidOCR (motor 100% Python ONNX)
    if HAS_RAPIDOCR and rapid_ocr_engine:
        try:
            boxes = caixas_rapidocr(pil_img)
            if boxes:
                linhas = reconstruir_linhas_por_coordenadas(boxes)
                texto = "\n".join(linhas)
                if len(texto.strip()) > 30:
                    return texto
        except Exception as e:
            print(f"[RapidOCR reconstrução erro] {e}")

    # 2. Tenta Tesseract OCR com image_to_data (coordenadas completas de cada palavra)
    if HAS_TESSERACT and HAS_PIL:
        try:
            img_tratada = preprocessar_imagem_ocr(pil_img)
            try:
                data = pytesseract.image_to_data(img_tratada, lang='por+eng', output_type=pytesseract.Output.DICT)
            except Exception:
                data = pytesseract.image_to_data(img_tratada, output_type=pytesseract.Output.DICT)

            boxes = []
            n_words = len(data.get('text', []))
            for idx in range(n_words):
                w_txt = str(data['text'][idx]).strip()
                if not w_txt:
                    continue
                left = data['left'][idx]
                top = data['top'][idx]
                w = data['width'][idx]
                h = data['height'][idx]
                boxes.append({
                    'x_min': left,
                    'x_max': left + w,
                    'y_min': top,
                    'y_max': top + h,
                    'y_center': top + h / 2.0,
                    'height': max(float(h), 8.0),
                    'text': w_txt
                })

            if boxes:
                linhas = reconstruir_linhas_por_coordenadas(boxes)
                texto = "\n".join(linhas)
                if len(texto.strip()) > 30:
                    return texto
        except Exception as e:
            print(f"[Tesseract coordenadas erro] {e}")

        # Fallback Tesseract simples
        try:
            img_tratada = preprocessar_imagem_ocr(pil_img)
            config_tess = "--oem 3 --psm 6"
            try:
                txt = pytesseract.image_to_string(img_tratada, lang='por+eng', config=config_tess)
            except Exception:
                txt = pytesseract.image_to_string(img_tratada, config=config_tess)
            if txt and len(txt.strip()) > 30:
                return txt
        except Exception as e:
            print(f"[Tesseract simples erro] {e}")

    return ""


