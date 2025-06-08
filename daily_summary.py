import requests
from datetime import datetime, timedelta
import asyncio
import logging
import os
import json
import time
from dateutil.parser import parse as parse_dt  # שים לב - זה צריך להיות מותקן ב־requirements.txt
from gpt_handler import USD_TO_ILS
import pytz  # הוספתי לוודא שיש pytz

# הגדרת נתיב לוג אחיד מתוך תיקיית הפרויקט
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

from telegram import Bot
from config import OPENAI_API_KEY, OPENAI_ADMIN_KEY, ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID, GPT_LOG_PATH

bot = Bot(token=ADMIN_BOT_TELEGRAM_TOKEN)

print("🚀 התחלת הרצה של daily_summary.py")

async def send_daily_summary(days_back=1):
    """
    days_back = 1 --> אתמול (ברירת מחדל)
    days_back = 0 --> היום
    days_back = 2 --> שלשום
    """

    try:
        # החלף ל-Europe/Berlin (UTC+1, כולל שעון קיץ)
        tz = pytz.timezone("Europe/Berlin")
        today = datetime.now(tz).date()
        target_date = today - timedelta(days=days_back)
        target_str = target_date.strftime("%Y-%m-%d")
        
        target_start = tz.localize(datetime.combine(target_date, datetime.min.time()))
        target_end = tz.localize(datetime.combine(target_date + timedelta(days=1), datetime.min.time()))
        start_time_unix = int(target_start.timestamp())
        end_time_unix = int(target_end.timestamp())

        print(f"🔍 DEBUG: target_date={target_date}, start_unix={start_time_unix}, end_unix={end_time_unix}")

        headers = {"Authorization": f"Bearer {OPENAI_ADMIN_KEY}"}
        print(f"🔍 DEBUG: API Key exists: {bool(OPENAI_ADMIN_KEY)}, Length: {len(OPENAI_ADMIN_KEY) if OPENAI_ADMIN_KEY else 0}")

        # -------------------------------------------------------------
        # משיכת usage (טוקנים, קריאות) - זה נותן נתונים טכניים!
        # -------------------------------------------------------------
        usage_url = "https://api.openai.com/v1/organization/usage/completions"
        usage_params = {
            "start_time": start_time_unix,
            "end_time": end_time_unix,
            "interval": "1d"
        }
        print(f"🔍 DEBUG: About to call usage API with params: {usage_params}")
        
        try:
            usage_resp = requests.get(usage_url, headers=headers, params=usage_params, timeout=30)
            print(f"🔍 DEBUG: Usage API response status: {usage_resp.status_code}")
            print(f"🔍 DEBUG: Usage API response headers: {dict(usage_resp.headers)}")
            
            usage_resp.raise_for_status()
            usage_data = usage_resp.json()
            print(f"🔍 DEBUG: Usage API response data: {json.dumps(usage_data, indent=2)}")
            # דיבאג נוסף
            if "data" in usage_data:
                print(f"🔍 DEBUG: usage_data['data'] = {usage_data['data']}")
                if usage_data["data"]:
                    print(f"🔍 DEBUG: usage_data['data'][0] = {usage_data['data'][0]}")
                    print(f"🔍 DEBUG: usage_data['data'][0].get('results') = {usage_data['data'][0].get('results')}")
                else:
                    print("🔍 DEBUG: usage_data['data'] is empty")
            else:
                print("🔍 DEBUG: usage_data has no 'data' key")
            
        except requests.RequestException as e:
            print(f"❌ DEBUG: Usage API Error: {e}")
            print(f"❌ DEBUG: Response text: {getattr(e.response, 'text', 'No response text')}")
            logging.error(f"שגיאה בקריאה ל-OpenAI usage API: {e}")
            usage_data = {}

        input_tokens = output_tokens = cached_tokens = num_requests = 0
        if "data" in usage_data and usage_data["data"]:
            usage_results = usage_data["data"][0].get("results", [])
            print(f"🔍 DEBUG: Found {len(usage_results)} usage results")
            if usage_results:
                u = usage_results[0]
                input_tokens = u.get("input_tokens", 0)
                output_tokens = u.get("output_tokens", 0)
                cached_tokens = u.get("input_cached_tokens", 0)
                num_requests = u.get("num_model_requests", 0)
                print(f"🔍 DEBUG: Extracted tokens - input:{input_tokens}, output:{output_tokens}, cached:{cached_tokens}, requests:{num_requests}")
        else:
            print("❌ DEBUG: No usage data found or empty data")

        # -------------------------------------------------------------
        # משיכת חיוב אמיתי (כסף שחויבת בפועל!) - זה מקור שונה!
        # -------------------------------------------------------------
        costs_url = "https://api.openai.com/v1/organization/costs"
        costs_params = {
            "start_time": start_time_unix,
            "end_time": end_time_unix,
            "interval": "1d"
        }
        print(f"🔍 DEBUG: About to call costs API with params: {costs_params}")
        
        try:
            costs_resp = requests.get(costs_url, headers=headers, params=costs_params, timeout=30)
            print(f"🔍 DEBUG: Costs API response status: {costs_resp.status_code}")
            print(f"🔍 DEBUG: Costs API response headers: {dict(costs_resp.headers)}")
            
            costs_resp.raise_for_status()
            costs_data = costs_resp.json()
            print(f"🔍 DEBUG: Costs API response data: {json.dumps(costs_data, indent=2)}")
            # דיבאג נוסף
            if "data" in costs_data:
                print(f"🔍 DEBUG: costs_data['data'] = {costs_data['data']}")
                if costs_data["data"]:
                    print(f"🔍 DEBUG: costs_data['data'][0] = {costs_data['data'][0]}")
                    print(f"🔍 DEBUG: costs_data['data'][0].get('results') = {costs_data['data'][0].get('results')}")
                else:
                    print("🔍 DEBUG: costs_data['data'] is empty")
            else:
                print("🔍 DEBUG: costs_data has no 'data' key")
            
        except requests.RequestException as e:
            print(f"❌ DEBUG: Costs API Error: {e}")
            print(f"❌ DEBUG: Response text: {getattr(e.response, 'text', 'No response text')}")
            logging.error(f"שגיאה בקריאה ל-OpenAI costs API: {e}")
            costs_data = {}

        dollar_cost = 0
        if "data" in costs_data and costs_data["data"]:
            cost_results = costs_data["data"][0].get("results", [])
            print(f"🔍 DEBUG: Found {len(cost_results)} cost results")
            if cost_results:
                dollar_cost = cost_results[0].get("amount", {}).get("value", 0)
                print(f"🔍 DEBUG: Extracted cost: ${dollar_cost}")
        else:
            print("❌ DEBUG: No cost data found or empty data")
            
        shekel_cost = dollar_cost * USD_TO_ILS

        # --- מחלץ גם נתונים מה-usage log שלך ---
        total_main = total_extract = total_summary = 0
        tokens_main = tokens_extract = tokens_summary = 0
        
        print(f"🔍 DEBUG: Checking log file: {GPT_LOG_PATH}, exists: {os.path.exists(GPT_LOG_PATH)}")
        
        if os.path.exists(GPT_LOG_PATH):
            line_count = 0
            matched_lines = 0
            with open(GPT_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line_count += 1
                    try:
                        entry = json.loads(line)
                        timestamp = entry.get("timestamp", "")
                        if not timestamp:
                            continue
                        try:
                            entry_dt = parse_dt(timestamp)
                            if entry_dt.tzinfo is None:
                                entry_dt = entry_dt.replace(tzinfo=pytz.UTC)
                            else:
                                entry_dt = entry_dt.astimezone(pytz.UTC)
                        except Exception:
                            continue
                        entry_date_utc = entry_dt.date()
                        if entry_date_utc != target_date:
                            continue
                        
                        matched_lines += 1
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
                    except Exception as parse_error:
                        print(f"🔍 DEBUG: Error parsing line {line_count}: {parse_error}")
                        continue
            
            print(f"🔍 DEBUG: Log analysis - total_lines:{line_count}, matched_lines:{matched_lines}")
            print(f"🔍 DEBUG: Log totals - main:{total_main}, extract:{total_extract}, summary:{total_summary}")

        total_messages = total_main
        total_calls = total_main + total_extract + total_summary

        # ===== חישוב עלות ממוצעת בשקלים =====
        if total_main > 0:
            avg_cost_shekel = (shekel_cost / total_main) * 100  # אגורות
        else:
            avg_cost_shekel = 0

        print(f"🔍 DEBUG: Final calculations - cost:${dollar_cost}, messages:{total_messages}, avg_cost:{avg_cost_shekel}")

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
        print(f"❌ DEBUG: General error in send_daily_summary: {e}")
        import traceback
        print(f"❌ DEBUG: Traceback: {traceback.format_exc()}")
        logging.error(f"שגיאה בשליחת סיכום usage: {e}")
        try:
            await bot.send_message(
                chat_id=ADMIN_NOTIFICATION_CHAT_ID,
                text="❗ מצטער, לא הצלחתי להפיק דוח usage. בדוק את השרת או את OpenAI."
            )
        except Exception as telegram_error:
            print(f"❌ DEBUG: Telegram error: {telegram_error}")
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

# ===============================================
# אתחול אוטומטי של דוחות יומיים
# ===============================================
import threading
import time
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

def setup_daily_reports():
    """הגדרת דוח מיידי ודוח יומי אוטומטי"""
    print("🚀 [DAILY] מתחיל הגדרת דוחות יומיים...")
    
    # דוח מיידי באתחול
    def startup_report():
        time.sleep(15)  # המתן שהכל יתייצב
        print("🔥 [DAILY] שולח דוח יומי באתחול...")
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_daily_summary())
            print("✅ [DAILY] דוח באתחול נשלח בהצלחה!")
        except Exception as e:
            print(f"❌ [DAILY] שגיאה בדוח באתחול: {e}")
    
    # דוח יומי אוטומטי
    try:
        thailand_tz = pytz.timezone("Asia/Bangkok")
        scheduler = BackgroundScheduler(timezone=thailand_tz)
        scheduler.add_job(send_daily_summary, 'cron', hour=12, minute=28)
        scheduler.start()
        print("✅ [DAILY] תזמון דוח יומי הופעל ב-12:28 תאילנד")
    except Exception as e:
        print(f"❌ [DAILY] שגיאה בהגדרת תזמון: {e}")
    
    # הפעל דוח מיידי
    threading.Thread(target=startup_report, daemon=True).start()

# הפעל אוטומטית כשטוענים את הקובץ
setup_daily_reports()

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(send_daily_summary(days_back=0))
    except Exception as e:
        print(f"❌ שגיאה כללית בהרצה: {e}")
