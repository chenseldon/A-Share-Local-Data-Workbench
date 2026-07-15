FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/pyproject.toml /app/backend/pyproject.toml

RUN pip install --no-cache-dir \
    "duckdb>=1.0.0" \
    "fastapi>=0.111.0" \
    "httpx>=0.27.0" \
    "pydantic>=2.7.0" \
    "uvicorn[standard]>=0.30.0"

COPY backend/app /app/backend/app

RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
