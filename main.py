import os
import logging
from datetime import datetime, timedelta
from typing import Optional

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


TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
DEFAULT_TIME_HOUR = int(os.getenv("DAILY_MESSAGE_HOUR", "9"))  # 9 AM UTC by default
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


def get_next_run_time_utc(days_from_now: int, hour_utc: int) -> datetime:
    now = datetime.utcnow()
    if FAST_SCHEDULE_HOURS > 0:
        # Hour-based acceleration for testing: each message is 1 hour after the previous
        return now + timedelta(hours=FAST_SCHEDULE_HOURS)
    if FAST_SCHEDULE_MINUTES > 0:
        # Minute-based acceleration for testing: each message is 1 minute after the previous
        return now + timedelta(minutes=FAST_SCHEDULE_MINUTES)
    # Normal daily schedule: each message is 1 day after the previous
    target = datetime(year=now.year, month=now.month, day=now.day, hour=hour_utc, minute=0)
    if target <= now:
        target = target + timedelta(days=1)
    target = target + timedelta(days=days_from_now)
    return target


async def schedule_day_message(app: Application, user_id: int, day_index: int) -> None:
    # Check if job already exists to avoid duplicates
    existing_jobs = app.job_queue.get_jobs_by_name(f"daily-{user_id}-{day_index}")
    if existing_jobs:
        return  # Job already scheduled, skip
    
    when = get_next_run_time_utc(days_from_now=day_index, hour_utc=DEFAULT_TIME_HOUR)
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

    # Determine the next day to send (0-based)
    next_day = get_next_day_to_send(user.id)
    if next_day >= len(MESSAGES_30_DAYS):
        if update.message:
            await update.message.reply_text("You’ve already completed the 30-day series. 🎉")
        else:
            await context.bot.send_message(chat_id=user.id, text="You’ve already completed the 30-day series. 🎉")
        return

    # Always start from Day 1 when user clicks /start
    # Send Day 1 immediately, then schedule Day 2+
    try:
        if 0 < len(MESSAGES_30_DAYS):
            await context.bot.send_message(chat_id=user.id, text=MESSAGES_30_DAYS[0])
            mark_sent(user.id, 0)
    except Exception:
        pass
    
    # Schedule from Day 2 (index 1) onwards
    if 1 < len(MESSAGES_30_DAYS):
        await schedule_day_message(context.application, user.id, 1)

    origin = f" from {source}" if source else ""
    # Compose welcome text based on schedule mode
    if FAST_SCHEDULE_HOURS > 0:
        schedule_text = f"every {FAST_SCHEDULE_HOURS} hour(s) for testing."
    elif FAST_SCHEDULE_MINUTES > 0:
        schedule_text = f"every {FAST_SCHEDULE_MINUTES} minute(s) for testing."
    else:
        schedule_text = f"daily at {DEFAULT_TIME_HOUR:02d}:00 UTC."
    welcome_text = f"Welcome{origin}! You will receive messages {schedule_text}"
    if update.message:
        await update.message.reply_text(welcome_text)
    else:
        await context.bot.send_message(chat_id=user.id, text=welcome_text)


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")


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
        # Schedule the next message based on current time
        when = get_next_run_time_utc(day_index, DEFAULT_TIME_HOUR)
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

    # Get port from Heroku or use default
    port = int(os.environ.get("PORT", 5000))
    
    # Run the bot
    print(f"Bot starting on port {port}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()


