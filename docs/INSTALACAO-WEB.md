# Instalação do site do Conversor (Windows)

Versão: 1.0 (26/11/2026). O site do Conversor roda na mesma máquina do Conciliador, escuta só em `127.0.0.1:8225` e é entregue pelo Caddy na porta 8215, com o login do Conciliador.

**Status:** o código do site foi testado no Linux (`python test_web.py`). **Verificado no Windows em 26/11/2026:** banco, variáveis, site pela porta 8215 com login, cadastro em Aplicativos, importação da base com os arquivos reais e conversão de um pedido. **Não verificado no Windows:** subir sozinho depois de reiniciar a máquina, usuário sem acesso (403), usuário fora de `ADMIN_EMAILS`, `atualizar_web.bat` e `reiniciar_web.bat`. Os itens que dependem do Caddy dependem também do guia do Conciliador (`07-INSTALACAO-LOCAL.md`, passo 7-A).

No PowerShell, rode scripts da pasta atual com `.\` na frente (ex.: `.\instalar_web.bat`).

## 1. Programas
Os mesmos do Conciliador, que já estão na máquina: Python 3.13 (com "Add python.exe to PATH"), Git para Windows e PostgreSQL. Não precisa instalar nada novo. O Caddy também já é o do Conciliador.

## 2. Banco
No pgAdmin, entre com o usuário `postgres`, abra Tools > Query Tool e rode uma linha de cada vez (troque `SUASENHA`; evite aspas e `@` na senha, e use uma senha diferente da do Conciliador):
```
CREATE USER conversor WITH PASSWORD 'SUASENHA';
CREATE DATABASE conversor OWNER conversor;
```
O banco `conversor` é separado do `conciliador`. As tabelas são criadas na primeira importação (passo 7).

## 3. Código
A pasta do repositório no PC é `C:\repositorios\ConvertorPdf`. Se ainda não existir:
```
git clone https://github.com/SenetoTi/conversor-pedidos-pdf-excel.git C:\repositorios\ConvertorPdf
```
O repositório é público e não guarda dados da empresa. Depois:
```
cd C:\repositorios\ConvertorPdf
.\instalar_web.bat
```
Isso cria a pasta `.venv` e instala as bibliotecas (a instalação do OCR pode demorar alguns minutos).

## 4. Variáveis de ambiente (nunca no repositório)
Em Configurações do Windows > Variáveis de ambiente (do usuário que roda o sistema), crie:
- `CONVERSOR_DATABASE_URL` = `postgresql://conversor:SUASENHA@localhost:5432/conversor`

**Atenção:** não use o nome `DATABASE_URL`. Ele já é do Conciliador (aponta para o banco `conciliador`) e não deve ser alterado. O Conversor só lê `CONVERSOR_DATABASE_URL`, para nunca escrever no banco errado.

- `ADMIN_EMAILS` = os e-mails de quem pode atualizar a base, separados por vírgula (ex.: `guilherme@empresa.com`). Use o mesmo e-mail do login no Conciliador.

Clique OK na janela de variáveis e também em Propriedades do Sistema, senão o Windows não grava. Feche o PowerShell e abra um novo. Para conferir: `echo $env:CONVERSOR_DATABASE_URL`.

Não precisa de `SECRET_KEY` nem de pasta de arquivos: o login é do Conciliador e os PDFs e Excel ficam só em pasta temporária, apagados depois do download.

## 5. Testar o site
```
.\iniciar_web.bat
```
No navegador da própria máquina, abra `http://localhost:8225/conversor/status`: deve aparecer `{"ok":true}`. Feche a janela do site (Ctrl+C) antes do passo 6.

`http://localhost:8225/conversor/` direto dá "Acesso só pela Central de Gestão" (403). Isso é o esperado: o e-mail só chega pelo Caddy. Para abrir o site, use sempre a porta 8215.

## 6. Subir sozinho ao ligar
**Opção A, pelo script.** Num terminal **como administrador** (PowerShell: botão direito > Executar como administrador; confira com `net session`, que não deve dar "Acesso negado"), na pasta do projeto:
```
.\agendar_web.bat
```
Ele cria a tarefa `ConversorWeb` (ao ligar a máquina, com o seu usuário do Windows) e pede a senha desse usuário. A tarefa usa o seu usuário porque as variáveis do passo 4 são dele. Se aparecer "ERRO: Acesso negado" mesmo como administrador, a conta pode não ter senha ou a senha digitada não é a da conta (em conta Microsoft vale a senha da conta, não o PIN): use a opção B.

