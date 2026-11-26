"""Pedido de compra: identificação do cabeçalho, extração dos produtos e geração do Excel por filial."""

from .motores import *  # noqa: F401,F403
from .pdf_texto import extrair_texto_pagina


# ==============================================================================
# SEÇÃO 3: IDENTIFICAÇÃO SEMÂNTICA, NORMALIZAÇÃO E ENCAIXE NO PADRÃO
# ==============================================================================

def limpar_numero(val_str):
    """Converte números em formato monetário ou numérico brasileiro para float."""
    if not val_str:
        return 0.0
    try:
        s = str(val_str).strip().replace('.', '').replace(',', '.')
        return float(s)
    except Exception:
        return 0.0


def normalizar_linha_ocr(texto):
    """
    Remove ruídos comuns gerados por OCR em tabelas e descola códigos aglutinados:
    - Corrige confusões de 'O' e 'o' em valores com vírgula ou decimais (ex: 12,OOO -> 12,000 / 8,5O -> 8,50)
    - Elimina espaços espúrios entre vírgula/ponto e dígitos (ex: 6, 000 -> 6,000 / 20. 36 -> 20,36 / 360, 000 -> 360,000)
    - Converte ponto decimal isolado em valores monetários (ex: 3.46 -> 3,46 / 5.50 -> 5,50), preservando dimensões (1.3L, 22CM)
    - Remove ruídos no final da descrição antes da UM (ex: 'OOOE', ':', '|')
    - Descola códigos de barras EAN colados em vírgulas ou códigos ERP
    """
    if not texto:
        return ""
    t = texto.replace('\xa0', ' ').replace('|', ' ').replace('：', ' ')
    # ':' que o OCR cola entre códigos (ex: 544986:7908008824945 -> 544986 7908008824945)
    t = re.sub(r'(\d):(?=\d{8})', r'\1 ', t)

    # Corrige 'O' ou 'o' no lugar de zeros numéricos decimais
    t = re.sub(r'(\d+)[,\.](\d*)([Oo]+)(\d*)', lambda m: m.group(0).replace('O', '0').replace('o', '0'), t)
    t = re.sub(r'([Oo]+)[,\.](\d+)', lambda m: m.group(0).replace('O', '0').replace('o', '0'), t)

    # Ponto de milhar seguido de espaço (1. 800,00 -> 1.800,00), antes da regra abaixo virar 1,800,00
    t = re.sub(r'(\d)\.\s+(\d{3},\d)', r'\1.\2', t)

    # Elimina espaços espúrios entre vírgula/ponto e dígitos numéricos (6, 000 -> 6,000 | 20. 36 -> 20,36 | 360, 000 -> 360,000)
    t = re.sub(r'(\d+)[,\.]\s+(\d+)', r'\1,\2', t)

    # Converte ponto isolado de preço em vírgula (ex: 3.46 -> 3,46 | 5.50 -> 5,50), sem alterar dimensões (1.3L, 2.5L)
    t = re.sub(r'(?<=\s)(\d{1,4})\.(\d{2})(?=\s|$)', r'\1,\2', t)

    # Remove ruídos de final de descrição
    t = re.sub(r'\s+OOOE\b', '', t)
    t = re.sub(r':(?=\s+[A-Z]{2}|\s+\d)', '', t)

    # Descola código de barras colado em vírgula (ex: ,007891234567895 -> ,00 7891234567895)
    t = re.sub(r',(\d{2,3})(789\d{10}|790\d{10}|\d{13})', r',\1 \2', t)

    # Descola código de barras colado em código ERP (ex: 0123457891234567895 -> 012345 7891234567895)
    t = re.sub(r'(\d{4,8})(789\d{10}|790\d{10})', r'\1 \2', t)
    t = re.sub(r'(\.\d{2})(789\d{10}|790\d{10})', r'\1 \2', t)

    return t.strip()


def analisar_codigos_prefixo(prefixo_str):
    """
    Analisa os tokens que antecedem o código de barras (EAN-13) para separar:
    - Código do Fornecedor (opcional, ex: 1234.56, 7890, 0001.00, 9A123B)
    - Código ERP da Loja (obrigatório, numérico de 4 a 8 dígitos, ex: 012345, 987654)

    Tratamentos inteligentes:
    1. Corrige ERP fragmentado pelo OCR: se o último token tiver 1 ou 2 dígitos (ex: '1')
       e o penúltimo tiver 3 a 5 dígitos (ex: '98765'), o OCR quebrou o código em dois.
       Unifica: '98765' + '4' -> '987654'.
    2. Evita duplicação: se cod_forn for idêntico a codigo_erp, limpa cod_forn = "".
    3. Se houver apenas 1 token, ele é o código ERP (cod_forn fica vazio).
    """
    if not prefixo_str:
        return "", ""
    tokens = prefixo_str.strip().split()
    if not tokens:
        return "", ""

    # Se o último token for 1 ou 2 dígitos (ex: '4') e o penúltimo tiver 3 a 5 dígitos (ex: '98765')
    if len(tokens) >= 2 and len(tokens[-1]) <= 2 and tokens[-1].isdigit() and tokens[-2].isdigit() and len(tokens[-2]) in [3, 4, 5]:
        tokens[-2] = tokens[-2] + tokens[-1]
        tokens.pop()

    # Se houver apenas 1 token
    if len(tokens) == 1:
        return "", tokens[0]

    # Se houver 2 tokens idênticos (duplicação por quebra de linha ou repetição)
    if len(tokens) == 2 and tokens[0] == tokens[1]:
        return "", tokens[1]

    codigo_erp = tokens[-1]
    cod_forn = " ".join(tokens[:-1])

    if cod_forn == codigo_erp:
        cod_forn = ""

    return cod_forn, codigo_erp


