"""Tests for risk rules."""
from risk_rules.base import RiskVerdict
from risk_rules.position import SingleSymbolLimit, SingleNarrativeLimit
from risk_rules.venue import VenueExposureLimit
from risk_rules.portfolio import PortfolioVaRLimit, MaxDrawdownLimit


def test_single_symbol_limit_pass():
    rule = SingleSymbolLimit(max_position_pct=0.2)
    state = {
        "positions": {"BTC": {"market_value": 15000.0}},
        "total_value": 100000.0,
    }
    result = rule.check(state)
    assert result.verdict == RiskVerdict.PASS


def test_single_symbol_limit_violation():
    rule = SingleSymbolLimit(max_position_pct=0.2)
    state = {
        "positions": {"BTC": {"market_value": 25000.0}},
        "total_value": 100000.0,
    }
    result = rule.check(state)
    assert result.verdict == RiskVerdict.VIOLATION
    assert result.threshold == 0.2


def test_venue_exposure_limit():
    rule = VenueExposureLimit(max_venue_pct=0.4)
    state = {"venue_exposure": {"binance": 50000.0}, "total_value": 100000.0}
    result = rule.check(state)
    assert result.verdict == RiskVerdict.VIOLATION


def test_var_limit():
    rule = PortfolioVaRLimit(max_var_pct=0.02)
    state = {"portfolio_var_pct": 0.03}
    result = rule.check(state)
    assert result.verdict == RiskVerdict.VIOLATION


def test_drawdown_limit():
    rule = MaxDrawdownLimit(max_drawdown_pct=0.05)
    state = {"current_drawdown_pct": 0.06}
    result = rule.check(state)
    assert result.verdict == RiskVerdict.VIOLATION
