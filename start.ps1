Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\Acer\ZEUS-IA\backend; venv\Scripts\activate; uvicorn app.api:app --host 0.0.0.0 --port 8000"
Start-Process http://localhost:8000