def extrair_dados_cabecalho_rodape(linhas):
    """
    Extrai com tolerância semântica todos os dados cadastrais da empresa compradora e filial,
    mesmo que as linhas do OCR estejam fora da ordem tradicional.
    """
    info = {
        'filial_cod': '',
        'ped_compra': '',
        'data_pedido': '',
        'razao_social': '',
        'cnpj': '',
        'ie': '',
        'endereco': '',
        'telefone': '',
        'email': '',
        'data_entrega': '',
        'cond_pagamento': '',
        'comprador': '',
        'quant_itens': '',
        'total_geral': '',
        'observacoes': '',
        'fornecedor': '',
        'cnpj_fornecedor': ''
    }

    texto_completo = "\n".join(linhas)

    # 1. CNPJ (com ou sem máscara)
    m_cnpj = re.search(r'\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b', texto_completo)
    if not m_cnpj:
        m_cnpj = re.search(r'CNPJ[\s:\.]*([0-9\.\/-]{14,20})', texto_completo, re.IGNORECASE)
    if m_cnpj:
        info['cnpj'] = m_cnpj.group(1).strip()
        # Se a filial não foi encontrada explicitamente, deduz do CNPJ (ex: /0002- -> Filial 002)
        m_fil_cnpj = re.search(r'/(\d{4})-', info['cnpj'])
        if m_fil_cnpj and not info['filial_cod']:
            info['filial_cod'] = str(int(m_fil_cnpj.group(1))).zfill(3)

    # 2. Código da Filial
    m_filial = re.search(r'Filial[\s:\.]*([0-9A-Za-z]+)', texto_completo, re.IGNORECASE)
    if m_filial:
        f_val = m_filial.group(1).strip()
        if f_val.isdigit():
            info['filial_cod'] = str(int(f_val)).zfill(3)
        else:
            info['filial_cod'] = f_val

    # 3. Número do Pedido de Compra
    m_ped = re.search(r'(?:Ped\.?\s*Compra|Pedido|Ordem\s*de\s*Compra|OC)[\s\.:#Nº]*([0-9]{3,12})', texto_completo, re.IGNORECASE)
    if m_ped:
        info['ped_compra'] = m_ped.group(1).strip()

    # 4. Data do Pedido
    m_data = re.search(r'Data\s*(?:do\s*)?Pedido[\s:\.]*([\d\/]{6,10})', texto_completo, re.IGNORECASE)
    if m_data:
        info['data_pedido'] = m_data.group(1).strip()

    # 5. Inscrição Estadual
    m_ie = re.search(r'Insc\.?\s*Estad\.?[\s:\.]*([\d-]+)', texto_completo, re.IGNORECASE)
    if m_ie:
        info['ie'] = m_ie.group(1).strip()

    # 6. Razão Social (busca em linhas próximas do topo com palavras-chave empresariais)
    for l in linhas[:15]:
        l_s = l.strip()
        if any(k in l_s.upper() for k in ['LTDA', 'S.A.', 'S/A', 'EIRELI', ' ME ', 'COMERCIO', 'COM.']):
            # Isola a Razão Social retirando trechos como CNPJ: ... ou Página x de y
            rz = re.split(r'CNPJ|Insc|Data|P[áa]gina|RUA|AV\.', l_s, flags=re.IGNORECASE)[0].strip()
            if len(rz) <= 3:
                continue
            if not info['razao_social']:
                info['razao_social'] = rz
            elif rz != info['razao_social']:
                # Segunda empresa do cabeçalho, com CNPJ na mesma linha: o fornecedor
                # (ex: comprador ARUNA, fornecedor MABEL). Exigir o CNPJ evita pegar descrição de produto.
                m_cf = re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', l_s)
                if m_cf and m_cf.group(0) != info['cnpj']:
                    info['fornecedor'] = rz
                    info['cnpj_fornecedor'] = m_cf.group(0)
                    break

    # 7. Endereço, Telefone e E-mail
    for l in linhas[:20]:
        if any(k in l.upper() for k in ["RUA ", "AV. ", "RODOVIA ", "ALAMEDA ", "CEP:"]) and not info['endereco']:
            info['endereco'] = re.sub(r'P[áa]gina\s+\d+\s+de\s+\d+', '', l).strip()
        if "Telefone:" in l and not info['telefone']:
            m_tel = re.search(r'Telefone:\s*([\d\s()-]+)', l)
            if m_tel:
                info['telefone'] = m_tel.group(1).strip()
        if "Email:" in l and not info['email']:
            m_em = re.search(r'Email:\s*([^\s]+@[^\s]+)', l)
            if m_em:
                info['email'] = m_em.group(1).strip()

    # 8. Data de Entrega
    m_ent = re.search(r'Data\s*(?:de\s*)?Entrega[\s:\.]*([\d\/]{6,10})', texto_completo, re.IGNORECASE)
    if m_ent:
        info['data_entrega'] = m_ent.group(1).strip()

    # 9. Condição de Pagamento
    m_cond = re.search(r'Condi[çc][ãa]o\s*(?:de\s*)?Pagamento[\s:\.]*([^\n\r]+)', texto_completo, re.IGNORECASE)
    if m_cond:
        info['cond_pagamento'] = m_cond.group(1).split("Despesas")[0].split("Comprador")[0].strip()

    # 10. Comprador
    m_comp = re.search(r'Comprador[\s:\.]*([A-Za-zÀ-ÿ\s]+)', texto_completo, re.IGNORECASE)
    if m_comp:
        info['comprador'] = m_comp.group(1).split("Email")[0].split("Obs")[0].strip()

    # 11. Quantidade de Itens e Total Geral do Rodapé
    m_qi = re.search(r'Quant\.?\s*Itens[\s:\.]*(\d+)', texto_completo, re.IGNORECASE)
    if m_qi:
        info['quant_itens'] = m_qi.group(1).strip()

    # Aceita o espaço que o OCR põe depois do ponto de milhar (43. 563,60)
    m_tot = re.search(r'Total\s*Geral[^0-9\n\r]*?(\d{1,3}(?:\.\s?\d{3})*,\d{2}|\d+,\d{2})', texto_completo, re.IGNORECASE)
    if m_tot:
        info['total_geral'] = re.sub(r'\s', '', m_tot.group(1))

    # 12. Observações
    m_obs = re.search(r'Observa[çc][õo]es:\s*([^\n\r]+(?:(?:\n[^\n\r]+){1,4})?)', texto_completo, re.IGNORECASE)
    if m_obs:
        obs_raw = m_obs.group(1)
        for parada in ["Peso Total:", "Total Geral:", "Quant. Itens:", "Subst. Tributária:"]:
            if parada in obs_raw:
                obs_raw = obs_raw.split(parada)[0]
        info['observacoes'] = " ".join([l.strip() for l in obs_raw.splitlines() if l.strip()])

    return info


