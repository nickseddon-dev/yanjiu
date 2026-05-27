
# Runbooks

## Starting All Services

```bash
cd infra/compose
docker-compose up -d
```

## Checking Service Health

```bash
curl http://localhost:8090/health    # signal_bridge
curl http://localhost:8091/health    # data_gateway
curl http://localhost:8094/health    # feature_service
curl http://localhost:8096/health    # risk_control
```

## Kill Switch Triggered

1. Check kill switch status: `GET /kill-switch`
2. Identify the trigger metric
3. Review logs for the affected service
4. Assess whether to reset or halt trading

## Shadow Trading Setup

1. Set `LIVE_HOST_URL` in signal_bridge to the live host NautilusTrader admin endpoint
2. Configure `SHADOW_MODE=true` in execution_control
3. Monitor signals via ops dashboard at `:3000`

## Feature Registration

New features should be registered in `packages/feature_registry/features/`.

## Model Promotion

1. Validate model IC/IR on historical data
2. Register in model_registry with `status=development`
3. Promote via `ModelRegistry.promote(model_id, version)` in research_runner
