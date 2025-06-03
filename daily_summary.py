import requests
from datetime import datetime, timedelta
import asyncio
import logging
import os
import json
import time
from dateutil.parser import parse as parse_dt  # שים לב - זה צריך להיות מותקן ב־requirements.txt

GPT_LOG_PATH = "/data/gpt_usage_log.jsonl"

if not os.path.exists(GPT_LOG_PATH):
    with open(GPT_LOG_PATH, "w", encoding="utf-8") as f:
        pass

from telegram import Bot
from config import OPENAI_API_KEY, OPENAI_ADMIN_KEY, ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID

bot = Bot(token=ADMIN_BOT_TELEGRAM_TOKEN)

async def send_daily_summary(days_back=1):
    """
    days_back = 1 --> אתמול (ברירת מחדל)
    days_back = 0 --> היום
    days_back = 2 --> שלשום
    """

    try:
        import pytz
        thailand_tz = pytz.timezone("Asia/Bangkok")
        today = datetime.now(thailand_tz).date()
        target_date = today - timedelta(days=days_back)
        target_str = target_date.strftime("%Y-%m-%d")
        
        target_start = thailand_tz.localize(datetime.combine(target_date, datetime.min.time()))
        target_end = thailand_tz.localize(datetime.combine(target_date + timedelta(days=1), datetime.min.time()))
        start_time_unix = int(target_start.timestamp())
        end_time_unix = int(target_end.timestamp())

        headers = {"Authorization": f"Bearer {OPENAI_ADMIN_KEY}"}

        # -------------------------------------------------------------
        # משיכת usage (טוקנים, קריאות) - זה נותן נתונים טכניים!
        # -------------------------------------------------------------
        usage_url = "https://api.openai.com/v1/organization/usage/completions"
        usage_params = {
            "start_time": start_time_unix,
            "end_time": end_time_unix,
            "interval": "1d"
        }
        try:
            usage_resp = requests.get(usage_url, headers=headers, params=usage_params, timeout=30)
            usage_resp.raise_for_status()
            usage_data = usage_resp.json()
        except requests.RequestException as e:
            logging.error(f"שגיאה בקריאה ל-OpenAI usage API: {e}")
            usage_data = {}

        input_tokens = output_tokens = cached_tokens = num_requests = 0
        if "data" in usage_data and usage_data["data"]:
            usage_results = usage_data["data"][0].get("results", [])
            if usage_results:
                u = usage_results[0]
                input_tokens = u.get("input_tokens", 0)
                output_tokens = u.get("output_tokens", 0)
                cached_tokens = u.get("input_cached_tokens", 0)
                num_requests = u.get("num_model_requests", 0)
        # כאן יכול להיות 0 אם אין usage לאותו יום

        # -------------------------------------------------------------
        # משיכת חיוב אמיתי (כסף שחויבת בפועל!) - זה מקור שונה!
        # -------------------------------------------------------------
        costs_url = "https://api.openai.com/v1/organization/costs"
        costs_params = {
            "start_time": start_time_unix,
            "end_time": end_time_unix,
            "interval": "1d"
        }
        try:
            costs_resp = requests.get(costs_url, headers=headers, params=costs_params, timeout=30)
            costs_resp.raise_for_status()
            costs_data = costs_resp.json()
        except requests.RequestException as e:
            logging.error(f"שגיאה בקריאה ל-OpenAI costs API: {e}")
            costs_data = {}

        dollar_cost = 0
        if "data" in costs_data and costs_data["data"]:
            cost_results = costs_data["data"][0].get("results", [])
            if cost_results:
                dollar_cost = cost_results[0].get("amount", {}).get("value", 0)
        shekel_cost = dollar_cost * 3.7

        # --- מחלץ גם נתונים מה-usage log שלך ---
        total_main = total_extract = total_summary = 0
        tokens_main = tokens_extract = tokens_summary = 0
        if os.path.exists(GPT_LOG_PATH):
            with open(GPT_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        timestamp = entry.get("timestamp", "")
                        if not timestamp:
                            continue
                        try:
                            entry_dt = parse_dt(timestamp)
                        except Exception:
                            continue
                        # המרה לאזור זמן של תאילנד להשוואה נכונה
                        if entry_dt.tzinfo is None:
                            entry_dt = thailand_tz.localize(entry_dt)
                        else:
                            entry_dt = entry_dt.astimezone(thailand_tz)
                            
                        entry_date = entry_dt.date()
                        if entry_date != target_date:
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

        # ===== חישוב עלות ממוצעת בשקלים =====
        if total_main > 0:
            avg_cost_shekel = (shekel_cost / total_main) * 100  # אגורות
        else:
            avg_cost_shekel = 0

        # ---- הודעה מסכמת ומפורטת ----
        summary = (
            f"📅 סיכום GPT ל-{target_str}\n"
            f"💰 עלות אמיתית: ${dollar_cost:.3f} (~₪{shekel_cost:.2f})\n"
            f"📨 הודעות משתמש (log): {total_messages:,}\n"
            f"🪙 עלות ממוצעת להודעת משתמש:  {avg_cost_shekel:.2f} אגורות\n"
            f"⚙️ קריאות GPT (log): {total_calls:,} (API: {num_requests:,})\n"
            f"🔢 טוקנים API: קלט={input_tokens:,} | פלט={output_tokens:,} | מטמון={cached_tokens:,}\n"
            f"🔢 טוקנים לוג: main={tokens_main:,} | extract={tokens_extract:,} | summary={tokens_summary:,}\n"
        )

        await bot.send_message(chat_id=ADMIN_NOTIFICATION_CHAT_ID, text=summary)
        print(f"📬 נשלח הסיכום ל-{target_str} ל-chat_id: {ADMIN_NOTIFICATION_CHAT_ID}")

    except Exception as e:
        logging.error(f"שגיאה בשליחת סיכום usage: {e}")
        try:
            await bot.send_message(
                chat_id=ADMIN_NOTIFICATION_CHAT_ID,
                text="❗ מצטער, לא הצלחתי להפיק דוח usage. בדוק את השרת או את OpenAI."
            )
        except Exception as telegram_error:
            logging.error(f"שגיאה גם בשליחת הודעת שגיאה לטלגרם: {telegram_error}")

# דוגמה לשימוש:
# await send_daily_summary(days_back=1)   # דוח של אתמול
# await send_daily_summary(days_back=0)   # דוח של היום
# await send_daily_summary(days_back=2)   # דוח של שלשום

async def schedule_daily_summary():
    await asyncio.sleep(2)  # מריץ עוד איקס שניות מהרגע שהפריסה הושלמה והבוט עלה
    await send_daily_summary()

async def delayed_daily_summary():
    print("👉 נכנסתי ל־delayed_daily_summary — עומד לשלוח דוח יומי!")
    await asyncio.sleep(1)  # מחכה איקס שניות לסיום כל התהליך
    await send_daily_summary(days_back=0)  # days_back=0 זה דוח של היום (אם רוצה אתמול – שנה ל־1)
