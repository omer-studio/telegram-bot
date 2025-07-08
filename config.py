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
import time
import logging
from typing import Optional

# Helper function to handle encoding issues in Windows/CI environments
def safe_print(message, fallback_prefix="[CONFIG]"):
    """
    Print message safely, handling encoding issues in Windows/CI environments.
    If encoding fails, prints a simplified ASCII version.
    """
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback for Windows with cp1255 or other problematic encodings
        # Remove emojis and problematic Unicode characters
        import re
        clean_message = re.sub(r'[^\x00-\x7F]+', '', str(message))
        print(f"{fallback_prefix} {clean_message}")
    except Exception:
        # Ultimate fallback
        print(f"{fallback_prefix} <message with encoding issues>")

# זיהוי סביבת CI/CD לפני imports חיצוניים
IS_CI_ENVIRONMENT = any([
    os.getenv("GITHUB_ACTIONS"),
    os.getenv("CI"),
    os.getenv("CONTINUOUS_INTEGRATION"),
    os.getenv("RUNNER_OS")
])

# imports תלויי dependencies - רק בסביבת ייצור/פיתוח
if not IS_CI_ENVIRONMENT:
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        from lazy_litellm import completion
        try:
            from fields_dict import FIELDS_DICT
        except ImportError:
            FIELDS_DICT = {"dummy": "dummy"}
        # ייבוא ישיר של הפרומט הראשי - רק בסביבת ייצור
        try:
            from prompts import SYSTEM_PROMPT
        except ImportError:
            SYSTEM_PROMPT = "dummy system prompt"
    except ImportError as e:
        print(f"⚠️ Warning: Failed to import dependency: {e}")
        # יצירת dummy modules כדי שהקוד לא יקרוס
        class DummyModule:
            def __getattr__(self, name):
                return lambda *args, **kwargs: None
        
        gspread = DummyModule()
        ServiceAccountCredentials = DummyModule()
        completion = DummyModule()
        try:
            from fields_dict import FIELDS_DICT
        except ImportError:
            FIELDS_DICT = {"dummy": "dummy"}
        try:
            from prompts import SYSTEM_PROMPT
        except ImportError:
            SYSTEM_PROMPT = "dummy system prompt"
else:
    # סביבת CI - dummy imports
    print("[CI] CI environment detected - using dummy modules")
    class DummyModule:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    
    gspread = DummyModule()
    ServiceAccountCredentials = DummyModule()
    completion = DummyModule()
    import sys as _sys, types as _types
    _lazy = _types.ModuleType("lazy_litellm")
    _lazy.completion = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    _lazy.embedding = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    _sys.modules.setdefault("lazy_litellm", _lazy)
    # הגדרות dummy לסביבת CI
    try:
        from fields_dict import FIELDS_DICT
    except ImportError:
        FIELDS_DICT = {"dummy": "dummy"}
    try:
        from prompts import SYSTEM_PROMPT
    except ImportError:
        SYSTEM_PROMPT = "dummy system prompt"


