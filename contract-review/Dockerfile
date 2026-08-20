FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libxcb1 \
    libxcb-shm0 \
    libx11-6 \
    libxext6 \
    libsm6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    python-multipart \
    minio \
    pymupdf \
    rapidocr_onnxruntime \
    "sqlalchemy[asyncio]>=2.0" \
    asyncpg \
    "psycopg[binary]>=3.2" \
    alembic \
    pydantic-settings \
    itsdangerous
COPY src ./src
ENV PYTHONPATH=/app/src
ENV OCR_PROVIDER=rapid

EXPOSE 8000
CMD ["uvicorn", "contract_review.api:app", "--host", "0.0.0.0", "--port", "8000"]
