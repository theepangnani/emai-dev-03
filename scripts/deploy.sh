#!/usr/bin/env bash
# Manual deployment script for ClassBridge to Google Cloud Run
# Usage: ./scripts/deploy.sh

set -euo pipefail

PROJECT_ID="emai-dev-01"
REGION="us-central1"
SERVICE="classbridge"
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/classbridge/classbridge"

echo "=== ClassBridge Manual Deploy ==="
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Service: ${SERVICE}"
echo ""

# Ensure correct project
gcloud config set project "${PROJECT_ID}"

# Build and push via Cloud Build
echo "Building and pushing Docker image..."
gcloud builds submit \
  --tag "${IMAGE}:latest" \
  --timeout=600

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE}" \
  --image "${IMAGE}:latest" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --add-cloudsql-instances "${PROJECT_ID}:${REGION}:emai-db" \
  --set-env-vars "ENVIRONMENT=production,LOG_LEVEL=WARNING,LOG_TO_FILE=false" \
  --set-secrets "SECRET_KEY=SECRET_KEY:latest,DATABASE_URL=DATABASE_URL:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest,GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest,SENDGRID_API_KEY=SENDGRID_API_KEY:latest" \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 300

# Show URL
URL=$(gcloud run services describe "${SERVICE}" --region "${REGION}" --format 'value(status.url)')
echo ""
echo "=== Deployed successfully ==="
echo "URL: ${URL}"
