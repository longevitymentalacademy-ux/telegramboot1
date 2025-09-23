import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- Configuration ---
# The ID of your Google Spreadsheet
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_ID", "1FWg3N2XakXPI5yhVFTMhbCctKMH5XHwdR34-sBszBs4")
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
        print("DEBUG: Attempting to connect to Google Sheets...")
        client = None
        
        # Try Base64 encoded credentials from environment variable first
        encoded_creds = os.getenv("GOOGLE_CREDS") or os.getenv("GOOGLE_CREDENTIALS_BASE64")
        if encoded_creds:
            try:
                import base64
                print("DEBUG: Found Base64 encoded credentials, decoding...")
                decoded_json = base64.b64decode(encoded_creds).decode('utf-8')
                creds_info = json.loads(decoded_json)
                client = gspread.service_account_from_dict(creds_info)
                print("DEBUG: Successfully authenticated with Base64 encoded credentials")
            except Exception as e:
                print(f"CRITICAL ERROR: Failed to decode Base64 credentials. Error: {e}")
                return None
        
        # Fallback: Try local service_account.json file
        if not client:
            try:
                print("DEBUG: Trying local service_account.json file...")
                client = gspread.service_account("service_account.json")
                print("DEBUG: Successfully authenticated with local service_account.json")
            except FileNotFoundError:
                print("CRITICAL ERROR: No credentials found.")
                print("Please set GOOGLE_CREDENTIALS_BASE64 environment variable or add service_account.json file.")
                return None
            except Exception as e:
                print(f"CRITICAL ERROR: Failed to authenticate with service_account.json. Error: {e}")
                return None
        
        # Open the spreadsheet and select the worksheet
        print(f"DEBUG: Opening spreadsheet with ID: {SPREADSHEET_ID}")
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        print(f"DEBUG: Successfully opened worksheet: {WORKSHEET_NAME}")
        return worksheet
        
    except gspread.exceptions.WorksheetNotFound:
        # If the worksheet doesn't exist, create it
        print(f"DEBUG: Worksheet '{WORKSHEET_NAME}' not found, creating it...")
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=100, cols=20)
        print(f"DEBUG: Created new worksheet: {WORKSHEET_NAME}")
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
