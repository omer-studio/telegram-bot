"""
קובץ הגדרות - כל הקונפיגורציה במקום אחד
"""
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI


# טעינת קונפיגורציה
def load_config():
    local_path = os.path.join("etc", "secrets", "config.json")
    print("DEBUG: cwd =", os.getcwd())
    print("DEBUG: local_path exists?", os.path.exists(local_path))
    abs_path = "/etc/secrets/config.json"
    path = local_path if os.path.exists(local_path) else abs_path
    print("DEBUG: using path", path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_system_prompt():
    """טוען את ה-system prompt"""
    with open("system_prompt.txt", encoding="utf-8") as f:
        return f.read()

# הגדרות גלובליות
config = load_config()
SYSTEM_PROMPT = load_system_prompt()

# טוקנים וזיהויים
TELEGRAM_BOT_TOKEN = config["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = config["OPENAI_API_KEY"]
OPENAI_ADMIN_KEY = os.getenv("OPENAI_ADMIN_KEY", config.get("OPENAI_ADMIN_KEY", OPENAI_API_KEY))
print("מפתח Admin בשימוש (ה־OPENAI_ADMIN_KEY):", OPENAI_ADMIN_KEY[:13] + "...")
GOOGLE_SHEET_ID = config["GOOGLE_SHEET_ID"]

# הגדרות התראות שגיאות (לבוט הניהולי החדש)
ADMIN_BOT_TELEGRAM_TOKEN = config.get("ADMIN_BOT_TELEGRAM_TOKEN", TELEGRAM_BOT_TOKEN)
ADMIN_NOTIFICATION_CHAT_ID = "111709341"  # ה־chat_id שלך בבוט admin

# יצירת קליינטים
client = OpenAI(api_key=OPENAI_API_KEY)

# הגדרת Google Sheets
def setup_google_sheets():
    """מגדיר את החיבור ל-Google Sheets"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(config["SERVICE_ACCOUNT_DICT"], scope)
    gs_client = gspread.authorize(creds)

    sheet_users = gs_client.open_by_key(GOOGLE_SHEET_ID).worksheet("גיליון1")
    sheet_log = gs_client.open_by_key(GOOGLE_SHEET_ID).worksheet("2")
    sheet_states = gs_client.open_by_key(GOOGLE_SHEET_ID).worksheet("user_states")

    return sheet_users, sheet_log, sheet_states


# שדות פרופיל משתמש
PROFILE_FIELDS = ["age", "closet_status", "relationship_type", "religious_context", "occupation_or_role", "attracted_to"]
SUMMARY_FIELD = "summary"

# הגדרות לוגים
LOG_FILE_PATH = "bot_trace_log.jsonl"
LOG_LIMIT = 100

# הגדרת נתיב לוג אחיד מתוך תיקיית הפרויקט
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# נתיבי קבצים עיקריים
GPT_LOG_PATH = os.path.join(DATA_DIR, "gpt_usage_log.jsonl")
BOT_TRACE_LOG_PATH = os.path.join(DATA_DIR, "bot_trace_log.jsonl")
CHAT_HISTORY_PATH = os.path.join(DATA_DIR, "chat_history.json")
BOT_ERRORS_PATH = os.path.join(DATA_DIR, "bot_errors.jsonl")
CRITICAL_ERRORS_PATH = os.path.join(DATA_DIR, "critical_errors.jsonl")
