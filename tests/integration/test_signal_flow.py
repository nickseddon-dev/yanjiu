"""
Integration tests: end-to-end signal flow test.

Flow: post signal -> signal_bridge -> execution_control

This test verifies the complete signal lifecycle:
1. A signal is posted to signal_bridge (POST /signals)
2. signal_bridge validates and forwards the signal
3. execution_control receives and processes the signal
4. The signal appears in the database / Redis stream with correct status
"""

import json
import time
import uuid
from typing import Any

import pytest
import requests


SIGNAL_BRIDGE_URL = "http://localhost:8090"
EXECUTION_CONTROL_URL = "http://localhost:8097"


def post_signal(signal_id: str, symbol: str, direction: str, strength: float) -> requests.Response:
    """
    Post a signal to the signal_bridge service.
    """
    payload = {
        "signal_id": signal_id,
        "symbol": symbol,
        "direction": direction,  # "long" or "short"
        "strength": strength,     # 0.0 to 1.0
        "timestamp": time.time(),
        "source": "integration_test",
    }
    return requests.post(
        f"{SIGNAL_BRIDGE_URL}/signals",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )


def get_signal_status(signal_id: str) -> requests.Response:
    """Query signal_bridge for a signal's status."""
    return requests.get(f"{SIGNAL_BRIDGE_URL}/signals/{signal_id}", timeout=10)


def get_execution_status(signal_id: str) -> requests.Response:
    """Query execution_control for signal execution status."""
    return requests.get(f"{EXECUTION_CONTROL_URL}/executions/{signal_id}", timeout=10)


class TestSignalFlow:
    """
    End-to-end tests for the signal processing pipeline:
    signal_bridge -> execution_control
    """

    @pytest.fixture(autouse=True)
    def setup(self, waitForSignalBridge: bool, waitForExecutionControl: bool):
        assert waitForSignalBridge, "signal_bridge not healthy"
        assert waitForExecutionControl, "execution_control not healthy"

    def test_signal_post_and_bridge_acknowledgement(self):
        """
        Test that posting a signal to signal_bridge returns HTTP 202
        and the signal is stored/trackable.
        """
        signal_id = f"test-signal-{uuid.uuid4().hex[:12]}"
        symbol = "BTC/USDT"
        direction = "long"
        strength = 0.85

        resp = post_signal(signal_id, symbol, direction, strength)
        assert resp.status_code in (200, 201, 202), (
            f"Expected 200/201/202 from signal_bridge, got {resp.status_code}: {resp.text}"
        )

        # Poll signal_bridge until the signal appears
        found = False
        for _ in range(30):  # up to 30 seconds
            resp = get_signal_status(signal_id)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") not in ("pending", "unknown"):
                    found = True
                    break
            time.sleep(1)

        assert found, f"Signal {signal_id} never reached signal_bridge or did not advance past pending state"

    def test_signal_flow_bridge_to_execution(self):
        """
        Test that a posted signal is picked up by execution_control.
        This is the core end-to-end test: signal -> signal_bridge -> execution_control.
        """
        signal_id = f"test-signal-{uuid.uuid4().hex[:12]}"
        symbol = "ETH/USDT"
        direction = "short"
        strength = 0.72

        # Post signal to signal_bridge
        resp = post_signal(signal_id, symbol, direction, strength)
        assert resp.status_code in (200, 201, 202), (
            f"Failed to post signal: {resp.status_code} {resp.text}"
        )

        # Wait for execution_control to receive the signal
        # (polls up to 60 seconds)
        execution_seen = False
        for _ in range(60):
            resp = get_execution_status(signal_id)
            if resp.status_code == 200:
                execution_seen = True
                break
            time.sleep(1)

        assert execution_seen, (
            f"Signal {signal_id} was not processed by execution_control within 60s"
        )

        # Verify execution status fields
        data = resp.json()
        assert data.get("signal_id") == signal_id, f"Unexpected signal_id in execution: {data}"
        assert data.get("symbol") == symbol, f"Unexpected symbol in execution: {data}"

    def test_signal_rejected_on_invalid_direction(self):
        """
        Test that signal_bridge rejects a signal with an invalid direction.
        """
        signal_id = f"test-signal-{uuid.uuid4().hex[:12]}"
        payload = {
            "signal_id": signal_id,
            "symbol": "BTC/USDT",
            "direction": "invalid_direction",  # should be "long" or "short"
            "strength": 0.5,
            "timestamp": time.time(),
            "source": "integration_test",
        }
        resp = requests.post(
            f"{SIGNAL_BRIDGE_URL}/signals",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        # signal_bridge should return 400 Bad Request for invalid input
        assert resp.status_code == 400, (
            f"Expected 400 for invalid direction, got {resp.status_code}: {resp.text}"
        )

    def test_signal_rejected_on_missing_fields(self):
        """
        Test that signal_bridge returns 422 when required fields are missing.
        """
        payload = {
            "signal_id": f"test-signal-{uuid.uuid4().hex[:12]}",
            # missing symbol, direction, strength
            "timestamp": time.time(),
        }
        resp = requests.post(
            f"{SIGNAL_BRIDGE_URL}/signals",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code == 422, (
            f"Expected 422 for missing fields, got {resp.status_code}: {resp.text}"
        )

    def test_batch_signals_flow(self):
        """
        Test posting multiple signals in quick succession and verify
        that execution_control processes all of them.
        """
        num_signals = 5
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT", "LINK/USDT"]
        signal_ids = []

        for i in range(num_signals):
            signal_id = f"test-signal-batch-{uuid.uuid4().hex[:8]}"
            signal_ids.append(signal_id)
            resp = post_signal(signal_id, symbols[i], "long", 0.5 + i * 0.1)
            assert resp.status_code in (200, 201, 202), (
                f"Failed to post batch signal {i}: {resp.status_code} {resp.text}"
            )

        # Wait and verify all signals reached execution_control
        time.sleep(5)  # give services time to process
        seen_count = 0
        for sid in signal_ids:
            resp = get_execution_status(sid)
            if resp.status_code == 200:
                seen_count += 1

        assert seen_count == num_signals, (
            f"Only {seen_count}/{num_signals} batch signals reached execution_control"
        )