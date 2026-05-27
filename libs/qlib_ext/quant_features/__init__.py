"""Quant features module for crypto asset analysis.

Provides social sentiment, on-chain, and technical indicator features.
"""

from libs.qlib_ext.quant_features.sentiment import (
    SentimentFeatures,
    compute_social_score,
    compute_bullish_ratio,
    compute_trend_momentum,
    compute_engagement_metrics,
)

from libs.qlib_ext.quant_features.onchain import (
    OnChainFeatures,
    compute_gas_price_gwei,
    compute_active_addresses_24h,
    compute_defi_protocol_tvl,
    compute_nft_volume,
)

from libs.qlib_ext.quant_features.technical import (
    TechnicalFeatures,
    compute_rsi_14,
    compute_macd,
    compute_bollinger_bands,
    compute_volume_ratio,
    compute_price_momentum,
)

__all__ = [
    # Sentiment
    "SentimentFeatures",
    "compute_social_score",
    "compute_bullish_ratio",
    "compute_trend_momentum",
    "compute_engagement_metrics",
    # On-chain
    "OnChainFeatures",
    "compute_gas_price_gwei",
    "compute_active_addresses_24h",
    "compute_defi_protocol_tvl",
    "compute_nft_volume",
    # Technical
    "TechnicalFeatures",
    "compute_rsi_14",
    "compute_macd",
    "compute_bollinger_bands",
    "compute_volume_ratio",
    "compute_price_momentum",
]