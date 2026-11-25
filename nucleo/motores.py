"""Bibliotecas opcionais (PDF, imagem, OCR) e se cada uma está disponível."""

import io
import os
import re
import subprocess
import sys

# 1. Leitura e Renderização de PDF
HAS_PYMUPDF = False
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    pass

HAS_PDFPLUMBER = False
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    pass

HAS_PYPDF = False
try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    pass

# 2. Geração de Planilhas Excel
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# 3. Processamento de Imagens (PIL)
HAS_PIL = False
try:
    from PIL import Image, ImageEnhance, ImageFilter
    HAS_PIL = True
except ImportError:
    pass

# 4. Motores de OCR para PDFs Escaneados
HAS_RAPIDOCR = False
RAPIDOCR_ERRO = ""
rapid_ocr_engine = None
try:
    from rapidocr_onnxruntime import RapidOCR
    rapid_ocr_engine = RapidOCR()
    HAS_RAPIDOCR = True
except Exception as e:
    # Qualquer falha ao iniciar o OCR (ex: modelos ausentes no .exe) não pode impedir o app de abrir
    RAPIDOCR_ERRO = f"{type(e).__name__}: {e}"

HAS_TESSERACT = False
try:
    import pytesseract
    tesseract_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
        os.path.join(os.getenv("USERPROFILE", ""), "AppData", "Local", "Programs", "Tesseract-OCR", "tesseract.exe"),
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract"
    ]
    for p in tesseract_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            HAS_TESSERACT = True
            break
except ImportError:
    pass


