
# Architecture

## System Overview

quant-os is a crypto social-sentiment driven quantitative trading system with two physically separate hosts:

1. **Research / Signal Host** - where signals are generated from social sentiment analysis
2. **Live / Execution Host** - where NautilusTrader executes trades based on signals

```
[Social Data] → [Data Gateway] → [Event Gateway] → [Feature Service] → [Execution Control]
                                                                    ↓
                                                           [Signal Publisher]
                                                                    ↓
                                                         [Signal Bridge] (HTTP)
                                                                    ↓
                                                      [Live Host: NautilusTrader]
```

## Host Separation

Research host (`:8090` etc.) and Live host (NautilusTrader) are physically separate.
Signal delivery is via Signal Bridge → HTTP POST → NautilusTrader admin endpoint.

## Feature Groups

| Group | Features |
|-------|----------|
| HYPE | x_mention_zscore, reddit_post_velocity |
| SENTIMENT | sentiment_mean, polarity_skew, sentiment_velocity |
| DIVERGENCE | bull_bear_ratio, neutral_ratio |
| DIFFUSION | cross_platform_speed, peak_heat_time |
| EXPECTATION | polymarket_delta, prob_jump_magnitude |

## Risk Dimensions

- SINGLE_SYMBOL: Single symbol max position (20%)
- SINGLE_NARRATIVE: Single narrative max exposure (30%)
- VENUE_EXPOSURE: Single venue max exposure (40%)
- PORTFOLIO_VAR: Portfolio VaR max (2%)
- DRAWDOWN: Max drawdown (5%)
- DATA_SOURCE: Data source failure monitoring
- LATENCY: Exchange latency monitoring

## Kill Switch Triggers

| Metric | Threshold |
|--------|-----------|
| Daily Drawdown | > 5% |
| Data Source Failures | >= 2 |
| Order Reject Rate | > 30% |
| Exchange Latency | > 2000ms |
