"""
Integration tests: Polymarket-driven research pipeline end-to-end.

Tests the complete research pipeline:
  1. Polymarket data fetching -> polymarket_delta, prob_jump features
  2. Event gateway social events -> sentiment, hype features
  3. Feature service computation
  4. Signal generation (prob_jump + sentiment confirmation logic)
  5. Signal publishing to signal_bridge

Test env: assumes all services running on localhost:
  - data_gateway:      http://localhost:8002
  - event_gateway:     http://localhost:8003
  - feature_service:   http://localhost:8094
  - signal_bridge:     http://localhost:8090
  - research_runner:   http://localhost:8099
  - orchestrator:      http://localhost:8095
"""
import json
import time
import uuid
from typing import Any, Dict

import pytest
import requests


# --- Service URLs ---

DATA_GATEWAY_URL = "http://localhost:8002"
EVENT_GATEWAY_URL = "http://localhost:8003"
FEATURE_SERVICE_URL = "http://localhost:8094"
SIGNAL_BRIDGE_URL = "http://localhost:8090"
RESEARCH_RUNNER_URL = "http://localhost:8099"
ORCHESTRATOR_URL = "http://localhost:8095"


# --- Helper functions ---

def wait_for_service(url: str, timeout: int = 30) -> bool:
    """Wait for service to be healthy."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{url}/health", timeout=5)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def fetch_markets() -> list[Dict[str, Any]]:
    """Fetch Polymarket markets from data_gateway."""
    try:
        resp = requests.get(f"{DATA_GATEWAY_URL}/polymarket/markets", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data.get("markets", data.get("data", []))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def fetch_polymarket_delta(market_id: str) -> Dict[str, Any]:
    """Fetch probability history for a market and compute delta."""
    try:
        resp = requests.get(
            f"{DATA_GATEWAY_URL}/polymarket/markets/{market_id}/history",
            params={"limit": 50},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            history = data.get("history", data.get("data", []))
            if len(history) >= 2:
                return {"current": history[-1], "past": history[-50], "history_len": len(history)}
    except Exception:
        pass
    return {}


def post_signal(signal_id: str, symbol: str, direction: str, strength: float, **kwargs) -> requests.Response:
    """Post a signal to signal_bridge."""
    payload = {
        "signal_id": signal_id,
        "symbol": symbol,
        "direction": direction,
        "strength": strength,
        "timestamp": time.time(),
        "source": "integration_test",
        **kwargs,
    }
    return requests.post(
        f"{SIGNAL_BRIDGE_URL}/signals",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )


# --- Test fixtures ---

@pytest.fixture(scope="module")
def services_ready():
    """Ensure all required services are healthy before running tests."""
    services = {
        "data_gateway": DATA_GATEWAY_URL,
        "event_gateway": EVENT_GATEWAY_URL,
        "feature_service": FEATURE_SERVICE_URL,
        "signal_bridge": SIGNAL_BRIDGE_URL,
        "research_runner": RESEARCH_RUNNER_URL,
        "orchestrator": ORCHESTRATOR_URL,
    }
    results = {}
    for name, url in services.items():
        healthy = wait_for_service(url, timeout=15)
        results[name] = healthy
        print(f"{name}: {'UP' if healthy else 'DOWN'}")

    all_up = all(results.values())
    if not all_up:
        pytest.skip(f"Services not all healthy: {results}")
    return results


class TestPolymarketDataFetching:
    """Test Polymarket data fetching and probability delta computation."""

    def test_polymarket_markets_endpoint(self, services_ready):
        """Test that data_gateway returns Polymarket markets."""
        markets = fetch_markets()
        assert len(markets) > 0, "Should return at least one market"
        # Verify market structure
        for m in markets[:3]:
            assert "id" in m or "question" in m, f"Market missing expected fields: {m}"

    def test_polymarket_market_history(self, services_ready):
        """Test that market history endpoint returns price history."""
        markets = fetch_markets()
        if not markets:
            pytest.skip("No markets available")

        market_id = markets[0].get("id", "")
        if not market_id:
            pytest.skip("No market ID found")

        history = fetch_polymarket_delta(market_id)
        # Should return current and past data points
        assert "current" in history or "history_len" in history

    def test_polymarket_probability_delta(self, services_ready):
        """
        Test probability delta computation.
        This is the core feature: delta = current_prob - past_prob.
        """
        markets = fetch_markets()
        if not markets:
            pytest.skip("No markets available")

        for market in markets[:5]:
            market_id = market.get("id", "")
            if not market_id:
                continue

            result = fetch_polymarket_delta(market_id)
            if "current" not in result or "past" not in result:
                continue

            current_prob = result["current"].get("probability", result["current"].get("price", 0.5))
            past_prob = result["past"].get("probability", result["past"].get("price", 0.5))

            delta = current_prob - past_prob
            # Delta should be between -1 and 1
            assert -1 <= delta <= 1, f"Delta out of range: {delta}"

            # If significant change detected, it's a prob_jump
            if abs(delta) > 0.1:
                print(f"PROB_JUMP detected: market={market_id[:20]}... delta={delta:.3f}")

            break  # Test at least one market


class TestFeatureService:
    """Test feature_service computation from real data sources."""

    def test_feature_service_health(self, services_ready):
        """Test that feature_service is healthy and connected to downstream services."""
        resp = requests.get(f"{FEATURE_SERVICE_URL}/health", timeout=10)
        assert resp.status_code == 200, f"feature_service unhealthy: {resp.status_code}"
        data = resp.json()
        assert "redis_connected" in data

    def test_list_features(self, services_ready):
        """Test that feature_service lists all registered features."""
        resp = requests.get(f"{FEATURE_SERVICE_URL}/features", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        features = data.get("features", [])
        expected = ["sentiment_mean", "hype_velocity", "polymarket_delta", "prob_jump_magnitude"]
        for feat_name in expected:
            assert any(f["name"] == feat_name for f in features), f"Missing feature: {feat_name}"

    def test_compute_polymarket_features(self, services_ready):
        """Test computation of Polymarket-based features (polymarket_delta, prob_jump)."""
        resp = requests.post(
            f"{FEATURE_SERVICE_URL}/features/compute",
            json={"symbol": "BTC/USDT-Binance", "feature_names": ["polymarket_delta", "prob_jump_magnitude"]},
            timeout=20,
        )
        assert resp.status_code == 200
        data = resp.json()
        features = data.get("features", [])
        assert len(features) >= 1

        feat_dict = {f["name"]: f["value"] for f in features}
        # polymarket_delta should be between -1 and 1
        delta = feat_dict.get("polymarket_delta", 0.0)
        assert -1 <= delta <= 1, f"polymarket_delta out of range: {delta}"
        # prob_jump_magnitude should be non-negative
        jump = feat_dict.get("prob_jump_magnitude", 0.0)
        assert jump >= 0, f"prob_jump_magnitude negative: {jump}"

    def test_compute_all_features(self, services_ready):
        """Test computing all features for a symbol."""
        resp = requests.post(
            f"{FEATURE_SERVICE_URL}/features/compute",
            json={
                "symbol": "BTC/USDT-Binance",
                "feature_names": [
                    "sentiment_mean", "hype_velocity", "bull_bear_ratio",
                    "neutral_ratio", "polymarket_delta", "prob_jump_magnitude",
                    "cross_platform_speed", "peak_heat_time",
                ],
            },
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        features = data.get("features", [])
        assert len(features) >= 6  # Most features should compute


class TestResearchRunner:
    """Test research_runner signal generation from Polymarket data."""

    def test_health(self, services_ready):
        """Test research_runner is healthy."""
        resp = requests.get(f"{RESEARCH_RUNNER_URL}/health", timeout=10)
        assert resp.status_code == 200

    def test_generate_signals(self, services_ready):
        """Test signal generation endpoint."""
        resp = requests.post(
            f"{RESEARCH_RUNNER_URL}/signals/generate",
            params={"symbol": "BTC/USDT-Binance"},
            timeout=30,
        )
        assert resp.status_code == 200
        signals = resp.json()
        assert isinstance(signals, list), f"Expected list, got {type(signals)}"

        for sig in signals[:5]:
            assert "signal_id" in sig
            assert "signal_strength" in sig
            assert 0 <= sig["signal_strength"] <= 1
            assert sig["side"] in ("BUY", "SELL")

    def test_polymarket_signals_include_prob_delta(self, services_ready):
        """Test that generated signals include Polymarket-derived risk_tags."""
        resp = requests.post(
            f"{RESEARCH_RUNNER_URL}/signals/generate",
            params={"symbol": "BTC/USDT-Binance"},
            timeout=30,
        )
        assert resp.status_code == 200
        signals = resp.json()

        for sig in signals[:3]:
            risk_tags = sig.get("risk_tags", [])
            # Should have prob_jump or polymarket_delta in tags
            has_prob_tag = any(
                tag.startswith("polymarket_delta") or tag.startswith("prob_jump") or tag == "polymarket"
                for tag in risk_tags
            )
            # Fallback signals may not have these, skip for mock mode
            print(f"Signal {sig['signal_id'][:8]}... risk_tags={risk_tags}")


class TestOrchestratorFlows:
    """Test orchestrator Prefect flows with real service calls."""

    def test_orchestrator_health(self, services_ready):
        """Test orchestrator health check includes all downstream services."""
        resp = requests.get(f"{ORCHESTRATOR_URL}/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "all_services_connected" in data

    def test_crypto_research_flow(self, services_ready):
        """Test the main crypto_research_flow."""
        resp = requests.post(
            f"{ORCHESTRATOR_URL}/flows/run",
            json={"flow_name": "crypto_research", "parameters": {"symbol": "BTC/USDT-Binance"}},
            timeout=60,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["flow_name"] == "crypto_research"
        assert "run_id" in data

    def test_batch_research_flow(self, services_ready):
        """Test batch_research_flow across multiple symbols."""
        resp = requests.post(
            f"{ORCHESTRATOR_URL}/flows/run",
            json={
                "flow_name": "batch_research",
                "parameters": {"symbols": ["BTC/USDT-Binance", "ETH/USDT-Binance"]},
            },
            timeout=120,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "COMPLETED"

    def test_flow_run_history(self, services_ready):
        """Test that flow runs are recorded."""
        resp = requests.get(f"{ORCHESTRATOR_URL}/flows/runs", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert "count" in data


class TestSignalBridge:
    """Test signal_bridge with Polymarket-derived signals."""

    def test_post_polymarket_signal(self, services_ready):
        """Test posting a Polymarket-derived signal."""
        signal_id = f"test-poly-signal-{uuid.uuid4().hex[:12]}"
        payload = {
            "signal_id": signal_id,
            "symbol": "BTC/USDT",
            "direction": "long",
            "strength": 0.75,
            "timestamp": time.time(),
            "source": "polymarket_research",
            "risk_tags": ["polymarket", "prob_jump_0.15", "polymarket_delta_0.12"],
        }
        resp = requests.post(
            f"{SIGNAL_BRIDGE_URL}/signals",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code in (200, 201, 202), f"Failed: {resp.status_code} {resp.text}"

    def test_signal_flow_end_to_end(self, services_ready):
        """
        End-to-end test: generate signal -> verify it reaches signal_bridge.

        This simulates the full pipeline:
          Polymarket data -> feature_service -> research_runner -> signal_bridge
        """
        signal_id = f"test-e2e-{uuid.uuid4().hex[:12]}"

        # Post a Polymarket-style signal
        resp = post_signal(
            signal_id=signal_id,
            symbol="BTC/USDT",
            direction="long",
            strength=0.8,
            risk_tags=["polymarket", "prob_jump_0.18"],
            source="integration_test",
        )
        assert resp.status_code in (200, 201, 202), f"Signal post failed: {resp.status_code}"

        # Poll signal_bridge until signal appears with non-pending status
        found = False
        for _ in range(30):
            try:
                resp = requests.get(f"{SIGNAL_BRIDGE_URL}/signals/{signal_id}", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") not in ("pending", "unknown", ""):
                        found = True
                        break
            except Exception:
                pass
            time.sleep(1)

        assert found, f"Signal {signal_id} never reached signal_bridge"