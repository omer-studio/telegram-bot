# =============================================
# bot_setup.py — סטאפ כללי של הבוט (לא תלוי סביבה)
# -------------------------------------------------------------
# קובץ זה עוסק רק בהגדרות והכנות כלליות של הבוט (שאינן תלויות סביבה).
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
from utils import log_event_to_file, update_chat_history, get_chat_history_messages
from gpt_handler import get_main_response, summarize_bot_reply, smart_update_profile
from apscheduler.schedulers.background import BackgroundScheduler
from daily_summary import send_daily_summary
import pytz
from message_handler import handle_message

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

def connect_google_sheets():
    try:
        logging.info("🔗 מתחבר ל-Google Sheets...")
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config["SERVICE_ACCOUNT_DICT"], scope)
        sheet = gspread.authorize(creds).open_by_key(config["GOOGLE_SHEET_ID"]).worksheet(config["SHEET_USER_TAB"])
        sheet_states = gspread.authorize(creds).open_by_key(config["GOOGLE_SHEET_ID"]).worksheet("user_states")
        app.bot_data["sheet"] = sheet
        app.bot_data["sheet_states"] = sheet_states
        logging.info("✅ חיבור ל-Google Sheets בוצע בהצלחה")
        print("✅ חיבור ל-Google Sheets בוצע בהצלחה")
    except Exception as ex:
        logging.critical(f"❌ שגיאה בהתחברות ל-Google Sheets: {ex}")
        print(f"❌ שגיאה בהתחברות ל-Google Sheets: {ex}")
        raise

# תזמון דוח יומי אוטומטי
scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Bangkok"))
scheduler.add_job(send_daily_summary, 'cron', hour=10, minute=38)
scheduler.start()

# הוספת handler להודעות טקסט
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# פונקציה שמבצעת את כל ההתקנה

def setup_bot():
    connect_google_sheets()
    send_startup_notification()
    return app 