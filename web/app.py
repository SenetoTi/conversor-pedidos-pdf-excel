"""Site do Conversor de Pedidos (Etapa 4): roda em 127.0.0.1:8225, sob /conversor/, atrás do Caddy.

Sem login próprio: o Caddy faz o login (forward_auth) e manda o e-mail em X-Usuario-Email.
Sem esse cabeçalho o pedido recebe 403. Só e-mails de ADMIN_EMAILS (separados por vírgula) atualizam a base.
Variáveis de ambiente: CONVERSOR_DATABASE_URL (banco "conversor"; a DATABASE_URL é do Conciliador e não é usada aqui), ADMIN_EMAILS, NOME_SISTEMA.
"""
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

PREFIXO = "/conversor"
PASTA_TEMP = Path(tempfile.gettempdir()) / "conversor_web"
VALIDADE_SEGUNDOS = 3600  # trabalho não baixado é apagado depois disso
LIMITE_MB = 80

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["NOME_SISTEMA"] = os.environ.get("NOME_SISTEMA", "Central de Gestão")
templates.env.globals["PREFIXO"] = PREFIXO

fila = ThreadPoolExecutor(max_workers=1)  # uma conversão por vez: o OCR usa bastante CPU do PC
trabalhos = {}
trava = threading.Lock()


def admins():
    return {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}


def usuario(request: Request):
    email = (request.headers.get("X-Usuario-Email") or "").strip()
    if not email:
        raise HTTPException(403, "Acesso só pela Central de Gestão.")
    return email


def so_admin(email=Depends(usuario)):
    if email.lower() not in admins():
        raise HTTPException(403, "Só o administrador atualiza a base.")
    return email


def pagina(request, nome, email, **contexto):
    contexto.update(email=email, admin=email.lower() in admins())
    return templates.TemplateResponse(request, nome, contexto)


# ------------------------------------------------------------------ temporários

def limpar_temporarios(tudo=False):
    """Apaga trabalhos antigos (ou todos, na subida do site)."""
    agora = time.time()
    with trava:
        for id_, t in list(trabalhos.items()):
            if t["estado"] != "processando" and (tudo or agora - t["criado"] > VALIDADE_SEGUNDOS):
                shutil.rmtree(t["pasta"], ignore_errors=True)
                del trabalhos[id_]
    if tudo and PASTA_TEMP.exists():
        for p in PASTA_TEMP.iterdir():
            shutil.rmtree(p, ignore_errors=True)


@asynccontextmanager
async def ciclo(app):
    PASTA_TEMP.mkdir(exist_ok=True)
    limpar_temporarios(tudo=True)
    yield


app = FastAPI(title="Conversor de Pedidos", lifespan=ciclo, docs_url=None, redoc_url=None, openapi_url=None)
rotas = APIRouter(prefix=PREFIXO)


@app.exception_handler(HTTPException)
async def erro_http(request: Request, exc: HTTPException):
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(request, "erro.html", {"codigo": exc.status_code, "mensagem": exc.detail,
                                                                  "email": request.headers.get("X-Usuario-Email", ""), "admin": False},
                                          status_code=exc.status_code)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


# ------------------------------------------------------------------ banco

def abrir_banco():
    """Conexão com a base de produtos, ou None se não estiver configurada/acessível."""
    if not os.environ.get("CONVERSOR_DATABASE_URL"):
        return None
    try:
        import base
        return base.conectar()
    except Exception as e:
        print(f"Base indisponível ({type(e).__name__})")
        return None


# ------------------------------------------------------------------ conversão

def nome_seguro(nome):
    nome = re.sub(r"[^\w.\- ]", "_", os.path.basename(nome or "arquivo.pdf"))
    return nome or "arquivo.pdf"


