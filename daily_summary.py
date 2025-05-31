import requests
from datetime import datetime, timedelta
import asyncio
import logging
from telegram import Bot
from config import OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, ERROR_NOTIFICATION_CHAT_ID

bot = Bot(token=TELEGRAM_BOT_TOKEN)

async def send_daily_summary():
    try:
        # תאריך של אתמול (UTC)
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        start_date = end_date = yesterday.strftime("%Y-%m-%d")

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        url = f"https://api.openai.com/v1/usage?start_date={start_date}&end_date={end_date}"
        response = requests.get(url, headers=headers)
        data = response.json()

        if "daily_costs" not in data or not data["daily_costs"]:
            summary = f"❌ אין נתונים זמינים ל-{start_date}"
        else:
            item = data["daily_costs"][0]["line_items"][0]
            model = item["model"]
            n_requests = item["n_requests"]
            n_prompt = item["n_prompt_tokens"]
            n_cached = item["n_cached_tokens"]
            n_output = item["n_output_tokens"]
            cost = item["cost"]

            summary = (
                f"💸 סיכום ל-{start_date}\n"
                f"מודל: {model}\n"
                f"בקשות: {n_requests}\n"
                f"prompt: {n_prompt} | cached: {n_cached} | output: {n_output}\n"
                f"💰 עלות סופית: ${cost:.3f}"
            )

        await bot.send_message(chat_id=ERROR_NOTIFICATION_CHAT_ID, text=summary)
        print("📬 נשלח הסיכום היומי לטלגרם")

    except Exception as e:
        logging.error(f"שגיאה בשליחת סיכום יומי: {e}")

async def schedule_daily_summary():
    await asyncio.sleep(5)  # מריץ עוד 5 שניות מהרגע שהבוט עלה
    await send_daily_summary()