# טעינת קונפיגורציה
def load_config():
    """
    טוען את קובץ הקונפיגורציה (config.json) מהנתיב המתאים.
    בסביבת CI/CD מחזיר הגדרות dummy.
    פלט: dict
    """
    # זיהוי סביבת CI/CD
    is_ci_environment = any([
        os.getenv("GITHUB_ACTIONS"),
        os.getenv("CI"),
        os.getenv("CONTINUOUS_INTEGRATION"),
        os.getenv("RUNNER_OS")  # GitHub Actions specific
    ])
    
    # 🌐 1) Highest priority – explicit JSON passed via CONFIG_GITHUB_JSON (secret)
    _env_json = os.getenv("CONFIG_GITHUB_JSON", "").strip()
    if _env_json:
        try:
            return json.loads(_env_json)
        except Exception as env_err:
            print(f"⚠️ CONFIG_GITHUB_JSON malformed: {env_err}. Falling back to defaults")

    # 🌐 2) CI environment without explicit JSON – use built-in dummy config
    if is_ci_environment:
        print("DEBUG: CI/CD environment detected - using dummy config")
        return {
            "TELEGRAM_BOT_TOKEN": "dummy_bot_token",
            "OPENAI_API_KEY": "dummy_openai_key", 
            "OPENAI_ADMIN_KEY": "dummy_admin_key",
            "GOOGLE_SHEET_ID": "dummy_sheet_id",
            "ADMIN_BOT_TELEGRAM_TOKEN": "dummy_admin_bot_token",
            "GEMINI_API_KEY": "dummy_gemini_key",
            "SERVICE_ACCOUNT_DICT": {
                "type": "service_account",
                "project_id": "dummy-project",
                "private_key_id": "dummy",
                "private_key": "-----BEGIN PRIVATE KEY-----\ndummy\n-----END PRIVATE KEY-----\n",
                "client_email": "dummy@dummy.iam.gserviceaccount.com",
                "client_id": "dummy",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            },
            "SHEET_USER_TAB": "user_profiles",
            "SHEET_LOG_TAB": "log", 
            "SHEET_STATES_TAB": "user_states"
        }
    
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

# ⚠️ תיקון קריטי: יצירת תיקיית data לפני הגדרת הלוגים!
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# הגדרות גלובליות
config = load_config()

# 🎛️ הגדרות בקרת לוגים
# רמות לוגים זמינות: DEBUG, INFO, WARNING, ERROR, CRITICAL

# ⚙️ הגדרות ברירת מחדל (ניתן לשנות כאן)
DEFAULT_LOG_LEVEL = "INFO"  # רמת לוגים כללית
ENABLE_DEBUG_PRINTS = False  # DEBUG prints כלליים (False = רזה יותר)
ENABLE_GPT_COST_DEBUG = True  # דיבאג עלויות GPT מפורט - חשוב לתפעול!
# 🗑️ עברנו למסד נתונים - Google Sheets לא נדרש יותר
ENABLE_SHEETS_DEBUG = False  # תמיד False - עברנו למסד נתונים
ENABLE_PERFORMANCE_DEBUG = True  # דיבאג ביצועים מפורט - חשוב לזמני תגובה!
ENABLE_MESSAGE_DEBUG = True  # הודעות בסיסיות (מומלץ True)
ENABLE_DATA_EXTRACTION_DEBUG = True  # מידע על חילוץ נתונים מ-GPT C,D,E

# 🔧 אפשרות לעקוף עם משתני סביבה (אופציונלי)
# דוגמאות שימוש:
# Windows: $env:ENABLE_GPT_COST_DEBUG="false"; python main.py
# Linux/Mac: ENABLE_GPT_COST_DEBUG=false python main.py
# או הגדר במשתני הסביבה של המערכת
import os
DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)
ENABLE_DEBUG_PRINTS = os.getenv("ENABLE_DEBUG_PRINTS", str(ENABLE_DEBUG_PRINTS)).lower() == "true"
ENABLE_GPT_COST_DEBUG = os.getenv("ENABLE_GPT_COST_DEBUG", str(ENABLE_GPT_COST_DEBUG)).lower() == "true"
ENABLE_SHEETS_DEBUG = os.getenv("ENABLE_SHEETS_DEBUG", str(ENABLE_SHEETS_DEBUG)).lower() == "true"
ENABLE_PERFORMANCE_DEBUG = os.getenv("ENABLE_PERFORMANCE_DEBUG", str(ENABLE_PERFORMANCE_DEBUG)).lower() == "true"
ENABLE_MESSAGE_DEBUG = os.getenv("ENABLE_MESSAGE_DEBUG", str(ENABLE_MESSAGE_DEBUG)).lower() == "true"
ENABLE_DATA_EXTRACTION_DEBUG = os.getenv("ENABLE_DATA_EXTRACTION_DEBUG", str(ENABLE_DATA_EXTRACTION_DEBUG)).lower() == "true"

