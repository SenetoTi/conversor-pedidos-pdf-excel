@echo off
rem Primeira instalacao do site do Conversor. Rodar uma vez, na pasta do projeto. Requer Python 3.13 no PATH.
cd /d "%~dp0"
python -m venv .venv || goto erro
call .venv\Scripts\activate.bat
pip install -r requirements-web.txt || goto erro
echo Instalado. Defina CONVERSOR_DATABASE_URL e ADMIN_EMAILS (veja docs\INSTALACAO-WEB.md) e rode iniciar_web.bat.
exit /b 0
:erro
echo FALHOU. Veja a mensagem acima.
exit /b 1
