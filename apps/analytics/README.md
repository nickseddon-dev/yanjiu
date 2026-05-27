# Analytics Service

Data analysis and report aggregation service for quant-os.

## Overview

Provides aggregated analytics across all trading system services, including portfolio analytics, signal performance, feature statistics, risk metrics, and report listing.

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /analytics/portfolio` | Portfolio positions, PnL summary, allocation breakdown |
| `GET /analytics/signals` | Signal performance by strategy (win rate, avg strength) |
| `GET /analytics/features/{symbol}` | Feature statistics for a symbol (min/max/mean/std) |
| `GET /analytics/risk` | Risk metrics (exposure, drawdown, Sharpe proxy, leverage) |
| `GET /reports` | List available reports from report_generator |
| `GET /health` | Health check |

## Port

Listens on port **3010**.

## Architecture

Aggregates data from underlying services via HTTP:

- `execution_control:8097` - positions data
- `data_gateway:8091` - account values
- `feature_service:8094` - feature computation
- `risk_control:8096` - risk state
- `signal_publisher:8093` - signal history
- `report_generator:8098` - report listing

## Running

```bash
# Local
python -m apps.analytics.main

# Docker
docker build -f apps/analytics/Dockerfile -t analytics .
docker run -p 3010:3010 analytics
```

## API Response Examples

### GET /analytics/portfolio

```json
{
  "updated_at": "2026-05-27T10:00:00Z",
  "total_value": 100000.0,
  "total_pnl": 2500.0,
  "total_pnl_pct": 2.5,
  "positions": [
    {
      "symbol": "BTC",
      "quantity": 0.5,
      "entry_price": 60000.0,
      "current_price": 61000.0,
      "unrealized_pnl": 500.0,
      "allocation_pct": 30.5
    }
  ],
  "allocation_breakdown": {"BTC": 30.5, "ETH": 25.0},
  "cash_available": 44500.0
}
```

### GET /analytics/risk

```json
{
  "updated_at": "2026-05-27T10:00:00Z",
  "total_exposure": 55500.0,
  "max_drawdown": -3200.0,
  "max_drawdown_pct": -3.2,
  "sharpe_proxy": 1.45,
  "leverage": 0.55,
  "leverage_ratio": 0.55
}
```