def rodar_trabalho(id_):
    t = trabalhos[id_]
    t["estado"] = "processando"
    conn = None
    try:
        saida = str(Path(t["pasta"]) / (Path(t["nome"]).stem + ".xlsx"))
        if t["tipo"] == "pedido":
            from nucleo.pedido import extrair_pdf_para_excel
            conn = abrir_banco()
            if conn is None:
                t["log"].append("Base de produtos indisponível: planilha gerada sem as colunas da base.")
            filiais, avisos = extrair_pdf_para_excel(t["pdf"], saida, forcar_ocr=t["ocr"], callback_log=t["log"].append,
                                                     conexao=conn, fidelidade=t["fidelidade"])
            t["resumo"] = f"{filiais} filial(is) e {avisos} ponto(s) a conferir (marcados em vermelho na planilha)."
        else:
            from nucleo.generico import converter_pdf_generico
            paginas = converter_pdf_generico(t["pdf"], saida, forcar_ocr=t["ocr"], callback_log=t["log"].append)
            t["resumo"] = f"{paginas} página(s) convertida(s)."
        os.remove(t["pdf"])  # o PDF original não precisa ficar guardado
        t["saida"], t["estado"] = saida, "pronto"
    except Exception as e:
        t["estado"], t["erro"] = "erro", str(e) or type(e).__name__
    finally:
        if conn is not None:
            conn.close()


async def novo_trabalho(request, email, tipo, pdf: UploadFile, ocr, fidelidade=""):
    limpar_temporarios()
    nome = nome_seguro(pdf.filename)
    if not nome.lower().endswith(".pdf"):
        raise HTTPException(400, "Envie um arquivo PDF.")
    id_ = uuid.uuid4().hex
    pasta = PASTA_TEMP / id_
    pasta.mkdir(parents=True)
    caminho = pasta / nome
    tamanho = 0
    with open(caminho, "wb") as f:
        while bloco := await pdf.read(1024 * 1024):
            tamanho += len(bloco)
            if tamanho > LIMITE_MB * 1024 * 1024:
                f.close()
                shutil.rmtree(pasta, ignore_errors=True)
                raise HTTPException(413, f"O PDF passa de {LIMITE_MB} MB.")
            f.write(bloco)
    trabalhos[id_] = {"id": id_, "email": email, "tipo": tipo, "nome": nome, "pdf": str(caminho), "pasta": str(pasta),
                      "ocr": bool(ocr), "fidelidade": (fidelidade or "").strip(), "estado": "fila", "log": [],
                      "criado": time.time(), "saida": None, "erro": "", "resumo": ""}
    fila.submit(rodar_trabalho, id_)
    return RedirectResponse(f"{PREFIXO}/trabalho/{id_}", status_code=303)


def meu_trabalho(id_, email):
    t = trabalhos.get(id_)
    if not t or t["email"].lower() != email.lower():
        raise HTTPException(404, "Trabalho não encontrado (ele é apagado depois de baixar ou de 1 hora).")
    return t


# ------------------------------------------------------------------ rotas

@rotas.get("/", response_class=HTMLResponse)
def converter(request: Request, email=Depends(usuario)):
    return pagina(request, "converter.html", email, aba=request.query_params.get("aba", "pedido"),
                  com_base=bool(os.environ.get("CONVERSOR_DATABASE_URL")))


@rotas.post("/pedido")
async def enviar_pedido(request: Request, pdf: UploadFile = File(...), fidelidade: str = Form(""),
                        ocr: bool = Form(False), email=Depends(usuario)):
    return await novo_trabalho(request, email, "pedido", pdf, ocr, fidelidade)


@rotas.post("/generico")
async def enviar_generico(request: Request, pdf: UploadFile = File(...), ocr: bool = Form(False), email=Depends(usuario)):
    return await novo_trabalho(request, email, "generico", pdf, ocr)


@rotas.get("/trabalho/{id_}", response_class=HTMLResponse)
def ver_trabalho(id_: str, request: Request, email=Depends(usuario)):
    return pagina(request, "trabalho.html", email, t=meu_trabalho(id_, email))


