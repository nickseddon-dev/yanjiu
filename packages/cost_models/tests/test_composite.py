"""Tests for cost models."""
from cost_models.composite import CompositeCostModel


def test_composite_cost():
    model = CompositeCostModel()
    est = model.estimate_cost("BUY", quantity=1.0, price=70000.0)
    assert est.total >= 0
    assert est.fee > 0
    assert est.slippage >= 0


def test_cost_estimate_serialization():
    from cost_models.types import CostEstimate
    est = CostEstimate(fee=1.0, slippage=0.5, impact=0.2, total=1.7)
    d = est.to_dict()
    assert d["fee"] == 1.0
    assert d["total"] == 1.7
