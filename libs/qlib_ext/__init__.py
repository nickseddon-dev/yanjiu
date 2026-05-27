"""Qlib extension library for crypto quantitative research.

Provides feature extraction (sentiment, on-chain, technical) and
backtesting capabilities for crypto trading strategies.
"""

from libs.qlib_ext.quant_features import (
    SentimentFeatures,
    OnChainFeatures,
    TechnicalFeatures,
    compute_social_score,
    compute_bullish_ratio,
    compute_trend_momentum,
    compute_engagement_metrics,
    compute_gas_price_gwei,
    compute_active_addresses_24h,
    compute_defi_protocol_tvl,
    compute_nft_volume,
    compute_rsi_14,
    compute_macd,
    compute_bollinger_bands,
    compute_volume_ratio,
    compute_price_momentum,
)

from libs.qlib_ext.backtest import (
    SignalDrivenBacktest,
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    BacktestMetrics,
    DataFetcher,
)

__all__ = [
    # Feature dataclasses
    "SentimentFeatures",
    "OnChainFeatures",
    "TechnicalFeatures",
    # Sentiment functions
    "compute_social_score",
    "compute_bullish_ratio",
    "compute_trend_momentum",
    "compute_engagement_metrics",
    # On-chain functions
    "compute_gas_price_gwei",
    "compute_active_addresses_24h",
    "compute_defi_protocol_tvl",
    "compute_nft_volume",
    # Technical functions
    "compute_rsi_14",
    "compute_macd",
    "compute_bollinger_bands",
    "compute_volume_ratio",
    "compute_price_momentum",
    # Backtest
    "SignalDrivenBacktest",
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "BacktestMetrics",
    "DataFetcher",
]