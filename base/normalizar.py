"""Limpeza de códigos e números vindos dos arquivos e dos pedidos."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation


def sem_acento(texto):
    base = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in base if not unicodedata.combining(c))


def normalizar_barras(valor):
    """Só dígitos, sem zeros à esquerda: '07896673138309' e 7896673138309 viram '7896673138309'.

    A mesma função serve para o arquivo e para o pedido, então os dois lados sempre se encontram.
    """
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return re.sub(r"\D", "", str(valor)).lstrip("0")


def normalizar_ncm(valor):
    """Devolve (ncm, problema). ncm tem 8 dígitos ou é vazio. problema: None, 'sufixo' ou 'invalido'.

    '70134100' e '9503.00.99' viram 8 dígitos; '09021000.1' (sufixo depois do ponto) fica '09021000' com problema 'sufixo'.
    """
    texto = str(valor or "").strip()
    if not texto:
        return "", None
    achou = re.fullmatch(r"(\d{8})\.\d+", texto)
    if achou:
        return achou.group(1), "sufixo"
    digitos = re.sub(r"\D", "", texto)
    if re.fullmatch(r"[\d.]+", texto) and len(digitos) == 8:
        return digitos, None
    return "", "invalido"


def normalizar_cest(valor):
    """Devolve (cest, problema). Formato 'NN.NNN.NN'; 7 dígitos sem pontos são formatados. problema: None ou 'invalido'."""
    texto = str(valor or "").strip()
    if not texto:
        return "", None
    if re.fullmatch(r"\d{2}\.\d{3}\.\d{2}", texto):
        return texto, None
    if re.fullmatch(r"\d{7}", texto):
        return f"{texto[:2]}.{texto[2:5]}.{texto[5:]}", None
    return "", "invalido"


def numero(valor):
    """Número da planilha como Decimal; vazio vira None. Levanta ValueError se não for número."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    texto = str(valor).replace("\xa0", " ").strip().replace(" ", "")
    if texto == "":
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        raise ValueError(f"não é número: {valor!r}") from None
