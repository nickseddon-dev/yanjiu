"""
Integration tests: data gateway features endpoint.

Tests the /features and related endpoints provided by data_gateway service.
"""

import time
import uuid

import pytest
import requests


DATA_GATEWAY_URL = "http://localhost:8091"


class TestDataGateway:
    """
    Tests for data_gateway service's feature API endpoints.
    """

    @pytest.fixture(autouse=True)
    def setup(self, waitForDataGateway: bool):
        assert waitForDataGateway, "data_gateway not healthy"

    def test_features_endpoint_exists(self):
        """
        Test that /features endpoint is reachable and returns HTTP 200.
        """
        resp = requests.get(f"{DATA_GATEWAY_URL}/features", timeout=10)
        assert resp.status_code == 200, (
            f"Expected 200 from /features, got {resp.status_code}: {resp.text}"
        )

    def test_features_list_format(self):
        """
        Test that /features returns a list (or dict with feature entries).
        """
        resp = requests.get(f"{DATA_GATEWAY_URL}/features", timeout=10)
        data = resp.json()
        assert isinstance(data, (list, dict)), (
            f"/features should return list or dict, got {type(data)}"
        )

    def test_feature_details_endpoint(self):
        """
        Test that /features/<feature_name> returns feature metadata.
        """
        # First, get the list of available features
        resp = requests.get(f"{DATA_GATEWAY_URL}/features", timeout=10)
        data = resp.json()

        features = []
        if isinstance(data, list):
            features = data
        elif isinstance(data, dict) and "features" in data:
            features = data["features"]

        if features:
            # Pick the first feature
            feature_name = features[0] if isinstance(features[0], str) else features[0].get("name")
            if feature_name:
                detail_resp = requests.get(
                    f"{DATA_GATEWAY_URL}/features/{feature_name}",
                    timeout=10,
                )
                assert detail_resp.status_code == 200, (
                    f"Expected 200 for feature detail, got {detail_resp.status_code}: "
                    f"{detail_resp.text}"
                )
                detail_data = detail_resp.json()
                assert "name" in detail_data or "feature" in detail_data, (
                    "Feature detail should contain 'name' or 'feature' key"
                )

    def test_features_backfill_endpoint(self):
        """
        Test that the /features/backfill endpoint accepts a symbol and returns 202.
        """
        symbol = "BTC/USDT"
        test_id = uuid.uuid4().hex[:8]
        payload = {
            "symbol": symbol,
            "features": ["sentiment", "hype", "divergence"],
            "start_ts": int((time.time() - 86400) * 1000),  # 24h ago
            "end_ts": int(time.time() * 1000),
            "request_id": f"test-backfill-{test_id}",
        }
        resp = requests.post(
            f"{DATA_GATEWAY_URL}/features/backfill",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code in (200, 201, 202), (
            f"Expected 200/201/202 from /features/backfill, got {resp.status_code}: "
            f"{resp.text}"
        )

    def test_features_health_includes_metrics(self):
        """
        Test that /health endpoint for data_gateway returns meaningful data.
        """
        resp = requests.get(f"{DATA_GATEWAY_URL}/health", timeout=10)
        assert resp.status_code == 200, f"Health check failed: {resp.status_code} {resp.text}"
        data = resp.json()
        # Health response should at minimum indicate 'status' or 'healthy'
        assert any(k in data for k in ("status", "healthy", "uptime")), (
            f"Health response missing expected keys: {data}"
        )

    def test_features_endpoint_with_symbol_filter(self):
        """
        Test that /features endpoint accepts a ?symbol= query parameter.
        """
        resp = requests.get(f"{DATA_GATEWAY_URL}/features?symbol=BTC/USDT", timeout=10)
        assert resp.status_code == 200, (
            f"Expected 200 from /features?symbol=BTC/USDT, got {resp.status_code}: "
            f"{resp.text}"
        )

    def test_features_endpoint_with_time_range(self):
        """
        Test that /features endpoint accepts start/end time range parameters.
        """
        start_ts = int((time.time() - 3600) * 1000)  # 1h ago
        end_ts = int(time.time() * 1000)
        resp = requests.get(
            f"{DATA_GATEWAY_URL}/features",
            params={"start_ts": start_ts, "end_ts": end_ts},
            timeout=10,
        )
        assert resp.status_code == 200, (
            f"Expected 200 from /features with time range, got {resp.status_code}: "
            f"{resp.text}"
        )