import io
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app import inference


def client():
    app = FastAPI()
    app.include_router(inference.router)
    return TestClient(app)


def png():
    stream = io.BytesIO()
    Image.new('RGB', (32, 24)).save(stream, format='PNG')
    return stream.getvalue()


def test_api_returns_real_adapter_output_without_dataset_writes(monkeypatch, tmp_path):
    svc = inference.InferenceService(tmp_path / 'model.pt')
    calls = []
    class Tensor:
        def __init__(self, values): self.values = values
        def tolist(self): return self.values
    class Model:
        def predict(self, **kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(names={0: 'automobile'}, boxes=SimpleNamespace(
                xyxy=Tensor([[2, 3, 12, 15]]), conf=Tensor([0.9]), cls=Tensor([0])))]
    svc._model = Model()
    monkeypatch.setattr(inference, 'inference_service', svc)
    response = client().post('/api/inference/detect?confidence=0.4', content=png(), headers={'Content-Type': 'image/png'})
    assert response.status_code == 200
    assert response.json()['detections'] == [{'label': 'car', 'confidence': 0.9, 'bbox': [2, 3, 10, 12]}]
    assert calls[0]['conf'] == 0.4
    assert calls[0]['save'] is False
    assert list(tmp_path.iterdir()) == []


def test_validation_and_status_do_not_load_model(monkeypatch, tmp_path):
    svc = inference.InferenceService(tmp_path / 'missing.pt')
    monkeypatch.setattr(inference, 'inference_service', svc)
    c = client()
    assert c.get('/api/inference/status').json()['loaded'] is False
    assert c.post('/api/inference/detect', content=b'bad', headers={'Content-Type': 'image/png'}).status_code == 422
    assert c.post('/api/inference/detect', content=png(), headers={'Content-Type': 'application/json'}).status_code == 415
    assert c.post('/api/inference/detect?confidence=2', content=png(), headers={'Content-Type': 'image/png'}).status_code == 422
    assert c.post('/api/inference/detect', content=png(), headers={'Content-Type': 'image/png'}).status_code == 503
    assert svc._model is None


def test_busy_and_upload_limits(monkeypatch, tmp_path):
    svc = inference.InferenceService(tmp_path / 'missing.pt')
    monkeypatch.setattr(inference, 'inference_service', svc)
    c = client()
    svc._lock.acquire()
    try:
        assert c.post('/api/inference/detect', content=png(), headers={'Content-Type': 'image/png'}).status_code == 429
    finally:
        svc._lock.release()
    monkeypatch.setattr(inference, 'MAX_BYTES', 10)
    assert c.post('/api/inference/detect', content=png(), headers={'Content-Type': 'image/png'}).status_code == 413
