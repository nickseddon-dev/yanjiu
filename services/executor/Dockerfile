FROM python:3.11-slim

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt . 2>/dev/null || \
    pip install --no-cache-dir fastapi uvicorn redis.asyncio httpx pydantic

COPY packages packages
COPY libs libs
COPY services/executor/main.py main.py
COPY services/executor/__init__.py __init__.py

EXPOSE 8100

HEALTHCHECK --interval=15s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8100/health || exit 1

CMD ["python", "main.py"]