# הגדרת רמת לוגים גלובלית
logging.basicConfig(
    level=getattr(logging, DEFAULT_LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # פלט למסוף
        logging.FileHandler(os.path.join(PROJECT_ROOT, 'data', 'bot.log'), encoding='utf-8')  # פלט לקובץ
    ]
)

# פונקציות עזר לבקרת לוגים
def should_log_debug_prints():
    """בודק האם להדפיס DEBUG prints בהתאם להגדרות"""
    return ENABLE_DEBUG_PRINTS

def should_log_gpt_cost_debug():
    """בודק האם להדפיס דיבאג עלויות GPT"""
    return ENABLE_GPT_COST_DEBUG

def should_log_sheets_debug():
    """בודק האם להדפיס דיבאג גיליונות"""
    return ENABLE_SHEETS_DEBUG

def should_log_performance_debug():
    """בודק האם להדפיס דיבאג ביצועים"""
    return ENABLE_PERFORMANCE_DEBUG

def should_log_message_debug():
    """בודק האם להדפיס הודעות בסיסיות"""
    return ENABLE_MESSAGE_DEBUG

def should_log_data_extraction_debug():
    """בודק האם להדפיס מידע על חילוץ נתונים מ-GPT C,D,E"""
    return ENABLE_DATA_EXTRACTION_DEBUG

# Helper to mask sensitive strings (defined early to avoid NameError)
def _mask_sensitive(value: Optional[str], visible_chars: int = 4) -> str:
    if not value:
        return "[empty]"
    value = str(value)
    if len(value) <= visible_chars:
        return value
    return value[:visible_chars] + "..."

