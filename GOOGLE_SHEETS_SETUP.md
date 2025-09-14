# Google Sheets Integration Setup

This guide will help you connect your Telegram bot to Google Sheets for real-time user data tracking.

## Step 1: Create Google Sheets Spreadsheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new spreadsheet
3. Name it "Telegram Bot Users" or similar
4. Copy the spreadsheet ID from the URL:
   - URL: `https://docs.google.com/spreadsheets/d/1ABC123XYZ789/edit`
   - ID: `1ABC123XYZ789`

## Step 2: Create Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing one
3. Enable the Google Sheets API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Sheets API" and enable it
   - Search for "Google Drive API" and enable it

4. Create Service Account:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Name it "telegram-bot-sheets"
   - Click "Create and Continue"
   - Skip role assignment, click "Continue"
   - Click "Done"

5. Generate JSON Key:
   - Click on your service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create New Key"
   - Choose "JSON" format
   - Download the JSON file

## Step 3: Share Spreadsheet with Service Account

1. Open the downloaded JSON file
2. Copy the `client_email` value (looks like: `telegram-bot-sheets@project-123.iam.gserviceaccount.com`)
3. In your Google Spreadsheet:
   - Click "Share" button
   - Paste the service account email
   - Give it "Editor" permissions
   - Click "Send"

## Step 4: Set Environment Variables

### For Local Testing:
```powershell
# Set the spreadsheet ID
$env:GOOGLE_SHEETS_ID="1ABC123XYZ789"

# Set the service account JSON (entire JSON content as one line)
$env:GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"your-project"...}'
```

### For Railway Deployment:
1. Go to your Railway project
2. Add environment variables:
   - `GOOGLE_SHEETS_ID` = `1ABC123XYZ789`
   - `GOOGLE_SERVICE_ACCOUNT_JSON` = `{"type":"service_account","project_id":"your-project"...}`

## Step 5: Test Integration

Run your bot and send `/start` - you should see a new row appear in your spreadsheet with:
- User ID
- Username
- First Name
- Last Name
- Source (tiktok/organic)
- Join Date
- Last Message Date
- Current Day
- Total Messages
- Status

## Available Commands

- `/stats` - View user statistics from the spreadsheet
- `/start` - Register user and begin 30-day sequence
- `/ping` - Test bot connectivity

## Spreadsheet Columns

| Column | Description |
|--------|-------------|
| User ID | Telegram user ID |
| Username | @username |
| First Name | User's first name |
| Last Name | User's last name |
| Source | tiktok/organic |
| Joined At | When user first started |
| Last Message | Last interaction time |
| Current Day | Which day they're on (1-30) |
| Total Messages | How many messages received |
| Status | Active/Completed |

Your spreadsheet will automatically update in real-time as users interact with your bot! 📊
