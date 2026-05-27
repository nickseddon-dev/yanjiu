
"""Execution control service - research-side entry decision engine."""
import logging
from datetime import datetime, timezone
from typing import Optional

import pydantic
from fastapi import FastAPI, HTTPException

logger = logging.getLogger("execution_control")


class EntrySignal(pydantic.BaseModel):
    symbol: str
    direction: str
    confidence: float
    narrative: str = ""
    features: dict = {}


class EntryDecision(pydantic.BaseModel):
    signal_id: str
    symbol: str
    decision: str
    reason: str = ""
    filtered_by: str = ""


class ExecutionController:
    def __init__(self, min_confidence: float = 0.65, blocklist: set = None):
        self.min_confidence = min_confidence
        self.blocklist = blocklist or set()
        self._log: list = []

    def evaluate(self, signal: EntrySignal) -> EntryDecision:
        sid = f"dec_{signal.symbol}_{int(datetime.now(timezone.utc).timestamp())}"
        if signal.symbol.upper() in self.blocklist or signal.narrative in self.blocklist:
            d = EntryDecision(signal_id=sid, symbol=signal.symbol, decision="BLOCKED",
                             reason="on block list", filtered_by="blocklist")
            self._log.append(d)
            return d
        if signal.confidence < self.min_confidence:
            d = EntryDecision(signal_id=sid, symbol=signal.symbol, decision="REJECTED",
                             reason=f"conf={signal.confidence:.3f} < {self.min_confidence:.3f}",
                             filtered_by="confidence")
            self._log.append(d)
            return d
        d = EntryDecision(signal_id=sid, symbol=signal.symbol, decision="APPROVED",
                         reason="all checks passed", filtered_by="")
        self._log.append(d)
        return d

    def add_blocklist(self, item: str) -> None:
        self.blocklist.add(item.upper() if len(item) <= 10 else item)

    def remove_blocklist(self, item: str) -> None:
        self.blocklist.discard(item.upper())

    def recent_decisions(self, limit: int = 50) -> list:
        return sorted(self._log, key=lambda x: x.signal_id, reverse=True)[:limit]


from pydantic import BaseModel

app = FastAPI(title="execution_control", version="0.1.0")
_ctrl: Optional[ExecutionController] = None


class EvalRequest(BaseModel):
    symbol: str
    direction: str
    confidence: float
    narrative: str = ""
    features: dict = {}


@app.on_event("startup")
async def startup():
    global _ctrl
    _ctrl = ExecutionController()
    logger.info("execution_control started")


@app.post("/evaluate", response_model=EntryDecision)
async def evaluate(req: EvalRequest):
    if _ctrl is None:
        raise HTTPException(503, "not initialized")
    return _ctrl.evaluate(EntrySignal(**req.model_dump()))


@app.get("/decisions", response_model=list[EntryDecision])
async def list_decisions(limit: int = 50):
    if _ctrl is None:
        return []
    return _ctrl.recent_decisions(limit)


@app.post("/blocklist")
async def add_bl(item: str):
    if _ctrl:
        _ctrl.add_blocklist(item)
    return {"blocklist": list(_ctrl.blocklist) if _ctrl else []}


@app.delete("/blocklist/{item}")
async def del_bl(item: str):
    if _ctrl:
        _ctrl.remove_blocklist(item)
    return {"blocklist": list(_ctrl.blocklist) if _ctrl else []}


@app.get("/blocklist")
async def get_bl():
    if _ctrl is None:
        return []
    return list(_ctrl.blocklist)


@app.get("/health")
async def health():
    return {"status": "ok", "min_confidence": _ctrl.min_confidence if _ctrl else None}


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8097, log_level="info")


if __name__ == "__main__":
    main()
