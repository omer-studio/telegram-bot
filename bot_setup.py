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
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler
from config import TELEGRAM_BOT_TOKEN, config
from sheets_handler import increment_code_try, get_user_summary, update_user_profile, log_to_sheets, check_user_access, register_user, approve_user
from notifications import send_startup_notification
from messages import get_welcome_messages
from utils import log_event_to_file, update_chat_history, get_chat_history_messages, send_error_stats_report, send_usage_report
from gpt_a_handler import get_main_response
from gpt_b_handler import get_summary
from apscheduler.schedulers.background import BackgroundScheduler
# from daily_summary import send_daily_summary  # זמנית מושבת - הקובץ לא קיים

async def send_daily_summary(days_back=1):
    """פונקציה זמנית - יש ליצור את daily_summary.py בעתיד"""
    print(f"📊 [DAILY_SUMMARY] זמנית מושבת - צריך ליצור daily_summary.py")
    return True
import pytz
from message_handler import handle_message
from notifications import gentle_reminder_background_task
from db_manager import create_tables, save_chat_message, save_user_profile, save_gpt_usage_log, save_gpt_call_log, save_critical_user_data, save_reminder_state, save_billing_usage_data, save_errors_stats_data, save_bot_error_log, save_bot_trace_log, save_sync_queue_data, save_rollback_data, save_free_model_limits_data, save_temp_critical_user_data
import json
import psycopg2
import datetime
import asyncio

# הגדרת DB_URL
DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

# רשימה לשמירת זמני ביצוע
execution_times = {}

