
# nautilus_ext

Fork of NautilusTrader with custom signal adapter extensions.

## Setup

```bash
git clone https://github.com.nautechsystems/nautilus_trader.git nautilus_ext
cd nautilus_ext
git remote rename origin upstream
git checkout -b upstream-main upstream/main
```

## Custom Extensions

- `adapters/signal_adapter.py` - SignalConsumer for signal-driven order execution
- `risk/signal_risk.py` - Risk rules specific to signal-driven trading
- `replay/signal_replay.py` - Historical signal replay for backtesting

## Integration

The SignalConsumer in `adapters/signal_adapter.py` receives signals from the
research host's SignalBridge via HTTP POST to the live host's admin endpoint.