@rotas.get("/trabalho/{id_}/estado")
def estado_trabalho(id_: str, email=Depends(usuario)):
    t = meu_trabalho(id_, email)
    return {"estado": t["estado"], "erro": t["erro"], "resumo": t["resumo"], "log": t["log"][-30:]}


@rotas.get("/trabalho/{id_}/baixar")
def baixar(id_: str, email=Depends(usuario)):
    t = meu_trabalho(id_, email)
    if t["estado"] != "pronto" or not t["saida"] or not os.path.exists(t["saida"]):
        raise HTTPException(409, "A planilha ainda não está pronta.")
    from starlette.background import BackgroundTask

    def apagar():
        shutil.rmtree(t["pasta"], ignore_errors=True)
        trabalhos.pop(id_, None)
    return FileResponse(t["saida"], filename=os.path.basename(t["saida"]),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        background=BackgroundTask(apagar))


# ------------------------------------------------------------------ atualizar base

TIPOS_BASE = [("fiscal", "AtualiProdutos.csv", "NCM e CEST dos produtos"),
              ("tipi", "tipi.docx", "Alíquota de IPI pelo NCM"),
              ("precos", "todos_os_produtos.xlsx", "Embalagem, custo, compra e venda")]


def dados_da_base():
    conn = abrir_banco()
    if conn is None:
        return None, [], []
    try:
        ultimas = {}
        for tipo, linhas, data, email, arquivo in conn.execute(
                "select tipo, linhas, data, email, arquivo from importacoes order by id desc").fetchall():
            ultimas.setdefault(tipo, {"linhas": linhas, "data": data, "email": email, "arquivo": arquivo})
        historico = conn.execute("select data, tipo, arquivo, linhas, email from importacoes order by id desc limit 30").fetchall()
        return ultimas, historico, True
    except Exception:  # base ainda sem as tabelas
        return {}, [], True
    finally:
        conn.close()


def pagina_base(request, email, mensagem="", erro="", avisos=()):
    ultimas, historico, ok = dados_da_base()
    return pagina(request, "atualizar_base.html", email, tipos=TIPOS_BASE, ultimas=ultimas or {}, historico=historico,
                  sem_banco=ultimas is None, mensagem=mensagem, erro=erro, avisos=list(avisos))


@rotas.get("/base", response_class=HTMLResponse)
def atualizar_base(request: Request, email=Depends(so_admin)):
    return pagina_base(request, email)


@rotas.post("/base/{tipo}", response_class=HTMLResponse)
async def enviar_base(tipo: str, request: Request, arquivo: UploadFile = File(...), email=Depends(so_admin)):
    import base
    importar = {"fiscal": base.importar_fiscal, "tipi": base.importar_tipi, "precos": base.importar_precos}.get(tipo)
    if importar is None:
        raise HTTPException(404, "Tipo de arquivo desconhecido.")
    conn = abrir_banco()
    if conn is None:
        return pagina_base(request, email, erro="Banco de dados não configurado ou indisponível.")
    pasta = PASTA_TEMP / uuid.uuid4().hex
    pasta.mkdir(parents=True)
    try:
        caminho = pasta / nome_seguro(arquivo.filename)
        with open(caminho, "wb") as f:
            shutil.copyfileobj(arquivo.file, f)
        base.criar_schema(conn)
        r = importar(conn, str(caminho), email)
        return pagina_base(request, email, mensagem=f"{caminho.name}: {r['linhas']} linhas importadas.", avisos=r["avisos"])
    except base.ErroImportacao as e:
        return pagina_base(request, email, erro=str(e))
    finally:
        conn.close()
        shutil.rmtree(pasta, ignore_errors=True)


@rotas.get("/status")
def status():
    return {"ok": True}


app.include_router(rotas)


@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse(f"{PREFIXO}/")
