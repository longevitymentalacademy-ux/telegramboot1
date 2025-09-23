import os
import logging
from datetime import datetime, timedelta, time
from typing import Optional, List, Tuple
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import sqlite3
import pytz

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from database import (
    initialize_database,
    upsert_user,
    get_next_day_to_send,
    mark_scheduled,
    mark_sent,
    get_pending_to_reschedule,
    clear_all_schedules_from_db,
)
from messages import MESSAGES_30_DAYS
from sheets_integration import (
    initialize_spreadsheet,
    log_user_to_sheets,
    update_user_progress,
    get_user_stats
)


# --- Configuration ---
# Your bot token from BotFather
# Trigger redeploy to pick up env vars
TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
# TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# if not TELEGRAM_BOT_TOKEN:
#     raise RuntimeError("Please set TELEGRAM_BOT_TOKEN in your environment.")

# --- Scheduling ---
# How many hours between messages. For production, this should be 24.
# MESSAGE_INTERVAL_HOURS = int(os.getenv("MESSAGE_INTERVAL_HOURS", 24))

# --- Timezone & Time ---
TARGET_TIMEZONE = "Europe/Rome"
TARGET_HOUR = 8
TARGET_MINUTE = 0


# --- Database ---
DB_FILE = "bot_database.db"


# --- Scheduling Logic ---
def get_next_run_time() -> datetime:
    """Calculates the next 8:00 AM in Italy time and returns it as a timezone-aware object."""
    tz = pytz.timezone(TARGET_TIMEZONE)
    now = datetime.now(tz)
    
    # Target time is 8:00 AM
    target_time = time(TARGET_HOUR, TARGET_MINUTE)
    
    # Today's target time in the specified timezone
    next_run = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    
    # If it's already past the target time today, schedule for the target time tomorrow
    if now >= next_run:
        next_run += timedelta(days=1)
        
    return next_run

