#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversor de Pedidos de Compra (PDF -> Excel) - Versão 5.0 com OCR Inteligente
Desenvolvido para extrair com precisão dados de PDFs digitais e escaneados/digitalizados,
reconstruindo dados que ficam misturados ou fragmentados pelo OCR e organizando-os
no padrão pré-estabelecido de planilhas Excel estruturadas por filial.

Recursos:
1. Reconstrução Espacial 2D por Coordenadas (RapidOCR e Tesseract):
   - Evita colunas e palavras misturadas agrupando caixas delimitadoras pela linha horizontal física (Y)
     e ordenando da esquerda para a direita (X).
2. Costura Inteligente de Linhas Quebradas (Stream Stitcher):
   - Une automaticamente fragmentos de descrição, códigos de barras e preços divididos em várias linhas pelo OCR.
3. Cura Automática de Ruídos de OCR:
   - Corrige confusões clássicas de OCR em números ('O' ou 'o' em vez de '0', 'l'/'|' em vez de '1').
   - Descola códigos de barras concatenados com vírgulas ou códigos ERP.
4. Identificação Semântica da Empresa e Filial:
   - Detecta CNPJ, Razão Social, Número da Filial (mesmo a partir do sufixo do CNPJ /0002- ou da sigla da loja),
     Número do Pedido, Datas, Comprador, Condição de Pagamento e Totais Gerais.
5. Exportação Formatada no Padrão Pré-Estabelecido:
   - Cabeçalho executivo por filial com metadados completos.
   - Tabela de 8 colunas com formatação monetária e de quantidades.
   - Linhas zebra, totais e rodapé de observações.
