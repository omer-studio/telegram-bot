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
from config import ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID, GPT_LOG_PATH

bot = Bot(token=ADMIN_BOT_TELEGRAM_TOKEN)

print("🚀 התחלת הרצה של daily_summary.py")

async def send_daily_summary(days_back=1):
    """
    days_back = 1 --> אתמול (ברירת מחדל)
    days_back = 0 --> היום
    days_back = 2 --> שלשום
    
    🔄 עדכון: עכשיו משתמש במערכת העלויות החדשה של LiteLLM במקום OpenAI API ישיר
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

        # 🔄 עדכון: שימוש במערכת העלויות החדשה של LiteLLM
        # במקום לקרוא ל-OpenAI API, נחשב עלויות מהלוגים המקומיים
        
        # --- מחלץ נתונים מה-usage log שלך ---
        total_main = total_extract = total_summary = 0
        tokens_main = tokens_extract = tokens_summary = 0
        cost_main = cost_extract = cost_summary = 0.0
        cost_main_ils = cost_extract_ils = cost_summary_ils = 0.0
        
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
                        
                        # 🔄 עדכון: חישוב עלויות מהנתונים החדשים
                        cost_total = entry.get("cost_total", 0)
                        cost_total_ils = entry.get("cost_total_ils", 0)
                        
                        if ttype == "main_reply":
                            total_main += 1
                            tokens_main += tokens
                            cost_main += cost_total
                            cost_main_ils += cost_total_ils
                        elif ttype == "identity_extraction":
                            total_extract += 1
                            tokens_extract += tokens
                            cost_extract += cost_total
                            cost_extract_ils += cost_total_ils
                        elif ttype == "reply_summary":
                            total_summary += 1
                            tokens_summary += tokens
                            cost_summary += cost_total
                            cost_summary_ils += cost_total_ils
                    except Exception as parse_error:
                        print(f"🔍 DEBUG: Error parsing line {line_count}: {parse_error}")
                        continue
            
            print(f"🔍 DEBUG: Log analysis - total_lines:{line_count}, matched_lines:{matched_lines}")
            print(f"🔍 DEBUG: Log totals - main:{total_main}, extract:{total_extract}, summary:{total_summary}")

        total_messages = total_main
        total_calls = total_main + total_extract + total_summary
        
        # 🔄 עדכון: חישוב עלויות כוללות מהלוגים
        total_cost_usd = cost_main + cost_extract + cost_summary
        total_cost_ils = cost_main_ils + cost_extract_ils + cost_summary_ils

        # ===== חישוב עלות ממוצעת בשקלים =====
        if total_main > 0:
            avg_cost_shekel = (total_cost_ils / total_main) * 100  # אגורות
        else:
            avg_cost_shekel = 0

        print(f"🔍 DEBUG: Final calculations - cost:${total_cost_usd:.6f}, cost_ils:{total_cost_ils:.4f}, messages:{total_messages}, avg_cost:{avg_cost_shekel:.2f}")

        # ---- הודעה מסכמת ומפורטת ----
        summary = (
            f"📅 סיכום GPT ל-{target_str}\n"
            f"💰 עלות LiteLLM: ${total_cost_usd:.6f} (~₪{total_cost_ils:.4f})\n"
            f"📨 הודעות משתמש (log): {total_messages:,}\n"
            f"🪙 עלות ממוצעת להודעת משתמש: {avg_cost_shekel:.2f} אגורות\n"
            f"⚙️ קריאות GPT (log): {total_calls:,}\n"
            f"🔢 טוקנים לוג: main={tokens_main:,} | extract={tokens_extract:,} | summary={tokens_summary:,}\n"
            f"💸 עלויות מפורטות: main=${cost_main:.6f} | extract=${cost_extract:.6f} | summary=${cost_summary:.6f}\n"
            f"🔄 מערכת: LiteLLM (עדכון {target_str})"
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
                text="❗ מצטער, לא הצלחתי להפיק דוח usage. בדוק את השרת או את הלוגים."
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