def extrair_produtos_inteligente(linhas):
    """
    Motor semântico de extração e costura de produtos:
    - Identifica produtos em linhas completas.
    - Costura linhas quebradas pelo OCR (Stream Stitcher).
    - Descola códigos e normaliza ruídos de OCR em decimais ('O' -> '0').
    - Utiliza analisar_codigos_prefixo() para separar Cód. Fornecedor e Código ERP sem fragmentação nem duplicidade.
    - Isola a Unidade de Medida (UM) real sem confundir com medidas da descrição (1.0 LT, 2.4L, 22CM, 25,5CM).
    - Impede que quantidade e preço vazem para dentro da descrição.
    - Valida e calcula totais matemáticos cruzados (total = quant * preco_unit).
    - Entrega rigorosamente no padrão de 8 colunas pré-estabelecido.
    """
    produtos = []
    buffer_linha = ""

    for l in linhas:
        l_norm = normalizar_linha_ocr(l)
        if not l_norm:
            continue

        # Ignora cabeçalhos de tabela e linhas de metadados
        if any(k in l_norm.lower() for k in [
            'código de barras', 'codigo de barras', 'preço unit', 'preco unit',
            'tot. subs', 'turno ent', 'tipo de frete', 'ordem de compra',
            'inscrição estadual', 'insc. estad', 'condição de pagamento',
            'telefone:', 'email:', 'status: aberto', 'endereço:', 'endereco:'
        ]):
            continue

        candidata = (buffer_linha + " " + l_norm).strip() if buffer_linha else l_norm

        # 1. Busca código de barras EAN (789..., 790... ou 13 dígitos)
        ean_match = re.search(r'(789\d{10}|790\d{10}|\b\d{13}\b)', candidata)
        texto_apos_ean = candidata[ean_match.end():].strip() if ean_match else candidata

        # Procura a Unidade de Medida (UM) de faturamento oficial: UN, CX, PC, KG, FD, RL, M2, PAR, JG, PCT, BD, SC
        # Deve estar perto dos números finais ou antes de '1' / quantidade (NÃO 'L' ou 'LT' isolado no meio do nome)
        m_um = re.search(r'\b(CX|UN|PC|KG|FD|RL|M2|PAR|JG|PÇ|SC|BD|PCT)(?:\s+1|\s+01)?\b(?=\s+\d)', texto_apos_ean, re.IGNORECASE)
        if not m_um:
            m_um = re.search(r'\b(CX|UN|PC|KG|FD|RL|M2|PAR|JG|PÇ|SC|BD|PCT)\b(?=\s+\d)', texto_apos_ean, re.IGNORECASE)
        if not m_um:
            m_um = re.search(r'\b(CX|UN|PC|KG|FD|RL|M2|PAR|JG|PÇ|SC|BD|PCT)(?:\s+1|\s+01)?\b', texto_apos_ean, re.IGNORECASE)

        if m_um:
            um = m_um.group(1).upper()
            desc_bruta = texto_apos_ean[:m_um.start()].strip()
            resto_nums = texto_apos_ean[m_um.start() + len(m_um.group(0)):].strip()
        else:
            um = "UN"
            m_num_inicio = re.search(r'(?<=\s)(\d{1,4}(?:\.\d{3})*,\d{2,4}|\d+,\d{2,4})(?=\s|$)', texto_apos_ean)
            if m_num_inicio:
                desc_bruta = texto_apos_ean[:m_num_inicio.start()].strip()
                resto_nums = texto_apos_ean[m_num_inicio.start():].strip()
            else:
                desc_bruta = texto_apos_ean
                resto_nums = ""

        # Extrai números no segmento numérico final
        nums = re.findall(r'\b\d{1,4}(?:\.\d{3})*,\d{2,4}\b|\b\d+,\d{2,4}\b', resto_nums)

        # Caso A: Linha com EAN e números
        if ean_match and len(nums) >= 2:
            ean = ean_match.group(1)
            prefixo = candidata[:ean_match.start()].strip()
            cod_forn, codigo_erp = analisar_codigos_prefixo(prefixo)

            desc = re.sub(r'[:\-\|]+$', '', desc_bruta).strip()
            desc = re.sub(r'^\d+\s+', '', desc).strip()
            desc = re.sub(r'\s+', ' ', desc).strip()

            quant_str = nums[0]
            preco_str = nums[1]
            total_str = nums[-1] if len(nums) >= 3 else ""

            q_num = limpar_numero(quant_str)
            p_num = limpar_numero(preco_str)
            t_num = limpar_numero(total_str) if total_str else round(q_num * p_num, 2)

            # Validação cruzada: se o preço estiver 0 mas tivermos total e quant
            if p_num == 0.0 and q_num > 0 and t_num > 0:
                p_num = round(t_num / q_num, 2)
                preco_str = f"{p_num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            # Se total estiver 0 e tivermos quant e preco
            if t_num == 0.0 and q_num > 0 and p_num > 0:
                t_num = round(q_num * p_num, 2)
                total_str = f"{t_num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            if not total_str:
                total_str = f"{t_num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            produtos.append({
                'cod_forn': cod_forn,
                'codigo_erp': codigo_erp,
                'cod_barras': ean,
                'descricao': desc,
                'um': um,
                'quant': quant_str,
                'preco_unit': preco_str,
                'total': total_str,
                'quant_num': q_num,
                'preco_num': p_num,
                'total_num': t_num
            })
            buffer_linha = ""

        # Caso B: Linha com EAN mas ainda sem os números (fragmentada pelo OCR)
        elif ean_match and len(nums) < 2:
            buffer_linha = candidata

        # Caso C: Linha SEM EAN, mas que pode ser produto de layout alternativo
        elif not ean_match and m_um and len(nums) >= 2 and not buffer_linha:
            texto_antes = candidata[:m_um.start()].strip()
            m_cod = re.match(r'^([A-Za-z0-9\.\-\/]{2,15})\s+(.+)', texto_antes)
            if m_cod:
                cod_erp = m_cod.group(1)
                desc = m_cod.group(2).strip()
            else:
                cod_erp = ""
                desc = texto_antes

            quant_str = nums[0]
            preco_str = nums[1]
            total_str = nums[-1] if len(nums) >= 3 else ""
            q_num = limpar_numero(quant_str)
            p_num = limpar_numero(preco_str)
            t_num = limpar_numero(total_str) if total_str else round(q_num * p_num, 2)

            produtos.append({
                'cod_forn': "",
                'codigo_erp': cod_erp,
                'cod_barras': "",
                'descricao': desc,
                'um': um,
                'quant': quant_str,
                'preco_unit': preco_str,
                'total': total_str,
                'quant_num': q_num,
                'preco_num': p_num,
                'total_num': t_num
            })
            buffer_linha = ""

        # Caso D: Linha que pode ser continuação do buffer anterior
        elif not ean_match and buffer_linha:
            buffer_linha = candidata

        # Caso E: Código fornecedor/ERP isolado antes da linha com EAN
        elif not ean_match and re.match(r'^[A-Za-z0-9\.\-\/\s]{2,25}$', l_norm):
            buffer_linha = l_norm

    return produtos