async def schedule_day_message(app: Application, user_id: int, day_index: int) -> None:
    """Schedules a message for a given day to be sent at the next TARGET_TIME."""
    # Check if job already exists to avoid duplicates
    existing_jobs = app.job_queue.get_jobs_by_name(f"daily-{user_id}-{day_index}")
    if existing_jobs:
        print(f"Job daily-{user_id}-{day_index} already exists. Skipping schedule.")
        return

    # Calculate when to send this message (8 AM Italy Time)
    when = get_next_run_time()
    
    print(f"Scheduling message for user {user_id}, day {day_index + 1} at {when} ({when.astimezone(pytz.utc)} UTC)")
    
    # Mark as scheduled in the database using UTC time
    mark_scheduled(user_id, day_index, when.astimezone(pytz.utc).isoformat())
    
    app.job_queue.run_once(
        send_day_message,
        when=when,
        chat_id=user_id,
        name=f"daily-{user_id}-{day_index}",
        data={"user_id": user_id, "day_index": day_index},
    )


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
        mark_sent(user_id, day_index, datetime.now(pytz.utc).isoformat())
        
        # Update Google Sheet (always try to update)
        try:
            day_number = day_index + 1
            message_id = f"G{day_number}"
            update_user_progress(user_id, day_number, message_id)
        except Exception as e:
            print(f"Warning: Failed to update Google Sheets: {e}")

        # Schedule next day if it exists
        next_day_index = day_index + 1
        if next_day_index < len(MESSAGES_30_DAYS):
            # Schedule next message for 8 AM the following day
            await schedule_day_message(context.application, user_id, next_day_index)
    except Exception:
        # Intentionally minimal: do not crash job queue for a single failure
        pass


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
    try:
        log_user_to_sheets(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            source=source or "organic"
        )
    except Exception as e:
        print(f"Warning: Failed to log user to Google Sheets: {e}")

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
            mark_sent(user.id, 0, datetime.now(pytz.utc).isoformat())

            # Update Google Sheet for Day 1
            try:
                log_user_to_sheets(user.id, user.username, user.first_name, user.last_name, source)
            except Exception as e:
                print(f"Warning: Failed to log user to Google Sheets: {e}")

            # Send Italian notification about the schedule
            italian_notification = """
🔔 **Notifica Automatica**

Ora inizierai a ricevere messaggi automatici ogni 2 ore per i prossimi 30 giorni come parte del tuo percorso nella Longevity Mental Academy.

📅 **Programma**: Un messaggio ogni 2 ore
⏰ **Durata**: 30 giorni completi
🎯 **Obiettivo**: La tua trasformazione mentale step by step

Preparati per questo viaggio di crescita personale! 🚀
            """
            await context.bot.send_message(chat_id=user.id, text=italian_notification, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("No messages configured for this bot.")
    except Exception:
        pass
    
    # Schedule Day 2 for 8 AM tomorrow (Italy Time)
    if len(MESSAGES_30_DAYS) > 1:
        await schedule_day_message(context.application, user.id, 1) # day_index=1 is Day 2

    origin = f" from {source}" if source else ""
    # Compose welcome text based on schedule mode
    schedule_text = f"every day at 8:00 AM Italy time."
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
    for user_id, day_index, scheduled_time_iso in pending:
        try:
            # The job name must be unique
            job_name = f"daily-{user_id}-{day_index}"

            # Avoid rescheduling if a job with the same name already exists
            if app.job_queue.get_jobs_by_name(job_name):
                print(f"Job {job_name} already in queue. Skipping reschedule.")
                continue

            scheduled_time_utc = datetime.fromisoformat(scheduled_time_iso).replace(tzinfo=pytz.utc)
            
            app.job_queue.run_once(
                send_day_message,
                when=scheduled_time_utc,
                chat_id=user_id,
                name=job_name,
                data={"user_id": user_id, "day_index": day_index},
            )
            print(f"Rescheduled message for user {user_id}, day {day_index + 1} for {scheduled_time_utc}")
        except Exception as e:
            print(f"Failed to reschedule for user {user_id}, day {day_index}: {e}")


async def on_startup(app: Application) -> None:
    initialize_database()
    try:
        initialize_spreadsheet()  # Initialize Google Sheets
        print("📊 Google Sheets integration initialized.")
    except Exception as e:
        print(f"⚠️ WARNING: Google Sheets initialization failed: {e}")
        print("Bot will run without Google Sheets functionality.")

    # Production deployment - database persists across restarts
    print("🚀 Bot starting...")
    
    # Ensure polling works even if a webhook was previously set
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    await reschedule_all_pending(app)


# --- Admin Command ---
ADMIN_IDS = [5170262928, 6136713410]  # Your user ID is added for admin commands

async def check_env(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a list of relevant environment variables (admin only)."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    message = "🔍 **Environment Variables on Server**\n\n"
    
    # Check for the variables we care about
    google_id = os.getenv("GOOGLE_SHEETS_ID", "Not Set")
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    # interval = os.getenv("MESSAGE_INTERVAL_HOURS", "Not Set") # This is no longer used
    
    message += f"`GOOGLE_SHEETS_ID`: `{google_id}`\n"
    # message += f"`MESSAGE_INTERVAL_HOURS`: `{interval}`\n\n"
    
    message += f"\n*Time Settings:*\n"
    message += f"`Timezone`: `{TARGET_TIMEZONE}`\n"
    message += f"`Scheduled Time`: `{TARGET_HOUR:02d}:{TARGET_MINUTE:02d}`\n\n"
    
    message += f"*Credentials Check:*\n"
    message += f"`GOOGLE_CREDENTIALS_JSON`: `{'Present' if creds_json else 'Not Found'}`\n"
    message += f"`GOOGLE_SERVICE_ACCOUNT_JSON`: `{'Present' if service_account_json else 'Not Found'}`\n\n"

    if not creds_json and not service_account_json:
        message += "⚠️ **CRITICAL: No Google credentials variable was found!**"
    else:
        message += "✅ A Google credentials variable was found."

    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2)


async def check_env_public(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Public, safe env check that reports only presence flags."""
    # Check environment variables and local file
    base64_creds = os.getenv("GOOGLE_CREDENTIALS_BASE64")
    service_account_exists = os.path.exists("service_account.json")
    
    # Debug: List all environment variables that contain "GOOGLE" or "CRED"
    import os
    google_vars = [key for key in os.environ.keys() if "GOOGLE" in key.upper() or "CRED" in key.upper()]
    
    # Check Google Sheets connection
    try:
        from sheets_integration import _get_worksheet
        worksheet = _get_worksheet()
        sheets_connected = worksheet is not None
    except Exception:
        sheets_connected = False
    
    lines = [
        "Env check (safe):",
        f"Base64 Credentials: {'Set' if base64_creds else 'Not Set'}",
        f"Local File: {'Found' if service_account_exists else 'Not Found'}",
        f"Google Sheets: {'Connected' if sheets_connected else 'Not Connected'}",
        f"Timezone: {TARGET_TIMEZONE}",
        f"Schedule: {TARGET_HOUR:02d}:{TARGET_MINUTE:02d}",
        f"Google/Cred vars found: {len(google_vars)}",
        f"Vars: {', '.join(google_vars[:3]) if google_vars else 'None'}",
    ]
    await update.message.reply_text("\n".join(lines))

async def clear_all_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears all scheduled jobs from the job queue and database (admin only)."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    # Clear from APScheduler
    jobs = context.application.job_queue.jobs()
    num_jobs = len(jobs)
    for job in jobs:
        job.schedule_removal()
    
    # Clear from database
    clear_all_schedules_from_db()
    
    await update.message.reply_text(f"✅ All {num_jobs} scheduled jobs have been cleared from the queue and the database.")


# --- Main Application ---
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

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("env", check_env, filters=filters.User(user_id=ADMIN_IDS)))
    application.add_handler(CommandHandler("clearschedules", clear_all_schedules, filters=filters.User(user_id=ADMIN_IDS)))
    application.add_handler(CommandHandler("envcheck", check_env_public))

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()


