"""FastAPI analytics service - aggregates data from underlying services."""
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
import pydantic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("analytics")

app = FastAPI(title="quant-os Analytics", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# Service endpoints (matching ops_dashboard patterns)
SERVICE_ENDPOINTS = {
    "data_gateway": "http://localhost:8091",
    "feature_service": "http://localhost:8094",
    "risk_control": "http://localhost:8096",
    "execution_control": "http://localhost:8097",
    "report_generator": "http://localhost:8098",
    "signal_publisher": "http://localhost:8093",
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Position(pydantic.BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    allocation_pct: float


class PortfolioAnalytics(pydantic.BaseModel):
    updated_at: str
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    positions: list[Position]
    allocation_breakdown: dict[str, float]
    cash_available: float


class SignalPerformance(pydantic.BaseModel):
    strategy: str
    total_signals: int
    winning_signals: int
    win_rate: float
    avg_strength: float
    avg_return_pct: Optional[float] = None


class SignalsAnalytics(pydantic.BaseModel):
    updated_at: str
    total_signals: int
    overall_win_rate: float
    overall_avg_strength: float
    by_strategy: list[SignalPerformance]


class FeatureStats(pydantic.BaseModel):
    name: str
    min: float
    max: float
    mean: float
    std: float
    latest: float


class FeatureAnalytics(pydantic.BaseModel):
    symbol: str
    updated_at: str
    features: list[FeatureStats]
    feature_count: int


class RiskAnalytics(pydantic.BaseModel):
    updated_at: str
    total_exposure: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_proxy: float
    leverage: float
    leverage_ratio: float  # current leverage vs max allowed


class ReportInfo(pydantic.BaseModel):
    report_id: str
    date: str
    generated_at: str


class ReportsList(pydantic.BaseModel):
    reports: list[str]
    count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def fetch_json(url: str, timeout: float = 5.0) -> dict:
    """Fetch JSON from a service URL, raising HTTPException on failure."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error fetching {url}: {e.response.status_code}")
        raise HTTPException(e.response.status_code, f"upstream error: {e}")
    except httpx.RequestError as e:
        logger.warning(f"Request error fetching {url}: {e}")
        raise HTTPException(503, f"service unreachable: {str(e)[:80]}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/analytics/portfolio")
async def get_portfolio_analytics():
    """
    Portfolio analytics: positions, PnL summary, allocation breakdown.
    Aggregates data from execution_control and data_gateway.
    """
    try:
        # Fetch positions from execution_control
        positions_data = await fetch_json(f"{SERVICE_ENDPOINTS['execution_control']}/positions")
        # Fetch account value from data_gateway
        account_data = await fetch_json(f"{SERVICE_ENDPOINTS['data_gateway']}/account")
    except HTTPException:
        # Fallback: return empty analytics if services unavailable
        logger.warning("Underlying services unavailable, returning empty portfolio")
        return PortfolioAnalytics(
            updated_at=datetime.now(timezone.utc).isoformat(),
            total_value=0.0,
            total_pnl=0.0,
            total_pnl_pct=0.0,
            positions=[],
            allocation_breakdown={},
            cash_available=0.0,
        )

    # Parse positions
    positions = []
    allocation_breakdown = {}
    total_value = account_data.get("total_value", 0.0)
    total_pnl = 0.0

    for pos in positions_data.get("positions", []):
        quantity = float(pos.get("quantity", 0))
        entry_price = float(pos.get("entry_price", 0))
        current_price = float(pos.get("current_price", entry_price))
        unrealized_pnl = (current_price - entry_price) * quantity
        alloc_pct = (current_price * quantity / total_value * 100) if total_value > 0 else 0.0

        positions.append(Position(
            symbol=pos.get("symbol", "UNKNOWN"),
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            allocation_pct=round(alloc_pct, 2),
        ))
        allocation_breakdown[pos.get("symbol", "UNKNOWN")] = round(alloc_pct, 2)
        total_pnl += unrealized_pnl

    total_pnl_pct = (total_pnl / (total_value - total_pnl) * 100) if total_value > total_pnl else 0.0

    return PortfolioAnalytics(
        updated_at=datetime.now(timezone.utc).isoformat(),
        total_value=total_value,
        total_pnl=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct, 2),
        positions=positions,
        allocation_breakdown=allocation_breakdown,
        cash_available=account_data.get("cash", 0.0),
    )


@app.get("/analytics/signals")
async def get_signals_analytics():
    """
    Signal performance analytics: win rate, avg strength, breakdown by strategy.
    Aggregates from signal_publisher.
    """
    try:
        signals_data = await fetch_json(f"{SERVICE_ENDPOINTS['signal_publisher']}/signals?limit=1000")
    except HTTPException:
        logger.warning("signal_publisher unavailable, returning empty analytics")
        return SignalsAnalytics(
            updated_at=datetime.now(timezone.utc).isoformat(),
            total_signals=0,
            overall_win_rate=0.0,
            overall_avg_strength=0.0,
            by_strategy=[],
        )

    # Aggregate by strategy
    strategy_stats: dict[str, dict] = {}
    all_win = 0
    all_strength = 0.0
    total = 0

    for sig in signals_data if isinstance(signals_data, list) else signals_data.get("signals", []):
        strategy = sig.get("strategy", "unknown")
        if strategy not in strategy_stats:
            strategy_stats[strategy] = {"total": 0, "wins": 0, "strength_sum": 0.0}
        strategy_stats[strategy]["total"] += 1
        strategy_stats[strategy]["strength_sum"] += float(sig.get("strength", 0))
        if sig.get("outcome") == "win":
            strategy_stats[strategy]["wins"] += 1
            all_win += 1
        all_strength += float(sig.get("strength", 0))
        total += 1

    by_strategy = []
    for strategy, stats in strategy_stats.items():
        wr = stats["wins"] / stats["total"] if stats["total"] > 0 else 0.0
        avg_str = stats["strength_sum"] / stats["total"] if stats["total"] > 0 else 0.0
        by_strategy.append(SignalPerformance(
            strategy=strategy,
            total_signals=stats["total"],
            winning_signals=stats["wins"],
            win_rate=round(wr, 4),
            avg_strength=round(avg_str, 4),
            avg_return_pct=sig.get("avg_return_pct"),
        ))

    overall_wr = all_win / total if total > 0 else 0.0
    overall_avg_str = all_strength / total if total > 0 else 0.0

    return SignalsAnalytics(
        updated_at=datetime.now(timezone.utc).isoformat(),
        total_signals=total,
        overall_win_rate=round(overall_wr, 4),
        overall_avg_strength=round(overall_avg_str, 4),
        by_strategy=by_strategy,
    )


@app.get("/analytics/features/{symbol}")
async def get_feature_analytics(symbol: str):
    """
    Feature analytics for a symbol: computed stats (min/max/mean/std).
    Fetches from feature_service.
    """
    try:
        features_data = await fetch_json(f"{SERVICE_ENDPOINTS['feature_service']}/features/{symbol}")
    except HTTPException:
        logger.warning(f"feature_service unavailable for {symbol}")
        raise HTTPException(503, f"feature_service unreachable for symbol: {symbol}")

    # Parse feature stats
    feature_list = features_data.get("features", [])
    parsed = []
    for feat in feature_list:
        vals = feat.get("values", [])
        if not vals:
            continue
        import statistics
        feat_mean = statistics.mean(vals)
        feat_std = statistics.stdev(vals) if len(vals) > 1 else 0.0
        parsed.append(FeatureStats(
            name=feat.get("name", "unknown"),
            min=round(min(vals), 6),
            max=round(max(vals), 6),
            mean=round(feat_mean, 6),
            std=round(feat_std, 6),
            latest=round(vals[-1], 6),
        ))

    return FeatureAnalytics(
        symbol=symbol.upper(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        features=parsed,
        feature_count=len(parsed),
    )


@app.get("/analytics/risk")
async def get_risk_analytics():
    """
    Risk analytics: total exposure, max drawdown, Sharpe proxy, leverage.
    Fetches from risk_control.
    """
    try:
        risk_data = await fetch_json(f"{SERVICE_ENDPOINTS['risk_control']}/state")
    except HTTPException:
        logger.warning("risk_control unavailable, returning empty risk analytics")
        return RiskAnalytics(
            updated_at=datetime.now(timezone.utc).isoformat(),
            total_exposure=0.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            sharpe_proxy=0.0,
            leverage=0.0,
            leverage_ratio=0.0,
        )

    exposure = float(risk_data.get("total_exposure", 0.0))
    dd = float(risk_data.get("max_drawdown", 0.0))
    dd_pct = float(risk_data.get("max_drawdown_pct", 0.0))
    sharpe = float(risk_data.get("sharpe_proxy", 0.0))
    lev = float(risk_data.get("leverage", 0.0))
    max_lev = float(risk_data.get("max_leverage", 1.0))

    return RiskAnalytics(
        updated_at=datetime.now(timezone.utc).isoformat(),
        total_exposure=exposure,
        max_drawdown=dd,
        max_drawdown_pct=dd_pct,
        sharpe_proxy=sharpe,
        leverage=lev,
        leverage_ratio=round(lev / max_lev, 4) if max_lev > 0 else 0.0,
    )


@app.get("/reports", response_model=ReportsList)
async def list_reports(limit: int = 30):
    """
    List available reports - forwards to report_generator service.
    """
    try:
        data = await fetch_json(f"{SERVICE_ENDPOINTS['report_generator']}/reports?limit={limit}")
        reports = data.get("reports", [])
        return ReportsList(reports=reports, count=len(reports))
    except HTTPException:
        # Fallback: return empty
        return ReportsList(reports=[], count=0)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "analytics"}


def main():
    import uvicorn
    logger.info("Starting analytics service on port 3010")
    uvicorn.run(app, host="0.0.0.0", port=3010, log_level="info")


if __name__ == "__main__":
    main()