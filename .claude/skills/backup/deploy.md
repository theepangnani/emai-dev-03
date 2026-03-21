# /deploy - Deploy to Google Cloud Platform

Deploy the EMAI application to Google Cloud Platform.

## Prerequisites

1. Google Cloud SDK installed
2. Project created in GCP Console
3. Required APIs enabled:
   - Cloud Run
   - Cloud SQL
   - Cloud Storage
   - Secret Manager

## Instructions

### 1. Set Up GCP Project

```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable sql-component.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### 2. Create Cloud SQL Instance (PostgreSQL)

```bash
# Create PostgreSQL instance
gcloud sql instances create emai-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# Create database
gcloud sql databases create emai --instance=emai-db

# Create user
gcloud sql users create emai-user \
  --instance=emai-db \
  --password=YOUR_PASSWORD
```

### 3. Store Secrets

```bash
# Store secrets in Secret Manager
echo -n "your-secret-key" | gcloud secrets create SECRET_KEY --data-file=-
echo -n "sk-your-openai-key" | gcloud secrets create OPENAI_API_KEY --data-file=-
echo -n "your-google-client-id" | gcloud secrets create GOOGLE_CLIENT_ID --data-file=-
echo -n "your-google-client-secret" | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=-
```

### 4. Create Backend Dockerfile

Create `Dockerfile` in project root:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install psycopg2-binary gunicorn

# Copy application
COPY . .

# Run with gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app -k uvicorn.workers.UvicornWorker
```

### 5. Deploy Backend to Cloud Run

```bash
# Build and push image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/emai-backend

# Deploy to Cloud Run
gcloud run deploy emai-backend \
  --image gcr.io/YOUR_PROJECT_ID/emai-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances YOUR_PROJECT_ID:us-central1:emai-db \
  --set-env-vars "DATABASE_URL=postgresql://emai-user:PASSWORD@/emai?host=/cloudsql/YOUR_PROJECT_ID:us-central1:emai-db" \
  --set-secrets "SECRET_KEY=SECRET_KEY:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest,GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest"
```

### 6. Deploy Frontend to Cloud Storage

```bash
# Build frontend
cd frontend
npm run build

# Create bucket
gsutil mb gs://YOUR_PROJECT_ID-frontend

# Upload files
gsutil -m cp -r dist/* gs://YOUR_PROJECT_ID-frontend

# Make public
gsutil iam ch allUsers:objectViewer gs://YOUR_PROJECT_ID-frontend

# Configure as website
gsutil web set -m index.html -e index.html gs://YOUR_PROJECT_ID-frontend
```

### 7. Set Up Load Balancer (Optional)

For custom domain with HTTPS:

```bash
# Create backend bucket for frontend
gcloud compute backend-buckets create emai-frontend \
  --gcs-bucket-name=YOUR_PROJECT_ID-frontend \
  --enable-cdn

# Create URL map, SSL cert, and forwarding rules
# (See GCP documentation for full setup)
```

## Environment Variables for Production

```env
# Backend (.env or Secret Manager)
DATABASE_URL=postgresql://user:pass@/db?host=/cloudsql/project:region:instance
SECRET_KEY=<secure-random-string>
OPENAI_API_KEY=sk-...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://api.classbridge.ca/api/google/callback
FRONTEND_URL=https://classbridge.ca
```

## CI/CD with GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to GCP

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_CREDENTIALS }}

      - name: Deploy to Cloud Run
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: emai-backend
          region: us-central1
          source: .

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Frontend
        run: |
          cd frontend
          npm ci
          npm run build

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_CREDENTIALS }}

      - name: Upload to GCS
        run: |
          gsutil -m rsync -r frontend/dist gs://YOUR_PROJECT_ID-frontend
```

## Rollback

```bash
# List revisions
gcloud run revisions list --service emai-backend

# Rollback to previous revision
gcloud run services update-traffic emai-backend \
  --to-revisions REVISION_NAME=100
```

## Monitoring

```bash
# View logs
gcloud run services logs read emai-backend

# View metrics in Console
# https://console.cloud.google.com/run
```

## Related Issues

- GitHub Issue #13: GCP Deployment & CI/CD Setup
- GitHub Issue #24: Domain Registration (classbridge.ca)
