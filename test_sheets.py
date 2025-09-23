#!/usr/bin/env python3
"""
Simple test script to verify Google Sheets integration works locally.
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sheets_integration import _get_worksheet, log_user_to_sheets

def test_sheets_connection():
    """Test if we can connect to Google Sheets."""
    print("🔍 Testing Google Sheets connection...")
    
    try:
        worksheet = _get_worksheet()
        if worksheet:
            print("✅ Successfully connected to Google Sheets!")
            print(f"📊 Worksheet name: {worksheet.title}")
            print(f"📈 Spreadsheet title: {worksheet.spreadsheet.title}")
            return True
        else:
            print("❌ Failed to connect to Google Sheets")
            return False
    except Exception as e:
        print(f"❌ Error connecting to Google Sheets: {e}")
        return False

def test_user_logging():
    """Test if we can log a test user to the sheet."""
    print("\n🧪 Testing user logging...")
    
    try:
        # Test with fake user data
        test_user_id = 123456789
        test_username = "test_user"
        test_first_name = "Test"
        test_last_name = "User"
        test_source = "local_test"
        
        log_user_to_sheets(
            user_id=test_user_id,
            username=test_username,
            first_name=test_first_name,
            last_name=test_last_name,
            source=test_source
        )
        
        print("✅ Successfully logged test user to Google Sheets!")
        print(f"👤 User ID: {test_user_id}")
        print(f"📝 Username: {test_username}")
        print(f"🏷️ Source: {test_source}")
        return True
        
    except Exception as e:
        print(f"❌ Error logging user to Google Sheets: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Google Sheets Integration Test\n")
    
    # Test connection
    connection_ok = test_sheets_connection()
    
    if connection_ok:
        # Test user logging
        logging_ok = test_user_logging()
        
        if logging_ok:
            print("\n🎉 All tests passed! Google Sheets integration is working.")
            print("📋 Check your Google Sheet to see the test user entry.")
        else:
            print("\n⚠️ Connection works but logging failed.")
    else:
        print("\n❌ Cannot connect to Google Sheets. Check your credentials.")
    
    print(f"\n🔗 Google Sheet URL: https://docs.google.com/spreadsheets/d/1FWg3N2XakXPI5yhVFTMhbCctKMH5XHwdR34-sBszBs4/edit")
