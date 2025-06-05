# =============================================
# bot_setup.py — התקנה והגדרה אוטומטית לסביבת פיתוח לוקאלית
# -------------------------------------------------------------
# קובץ זה מרכז את כל שלבי ההתקנה וההגדרה הראשוניים:
# 1. בדיקת venv והפעלה
# 2. התקנת כל התלויות (pip install ...)
# 3. בדיקת והרצת ngrok
# 4. איתור כתובת ngrok ועדכון webhook בטלגרם
# -------------------------------------------------------------
# הקובץ לא משנה כלום ב-Render, רק בסביבה לוקאלית.
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

# 3. בדיקת והרצת ngrok
ngrok_path = os.path.join('ngrok-v3-stable-windows-amd64', 'ngrok.exe')
if not os.path.exists(ngrok_path):
    print('❌ לא נמצא ngrok.exe! יש להוריד ולהניח בתיקיה ngrok-v3-stable-windows-amd64')
    sys.exit(1)
else:
    print('✅ ngrok.exe קיים')

# בדוק אם ngrok כבר רץ
import psutil
ngrok_running = any('ngrok' in p.name().lower() for p in psutil.process_iter())
if not ngrok_running:
    print('🚀 מפעיל ngrok על פורט 10000...')
    subprocess.Popen([ngrok_path, 'http', '10000'])
    time.sleep(3)  # מחכה ש-ngrok יעלה
else:
    print('✅ ngrok כבר רץ')

# 4. איתור כתובת ngrok ועדכון webhook בטלגרם

def get_ngrok_public_url():
    try:
        resp = requests.get('http://127.0.0.1:4040/api/tunnels')
        tunnels = resp.json()['tunnels']
        for tunnel in tunnels:
            if tunnel['proto'] == 'https':
                return tunnel['public_url']
        for tunnel in tunnels:
            if tunnel['proto'] == 'http':
                return tunnel['public_url']
    except Exception as e:
        print('❌ לא הצלחתי לשלוף כתובת ngrok:', e)
    return None

# טען את הטוקן מה-config.json
import json
with open(os.path.join('etc', 'secrets', 'config.json'), encoding='utf-8') as f:
    config = json.load(f)
TELEGRAM_BOT_TOKEN = config['TELEGRAM_BOT_TOKEN']

ngrok_url = get_ngrok_public_url()
if not ngrok_url:
    print('❌ לא נמצאה כתובת ngrok פעילה! ודא ש-ngrok רץ.')
    sys.exit(1)
webhook_url = ngrok_url + '/webhook'
set_webhook_url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}'
try:
    resp = requests.get(set_webhook_url)
    if resp.status_code == 200 and resp.json().get('ok'):
        print(f'✅ Webhook נקבע בטלגרם (אוטומטית לכתובת {webhook_url})!')
    else:
        print('⚠️ שגיאה בהגדרת Webhook:', resp.text)
except Exception as e:
    print('❌ שגיאה:', e)

print('\n✨ הכל מוכן! עכשיו תוכל להפעיל את השרת שלך כרגיל (uvicorn main:app_fastapi --host 0.0.0.0 --port 10000)')

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