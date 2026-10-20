@echo off
rem ===========================================================================
rem  Transcriere locala - instalare cu un singur dublu-click.
rem  Nu cere drepturi de administrator si nu pune intrebari tehnice.
rem ===========================================================================
chcp 65001 >nul
setlocal EnableDelayedExpansion
title Transcriere locala - instalare

set "RADACINA=%~dp0"
set "INTRARE=%RADACINA%pornire.py"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo.
        echo   Nu am gasit Python pe acest calculator.
        echo.
        echo   Programul are nevoie de Python ca sa poata instala restul componentelor.
        echo   Instaleaza Python 3.12 de pe https://www.python.org/downloads/windows/
        echo   bifeaza "Add python.exe to PATH" la instalare, apoi ruleaza din nou acest fisier.
        echo.
        pause
        exit /b 1
    )
)

%PY% "%INTRARE%" --instaleaza --interfata %*
set "COD=%errorlevel%"
if not "%COD%"=="0" (
    echo.
    echo   Instalarea nu s-a terminat. Jurnalul este in:
    echo   %%LOCALAPPDATA%%\TranscriereLocala\jurnale\instalare.log
    echo.
    pause
)
endlocal
exit /b %COD%
