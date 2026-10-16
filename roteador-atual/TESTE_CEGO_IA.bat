@echo off
setlocal
title Rotrix L-1000 - teste as cegas das IAs na TC
color 0F
rem ==========================================================================
rem  A mesma folha de TC em tres IAs (Sol padrao, Sol raciocinio baixo, Luna),
rem  sem dizer qual e qual. 20 ditados INVENTADOS - nenhum laudo real.
rem  Mostra o custo estimado e pergunta antes de gastar.
rem  O resultado fica em laudo-router\logs_teste\teste_cego_<data>\
rem ==========================================================================
set "RAIZ=%~dp0"
if not exist "%RAIZ%teste_cego_ia.py" echo [PAROU] teste_cego_ia.py nao esta nesta pasta. Rode o ATUALIZAR_ROTRIX antes. & goto :fim
set "PY="
for %%V in (313 312 311 310) do if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY echo [PAROU] Python nao encontrado. & goto :fim
cd /d "%RAIZ%"
set PYTHONIOENCODING=utf-8
"%PY%" teste_cego_ia.py %*
:fim
echo.
pause
endlocal
