"""Arayüzsüz çalıştırma.

  python run_pipeline.py                      # deterministik analiz → outputs/analysis.json
  python run_pipeline.py --agent              # + tüm kareler için LangChain ajanı
  python run_pipeline.py --agent --min-risk ORTA --frame img_000860
  python run_pipeline.py --chat "T0122 neden yüksek riskli?"
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging

from app.config import RISK_ORDER, settings
from app.service import service


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", action="store_true", help="LangChain ajanıyla kare değerlendirmesi üret")
    ap.add_argument("--frame", action="append", help="Sadece bu kare(ler)")
    ap.add_argument("--min-risk", default="DUSUK", choices=RISK_ORDER)
    ap.add_argument("--force", action="store_true", help="Önbelleği yok say")
    ap.add_argument("--chat", help="Ajana tek seferlik soru sor")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    service.load()
    st = service.state
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    out = {
        "summary": service.summary(),
        "frames": {fid: st.frame_view(fid, include_tracks=False) for fid in st.frames},
        "reports": st.reports,
        "alerts": service.alerts(),
        "offframe_tracks": st.offframe_risk,
    }
    path = settings.output_dir / "analysis.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n✔ Analiz yazıldı: {path}")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2, default=str))

    print("\nKare riskleri:")
    for f in sorted(st.frames.values(), key=lambda x: x["capture_time"]):
        top = st.vehicles.get(f["top_vehicle_id"]) if f["top_vehicle_id"] else None
        why = f"{top['track_id'] or top['vehicle_id']} {top['scenario']}" if top and f["risk_level"] != "DUSUK" else ""
        print(f"  {f['frame_id']}  {f['capture_time']}  {f['zone']:<24} {f['risk_level']:<7} {why}")

    if args.agent:
        lo = RISK_ORDER.index(args.min_risk)
        ids = args.frame or [f for f, fr in st.frames.items() if RISK_ORDER.index(fr["risk_level"]) >= lo]
        print(f"\nAjan {len(ids)} kare için çalışıyor (model: {settings.openai_model if settings.llm_enabled else 'yok → şablon'})...")
        res = asyncio.run(service.assess_many(ids, force=args.force))
        for fid, a in sorted(res.items()):
            print(f"\n[{fid}] {a['risk_level']} — {a['headline']}")
            for act in a["recommended_actions"][:3]:
                print(f"   • {act}")
            for n in a.get("guardrail_notes", []):
                print(f"   ⚠ {n}")
        print(f"\n✔ Değerlendirmeler: {service.cache_path}")

    if args.chat:
        if service.agent is None:
            print("LLM devre dışı (OPENAI_API_KEY yok).")
            return
        r = asyncio.run(service.agent.chat(args.chat, frame_id=(args.frame or [None])[0]))
        print("\n" + r["answer"])
        print("\nAraç çağrıları:", [t["tool"] for t in r["tool_calls"]])


if __name__ == "__main__":
    main()
