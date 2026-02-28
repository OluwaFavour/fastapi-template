# ── Base stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ── API server ────────────────────────────────────────────────────────────
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── RabbitMQ worker ───────────────────────────────────────────────────────
FROM base AS worker
CMD ["python", "-m", "app.infrastructure.messaging.main"]

# ── Scheduler ─────────────────────────────────────────────────────────────
FROM base AS scheduler
CMD ["python", "-m", "app.infrastructure.scheduler.main"]
