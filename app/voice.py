"""Server-side speech synthesis gateway; provider credentials stay on the server."""
import os
import httpx
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, ConfigDict

router = APIRouter(prefix='/api/voice', tags=['Voice Alerts'])


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')
    text: str = Field(min_length=1, max_length=1500)
    voice_id: str = Field(default='EXAVITQu4vr4xnSDxMaL', pattern=r'^[a-zA-Z0-9]{1,64}$')
    model_id: str = Field(default='eleven_multilingual_v2', pattern=r'^[a-zA-Z0-9_]{1,64}$')


@router.post('/synthesize', responses={200: {'content': {'audio/mpeg': {}}}})
async def synthesize(body: SpeechRequest):
    key = os.getenv('ELEVENLABS_API_KEY')
    if not key:
        raise HTTPException(503, 'Speech provider is not configured.')
    if not body.text.strip():
        raise HTTPException(422, 'Speech text is empty.')
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            result = await client.post(
                f'https://api.elevenlabs.io/v1/text-to-speech/{body.voice_id}',
                headers={'xi-api-key': key, 'Accept': 'audio/mpeg'},
                json={'text': body.text, 'model_id': body.model_id,
                      'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}},
            )
        if not result.is_success:
            raise HTTPException(502, 'Speech provider could not complete the request.')
        return Response(content=result.content, media_type='audio/mpeg', headers={'Cache-Control': 'no-store'})
    except httpx.TimeoutException:
        raise HTTPException(504, 'Speech provider timed out.') from None
    except httpx.HTTPError:
        raise HTTPException(502, 'Speech provider is unavailable.') from None
