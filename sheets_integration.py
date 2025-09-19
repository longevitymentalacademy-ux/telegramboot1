import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- Configuration ---
# The ID of your Google Spreadsheet
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_ID", "1O5b8TxH579zc54G-20Ult5BXflnB5asFcOuf3NInB4w")
# The name of the worksheet to use
WORKSHEET_NAME = "Users"

# Define the scope for the credentials
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# --- Global Variables ---
worksheet = None

def _get_worksheet():
    """Initializes and returns the gspread worksheet object."""
    global worksheet
    if worksheet is not None:
        return worksheet

    try:
        creds = None
        # Try to load credentials from environment variable (for Railway)
        # --- MODIFIED: Check for multiple possible environment variable names ---
        creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON") or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        
        print(f"DEBUG: Found Google credentials environment variable: {bool(creds_json_str)}")

        if creds_json_str:
            try:
                creds_info = json.loads(creds_json_str)
                creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            except json.JSONDecodeError as e:
                print(f"CRITICAL ERROR: Could not parse GOOGLE_CREDENTIALS_JSON. Make sure it's valid JSON. Error: {e}")
                return None
        
        # If env var is not found, fall back to file (for local testing)
        if not creds:
            creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
        
        client = gspread.authorize(creds)
        
        # Open the spreadsheet and select the worksheet
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        return worksheet
    except FileNotFoundError:
        print("CRITICAL ERROR: `service_account.json` not found. Please follow `GOOGLE_SHEETS_SETUP.md`.")
        return None
    except gspread.exceptions.WorksheetNotFound:
        # If the worksheet doesn't exist, create it
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=100, cols=20)
        return worksheet
    except Exception as e:
        print(f"CRITICAL ERROR connecting to Google Sheets: {e}")
        return None

def initialize_spreadsheet():
    """Ensures the spreadsheet has the correct header row."""
    ws = _get_worksheet()
    if not ws:
        return
    
    header = ["User ID", "Day", "Lead Name", "Message ID", "Status"]
    # Check if the first row is empty
    if not ws.row_values(1):
        ws.append_row(header)
        print("📊 Google Sheet header row created.")

def log_user_to_sheets(user_id, username, first_name, last_name, source):
    """Adds a new user or resets an existing user in the spreadsheet."""
    ws = _get_worksheet()
    if not ws:
        return

    lead_name = f"{first_name or ''} {last_name or ''}".strip()
    
    try:
        # Try to find the user in the sheet
        cell = ws.find(str(user_id))
        row_number = cell.row
        
        # If found, update their row to reset them to Day 1
        update_values = [
            user_id,
            1,  # Reset to Day 1
            lead_name,
            "G1",
            "Active"
        ]
        ws.update(f'A{row_number}:E{row_number}', [update_values])
        print(f"🔄 Existing user {user_id} reset to Day 1 in Google Sheet.")

    except gspread.exceptions.CellNotFound:
        # If user is not found, add them as a new row
        new_row = [
            user_id,
            1,  # Starts at Day 1
            lead_name,
            "G1",
            "Active"
        ]
        ws.append_row(new_row)
        print(f"📝 New user {user_id} added to Google Sheet.")
    except Exception as e:
        print(f"CRITICAL ERROR in log_user_to_sheets: {e}")


def update_user_progress(user_id, current_day, message_id):
    """Updates a user's progress in the spreadsheet."""
    ws = _get_worksheet()
    if not ws:
        return

    try:
        cell = ws.find(str(user_id))
        row_number = cell.row
        
        status = "Completed" if current_day >= 30 else "Active"
        
        # Update Day, Message ID, and Status
        ws.update_cell(row_number, 2, current_day)
        ws.update_cell(row_number, 4, message_id)
        ws.update_cell(row_number, 5, status)

    except gspread.exceptions.CellNotFound:
        # This can happen if the user was added before sheets was integrated
        print(f"User {user_id} not found in sheet for updating, skipping.")
    except Exception as e:
        print(f"Error updating user progress in Google Sheets: {e}")

def get_user_stats():
    """Calculates and returns basic statistics from the spreadsheet."""
    ws = _get_worksheet()
    if not ws:
        return None

    try:
        records = ws.get_all_records()
        total_users = len(records)
        
        if total_users == 0:
            return {"total_users": 0, "active_users": 0, "completed_users": 0, "avg_day": 0}

        active_users = sum(1 for record in records if record.get("Status") == "Active")
        completed_users = sum(1 for record in records if record.get("Status") == "Completed")
        total_day = sum(int(record.get("Day", 0)) for record in records)
        avg_day = round(total_day / total_users, 1)

        return {
            "total_users": total_users,
            "active_users": active_users,
            "completed_users": completed_users,
            "avg_day": avg_day,
        }
    except Exception as e:
        print(f"Error getting user stats from Google Sheets: {e}")
        return None
