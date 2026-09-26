import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import voice


def client():
    app = FastAPI()
    app.include_router(voice.router)
    return TestClient(app)


def test_unconfigured_voice_returns_service_unavailable(monkeypatch):
    monkeypatch.delenv('ELEVENLABS_API_KEY', raising=False)
    assert client().post('/api/voice/synthesize', json={'text': 'Merhaba'}).status_code == 503


def test_proxy_keeps_key_server_side_and_returns_audio(monkeypatch):
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'test-only')
    calls = []
    class Upstream:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return httpx.Response(200, content=b'audio')
    monkeypatch.setattr(voice.httpx, 'AsyncClient', lambda **kwargs: Upstream())
    response = client().post('/api/voice/synthesize', json={'text': 'Merhaba'})
    assert response.status_code == 200
    assert response.content == b'audio'
    assert response.headers['content-type'] == 'audio/mpeg'
    assert calls[0][1]['headers']['xi-api-key'] == 'test-only'
    assert 'test-only' not in response.text


def test_provider_error_does_not_expose_upstream_response(monkeypatch):
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'test-only')
    class Upstream:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return httpx.Response(401, text='private-provider-details')
    monkeypatch.setattr(voice.httpx, 'AsyncClient', lambda **kwargs: Upstream())
    response = client().post('/api/voice/synthesize', json={'text': 'Merhaba'})
    assert response.status_code == 502
    assert 'private-provider-details' not in response.text
    assert client().post('/api/voice/synthesize', json={'text': 'x' * 1501}).status_code == 422
