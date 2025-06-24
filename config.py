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

================================================================================

config.py
---------
קובץ זה מרכז את כל ההגדרות (config) של הבוט: טוקנים, מפתחות, קבצים, Sheets, ועוד.
הרציונל: כל קונפיגורציה במקום אחד, כולל טעינה, בדיקות, ויצירת קליינטים.
"""
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from litellm import completion
from fields_dict import FIELDS_DICT
from prompts import SYSTEM_PROMPT  # ייבוא ישיר של הפרומט הראשי
import time
import logging


# טעינת קונפיגורציה
def load_config():
    """
    טוען את קובץ הקונפיגורציה (config.json) מהנתיב המתאים.
    פלט: dict
    """
    env_path = os.getenv("CONFIG_PATH")
    if env_path and os.path.exists(env_path):
        path = env_path
    else:
        # שימוש במשתנה הגלובלי PROJECT_ROOT במקום חישוב מחדש
        local_path = os.path.join(PROJECT_ROOT, "etc", "secrets", "config.json")
        abs_path = "/etc/secrets/config.json"
        if os.path.exists(local_path):
            path = local_path
        elif os.path.exists(abs_path):
            path = abs_path
        else:
            raise FileNotFoundError("config.json לא נמצא בנתיבים הידועים")
    print("DEBUG: using config path:", path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# הגדרת נתיב לוג אחיד מתוך תיקיית הפרויקט
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# הגדרות גלובליות
config = load_config()

# טוקנים וזיהויים
TELEGRAM_BOT_TOKEN = config["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = config["OPENAI_API_KEY"]
OPENAI_ADMIN_KEY = os.getenv("OPENAI_ADMIN_KEY", config.get("OPENAI_ADMIN_KEY", OPENAI_API_KEY))
print("מפתח Admin בשימוש (ה־OPENAI_ADMIN_KEY):", OPENAI_ADMIN_KEY[:13] + "...")
GOOGLE_SHEET_ID = config["GOOGLE_SHEET_ID"]

# הגדרות התראות שגיאות (לבוט הניהולי החדש)
ADMIN_BOT_TELEGRAM_TOKEN = config.get("ADMIN_BOT_TELEGRAM_TOKEN", TELEGRAM_BOT_TOKEN)
ADMIN_NOTIFICATION_CHAT_ID = "111709341"  # ה־chat_id שלך בבוט admin

# הגדרת LiteLLM
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# הגדרת Google Sheets
def setup_google_sheets():
    """
    מגדיר את החיבור ל-Google Sheets ומחזיר שלושה גיליונות עיקריים.
    פלט: sheet_users, sheet_log, sheet_states
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(config["SERVICE_ACCOUNT_DICT"], scope)
    gs_client = gspread.authorize(creds)

    max_retries = 3
    delay = 5
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[DEBUG] Attempt {attempt}: Opening Google Sheet with ID: {GOOGLE_SHEET_ID}")
            sheet = gs_client.open_by_key(GOOGLE_SHEET_ID)
            print(f"[DEBUG] Attempt {attempt}: Accessing worksheet: {config['SHEET_USER_TAB']}")
            sheet_users = sheet.worksheet(config["SHEET_USER_TAB"])
            print(f"[DEBUG] Attempt {attempt}: Accessing worksheet: {config['SHEET_LOG_TAB']}")
            sheet_log = sheet.worksheet(config["SHEET_LOG_TAB"])
            print(f"[DEBUG] Attempt {attempt}: Accessing worksheet: {config['SHEET_STATES_TAB']}")
            sheet_states = sheet.worksheet(config["SHEET_STATES_TAB"])
            print(f"[DEBUG] Google Sheets loaded successfully!")
            return sheet_users, sheet_log, sheet_states
        except Exception as e:
            print(f"[ERROR] Google Sheets access failed on attempt {attempt}: {e}")
            last_exception = e
            if attempt < max_retries:
                print(f"[DEBUG] Retrying in {delay} seconds...")
                time.sleep(delay)
    print(f"[FATAL] All attempts to access Google Sheets failed.")
    raise last_exception


# ⚠️ יש להשתמש אך ורק במפתחות מתוך FIELDS_DICT! אין להכניס שמות שדה קשיחים חדשים כאן או בקוד אחר.
# שדות פרופיל משתמש
PROFILE_FIELDS = [
    key for key in [
        "age", "closet_status", "relationship_type", "self_religiosity_level", "occupation_or_role", "attracted_to"
    ] if key in FIELDS_DICT
]
SUMMARY_FIELD = "summary" if "summary" in FIELDS_DICT else list(FIELDS_DICT.keys())[-1]

