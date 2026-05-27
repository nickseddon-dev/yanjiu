
"""Ops dashboard main application."""
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

import pydantic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("ops_dashboard")

app = FastAPI(title="quant-os Ops Dashboard", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

SERVICE_ENDPOINTS = {
    "data_gateway": "http://localhost:8091",
    "event_gateway": "http://localhost:8092",
    "signal_publisher": "http://localhost:8093",
    "feature_service": "http://localhost:8094",
    "orchestrator": "http://localhost:8095",
    "risk_control": "http://localhost:8096",
    "execution_control": "http://localhost:8097",
    "report_generator": "http://localhost:8098",
    "signal_bridge": "http://localhost:8090",
    "research_runner": "http://localhost:8099",
}


class ServiceHealth(pydantic.BaseModel):
    name: str
    url: str
    status: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class DashboardState(pydantic.BaseModel):
    checked_at: str
    services: list[ServiceHealth]
    healthy_count: int
    unhealthy_count: int


async def check_service(name: str, url: str) -> ServiceHealth:
    """Check a single service health endpoint."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            start = datetime.now()
            resp = await client.get(f"{url}/health")
            latency = (datetime.now() - start).total_seconds() * 1000
            if resp.status_code == 200:
                return ServiceHealth(name=name, url=url, status="healthy", latency_ms=round(latency, 1))
            else:
                return ServiceHealth(name=name, url=url, status="degraded", error=f"HTTP {resp.status_code}")
    except Exception as e:
        return ServiceHealth(name=name, url=url, status="unreachable", error=str(e)[:80])


@app.get("/", response_class=FileResponse)
async def root():
    static_index = Path(__file__).parent / "static" / "index.html"
    return FileResponse(str(static_index))


@app.get("/health", response_model=DashboardState)
async def dashboard_health():
    """Check all service health endpoints."""
    results = []
    for name, url in SERVICE_ENDPOINTS.items():
        results.append(await check_service(name, url))
    healthy = sum(1 for r in results if r.status == "healthy")
    return DashboardState(
        checked_at=datetime.now(timezone.utc).isoformat(),
        services=results,
        healthy_count=healthy,
        unhealthy_count=len(results) - healthy,
    )


@app.get("/services/{name}/health")
async def service_health(name: str):
    """Check a specific service."""
    if name not in SERVICE_ENDPOINTS:
        raise HTTPException(404, f"unknown service: {name}")
    result = await check_service(name, SERVICE_ENDPOINTS[name])
    return result.model_dump()


@app.get("/signals/recent", response_model=list[dict])
async def recent_signals(limit: int = 20):
    """Fetch recent signals from signal_publisher."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{SERVICE_ENDPOINTS['signal_publisher']}/signals?limit={limit}")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"signal_publisher unreachable: {e}")


@app.get("/features/{symbol}")
async def get_features(symbol: str):
    """Fetch computed features for a symbol from feature_service."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{SERVICE_ENDPOINTS['feature_service']}/features/{symbol}")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"feature_service unreachable: {e}")


@app.get("/risk/state")
async def get_risk_state():
    """Get current risk state from risk_control."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{SERVICE_ENDPOINTS['risk_control']}/state")
            if resp.status_code == 404:
                return {"state": "no_data"}
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"risk_control unreachable: {e}")


@app.get("/kill-switch")
async def get_kill_switch():
    """Get kill switch status from risk_control."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{SERVICE_ENDPOINTS['risk_control']}/kill-switch")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"risk_control unreachable: {e}")


@app.get("/reports")
async def list_reports():
    """List available reports from report_generator."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{SERVICE_ENDPOINTS['report_generator']}/reports")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"report_generator unreachable: {e}")


def main():
    import uvicorn
    logger.info("Starting ops_dashboard")
    uvicorn.run(app, host="0.0.0.0", port=3000, log_level="info")


if __name__ == "__main__":
    main()