# ==============================================================================
# SEÇÃO 4: PROCESSO COMPLETO DE CONVERSÃO E GERAÇÃO DO EXCEL NO PADRÃO
# ==============================================================================

def extrair_pdf_para_excel(caminho_pdf, caminho_excel, forcar_ocr=False, callback_log=None, conexao=None, fidelidade=""):
    """
    Se `conexao` (base de produtos) for dada, a planilha ganha as colunas da base depois do Total;
    `fidelidade` é o texto livre da Fidelidade da NF (vazio = coluna vazia). Sem `conexao`, sai como antes.
    Processa o PDF integralmente (página por página), executa OCR com reconstrução
    espacial 2D se necessário, identifica empresas/filiais e seus produtos cadastrados
    e gera a planilha Excel no padrão pré-estabelecido.
    """
    def log(msg):
        if callback_log:
            callback_log(msg)
        print(f"[PDF Conversor] {msg}")

    if not HAS_PYPDF and not HAS_PDFPLUMBER and not HAS_PYMUPDF:
        raise RuntimeError("Instale as bibliotecas para leitura de PDF:\npip install pypdf openpyxl")

    reader = None
    total_paginas = 0

    if HAS_PYPDF:
        reader = PdfReader(caminho_pdf)
        total_paginas = len(reader.pages)
    elif HAS_PDFPLUMBER:
        with pdfplumber.open(caminho_pdf) as p:
            total_paginas = len(p.pages)
    elif HAS_PYMUPDF:
        doc = fitz.open(caminho_pdf)
        total_paginas = len(doc)
        doc.close()

    log(f"Arquivo selecionado: '{os.path.basename(caminho_pdf)}'")
    log(f"Total de páginas a processar: {total_paginas}")

    # Diagnóstico dos motores disponíveis
    if HAS_RAPIDOCR:
        log("Motor OCR primário: RapidOCR (Ativo, 100% Python ONNX)")
    elif HAS_TESSERACT:
        log("Motor OCR primário: Tesseract OCR (Ativo no Windows)")
    else:
        log("Aviso: Nenhum motor OCR detectado. Se for PDF escaneado, instale: pip install rapidocr-onnxruntime")
    if RAPIDOCR_ERRO:
        log(f"Aviso: o RapidOCR falhou ao iniciar: {RAPIDOCR_ERRO}")

    if forcar_ocr:
        log("Opção ativada: FORÇAR OCR INTELIGENTE EM TODAS AS PÁGINAS.")

    pedidos_filiais = {}
    filial_chave_atual = None
    total_caracteres_geral = 0
    paginas_com_ocr = 0

    for i in range(total_paginas):
        page = reader.pages[i] if (reader and i < len(reader.pages)) else None
        texto, modo_extracao = extrair_texto_pagina(
            page, caminho_pdf, i, forcar_ocr=forcar_ocr, callback_log=log
        )
        chars = len(texto.strip()) if texto else 0
        total_caracteres_geral += chars

        if "OCR" in modo_extracao:
            paginas_com_ocr += 1

        log(f"Pág. {i+1}: {chars} caracteres obtidos via [{modo_extracao}].")

        if not texto or chars < 10:
            continue

        linhas = [l.strip() for l in texto.split('\n') if l.strip()]

        # 1. Identifica dados cadastrais da empresa/filial da página
        info_pagina = extrair_dados_cabecalho_rodape(linhas)

        # 2. Determina a chave identificadora da filial
        chave_candidata = ""
        if info_pagina['filial_cod']:
            chave_candidata = f"FILIAL_{info_pagina['filial_cod']}"
            if info_pagina['ped_compra']:
                chave_candidata += f"_PED_{info_pagina['ped_compra']}"
        elif info_pagina['cnpj']:
            chave_candidata = f"CNPJ_{info_pagina['cnpj']}"
        elif info_pagina['razao_social']:
            chave_candidata = f"RZ_{info_pagina['razao_social'][:20]}"

        if chave_candidata:
            filial_chave_atual = chave_candidata
            if filial_chave_atual not in pedidos_filiais:
                log(f"-> Filial Identificada na Pág. {i+1}: {filial_chave_atual} ({info_pagina['razao_social']})")
                pedidos_filiais[filial_chave_atual] = {
                    'filial_cod': info_pagina['filial_cod'],
                    'ped_compra': info_pagina['ped_compra'],
                    'data_pedido': info_pagina['data_pedido'],
                    'razao_social': info_pagina['razao_social'] or (f"Filial {info_pagina['filial_cod']}" if info_pagina['filial_cod'] else "Filial"),
                    'cnpj': info_pagina['cnpj'],
                    'ie': info_pagina['ie'],
                    'endereco': info_pagina['endereco'],
                    'telefone': info_pagina['telefone'],
                    'email': info_pagina['email'],
                    'data_entrega': info_pagina['data_entrega'],
                    'cond_pagamento': info_pagina['cond_pagamento'],
                    'comprador': info_pagina['comprador'],
                    'quant_itens': info_pagina['quant_itens'],
                    'total_geral': info_pagina['total_geral'],
                    'observacoes': info_pagina['observacoes'],
                    'fornecedor': info_pagina['fornecedor'],
                    'cnpj_fornecedor': info_pagina['cnpj_fornecedor'],
                    'produtos': []
                }
            else:
                for k, v in info_pagina.items():
                    if v and not pedidos_filiais[filial_chave_atual].get(k):
                        pedidos_filiais[filial_chave_atual][k] = v

        if not filial_chave_atual:
            filial_chave_atual = "FILIAL_001"
            pedidos_filiais[filial_chave_atual] = {
                'filial_cod': '001',
                'ped_compra': '',
                'data_pedido': '',
                'razao_social': 'Filial 001',
                'cnpj': '',
                'ie': '',
                'endereco': '',
                'telefone': '',
                'email': '',
                'data_entrega': '',
                'cond_pagamento': '',
                'comprador': '',
                'quant_itens': '',
                'total_geral': '',
                'observacoes': '',
                'produtos': []
            }

        # Atualiza totais de rodapé se presentes nesta página
        for k in ['quant_itens', 'total_geral', 'data_entrega', 'cond_pagamento', 'comprador', 'observacoes']:
            if info_pagina.get(k):
                pedidos_filiais[filial_chave_atual][k] = info_pagina[k]

        # 3. Extrai produtos cadastrados da página com o motor semântico
        novos_produtos = extrair_produtos_inteligente(linhas)
        if novos_produtos:
            pedidos_filiais[filial_chave_atual]['produtos'].extend(novos_produtos)
            log(f"   -> {len(novos_produtos)} produtos estruturados e validados no padrão!")
        else:
            log("   -> Nenhum produto detectado nesta página.")

    if total_caracteres_geral == 0:
        raise RuntimeError(
            "O arquivo PDF é uma imagem escaneada e nenhum motor de OCR conseguiu ler o conteúdo.\n\n"
            "Solução Simples no Terminal (CMD):\n"
            "pip install pymupdf rapidocr-onnxruntime pillow\n\n"
            "Isso ativa o OCR de alta precisão 100% automático no Python!"
        )

    return gerar_planilha(pedidos_filiais, caminho_excel, log, conexao=conexao, fidelidade=fidelidade)


