import requests
from datetime import datetime, timedelta
import asyncio
import logging
import os
import json

GPT_LOG_PATH = "/data/gpt_usage_log.jsonl"

# יצירת הקובץ אם הוא לא קיים
if not os.path.exists(GPT_LOG_PATH):
    with open(GPT_LOG_PATH, "w", encoding="utf-8") as f:
        pass  # פשוט יוצר קובץ ריק

from telegram import Bot
from config import OPENAI_API_KEY, OPENAI_ADMIN_KEY, ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID

bot = Bot(token=ADMIN_BOT_TELEGRAM_TOKEN)

async def send_daily_summary():
    try:
        # תאריך של אתמול (UTC)
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        start_date = end_date = yesterday.strftime("%Y-%m-%d")

        # --- משיכת עלות אמיתית מתוך OpenAI ---
        headers = {
            "Authorization": f"Bearer {OPENAI_ADMIN_KEY}"
        }
        url = f"https://api.openai.com/v1/usage?start_date={start_date}&end_date={end_date}"
        print(f"משיכת usage ל-{start_date} בלבד")
        print(f"URL: {url}")
        response = requests.get(url, headers=headers)
        print("Response status code:", response.status_code)
        print("Response JSON:", response.json())
        data = response.json()

        if "daily_costs" not in data or not data["daily_costs"]:
            summary =  (
                f"❕הודעה לאדמין❕\n\n"
                f"❌ אין נתונים זמינים מ-OPENAI ל-{start_date}\n"
                f"באסוש... מצטער"
            )
        else:
            item = data["daily_costs"][0]["line_items"][0]
            dollar_cost = item["cost"]
            shekel_cost = dollar_cost * 3.7
            model = item["model"]
            n_requests = item["n_requests"]
            n_prompt = item["n_prompt_tokens"]
            n_cached = item["n_cached_tokens"]
            n_output = item["n_output_tokens"]

            # --- ניתוח קובץ usage log ---
            total_main = total_extract = total_summary = 0
            tokens_main = tokens_extract = tokens_summary = 0

            if os.path.exists(GPT_LOG_PATH):
                with open(GPT_LOG_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            timestamp = entry.get("timestamp", "")
                            if not timestamp.startswith(start_date):
                                continue
                            ttype = entry.get("type")
                            tokens = entry.get("tokens_total", 0)
                            if ttype == "main_reply":
                                total_main += 1
                                tokens_main += tokens
                            elif ttype == "identity_extraction":
                                total_extract += 1
                                tokens_extract += tokens
                            elif ttype == "reply_summary":
                                total_summary += 1
                                tokens_summary += tokens
                        except:
                            continue

            total_messages = total_main
            total_calls = total_main + total_extract + total_summary

            # --- בניית הסיכום לטלגרם ---
            summary = (
                f"📅 סיכום GPT ל-{start_date}\n"
                f"💰 עלות מ־OpenAI: ${dollar_cost:.3f} (~₪{shekel_cost:.1f})\n"
                f"📨 הודעות משתמש: {total_messages:,}\n"
                f"⚙️ קריאות GPT: {total_calls:,} "
                f"(תשובות: {total_main:,}, חילוץ: {total_extract:,}, קיצור: {total_summary:,})\n"
                f"🔢 טוקנים: main={tokens_main:,} | extract={tokens_extract:,} | summary={tokens_summary:,}\n"
                f"🧠 מודל: {model} | Cached: {n_cached:,}\n"
            )

        await bot.send_message(chat_id=ADMIN_NOTIFICATION_CHAT_ID, text=summary)
        print(f"📬 נשלח הסיכום היומי ל-chat_id: {ADMIN_NOTIFICATION_CHAT_ID}")

    except Exception as e:
        logging.error(f"שגיאה בשליחת סיכום יומי: {e}")
        try:
            await bot.send_message(
                chat_id=ADMIN_NOTIFICATION_CHAT_ID,
                text="❗ מצטער, לא הצלחתי להפיק דוח יומי היום. בדוק את השרת או את OpenAI."
            )
        except Exception as telegram_error:
            logging.error(f"שגיאה גם בשליחת הודעת שגיאה לטלגרם: {telegram_error}")

async def schedule_daily_summary():
    await asyncio.sleep(50)  # מריץ עוד 50 שניות מהרגע שהבוט עלה
    await send_daily_summary()
