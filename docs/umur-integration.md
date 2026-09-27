# Umur integration

Base: origin/main a7d7aac. Retains fusion-v3, updated risk engine, draggable panels, settings, timeline, agent Markdown, help and vehicle sprites. Adds on-demand model inference and server-side ElevenLabs speech.

## Setup

1. Create a Python virtual environment and install `requirements-inference.txt` (or `requirements-dev.txt` without image inference dependencies).
2. Copy the root `.env.example` to the root `.env`; configure your LLM provider (key, model and matching base URL) and `ELEVENLABS_API_KEY` locally. Backend and Vite both use this single file; do not create `frontend/.env` files. Only `VITE_` variables are exposed to the browser. Restart both servers after changing settings. Existing process environment variables retain precedence. Secrets are not frontend build settings. Rotate any key previously embedded in browser source.
3. Place `yolo26x_custom.pt` in `model/` or set `INFERENCE_WEIGHTS`. Weight files are not committed. Existing `model/YOLO_eval.py` is retained.
4. Run `python -m uvicorn app.api:app --port 8000`. In `frontend/`, install dependencies with `npm ci` and run `npm run dev`.

## Dataset and assessments

The branch leaves main's data files unchanged. The original local dataset is preserved at `outputs/datasets/pre-integration`; the shared `.env` defaults to main's `data/` directory. This local snapshot is not committed. A fresh team checkout uses main's `data/` by default. To reproduce the earlier dataset, copy the backed-up dataset into a separate directory and configure `DATA_DIR`.

Fusion-v3 discards incompatible old assessments from active use. Old files are retained locally; producing a new assessment updates vehicle feedback.

## Features

- `POST /api/inference/detect` accepts JPEG/PNG bytes without altering the dataset; `/api/inference/status` reports availability. See `inference-api.md`.
- Voice alerts keep main's queue/chime system. `/api/voice/synthesize` calls ElevenLabs using the server key. Browser audio is cached locally and browser speech is used on provider/playback failure.
- Main's font scale settings replace the older blanket CSS zoom. Panel layout and map controls remain from main.

Local environment files and Python bytecode are no longer tracked; their files are retained on disk. The pre-integration feature stash is retained for rollback. No merge into main is performed by this integration.

Main integration: retains the guided tutorial, updated map and agent prompt, and demo PDF endpoint. Configure `VITE_DEMO_REPORT` in the root `.env`; default false generates live reports.