# 🚀 טוקנים וזיהויים
TELEGRAM_BOT_TOKEN = config["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = config["OPENAI_API_KEY"]
OPENAI_ADMIN_KEY = os.getenv("OPENAI_ADMIN_KEY", config.get("OPENAI_ADMIN_KEY", OPENAI_API_KEY))
print("מפתח Admin בשימוש (ה־OPENAI_ADMIN_KEY):", _mask_sensitive(OPENAI_ADMIN_KEY, 5))
GOOGLE_SHEET_ID = config["GOOGLE_SHEET_ID"]

# Service Account Dictionary for Google Drive uploads
SERVICE_ACCOUNT_DICT = config.get("SERVICE_ACCOUNT_DICT", {})

# הגדרות התראות שגיאות (לבוט הניהולי החדש)
ADMIN_BOT_TELEGRAM_TOKEN = config.get("ADMIN_BOT_TELEGRAM_TOKEN", TELEGRAM_BOT_TOKEN)
ADMIN_NOTIFICATION_CHAT_ID = "111709341"  # ה־chat_id שלך בבוט admin

# משתנים נוספים שנדרשים ל-notifications.py ו-message_handler.py
ADMIN_CHAT_ID = ADMIN_NOTIFICATION_CHAT_ID  # alias לעקביות
BOT_TOKEN = TELEGRAM_BOT_TOKEN  # alias לעקביות
MAX_MESSAGE_LENGTH = 4096  # מגבלת אורך הודעה בטלגרם
MAX_CODE_TRIES = 3  # מספר מקסימלי של ניסיונות קוד

# הגדרת LiteLLM
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# 🚀 הגדרת Google AI Studio (Gemini)
# פשוט יותר מ-Vertex AI - רק API key אחד ללא service accounts מסובכים
GEMINI_API_KEY = config.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
    safe_print(f"✅ [CONFIG] Google AI Studio (Gemini) API Key configured")
    print(f"   Key prefix: {_mask_sensitive(GEMINI_API_KEY, 5)}")  # 🔒 הפחתה ל-5 תווים לבטיחות
else:
    safe_print("⚠️ [CONFIG] אזהרה: GEMINI_API_KEY לא נמצא בקונפיגורציה.")

# 🚀 הגדרות Render לשחזור לוגים
RENDER_CONFIG = {
    "API_KEY": config.get("RENDER_API_KEY", ""),
    "SERVICE_ID": config.get("RENDER_SERVICE_ID", ""),
    "BASE_URL": "https://api.render.com/v1"
}

# בדיקת תקינות פרטי Render
if RENDER_CONFIG["API_KEY"]:
    safe_print(f"✅ [CONFIG] Render API Key configured")
    print(f"   Key prefix: {_mask_sensitive(RENDER_CONFIG['API_KEY'], 5)}")
else:
    safe_print("⚠️ [CONFIG] אזהרה: RENDER_API_KEY לא נמצא בקונפיגורציה.")

if RENDER_CONFIG["SERVICE_ID"]:
    safe_print(f"✅ [CONFIG] Render Service ID configured")
    print(f"   Service ID: {_mask_sensitive(RENDER_CONFIG['SERVICE_ID'], 8)}")
else:
    safe_print("⚠️ [CONFIG] אזהרה: RENDER_SERVICE_ID לא נמצא בקונפיגורציה.")

# 🎯 הגדרות מודלים
FREE_MODELS = ["gemini/gemini-1.5-flash", "gemini/gemini-2.0-flash-exp"]
PAID_MODELS = ["gpt-4o-mini", "gpt-4o", "gemini/gemini-2.5-flash"]
FREE_MODEL_DAILY_LIMIT = 100

# 🔑 הגדרת אימות גלובלית עבור Google Vertex AI (לא בשימוש)
# השארנו את הקוד הזה כגיבוי למקרה של מעבר עתידי ל-Vertex AI
# כרגע אנחנו משתמשים ב-Google AI Studio שפשוט יותר ועם GEMINI_API_KEY למעלה

# try:
#     # יצירת קובץ זמני עם credentials
#     import tempfile
#     import json as json_module
#     
#     service_account_dict = config["SERVICE_ACCOUNT_DICT"]
#     
#     # יצירת קובץ זמני עם ה-service account credentials
#     with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
#         json_module.dump(service_account_dict, temp_file, indent=2)
#         temp_credentials_path = temp_file.name
#     
#     # הגדרת משתני הסביבה כפי ש-LiteLLM מצפה
#     os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_credentials_path
#     os.environ["VERTEXAI_PROJECT"] = service_account_dict["project_id"]
#     os.environ["VERTEXAI_LOCATION"] = "us-central1"  # ברירת מחדל
#     
#     print(f"✅ [CONFIG] אימות Google Vertex AI הוגדר בהצלחה")
#     print(f"   Project: {service_account_dict['project_id']}")
#     print(f"   Credentials file: {temp_credentials_path}")
#     
# except KeyError as e:
#     print(f"⚠️ [CONFIG] אזהרה: לא נמצא מפתח '{e}' בקונפיגורציה עבור Vertex AI.")
# except Exception as e:
#     print(f"❌ [CONFIG] שגיאה בהגדרת אימות עבור Google Vertex AI: {e}")

# הגדרת Google Sheets
_sheets_cache = None  # Cache גלובלי לחיבורי Google Sheets
_cache_created_at = None  # זמן יצירת ה-cache

def reset_sheets_cache():
    """מאפס את ה-cache של Google Sheets - שימושי לפתרון בעיות"""
    global _sheets_cache, _cache_created_at
    _sheets_cache = None
    _cache_created_at = None
    print("[DEBUG] 🔄 Google Sheets cache reset")

def get_sheets_cache_info():
    """מחזיר מידע על מצב ה-cache"""
    global _sheets_cache, _cache_created_at
    if _sheets_cache is None:
        return {"status": "empty", "created_at": None, "age_seconds": 0}
    
    age_seconds = (time.time() - _cache_created_at) if _cache_created_at else 0
    return {
        "status": "active",
        "created_at": _cache_created_at,
        "age_seconds": round(age_seconds, 2)
    }

def setup_google_sheets():
    """
    מגדיר את החיבור ל-Google Sheets ומחזיר ארבעה ערכים: client וגיליונות עיקריים.
    עם מנגנון cache לביצועים מהירים יותר.
    פלט: gs_client, sheet_users, sheet_log, sheet_states
    """
    global _sheets_cache, _cache_created_at
    
    # 📦  אם רצים בסביבת CI – מחזירים dummy placeholders ומדלגים על התחברות אמיתית
    if any(os.getenv(var) for var in ["CI", "GITHUB_ACTIONS", "CONTINUOUS_INTEGRATION"]):
        if _sheets_cache is None:
            # יצירת tuple ריק פעם אחת ושמירתו ב-cache כדי להימנע מיצירה חוזרת בבדיקות
            _sheets_cache = (None, None, None, None)
            _cache_created_at = time.time()
        return _sheets_cache
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # מאפשר override של SERVICE_ACCOUNT_DICT באמצעות משתנה סביבה – שימושי ב-CI/Secrets
    _env_sa = os.getenv("SERVICE_ACCOUNT_DICT", "").strip()
    try:
        _sa_dict = json.loads(_env_sa) if _env_sa else config["SERVICE_ACCOUNT_DICT"]
    except Exception:
        _sa_dict = config["SERVICE_ACCOUNT_DICT"]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(_sa_dict, scope)
    gs_client = gspread.authorize(creds)

    # הגנת Fail-Fast – אם ההרשאה לא החזירה אובייקט תקף נזרוק שגיאה מיידית
    if gs_client is None or getattr(gs_client, "open_by_key", None) is None:
        raise RuntimeError("Google Sheets client failed to initialize – check credentials and environment variables (GOOGLE_APPLICATION_CREDENTIALS / SERVICE_ACCOUNT_DICT)")

    max_retries = 3
    delay = 5
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            # Obfuscate the Sheet ID – show only the first 4 characters to avoid exposing the full key
            safe_sheet_id = _mask_sensitive(GOOGLE_SHEET_ID, 4)
            print(f"[DEBUG] Attempt {attempt}: Opening Google Sheet with ID: {safe_sheet_id}")
            sheet = gs_client.open_by_key(GOOGLE_SHEET_ID)
            print(f"[DEBUG] Attempt {attempt}: Accessing worksheet: {config['SHEET_USER_TAB']}")
            sheet_users = sheet.worksheet(config["SHEET_USER_TAB"])
            print(f"[DEBUG] Attempt {attempt}: Accessing worksheet: {config['SHEET_LOG_TAB']}")
            sheet_log = sheet.worksheet(config["SHEET_LOG_TAB"])
            print(f"[DEBUG] Attempt {attempt}: Accessing worksheet: {config['SHEET_STATES_TAB']}")
            sheet_states = sheet.worksheet(config["SHEET_STATES_TAB"])
            print(f"[DEBUG] ✅ Google Sheets loaded successfully and cached!")
            
            # 🗑️ עברנו למסד נתונים - וידוא עמודות לא נדרש!
            # במסד נתונים עמודות נוצרות אוטומטית
            try:
                # Google Sheets עמודות היו נדרשות רק ב
                # במסד נתונים זה לא נדרש
                pass
                safe_print(f"[DEBUG] ✅ Ensured 'name' column exists in sheets")
            except Exception as e:
                safe_print(f"[DEBUG] ⚠️ Warning: Could not ensure 'name' column: {e}")
            
            # שמירה ב-cache עם timestamp
            _sheets_cache = (gs_client, sheet_users, sheet_log, sheet_states)
            _cache_created_at = time.time()
            return _sheets_cache
        except Exception as e:
            print(f"[ERROR] Google Sheets access failed on attempt {attempt}: {e}")
            last_exception = e
            if attempt < max_retries:
                print(f"[DEBUG] Retrying in {delay} seconds...")
                time.sleep(delay)
    print(f"[FATAL] All attempts to access Google Sheets failed.")
    logging.critical("[FATAL] All attempts to access Google Sheets failed.")
    return None, None, None, None


# ⚠️ יש להשתמש אך ורק במפתחות מתוך FIELDS_DICT! אין להכניס שמות שדה קשיחים חדשים כאן או בקוד אחר.
# שדות פרופיל משתמש - שימוש בפונקציה מה-fields_dict
def get_profile_fields():
    try:
        from fields_dict import FIELDS_DICT
        core_fields = ["age", "closet_status", "relationship_type", "self_religiosity_level", "occupation_or_role", "attracted_to"]
        return [key for key in core_fields if key in FIELDS_DICT]
    except ImportError:
        # fallback אם fields_dict לא זמין
        return ["age", "closet_status", "relationship_type", "self_religiosity_level", "occupation_or_role", "attracted_to"]

def get_summary_field():
    try:
        from fields_dict import FIELDS_DICT
        return "summary" if "summary" in FIELDS_DICT else list(FIELDS_DICT.keys())[-1]
    except ImportError:
        return "summary"

PROFILE_FIELDS = get_profile_fields()
SUMMARY_FIELD = get_summary_field()

# הגדרות לוגים
BOT_TRACE_LOG_FILENAME = "bot_trace_log.jsonl"
GPT_USAGE_LOG_FILENAME = "gpt_usage_log.jsonl"
CHAT_HISTORY_FILENAME = "chat_history.json"
BOT_ERRORS_FILENAME = "bot_errors.jsonl"
CRITICAL_ERRORS_FILENAME = "critical_errors.jsonl"
LOG_LIMIT = 100



# נתיבי קבצים עיקריים
gpt_log_path = os.path.join(DATA_DIR, GPT_USAGE_LOG_FILENAME)
BOT_TRACE_LOG_PATH = os.path.join(DATA_DIR, BOT_TRACE_LOG_FILENAME)
CHAT_HISTORY_PATH = os.path.join(DATA_DIR, CHAT_HISTORY_FILENAME)
BOT_ERRORS_PATH = os.path.join(DATA_DIR, BOT_ERRORS_FILENAME)
CRITICAL_ERRORS_PATH = os.path.join(DATA_DIR, CRITICAL_ERRORS_FILENAME)

# 🚀 נתיבי קבצים למערכת ניהול נתונים מקבילה
USER_PROFILES_PATH = os.path.join(DATA_DIR, "user_profiles.json")
SYNC_QUEUE_PATH = os.path.join(DATA_DIR, "sync_queue.json")

# 🔄 הגדרות סנכרון
SYNC_BATCH_SIZE = 10  # כמות עדכונים לסנכרון במקביל
SYNC_INTERVAL_SECONDS = 30  # זמן בין סנכרונים
MAX_SYNC_RETRIES = 3  # מספר ניסיונות סנכרון

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
        safe_print(f"❌ [CONFIG] חסרים משתני קונפיגורציה קריטיים: {missing}")
    else:
        safe_print("✅ [CONFIG] כל משתני הקונפיגורציה הקריטיים קיימים.")

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
        "CRITICAL_ERRORS_PATH": CRITICAL_ERRORS_PATH,
        "USER_PROFILES_PATH": USER_PROFILES_PATH,
        "SYNC_QUEUE_PATH": SYNC_QUEUE_PATH
    }

