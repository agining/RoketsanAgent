# Roketsan DEMO


## Çalıştırmak için
python=>3.11 
nodejs

```bash
pip install -r requirements.txt
uvicorn app.api:app --reload --port 8000
cd frontend
npm ci 
npm run dev
```

Arayüz localhost:5173
API arayüz localhost:8000

Görüntüden araç tespiti: [Inference API](docs/inference-api.md). Endpoint: `POST /api/inference/detect`; model durumu: `GET /api/inference/status`.

```bash
python run_pipeline.py                          # deterministik analiz → outputs/analysis.json
python run_pipeline.py --agent --min-risk ORTA  # riskli kareler için ajan → outputs/assessments.json
python run_pipeline.py --chat "T0122 neden yüksek riskli?"
uvicorn app.api:app --reload --port 8000        # React için API, dokümantasyon: /docs
```
