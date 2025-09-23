import os
from datetime import datetime, timedelta, time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import pytz
from database import initialize_database, upsert_user, mark_scheduled, mark_sent, get_conn
from messages import MESSAGES_30_DAYS
from sheets_integration import initialize_spreadsheet, log_user_to_sheets, update_user_progress

TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TARGET_TIMEZONE = "Europe/Rome"
TARGET_HOUR = 8
TARGET_MINUTE = 0

def get_next_run_time() -> datetime:
    tz = pytz.timezone(TARGET_TIMEZONE)
    now = datetime.now(tz)
    target_time = time(TARGET_HOUR, TARGET_MINUTE)
    next_run = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)
    return next_run

async def schedule_day_message(app: Application, user_id: int, day_index: int):
    job_name = f"daily-{user_id}-{day_index}"
    if not app.job_queue.get_jobs_by_name(job_name):
        when = get_next_run_time()
        app.job_queue.run_once(
            send_day_message, when, chat_id=user_id, name=job_name, data={"user_id": user_id, "day_index": day_index}
        )
        mark_scheduled(user_id, day_index, when.astimezone(pytz.utc).isoformat())
        print(f"Scheduled message for user {user_id}, day {day_index + 1} at {when}")

async def send_day_message(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data["user_id"]
    day_index = context.job.data["day_index"]
    if 0 <= day_index < len(MESSAGES_30_DAYS):
        text = MESSAGES_30_DAYS[day_index]
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
            mark_sent(user_id, day_index, datetime.now(pytz.utc).isoformat())
            update_user_progress(user_id, day_index + 1, f"G{day_index + 1}")
            if day_index + 1 < len(MESSAGES_30_DAYS):
                await schedule_day_message(context.application, user_id, day_index + 1)
        except Exception as e:
            print(f"Error sending message to {user_id}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    source = context.args[0].lower() if context.args else "organic"
    upsert_user(user.id, user.username, user.first_name, user.last_name, source)
    log_user_to_sheets(user.id, user.username, user.first_name, user.last_name, source)
    
    with get_conn() as conn:
        conn.execute("DELETE FROM schedules WHERE user_id = ?", (user.id,))
    
    if MESSAGES_30_DAYS:
        await context.bot.send_message(chat_id=user.id, text=MESSAGES_30_DAYS[0])
        mark_sent(user.id, 0, datetime.now(pytz.utc).isoformat())
        if len(MESSAGES_30_DAYS) > 1:
            await schedule_day_message(context.application, user.id, 1)
    await update.message.reply_text("Welcome! You will now receive daily messages.")

async def on_startup(app: Application):
    initialize_database()
    initialize_spreadsheet()
    await app.bot.delete_webhook(drop_pending_updates=True)

def main():
    token = os.getenv(TOKEN_ENV)
    if not token:
        raise ValueError(f"{TOKEN_ENV} not set!")
    
    app = Application.builder().token(token).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == '__main__':
    main()