# ==============================================================================
# GERAÇÃO DA PLANILHA EXCEL FORMATADA (PADRÃO PRÉ-ESTABELECIDO)
# ==============================================================================

COLUNAS_BASE = [
    "Preço de venda", "NCM", "CEST", "IPI (%)", "Qtd. embalagem", "Valor Tabela comprado", "Fidelidade da NF",
]
CONFERIR = "CONFERIR"


def _dados_da_base(conexao, pedidos_filiais):
    """Busca em lote (uma vez por pedido). Devolve {id(produto): Produto da base}."""
    from base import buscar_produtos
    itens, achados = [], []
    for filial in pedidos_filiais.values():
        for prod in filial['produtos']:
            itens.append((prod.get('cod_barras', ''), prod.get('codigo_erp', '')))
            achados.append(prod)
    if not itens:
        return {}
    return {id(prod): dado for prod, dado in zip(achados, buscar_produtos(conexao, itens))}


def _linha_da_base(dado, fidelidade):
    """As 7 células da base: lista de (valor, formato, erro). erro=True vira vermelho."""
    def num(valor):
        return float(valor) if valor is not None else None

    def ou_conferir(valor, ok, formato):
        if not ok or valor is None:
            return (CONFERIR, None, True)
        return (num(valor) if not isinstance(valor, str) else valor, formato, False)

    if dado is None:
        dado = type("SemDado", (), {"achou_fiscal": False, "achou_precos": False})()
    fiscal, precos = dado.achou_fiscal, dado.achou_precos
    compra = getattr(dado, "compra", None)
    compra_zero = precos and compra is not None and compra == 0
    return [
        ou_conferir(getattr(dado, "venda", None), precos, 'R$ #,##0.00'),
        ou_conferir(getattr(dado, "ncm", None) or None, fiscal, '@'),
        (getattr(dado, "cest", "") or "", '@', False) if fiscal else (CONFERIR, None, True),
        ou_conferir(getattr(dado, "aliquota_ipi", None), fiscal, '0.00"%"'),
        ou_conferir(getattr(dado, "embalagem", None), precos, '#,##0.####'),
        (num(compra), 'R$ #,##0.00', True) if compra_zero else ou_conferir(compra, precos, 'R$ #,##0.00'),
        (fidelidade or "", '@', False),
    ]