**Opção B, pela tela do Agendador de Tarefas** (a mesma do Conciliador, validada no Windows):
1. Agendador de Tarefas > Criar Tarefa.
2. Nome: `ConversorWeb`. Marque "Executar estando o usuário conectado ou não" e "Executar com privilégios mais altos".
3. Gatilho: "Ao iniciar o computador".
4. Ação: iniciar programa `C:\repositorios\ConvertorPdf\iniciar_web.bat`, com "Iniciar em" `C:\repositorios\ConvertorPdf`.
5. Usuário: o mesmo da tarefa do Conciliador.

Depois confira `http://localhost:8215/conversor/` (a `localhost:8225` direto dá 403, o que é o esperado). Reinicie a máquina uma vez para ver se sobe sozinho (ainda não verificado).

## 7. Primeira importação da base
No terminal, na pasta do projeto, use o Python do próprio `.venv` (não precisa ativar o ambiente; em muitos PCs o PowerShell bloqueia o `Activate.ps1`):
```
.\.venv\Scripts\python.exe -m base criar-schema
.\.venv\Scripts\python.exe -m base validar fiscal "C:\caminho\AtualiProdutos.csv"
.\.venv\Scripts\python.exe -m base validar precos "C:\caminho\todos os produtos.xlsx"
.\.venv\Scripts\python.exe -m base validar tipi "C:\caminho\tipi.docx"
```
Troque `C:\caminho\` pela pasta dos arquivos e confira o nome exato de cada um (aspas por causa dos espaços). Se o `criar-schema` avisar que falta `CONVERSOR_DATABASE_URL`, abra um PowerShell novo (passo 4).

O `validar` só lê o arquivo e mostra os avisos, sem usar o banco. Os números esperados com os arquivos de novembro: fiscal 50.395 linhas, preços 47.621, TIPI 10.516 (validado no Windows em 26/11/2026). Se algum aviso parecer estranho, não importe e avise antes.

Depois, pela tela: abra `http://IP-DA-MAQUINA:8215/conversor/base` (só aparece para os e-mails de `ADMIN_EMAILS`) e envie os três arquivos. O quadro mostra as linhas e a data de cada um. Os arquivos são do Linear e do ERP: não os coloque no repositório.

**Cada envio troca a parte da base daquele arquivo, não acrescenta.** Envie sempre a lista completa exportada do ERP, nunca só os produtos novos: o que não estiver no arquivo sai da base e vira CONFERIR nos pedidos. Se o arquivo vier com erro, o envio é recusado e a base fica como estava.

## 8. Cadastrar na Central de Gestão
No Conciliador, entre como admin: Configurações > Aplicativos. Cadastre:
- Nome: `Conversor de Pedidos` (o Caddy usa o apelido `conversor-de-pedidos`, que sai desse nome; se mudar o nome, o apelido muda e o Caddyfile precisa acompanhar)
- Caminho: `/conversor/`

Depois libere o aplicativo para os usuários que vão usar (tela Usuários). Admin vê todos. O cartão aparece na tela inicial (`http://IP-DA-MAQUINA:8215/`).

## 9. Firewall
Só a porta 8215 aberta na rede interna. As portas 8225 (Conversor), 8210 (Conciliador) e 5432 (PostgreSQL) ficam fechadas: escutam só em `127.0.0.1`. Se for usar VPN, a regra da 8215 precisa incluir a faixa da VPN (a faixa ainda não foi definida).

## 10. Testar de ponta a ponta
1. De outro computador, abra `http://IP-DA-MAQUINA:8215/` e entre. O cartão "Conversor de Pedidos" deve aparecer.
2. Abra o Conversor. Aba Pedido de compra: envie um PDF, preencha a Fidelidade da NF e baixe o Excel. Confira as colunas depois do Total: Preço de venda, NCM, CEST, IPI (%), Qtd. embalagem, Valor Tabela comprado, Fidelidade da NF e Conferência.
3. Com um usuário sem acesso ao aplicativo: `http://IP-DA-MAQUINA:8215/conversor/` deve dar "Sem acesso a este aplicativo" (403).
4. Com um usuário que não está em `ADMIN_EMAILS`: o botão Atualizar base não aparece e `/conversor/base` dá 403.

## 11. Atualizar e reiniciar
```
.\atualizar_web.bat
.\reiniciar_web.bat
```
O `reiniciar_web.bat` encerra o que está na porta 8225 e roda a tarefa `ConversorWeb`. Se der erro, abra o terminal como administrador.

## 12. Desligar o .exe
Só depois do passo 10 dar certo e da equipe usar o site por alguns dias. O `.exe` (`Conversor_de_Pedidos.exe`, de `gerar_exe.bat`) não é mais necessário: avise os usuários, apague o atalho e guarde o último `.exe` por segurança. O código do `.exe` continua no repositório e o `atualizar.bat` antigo continua servindo a ele.

## Pendente
- Backup do banco `conversor`. A base pode ser recriada reimportando os três arquivos, mas o histórico de importações se perde.
- VPN e a regra de firewall dela.
