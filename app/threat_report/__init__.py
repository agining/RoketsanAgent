"""Şüpheli araç tehdit raporu (PDF).

Tüm kareler değerlendirildikten sonra seçilen risk seviyesindeki her araç için: rota ve üsse mesafe
grafikleri, motor kural tablosu, karar zinciri (motor → LLM → karar tablosu → insan onayı), ilgili saha
raporları ve LLM'in (yoksa deterministik şablonun) yazdığı "neden şüpheli" açıklaması. Tema ve bölüm
sırası sabittir.

    from app.threat_report import ReportOptions, build_threat_report
    summary = await build_threat_report(service, ReportOptions(min_risk="YUKSEK"))
"""
from .builder import build_threat_report, list_reports
from .collect import ReportOptions, collect_report_data

__all__ = ["ReportOptions", "build_threat_report", "collect_report_data", "list_reports"]
