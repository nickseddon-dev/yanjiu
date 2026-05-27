"""Tests for feature registry."""
from feature_registry.base import FeatureGroup, FeatureSpec
from feature_registry.registry import FeatureRegistry
from feature_registry.features.hype import X_MENTION_ZSCORE, REDDIT_POST_VELOCITY
from feature_registry.features.sentiment import SENTIMENT_MEAN


def test_register_and_resolve():
    FeatureRegistry.clear()
    FeatureRegistry.register(X_MENTION_ZSCORE)
    resolved = FeatureRegistry.resolve("x_mention_zscore", "1.0")
    assert resolved.name == "x_mention_zscore"
    assert resolved.group == FeatureGroup.HYPE


def test_list_by_group():
    FeatureRegistry.clear()
    FeatureRegistry.register(X_MENTION_ZSCORE)
    FeatureRegistry.register(REDDIT_POST_VELOCITY)
    FeatureRegistry.register(SENTIMENT_MEAN)
    hype_feats = FeatureRegistry.list_by_group(FeatureGroup.HYPE)
    assert len(hype_feats) == 2


def test_feature_spec_serialization():
    d = X_MENTION_ZSCORE.to_dict()
    restored = FeatureSpec.from_dict(d)
    assert restored.name == X_MENTION_ZSCORE.name
    assert restored.group == FeatureGroup.HYPE