# ================================
# 🎯 הגדרת מודלים ופרמטרים מרכזית
# ================================
# כל שינוי כאן משפיע על כל מנועי ה-GPT

# ================================
# 🔧 הגדרות Concurrent Handling
# ================================
# הגדרות לניהול עומסי משתמשים מרובים
MAX_CONCURRENT_USERS = 50  # מספר משתמשים מקסימלי במקביל (הוגדל ל-50 - הרבה מקום)
MAX_SHEETS_OPERATIONS_PER_MINUTE = 60  # מגבלת Google Sheets (60% מ-100)
SHEETS_QUEUE_SIZE = 100  # גודל תור לפעולות Sheets
SHEETS_BATCH_SIZE = 10  # כמות פעולות לעיבוד במקביל (הוגדל מ-5 ל-10 לטיפול בשימוש מוגזם)

# סוגי עדכונים לפי עדיפות
UPDATE_PRIORITY = {
    "critical": 1,    # היסטוריה + פרופיל - מיידי
    "normal": 2,      # לוגים רגילים - יכול לחכות
    "low": 3          # נתונים סטטיסטיים - לא דחוף
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

# 🚀 הגדרת פורט דינמית - תואמת לפלטפורמות cloud
# בפלטפורמות כמו Render, Heroku, Railway - הפלטפורמה מגדירה את הפורט דינמית
PRODUCTION_PORT = int(os.getenv("PORT", 8000))     # פורט דינמי מהפלטפורמה או 8000
DEVELOPMENT_PORT = 10000     # פורט לסביבת פיתוח

safe_print(f"🔧 [CONFIG] פורט שרת: {PRODUCTION_PORT} (מקור: {'משתנה סביבה PORT' if os.getenv('PORT') else 'ברירת מחדל 8000'})")

MODEL_ROUTES = {
    # ========= מקרא =========
    # default       – המודל הראשי (Fast רגיל)
    # extra_emotion – מודל רגשי מתקדם (שייך רק ל-gpt_a)
    # fallback1     – fallback מהיר/זול (אם default נכשל)
    # fallback2     – fallback חירום GPT-4o (אם הכל נכשל)
    # ========================
    "gpt_a": {
        "default": "gemini/gemini-1.5-pro",   # Fast (filter FALSE)
        "extra_emotion": "gemini/gemini-2.5-flash", # Smart (filter TRUE)
        "fallback1": "gemini/gemini-2.0-flash-exp", # rate-limit fallback
        "fallback2": "openai/gpt-4o"              # Emergency paid
    },
    "gpt_b": {
        "default": "gemini/gemini-2.0-flash-exp",
        "fallback1": "gemini/gemini-1.5-pro",
        "fallback2": "openai/gpt-4o"
    },
    "gpt_c": {
        "default": "gemini/gemini-1.5-pro",
        "fallback1": "gemini/gemini-2.0-flash-exp",
        "fallback2": "openai/gpt-4o"
    },
    "gpt_d": {
        "default": "gemini/gemini-1.5-pro",
        "fallback1": "gemini/gemini-2.0-flash-exp",
        "fallback2": "openai/gpt-4o"
    },
    "gpt_e": {
        "default": "gemini/gemini-2.5-pro",
        "fallback1": "gemini/gemini-2.5-flash",
        "fallback2": "openai/gpt-4o"
    },
}

# --------------------------
# ⬇️ Generating legacy maps so שאר הקוד ימשיך לעבוד בלי שינוי
# --------------------------
GPT_MODELS = {}
GPT_FALLBACK_MODELS = {}
GPT_PREMIUM_FALLBACK = {}

for engine, routes in MODEL_ROUTES.items():
    if engine == "gpt_a":
        # Smart (extra_emotion) משמש כ-GPT_MODELS
        GPT_MODELS[engine] = routes.get("extra_emotion", routes["default"])
        # default משמש כ-fallback ראשון
        if routes.get("default"):
            GPT_FALLBACK_MODELS[engine] = routes["default"]
    else:
        GPT_MODELS[engine] = routes["default"]
        if routes.get("fallback1"):
            GPT_FALLBACK_MODELS[engine] = routes["fallback1"]
    if routes.get("fallback2"):
        GPT_PREMIUM_FALLBACK[engine] = routes["fallback2"]

# --------------------------------------------------------------------------
# סוף SECTION – From here downwards אין שינויי מודלים נוספים.
# --------------------------------------------------------------------------

# === Database URL from config ===
DATABASE_URL = config.get("DATABASE_INTERNAL_URL") or config.get("DATABASE_URL")
