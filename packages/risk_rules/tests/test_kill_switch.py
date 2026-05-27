"""Tests for kill switch."""
from risk_rules.kill_switch import KillSwitch


def test_kill_switch_no_trigger():
    ks = KillSwitch()
    state = {"daily_drawdown": 0.02, "data_source_failure": 0, "order_reject_rate": 0.1}
    should_kill, reason = ks.check(state)
    assert should_kill is False


def test_kill_switch_triggered():
    ks = KillSwitch()
    state = {"daily_drawdown": 0.08, "data_source_failure": 0}
    should_kill, reason = ks.check(state)
    assert should_kill is True
    assert "daily_drawdown" in reason


def test_kill_switch_multi_trigger():
    ks = KillSwitch()
    state = {"daily_drawdown": 0.08, "exchange_latency_ms": 3000}
    should_kill, reason = ks.check(state)
    assert should_kill is True


def test_get_trigger_states():
    ks = KillSwitch()
    state = {"daily_drawdown": 0.08, "exchange_latency_ms": 3000}
    triggered = ks.get_trigger_states(state)
    assert len(triggered) == 2
