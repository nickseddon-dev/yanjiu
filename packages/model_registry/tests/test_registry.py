"""Tests for model registry."""
from model_registry.base import ModelType, ModelSpec
from model_registry.registry import ModelRegistry


def test_register_and_resolve():
    ModelRegistry.clear()
    spec = ModelSpec(
        model_id="sentiment_classifier_v1",
        model_type=ModelType.CLASSIFIER,
        version="1.0",
        features=("sentiment_mean", "polarity_skew"),
        hyperparams=(("lr", 0.001), ("epochs", 100)),
        metrics=(("accuracy", 0.82), ("f1", 0.79)),
        status="development",
    )
    ModelRegistry.register(spec)
    resolved = ModelRegistry.resolve("sentiment_classifier_v1", "1.0")
    assert resolved.model_id == "sentiment_classifier_v1"
    assert resolved.metrics[0][1] == 0.82


def test_promote():
    ModelRegistry.clear()
    spec = ModelSpec(
        model_id="alpha_model",
        model_type=ModelType.REGRESSOR,
        version="1.0",
        features=("x_mention_zscore",),
        metrics=(("ic", 0.05),),
        status="development",
    )
    ModelRegistry.register(spec)
    promoted = ModelRegistry.promote("alpha_model", "1.0")
    assert promoted.status == "production"
    prod = ModelRegistry.list_by_status("production")
    assert len(prod) == 1
