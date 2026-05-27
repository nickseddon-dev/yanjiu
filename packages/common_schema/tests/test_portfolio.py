"""Tests for portfolio schemas."""
from datetime import datetime, timezone
from common_schema.portfolio import Position, PortfolioState, RiskBudget


def test_position():
    pos = Position(
        symbol="BTCUSDT",
        quantity=0.5,
        avg_entry_price=68000.0,
        market_value=35000.0,
        unrealized_pnl=1000.0,
        realized_pnl=0.0,
    )
    d = pos.to_dict()
    restored = Position.from_dict(d)
    assert restored.quantity == 0.5
    assert restored.unrealized_pnl == 1000.0


def test_portfolio_state():
    pos = Position("BTCUSDT", 0.5, 68000.0, 35000.0, 1000.0, 0.0)
    pf = PortfolioState(
        total_value=100000.0,
        cash=65000.0,
        positions=(("BTCUSDT", pos),),
        total_unrealized_pnl=1000.0,
        total_realized_pnl=0.0,
        leverage=1.0,
    )
    d = pf.to_dict()
    restored = PortfolioState.from_dict(d)
    assert restored.total_value == 100000.0
    assert len(dict(restored.positions)) == 1


def test_risk_budget():
    rb = RiskBudget(
        max_position_pct=0.1,
        max_single_symbol_pct=0.2,
        max_drawdown_pct=0.05,
        max_var_pct=0.02,
    )
    d = rb.to_dict()
    restored = RiskBudget.from_dict(d)
    assert restored.max_drawdown_pct == 0.05
