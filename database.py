from datetime import datetime
from typing import Optional, List

# Simple in-memory storage for Railway compatibility
users_data = {}
schedules_data = {}

def initialize_database() -> None:
    """Initialize in-memory storage - no setup needed"""
    print("Database initialized (in-memory)")

class MockRow:
    def __init__(self, data):
        self._data = data
    
    def __getitem__(self, key):
        return self._data.get(key)

def get_conn():
    """Mock connection context manager"""
    class MockConn:
        def execute(self, query, params=None):
            return self
        
        def fetchone(self):
            return None
        
        def __enter__(self):
            return self
        
        def __exit__(self, *args):
            pass
    
    return MockConn()

def upsert_user(user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str], source: Optional[str]) -> None:
    """Store user data in memory"""
    now_iso = datetime.utcnow().isoformat()
    users_data[user_id] = {
        'user_id': user_id,
        'username': username,
        'first_name': first_name,
        'last_name': last_name,
        'source': source,
        'joined_at': now_iso
    }

def get_user(user_id: int) -> Optional[MockRow]:
    """Get user from memory"""
    if user_id in users_data:
        return MockRow(users_data[user_id])
    return None

def get_next_day_to_send(user_id: int) -> int:
    """Get next day to send for user"""
    user_schedules = [s for s in schedules_data.values() if s['user_id'] == user_id and s.get('sent_at')]
    if not user_schedules:
        return 0
    max_day = max(s['day_index'] for s in user_schedules)
    return max_day + 1

def mark_scheduled(user_id: int, day_index: int, scheduled_at_iso: str) -> None:
    """Mark message as scheduled"""
    key = f"{user_id}_{day_index}"
    schedules_data[key] = {
        'user_id': user_id,
        'day_index': day_index,
        'scheduled_at': scheduled_at_iso,
        'sent_at': None
    }

def mark_sent(user_id: int, day_index: int, sent_at_iso: str) -> None:
    """Mark message as sent"""
    key = f"{user_id}_{day_index}"
    if key in schedules_data:
        schedules_data[key]['sent_at'] = sent_at_iso
    else:
        schedules_data[key] = {
            'user_id': user_id,
            'day_index': day_index,
            'scheduled_at': None,
            'sent_at': sent_at_iso
        }

def get_pending_to_reschedule(current_time_iso: str) -> List[MockRow]:
    """Get pending schedules"""
    pending = [s for s in schedules_data.values() if not s.get('sent_at')]
    return [MockRow(s) for s in pending]

def clear_all_schedules_from_db():
    """Clear all schedules"""
    global schedules_data
    schedules_data = {}
    print("All schedules cleared from memory.")