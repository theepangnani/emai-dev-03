# Stage 1: Build frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG BUILD_DATE=unknown
RUN echo "Build date: $BUILD_DATE" && npm run build

# Stage 2: Runtime (no Node.js, no gcc)
FROM python:3.13-slim
WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Copy backend application
COPY app/ ./app/
COPY data/ ./data/
COPY main.py .
COPY alembic.ini .
COPY alembic/ ./alembic/

# Run with gunicorn + uvicorn workers
# Cloud Run sets $PORT (default 8080)
CMD exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 8 --timeout 0 main:app -k uvicorn.workers.UvicornWorker
