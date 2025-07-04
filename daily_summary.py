import requests
from datetime import datetime, timedelta
import asyncio
import logging
import os
import json
import time
from dateutil.parser import parse as parse_dt  # שים לב - זה צריך להיות מותקן ב־requirements.txt
from gpt_utils import USD_TO_ILS
import pytz  # הוספתי לוודא שיש pytz

from telegram import Bot
from config import ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID, gpt_log_path

print("🚀 התחלת הרצה של daily_summary.py")

def _get_summary_for_date(target_date: datetime.date, tz: pytz.timezone):
    """
    מחשב סיכום אינטראקציות לתאריך נתון.
    פלט: dict עם נתוני הסיכום, או None אם אין נתונים.
    """
    interactions = {}
    call_types_counter = {}

    # יצירת קובץ הלוג אם הוא לא קיים
    if not os.path.exists(gpt_log_path):
        print(f"⚠️ קובץ הלוג לא קיים: {gpt_log_path}")
        print("📝 יוצר קובץ לוג ריק...")
        os.makedirs(os.path.dirname(gpt_log_path), exist_ok=True)
        with open(gpt_log_path, "w", encoding="utf-8") as f:
            pass  # יוצר קובץ ריק
        print("✅ קובץ לוג נוצר")
        return None  # אין נתונים לדווח עליהם

    with open(gpt_log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
                entry_dt = parse_dt(entry["timestamp"]).astimezone(pytz.UTC)
                
                if entry_dt.date() != target_date:
                    continue
                
                # שימוש ב-interaction_id אם קיים, אחרת שימוש ב-timestamp כ-identifier
                interaction_id = entry.get("interaction_id")
                if not interaction_id:
                    interaction_id = entry["timestamp"]  # fallback ל-timestamp

                if interaction_id not in interactions:
                    interactions[interaction_id] = {"cost_total_ils": 0}
                
                interactions[interaction_id]["cost_total_ils"] += entry.get("cost_total_ils", 0)
                
                call_type = entry.get("type", "unknown")
                call_types_counter[call_type] = call_types_counter.get(call_type, 0) + 1

            except (json.JSONDecodeError, KeyError, AttributeError):
                continue

    total_interactions = len(interactions)
    if total_interactions == 0:
        return None

    total_cost_ils = sum(i["cost_total_ils"] for i in interactions.values())
    avg_cost_agorot = (total_cost_ils / total_interactions) * 100
    total_api_calls = sum(call_types_counter.values())
    call_types_str = " | ".join([f"{k}:{v}" for k, v in sorted(call_types_counter.items())])

    return {
        "total_interactions": total_interactions,
        "total_cost_ils": total_cost_ils,
        "avg_cost_agorot": avg_cost_agorot,
        "total_api_calls": total_api_calls,
        "call_types_str": call_types_str,
    }


async def send_daily_summary(days_back=1):
    """
    מחשב ושולח דוח עלות ושימוש יומי, כולל סיכום להיום.
    """
    bot = Bot(token=ADMIN_BOT_TELEGRAM_TOKEN)
    try:
        tz = pytz.timezone("Europe/Berlin")
        yesterday_date = datetime.now(tz).date() - timedelta(days=days_back)
        today_date = datetime.now(tz).date()

        # הפקת דוח עיקרי (אתמול)
        yesterday_summary_data = _get_summary_for_date(yesterday_date, tz)
        
        if not yesterday_summary_data:
            summary = f"📅 סיכום אינטראקציות ל-{yesterday_date.strftime('%d/%m/%Y')}\n\nלא נמצאו אינטראקציות בתאריך זה."
        else:
            summary = (
                f"📊 **דוח אינטראקציות יומי**\n"
                f"📅 **תאריך:** {yesterday_date.strftime('%d/%m/%Y')}\n"
                f"──────────────────\n"
                f"🗣️ **סה\"כ אינטראקציות:** {yesterday_summary_data['total_interactions']}\n"
                f"💰 **עלות כוללת:** {yesterday_summary_data['total_cost_ils']:.2f} ₪\n"
                f"🪙 **עלות ממוצעת לאינטראקציה:** {yesterday_summary_data['avg_cost_agorot']:.2f} אגורות\n"
                f"⚙️ **סה\"כ קריאות API:** {yesterday_summary_data['total_api_calls']} ({yesterday_summary_data['call_types_str']})"
            )
        
        # הפקת סיכום להיום
        today_summary_data = _get_summary_for_date(today_date, tz)
        if today_summary_data:
            summary += (
                f"\n\n---\n"
                f"📈 **סיכום להיום ({today_date.strftime('%d/%m')})**\n"
                f"אינטראקציות: {today_summary_data['total_interactions']} | "
                f"עלות: {today_summary_data['total_cost_ils']:.2f} ₪ | "
                f"ממוצע: {today_summary_data['avg_cost_agorot']:.2f} אגורות"
            )

        await bot.send_message(chat_id=ADMIN_NOTIFICATION_CHAT_ID, text=summary)
        print(f"✅  הדוח ל-{yesterday_date.strftime('%Y-%m-%d')} (כולל היום) נשלח בהצלחה.")

    except Exception as e:
        error_message = f"❌ אירעה שגיאה חמורה בהפקת הדוח היומי: {e}"
        print(error_message)
        import traceback
        print(traceback.format_exc())
        await bot.send_message(chat_id=ADMIN_NOTIFICATION_CHAT_ID, text=error_message)

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
            loop.close()
            print("✅ [DAILY] דוח באתחול נשלח בהצלחה!")
            print("📱 מחכה להודעה חדשה ממשתמש בטלגרם...")
        except Exception as e:
            print(f"❌ [DAILY] שגיאה בדוח באתחול: {e}")
            print("📱 מחכה להודעה חדשה ממשתמש בטלגרם...")
    
    # תזמון יומי קבוע ל-8:00 בבוקר
    def scheduled_daily_report():
        print("🔥 [DAILY] שולח דוח יומי מתוזמן...")
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_daily_summary())
            print("✅ [DAILY] דוח מתוזמן נשלח בהצלחה!")
        except Exception as e:
            print(f"❌ [DAILY] שגיאה בדוח מתוזמן: {e}")
    
    # הגדרת תזמון מבוצעת ב-bot_setup.py במסגרת המתזמן המרכזי
    print("ℹ️ [DAILY] תזמון יומי מנוהל ב-bot_setup.py")
    
    # הפעל דוח מיידי
    threading.Thread(target=startup_report, daemon=True).start()

# הפעל אוטומטית כשטוענים את הקובץ (רק אם זה לא import)
if __name__ == "__main__":
    setup_daily_reports()

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(send_daily_summary(days_back=0))
    except Exception as e:
        print(f"❌ שגיאה כללית בהרצה: {e}")
