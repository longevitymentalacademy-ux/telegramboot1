import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from database import (
    initialize_database,
    upsert_user,
    get_next_day_to_send,
    mark_scheduled,
    mark_sent,
    get_pending_to_reschedule,
)
from messages import MESSAGES_30_DAYS
try:
    from sheets_integration import (
        initialize_spreadsheet,
        log_user_to_sheets,
        update_user_progress,
        get_user_stats
    )
    SHEETS_ENABLED = True
except ImportError:
    SHEETS_ENABLED = False
    def initialize_spreadsheet(): return True
    def log_user_to_sheets(*args): return True
    def update_user_progress(*args): return True
    def get_user_stats(): return None


TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
DEFAULT_TIME_HOUR = int(os.getenv("DAILY_MESSAGE_HOUR", "9"))  # 9 AM UTC by default
MESSAGE_INTERVAL_HOURS = int(os.getenv("MESSAGE_INTERVAL_HOURS", "2"))  # 2 hours by default
# If set to a positive integer, use hour/minute-based scheduling for testing instead of days
FAST_SCHEDULE_HOURS = int(os.getenv("FAST_SCHEDULE_HOURS", "0"))
FAST_SCHEDULE_MINUTES = int(os.getenv("FAST_SCHEDULE_MINUTES", "0"))


async def send_day_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data or {}
    user_id: int = job_data.get("user_id")
    day_index: int = job_data.get("day_index")
    if user_id is None or day_index is None:
        return

    if 0 <= day_index < len(MESSAGES_30_DAYS):
        text = MESSAGES_30_DAYS[day_index]
    else:
        return

    try:
        await context.bot.send_message(chat_id=user_id, text=text, parse_mode=ParseMode.HTML)
        mark_sent(user_id, day_index)
        
        # Update user progress in Google Sheets
        current_day = day_index + 1  # Convert to 1-based day number
        message_id = f"G{current_day}"  # G1, G2, G3, etc.
        update_user_progress(user_id, current_day, message_id)
        
        # Schedule next day if exists and not already scheduled
        next_day = day_index + 1
        if next_day < len(MESSAGES_30_DAYS):
            # Check if next day is already scheduled
            existing_jobs = context.application.job_queue.get_jobs_by_name(f"daily-{user_id}-{next_day}")
            if not existing_jobs:
                await schedule_day_message(context.application, user_id, next_day)
    except Exception:
        # Intentionally minimal: do not crash job queue for a single failure
        pass


def get_next_run_time_utc(day_number: int, hour_utc: int) -> datetime:
    """Calculate when to send a specific day's message.
    day_number: 1-based day number (Day 2 = day_number 2)
    """
    now = datetime.utcnow()
    if FAST_SCHEDULE_HOURS > 0:
        # Hour-based testing: Day 2 = 1 hour, Day 3 = 2 hours, etc.
        return now + timedelta(hours=FAST_SCHEDULE_HOURS * (day_number - 1))
    if FAST_SCHEDULE_MINUTES > 0:
        # Minute-based testing: Day 2 = 1 minute, Day 3 = 2 minutes, etc.
        return now + timedelta(minutes=FAST_SCHEDULE_MINUTES * (day_number - 1))
    
    # 2-hour interval schedule: Day 2 = 2 hours, Day 3 = 4 hours, etc.
    return now + timedelta(hours=MESSAGE_INTERVAL_HOURS * (day_number - 1))


