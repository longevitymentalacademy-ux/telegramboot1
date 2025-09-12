## Telegram 30-Day Auto Message Bot

A Python bot that sends automated daily messages for 30 days to new users who join via TikTok deep link.

### Features
- Deep-link tracking: `/start tiktok`
- SQLite persistence (users, schedules, progress)
- Automatic scheduling using JobQueue
- Reschedules pending messages on restart

### Setup
1. Create a bot with BotFather and get the token.
2. Set environment variable:
   - Windows (PowerShell): `setx TELEGRAM_BOT_TOKEN "<YOUR_TOKEN>"`
   - macOS/Linux: `export TELEGRAM_BOT_TOKEN="<YOUR_TOKEN>"`
3. Optionally set daily hour (UTC):
   - `export DAILY_MESSAGE_HOUR=9` (default 9)
4. Install dependencies:
   - `pip install -r requirements.txt`
5. Run:
   - `python main.py`

### Deep Link
- Use `https://t.me/<YourBotUsername>?start=tiktok` in your TikTok bio.

### Custom Messages
- Edit `messages.py` and replace `MESSAGES_30_DAYS` with your content.

### Notes
- Scheduling uses UTC. Adjust `DAILY_MESSAGE_HOUR` as needed.
- The bot stores data in `bot.db` next to the scripts.


