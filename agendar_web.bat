@echo off
rem Cria a tarefa ConversorWeb: sobe o site do Conversor ao ligar a maquina. Rode uma vez, como administrador, na pasta do projeto.
rem A tarefa roda com o seu usuario do Windows (as variaveis CONVERSOR_DATABASE_URL e ADMIN_EMAILS sao desse usuario). O Windows pede a senha dele.
cd /d "%~dp0"
schtasks /Create /SC ONSTART /RU "%USERDOMAIN%\%USERNAME%" /RP * /RL HIGHEST /TN "ConversorWeb" /TR "\"%~dp0iniciar_web.bat\"" /F || goto erro
schtasks /Run /TN "ConversorWeb" || goto erro
echo.
echo Tarefa ConversorWeb criada e iniciada. Teste: http://localhost:8225/conversor/status
exit /b 0
:erro
echo FALHOU. Veja a mensagem acima e rode como administrador.
exit /b 1
