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
from gpt_b_handler import get_summary
from apscheduler.schedulers.background import BackgroundScheduler
from daily_summary import send_daily_summary
import pytz
from message_handler import handle_message
from notifications import gentle_reminder_background_task

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
    print(f"⏱️  בודק/יוצר קובץ {file_name}...")
    
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
    print(f"✅ קובץ {file_name} ({status}) - {elapsed_time:.3f} שניות")

@time_operation("בדיקת קיום קבצים קריטיים - סה״כ")
def setup_critical_files():
    """יוצר קבצים קריטיים הנדרשים לפעולת הבוט"""
    critical_files = [
        "data/gpt_usage_log.jsonl",
        "data/chat_history.json", 
        "data/bot_errors.jsonl"
    ]
    
    print(f"🔍 בודק {len(critical_files)} קבצים קריטיים...")
    for file_path in critical_files:
        setup_single_critical_file(file_path)

@time_operation("בדיקת והכנת סביבה וירטואלית")
def setup_virtual_environment():
    """בודק ויוצר venv במידת הצורך (Windows בלבד)"""
    # 🔧 תיקון: בסביבת production לא צריך venv
    if os.getenv("RENDER"):  # אם רץ ברנדר
        print("ℹ️  רץ בסביבת production - מדלג על יצירת venv")
        return
        
    if os.name == 'nt':
        venv_path = os.path.join(os.getcwd(), 'venv')
        if not os.path.exists(venv_path):
            print('🔧 יוצר venv חדש...')
            subprocess.run([sys.executable, '-m', 'venv', 'venv'])
        else:
            print('✅ venv קיים')

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
    print("📦 בודק התקנת תלויות...")
    
    # 🔧 תיקון חשוב: מניעת התקנות בsandbox ובproduction
    if os.getenv("RENDER"):
        print("ℹ️  רץ בסביבת production (רנדר) - מדלג על התקנת תלויות")
        print("    (התלויות כבר אמורות להיות מותקנות מה-requirements.txt)")
        return
    
    # בדיקה נוספת: אם זה sandbox mode
    if any(arg in sys.argv[0].lower() for arg in ["sandbox", "uvicorn"]):
        print("ℹ️  רץ במצב sandbox - מדלג על התקנת תלויות")
        return
    
    # רק בסביבת פיתוח מקומי (Windows בדרך כלל)
    print("🔧 סביבת פיתוח מקומי - בודק תלויות...")
    
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

@time_operation("הגדרת תזמון דוחות אוטומטיים - סה״כ")
def setup_admin_reports(): # מתזמן דוחות אוטומטיים לאדמין (שגיאות ו-usage) לשעה 8:00 בבוקר
    """
    מתזמן דוחות אוטומטיים לאדמין (שגיאות ו-usage) לשעה 8:00 בבוקר.
    פלט: אין (מתזמן דוחות)
    """
    # הגדרת אזור זמן
    def setup_timezone():
        return pytz.timezone("Asia/Jerusalem")
    
    tz = time_scheduler_step("הגדרת אזור זמן ישראל", setup_timezone)
    
    # יצירת מתזמן
    def create_scheduler():
        return BackgroundScheduler(timezone=tz)
    
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
    """מוסיף handlers לטיפול בהודעות טקסט (הודעות קוליות זמנית מבוטלות)"""
    start_time = time.time()
    print(f"⏱️  מוסיף handler להודעות טקסט...")
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    elapsed_time = time.time() - start_time
    execution_times["הוספת message handler"] = elapsed_time
    print(f"✅ Message handler נוסף תוך {elapsed_time:.3f} שניות")

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
    
    # הדפסת סיכום זמני הביצוע
    print_execution_summary()
    
    print("🎉 ההתקנה הושלמה בהצלחה!")
    
    _setup_completed = True
    return app 