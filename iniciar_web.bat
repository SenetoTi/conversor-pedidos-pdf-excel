@echo off
rem Sobe o site do Conversor. O Agendador de Tarefas (tarefa ConversorWeb) chama este arquivo ao ligar a maquina.
rem Escuta so na propria maquina, em 127.0.0.1:8225. Quem atende a rede e o Caddy, na porta 8215.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m uvicorn web.app:app --host 127.0.0.1 --port 8225 --proxy-headers --forwarded-allow-ips 127.0.0.1
