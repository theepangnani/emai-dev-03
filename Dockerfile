FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (PostgreSQL client libs + Node.js for frontend build + Tesseract for OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    tesseract-ocr \
    poppler-utils \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build frontend
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci

# Copy frontend source (changes here invalidate the build cache)
COPY frontend/ ./frontend/
ARG BUILD_DATE=unknown
RUN echo "Build date: $BUILD_DATE" && cd frontend && npm run build

# Copy backend application
COPY app/ ./app/
COPY data/ ./data/
COPY main.py .
COPY alembic.ini .
COPY alembic/ ./alembic/

# Run with gunicorn + uvicorn workers
# Cloud Run sets $PORT (default 8080)
CMD exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 8 --timeout 0 main:app -k uvicorn.workers.UvicornWorker
