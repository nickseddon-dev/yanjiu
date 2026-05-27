
FROM python:3.11-slim
WORKDIR /app
COPY apps/ops_dashboard /app
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic
EXPOSE 3000
CMD ["python", "-m", "ops_dashboard.main"]