"""

import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext

from nucleo.motores import *  # noqa: F401,F403
from nucleo.ocr import *  # noqa: F401,F403
from nucleo.pdf_texto import *  # noqa: F401,F403
from nucleo.pedido import *  # noqa: F401,F403
from nucleo.generico import *  # noqa: F401,F403


# ==============================================================================
# SEÇÃO 5: INTERFACE GRÁFICA TKINTER MODERNA
# ==============================================================================

class ConversorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Conversor de Pedidos PDF -> Excel | Versão 5.0 com OCR Inteligente")
        self.root.geometry("820x640")
        self.root.minsize(700, 520)
        # Ícone da janela: dentro do .exe ele fica na pasta temporária do PyInstaller (_MEIPASS)
        pasta = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        try:
            self.root.iconbitmap(os.path.join(pasta, "icone.ico"))
        except tk.TclError:
            pass

        self.caminho_pdf = tk.StringVar()
        self.caminho_excel = tk.StringVar()
        self.forcar_ocr = tk.BooleanVar(value=False)
        self.is_processing = False

        self._criar_layout()

    def _criar_layout(self):
        # 1. CABEÇALHO SUPERIOR
        header_frame = tk.Frame(self.root, bg="#1F497D", padx=16, pady=12)
        header_frame.pack(fill=tk.X)

        lbl_titulo = tk.Label(
            header_frame,
            text="Conversor de Pedidos de Compra (PDF -> Excel)",
            font=("Segoe UI", 14, "bold"),
            fg="#FFFFFF",
            bg="#1F497D"
        )
        lbl_titulo.pack(anchor=tk.W)

        lbl_sub = tk.Label(
            header_frame,
            text="Versão 5.0: Reconstrução Espacial 2D de Dados Misturados & OCR com Costura de Produtos",
            font=("Segoe UI", 9),
            fg="#DCE6F1",
            bg="#1F497D"
        )
        lbl_sub.pack(anchor=tk.W)

        # 2. CONTAINER PRINCIPAL
        abas = ttk.Notebook(self.root)
        abas.pack(fill=tk.BOTH, expand=True)
        aba_generica = tk.Frame(abas, padx=16, pady=12)
        abas.add(aba_generica, text="  Qualquer PDF  ")
        self._criar_aba_generica(aba_generica)
        main_frame = tk.Frame(abas, padx=16, pady=12)
        abas.add(main_frame, text="  Pedido de Compra  ")

        # SELETOR DE ARQUIVOS
        file_frame = tk.LabelFrame(main_frame, text=" Arquivos ", font=("Segoe UI", 10, "bold"), padx=10, pady=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))

        # PDF Input
        lbl_pdf = tk.Label(file_frame, text="Arquivo PDF:", font=("Segoe UI", 9))
        lbl_pdf.grid(row=0, column=0, sticky=tk.W, pady=4)
        entry_pdf = tk.Entry(file_frame, textvariable=self.caminho_pdf, font=("Segoe UI", 9))
        entry_pdf.grid(row=0, column=1, sticky=tk.EW, padx=8, pady=4)
        btn_pdf = tk.Button(file_frame, text="Selecionar PDF...", command=self._selecionar_pdf, width=15)
        btn_pdf.grid(row=0, column=2, pady=4)

        # Excel Output
        lbl_excel = tk.Label(file_frame, text="Salvar Excel em:", font=("Segoe UI", 9))
        lbl_excel.grid(row=1, column=0, sticky=tk.W, pady=4)
        entry_excel = tk.Entry(file_frame, textvariable=self.caminho_excel, font=("Segoe UI", 9))
        entry_excel.grid(row=1, column=1, sticky=tk.EW, padx=8, pady=4)
        btn_excel = tk.Button(file_frame, text="Alterar Local...", command=self._selecionar_excel, width=15)
        btn_excel.grid(row=1, column=2, pady=4)

        file_frame.columnconfigure(1, weight=1)

        # OPÇÕES DO MOTOR OCR
        opts_frame = tk.LabelFrame(main_frame, text=" Opções do Motor OCR & Reconstrução ", font=("Segoe UI", 9, "bold"), padx=10, pady=6)
        opts_frame.pack(fill=tk.X, pady=(0, 10))

        chk_ocr = tk.Checkbutton(
            opts_frame,
            text="Forçar OCR Inteligente em Todas as Páginas (recomendado para documentos escaneados/fotos)",
            variable=self.forcar_ocr,
            font=("Segoe UI", 9)
        )
        chk_ocr.pack(anchor=tk.W)

        # BOTÕES DE AÇÃO
        act_frame = tk.Frame(main_frame)
        act_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_inspecionar = tk.Button(
            act_frame,
            text="🔍 Inspecionar Leitura / OCR da Pág 1",
            command=self._inspecionar_pagina_1,
            font=("Segoe UI", 9),
            padx=10,
            pady=6
        )
        self.btn_inspecionar.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_converter = tk.Button(
            act_frame,
            text="⚡ Exportar para Excel (.xlsx)",
            command=self._iniciar_conversao,
            font=("Segoe UI", 10, "bold"),
            bg="#1F497D",
            fg="#FFFFFF",
            activebackground="#16365C",
            activeforeground="#FFFFFF",
            padx=16,
            pady=6
        )
        self.btn_converter.pack(side=tk.RIGHT)

        # BARRA DE PROGRESSO
        self.progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=(0, 8))

        # LOG EM TEMPO REAL
        log_frame = tk.LabelFrame(main_frame, text=" Progresso e Diagnóstico em Tempo Real ", font=("Segoe UI", 9, "bold"), padx=8, pady=8)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_log = scrolledtext.ScrolledText(log_frame, font=("Consolas", 9), state=tk.DISABLED, bg="#F9FAFB")
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        # Status inicial do sistema
        self._log("=== SISTEMA PRONTO ===")
        self._log(f"- Leitor Nativo (pypdf): {'Disponível' if HAS_PYPDF else 'Não instalado'}")
        self._log(f"- Renderizador (PyMuPDF): {'Disponível' if HAS_PYMUPDF else 'Não instalado (opcional)'}")
        self._log(f"- Motor OCR RapidOCR: {'Disponível (100% Python)' if HAS_RAPIDOCR else 'Não instalado'}")
        self._log(f"- Motor OCR Tesseract: {'Disponível no Windows' if HAS_TESSERACT else 'Não configurado'}")
        self._log("Selecione um arquivo PDF acima para iniciar.")

    def _criar_aba_generica(self, aba):
        """Segunda aba: converte qualquer PDF em Excel mantendo linhas e colunas da página."""
        self.gen_pdf = tk.StringVar()
        self.gen_excel = tk.StringVar()
        self.gen_forcar_ocr = tk.BooleanVar(value=False)
        self.gen_aba_por_pagina = tk.BooleanVar(value=True)

        tk.Label(
            aba,
            text="Converte qualquer PDF (relatórios, extratos, tabelas, PDFs escaneados) mantendo as linhas e colunas da página.",
            font=("Segoe UI", 9), anchor=tk.W, justify=tk.LEFT, wraplength=760
        ).pack(fill=tk.X, pady=(0, 8))

        file_frame = tk.LabelFrame(aba, text=" Arquivos ", font=("Segoe UI", 10, "bold"), padx=10, pady=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(file_frame, text="Arquivo PDF:", font=("Segoe UI", 9)).grid(row=0, column=0, sticky=tk.W, pady=4)
        tk.Entry(file_frame, textvariable=self.gen_pdf, font=("Segoe UI", 9)).grid(row=0, column=1, sticky=tk.EW, padx=8, pady=4)
        tk.Button(file_frame, text="Selecionar PDF...", command=self._gen_selecionar_pdf, width=15).grid(row=0, column=2, pady=4)
        tk.Label(file_frame, text="Salvar Excel em:", font=("Segoe UI", 9)).grid(row=1, column=0, sticky=tk.W, pady=4)
        tk.Entry(file_frame, textvariable=self.gen_excel, font=("Segoe UI", 9)).grid(row=1, column=1, sticky=tk.EW, padx=8, pady=4)
        tk.Button(file_frame, text="Alterar Local...", command=self._gen_selecionar_excel, width=15).grid(row=1, column=2, pady=4)
        file_frame.columnconfigure(1, weight=1)

        opts_frame = tk.LabelFrame(aba, text=" Opções ", font=("Segoe UI", 9, "bold"), padx=10, pady=6)
        opts_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Checkbutton(opts_frame, text="Uma aba da planilha para cada página (desmarcado: tudo em uma aba só)",
                       variable=self.gen_aba_por_pagina, font=("Segoe UI", 9)).pack(anchor=tk.W)
        tk.Checkbutton(opts_frame, text="Forçar OCR em todas as páginas (use se o texto sair embaralhado)",
                       variable=self.gen_forcar_ocr, font=("Segoe UI", 9)).pack(anchor=tk.W)

        self.gen_btn = tk.Button(
            aba, text="⚡ Converter para Excel (.xlsx)", command=self._gen_converter,
            font=("Segoe UI", 10, "bold"), bg="#1F497D", fg="#FFFFFF",
            activebackground="#16365C", activeforeground="#FFFFFF", padx=16, pady=6
        )
        self.gen_btn.pack(anchor=tk.E, pady=(0, 10))

        self.gen_progress = ttk.Progressbar(aba, mode='indeterminate')
        self.gen_progress.pack(fill=tk.X, pady=(0, 8))

        log_frame = tk.LabelFrame(aba, text=" Progresso ", font=("Segoe UI", 9, "bold"), padx=8, pady=8)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.gen_txt_log = scrolledtext.ScrolledText(log_frame, font=("Consolas", 9), state=tk.DISABLED, bg="#F9FAFB")
        self.gen_txt_log.pack(fill=tk.BOTH, expand=True)

    def _gen_log(self, msg):
        self.gen_txt_log.config(state=tk.NORMAL)
        self.gen_txt_log.insert(tk.END, msg + "\n")
        self.gen_txt_log.see(tk.END)
        self.gen_txt_log.config(state=tk.DISABLED)

    def _gen_selecionar_pdf(self):
        caminho = filedialog.askopenfilename(
            title="Selecione o PDF",
            filetypes=[("Arquivos PDF", "*.pdf"), ("Todos os Arquivos", "*.*")]
        )
        if caminho:
            self.gen_pdf.set(caminho)
            self.gen_excel.set(os.path.splitext(caminho)[0] + ".xlsx")
            self._gen_log(f"PDF carregado: {os.path.basename(caminho)}")

    def _gen_selecionar_excel(self):
        caminho = filedialog.asksaveasfilename(
            title="Salvar Planilha Excel",
            defaultextension=".xlsx",
            filetypes=[("Planilha Excel (*.xlsx)", "*.xlsx")]
        )
        if caminho:
            self.gen_excel.set(caminho)

    def _gen_converter(self):
        pdf_path = self.gen_pdf.get().strip()
        excel_path = self.gen_excel.get().strip()
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showwarning("Atenção", "Por favor, selecione um arquivo PDF existente!")
            return
        if not excel_path:
            messagebox.showwarning("Atenção", "Defina o local onde o Excel será salvo!")
            return

        self.gen_btn.config(state=tk.DISABLED)
        self.gen_progress.start(10)
        self._gen_log("\n--- INICIANDO CONVERSÃO ---")

        def task():
            try:
                paginas = converter_pdf_generico(
                    pdf_path, excel_path,
                    forcar_ocr=self.gen_forcar_ocr.get(),
                    aba_por_pagina=self.gen_aba_por_pagina.get(),
                    callback_log=self._gen_log
                )

                def sucesso():
                    if messagebox.askyesno("Sucesso!", f"{paginas} página(s) convertida(s).\n\nArquivo salvo em:\n{excel_path}\n\nDeseja abrir a planilha agora?"):
                        try:
                            os.startfile(excel_path)
                        except Exception as ex:
                            messagebox.showinfo("Aviso", f"Não foi possível abrir o arquivo automaticamente: {ex}")

                self.root.after(0, sucesso)
            except Exception as e:
                self._gen_log(f"[ERRO] {e}")
                self.root.after(0, lambda: messagebox.showerror("Erro na Conversão", str(e)))
            finally:
                self.gen_btn.config(state=tk.NORMAL)
                self.gen_progress.stop()

        threading.Thread(target=task, daemon=True).start()

    def _log(self, msg):
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state=tk.DISABLED)

    def _selecionar_pdf(self):
        caminho = filedialog.askopenfilename(
            title="Selecione o Pedido de Compra em PDF",
            filetypes=[("Arquivos PDF", "*.pdf"), ("Todos os Arquivos", "*.*")]
        )
        if caminho:
            self.caminho_pdf.set(caminho)
            padrao_excel = os.path.splitext(caminho)[0] + "_Filiais.xlsx"
            self.caminho_excel.set(padrao_excel)
            self._log(f"PDF carregado: {os.path.basename(caminho)}")

    def _selecionar_excel(self):
        caminho = filedialog.asksaveasfilename(
            title="Salvar Planilha Excel",
            defaultextension=".xlsx",
            filetypes=[("Planilha Excel (*.xlsx)", "*.xlsx")]
        )
        if caminho:
            self.caminho_excel.set(caminho)

    def _inspecionar_pagina_1(self):
        pdf_path = self.caminho_pdf.get().strip()
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showwarning("Atenção", "Selecione um arquivo PDF válido primeiro!")
            return

        def task():
            self.btn_inspecionar.config(state=tk.DISABLED)
            self.progress_bar.start(10)
            self._log("--- Inspecionando Página 1 com Reconstrução 2D ---")

            try:
                reader = PdfReader(pdf_path) if HAS_PYPDF else None
                page = reader.pages[0] if (reader and len(reader.pages) > 0) else None
                texto, modo = extrair_texto_pagina(
                    page, pdf_path, 0, forcar_ocr=self.forcar_ocr.get(), callback_log=self._log
                )

                linhas = [l.strip() for l in texto.splitlines() if l.strip()]
                meta = extrair_dados_cabecalho_rodape(linhas)
                prods = extrair_produtos_inteligente(linhas)

                def show_popup():
                    win = tk.Toplevel(self.root)
                    win.title(f"Diagnóstico da Página 1 [{modo}]")
                    win.geometry("780x540")

                    lbl = tk.Label(
                        win,
                        text=f"Filial: {meta['filial_cod']} | Pedido: {meta['ped_compra']} | {meta['razao_social']} | {len(prods)} Produtos Detectados",
                        font=("Segoe UI", 10, "bold"),
                        bg="#1F497D",
                        fg="#FFFFFF",
                        pady=6
                    )
                    lbl.pack(fill=tk.X)

                    txt = scrolledtext.ScrolledText(win, font=("Consolas", 9), padx=8, pady=8)
                    txt.pack(fill=tk.BOTH, expand=True)

                    txt.insert(tk.END, "=== METADADOS IDENTIFICADOS ===\n")
                    for k, v in meta.items():
                        txt.insert(tk.END, f"{k}: {v}\n")

                    txt.insert(tk.END, f"\n=== PRODUTOS IDENTIFICADOS ({len(prods)}) ===\n")
                    for idx, p in enumerate(prods, 1):
                        txt.insert(tk.END, f"{idx:02d}. ERP: {p['codigo_erp']:<8} | EAN: {p['cod_barras']:<14} | UM: {p['um']:<3} | Qtd: {p['quant']:<8} | Preço: {p['preco_unit']:<8} | {p['descricao']}\n")

                    txt.insert(tk.END, "\n=== TEXTO RECONSTRUÍDO PELA LINHA FÍSICA ===\n")
                    txt.insert(tk.END, texto)
                    txt.config(state=tk.DISABLED)

                self.root.after(0, show_popup)

            except Exception as e:
                self._log(f"Erro na inspeção: {e}")
                self.root.after(0, lambda: messagebox.showerror("Erro", str(e)))
            finally:
                self.progress_bar.stop()
                self.btn_inspecionar.config(state=tk.NORMAL)

        threading.Thread(target=task, daemon=True).start()

    def _iniciar_conversao(self):
        pdf_path = self.caminho_pdf.get().strip()
        excel_path = self.caminho_excel.get().strip()

        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showwarning("Atenção", "Por favor, selecione um arquivo PDF existente!")
            return

        if not excel_path:
            messagebox.showwarning("Atenção", "Defina o local onde o Excel será salvo!")
            return

        if self.is_processing:
            return

        self.is_processing = True
        self.btn_converter.config(state=tk.DISABLED)
        self.progress_bar.start(10)
        self._log("\n--- INICIANDO CONVERSÃO BLINDADA ---")

        def task():
            try:
                total_f, avisos = extrair_pdf_para_excel(
                    pdf_path,
                    excel_path,
                    forcar_ocr=self.forcar_ocr.get(),
                    callback_log=self._log
                )

                def sucesso():
                    msg = (
                        f"Conversão concluída com sucesso!\n\n"
                        f"• Filiais geradas: {total_f}\n"
                        f"• Arquivo salvo em:\n{excel_path}\n\n"
                    )
                    if avisos:
                        msg += f"ATENÇÃO: {avisos} ponto(s) a conferir, marcados em vermelho na planilha.\n\n"
                    msg += "Deseja abrir a planilha Excel agora?"
                    resp = messagebox.askyesno("Concluído com avisos" if avisos else "Sucesso!", msg)
                    if resp:
                        try:
                            if os.name == 'nt':
                                os.startfile(excel_path)
                            elif os.uname().sysname == 'Darwin':
                                subprocess.Popen(['open', excel_path])
                            else:
                                subprocess.Popen(['xdg-open', excel_path])
                        except Exception as ex:
                            messagebox.showinfo("Aviso", f"Não foi possível abrir o arquivo automaticamente: {ex}")

                self.root.after(0, sucesso)

            except Exception as e:
                self._log(f"[ERRO CRÍTICO] {e}")
                self.root.after(0, lambda: messagebox.showerror("Erro na Conversão", str(e)))
            finally:
                self.is_processing = False
                self.btn_converter.config(state=tk.NORMAL)
                self.progress_bar.stop()

        threading.Thread(target=task, daemon=True).start()


def main():
    # Modo sem janela: Conversor_de_Pedidos.exe [--qualquer] arquivo.pdf [saida.xlsx]
    args = sys.argv[1:]
    generico = bool(args) and args[0] == "--qualquer"
    if generico:
        args = args[1:]
    if args:
        pdf = args[0]
        sufixo = ".xlsx" if generico else "_Filiais.xlsx"
        saida = args[1] if len(args) > 1 else os.path.splitext(pdf)[0] + sufixo
        converter = converter_pdf_generico if generico else extrair_pdf_para_excel
        # O .exe não tem console: o progresso vai para um .log ao lado da planilha
        with open(os.path.splitext(saida)[0] + ".log", "w", encoding="utf-8") as f:
            def log(msg):
                f.write(msg + "\n")
            try:
                converter(pdf, saida, callback_log=log)
            except Exception as e:
                log(f"[ERRO] {e}")
                sys.exit(1)
        return

    root = tk.Tk()
    app = ConversorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
