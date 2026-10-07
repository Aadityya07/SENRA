@echo off
REM One-time setup for SENRA (Phase 1). Requires Python 3.10+, Node 18+ and Ollama.
cd /d "%~dp0"

echo [1/4] Creating Python virtual environment...
if not exist backend\.venv python -m venv backend\.venv
call backend\.venv\Scripts\python -m pip install --upgrade pip
call backend\.venv\Scripts\python -m pip install -r backend\requirements.txt || goto :error

echo [2/4] Downloading the GoEmotions text-emotion model...
call backend\.venv\Scripts\python -c "from transformers import pipeline; pipeline('text-classification', model='SamLowe/roberta-base-go_emotions', top_k=None)" || goto :error

echo [3/4] Pulling Gemma 3n E2B (2B effective) into Ollama...
ollama pull gemma3n:e2b || goto :error

echo [4/4] Installing frontend dependencies...
cd frontend
call npm install || goto :error
cd ..

echo.
echo Setup complete. Run start.bat to launch SENRA.
exit /b 0

:error
echo.
echo Setup failed. See the messages above.
exit /b 1