# הגדרות לוגים
BOT_TRACE_LOG_FILENAME = "bot_trace_log.jsonl"
GPT_USAGE_LOG_FILENAME = "gpt_usage_log.jsonl"
CHAT_HISTORY_FILENAME = "chat_history.json"
BOT_ERRORS_FILENAME = "bot_errors.jsonl"
CRITICAL_ERRORS_FILENAME = "critical_errors.jsonl"
LOG_LIMIT = 100

# הגדרת נתיב לוג אחיד מתוך תיקיית הפרויקט
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# נתיבי קבצים עיקריים
gpt_log_path = os.path.join(DATA_DIR, GPT_USAGE_LOG_FILENAME)
BOT_TRACE_LOG_PATH = os.path.join(DATA_DIR, BOT_TRACE_LOG_FILENAME)
CHAT_HISTORY_PATH = os.path.join(DATA_DIR, CHAT_HISTORY_FILENAME)
BOT_ERRORS_PATH = os.path.join(DATA_DIR, BOT_ERRORS_FILENAME)
CRITICAL_ERRORS_PATH = os.path.join(DATA_DIR, CRITICAL_ERRORS_FILENAME)

def check_config_sanity():
    """
    בודק שכל משתני הקונפיגורציה הקריטיים קיימים.
    פלט: אין (מדפיס/מתריע)
    """
    missing = []
    sensitive_keys = [
        "TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY", "OPENAI_ADMIN_KEY", "GOOGLE_SHEET_ID", "ADMIN_BOT_TELEGRAM_TOKEN"
    ]
    for key in sensitive_keys:
        val = globals().get(key, None)
        if not val or (isinstance(val, str) and not val.strip()):
            missing.append(key)
    if missing:
        print(f"❌ [CONFIG] חסרים משתני קונפיגורציה קריטיים: {missing}")
    else:
        print("✅ [CONFIG] כל משתני הקונפיגורציה הקריטיים קיימים.")

def get_config_snapshot():
    """
    מחזיר snapshot של קונפיגורציה ללא ערכים רגישים.
    פלט: dict
    """
    # מחזיר snapshot של קונפיגורציה ללא ערכים רגישים
    return {
        "GOOGLE_SHEET_ID": "***",
        "DATA_DIR": DATA_DIR,
        "PROJECT_ROOT": PROJECT_ROOT,
        "LOG_FILE_PATH": BOT_TRACE_LOG_FILENAME,
        "gpt_log_path": gpt_log_path,
        "BOT_TRACE_LOG_PATH": BOT_TRACE_LOG_PATH,
        "CHAT_HISTORY_PATH": CHAT_HISTORY_PATH,
        "BOT_ERRORS_PATH": BOT_ERRORS_PATH,
        "CRITICAL_ERRORS_PATH": CRITICAL_ERRORS_PATH
    }

# ================================
# 🎯 הגדרת מודלים ופרמטרים מרכזית
# ================================
# כל שינוי כאן משפיע על כל מנועי ה-GPT - Single Source of Truth!

GPT_MODELS = {
    "gpt_a": "gpt-4o",           # המנוע הראשי - תשובות איכותיות
    "gpt_b": "gpt-4.1-nano",     # סיכום תשובות - מהיר וזול
    "gpt_c": "gpt-4o-mini",      # חילוץ פרופיל - מהיר יחסית
    "gpt_d": "gpt-4o-mini",      # מיזוג פרופיל - מהיר יחסית  
    "gpt_e": "gpt-4o",           # עדכון פרופיל מתקדם - איכותי
}

GPT_PARAMS = {
    "gpt_a": {
        "temperature": 1,
        "max_tokens": None,  # ללא הגבלה
    },
    "gpt_b": {
        "temperature": 0.5,
        "max_tokens": None,  # ללא הגבלה
    },
    "gpt_c": {
        "temperature": 0.3,
        "max_tokens": 500,
    },
    "gpt_d": {
        "temperature": 0.1,
        "max_tokens": 300,
    },
    "gpt_e": {
        "temperature": 0.8,
        "max_tokens": 2000,
    },
}

# קבועים מספריים - Single Source of Truth
MAX_LOG_LINES_TO_KEEP = 500  # למגבלת לוגים ישנים
MAX_OLD_LOG_LINES = 1000     # לניקוי לוגים ישנים  
MAX_CHAT_HISTORY_MESSAGES = 30000  # מגבלת היסטוריית שיחה
MAX_TRACEBACK_LENGTH = 500   # אורך מקסימלי של traceback בהודעות שגיאה
PRODUCTION_PORT = 8000       # פורט לסביבת ייצור
DEVELOPMENT_PORT = 10000     # פורט לסביבת פיתוח
