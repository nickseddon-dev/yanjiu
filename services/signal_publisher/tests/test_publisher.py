
import asyncio
from signal_publisher.main import SignalPublisher, Signal


def test_signal_creation():
    s = Signal(symbol="BTC", direction="LONG", confidence=0.7)
    assert s.signal_id
    assert s.symbol == "BTC"
    d = s.model_dump(mode="json")
    assert d["symbol"] == "BTC"


def test_publisher_queue():
    async def run():
        pub = SignalPublisher()
        s = Signal(symbol="BTC", direction="LONG")
        await pub.publish(s)
        assert pub.get_queue_size() == 1
        await pub.stop()
    asyncio.run(run())
