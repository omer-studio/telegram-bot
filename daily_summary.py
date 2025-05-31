import requests
from datetime import datetime, timedelta
import asyncio
import logging
import os
import json
import time

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
        # תאריך היום והאתמול (UTC)
        today = datetime.utcnow().date()
        days_to_fetch = 4  # משיכת usage ל-4 ימים אחורה
        start_date_dt = today - timedelta(days=days_to_fetch)
        end_date_dt = today

        start_time_unix = int(time.mktime(datetime.combine(start_date_dt, datetime.min.time()).timetuple()))
        end_time_unix = int(time.mktime(datetime.combine(end_date_dt, datetime.min.time()).timetuple()))

        url = "https://api.openai.com/v1/organization/usage/completions"
        params = {
            "start_time": start_time_unix,
            "end_time": end_time_unix,
            "interval": "1d"
        }

        headers = {
            "Authorization": f"Bearer {OPENAI_ADMIN_KEY}"
        }

        print(f"משיכת usage ל-{days_to_fetch} ימים אחורה מ-{start_date_dt} ועד {end_date_dt}")
        print(f"URL: {url} עם params: {params}")

        response = requests.get(url, headers=headers, params=params)
        print("Response status code:", response.status_code)
        data = response.json()
        print("Response JSON:", data)

        yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")

        # סינון הנתונים ליום אתמול בלבד
        filtered_data = []
        for day_data in data.get("data", []):
            day_str = datetime.utcfromtimestamp(day_data["start_time"]).strftime("%Y-%m-%d")
            if day_str == yesterday_str:
                filtered_data.append(day_data)

        if not filtered_data:
            summary = (
                f"❕הודעה לאדמין❕\n\n"
                f"❌ אין נתונים זמינים מ-OPENAI ל-{yesterday_str}\n"
                f"באסוש... מצטער"
            )
        else:
            usage_item = filtered_data[0]["results"][0]
            dollar_cost = usage_item.get("cost", 0)
            shekel_cost = dollar_cost * 3.7
            model = usage_item.get("model", "unknown")
            n_requests = usage_item.get("num_model_requests", 0)
            n_prompt = usage_item.get("input_tokens", 0)
            n_cached = usage_item.get("input_cached_tokens", 0)
            n_output = usage_item.get("output_tokens", 0)

            # --- ניתוח קובץ usage log ---
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
    await asyncio.sleep(3)  # מריץ עוד 3 שניות מהרגע שהבוט עלה
    await send_daily_summary()
