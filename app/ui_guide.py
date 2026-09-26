"""Arayüz yardımı: "Filtre nasıl yapılır?" gibi bir soruyu vurgulanacak arayüz öğelerinin sırasına çevirir.

  POST /api/ui-guide   ← {"question": "Filtre nasıl yapılır"}
                       → {"question", "message", "steps": [{"id", "instruction", "opens"}], "dropped": [...]}

Akış: STT metni + app/ui_guide.md (kılavuz) → LLM → `parse_guide_response` → sıralı adımlar. Arayüz her adımda
`[data-guide="<id>"]` öğesini vurgular; kullanıcı öğeye tıkladıkça bir sonrakine geçer.

Geçerli ID'ler ve "açtığı alan" bilgisi kılavuzdaki katalog tablolarından okunur (tek kaynak ui_guide.md).
LLM çıktısı güvenilmez kabul edilir: kod bloğu / düşünme etiketi / serbest metin içinden JSON çıkarılır, katalogda
olmayan ID'ler atılır (`dropped`), art arda tekrarlar birleştirilir, en fazla MAX_STEPS adım döner. JSON hiç
bulunamazsa metinde geçen katalog ID'leri geçiş sırasıyla kullanılır.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .config import settings

log = logging.getLogger(__name__)

GUIDE_PATH = Path(__file__).with_name("ui_guide.md")
MAX_STEPS = 8

_ROW_RE = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$", re.MULTILINE)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_ID_KEYS = ("id", "element", "element_id", "target", "guide_id", "data-guide")
_TEXT_KEYS = ("instruction", "text", "description", "tip", "hint", "message")


@dataclass(frozen=True)
class CatalogItem:
    id: str
    label: str
    purpose: str
    opens: str | None


@dataclass
class GuideStep:
    id: str
    instruction: str
    opens: str | None = None


@dataclass
class GuidePlan:
    steps: list[GuideStep] = field(default_factory=list)
    message: str = ""
    dropped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ kılavuz
@lru_cache(maxsize=1)
def load_guide() -> tuple[str, dict[str, CatalogItem]]:
    """Kılavuz metni + katalog (ID → öğe). Tablo satırı: | `id` | ad | ne işe yarar | açtığı alan |"""
    text = GUIDE_PATH.read_text(encoding="utf-8")
    catalog: dict[str, CatalogItem] = {}
    for m in _ROW_RE.finditer(text):
        opens = m.group(4).strip().strip("`").strip()
        catalog[m.group(1)] = CatalogItem(m.group(1), m.group(2).strip(), m.group(3).strip(),
                                          None if opens in ("", "—", "-") else opens)
    unknown = {c.opens for c in catalog.values() if c.opens and c.opens not in catalog}
    if unknown:
        log.warning("ui_guide.md: 'açtığı alan' katalogda yok: %s", sorted(unknown))
    return text, catalog


def build_messages(question: str) -> list[tuple[str, str]]:
    guide, _ = load_guide()
    system = ("Bir operasyon arayüzünün kullanım asistanısın. Kullanıcının sorusunu, aşağıdaki kılavuzdaki "
              "arayüz öğelerinden sıralı bir vurgulama planına çevir. Yalnızca kılavuzun 'Yanıt biçimi' "
              "bölümündeki JSON nesnesini döndür.\n\n=== KILAVUZ ===\n" + guide)
    return [("system", system), ("human", f"Kullanıcının sorusu (konuşmadan metne çevrildi): {question}")]


# ------------------------------------------------------------------ LLM çıktısını ayrıştırma
def _normalize_id(value: object) -> str:
    s = str(value).strip().strip("`'\"").strip()
    s = re.sub(r"^\[?data-guide\s*=\s*[\"']?", "", s, flags=re.IGNORECASE).rstrip("\"']")
    return s.lower().replace("_", "-").replace(" ", "-")


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
    """(adım listesi, mesaj) — adım içeren ilk JSON değeri."""
    for value in _json_candidates(text):
        if isinstance(value, dict):
            steps = next((value[k] for k in ("steps", "highlights", "sequence", "elements") if isinstance(value.get(k), list)), None)
            if steps is not None:
                msg = value.get("message") or value.get("summary") or value.get("answer") or ""
                return steps, str(msg).strip()
        elif isinstance(value, list) and value and all(isinstance(v, (dict, str)) for v in value):
            return value, ""
    return None


def parse_guide_response(text: str, catalog: dict[str, CatalogItem] | None = None) -> GuidePlan:
    """LLM yanıtını sıralı, doğrulanmış vurgulama adımlarına çevirir."""
    if catalog is None:
        catalog = load_guide()[1]
    text = _THINK_RE.sub("", text or "").strip()
    plan = GuidePlan()

    extracted = _extract_plan_json(text)
    if extracted is not None:
        raw_steps, plan.message = extracted
    else:  # JSON yok → metinde geçen katalog ID'leri, geçiş sırasıyla
        found = sorted(((m.start(), cid) for cid in catalog
                        for m in re.finditer(rf"(?<![a-z0-9-]){re.escape(cid)}(?![a-z0-9-])", text)))
        raw_steps = [cid for _, cid in found]
        plan.message = "" if raw_steps else text[:300]

    for raw in raw_steps:
        if isinstance(raw, dict):
            sid = next((raw[k] for k in _ID_KEYS if raw.get(k)), "")
            instruction = next((str(raw[k]).strip() for k in _TEXT_KEYS if raw.get(k)), "")
        else:
            sid, instruction = raw, ""
        sid = _normalize_id(sid)
        if sid not in catalog:
            if sid:
                plan.dropped.append(sid)
            continue
        if plan.steps and plan.steps[-1].id == sid:
            continue
        item = catalog[sid]
        plan.steps.append(GuideStep(sid, instruction or f"{item.label}: {item.purpose}", item.opens))
        if len(plan.steps) == MAX_STEPS:
            break
    return plan


# ------------------------------------------------------------------ REST
router = APIRouter(prefix="/api/ui-guide", tags=["Arayüz yardımı"])


class GuideRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="Kullanıcının sorusu (STT çıktısı)")


@lru_cache(maxsize=1)
def _llm():
    from .agent import build_llm
    return build_llm()


@router.post("")
async def ui_guide(body: GuideRequest):
    if not settings.llm_enabled:
        raise HTTPException(503, "LLM devre dışı (OPENAI_API_KEY tanımlı değil); arayüz yardımı kullanılamıyor.")
    question = body.question.strip()
    try:
        reply = await _llm().ainvoke(build_messages(question))
    except Exception as e:
        log.exception("Arayüz yardımı LLM çağrısı başarısız")
        raise HTTPException(502, f"LLM çağrısı başarısız: {e}") from e
    content = reply.content if isinstance(reply.content, str) else "".join(
        part.get("text", "") if isinstance(part, dict) else str(part) for part in reply.content)
    plan = parse_guide_response(content)
    if plan.dropped:
        log.info("Arayüz yardımı: katalogda olmayan ID'ler atıldı: %s", plan.dropped)
    if not plan.steps and not plan.message:
        plan.message = "Bu soru için vurgulanacak bir arayüz öğesi bulunamadı."
    return {"question": question, **plan.to_dict()}
