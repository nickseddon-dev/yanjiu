
from report_generator.main import ReportGenerator
from datetime import datetime, timezone


def test_generate():
    gen = ReportGenerator(output_dir="/tmp/test_reports")
    r = gen.generate("2026-01-15", ["BTC", "ETH"], 10, 7, 3,
                     [{"name": "x_mention_zscore", "importance": 0.8}], {}, {})
    assert r.report_id == "daily_report_2026-01-15"
    assert r.signals_approved == 7


def test_load():
    gen = ReportGenerator(output_dir="/tmp/test_reports")
    r = gen.load("2026-01-15")
    assert r is not None
    assert r.date == "2026-01-15"
