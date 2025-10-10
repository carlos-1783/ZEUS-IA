@echo off
REM Activar entorno virtual y lanzar backend
start cmd /k "cd /d %~dp0 && call venv\Scripts\activate && pip install -r requirements.txt && uvicorn main:app --reload --host 0.0.0.0 --port 8000"

REM Lanzar frontend en otra ventana
start cmd /k "cd /d ..\frontend && npm install && npm run dev"

pause