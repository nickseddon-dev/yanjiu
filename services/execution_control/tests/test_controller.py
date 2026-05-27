
from execution_control.main import ExecutionController, EntrySignal


def test_approved():
    ctrl = ExecutionController(min_confidence=0.65)
    d = ctrl.evaluate(EntrySignal(symbol="BTC", direction="LONG", confidence=0.8))
    assert d.decision == "APPROVED"


def test_rejected():
    ctrl = ExecutionController(min_confidence=0.65)
    d = ctrl.evaluate(EntrySignal(symbol="BTC", direction="LONG", confidence=0.5))
    assert d.decision == "REJECTED"


def test_blocked():
    ctrl = ExecutionController(min_confidence=0.65, blocklist={"BTC"})
    d = ctrl.evaluate(EntrySignal(symbol="BTC", direction="LONG", confidence=0.8))
    assert d.decision == "BLOCKED"
