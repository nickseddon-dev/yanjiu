"""
Integration tests: risk engine integration with risk_control service.

Tests the risk_control /risk/evaluate endpoint and related functionality.
"""

import time
import uuid

import pytest
import requests


RISK_CONTROL_URL = "http://localhost:8096"


class TestRiskControl:
    """
    Tests for risk_control service's risk evaluation API.
    """

    @pytest.fixture(autouse=True)
    def setup(self, waitForRiskControl: bool):
        assert waitForRiskControl, "risk_control not healthy"

    def test_risk_evaluate_endpoint_exists(self):
        """
        Test that POST /risk/evaluate is reachable and returns HTTP 200 or 400.
        """
        payload = {
            "request_id": f"test-{uuid.uuid4().hex[:8]}",
            "symbol": "BTC/USDT",
            "direction": "long",
            "quantity": 0.1,
            "price": 50000.0,
            "timestamp": time.time(),
        }
        resp = requests.post(
            f"{RISK_CONTROL_URL}/risk/evaluate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code in (200, 201, 202, 400), (
            f"Unexpected status from /risk/evaluate: {resp.status_code} {resp.text}"
        )

    def test_risk_evaluate_returns_decision(self):
        """
        Test that /risk/evaluate returns a decision field (approve/reject).
        """
        payload = {
            "request_id": f"test-{uuid.uuid4().hex[:8]}",
            "symbol": "BTC/USDT",
            "direction": "long",
            "quantity": 0.1,
            "price": 50000.0,
            "timestamp": time.time(),
        }
        resp = requests.post(
            f"{RISK_CONTROL_URL}/risk/evaluate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code in (200, 201, 202):
            data = resp.json()
            assert "decision" in data, f"Response missing 'decision' field: {data}"
            assert data["decision"] in ("approve", "reject", "pending"), (
                f"Invalid decision value: {data['decision']}"
            )

    def test_risk_evaluate_rejects_missing_fields(self):
        """
        Test that /risk/evaluate returns 422 when required fields are missing.
        """
        payload = {
            "request_id": f"test-{uuid.uuid4().hex[:8]}",
            # missing symbol, direction, quantity, price
            "timestamp": time.time(),
        }
        resp = requests.post(
            f"{RISK_CONTROL_URL}/risk/evaluate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code == 422, (
            f"Expected 422 for missing fields, got {resp.status_code}: {resp.text}"
        )

    def test_risk_evaluate_exposure_limit(self):
        """
        Test that sending a very large quantity triggers risk rejection.
        """
        payload = {
            "request_id": f"test-{uuid.uuid4().hex[:8]}",
            "symbol": "BTC/USDT",
            "direction": "long",
            "quantity": 9999999.0,  # absurdly large
            "price": 50000.0,
            "timestamp": time.time(),
        }
        resp = requests.post(
            f"{RISK_CONTROL_URL}/risk/evaluate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        # Should either be 400 (bad request) or 200 with reject decision
        if resp.status_code in (200, 201, 202):
            data = resp.json()
            assert data.get("decision") == "reject", (
                f"Expected reject for huge quantity, got: {data}"
            )
        else:
            assert resp.status_code == 400, (
                f"Expected 400 or 200+reject for oversized trade, got {resp.status_code}: "
                f"{resp.text}"
            )

    def test_risk_health_endpoint(self):
        """
        Test that /health endpoint for risk_control returns HTTP 200.
        """
        resp = requests.get(f"{RISK_CONTROL_URL}/health", timeout=10)
        assert resp.status_code == 200, (
            f"Health check failed: {resp.status_code} {resp.text}"
        )

    def test_risk_rules_endpoint(self):
        """
        Test that GET /risk/rules returns the list of active risk rules.
        """
        resp = requests.get(f"{RISK_CONTROL_URL}/risk/rules", timeout=10)
        assert resp.status_code == 200, (
            f"Expected 200 from /risk/rules, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert isinstance(data, (list, dict)), (
            f"/risk/rules should return list or dict, got {type(data)}"
        )

    def test_risk_evaluate_short_direction(self):
        """
        Test that risk_evaluate correctly processes a 'short' direction signal.
        """
        payload = {
            "request_id": f"test-{uuid.uuid4().hex[:8]}",
            "symbol": "ETH/USDT",
            "direction": "short",
            "quantity": 1.0,
            "price": 3000.0,
            "timestamp": time.time(),
        }
        resp = requests.post(
            f"{RISK_CONTROL_URL}/risk/evaluate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code in (200, 201, 202, 400), (
            f"Unexpected status for short direction: {resp.status_code} {resp.text}"
        )
        if resp.status_code in (200, 201, 202):
            data = resp.json()
            assert "decision" in data, f"Response missing 'decision': {data}"