@echo off
rem Reinicia o site do Conversor: encerra o que escuta na porta 8225 e executa a tarefa ConversorWeb do Agendador de Tarefas.
rem Uso: reiniciar_web.bat [nome-da-tarefa]   (padrao: ConversorWeb)
set TAREFA=%~1
if "%TAREFA%"=="" set TAREFA=ConversorWeb
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8225 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
schtasks /End /TN "%TAREFA%" >nul 2>&1
timeout /t 2 /nobreak >nul
schtasks /Run /TN "%TAREFA%" || goto erro
echo Reiniciado (Conversor na porta 8225). Teste: http://localhost:8225/conversor/status
exit /b 0
:erro
echo FALHOU. Confira se a tarefa existe (agendar_web.bat) e rode como administrador.
exit /b 1
