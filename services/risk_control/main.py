
"""Risk control service - research-side risk monitoring and kill switch."""
import logging
from datetime import datetime, timezone
from typing import Optional

import pydantic
from fastapi import FastAPI, HTTPException

logger = logging.getLogger("risk_control")


class RiskState(pydantic.BaseModel):
    """Current risk state snapshot."""
    timestamp: str
    total_value: float
    daily_pnl_pct: float
    current_drawdown_pct: float
    portfolio_var_pct: float
    positions: dict
    venue_exposure: dict
    narrative_exposure: dict
    data_sources_healthy: int
    data_sources_total: int
    order_reject_rate: float
    exchange_latency_ms: float
    kill_switch_triggered: bool = False


class RiskControlService:
    """Research-side risk monitoring service."""

    def __init__(self):
        self._state: Optional[RiskState] = None
        self._kill_switch_thresholds = {
            "daily_drawdown": 0.05,
            "data_source_failure": 2,
            "order_reject_rate": 0.30,
            "exchange_latency_ms": 2000,
        }

    def update_state(self, state: RiskState) -> None:
        """Update the current risk state."""
        self._state = state
        logger.info(f"Risk state updated: portfolio_value={state.total_value:.2f}")

    def get_state(self) -> Optional[RiskState]:
        return self._state

    def check_kill_switch(self) -> tuple[bool, str]:
        """Check if kill switch should trigger."""
        if self._state is None:
            return False, "no state"
        s = self._state
        if s.current_drawdown_pct > self._kill_switch_thresholds["daily_drawdown"]:
            return True, f"drawdown {s.current_drawdown_pct:.2%} exceeds limit"
        total_ds = max(s.data_sources_total, 1)
        failed_ds = total_ds - s.data_sources_healthy
        if failed_ds >= self._kill_switch_thresholds["data_source_failure"]:
            return True, f"{failed_ds} data sources failed"
        if s.order_reject_rate > self._kill_switch_thresholds["order_reject_rate"]:
            return True, f"reject rate {s.order_reject_rate:.2%} exceeds limit"
        if s.exchange_latency_ms > self._kill_switch_thresholds["exchange_latency_ms"]:
            return True, f"latency {s.exchange_latency_ms:.0f}ms exceeds limit"
        return False, ""

    def get_violations(self, state: RiskState) -> list[str]:
        """Return list of risk violations for current state."""
        violations = []
        if state.current_drawdown_pct > 0.05:
            violations.append(f"drawdown {state.current_drawdown_pct:.2%} > 5%")
        if state.portfolio_var_pct > 0.02:
            violations.append(f"VaR {state.portfolio_var_pct:.2%} > 2%")
        if state.order_reject_rate > 0.10:
            violations.append(f"reject_rate {state.order_reject_rate:.2%} > 10%")
        for venue, exposure in state.venue_exposure.items():
            total = max(state.total_value, 1.0)
            if abs(exposure / total) > 0.40:
                violations.append(f"venue {venue} exposure {abs(exposure/total):.2%} > 40%")
        return violations


from pydantic import BaseModel

app = FastAPI(title="risk_control", version="0.1.0")
_svc: Optional[RiskControlService] = None


class UpdateStateRequest(BaseModel):
    total_value: float
    daily_pnl_pct: float
    current_drawdown_pct: float
    portfolio_var_pct: float
    positions: dict = {}
    venue_exposure: dict = {}
    narrative_exposure: dict = {}
    data_sources_healthy: int = 3
    data_sources_total: int = 3
    order_reject_rate: float = 0.0
    exchange_latency_ms: float = 0.0


class KillSwitchResponse(BaseModel):
    triggered: bool
    reason: str


class ViolationsResponse(BaseModel):
    violations: list[str]


@app.on_event("startup")
async def startup():
    global _svc
    _svc = RiskControlService()
    logger.info("risk_control started")


@app.post("/state")
async def update_state(req: UpdateStateRequest):
    if _svc is None:
        raise HTTPException(503, "not initialized")
    state = RiskState(
        timestamp=datetime.now(timezone.utc).isoformat(),
        **req.model_dump(),
    )
    _svc.update_state(state)
    return {"status": "updated"}


@app.get("/state", response_model=RiskState)
async def get_state():
    if _svc is None:
        raise HTTPException(503, "not initialized")
    s = _svc.get_state()
    if s is None:
        raise HTTPException(404, "no state available")
    return s


@app.get("/kill-switch", response_model=KillSwitchResponse)
async def check_kill_switch():
    if _svc is None:
        raise HTTPException(503, "not initialized")
    triggered, reason = _svc.check_kill_switch()
    return KillSwitchResponse(triggered=triggered, reason=reason)


@app.post("/violations", response_model=ViolationsResponse)
async def check_violations(req: UpdateStateRequest):
    if _svc is None:
        raise HTTPException(503, "not initialized")
    state = RiskState(
        timestamp=datetime.now(timezone.utc).isoformat(),
        **req.model_dump(),
    )
    violations = _svc.get_violations(state)
    return ViolationsResponse(violations=violations)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "has_state": _svc.get_state() is not None if _svc else False,
    }


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8096, log_level="info")


if __name__ == "__main__":
    main()
