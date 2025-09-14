import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import Optional
import json

# Google Sheets configuration
SCOPES = ["https://www.googleapis.com/spreadsheets", "https://www.googleapis.com/drive"]
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_ID", "1FwQ5eUYyyyKhSzB447VJ4osT_XiQ_GAoOhRc24wiR4k")
WORKSHEET_NAME = "Foglio1"  # Sheet tab name


def get_sheets_client():
    """Initialize Google Sheets client using service account credentials."""
    try:
        # Try to get credentials from environment variable (JSON string)
        creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if creds_json:
            creds_info = json.loads(creds_json)
            credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        else:
            # Fallback to service account file
            credentials = Credentials.from_service_account_file(
                "service_account.json", scopes=SCOPES
            )
        
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        print(f"Error connecting to Google Sheets: {e}")
        return None


def initialize_spreadsheet():
    """Initialize the spreadsheet - headers already exist in your sheet."""
    try:
        client = get_sheets_client()
        if not client or not SPREADSHEET_ID:
            return False
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        
        # Your sheet already has headers: User ID, Day, Lead Name, Message ID, Status
        # No need to add headers
        print("Connected to existing Google Sheet successfully!")
        return True
    except Exception as e:
        print(f"Error connecting to spreadsheet: {e}")
        return False


def log_user_to_sheets(user_id: int, username: Optional[str], first_name: Optional[str], 
                      last_name: Optional[str], source: Optional[str]):
    """Log new user data to Google Sheets matching your column structure."""
    try:
        client = get_sheets_client()
        if not client or not SPREADSHEET_ID:
            return False
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        
        # Check if user already exists (check column A for User ID)
        all_values = worksheet.get_all_values()
        existing_row = None
        row_index = None
        
        for i, row in enumerate(all_values[1:], start=2):  # Skip header row
            if row and str(row[0]) == str(user_id):  # Column A = User ID
                existing_row = row
                row_index = i
                break
        
        # Create lead name from first name and last name
        lead_name = f"{first_name or ''} {last_name or ''}".strip()
        if not lead_name:
            lead_name = username or f"User_{user_id}"
        
        if existing_row:
            # Update existing user - just update the status to show they're active
            worksheet.update_cell(row_index, 5, "Active")  # Column E = Status
        else:
            # Add new user - find first empty row
            next_row = len(all_values) + 1
            new_row = [
                user_id,        # Column A: User ID
                1,              # Column B: Day (starting at day 1)
                lead_name,      # Column C: Lead Name
                "",             # Column D: Message ID (will be filled when messages are sent)
                "Active"        # Column E: Status
            ]
            
            # Insert the new row
            worksheet.insert_row(new_row, next_row)
        
        return True
    except Exception as e:
        print(f"Error logging user to sheets: {e}")
        return False


def update_user_progress(user_id: int, current_day: int, message_id: Optional[str] = None):
    """Update user's progress in your spreadsheet structure."""
    try:
        client = get_sheets_client()
        if not client or not SPREADSHEET_ID:
            return False
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        
        # Find the user's row
        all_values = worksheet.get_all_values()
        for i, row in enumerate(all_values[1:], start=2):  # Skip header row
            if row and str(row[0]) == str(user_id):  # Column A = User ID
                # Update Day (Column B) and Message ID (Column D)
                worksheet.update_cell(i, 2, current_day)  # Column B: Day
                if message_id:
                    worksheet.update_cell(i, 4, message_id)  # Column D: Message ID
                
                # Update status based on progress
                if current_day >= 30:
                    worksheet.update_cell(i, 5, "Completed")  # Column E: Status
                else:
                    worksheet.update_cell(i, 5, f"Active - Day {current_day}")
                
                return True
        
        return False
    except Exception as e:
        print(f"Error updating user progress: {e}")
        return False


def get_user_stats():
    """Get basic statistics from your spreadsheet."""
    try:
        client = get_sheets_client()
        if not client or not SPREADSHEET_ID:
            return None
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        
        all_values = worksheet.get_all_values()
        if len(all_values) <= 1:  # Only headers or empty
            return {"total_users": 0, "active_users": 0, "completed_users": 0, "avg_day": 0}
        
        user_data = all_values[1:]  # Skip header row
        total_users = len([row for row in user_data if row and row[0]])  # Count rows with User ID
        
        active_users = 0
        completed_users = 0
        days_sum = 0
        
        for row in user_data:
            if row and len(row) >= 5:
                status = row[4] if len(row) > 4 else ""  # Column E: Status
                day = row[1] if len(row) > 1 else "1"    # Column B: Day
                
                if "Active" in status:
                    active_users += 1
                elif "Completed" in status:
                    completed_users += 1
                
                try:
                    days_sum += int(day) if day.isdigit() else 1
                except:
                    days_sum += 1
        
        avg_day = round(days_sum / total_users, 1) if total_users > 0 else 0
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "completed_users": completed_users,
            "avg_day": avg_day
        }
    except Exception as e:
        print(f"Error getting user stats: {e}")
        return None