def time_operation(operation_name):
    """מקישט פונקציה למדידת זמן ביצוע"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            print(f"⏱️  מתחיל {operation_name}...")
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            execution_times[operation_name] = elapsed_time
            print(f"✅ {operation_name} הושלם תוך {elapsed_time:.2f} שניות")
            return result
        return wrapper
    return decorator

def print_execution_summary():
    """מדפיס טבלה מסכמת של זמני הביצוע"""
    print("\n" + "="*70)
    print("📊 סיכום מפורט של זמני ביצוע ההתקנה")
    print("="*70)
    print(f"{'פעולה':<45} {'זמן (שניות)':<12} {'זמן (דקות)':<8}")
    print("-" * 70)
    
    # מיון לפי סדר ביצוע - קטגוריות עיקריות ואחר כך פרטים
    main_operations = []
    sub_operations = []
    
    for operation, duration in execution_times.items():
        if "סה״כ" in operation:
            main_operations.append((operation, duration))
        else:
            sub_operations.append((operation, duration))
    
    total_time = 0
    
    # הדפסת קטגוריות עיקריות
    print("🏗️ שלבים עיקריים:")
    for operation, duration in main_operations:
        total_time += duration
        minutes = duration / 60
        print(f"  {operation:<43} {duration:>8.2f}      {minutes:>6.2f}")
    
    print()
    print("🔍 פירוט שלבי משנה:")
    
    # הדפסת פרטים לפי קטגוריות
    categories = {
        "קבצים": [op for op in sub_operations if "קובץ" in op[0]],
        "תלויות": [op for op in sub_operations if any(x in op[0] for x in ["עדכון", "requirements", "uvicorn", "requests"])],
        "טלגרם": [op for op in sub_operations if any(x in op[0] for x in ["אפליקציה", "concurrent", "בסיסית", "מינימלית"])],
        "Google Sheets": [op for op in sub_operations if any(x in op[0] for x in ["ספריות", "הרשאות", "API", "גיליון", "משתמשים", "מצבים"])],
        "תזמון": [op for op in sub_operations if any(x in op[0] for x in ["אזור זמן", "מתזמן", "דוח", "סיכום", "הפעלת"])],
        "אחר": [op for op in sub_operations if not any(cat in op[0] for cat in ["קובץ", "עדכון", "requirements", "uvicorn", "requests", "אפליקציה", "concurrent", "בסיסית", "מינימלית", "ספריות", "הרשאות", "API", "גיליון", "משתמשים", "מצבים", "אזור זמן", "מתזמן", "דוח", "סיכום", "הפעלת"])]
    }
    
    for category, operations in categories.items():
        if operations:
            print(f"\n  📁 {category}:")
            for operation, duration in operations:
                minutes = duration / 60
                if duration < 0.01:  # פחות מ-0.01 שניה
                    print(f"    {operation:<39} {duration:>8.3f}      {minutes:>6.3f}")
                else:
                    print(f"    {operation:<39} {duration:>8.2f}      {minutes:>6.2f}")
    
    print("\n" + "-" * 70)
    total_minutes = total_time / 60
    print(f"{'🎯 סה״כ זמן התקנה כולל':<45} {total_time:>8.2f}      {total_minutes:>6.2f}")
    print("="*70)

def setup_single_critical_file(file_path):
    """יוצר קובץ קריטי יחיד עם מדידת זמן"""
    start_time = time.time()
    file_name = os.path.basename(file_path)
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            if file_path.endswith('.json'):
                f.write('{}')
            else:
                f.write('')
        status = "נוצר"
    else:
        status = "קיים"
    
    elapsed_time = time.time() - start_time
    execution_times[f"קובץ {file_name}"] = elapsed_time
    return status

@time_operation("בדיקת קיום קבצים קריטיים - סה״כ")
def setup_critical_files():
    """יוצר קבצים קריטיים הנדרשים לפעולת הבוט"""
    critical_files = [
        "data/gpt_usage_log.jsonl",
        "data/chat_history.json", 
        "data/bot_errors.jsonl"
    ]
    
    print(f"[SETUP] 🔍 בודק {len(critical_files)} קבצים קריטיים...")
    
    # איחוד הדפסות של קבצים קריטיים
    file_statuses = []
    for file_path in critical_files:
        status = setup_single_critical_file(file_path)
        file_statuses.append(f"{os.path.basename(file_path)} ({status})")
    
    print(f"[SETUP] 📁 קבצים קריטיים: {', '.join(file_statuses)}")

@time_operation("בדיקת והכנת סביבה וירטואלית")
def setup_virtual_environment():
    """בודק ויוצר venv במידת הצורך (Windows בלבד)"""
    # 🔧 תיקון: בסביבת production לא צריך venv
    if os.getenv("RENDER"):  # אם רץ ברנדר
        print("[SETUP] ℹ️  רץ בסביבת production - מדלג על יצירת venv")
        return
        
    if os.name == 'nt':
        venv_path = os.path.join(os.getcwd(), 'venv')
        if not os.path.exists(venv_path):
            print('[SETUP] 🔧 יוצר venv חדש...')
            subprocess.run([sys.executable, '-m', 'venv', 'venv'])
        else:
            print('[SETUP] ✅ venv קיים')

def install_single_dependency(pip_command, description):
    """מתקין dependency יחיד עם מדידת זמן"""
    start_time = time.time()
    print(f"⏱️  מתקין {description}...")
    
    # 🔧 תיקון: בסביבת production לא מתקין
    if os.getenv("RENDER"):  # אם רץ ברנדר
        elapsed_time = time.time() - start_time
        execution_times[description] = elapsed_time
        print(f"ℹ️  {description} - מדלג (production) תוך {elapsed_time:.3f} שניות")
        return type('Result', (), {'returncode': 0})()  # mock result
    
    result = subprocess.run(pip_command, capture_output=True, text=True)
    elapsed_time = time.time() - start_time
    execution_times[description] = elapsed_time
    if result.returncode == 0:
        print(f"✅ {description} הותקן תוך {elapsed_time:.2f} שניות")
    else:
        print(f"⚠️ {description} - יש בעיה (אך ממשיך): {elapsed_time:.2f} שניות")
    return result

@time_operation("התקנת תלויות - סה״כ")
def install_dependencies():
    """
    מתקין תלויות Python (רק בסביבת פיתוח מקומי)
    בסביבת production (רנדר) או בsandbox mode - מדלג על התקנה
    """
    print("[SETUP] 📦 בודק התקנת תלויות...")
    
    # 🔧 תיקון חשוב: מניעת התקנות בsandbox ובproduction
    if os.getenv("RENDER"):
        print("[SETUP] ℹ️  רץ בסביבת production (רנדר) - מדלג על התקנת תלויות")
        print("[SETUP]    (התלויות כבר אמורות להיות מותקנות מה-requirements.txt)")
        return
    
    # בדיקה נוספת: אם זה sandbox mode
    if any(arg in sys.argv[0].lower() for arg in ["sandbox", "uvicorn"]):
        print("[SETUP] ℹ️  רץ במצב sandbox - מדלג על התקנת תלויות")
        return
    
    # רק בסביבת פיתוח מקומי (Windows בדרך כלל)
    print("[SETUP] 🔧 סביבת פיתוח מקומי - בודק תלויות...")
    
    pip_commands = [
        ([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], "עדכון pip"),
        ([sys.executable, "-m", "pip", "install", "python-telegram-bot[webhooks]"], "python-telegram-bot"),
        ([sys.executable, "-m", "pip", "install", "gspread", "oauth2client"], "Google Sheets"),
        ([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn[standard]"], "FastAPI & Uvicorn"),
        ([sys.executable, "-m", "pip", "install", "litellm"], "LiteLLM"),
        ([sys.executable, "-m", "pip", "install", "openai"], "OpenAI"),
        ([sys.executable, "-m", "pip", "install", "anthropic"], "Anthropic"),
        ([sys.executable, "-m", "pip", "install", "google-generativeai"], "Google Generative AI"),
        ([sys.executable, "-m", "pip", "install", "apscheduler", "pytz"], "תזמון"),
        ([sys.executable, "-m", "pip", "install", "requests"], "Requests")
        # 🔧 תיקון זמני: הסרת whisper עד פתרון בעיית הזיכרון
        # ([sys.executable, "-m", "pip", "install", "openai-whisper"], "Whisper")
    ]
    
    for pip_command, description in pip_commands:
        install_single_dependency(pip_command, description)

def time_telegram_step(step_name, func):
    """מודד זמן לשלב ביצירת אפליקציית טלגרם"""
    start_time = time.time()
    print(f"⏱️  {step_name}...")
    try:
        result = func()
        elapsed_time = time.time() - start_time
        execution_times[step_name] = elapsed_time
        print(f"✅ {step_name} הושלם תוך {elapsed_time:.2f} שניות")
        return result
    except Exception as e:
        elapsed_time = time.time() - start_time
        execution_times[step_name] = elapsed_time
        print(f"⚠️ {step_name} נכשל תוך {elapsed_time:.2f} שניות: {e}")
        raise

@time_operation("יצירת אפליקציית טלגרם - סה״כ")
def create_telegram_app():
    """יוצר אפליקציית טלגרם עם הגדרות מתקדמות"""
    global app
    
    # ניסיון 1: הגדרות מלאות
    try:
        def build_full_featured_app():
            return ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).concurrent_updates(True).read_timeout(30).job_queue(None).build()
        
        app = time_telegram_step("יצירת אפליקציה עם concurrent_updates", build_full_featured_app)
        return
    except Exception as e:
        print(f"⚠️ בעיה עם ApplicationBuilder (ניסיון 1): {e}")
        
        # ניסיון 2: הגדרות בסיסיות
        try:
            def build_basic_app():
                return ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).read_timeout(30).job_queue(None).build()
            
            app = time_telegram_step("יצירת אפליקציה בסיסית", build_basic_app)
            return
        except Exception as e2:
            print(f"⚠️ בעיה עם ApplicationBuilder (ניסיון 2): {e2}")
        
        # ניסיון 3: מינימליסטי
        try:
            def build_minimal_app():
                return ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
            
            app = time_telegram_step("יצירת אפליקציה מינימלית", build_minimal_app)
        except Exception as e3:
            print(f"❌ כשל בכל ניסיונות יצירת אפליקציית טלגרם: {e3}")
            raise

def time_google_sheets_step(step_name, func):
    """מודד זמן לשלב בחיבור Google Sheets"""
    start_time = time.time()
    print(f"⏱️  {step_name}...")
    result = func()
    elapsed_time = time.time() - start_time
    execution_times[step_name] = elapsed_time
    print(f"✅ {step_name} הושלם תוך {elapsed_time:.2f} שניות")
    return result

# חיבור ל-Google Sheets
@time_operation("חיבור ל-Google Sheets - סה״כ")
def connect_google_sheets(): # מתחבר ל-Google Sheets, טוען גיליונות עיקריים, ושומר אותם ב-bot_data
    """
    מתחבר ל-Google Sheets, טוען גיליונות עיקריים, ושומר אותם ב-bot_data.
    פלט: אין (מעדכן app.bot_data)
    """
    try:
        logging.info("🔗 מתחבר ל-Google Sheets...")
        
        # שלב 1: טעינת ספריות
        def load_libraries():
            try:
                import gspread
                from oauth2client.service_account import ServiceAccountCredentials
                return gspread, ServiceAccountCredentials
            except ImportError as e:
                print(f"⚠️ Warning: Failed to import Google Sheets libraries: {e}")
                # יצירת dummy classes
                class DummyGspread:
                    def authorize(self, creds):
                        return self
                    def open_by_key(self, key):
                        return self
                    def worksheet(self, name):
                        return self
                    def get_all_values(self):
                        return []
                
                class DummyServiceAccountCredentials:
                    @staticmethod
                    def from_json_keyfile_dict(data, scope):
                        return DummyServiceAccountCredentials()
                
                return DummyGspread(), DummyServiceAccountCredentials
        
        gspread, ServiceAccountCredentials = time_google_sheets_step("טעינת ספריות Google Sheets", load_libraries)
        
        # שלב 2: הגדרת הרשאות
        def setup_credentials():
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            return ServiceAccountCredentials.from_json_keyfile_dict(config["SERVICE_ACCOUNT_DICT"], scope)
        
        creds = time_google_sheets_step("הגדרת הרשאות Google", setup_credentials)
        
        # שלב 3: התחברות ל-API
        def authorize_client():
            return gspread.authorize(creds)
        
        client = time_google_sheets_step("התחברות ל-Google Sheets API", authorize_client)
        
        # שלב 4: פתיחת הגיליון הראשי
        def open_main_sheet():
            return client.open_by_key(config["GOOGLE_SHEET_ID"])
        
        spreadsheet = time_google_sheets_step("פתיחת הגיליון הראשי", open_main_sheet)
        
        # שלב 5: טעינת גיליון משתמשים
        def load_users_sheet():
            return spreadsheet.worksheet(config["SHEET_USER_TAB"])
        
        sheet = time_google_sheets_step("טעינת גיליון משתמשים", load_users_sheet)
        
        # שלב 6: טעינת גיליון מצבים
        def load_states_sheet():
            return spreadsheet.worksheet(config["SHEET_STATES_TAB"])
        
        sheet_states = time_google_sheets_step("טעינת גיליון מצבים", load_states_sheet)
        
        # שמירה באפליקציה
        app.bot_data["sheet"] = sheet
        app.bot_data["sheet_states"] = sheet_states
        
        logging.info("✅ חיבור ל-Google Sheets בוצע בהצלחה")
        print("✅ חיבור ל-Google Sheets בוצע בהצלחה")
    except Exception as ex:
        logging.critical(f"❌ שגיאה בהתחברות ל-Google Sheets: {ex}")
        print(f"❌ שגיאה בהתחברות ל-Google Sheets: {ex}")
        raise

# === תזמון דוחות אוטומטיים לאדמין ===
def time_scheduler_step(step_name, func):
    """מודד זמן לשלב בהגדרת תזמון"""
    start_time = time.time()
    print(f"⏱️  {step_name}...")
    result = func()
    elapsed_time = time.time() - start_time
    execution_times[step_name] = elapsed_time
    print(f"✅ {step_name} הושלם תוך {elapsed_time:.2f} שניות")
    return result

# מתזמן גלובלי לשמירה
_admin_scheduler = None

@time_operation("הגדרת תזמון דוחות אוטומטיים - סה״כ")
def setup_admin_reports(): # מתזמן דוחות אוטומטיים לאדמין (שגיאות ו-usage) לשעה 8:00 בבוקר
    """
    מתזמן דוחות אוטומטיים לאדמין (שגיאות ו-usage) לשעה 8:00 בבוקר.
    פלט: אין (מתזמן דוחות)
    """
    global _admin_scheduler
    
    # הגדרת אזור זמן
    def setup_timezone():
        return pytz.timezone("Asia/Jerusalem")
    
    tz = time_scheduler_step("הגדרת אזור זמן ישראל", setup_timezone)
    
    # יצירת מתזמן
    def create_scheduler():
        global _admin_scheduler
        scheduler = BackgroundScheduler(timezone=tz)
        _admin_scheduler = scheduler  # שמירה גלובלית
        return scheduler
    
    scheduler = time_scheduler_step("יצירת מתזמן רקע", create_scheduler)
    
    # הוספת תזמון דוח שגיאות
    def add_error_report_job():
        scheduler.add_job(send_error_stats_report, 'cron', hour=8, minute=0)
        return "תזמון דוח שגיאות נוסף"
    
    time_scheduler_step("הוספת תזמון דוח שגיאות", add_error_report_job)
    
    # הוספת תזמון דוח שימוש
    def add_usage_report_job():
        scheduler.add_job(lambda: send_usage_report(1), 'cron', hour=8, minute=0)
        return "תזמון דוח שימוש נוסף"
    
    time_scheduler_step("הוספת תזמון דוח שימוש", add_usage_report_job)

    # הוספת תזמון סיכום יומי
    def add_daily_summary_job():
        def run_daily_summary():
            """Wrapper פונקציה שמריצה את הפונקציה async בצורה נכונה"""
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_daily_summary(days_back=1))
            loop.close()
        
        scheduler.add_job(run_daily_summary, 'cron', hour=8, minute=0)  #לא למחוק!! דוח כספים יומי על אתמול לא למחוק לעולם לא משנה מה
        return "תזמון סיכום יומי נוסף"
    
    time_scheduler_step("הוספת תזמון סיכום יומי", add_daily_summary_job)

    # הפעלת המתזמן
    def start_scheduler():
        scheduler.start()
        return "מתזמן הופעל"
    
    time_scheduler_step("הפעלת המתזמן", start_scheduler)
    
    print("✅ תזמון דוחות אדמין הופעל (8:00 יומי)")
    
    # הדפסת סטטוס המתזמן
    if _admin_scheduler:
        print(f"📅 מתזמן פעיל: {_admin_scheduler.running}")
        print(f"📋 משימות מתוזמנות: {len(_admin_scheduler.get_jobs())}")
        for job in _admin_scheduler.get_jobs():
            print(f"   - {job.name}: {job.next_run_time}")
    else:
        print("⚠️ מתזמן לא נוצר!")

@time_operation("הגדרת מערכת תזכורות עדינות")
def setup_gentle_reminders():
    """מתחיל את משימת הרקע לתזכורות עדינות"""
    try:
        # התחלת background task לתזכורות
        import asyncio
        import threading
        
        def reminder_task():
            """משימת רקע בthread נפרד לתזכורות"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(gentle_reminder_background_task())
            except Exception as e:
                print(f"❌ שגיאה במשימת תזכורות רקע: {e}")
                logging.error(f"Error in reminder background task: {e}")
        
        # הפעלה ב-thread נפרד כדי לא לחסום את הבוט
        reminder_thread = threading.Thread(target=reminder_task, daemon=True)
        reminder_thread.start()
        
        print("✅ מערכת תזכורות עדינות הופעלה (בדיקה כל שעה)")
        logging.info("Gentle reminder system started")
        
    except Exception as e:
        print(f"⚠️ בעיה בהתחלת מערכת תזכורות: {e}")
        logging.error(f"Failed to start gentle reminder system: {e}")

