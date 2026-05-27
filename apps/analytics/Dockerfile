FROM python:3.11-slim
WORKDIR /app
COPY apps/analytics /app
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic
EXPOSE 3010
CMD ["python", "-m", "analytics.main"]