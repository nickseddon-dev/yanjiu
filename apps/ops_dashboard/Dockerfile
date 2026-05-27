
FROM python:3.11-slim
WORKDIR /app
COPY apps/ops_dashboard /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic
EXPOSE 3000
CMD ["python", "-m", "ops_dashboard.main"]
