
from risk_control.main import RiskControlService, RiskState
from datetime import datetime, timezone


def test_kill_switch_not_triggered():
    svc = RiskControlService()
    svc.update_state(RiskState(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_value=100000, daily_pnl_pct=0.01, current_drawdown_pct=0.02,
        portfolio_var_pct=0.01, positions={}, venue_exposure={}, narrative_exposure={},
    ))
    triggered, reason = svc.check_kill_switch()
    assert triggered is False


def test_kill_switch_triggered():
    svc = RiskControlService()
    svc.update_state(RiskState(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_value=100000, daily_pnl_pct=-0.08, current_drawdown_pct=0.08,
        portfolio_var_pct=0.03, positions={}, venue_exposure={}, narrative_exposure={},
    ))
    triggered, reason = svc.check_kill_switch()
    assert triggered is True
    assert "drawdown" in reason


def test_violations():
    svc = RiskControlService()
    state = RiskState(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_value=100000, daily_pnl_pct=-0.01, current_drawdown_pct=0.06,
        portfolio_var_pct=0.03, positions={}, venue_exposure={}, narrative_exposure={},
    )
    violations = svc.get_violations(state)
    assert len(violations) >= 2
