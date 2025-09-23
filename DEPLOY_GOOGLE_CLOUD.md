# Deploy Telegram Bot to Google Cloud Run

## Prerequisites

1. **Google Cloud CLI installed**: Download from https://cloud.google.com/sdk/docs/install
2. **Authenticated with Google Cloud**: Run `gcloud auth login`
3. **Docker installed** (optional, Cloud Build will handle this)

## Step-by-Step Deployment

### 1. Set up Google Cloud Project

```bash
# Set your project (use your existing project)
gcloud config set project telegram-bot-users-2

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### 2. Deploy the Bot

```bash
# Build and deploy in one command
gcloud builds submit --config cloudbuild.yaml \
  --substitutions _TELEGRAM_BOT_TOKEN="8330039679:AAHDOG-LRHyhplFXRocsn-m6OaKFR805Ar4"
```

### 3. Verify Deployment

```bash
# Check if service is running
gcloud run services list --region=us-central1

# View logs
gcloud logs tail --service=telegram-bot

# Get service URL
gcloud run services describe telegram-bot --region=us-central1 --format="value(status.url)"
```

## Advantages of Google Cloud Run

✅ **Native Google Integration**: Works seamlessly with Google Sheets  
✅ **Service Account**: Uses the same service account automatically  
✅ **Serverless**: Only pay when bot is active  
✅ **Reliable**: Google's infrastructure  
✅ **Easy Scaling**: Handles traffic automatically  
✅ **Better Logging**: Integrated with Google Cloud Logging  

## Environment Variables

The bot will automatically use:
- `TELEGRAM_BOT_TOKEN`: Set during deployment
- Service account credentials: Automatically available in Google Cloud
- `GOOGLE_SHEETS_ID`: Hardcoded in the application

## Testing

Once deployed, test your bot:
1. Send `/envcheck` - Should show Google Sheets connected
2. Send `/start` - Should log user to Google Sheets
3. Check your Google Sheet for new entries

## Troubleshooting

```bash
# View real-time logs
gcloud logs tail --service=telegram-bot --follow

# Redeploy if needed
gcloud builds submit --config cloudbuild.yaml \
  --substitutions _TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
```
