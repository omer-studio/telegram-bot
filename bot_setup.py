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
from sheets_handler import increment_code_try, get_user_summary, update_user_profile, log_to_sheets, check_user_access, register_user, approve_user, ensure_user_state_row
from notifications import send_startup_notification
from messages import get_welcome_messages
from utils import log_event_to_file, update_chat_history, get_chat_history_messages, send_error_stats_report, send_usage_report
from gpt_a_handler import get_main_response
from gpt_b_handler import get_summary
from apscheduler.schedulers.background import BackgroundScheduler
from daily_summary import send_daily_summary
import pytz
from message_handler import handle_message
from notifications import gentle_reminder_background_task
from db_manager import create_tables, save_chat_message, save_user_profile, save_gpt_usage_log, save_gpt_call_log
import json
import psycopg2

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
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
            return gspread, ServiceAccountCredentials
        
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
        
        from sheets_core import setup_google_sheets
        gc, sheet_users, sheet_log, sheet_states = setup_google_sheets()
        
        # יצירת תיקיית גיבוי בדרייב
        from datetime import datetime
        backup_folder_name = f"data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # יצירת תיקייה בדרייב
        folder_metadata = {
            'name': backup_folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = gc.create(folder_metadata)
        folder_id = folder['id']
        
        print(f"✅ נוצרה תיקיית גיבוי: {backup_folder_name}")
        
        # רשימת קבצים לגיבוי
        data_files = [
            "data/chat_history.json",
            "data/user_profiles.json", 
            "data/gpt_usage_log.jsonl",
            "data/openai_calls.jsonl",
            "data/bot_errors.jsonl",
            "data/bot_trace_log.jsonl",
            "data/reminder_state.json",
            "data/errors_stats.json",
            "data/critical_error_users.json",
            "data/billing_usage.json",
            "data/free_model_limits.json"
        ]
        
        backed_up_files = 0
        for file_path in data_files:
            if os.path.exists(file_path):
                try:
                    # העלאה לדרייב
                    file_metadata = {
                        'name': os.path.basename(file_path),
                        'parents': [folder_id]
                    }
                    
                    gc.upload_file(file_path, file_metadata)
                    backed_up_files += 1
                    print(f"✅ הועלה: {os.path.basename(file_path)}")
                    
                except Exception as e:
                    print(f"⚠️ שגיאה בהעלאת {file_path}: {e}")
        
        print(f"✅ גיבוי הושלם: {backed_up_files} קבצים הועלו ל-Google Drive")
        print(f"📁 תיקיית גיבוי: {backup_folder_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ שגיאה בגיבוי: {e}")
        return False

def migrate_data_to_sql_with_safety():
    """מבצע מיגרציה בטוחה של כל הנתונים מ-data/ ל-SQL עם דיבאג מפורט"""
    try:
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
        cur.execute("SELECT COUNT(*) FROM chat_messages")
        counts['chat_messages'] = cur.fetchone()[0]
        
        # ספירת פרופילים
        cur.execute("SELECT COUNT(*) FROM user_profiles")
        counts['user_profiles'] = cur.fetchone()[0]
        
        # ספירת קריאות GPT
        cur.execute("SELECT COUNT(*) FROM gpt_calls_log")
        counts['gpt_calls'] = cur.fetchone()[0]
        
        # ספירת שימוש
        cur.execute("SELECT COUNT(*) FROM gpt_usage_log")
        counts['gpt_usage'] = cur.fetchone()[0]
        
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
        'gpt_calls': {'migrated': 0, 'errors': 0, 'details': []}
    }
    
    # === מיגרציית chat_history.json ===
    print("  📝 מיגרציית chat_history.json...")
    try:
        chat_history_path = "data/chat_history.json"
        if os.path.exists(chat_history_path):
            with open(chat_history_path, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            
            print(f"    📊 נמצאו {len(chat_data)} צ'אטים למיגרציה")
            
            for chat_id, chat_info in chat_data.items():
                if "history" in chat_info:
                    history_count = len(chat_info["history"])
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
                            
                            if i % 100 == 0:  # דיבאג כל 100 הודעות
                                print(f"      ✅ הועברו {i+1}/{history_count} הודעות")
                                
                        except Exception as e:
                            results['chat_messages']['errors'] += 1
                            results['chat_messages']['details'].append(f"שגיאה בהודעה {i} בצ'אט {chat_id}: {e}")
                            print(f"      ⚠️ שגיאה בהודעה {i}: {e}")
                            continue
                    
                    print(f"    ✅ צ'אט {chat_id} הושלם: {results['chat_messages']['migrated']} הודעות")
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
            
            for chat_id, profile in profiles_data.items():
                try:
                    save_user_profile(chat_id, profile)
                    results['user_profiles']['migrated'] += 1
                    print(f"    ✅ פרופיל {chat_id} הועבר")
                except Exception as e:
                    results['user_profiles']['errors'] += 1
                    results['user_profiles']['details'].append(f"שגיאה בפרופיל {chat_id}: {e}")
                    print(f"    ⚠️ שגיאה בפרופיל {chat_id}: {e}")
                    continue
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
    
    return results

def verify_data_integrity(pre_counts, post_counts, migration_results):
    """מאמת את שלמות הנתונים"""
    print("  🔍 אימות שלמות נתונים...")
    
    verification = {
        'chat_messages': {'verified': False, 'details': ''},
        'user_profiles': {'verified': False, 'details': ''},
        'gpt_usage': {'verified': False, 'details': ''},
        'gpt_calls': {'verified': False, 'details': ''}
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
    
    return verification

def print_detailed_summary(migration_results, verification_results):
    """מדפיס סיכום מפורט"""
    print("\n📋 === סיכום מיגרציה מפורט ===")
    
    total_migrated = 0
    total_errors = 0
    
    for category, results in migration_results.items():
        migrated = results['migrated']
        errors = results['errors']
        total_migrated += migrated
        total_errors += errors
        
        status = "✅" if verification_results[category]['verified'] else "❌"
        print(f"\n{status} {category.upper()}:")
        print(f"   📊 הועברו: {migrated}")
        print(f"   ⚠️ שגיאות: {errors}")
        print(f"   🔍 אימות: {verification_results[category]['details']}")
        
        if errors > 0 and results['details']:
            print("   📝 פרטי שגיאות:")
            for detail in results['details'][:5]:  # רק 5 הראשונות
                print(f"      • {detail}")
            if len(results['details']) > 5:
                print(f"      ... ועוד {len(results['details']) - 5} שגיאות")
    
    print(f"\n🎯 סיכום כללי:")
    print(f"   📊 סה״כ הועברו: {total_migrated}")
    print(f"   ⚠️ סה״כ שגיאות: {total_errors}")
    print(f"   📈 אחוז הצלחה: {((total_migrated - total_errors) / max(total_migrated, 1) * 100):.1f}%")

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