FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/proxy-hub/backend/pyproject.toml ./pyproject.toml
COPY services/proxy-hub/backend/README.md ./README.md
COPY services/proxy-hub/backend/proxy_hub ./proxy_hub
COPY services/proxy-hub/backend/alembic.ini ./alembic.ini
COPY services/proxy-hub/backend/migrations ./migrations

RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 proxyhub \
    && chown -R proxyhub:proxyhub /app

USER proxyhub

EXPOSE 8000

CMD ["uvicorn", "proxy_hub.app:app", "--host", "0.0.0.0", "--port", "8000"]
