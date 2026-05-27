
"""Report generation service - generates daily research reports."""
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pydantic
from fastapi import FastAPI

logger = logging.getLogger("report_generator")


class DailyReport(pydantic.BaseModel):
    report_id: str
    date: str
    generated_at: str
    symbols_covered: list[str]
    signals_generated: int
    signals_approved: int
    signals_rejected: int
    top_features: list[dict]
    narrative_summary: dict
    performance_summary: dict


class ReportGenerator:
    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, date: str, symbols: list, sg: int, sa: int, sr: int,
                 top_feats: list, ns: dict, ps: dict) -> DailyReport:
        rid = f"daily_report_{date}"
        report = DailyReport(
            report_id=rid, date=date,
            generated_at=datetime.now(timezone.utc).isoformat(),
            symbols_covered=symbols, signals_generated=sg, signals_approved=sa,
            signals_rejected=sr, top_features=top_feats,
            narrative_summary=ns, performance_summary=ps,
        )
        path = self.output_dir / f"{rid}.json"
        with open(path, "w") as f:
            json.dump(report.model_dump(), f, indent=2)
        logger.info(f"Saved {path}")
        return report

    def load(self, date: str) -> Optional[DailyReport]:
        p = self.output_dir / f"daily_report_{date}.json"
        if not p.exists():
            return None
        with open(p) as f:
            return DailyReport(**json.load(f))

    def list_dates(self, limit: int = 30) -> list[str]:
        files = sorted(self.output_dir.glob("daily_report_*.json"), reverse=True)
        return [f.stem.replace("daily_report_", "") for f in files[:limit]]

    def cleanup(self, retention_days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        removed = 0
        for f in self.output_dir.glob("daily_report_*.json"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                f.unlink()
                removed += 1
        return removed


app = FastAPI(title="report_generator", version="0.1.0")
_gen: Optional[ReportGenerator] = None


class GenReq(pydantic.BaseModel):
    date: str
    symbols: list[str]
    signals_generated: int = 0
    signals_approved: int = 0
    signals_rejected: int = 0
    top_features: list[dict] = []
    narrative_summary: dict = {}
    performance_summary: dict = {}


@app.on_event("startup")
async def startup():
    global _gen
    _gen = ReportGenerator()
    logger.info("report_generator started")


@app.post("/reports/daily", response_model=DailyReport)
async def gen_report(req: GenReq):
    if _gen is None:
        from fastapi import HTTPException
        raise HTTPException(503, "not initialized")
    return _gen.generate(req.date, req.symbols, req.signals_generated,
                         req.signals_approved, req.signals_rejected,
                         req.top_features, req.narrative_summary,
                         req.performance_summary)


@app.get("/reports/daily/{date}")
async def get_report(date: str):
    if _gen is None:
        from fastapi import HTTPException
        raise HTTPException(503, "not initialized")
    r = _gen.load(date)
    if r is None:
        from fastapi import HTTPException
        raise HTTPException(404, "not found")
    return r.model_dump()


@app.get("/reports")
async def list_reports(limit: int = 30):
    if _gen is None:
        return []
    dates = _gen.list_dates(limit)
    return {"reports": dates, "count": len(dates)}


@app.post("/reports/cleanup")
async def cleanup(retention_days: int = 30):
    if _gen is None:
        from fastapi import HTTPException
        raise HTTPException(503, "not initialized")
    removed = _gen.cleanup(retention_days)
    return {"status": "ok", "removed": removed}


@app.get("/health")
async def health():
    return {"status": "ok", "count": len(_gen.list_dates()) if _gen else 0}


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8098, log_level="info")


if __name__ == "__main__":
    main()
