#!/bin/bash

# Google Cloud deployment script for Telegram Bot
# Make sure you have gcloud CLI installed and authenticated

set -e

# Configuration
PROJECT_ID="telegram-bot-users-2"  # Your existing Google Cloud project
SERVICE_NAME="telegram-bot"
REGION="us-central1"
TELEGRAM_BOT_TOKEN="8330039679:AAHDOG-LRHyhplFXRocsn-m6OaKFR805Ar4"

echo "🚀 Deploying Telegram Bot to Google Cloud Run..."

# Set the project
echo "📋 Setting project to $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build and deploy using Cloud Build
echo "🏗️ Building and deploying with Cloud Build..."
gcloud builds submit --config cloudbuild.yaml \
  --substitutions _TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN"

# Get the service URL
echo "🌐 Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo "✅ Deployment complete!"
echo "🔗 Service URL: $SERVICE_URL"
echo "🤖 Your bot is now running on Google Cloud Run!"
echo ""
echo "📝 Next steps:"
echo "1. Test your bot with /envcheck"
echo "2. The service account credentials should work automatically"
echo "3. Check logs with: gcloud logs tail --service=$SERVICE_NAME"
