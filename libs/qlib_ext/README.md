
# qlib_ext

Fork of Qlib with custom quant feature extensions.

## Setup

```bash
git clone https://github.com/microsoft/qlib.git qlib_ext
cd qlib_ext
git remote rename origin upstream
git checkout -b upstream-main upstream/main
```

## Custom Extensions

- `quant_features/` - Custom social sentiment features
- `backtest/signal_backtest.py` - Signal-driven backtesting engine

## Integration

qlib_ext is used by the research_runner service for:
- Historical factor computation
- Alpha discovery
- Backtesting against historical signals
