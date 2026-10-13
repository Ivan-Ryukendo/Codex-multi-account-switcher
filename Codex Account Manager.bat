@echo off
rem Starts the Codex account manager (codex_switch.py). Needs Python 3.
where py >nul 2>&1 && goto with_py
python "%~dp0codex_switch.py" %*
goto check
:with_py
py -3 "%~dp0codex_switch.py" %*
:check
if errorlevel 1 pause