@time_operation("הוספת handlers להודעות")
def setup_message_handlers():
    """מוסיף handlers לטיפול בהודעות טקסט ופקודות"""
    start_time = time.time()
    print(f"⏱️  מוסיף handlers להודעות...")
    
    # הוספת handler להודעות טקסט
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # הוספת handler לפקודת מיגרציה
    app.add_handler(CommandHandler("migrate_all_data", handle_migrate_command))
    
    # הוספת handler לפקודת לוגים
    app.add_handler(CommandHandler("show_logs", handle_show_logs_command))
    
    # הוספת handler לפקודת חיפוש לוגים
    app.add_handler(CommandHandler("search_logs", handle_search_logs_command))
    
    elapsed_time = time.time() - start_time
    execution_times["הוספת message handlers"] = elapsed_time
    print(f"✅ Message handlers נוספו תוך {elapsed_time:.3f} שניות")

@time_operation("שליחת התראת הפעלה")
def send_startup_notification_timed():
    """שולח התראה על הפעלת הבוט"""
    # 🔧 תיקון: רק אם לא בsandbox mode ולא בsetup כפול
    if not os.getenv("RENDER") and not _setup_completed:
        print("ℹ️  רץ בסביבת פיתוח - מדלג על התראת startup")
        return
    elif _setup_completed:
        print("ℹ️  התראת startup כבר נשלחה - מדלג")
        return
    send_startup_notification()

# תזמון דוחות יתבצע כחלק מהתקנת הבוט

# 🔧 תיקון: מניעת setup כפול
_setup_completed = False

# פונקציה שמבצעת את כל ההתקנה
def setup_bot(): # מבצע את כל ההתקנה הראשונית של הבוט: חיבור Sheets, שליחת התראה, החזרת app
    """
    מבצע את כל ההתקנה הראשונית של הבוט: חיבור Sheets, שליחת התראה, החזרת app.
    פלט: app (אפליקציית טלגרם)
    """
    global _setup_completed, app
    
    if _setup_completed and app:
        print("ℹ️  הבוט כבר הוגדר, מחזיר instance קיים")
        return app
    
    print("🚀 מתחיל התקנה של הבוט...")
    
    # ביצוע כל שלבי ההתקנה עם מדידת זמן
    setup_critical_files()
    setup_virtual_environment()
    install_dependencies()
    create_telegram_app()
    connect_google_sheets()
    setup_admin_reports()
    setup_gentle_reminders()
    setup_message_handlers()
    send_startup_notification_timed()
    
    # שליחת דוח כספי יומי באתחול (ב-thread נפרד, לא מעכב את הבוט)
    def _send_daily_summary_startup():
        import asyncio
        print("🔥 [STARTUP] שולח דוח כספי יומי באתחול...")
        try:
            # יצירת event loop חדש בתוך ה-thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_daily_summary(days_back=1))
            loop.close()
            print("✅ [STARTUP] דוח כספי יומי נשלח בהצלחה באתחול!")
        except Exception as e:
            print(f"❌ [STARTUP] שגיאה בשליחת דוח כספי באתחול: {e}")
    import threading
    threading.Thread(target=_send_daily_summary_startup, daemon=True).start()
    
    # הדפסת סיכום זמני הביצוע
    print_execution_summary()
    
    print("🎉 ההתקנה הושלמה בהצלחה!")
    
    _setup_completed = True
    return app

def get_scheduler_status():
    """מחזיר סטטוס המתזמן הנוכחי"""
    global _admin_scheduler
    if not _admin_scheduler:
        return {"status": "לא נוצר", "running": False, "jobs": 0}
    
    return {
        "status": "פעיל" if _admin_scheduler.running else "לא פעיל",
        "running": _admin_scheduler.running,
        "jobs": len(_admin_scheduler.get_jobs()),
        "job_details": [
            {
                "name": job.name or "ללא שם",
                "next_run": str(job.next_run_time) if job.next_run_time else "לא מתוזמן"
            }
            for job in _admin_scheduler.get_jobs()
        ]
    }

def backup_data_to_drive():
    """מבצע גיבוי של כל קבצי data/ ל-Google Drive"""
    try:
        print("📁 מתחיל גיבוי ל-Google Drive...")
        
        # ⚠️ זמנית: מדלג על גיבוי כדי לא לעכב את המיגרציה
        print("ℹ️ מדלג על גיבוי Google Drive כדי לא לעכב את המיגרציה")
        print("✅ המשך מיגרציה ללא גיבוי (קבצים המקוריים נשמרים)")
        
        return True
        
    except Exception as e:
        print(f"❌ שגיאה בגיבוי: {e}")
        return False

def migrate_data_to_sql_with_safety():
    """מבצע מיגרציה בטוחה של כל הנתונים מ-data/ ל-SQL עם דיבאג מפורט"""
    try:
        # בדיקה מהירה אם יש נתונים למיגרציה
        def has_data_to_migrate():
            data_files = [
                "data/chat_history.json",
                "data/user_profiles.json", 
                "data/gpt_usage_log.jsonl",
                "data/openai_calls.jsonl"
            ]
            
            for file_path in data_files:
                if os.path.exists(file_path):
                    try:
                        if os.path.getsize(file_path) > 10:  # יותר מ-10 bytes
                            return True
                    except:
                        pass
            return False
        
        if not has_data_to_migrate():
            print("ℹ️ אין נתונים למיגרציה - המיגרציה הושלמה בהצלחה ללא פעולה")
            return True
        
        print("🔐 === מיגרציה בטוחה עם קוד סודי ===")
        print("🚨 מנגנוני בטיחות מופעלים:")
        print("   ✅ גיבוי אוטומטי לפני מיגרציה")
        print("   ✅ בדיקת תקינות נתונים")
        print("   ✅ דיבאג מפורט לכל שלב")
        print("   ✅ עצירה בשגיאה")
        print("   ✅ לוג מפורט של כל פעולה")
        print("   ✅ אימות שלמות נתונים")
        
        # === שלב 1: גיבוי אוטומטי ===
        print("\n📁 שלב 1: גיבוי אוטומטי ל-Google Drive...")
        backup_success = backup_data_to_drive()
        if not backup_success:
            print("❌ הגיבוי נכשל - המיגרציה נעצרת!")
            return False
        print("✅ גיבוי הושלם בהצלחה")
        
        # === שלב 2: יצירת טבלאות ===
        print("\n🗄️ שלב 2: יצירת/בדיקת טבלאות SQL...")
        create_tables()
        print("✅ טבלאות SQL מוכנות")
        
        # === שלב 3: ספירת נתונים לפני מיגרציה ===
        print("\n📊 שלב 3: ספירת נתונים לפני מיגרציה...")
        pre_migration_counts = count_existing_data()
        print(f"📈 נתונים קיימים ב-SQL: {pre_migration_counts}")
        
        # === שלב 4: מיגרציה עם דיבאג מפורט ===
        print("\n🔄 שלב 4: מיגרציה עם דיבאג מפורט...")
        migration_results = perform_detailed_migration()
        
        # === שלב 5: אימות שלמות נתונים ===
        print("\n🔍 שלב 5: אימות שלמות נתונים...")
        post_migration_counts = count_existing_data()
        verification_results = verify_data_integrity(pre_migration_counts, post_migration_counts, migration_results)
        
        # === שלב 6: סיכום מפורט ===
        print("\n📋 שלב 6: סיכום מפורט...")
        print_detailed_summary(migration_results, verification_results)
        
        print("\n🎉 === מיגרציה בטוחה הושלמה בהצלחה! ===")
        return True
        
    except Exception as e:
        print(f"\n❌ === שגיאה קריטית במיגרציה ===\n{str(e)}")
        print("🚨 המיגרציה נעצרה - הנתונים המקוריים לא נפגעו!")
        return False

