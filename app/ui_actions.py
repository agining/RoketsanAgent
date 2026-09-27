"""Sesli komut → arayüz eylemleri: "Sadece otobüsleri göster" gibi bir komutu arayüzde uygulanacak eylem listesine çevirir.

  POST /api/ui-command   ← {"command": "Sadece otobüsleri göster", "context": {...arayüz durumu ve seçenekler...}}
                         → {"command", "message", "actions": [{"action", "params"}], "dropped": [...]}

Akış: STT metni + arayüz durumu (frontend gönderir: filtre seçenekleri, iz kimlikleri, açık paneller …) +
app/ui_actions.md (eylem kataloğu) → LLM → `parse_action_response` → sıralı eylemler. Arayüz eylemleri mevcut
fonksiyonlarıyla (filtre, katman, panel, oynatma, ayar …) uygular; parametreleri ayrıca kendisi doğrular.

Geçerli eylem adları kılavuzdaki katalog tablolarından okunur (tek kaynak ui_actions.md). LLM çıktısı güvenilmez
kabul edilir: kod bloğu / düşünme etiketi / serbest metin içinden JSON çıkarılır, katalogda olmayan eylemler atılır
(`dropped`), en fazla MAX_ACTIONS eylem döner.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .config import settings

log = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).with_name("ui_actions.md")
MAX_ACTIONS = 12
MAX_CONTEXT_CHARS = 40_000

_ROW_RE = re.compile(r"^\|\s*`([a-z_]+)`\s*\|([^|]*)\|([^|]*)\|\s*$", re.MULTILINE)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_NAME_KEYS = ("action", "name", "type", "function", "tool")
_PARAM_KEYS = ("params", "parameters", "args", "arguments", "input")


@dataclass(frozen=True)
class CatalogAction:
    name: str
    params: str
    purpose: str


@dataclass
class UiAction:
    action: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionPlan:
    actions: list[UiAction] = field(default_factory=list)
    message: str = ""
    dropped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ katalog
@lru_cache(maxsize=1)
def load_catalog() -> tuple[str, dict[str, CatalogAction]]:
    """Katalog metni + eylemler (ad → eylem). Tablo satırı: | `eylem` | parametreler | ne yapar |"""
    text = CATALOG_PATH.read_text(encoding="utf-8")
    catalog = {m.group(1): CatalogAction(m.group(1), m.group(2).strip(), m.group(3).strip())
               for m in _ROW_RE.finditer(text)}
    return text, catalog


def build_messages(command: str, context: dict | None) -> list[tuple[str, str]]:
    guide, _ = load_catalog()
    system = ("Bir operasyon arayüzünü kullanıcının sesli komutuyla kullanan asistansın. Komutu, aşağıdaki katalogdaki "
              "eylemlerden sıralı bir eylem listesine çevir; eylemler arayüzde hemen uygulanacak. Yalnızca katalogdaki "
              "'Yanıt biçimi' bölümündeki JSON nesnesini döndür.\n\n=== EYLEM KATALOĞU ===\n" + guide)
    ctx = json.dumps(context or {}, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(ctx) > MAX_CONTEXT_CHARS:
        ctx = ctx[:MAX_CONTEXT_CHARS] + "…(kısaltıldı)"
    human = f"Arayüz durumu (bağlam):\n{ctx}\n\nKullanıcının komutu (konuşmadan metne çevrildi): {command}"
    return [("system", system), ("human", human)]


# ------------------------------------------------------------------ LLM çıktısını ayrıştırma
def _normalize_name(value: object) -> str:
    s = str(value).strip().strip("`'\"").strip()
    return re.sub(r"[\s-]+", "_", s).lower()


def _json_candidates(text: str):
    """Metindeki JSON değerlerini olası sırayla verir: kod blokları, sonra her { / [ konumundan ilk geçerli değer."""
    decoder = json.JSONDecoder()
    for block in _FENCE_RE.findall(text):
        try:
            yield json.loads(block.strip())
        except json.JSONDecodeError:
            pass
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                yield decoder.raw_decode(text, i)[0]
            except json.JSONDecodeError:
                continue


def _extract_plan_json(text: str) -> tuple[list, str] | None:
    """(eylem listesi, mesaj) — eylem içeren ilk JSON değeri."""
    for value in _json_candidates(text):
        if isinstance(value, dict):
            actions = next((value[k] for k in ("actions", "steps", "commands", "tool_calls") if isinstance(value.get(k), list)), None)
            if actions is not None:
                msg = value.get("message") or value.get("summary") or value.get("answer") or ""
                return actions, str(msg).strip()
            if any(k in value for k in _NAME_KEYS):      # tek eylem nesnesi
                return [value], ""
        elif isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            return value, ""
    return None


def _params_of(raw: dict) -> dict[str, Any]:
    params = next((raw[k] for k in _PARAM_KEYS if k in raw), None)
    if isinstance(params, str):                          # OpenAI tarzı "arguments": "{...}"
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            params = None
    if isinstance(params, dict):
        return params
    # parametreler düz yazılmış olabilir: {"action": "set_theme", "mode": "light"}
    return {k: v for k, v in raw.items() if k not in _NAME_KEYS and k not in _PARAM_KEYS}


def parse_action_response(text: str, catalog: dict[str, CatalogAction] | None = None) -> ActionPlan:
    """LLM yanıtını sıralı, katalogla doğrulanmış arayüz eylemlerine çevirir."""
    if catalog is None:
        catalog = load_catalog()[1]
    text = _THINK_RE.sub("", text or "").strip()
    plan = ActionPlan()

    extracted = _extract_plan_json(text)
    if extracted is None:
        plan.message = text[:300]
        return plan
    raw_actions, plan.message = extracted

    for raw in raw_actions:
        if not isinstance(raw, dict):
            continue
        name_value = next((raw[k] for k in _NAME_KEYS if raw.get(k)), "")
        if isinstance(name_value, dict):                 # {"function": {"name": ..., "arguments": ...}}
            raw, name_value = name_value, name_value.get("name", "")
        name = _normalize_name(name_value)
        if name not in catalog:
            if name:
                plan.dropped.append(name)
            continue
        plan.actions.append(UiAction(name, _params_of(raw)))
        if len(plan.actions) == MAX_ACTIONS:
            break
    return plan


# ------------------------------------------------------------------ REST
router = APIRouter(prefix="/api/ui-command", tags=["Sesli komut"])


class CommandRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=500, description="Kullanıcının komutu (STT çıktısı)")
    context: dict[str, Any] | None = Field(None, description="Arayüz durumu: seçenekler, iz kimlikleri, açık paneller")


@lru_cache(maxsize=1)
def _llm():
    from .agent import build_llm
    return build_llm()


@router.post("")
async def ui_command(body: CommandRequest):
    if not settings.llm_enabled:
        raise HTTPException(503, "LLM devre dışı (OPENAI_API_KEY tanımlı değil); sesli komut kullanılamıyor.")
    command = body.command.strip()
    try:
        reply = await _llm().ainvoke(build_messages(command, body.context))
    except Exception as e:
        log.exception("Sesli komut LLM çağrısı başarısız")
        raise HTTPException(502, f"LLM çağrısı başarısız: {e}") from e
    content = reply.content if isinstance(reply.content, str) else "".join(
        part.get("text", "") if isinstance(part, dict) else str(part) for part in reply.content)
    plan = parse_action_response(content)
    if plan.dropped:
        log.info("Sesli komut: katalogda olmayan eylemler atıldı: %s", plan.dropped)
    if not plan.actions and not plan.message:
        plan.message = "Bu komut için uygulanacak bir arayüz eylemi bulunamadı."
    return {"command": command, **plan.to_dict()}
