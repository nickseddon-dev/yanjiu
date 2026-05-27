FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY packages/common_schema /packages/common_schema
COPY packages/event_schema /packages/event_schema
COPY packages/feature_registry /packages/feature_registry
COPY packages/model_registry /packages/model_registry
COPY packages/risk_rules /packages/risk_rules
COPY packages/cost_models /packages/cost_models
COPY packages/adapters /packages/adapters
COPY services/orchestrator /app

RUN pip install --no-cache-dir -e /packages/common_schema \
    -e /packages/event_schema \
    -e /packages/feature_registry \
    -e /packages/model_registry \
    -e /packages/risk_rules \
    -e /packages/cost_models \
    -e /packages/adapters

RUN pip install --no-cache-dir prefect fastapi uvicorn

CMD ["python", "-m", "orchestrator.main"]