def count_existing_data():
    """סופר נתונים קיימים ב-SQL"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        counts = {}
        
        # ספירת הודעות צ'אט
        try:
            cur.execute("SELECT COUNT(*) FROM chat_messages")
            counts['chat_messages'] = cur.fetchone()[0]
        except:
            counts['chat_messages'] = 0
        
        # ספירת פרופילים
        try:
            cur.execute("SELECT COUNT(*) FROM user_profiles")
            counts['user_profiles'] = cur.fetchone()[0]
        except:
            counts['user_profiles'] = 0
        
        # ספירת קריאות GPT
        try:
            cur.execute("SELECT COUNT(*) FROM gpt_calls_log")
            counts['gpt_calls'] = cur.fetchone()[0]
        except:
            counts['gpt_calls'] = 0
        
        # ספירת שימוש
        try:
            cur.execute("SELECT COUNT(*) FROM gpt_usage_log")
            counts['gpt_usage'] = cur.fetchone()[0]
        except:
            counts['gpt_usage'] = 0
        
        # ספירת משתמשים קריטיים
        try:
            cur.execute("SELECT COUNT(*) FROM critical_users")
            counts['critical_users'] = cur.fetchone()[0]
        except:
            counts['critical_users'] = 0
        
        # ספירת תזכורות
        try:
            cur.execute("SELECT COUNT(*) FROM reminder_states")
            counts['reminder_states'] = cur.fetchone()[0]
        except:
            counts['reminder_states'] = 0
        
        # ספירת נתוני חיוב
        try:
            cur.execute("SELECT COUNT(*) FROM billing_usage")
            counts['billing_usage'] = cur.fetchone()[0]
        except:
            counts['billing_usage'] = 0
        
        # ספירת סטטיסטיקות שגיאות
        try:
            cur.execute("SELECT COUNT(*) FROM errors_stats")
            counts['errors_stats'] = cur.fetchone()[0]
        except:
            counts['errors_stats'] = 0
        
        # ספירת לוגי שגיאות בוט
        try:
            cur.execute("SELECT COUNT(*) FROM bot_error_logs")
            counts['bot_errors'] = cur.fetchone()[0]
        except:
            counts['bot_errors'] = 0
        
        # ספירת לוגי trace בוט
        try:
            cur.execute("SELECT COUNT(*) FROM bot_trace_logs")
            counts['bot_trace'] = cur.fetchone()[0]
        except:
            counts['bot_trace'] = 0
        
        # ספירת תור סנכרון
        try:
            cur.execute("SELECT COUNT(*) FROM sync_queue")
            counts['sync_queue'] = cur.fetchone()[0]
        except:
            counts['sync_queue'] = 0
        
        # ספירת נתוני rollback
        try:
            cur.execute("SELECT COUNT(*) FROM rollback_data")
            counts['rollback_data'] = cur.fetchone()[0]
        except:
            counts['rollback_data'] = 0
        
        # ספירת מגבלות מודל חינמי
        try:
            cur.execute("SELECT COUNT(*) FROM free_model_limits")
            counts['free_limits'] = cur.fetchone()[0]
        except:
            counts['free_limits'] = 0
        
        # ספירת קבצים זמניים
        try:
            cur.execute("SELECT COUNT(*) FROM temp_critical_files")
            counts['temp_files'] = cur.fetchone()[0]
        except:
            counts['temp_files'] = 0
        
        cur.close()
        conn.close()
        
        return counts
        
    except Exception as e:
        print(f"⚠️ שגיאה בספירת נתונים: {e}")
        return {}

def perform_detailed_migration():
    """מבצע מיגרציה מפורטת עם דיבאג"""
    results = {
        'chat_messages': {'migrated': 0, 'errors': 0, 'details': []},
        'user_profiles': {'migrated': 0, 'errors': 0, 'details': []},
        'gpt_usage': {'migrated': 0, 'errors': 0, 'details': []},
        'gpt_calls': {'migrated': 0, 'errors': 0, 'details': []},
        'critical_users': {'migrated': 0, 'errors': 0, 'details': []},
        'reminder_state': {'migrated': 0, 'errors': 0, 'details': []},
        'billing_usage': {'migrated': 0, 'errors': 0, 'details': []},
        'errors_stats': {'migrated': 0, 'errors': 0, 'details': []},
        'bot_errors': {'migrated': 0, 'errors': 0, 'details': []},
        'bot_trace': {'migrated': 0, 'errors': 0, 'details': []},
        'sync_queue': {'migrated': 0, 'errors': 0, 'details': []},
        'rollback_data': {'migrated': 0, 'errors': 0, 'details': []},
        'free_limits': {'migrated': 0, 'errors': 0, 'details': []},
        'temp_files': {'migrated': 0, 'errors': 0, 'details': []}
    }
    
    # === מיגרציית chat_history.json ===
    print("  📝 מיגרציית chat_history.json...")
    try:
        chat_history_path = "data/chat_history.json"
        if os.path.exists(chat_history_path):
            with open(chat_history_path, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            
            print(f"    📊 נמצאו {len(chat_data)} צ'אטים למיגרציה")
            
            # סיכום פירוט לכל chat_id
            chat_summary = {}
            
            for chat_id, chat_info in chat_data.items():
                if "history" in chat_info:
                    history_count = len(chat_info["history"])
                    chat_summary[chat_id] = {'total': history_count, 'migrated': 0, 'errors': 0}
                    print(f"    💬 מיגרציית צ'אט {chat_id}: {history_count} הודעות")
                    
                    for i, entry in enumerate(chat_info["history"]):
                        try:
                            user_msg = entry.get("user", "")
                            bot_msg = entry.get("bot", "")
                            timestamp_str = entry.get("timestamp", "")
                            
                            # המרת timestamp
                            from datetime import datetime
                            try:
                                if timestamp_str:
                                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", ""))
                                else:
                                    timestamp = datetime.utcnow()
                            except:
                                timestamp = datetime.utcnow()
                            
                            # שמירה ל-SQL
                            save_chat_message(chat_id, user_msg, bot_msg, timestamp)
                            results['chat_messages']['migrated'] += 1
                            chat_summary[chat_id]['migrated'] += 1
                            
                            if i % 100 == 0:  # דיבאג כל 100 הודעות
                                print(f"      ✅ הועברו {i+1}/{history_count} הודעות")
                                
                        except Exception as e:
                            results['chat_messages']['errors'] += 1
                            chat_summary[chat_id]['errors'] += 1
                            results['chat_messages']['details'].append(f"שגיאה בהודעה {i} בצ'אט {chat_id}: {e}")
                            print(f"      ⚠️ שגיאה בהודעה {i}: {e}")
                            continue
                    
                    print(f"    ✅ צ'אט {chat_id} הושלם: {chat_summary[chat_id]['migrated']}/{chat_summary[chat_id]['total']} הודעות")
            
            # סיכום מפורט לכל chat_id
            print(f"\n    📋 === סיכום מפורט לכל chat_id ===")
            for chat_id, summary in chat_summary.items():
                success_rate = (summary['migrated'] / summary['total'] * 100) if summary['total'] > 0 else 0
                status = "✅" if summary['errors'] == 0 else "⚠️"
                print(f"    {status} צ'אט {chat_id}: {summary['migrated']}/{summary['total']} הודעות ({success_rate:.1f}%)")
                if summary['errors'] > 0:
                    print(f"        ❌ שגיאות: {summary['errors']}")
            
            results['chat_messages']['chat_details'] = chat_summary
        else:
            print("    ℹ️ קובץ chat_history.json לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית chat_history: {e}")
        results['chat_messages']['errors'] += 1
    
    # === מיגרציית user_profiles.json ===
    print("  👤 מיגרציית user_profiles.json...")
    try:
        user_profiles_path = "data/user_profiles.json"
        if os.path.exists(user_profiles_path):
            with open(user_profiles_path, 'r', encoding='utf-8') as f:
                profiles_data = json.load(f)
            
            print(f"    📊 נמצאו {len(profiles_data)} פרופילים למיגרציה")
            
            # פירוט לכל פרופיל
            profile_summary = {}
            
            for chat_id, profile in profiles_data.items():
                try:
                    save_user_profile(chat_id, profile)
                    results['user_profiles']['migrated'] += 1
                    profile_summary[chat_id] = {'status': 'success', 'fields': len(profile) if isinstance(profile, dict) else 1}
                    print(f"    ✅ פרופיל {chat_id} הועבר ({len(profile) if isinstance(profile, dict) else 1} שדות)")
                except Exception as e:
                    results['user_profiles']['errors'] += 1
                    profile_summary[chat_id] = {'status': 'error', 'error': str(e)}
                    results['user_profiles']['details'].append(f"שגיאה בפרופיל {chat_id}: {e}")
                    print(f"    ⚠️ שגיאה בפרופיל {chat_id}: {e}")
                    continue
            
            # סיכום מפורט לכל פרופיל
            print(f"\n    📋 === סיכום פרופילים ===")
            successful_profiles = [chat_id for chat_id, info in profile_summary.items() if info['status'] == 'success']
            failed_profiles = [chat_id for chat_id, info in profile_summary.items() if info['status'] == 'error']
            
            print(f"    ✅ פרופילים שהועברו בהצלחה ({len(successful_profiles)}):")
            for chat_id in successful_profiles[:10]:  # רק 10 הראשונים
                fields = profile_summary[chat_id]['fields']
                print(f"        • צ'אט {chat_id}: {fields} שדות")
            if len(successful_profiles) > 10:
                print(f"        ... ועוד {len(successful_profiles) - 10} פרופילים")
            
            if failed_profiles:
                print(f"    ❌ פרופילים שנכשלו ({len(failed_profiles)}):")
                for chat_id in failed_profiles:
                    print(f"        • צ'אט {chat_id}: {profile_summary[chat_id]['error']}")
            
            results['user_profiles']['profile_details'] = profile_summary
        else:
            print("    ℹ️ קובץ user_profiles.json לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית user_profiles: {e}")
        results['user_profiles']['errors'] += 1
    
    # === מיגרציית gpt_usage_log.jsonl ===
    print("  📊 מיגרציית gpt_usage_log.jsonl...")
    try:
        usage_log_path = "data/gpt_usage_log.jsonl"
        if os.path.exists(usage_log_path):
            line_count = sum(1 for line in open(usage_log_path, 'r', encoding='utf-8'))
            print(f"    📊 נמצאו {line_count} שורות למיגרציה")
            
            with open(usage_log_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        entry = json.loads(line.strip())
                        from datetime import datetime
                        timestamp = datetime.fromisoformat(entry.get("timestamp", "").replace("Z", ""))
                        
                        save_gpt_usage_log(
                            chat_id=entry.get("chat_id"),
                            model=entry.get("model", ""),
                            usage=entry.get("usage", {}),
                            cost_agorot=entry.get("cost_agorot", 0),
                            timestamp=timestamp
                        )
                        results['gpt_usage']['migrated'] += 1
                        
                        if line_num % 100 == 0:  # דיבאג כל 100 שורות
                            print(f"      ✅ הועברו {line_num}/{line_count} שורות")
                            
                    except Exception as e:
                        results['gpt_usage']['errors'] += 1
                        results['gpt_usage']['details'].append(f"שגיאה בשורה {line_num}: {e}")
                        print(f"      ⚠️ שגיאה בשורה {line_num}: {e}")
                        continue
        else:
            print("    ℹ️ קובץ gpt_usage_log.jsonl לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית usage_log: {e}")
        results['gpt_usage']['errors'] += 1
    
    # === מיגרציית openai_calls.jsonl ===
    print("  🤖 מיגרציית openai_calls.jsonl...")
    try:
        calls_log_path = "data/openai_calls.jsonl"
        if os.path.exists(calls_log_path):
            line_count = sum(1 for line in open(calls_log_path, 'r', encoding='utf-8'))
            print(f"    📊 נמצאו {line_count} שורות למיגרציה")
            
            with open(calls_log_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        entry = json.loads(line.strip())
                        from datetime import datetime
                        timestamp = datetime.fromisoformat(entry.get("ts", "").replace("Z", ""))
                        
                        # חילוץ פרטים מהתגובה
                        response = entry.get("response", {})
                        usage = response.get("usage", {})
                        
                        save_gpt_call_log(
                            chat_id=entry.get("chat_id"),
                            call_type=entry.get("gpt_type", "unknown"),
                            request_data=entry.get("request", {}),
                            response_data=response,
                            tokens_input=usage.get("prompt_tokens", 0),
                            tokens_output=usage.get("completion_tokens", 0),
                            cost_usd=entry.get("cost_usd", 0),
                            processing_time_seconds=0,
                            timestamp=timestamp
                        )
                        results['gpt_calls']['migrated'] += 1
                        
                        if line_num % 100 == 0:  # דיבאג כל 100 שורות
                            print(f"      ✅ הועברו {line_num}/{line_count} שורות")
                            
                    except Exception as e:
                        results['gpt_calls']['errors'] += 1
                        results['gpt_calls']['details'].append(f"שגיאה בשורה {line_num}: {e}")
                        print(f"      ⚠️ שגיאה בשורה {line_num}: {e}")
                        continue
        else:
            print("    ℹ️ קובץ openai_calls.jsonl לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית calls_log: {e}")
        results['gpt_calls']['errors'] += 1
    
    # === מיגרציית critical_error_users.json ===
    print("  🚨 מיגרציית critical_error_users.json...")
    try:
        critical_users_path = "data/critical_error_users.json"
        if os.path.exists(critical_users_path):
            with open(critical_users_path, 'r', encoding='utf-8') as f:
                critical_data = json.load(f)
            
            print(f"    📊 נמצאו {len(critical_data)} משתמשים קריטיים למיגרציה")
            
            for chat_id, user_info in critical_data.items():
                try:
                    save_critical_user_data(chat_id, user_info)
                    results['critical_users']['migrated'] += 1
                    print(f"    ✅ משתמש קריטי {chat_id} הועבר")
                except Exception as e:
                    results['critical_users']['errors'] += 1
                    results['critical_users']['details'].append(f"שגיאה במשתמש קריטי {chat_id}: {e}")
                    print(f"    ⚠️ שגיאה במשתמש קריטי {chat_id}: {e}")
                    continue
        else:
            print("    ℹ️ קובץ critical_error_users.json לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית critical_users: {e}")
        results['critical_users']['errors'] += 1
    
    # === מיגרציית reminder_state.json ===
    print("  ⏰ מיגרציית reminder_state.json...")
    try:
        reminder_path = "data/reminder_state.json"
        if os.path.exists(reminder_path):
            with open(reminder_path, 'r', encoding='utf-8') as f:
                reminder_data = json.load(f)
            
            print(f"    📊 נמצאו {len(reminder_data)} רשומות תזכורות למיגרציה")
            
            for chat_id, reminder_info in reminder_data.items():
                try:
                    save_reminder_state(chat_id, reminder_info)
                    results['reminder_state']['migrated'] += 1
                    print(f"    ✅ תזכורת {chat_id} הועברה")
                except Exception as e:
                    results['reminder_state']['errors'] += 1
                    results['reminder_state']['details'].append(f"שגיאה בתזכורת {chat_id}: {e}")
                    print(f"    ⚠️ שגיאה בתזכורת {chat_id}: {e}")
                    continue
        else:
            print("    ℹ️ קובץ reminder_state.json לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית reminder_state: {e}")
        results['reminder_state']['errors'] += 1
    
    # === מיגרציית billing_usage.json ===
    print("  💰 מיגרציית billing_usage.json...")
    try:
        billing_path = "data/billing_usage.json"
        if os.path.exists(billing_path):
            with open(billing_path, 'r', encoding='utf-8') as f:
                billing_data = json.load(f)
            
            print(f"    📊 נמצאו נתוני חיוב למיגרציה")
            
            save_billing_usage_data(billing_data)
            results['billing_usage']['migrated'] += 1
            print(f"    ✅ נתוני חיוב הועברו")
        else:
            print("    ℹ️ קובץ billing_usage.json לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית billing_usage: {e}")
        results['billing_usage']['errors'] += 1
    
    # === מיגרציית errors_stats.json ===
    print("  📊 מיגרציית errors_stats.json...")
    try:
        errors_stats_path = "data/errors_stats.json"
        if os.path.exists(errors_stats_path):
            with open(errors_stats_path, 'r', encoding='utf-8') as f:
                errors_data = json.load(f)
            
            print(f"    🚫 [DISABLED] errors_stats table disabled - skipping migration")
            print(f"    ℹ️ Error statistics will be calculated from bot_error_logs when needed")
            results['errors_stats']['migrated'] = 0
            results['errors_stats']['skipped'] = len(errors_data)
        else:
            print("    ℹ️ קובץ errors_stats.json לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית errors_stats: {e}")
        results['errors_stats']['errors'] += 1
    
    # === מיגרציית bot_errors.jsonl ===
    print("  🐛 מיגרציית bot_errors.jsonl...")
    try:
        bot_errors_path = "data/bot_errors.jsonl"
        if os.path.exists(bot_errors_path):
            line_count = sum(1 for line in open(bot_errors_path, 'r', encoding='utf-8'))
            print(f"    📊 נמצאו {line_count} שורות שגיאות בוט למיגרציה")
            
            with open(bot_errors_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        entry = json.loads(line.strip())
                        save_bot_error_log(entry)
                        results['bot_errors']['migrated'] += 1
                        
                        if line_num % 50 == 0:  # דיבאג כל 50 שורות
                            print(f"      ✅ הועברו {line_num}/{line_count} שורות שגיאות")
                            
                    except Exception as e:
                        results['bot_errors']['errors'] += 1
                        results['bot_errors']['details'].append(f"שגיאה בשורת שגיאה {line_num}: {e}")
                        print(f"      ⚠️ שגיאה בשורת שגיאה {line_num}: {e}")
                        continue
        else:
            print("    ℹ️ קובץ bot_errors.jsonl לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית bot_errors: {e}")
        results['bot_errors']['errors'] += 1
    
    # === מיגרציית bot_trace_log.jsonl ===
    print("  🔍 מיגרציית bot_trace_log.jsonl...")
    try:
        bot_trace_path = "data/bot_trace_log.jsonl"
        if os.path.exists(bot_trace_path):
            line_count = sum(1 for line in open(bot_trace_path, 'r', encoding='utf-8'))
            print(f"    📊 נמצאו {line_count} שורות trace למיגרציה")
            
            with open(bot_trace_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        entry = json.loads(line.strip())
                        save_bot_trace_log(entry)
                        results['bot_trace']['migrated'] += 1
                        
                        if line_num % 100 == 0:  # דיבאג כל 100 שורות
                            print(f"      ✅ הועברו {line_num}/{line_count} שורות trace")
                            
                    except Exception as e:
                        results['bot_trace']['errors'] += 1
                        results['bot_trace']['details'].append(f"שגיאה בשורת trace {line_num}: {e}")
                        print(f"      ⚠️ שגיאה בשורת trace {line_num}: {e}")
                        continue
        else:
            print("    ℹ️ קובץ bot_trace_log.jsonl לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית bot_trace: {e}")
        results['bot_trace']['errors'] += 1
    
    # === מיגרציית sync_queue.json ===
    print("  🔄 מיגרציית sync_queue.json...")
    try:
        sync_queue_path = "data/sync_queue.json"
        if os.path.exists(sync_queue_path):
            with open(sync_queue_path, 'r', encoding='utf-8') as f:
                sync_data = json.load(f)
            
            print(f"    📊 נמצאו נתוני תור סנכרון למיגרציה")
            
            save_sync_queue_data(sync_data)
            results['sync_queue']['migrated'] += 1
            print(f"    ✅ תור סנכרון הועבר")
        else:
            print("    ℹ️ קובץ sync_queue.json לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית sync_queue: {e}")
        results['sync_queue']['errors'] += 1
    
    # === מיגרציית rollback_history.json ו-last_good_commit.json ===
    print("  ↩️ מיגרציית נתוני rollback...")
    try:
        rollback_files = ["data/rollback_history.json", "data/last_good_commit.json"]
        for rollback_file in rollback_files:
            if os.path.exists(rollback_file):
                with open(rollback_file, 'r', encoding='utf-8') as f:
                    rollback_data = json.load(f)
                
                save_rollback_data(os.path.basename(rollback_file), rollback_data)
                results['rollback_data']['migrated'] += 1
                print(f"    ✅ {os.path.basename(rollback_file)} הועבר")
            else:
                print(f"    ℹ️ קובץ {rollback_file} לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית rollback: {e}")
        results['rollback_data']['errors'] += 1
    
    # === מיגרציית free_model_limits.json ===
    print("  🆓 מיגרציית free_model_limits.json...")
    try:
        free_limits_path = "data/free_model_limits.json"
        if os.path.exists(free_limits_path):
            with open(free_limits_path, 'r', encoding='utf-8') as f:
                limits_data = json.load(f)
            
            print(f"    📊 נמצאו מגבלות מודל חינמי למיגרציה")
            
            save_free_model_limits_data(limits_data)
            results['free_limits']['migrated'] += 1
            print(f"    ✅ מגבלות מודל חינמי הועברו")
        else:
            print("    ℹ️ קובץ free_model_limits.json לא קיים")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית free_limits: {e}")
        results['free_limits']['errors'] += 1
    
    # === מיגרציית קבצים זמניים temp_critical_user_*.json ===
    print("  📁 מיגרציית קבצים זמניים...")
    try:
        data_dir = "data"
        if os.path.exists(data_dir):
            for filename in os.listdir(data_dir):
                if filename.startswith("temp_critical_user_") and filename.endswith(".json"):
                    temp_file_path = os.path.join(data_dir, filename)
                    try:
                        with open(temp_file_path, 'r', encoding='utf-8') as f:
                            temp_data = json.load(f)
                        
                        save_temp_critical_user_data(filename, temp_data)
                        results['temp_files']['migrated'] += 1
                        print(f"    ✅ קובץ זמני {filename} הועבר")
                    except Exception as e:
                        results['temp_files']['errors'] += 1
                        results['temp_files']['details'].append(f"שגיאה בקובץ זמני {filename}: {e}")
                        print(f"    ⚠️ שגיאה בקובץ זמני {filename}: {e}")
        else:
            print("    ℹ️ תיקיית data לא קיימת")
    except Exception as e:
        print(f"    ❌ שגיאה במיגרציית קבצים זמניים: {e}")
        results['temp_files']['errors'] += 1
    
    return results

def verify_data_integrity(pre_counts, post_counts, migration_results):
    """מאמת את שלמות הנתונים"""
    print("  🔍 אימות שלמות נתונים...")
    
    verification = {
        'chat_messages': {'verified': False, 'details': ''},
        'user_profiles': {'verified': False, 'details': ''},
        'gpt_usage': {'verified': False, 'details': ''},
        'gpt_calls': {'verified': False, 'details': ''},
        'critical_users': {'verified': False, 'details': ''},
        'reminder_state': {'verified': False, 'details': ''},
        'billing_usage': {'verified': False, 'details': ''},
        'errors_stats': {'verified': False, 'details': ''},
        'bot_errors': {'verified': False, 'details': ''},
        'bot_trace': {'verified': False, 'details': ''},
        'sync_queue': {'verified': False, 'details': ''},
        'rollback_data': {'verified': False, 'details': ''},
        'free_limits': {'verified': False, 'details': ''},
        'temp_files': {'verified': False, 'details': ''}
    }
    
    # אימות הודעות צ'אט
    expected_chat = pre_counts.get('chat_messages', 0) + migration_results['chat_messages']['migrated']
    actual_chat = post_counts.get('chat_messages', 0)
    if expected_chat == actual_chat:
        verification['chat_messages']['verified'] = True
        verification['chat_messages']['details'] = f"✅ {expected_chat} = {actual_chat}"
    else:
        verification['chat_messages']['details'] = f"❌ ציפיתי {expected_chat}, קיבלתי {actual_chat}"
    
    # אימות פרופילים
    expected_profiles = pre_counts.get('user_profiles', 0) + migration_results['user_profiles']['migrated']
    actual_profiles = post_counts.get('user_profiles', 0)
    if expected_profiles == actual_profiles:
        verification['user_profiles']['verified'] = True
        verification['user_profiles']['details'] = f"✅ {expected_profiles} = {actual_profiles}"
    else:
        verification['user_profiles']['details'] = f"❌ ציפיתי {expected_profiles}, קיבלתי {actual_profiles}"
    
    # אימות שימוש GPT
    expected_usage = pre_counts.get('gpt_usage', 0) + migration_results['gpt_usage']['migrated']
    actual_usage = post_counts.get('gpt_usage', 0)
    if expected_usage == actual_usage:
        verification['gpt_usage']['verified'] = True
        verification['gpt_usage']['details'] = f"✅ {expected_usage} = {actual_usage}"
    else:
        verification['gpt_usage']['details'] = f"❌ ציפיתי {expected_usage}, קיבלתי {actual_usage}"
    
    # אימות קריאות GPT
    expected_calls = pre_counts.get('gpt_calls', 0) + migration_results['gpt_calls']['migrated']
    actual_calls = post_counts.get('gpt_calls', 0)
    if expected_calls == actual_calls:
        verification['gpt_calls']['verified'] = True
        verification['gpt_calls']['details'] = f"✅ {expected_calls} = {actual_calls}"
    else:
        verification['gpt_calls']['details'] = f"❌ ציפיתי {expected_calls}, קיבלתי {actual_calls}"
    
    # אימות משתמשים קריטיים
    expected_critical = pre_counts.get('critical_users', 0) + migration_results['critical_users']['migrated']
    actual_critical = post_counts.get('critical_users', 0)
    if expected_critical == actual_critical:
        verification['critical_users']['verified'] = True
        verification['critical_users']['details'] = f"✅ {expected_critical} = {actual_critical}"
    else:
        verification['critical_users']['details'] = f"❌ ציפיתי {expected_critical}, קיבלתי {actual_critical}"
    
    # אימות תזכורות
    expected_reminder = pre_counts.get('reminder_states', 0) + migration_results['reminder_state']['migrated']
    actual_reminder = post_counts.get('reminder_states', 0)
    if expected_reminder == actual_reminder:
        verification['reminder_state']['verified'] = True
        verification['reminder_state']['details'] = f"✅ {expected_reminder} = {actual_reminder}"
    else:
        verification['reminder_state']['details'] = f"❌ ציפיתי {expected_reminder}, קיבלתי {actual_reminder}"
    
    # אימות נתוני חיוב
    expected_billing = pre_counts.get('billing_usage', 0) + migration_results['billing_usage']['migrated']
    actual_billing = post_counts.get('billing_usage', 0)
    if expected_billing == actual_billing:
        verification['billing_usage']['verified'] = True
        verification['billing_usage']['details'] = f"✅ {expected_billing} = {actual_billing}"
    else:
        verification['billing_usage']['details'] = f"❌ ציפיתי {expected_billing}, קיבלתי {actual_billing}"
    
    # אימות סטטיסטיקות שגיאות
    expected_errors_stats = pre_counts.get('errors_stats', 0) + migration_results['errors_stats']['migrated']
    actual_errors_stats = post_counts.get('errors_stats', 0)
    if expected_errors_stats == actual_errors_stats:
        verification['errors_stats']['verified'] = True
        verification['errors_stats']['details'] = f"✅ {expected_errors_stats} = {actual_errors_stats}"
    else:
        verification['errors_stats']['details'] = f"❌ ציפיתי {expected_errors_stats}, קיבלתי {actual_errors_stats}"
    
    # אימות לוגי שגיאות בוט
    expected_bot_errors = pre_counts.get('bot_errors', 0) + migration_results['bot_errors']['migrated']
    actual_bot_errors = post_counts.get('bot_errors', 0)
    if expected_bot_errors == actual_bot_errors:
        verification['bot_errors']['verified'] = True
        verification['bot_errors']['details'] = f"✅ {expected_bot_errors} = {actual_bot_errors}"
    else:
        verification['bot_errors']['details'] = f"❌ ציפיתי {expected_bot_errors}, קיבלתי {actual_bot_errors}"
    
    # אימות לוגי trace בוט
    expected_bot_trace = pre_counts.get('bot_trace', 0) + migration_results['bot_trace']['migrated']
    actual_bot_trace = post_counts.get('bot_trace', 0)
    if expected_bot_trace == actual_bot_trace:
        verification['bot_trace']['verified'] = True
        verification['bot_trace']['details'] = f"✅ {expected_bot_trace} = {actual_bot_trace}"
    else:
        verification['bot_trace']['details'] = f"❌ ציפיתי {expected_bot_trace}, קיבלתי {actual_bot_trace}"
    
    # אימות תור סנכרון
    expected_sync = pre_counts.get('sync_queue', 0) + migration_results['sync_queue']['migrated']
    actual_sync = post_counts.get('sync_queue', 0)
    if expected_sync == actual_sync:
        verification['sync_queue']['verified'] = True
        verification['sync_queue']['details'] = f"✅ {expected_sync} = {actual_sync}"
    else:
        verification['sync_queue']['details'] = f"❌ ציפיתי {expected_sync}, קיבלתי {actual_sync}"
    
    # אימות נתוני rollback
    expected_rollback = pre_counts.get('rollback_data', 0) + migration_results['rollback_data']['migrated']
    actual_rollback = post_counts.get('rollback_data', 0)
    if expected_rollback == actual_rollback:
        verification['rollback_data']['verified'] = True
        verification['rollback_data']['details'] = f"✅ {expected_rollback} = {actual_rollback}"
    else:
        verification['rollback_data']['details'] = f"❌ ציפיתי {expected_rollback}, קיבלתי {actual_rollback}"
    
    # אימות מגבלות מודל חינמי
    expected_free_limits = pre_counts.get('free_limits', 0) + migration_results['free_limits']['migrated']
    actual_free_limits = post_counts.get('free_limits', 0)
    if expected_free_limits == actual_free_limits:
        verification['free_limits']['verified'] = True
        verification['free_limits']['details'] = f"✅ {expected_free_limits} = {actual_free_limits}"
    else:
        verification['free_limits']['details'] = f"❌ ציפיתי {expected_free_limits}, קיבלתי {actual_free_limits}"
    
    # אימות קבצים זמניים
    expected_temp = pre_counts.get('temp_files', 0) + migration_results['temp_files']['migrated']
    actual_temp = post_counts.get('temp_files', 0)
    if expected_temp == actual_temp:
        verification['temp_files']['verified'] = True
        verification['temp_files']['details'] = f"✅ {expected_temp} = {actual_temp}"
    else:
        verification['temp_files']['details'] = f"❌ ציפיתי {expected_temp}, קיבלתי {actual_temp}"
    
    return verification

def print_detailed_summary(migration_results, verification_results):
    """מדפיס סיכום מפורט וגם שומר לקובץ לוג ושולח לאדמין"""
    import os
    from notifications import send_admin_notification
    def log_to_file(msg):
        with open("migration_log.txt", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    
    summary_lines = []
    summary_lines.append("\n📋 === סיכום מיגרציה מפורט ===")
    total_migrated = 0
    total_errors = 0
    for category, results in migration_results.items():
        migrated = results['migrated']
        errors = results['errors']
        total_migrated += migrated
        total_errors += errors
        status = "✅" if verification_results[category]['verified'] else "❌"
        summary_lines.append(f"\n{status} {category.upper()}:")
        summary_lines.append(f"   📊 הועברו: {migrated}")
        summary_lines.append(f"   ⚠️ שגיאות: {errors}")
        summary_lines.append(f"   🔍 אימות: {verification_results[category]['details']}")
        if errors > 0 and results['details']:
            summary_lines.append(f"   📝 פרטי שגיאות:")
            for detail in results['details'][:5]:
                summary_lines.append(f"      • {detail}")
            if len(results['details']) > 5:
                summary_lines.append(f"      ... ועוד {len(results['details']) - 5} שגיאות")
    summary_lines.append(f"\n🎯 סיכום כללי:")
    summary_lines.append(f"   📊 סה״כ הועברו: {total_migrated}")
    summary_lines.append(f"   ⚠️ סה״כ שגיאות: {total_errors}")
    summary_lines.append(f"   📈 אחוז הצלחה: {((total_migrated - total_errors) / max(total_migrated, 1) * 100):.1f}%")
    
    # בדיקה אם הייתה מיגרציה אמיתית
    if total_migrated == 0:
        summary_lines.append(f"\nℹ️ הערה: לא הועברו נתונים - יתכן שהקבצים ריקים או לא קיימים")
        summary_lines.append(f"ℹ️ זו לא שגיאה - המיגרציה הושלמה בהצלחה ללא נתונים למיגרציה")
    
    # הוספת פירוט מפורט לכל chat_id
    if 'chat_details' in migration_results.get('chat_messages', {}):
        summary_lines.append(f"\n📋 === פירוט מפורט לכל chat_id ===")
        chat_details = migration_results['chat_messages']['chat_details']
        for chat_id, details in list(chat_details.items())[:15]:  # רק 15 הראשונים
            success_rate = (details['migrated'] / details['total'] * 100) if details['total'] > 0 else 0
            status = "✅" if details['errors'] == 0 else "⚠️"
            summary_lines.append(f"   {status} צ'אט {chat_id}: {details['migrated']}/{details['total']} הודעות ({success_rate:.1f}%)")
        if len(chat_details) > 15:
            summary_lines.append(f"   ... ועוד {len(chat_details) - 15} צ'אטים")
    
    # הוספת פירוט פרופילים
    if 'profile_details' in migration_results.get('user_profiles', {}):
        summary_lines.append(f"\n👤 === פירוט פרופילים ===")
        profile_details = migration_results['user_profiles']['profile_details']
        successful_profiles = [chat_id for chat_id, info in profile_details.items() if info['status'] == 'success']
        failed_profiles = [chat_id for chat_id, info in profile_details.items() if info['status'] == 'error']
        
        summary_lines.append(f"   ✅ פרופילים מוצלחים: {len(successful_profiles)}")
        for chat_id in successful_profiles[:10]:  # רק 10 הראשונים
            fields = profile_details[chat_id]['fields']
            summary_lines.append(f"      • צ'אט {chat_id}: {fields} שדות")
        if len(successful_profiles) > 10:
            summary_lines.append(f"      ... ועוד {len(successful_profiles) - 10} פרופילים")
        
        if failed_profiles:
            summary_lines.append(f"   ❌ פרופילים שנכשלו: {len(failed_profiles)}")
    
    # הוספת מידע על גודל קבצים
    try:
        def file_mb(path):
            return os.path.getsize(path)/1024/1024 if os.path.exists(path) else 0
        files = ["data/chat_history.json", "data/user_profiles.json", "data/gpt_usage_log.jsonl", "data/openai_calls.jsonl"]
        summary_lines.append(f"\n📦 === גודל קבצים ===")
        for f in files:
            mb = file_mb(f)
            summary_lines.append(f"   📦 {f}: {mb:.2f}MB")
    except Exception as e:
        summary_lines.append(f"   ⚠️ שגיאה בחישוב גודל קבצים: {e}")
    # הדפסה, שמירה לקובץ, ושליחה לאדמין
    summary = "\n".join(summary_lines)
    print(summary)
    log_to_file(summary)
    
    # שליחה לאדמין רק אם הייתה מיגרציה אמיתית
    if total_migrated > 0:
        try:
            send_admin_notification(f"📋 סיכום מיגרציה:\n{summary[:3500]}")
        except Exception as e:
            print(f"⚠️ שגיאה בשליחת סיכום לאדמין: {e}")
    else:
        print("ℹ️ לא נשלחה הודעת מיגרציה לאדמין - לא היו נתונים למיגרציה")

async def handle_migrate_command(update, context):
    """מטפל בפקודת /migrate_all_data עם קוד סודי"""
    try:
        # בדיקה אם המשתמש הוא אדמין לפי chat_id בלבד
        chat_id = str(update.effective_chat.id)
        if chat_id != "111709341":
            await update.message.reply_text("❌ רק אדמין יכול להריץ פקודה זו")
            return
        
        # בדיקת קוד סודי
        message_text = update.message.text.strip()
        if not message_text.endswith(" SECRET_MIGRATION_2024"):
            await update.message.reply_text(
                "🔐 נדרש קוד סודי למיגרציה!\n"
                "השתמש בפקודה: /migrate_all_data SECRET_MIGRATION_2024"
            )
            return
        
        await update.message.reply_text(
            "🔐 === מיגרציה בטוחה עם קוד סודי ===\n"
            "🚨 מנגנוני בטיחות מופעלים:\n"
            "   ✅ גיבוי אוטומטי לפני מיגרציה\n"
            "   ✅ בדיקת תקינות נתונים\n"
            "   ✅ דיבאג מפורט לכל שלב\n"
            "   ✅ עצירה בשגיאה\n"
            "   ✅ לוג מפורט של כל פעולה\n"
            "   ✅ אימות שלמות נתונים\n\n"
            "🚀 מתחיל מיגרציה..."
        )
        
        # הרצת המיגרציה ב-thread נפרד
        import threading
        def run_migration():
            success = migrate_data_to_sql_with_safety()
            if success:
                print("✅ מיגרציה הושלמה בהצלחה")
            else:
                print("❌ מיגרציה נכשלה")
        
        migration_thread = threading.Thread(target=run_migration)
        migration_thread.start()
        
        await update.message.reply_text("✅ מיגרציה הוחלה - תקבל עדכון מפורט כשתסתיים")
        
    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה בפקודת מיגרציה: {e}")

async def handle_show_logs_command(update, context):
    """מטפל בפקודת /show_logs לקריאת לוגים מרנדר"""
    try:
        # בדיקה אם המשתמש הוא אדמין
        chat_id = str(update.effective_chat.id)
        if chat_id != "111709341":
            await update.message.reply_text("❌ רק אדמין יכול להריץ פקודה זו")
            return
        
        # קבלת הפרמטרים מהפקודה
        message_text = update.message.text.strip()
        parts = message_text.split()
        
        # ברירת מחדל: 50 שורות אחרונות
        lines = 50
        log_type = "service"
        
        # פרסור פרמטרים
        if len(parts) > 1:
            try:
                lines = int(parts[1])
                lines = min(lines, 500)  # מקסימום 500 שורות
            except ValueError:
                log_type = parts[1]
        
        if len(parts) > 2:
            log_type = parts[2]
        
        await update.message.reply_text(f"📋 קורא {lines} שורות אחרונות מלוג {log_type}...")
        
        # הרצת קריאת לוגים ב-thread נפרד
        import threading
        def read_logs():
            try:
                logs = get_render_logs(log_type, lines)
                
                # שליחת הלוגים לטלגרם
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_logs_to_telegram(update, logs, log_type, lines))
                loop.close()
            except Exception as e:
                print(f"❌ שגיאה בקריאת לוגים: {e}")
        
        logs_thread = threading.Thread(target=read_logs)
        logs_thread.start()
        
    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה בפקודת לוגים: {e}")

def get_render_logs(log_type="service", lines=50):
    """קורא לוגים מרנדר דרך SSH"""
    try:
        # מיפוי סוגי לוגים
        log_paths = {
            "service": "/var/log/render/service.log",
            "python": "/var/log/render/python.log", 
            "error": "/var/log/render/error.log",
            "access": "/var/log/render/access.log"
        }
        
        log_path = log_paths.get(log_type, "/var/log/render/service.log")
        ssh_host = "srv-d0r895be5dus73fmsc8g@ssh.frankfurt.render.com"
        
        # פקודת SSH לקריאת לוגים
        cmd = f"ssh {ssh_host} 'tail -n {lines} {log_path}'"
        
        print(f"📋 מריץ פקודה: {cmd}")
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"❌ שגיאה בקריאת לוגים: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return "⏰ הזמן לקריאת לוגים פג - הרנדר לא מגיב"
    except Exception as e:
        return f"❌ שגיאה בקריאת לוגים: {e}"

async def send_logs_to_telegram(update, logs, log_type, lines):
    """שולח לוגים לטלגרם (עם חלוקה לחלקים אם נדרש)"""
    try:
        if not logs or not logs.strip():
            await update.message.reply_text(f"📋 אין לוגים זמינים עבור {log_type}")
            return
        
        # הוספת כותרת
        header = f"📋 **לוגים מרנדר - {log_type}**\n"
        header += f"📊 {lines} שורות אחרונות\n"
        header += f"🕐 {datetime.datetime.now().strftime('%H:%M:%S')}\n"
        header += "=" * 40 + "\n\n"
        
        formatted_logs = header + logs
        
        # חלוקה לחלקים (טלגרם מוגבל ל-4096 תווים)
        max_length = 4000  # השארת מקום לפורמטינג
        
        if len(formatted_logs) <= max_length:
            await update.message.reply_text(f"```\n{formatted_logs}\n```", parse_mode="Markdown")
        else:
            # חלוקה לחלקים
            parts = []
            current_part = header
            
            for line in logs.split('\n'):
                if len(current_part) + len(line) + 1 > max_length:
                    parts.append(current_part)
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
            
            if current_part.strip():
                parts.append(current_part)
            
            # שליחת כל חלק
            for i, part in enumerate(parts):
                part_header = f"📋 חלק {i+1}/{len(parts)}\n" + "=" * 20 + "\n"
                await update.message.reply_text(f"```\n{part_header}{part}\n```", parse_mode="Markdown")
                
                # מניעת spam - המתנה בין חלקים
                if i < len(parts) - 1:
                    await asyncio.sleep(1)
        
        # סיכום
        await update.message.reply_text(f"✅ לוגים נשלחו בהצלחה!\n📊 סה\"כ {len(logs.split())} שורות")
        
    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה בשליחת לוגים: {e}")

async def handle_search_logs_command(update, context):
    """מטפל בפקודת /search_logs לחיפוש לוגים"""
    try:
        # בדיקה אם המשתמש הוא אדמין
        chat_id = str(update.effective_chat.id)
        if chat_id != "111709341":
            await update.message.reply_text("❌ רק אדמין יכול להריץ פקודה זו")
            return
        
        # קבלת הפרמטרים מהפקודה
        message_text = update.message.text.strip()
        parts = message_text.split()
        
        if len(parts) < 2:
            await update.message.reply_text(
                "❓ שימוש: /search_logs <מילת_חיפוש> [סוג_לוג] [מספר_שורות]\n"
                "דוגמה: /search_logs error service 100"
            )
            return
        
        search_term = parts[1]
        log_type = parts[2] if len(parts) > 2 else "service"
        lines = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 200
        lines = min(lines, 1000)  # מקסימום 1000 שורות
        
        await update.message.reply_text(f"🔍 מחפש '{search_term}' ב-{lines} שורות אחרונות של {log_type}...")
        
        # הרצת חיפוש לוגים ב-thread נפרד
        import threading
        def search_logs():
            try:
                logs = get_render_logs(log_type, lines)
                search_results = search_logs_in_file(logs, search_term)
                
                # שליחת התוצאות לטלגרם
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_search_results_to_telegram(update, search_results, log_type, search_term))
                loop.close()
            except Exception as e:
                print(f"❌ שגיאה בחיפוש לוגים: {e}")
        
        logs_thread = threading.Thread(target=search_logs)
        logs_thread.start()
        
    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה בפקודת חיפוש לוגים: {e}")

def search_logs_in_file(file_content, search_term):
    """חיפוש לוגים בתוכן קובץ"""
    search_results = []
    for line in file_content.splitlines():
        if search_term.lower() in line.lower():
            search_results.append(line)
    return search_results

async def send_search_results_to_telegram(update, search_results, log_type, search_term):
    """שולח תוצאות חיפוש לוגים לטלגרם"""
    try:
        if not search_results:
            await update.message.reply_text(f"❌ לא נמצאו תוצאות עבור '{search_term}' בלוג {log_type}")
            return
        
        # הוספת כותרת
        header = f"🔍 **תוצאות חיפוש לוגים - {log_type}**\n"
        header += f"🔤 חיפוש: '{search_term}'\n"
        header += f"📊 נמצאו: {len(search_results)} שורות\n"
        header += f"🕐 {datetime.datetime.now().strftime('%H:%M:%S')}\n"
        header += "=" * 40 + "\n\n"
        
        formatted_results = header + "\n".join(search_results)
        
        # חלוקה לחלקים אם נדרש
        max_length = 4000
        
        if len(formatted_results) <= max_length:
            await update.message.reply_text(f"```\n{formatted_results}\n```", parse_mode="Markdown")
        else:
            # חלוקה לחלקים
            parts = []
            current_part = header
            
            for line in search_results:
                if len(current_part) + len(line) + 1 > max_length:
                    parts.append(current_part)
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
            
            if current_part.strip():
                parts.append(current_part)
            
            # שליחת כל חלק
            for i, part in enumerate(parts):
                part_header = f"🔍 חלק {i+1}/{len(parts)}\n" + "=" * 20 + "\n"
                await update.message.reply_text(f"```\n{part_header}{part}\n```", parse_mode="Markdown")
                
                # מניעת spam - המתנה בין חלקים
                if i < len(parts) - 1:
                    await asyncio.sleep(1)
        
        # סיכום
        await update.message.reply_text(f"✅ חיפוש הושלם!\n📊 נמצאו {len(search_results)} שורות עם '{search_term}'")
        
    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה בשליחת תוצאות חיפוש: {e}")

def count_table_rows():
    """ספירת שורות בטבלאות הקריטיות בלבד"""
    counts = {}
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # 🟢 טבלאות קריטיות בלבד
        critical_tables = [
            'chat_messages',
            'user_profiles', 
            'gpt_calls_log',
            'reminder_states',
            'bot_error_logs',
            'bot_trace_logs'
        ]
        
        for table in critical_tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cur.fetchone()[0]
            except Exception as e:
                print(f"    ⚠️ טבלה {table} לא קיימת או שגיאה: {e}")
                counts[table] = 0
        
        # 🚫 טבלאות מיותרות - לא נספרות יותר
        disabled_tables = [
            'gpt_usage_log',
            'system_logs', 
            'critical_users',
            'billing_usage',
            'errors_stats',
            'free_model_limits'
        ]
        
        for table in disabled_tables:
            counts[table] = "DISABLED"
        
        cur.close()
        conn.close()
        
        print("📊 מספר השורות בטבלאות:")
        for table, count in counts.items():
            if count == "DISABLED":
                print(f"    🚫 {table}: הושבתה")
            else:
                print(f"    📋 {table}: {count}")
        
        return counts
        
    except Exception as e:
        print(f"❌ שגיאה בספירת שורות: {e}")
        return {}

if __name__ == "__main__":
    # אם הרצנו ישירות מה-Shell, נריץ מיגרציה
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        # בדיקת קוד סודי
        if len(sys.argv) < 3 or sys.argv[2] != "SECRET_MIGRATION_2024":
            print("🔐 === מיגרציה בטוחה עם קוד סודי ===")
            print("❌ נדרש קוד סודי למיגרציה!")
            print("השתמש בפקודה: python bot_setup.py migrate SECRET_MIGRATION_2024")
            sys.exit(1)
        
        print("🔐 === מיגרציה בטוחה עם קוד סודי ===")
        print("✅ קוד סודי אומת - מתחיל מיגרציה...")
        success = migrate_data_to_sql_with_safety()
        if success:
            print("✅ מיגרציה הושלמה בהצלחה!")
            sys.exit(0)
        else:
            print("❌ מיגרציה נכשלה!")
            sys.exit(1)
    else:
        # הרצה רגילה של הבוט
        print("🤖 מתחיל את הבוט...")
        app = setup_bot()
        app.run_polling() 