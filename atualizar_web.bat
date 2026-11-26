@echo off
rem Baixa a versao nova do codigo e atualiza as dependencias do site. Depois rode reiniciar_web.bat.
cd /d "%~dp0"
git pull origin main || goto erro
call .venv\Scripts\activate.bat
pip install -r requirements-web.txt || goto erro
echo Atualizado. Rode reiniciar_web.bat (ou reinicie a maquina).
exit /b 0
:erro
echo FALHOU. Veja a mensagem acima.
exit /b 1
