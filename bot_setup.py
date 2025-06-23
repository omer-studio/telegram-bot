"""
================================================================================
🚨 חשוב מאוד - שתי סביבות נפרדות! 🚨
================================================================================

סביבה 1 - רנדר (ייצור):
   - הקובץ הזה רץ ישירות: python main.py
   - לא משתמש ב-ngrok
   - לא משתמש ב-sandbox.py
   - רץ על פורט 8000 עם HTTP server פשוט

סביבה 2 - לוקאלית (פיתוח):
   - הקובץ הזה רץ דרך sandbox.py: python sandbox.py
   - משתמש ב-ngrok
   - רץ על פורט 10000 עם uvicorn

⚠️  אל תשנה את הקובץ הזה כדי שיתאים לסביבה לוקאלית!
   הסביבה ברנדר לא אמורה לדעת בכלל על sandbox.py!
   כל שינוי כאן ישפיע על הסביבה ברנדר!

🚨 הפעלה בסביבה לוקאלית:
   python sandbox.py  ✅
   
   אל תפעיל ישירות:
   python main.py  ❌

================================================================================

bot_setup.py
------------
קובץ זה עוסק רק בהגדרות והכנות כלליות של הבוט (שאינן תלויות סביבה).
הרציונל: אתחול סביבתי, חיבור ל-Google Sheets, תזמון דוחות, והוספת handlers.
"""

# =============================================
# bot_setup.py — סטאפ כללי של הבוט (לא תלוי סביבה)
# -------------------------------------------------------------
# אין להפעיל כאן ngrok או הגדרת webhook ל-local!
# כל קוד סביבת פיתוח לוקאלית (כולל ngrok/webhook) נמצא אך ורק ב-sandbox.py
# =============================================

import os
import subprocess
import sys
import time
import requests
import logging
from telegram.ext import ApplicationBuilder, MessageHandler, filters
from config import TELEGRAM_BOT_TOKEN, config
from sheets_handler import increment_code_try, get_user_summary, update_user_profile, log_to_sheets, check_user_access, register_user, approve_user, ensure_user_state_row
from notifications import send_startup_notification
from messages import get_welcome_messages
from utils import log_event_to_file, update_chat_history, get_chat_history_messages, send_error_stats_report, send_usage_report
from gpt_a_handler import get_main_response
from gpt_b_handler import summarize_bot_reply
from apscheduler.schedulers.background import BackgroundScheduler
from daily_summary import send_daily_summary
import pytz
from message_handler import handle_message

# בדיקת קיום קבצים קריטיים
critical_files = [
    "data/gpt_usage_log.jsonl",
    "data/chat_history.json",
    "data/bot_errors.jsonl"
]
for file_path in critical_files:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            if file_path.endswith('.json'):
                f.write('{}')
            else:
                f.write('')

# --- קטעי התקנה והרצה לוקאלית (Windows בלבד) ---
if os.name == 'nt':
    # 1. בדיקת venv והפעלה
    venv_path = os.path.join(os.getcwd(), 'venv')
    if not os.path.exists(venv_path):
        print('🔧 יוצר venv חדש...')
        subprocess.run([sys.executable, '-m', 'venv', 'venv'])
    else:
        print('✅ venv קיים')

    # 2. התקנת כל התלויות
    print('🔧 מתקין תלויות מ-requirements.txt...')
    subprocess.run([os.path.join('venv', 'Scripts', 'python.exe'), '-m', 'pip', 'install', '--upgrade', 'pip'])
    subprocess.run([os.path.join('venv', 'Scripts', 'python.exe'), '-m', 'pip', 'install', '-r', 'requirements.txt'])
    subprocess.run([os.path.join('venv', 'Scripts', 'python.exe'), '-m', 'pip', 'install', 'uvicorn', 'requests'])

# יצירת אפליקציית טלגרם
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# חיבור ל-Google Sheets
def connect_google_sheets(): # מתחבר ל-Google Sheets, טוען גיליונות עיקריים, ושומר אותם ב-bot_data
    """
    מתחבר ל-Google Sheets, טוען גיליונות עיקריים, ושומר אותם ב-bot_data.
    פלט: אין (מעדכן app.bot_data)
    """
    try:
        logging.info("🔗 מתחבר ל-Google Sheets...")
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config["SERVICE_ACCOUNT_DICT"], scope)
        sheet = gspread.authorize(creds).open_by_key(config["GOOGLE_SHEET_ID"]).worksheet(config["SHEET_USER_TAB"])  # בטוח כי SHEET_USER_TAB מוגדר ב-config.json
        sheet_states = gspread.authorize(creds).open_by_key(config["GOOGLE_SHEET_ID"]).worksheet("user_states")
        app.bot_data["sheet"] = sheet
        app.bot_data["sheet_states"] = sheet_states
        logging.info("✅ חיבור ל-Google Sheets בוצע בהצלחה")
        print("✅ חיבור ל-Google Sheets בוצע בהצלחה")
    except Exception as ex:
        logging.critical(f"❌ שגיאה בהתחברות ל-Google Sheets: {ex}")
        print(f"❌ שגיאה בהתחברות ל-Google Sheets: {ex}")
        raise

# === תזמון דוחות אוטומטיים לאדמין ===
def setup_admin_reports(): # מתזמן דוחות אוטומטיים לאדמין (שגיאות ו-usage) לשעה 8:00 בבוקר
    """
    מתזמן דוחות אוטומטיים לאדמין (שגיאות ו-usage) לשעה 8:00 בבוקר.
    פלט: אין (מתזמן דוחות)
    """
    tz = pytz.timezone("Asia/Jerusalem")
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(send_error_stats_report, 'cron', hour=8, minute=0)
    scheduler.add_job(lambda: send_usage_report(1), 'cron', hour=8, minute=0)
    scheduler.add_job(lambda: send_daily_summary(days_back=1), 'cron', hour=8, minute=0)  #לא למחוק!! דוח כספים יומי על אתמול לא למחוק לעולם לא משנה מה

    scheduler.start()
    print("✅ תזמון דוחות אדמין הופעל (8:00 יומי)")

setup_admin_reports()

# הוספת handler להודעות טקסט
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# פונקציה שמבצעת את כל ההתקנה
def setup_bot(): # מבצע את כל ההתקנה הראשונית של הבוט: חיבור Sheets, שליחת התראה, החזרת app
    """
    מבצע את כל ההתקנה הראשונית של הבוט: חיבור Sheets, שליחת התראה, החזרת app.
    פלט: app (אפליקציית טלגרם)
    """
    connect_google_sheets()
    send_startup_notification()
    return app 