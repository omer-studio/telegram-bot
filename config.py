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
        project_root = os.path.dirname(os.path.abspath(__file__))
        local_path = os.path.join(project_root, "etc", "secrets", "config.json")
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

# פונקציה ליצירת קליינט LiteLLM (לשמירה על תאימות)
def get_client():
    """
    מחזיר פונקציה שמדמה את הקליינט המקורי של OpenAI אבל משתמשת ב-LiteLLM.
    פלט: פונקציה שמדמה OpenAI client
    """
    import litellm
    
    class LiteLLMClient:
        def __init__(self):
            self.chat = self.Chat()
        
        class Chat:
            def __init__(self):
                self.completions = self.Completions()
            
            class Completions:
                def create(self, model, messages, temperature=1, metadata=None, store=True, max_tokens=None):
                    # המרת metadata ל-litellm format
                    litellm_kwargs = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                    if metadata:
                        litellm_kwargs["metadata"] = metadata
                    response = litellm.completion(**litellm_kwargs)
                    return self._convert_response(response)
                
                def _convert_response(self, litellm_response):
                    print(f"[DEBUG] === LITELLM RAW RESPONSE ===")
                    print(f"[DEBUG] litellm_response type: {type(litellm_response)}")
                    print(f"[DEBUG] litellm_response: {litellm_response}")
                    print(f"[DEBUG] === END LITELLM RAW RESPONSE ===")
                    
                    class MockResponse:
                        def __init__(self, litellm_response):
                            self.choices = [self.MockChoice(litellm_response)]
                            self.usage = self.MockUsage(litellm_response)
                            self.model = litellm_response.get("model", "unknown")
                        class MockChoice:
                            def __init__(self, response):
                                self.message = self.MockMessage(response)
                            class MockMessage:
                                def __init__(self, response):
                                    self.content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
                        class MockUsage:
                            def __init__(self, response):
                                usage_data = response.get("usage", {})
                                self.prompt_tokens = usage_data.get("prompt_tokens", 0)
                                self.completion_tokens = usage_data.get("completion_tokens", 0)
                                self.total_tokens = usage_data.get("total_tokens", 0)
                                self.prompt_tokens_details = self.MockPromptTokensDetails(usage_data)
                            class MockPromptTokensDetails:
                                def __init__(self, usage_data):
                                    # נסה כמה אפשרויות שונות לקבל cached tokens
                                    self.cached_tokens = 0
                                    
                                    try:
                                        # המר ל-dict אם זה לא dict
                                        if not isinstance(usage_data, dict):
                                            if hasattr(usage_data, '__dict__'):
                                                usage_data = usage_data.__dict__
                                            else:
                                                usage_data = {}
                                        
                                        # אפשרות 1: מ-prompt_tokens_details
                                        if 'prompt_tokens_details' in usage_data:
                                            prompt_details = usage_data['prompt_tokens_details']
                                            if isinstance(prompt_details, dict):
                                                self.cached_tokens = prompt_details.get('cached_tokens', 0)
                                            elif hasattr(prompt_details, 'cached_tokens'):
                                                self.cached_tokens = getattr(prompt_details, 'cached_tokens', 0)
                                        
                                        # אפשרות 2: ישירות מ-usage
                                        if self.cached_tokens == 0:
                                            self.cached_tokens = usage_data.get('cached_tokens', 0)
                                        
                                        # אפשרות 3: שמות אחרים שLiteLLM עשוי להשתמש בהם
                                        if self.cached_tokens == 0:
                                            self.cached_tokens = usage_data.get('cache_read_input_tokens', 0)
                                        
                                        # אפשרות 4: מ-raw response אם קיים
                                        if self.cached_tokens == 0 and hasattr(usage_data, '_raw_response'):
                                            raw_usage = usage_data._raw_response.get('usage', {})
                                            if 'prompt_tokens_details' in raw_usage:
                                                self.cached_tokens = raw_usage['prompt_tokens_details'].get('cached_tokens', 0)
                                            elif 'cached_tokens' in raw_usage:
                                                self.cached_tokens = raw_usage.get('cached_tokens', 0)
                                        
                                    except Exception as e:
                                        print(f"[DEBUG] MockPromptTokensDetails error: {e}")
                                        self.cached_tokens = 0
                                    
                                    print(f"[DEBUG] MockPromptTokensDetails: cached_tokens = {self.cached_tokens}")
                                    print(f"[DEBUG] MockPromptTokensDetails: usage_data type = {type(usage_data)}")
                                    print(f"[DEBUG] MockPromptTokensDetails: usage_data = {usage_data}")
                    return MockResponse(litellm_response)
    return LiteLLMClient()

# יצירת קליינט (לשמירה על תאימות)
client = get_client()

# הגדרת Google Sheets
def setup_google_sheets():
    """
    מגדיר את החיבור ל-Google Sheets ומחזיר שלושה גיליונות עיקריים.
    פלט: sheet_users, sheet_log, sheet_states
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(config["SERVICE_ACCOUNT_DICT"], scope)
    gs_client = gspread.authorize(creds)

    sheet_users = gs_client.open_by_key(GOOGLE_SHEET_ID).worksheet("גיליון1")
    sheet_log = gs_client.open_by_key(GOOGLE_SHEET_ID).worksheet("2")
    sheet_states = gs_client.open_by_key(GOOGLE_SHEET_ID).worksheet("user_states")

    return sheet_users, sheet_log, sheet_states


# ⚠️ יש להשתמש אך ורק במפתחות מתוך FIELDS_DICT! אין להכניס שמות שדה קשיחים חדשים כאן או בקוד אחר.
# שדות פרופיל משתמש
PROFILE_FIELDS = [
    key for key in [
        "age", "closet_status", "relationship_type", "self_religiosity_level", "occupation_or_role", "attracted_to"
    ] if key in FIELDS_DICT
]
SUMMARY_FIELD = "summary" if "summary" in FIELDS_DICT else list(FIELDS_DICT.keys())[-1]

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
        "LOG_FILE_PATH": LOG_FILE_PATH,
        "GPT_LOG_PATH": GPT_LOG_PATH,
        "BOT_TRACE_LOG_PATH": BOT_TRACE_LOG_PATH,
        "CHAT_HISTORY_PATH": CHAT_HISTORY_PATH,
        "BOT_ERRORS_PATH": BOT_ERRORS_PATH,
        "CRITICAL_ERRORS_PATH": CRITICAL_ERRORS_PATH
    }
