import requests
from datetime import datetime, timedelta
import asyncio
import logging
import os
import json
import time

GPT_LOG_PATH = "/data/gpt_usage_log.jsonl"

from telegram import Bot
from config import OPENAI_API_KEY, OPENAI_ADMIN_KEY, ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID

bot = Bot(token=ADMIN_BOT_TELEGRAM_TOKEN)

async def send_daily_summary():
    try:
        # תאריך אתמול (UTC)
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")

        # זמן התחלה וסיום UNIX
        start_time_unix = int(time.mktime(datetime.combine(yesterday, datetime.min.time()).timetuple()))
        end_time_unix = int(time.mktime(datetime.combine(yesterday + timedelta(days=1), datetime.min.time()).timetuple()))

        headers = {"Authorization": f"Bearer {OPENAI_ADMIN_KEY}"}

        # -- שימוש בטוקנים --
        usage_url = "https://api.openai.com/v1/organization/usage/completions"
        usage_params = {
            "start_time": start_time_unix,
            "end_time": end_time_unix,
            "interval": "1d"
        }
        usage_resp = requests.get(usage_url, headers=headers, params=usage_params)
        usage_data = usage_resp.json()
        print("Usage response:", usage_data)

        # -- חיוב אמיתי --
        costs_url = "https://api.openai.com/v1/organization/costs"
        costs_params = {
            "start_time": start_time_unix,
            "end_time": end_time_unix,
            "interval": "1d"
        }
        costs_resp = requests.get(costs_url, headers=headers, params=costs_params)
        costs_data = costs_resp.json()
        print("Costs response:", costs_data)

        exchange_rate = 3.7

        # שליפת usage
        input_tokens = output_tokens = cached_tokens = num_requests = 0
        if "data" in usage_data and usage_data["data"]:
            usage_results = usage_data["data"][0].get("results", [])
            if usage_results:
                u = usage_results[0]
                input_tokens = u.get("input_tokens", 0)
                output_tokens = u.get("output_tokens", 0)
                cached_tokens = u.get("input_cached_tokens", 0)
                num_requests = u.get("num_model_requests", 0)

        # שליפת עלות אמיתית
        dollar_cost = 0
        if "data" in costs_data and costs_data["data"]:
            cost_results = costs_data["data"][0].get("results", [])
            if cost_results:
                dollar_cost = cost_results[0].get("amount", {}).get("value", 0)
        shekel_cost = dollar_cost * exchange_rate

        # ניתוח usage log לסטטיסטיקות פנימיות (כמו תמיד)
        total_main = total_extract = total_summary = 0
        tokens_main = tokens_extract = tokens_summary = 0
        if os.path.exists(GPT_LOG_PATH):
            with open(GPT_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        timestamp = entry.get("timestamp", "")
                        if not timestamp.startswith(yesterday_str):
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

        summary = (
            f"📅 סיכום GPT ל-{yesterday_str}\n"
            f"💰 עלות אמיתית מ־OpenAI: ${dollar_cost:.3f} (~₪{shekel_cost:.2f})\n"
            f"📨 הודעות משתמש: {total_messages:,}\n"
            f"⚙️ קריאות GPT: {total_calls:,} (API: {num_requests:,})\n"
            f"🔢 טוקנים: קלט={input_tokens:,} | פלט={output_tokens:,} | מטמון={cached_tokens:,}\n"
            f"🔢 טוקנים ע״פ usage log: main={tokens_main:,} | extract={tokens_extract:,} | summary={tokens_summary:,}\n"
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
    await asyncio.sleep(3)  # מריץ עוד 3 שניות מהרגע שהבוט עלה
    await send_daily_summary()