async def schedule_day_message(app: Application, user_id: int, day_index: int) -> None:
    # Check if job already exists to avoid duplicates
    existing_jobs = app.job_queue.get_jobs_by_name(f"daily-{user_id}-{day_index}")
    if existing_jobs:
        return  # Job already scheduled, skip
    
    # Convert 0-based day_index to 1-based day number for timing calculation
    day_number = day_index + 1  # day_index 1 = Day 2, day_index 2 = Day 3, etc.
    when = get_next_run_time_utc(day_number, DEFAULT_TIME_HOUR)
    mark_scheduled(user_id, day_index, when.isoformat())
    app.job_queue.run_once(
        send_day_message,
        when=when,
        chat_id=user_id,
        name=f"daily-{user_id}-{day_index}",
        data={"user_id": user_id, "day_index": day_index},
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return

    # Deep-link payload like /start tiktok
    source: Optional[str] = None
    if context.args:
        source = context.args[0].strip().lower()

    upsert_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        source=source or "organic",
    )
    
    # Log user to Google Sheets
    log_user_to_sheets(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        source=source or "organic"
    )

    # Clear any existing scheduled jobs for this user to restart fresh
    all_jobs = context.application.job_queue.jobs()
    for job in all_jobs:
        if job.name and job.name.startswith(f"daily-{user.id}-"):
            job.schedule_removal()

    # Reset user progress in database - force restart from Day 1
    from database import get_conn
    with get_conn() as conn:
        # Clear all previous message records for this user
        conn.execute("DELETE FROM schedules WHERE user_id = ?", (user.id,))

    # Always restart from Day 1 when user clicks /start
    # Send Day 1 immediately, then schedule Day 2+
    try:
        if len(MESSAGES_30_DAYS) > 0:
            await context.bot.send_message(chat_id=user.id, text=MESSAGES_30_DAYS[0])
            mark_sent(user.id, 0)
            if SHEETS_ENABLED:
                update_user_progress(user.id, 1, "G1")
            
            # Send Italian notification about automatic messaging
            italian_notification = """
🔔 **Notifica Automatica**

Ora inizierai a ricevere messaggi automatici ogni 2 ore per i prossimi 30 giorni come parte del tuo percorso nella Longevity Mental Academy.

📅 **Programma**: Un messaggio ogni 2 ore
⏰ **Durata**: 30 giorni completi
🎯 **Obiettivo**: La tua trasformazione mentale step by step

Preparati per questo viaggio di crescita personale! 🚀
            """
            await context.bot.send_message(chat_id=user.id, text=italian_notification, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass
    
    # Schedule Day 2 onwards in strict sequence
    if len(MESSAGES_30_DAYS) > 1:
        await schedule_day_message(context.application, user.id, 1)

    origin = f" from {source}" if source else ""
    # Compose welcome text based on schedule mode
    if FAST_SCHEDULE_HOURS > 0:
        schedule_text = f"every {FAST_SCHEDULE_HOURS} hour(s) for testing."
    elif FAST_SCHEDULE_MINUTES > 0:
        schedule_text = f"every {FAST_SCHEDULE_MINUTES} minute(s) for testing."
    else:
        schedule_text = f"every {MESSAGE_INTERVAL_HOURS} hours."
    welcome_text = f"Welcome{origin}! You will receive messages {schedule_text}"
    if update.message:
        await update.message.reply_text(welcome_text)
    else:
        await context.bot.send_message(chat_id=user.id, text=welcome_text)


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await update.message.reply_text("pong")
    except Exception as e:
        print(f"Ping error: {e}")
        try:
            await context.bot.send_message(chat_id=update.effective_user.id, text="pong")
        except Exception as e2:
            print(f"Ping fallback error: {e2}")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user statistics from Google Sheets."""
    stats_data = get_user_stats()
    if stats_data:
        stats_text = f"""📊 **Bot Statistics**

👥 Total Users: {stats_data['total_users']}
🟢 Active Users: {stats_data['active_users']}
✅ Completed Users: {stats_data['completed_users']}
📊 Average Day: {stats_data['avg_day']}"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Unable to fetch statistics at the moment.")


async def reschedule_all_pending(app: Application) -> None:
    # Reschedule any messages that were planned but not sent
    pending = get_pending_to_reschedule(datetime.utcnow().isoformat())
    for row in pending:
        user_id = int(row["user_id"])  # type: ignore[index]
        day_index = int(row["day_index"])  # type: ignore[index]
        # If job already exists, skip
        existing = app.job_queue.get_jobs_by_name(f"daily-{user_id}-{day_index}")
        if existing:
            continue
        # Convert 0-based day_index to 1-based day number
        day_number = day_index + 1
        when = get_next_run_time_utc(day_number, DEFAULT_TIME_HOUR)
        mark_scheduled(user_id, day_index, when.isoformat())
        app.job_queue.run_once(
            send_day_message,
            when=when,
            chat_id=user_id,
            name=f"daily-{user_id}-{day_index}",
            data={"user_id": user_id, "day_index": day_index},
        )


async def on_startup(app: Application) -> None:
    initialize_database()
    
    # TEMPORARY: Clear database on startup (remove this after first deploy)
    import sqlite3
    try:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM schedules')
        cursor.execute('DELETE FROM users')
        conn.commit()
        conn.close()
        print("🗑️ Database cleared on startup!")
    except Exception as e:
        print(f"Database clear error: {e}")
    
    if SHEETS_ENABLED:
        initialize_spreadsheet()  # Initialize Google Sheets only if enabled
    # Ensure polling works even if a webhook was previously set
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    await reschedule_all_pending(app)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = os.getenv(TOKEN_ENV)
    if not token:
        raise RuntimeError(f"Please set {TOKEN_ENV} in your environment.")

    application = (
        Application.builder()
        .token(token)
        .post_init(on_startup)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("stats", stats))

    # Get port from Heroku or use default
    port = int(os.environ.get("PORT", 5000))
    
    # Run the bot
    print(f"Bot starting on port {port}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()