def gerar_planilha(pedidos_filiais, caminho_excel, log=lambda msg: None, conexao=None, fidelidade=""):
    """Escreve a planilha a partir dos pedidos já lidos. Devolve (filiais, avisos)."""
    com_base = conexao is not None
    dados_base = _dados_da_base(conexao, pedidos_filiais) if com_base else {}
    if not com_base:
        log("Base de produtos não configurada: planilha gerada sem as colunas da base.")
    fidelidade = (fidelidade or "").strip()
    col_conf = 9 + (len(COLUNAS_BASE) if com_base else 0)  # coluna do aviso "CONFERIR" da linha
    ultima_col = col_conf if com_base else 8

    wb = Workbook()
    ws = wb.active
    ws.title = "Pedidos por Filial"

    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    fonte_titulo = Font(name="Calibri", size=11, bold=True, color="1F497D")
    fonte_negrito = Font(name="Calibri", size=10, bold=True)
    fonte_normal = Font(name="Calibri", size=10)
    fonte_cabecalho_tab = Font(name="Calibri", size=10, bold=True, color="FFFFFF")

    fill_cabecalho_tab = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    fill_zebra = PatternFill(start_color="F2F5F8", end_color="F2F5F8", fill_type="solid")
    fill_divisor = PatternFill(start_color="B8CCE4", end_color="B8CCE4", fill_type="solid")
    fill_suspeito = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    fonte_suspeito = Font(name="Calibri", size=10, bold=True, color="9C0006")
    avisos = 0

    borda_fina = Border(
        left=Side(style='thin', color="BFBFBF"),
        right=Side(style='thin', color="BFBFBF"),
        top=Side(style='thin', color="BFBFBF"),
        bottom=Side(style='thin', color="BFBFBF")
    )
    borda_divisor = Border(
        top=Side(style='medium', color="1F497D"),
        bottom=Side(style='medium', color="1F497D")
    )

    num_linha = 1
    total_filiais_processadas = 0

    for chave, filial in pedidos_filiais.items():
        if not filial['produtos']:
            continue

        total_filiais_processadas += 1

        # 1. TÍTULO DO BLOCO DA FILIAL
        rotulo_filial = f"PEDIDO DE COMPRA - FILIAL {filial['filial_cod']} ({filial['razao_social']})"
        ws.cell(row=num_linha, column=1, value=rotulo_filial).font = fonte_titulo
        num_linha += 1

        # 2. METADADOS DA EMPRESA E PEDIDO
        metadados = [
            ("Pedido de Compra:", filial['ped_compra'], "Data Pedido:", filial['data_pedido'], "Data Entrega:", filial['data_entrega']),
            ("Razão Social:", filial['razao_social'], "CNPJ:", filial['cnpj'], "Insc. Estadual:", filial['ie']),
            ("Endereço:", filial['endereco'], "Telefone:", filial['telefone'], "Email:", filial['email']),
            ("Comprador:", filial['comprador'], "Cond. Pagamento:", filial['cond_pagamento'], "", "")
        ]
        if filial.get('fornecedor'):
            metadados.insert(2, ("Fornecedor:", filial['fornecedor'], "CNPJ Fornecedor:", filial.get('cnpj_fornecedor', ''), "", ""))

        for meta in metadados:
            c1, v1, c2, v2, c3, v3 = meta
            ws.cell(row=num_linha, column=1, value=c1).font = fonte_negrito
            ws.cell(row=num_linha, column=2, value=v1).font = fonte_normal
            if c2:
                ws.cell(row=num_linha, column=3, value=c2).font = fonte_negrito
                ws.cell(row=num_linha, column=4, value=v2).font = fonte_normal
            if c3:
                ws.cell(row=num_linha, column=5, value=c3).font = fonte_negrito
                ws.cell(row=num_linha, column=6, value=v3).font = fonte_normal
            num_linha += 1

        num_linha += 1  # Espaço antes da tabela

        # 3. CABEÇALHO DA TABELA DE PRODUTOS (8 COLUNAS DO PADRÃO)
        colunas_tabela = [
            "Cód. Forn.",
            "Código ERP",
            "Código de Barras",
            "Descrição do Produto",
            "UM",
            "Quant.",
            "Preço Unit.",
            "Total"
        ]
        if com_base:
            colunas_tabela = colunas_tabela + COLUNAS_BASE + ["Conferência"]

        for col_idx, col_nome in enumerate(colunas_tabela, start=1):
            cell = ws.cell(row=num_linha, column=col_idx, value=col_nome)
            cell.font = fonte_cabecalho_tab
            cell.fill = fill_cabecalho_tab
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = borda_fina
        num_linha += 1

        # 4. LINHAS DE PRODUTOS
        soma_quant = 0.0
        soma_total = 0.0

        for p_idx, prod in enumerate(filial['produtos']):
            bg = fill_zebra if (p_idx % 2 == 1) else None

            # Validação da linha: quantidade x preço tem que bater com o total lido
            # ponytail: tolerância fixa de R$ 0,05; se o ERP aplicar desconto/frete por item, descontar aqui
            if abs(prod['quant_num'] * prod['preco_num'] - prod['total_num']) > 0.05:
                bg = fill_suspeito
                avisos += 1
                ws.cell(row=num_linha, column=col_conf, value="CONFERIR: quant. x preço ≠ total").font = fonte_suspeito

            # Cód. Forn
            c = ws.cell(row=num_linha, column=1, value=prod['cod_forn'])
            c.font = fonte_normal
            c.alignment = Alignment(horizontal="left", vertical="center")
            c.border = borda_fina
            if bg: c.fill = bg

            # Código ERP
            c = ws.cell(row=num_linha, column=2, value=prod['codigo_erp'])
            c.font = fonte_normal
            c.alignment = Alignment(horizontal="left", vertical="center")
            c.border = borda_fina
            if bg: c.fill = bg

            # Código de Barras (EAN)
            c = ws.cell(row=num_linha, column=3, value=prod['cod_barras'])
            c.font = fonte_normal
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = borda_fina
            if bg: c.fill = bg

            # Descrição do Produto
            c = ws.cell(row=num_linha, column=4, value=prod['descricao'])
            c.font = fonte_normal
            c.alignment = Alignment(horizontal="left", vertical="center")
            c.border = borda_fina
            if bg: c.fill = bg

            # UM
            c = ws.cell(row=num_linha, column=5, value=prod['um'])
            c.font = fonte_normal
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = borda_fina
            if bg: c.fill = bg

            # Quantidade
            c = ws.cell(row=num_linha, column=6, value=prod['quant_num'])
            c.font = fonte_normal
            c.alignment = Alignment(horizontal="right", vertical="center")
            c.number_format = '#,##0.000'
            c.border = borda_fina
            if bg: c.fill = bg
            soma_quant += prod['quant_num']

            # Preço Unitário
            c = ws.cell(row=num_linha, column=7, value=prod['preco_num'])
            c.font = fonte_normal
            c.alignment = Alignment(horizontal="right", vertical="center")
            c.number_format = 'R$ #,##0.00'
            c.border = borda_fina
            if bg: c.fill = bg

            # Total
            c = ws.cell(row=num_linha, column=8, value=prod['total_num'])
            c.font = fonte_normal
            c.alignment = Alignment(horizontal="right", vertical="center")
            c.number_format = 'R$ #,##0.00'
            c.border = borda_fina
            if bg: c.fill = bg
            soma_total += prod['total_num']

            if com_base:
                for k, (valor, formato, erro) in enumerate(_linha_da_base(dados_base.get(id(prod)), fidelidade)):
                    c = ws.cell(row=num_linha, column=9 + k, value=valor)
                    c.font = fonte_suspeito if erro else fonte_normal
                    c.alignment = Alignment(horizontal="center" if valor == CONFERIR else ("left" if k == 6 else "right"), vertical="center")
                    if formato:
                        c.number_format = formato
                    c.border = borda_fina
                    if erro:
                        c.fill = fill_suspeito
                    elif bg:
                        c.fill = bg

                if any(erro for _, _, erro in _linha_da_base(dados_base.get(id(prod)), fidelidade)):
                    avisos += 1

            num_linha += 1

        # 5. LINHA DE SUBTOTAIS DA FILIAL
        c = ws.cell(row=num_linha, column=4, value="TOTAL DA FILIAL:")
        c.font = fonte_negrito
        c.alignment = Alignment(horizontal="right", vertical="center")
        c.border = borda_fina

        c = ws.cell(row=num_linha, column=6, value=soma_quant)
        c.font = fonte_negrito
        c.alignment = Alignment(horizontal="right", vertical="center")
        c.number_format = '#,##0.000'
        c.border = borda_fina

        c = ws.cell(row=num_linha, column=8, value=soma_total)
        c.font = fonte_negrito
        c.alignment = Alignment(horizontal="right", vertical="center")
        c.number_format = 'R$ #,##0.00'
        c.border = borda_fina

        num_linha += 1

        # 6. RODAPÉ DE RESUMO
        num_linha += 1
        ws.cell(row=num_linha, column=1, value="Total de Itens Cadastrados:").font = fonte_negrito
        ws.cell(row=num_linha, column=2, value=len(filial['produtos'])).font = fonte_normal

        if filial['total_geral']:
            ws.cell(row=num_linha, column=4, value="Total Geral Informado no PDF:").font = fonte_negrito
            ws.cell(row=num_linha, column=5, value=f"R$ {filial['total_geral']}").font = fonte_normal
            # Validação da filial: soma das linhas tem que bater com o Total Geral do PDF
            if abs(soma_total - limpar_numero(filial['total_geral'])) > 0.05:
                avisos += 1
                c = ws.cell(row=num_linha, column=6, value="CONFERIR: soma das linhas ≠ Total Geral do PDF")
                c.font = fonte_suspeito
                c.fill = fill_suspeito
                log(f"ATENÇÃO: Filial {filial['filial_cod']}: soma das linhas {soma_total:.2f} ≠ Total Geral do PDF {filial['total_geral']}")
        else:
            # Sem o Total Geral não há como conferir a soma: avisa em vez de passar em silêncio
            avisos += 1
            c = ws.cell(row=num_linha, column=4, value="CONFERIR: Total Geral não encontrado no PDF")
            c.font = fonte_suspeito
            c.fill = fill_suspeito
            log(f"ATENÇÃO: Filial {filial['filial_cod']}: Total Geral não encontrado no PDF, soma não conferida.")
        num_linha += 1

        if filial['observacoes']:
            ws.cell(row=num_linha, column=1, value="Observações:").font = fonte_negrito
            ws.cell(row=num_linha, column=2, value=filial['observacoes']).font = fonte_normal
            num_linha += 1

        # 7. LINHA DIVISÓRIA ENTRE FILIAIS
        num_linha += 1
        for col_idx in range(1, ultima_col + 1):
            cell = ws.cell(row=num_linha, column=col_idx, value="")
            cell.fill = fill_divisor
            cell.border = borda_divisor
        num_linha += 2

    if total_filiais_processadas == 0:
        raise RuntimeError(
            "Nenhum produto ou filial pôde ser identificado no documento.\n"
            "Dica: Marque a opção 'Forçar OCR Inteligente em Todas as Páginas' se o documento foi escaneado."
        )

    # 8. AJUSTE AUTOMÁTICO DE LARGURA DAS COLUNAS
    larguras_minimas = {
        'A': 14,  # Cód. Forn.
        'B': 14,  # Código ERP
        'C': 18,  # Código de Barras
        'D': 42,  # Descrição do Produto
        'E': 8,   # UM
        'F': 14,  # Quant.
        'G': 14,  # Preço Unit.
        'H': 16   # Total
    }
    if com_base:
        for letra, largura in zip("IJKLMNOP", (14, 12, 12, 10, 14, 20, 20, 30)):
            larguras_minimas[letra] = largura

    for col_letter, min_w in larguras_minimas.items():
        col_idx = ord(col_letter) - ord('A') + 1
        max_len = min_w
        for r in range(1, min(num_linha, 500)):
            val = ws.cell(row=r, column=col_idx).value
            if val is not None:
                max_len = max(max_len, min(len(str(val)) + 2, 60))
        ws.column_dimensions[col_letter].width = max_len

    # Salva planilha
    wb.save(caminho_excel)
    log(f"Sucesso! Planilha gerada com {total_filiais_processadas} filiais em: {caminho_excel}")
    if avisos:
        log(f"ATENÇÃO: {avisos} ponto(s) a conferir, marcados em vermelho na planilha.")
    return total_filiais_processadas, avisos


