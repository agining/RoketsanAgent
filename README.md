# Roketsan DEMO

## Çalıştırmak için
python=>3.11

```bash
pip install -r requirements.txt
uvicorn app.api:app --reload --port 8000
cd frontend
npm ci & npm run dev
```

Arayüz localhost:5173
API arayüz localhost:8000