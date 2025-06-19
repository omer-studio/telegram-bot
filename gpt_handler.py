"""
gpt_handler.py
--------------
קובץ זה מרכז את כל הפונקציות שמבצעות אינטראקציה עם GPT (שליחת הודעות, חישוב עלות, דיבאגינג).
הרציונל: ריכוז כל הלוגיקה של GPT במקום אחד, כולל תיעוד מלא של טוקנים, עלויות, ולוגים.

מערכת חישוב עלות GPT דינאמית (יוני 2025)
--------------------------------------------------
- כל חישוב עלות טוקנים מתבצע דינאמית לפי קובץ gpt_pricing.json.
- כל מודל (gpt-4o, nano, mini וכו') מוגדר עם מחירי prompt/cached/completion בקובץ JSON זה.
- כל שינוי מחירון או הוספת מודל חדש – יש לעדכן אך ורק את gpt_pricing.json (אין צורך לשנות קוד).
- אם שם המודל לא קיים במחירון – תוחזר עלות 0 ותירשם שגיאה בלוג.
לפני השינוי הגדול של הGPTS ----------------------------
# דוקומנטציה:
# - לעדכון מחירים: ערוך את gpt_pricing.json בלבד.
# - להוסף מודל: הוסף ערך חדש ל-gpt_pricing.json עם שם המודל והמחירים.
# - חובה לשמור על שמות תואמים בין usage (response.model) לבין המפתחות ב-JSON.
"""

import json
import logging
from datetime import datetime
from config import client, GPT_LOG_PATH
import os
from fields_dict import FIELDS_DICT
import threading
from prompts import BOT_REPLY_SUMMARY_PROMPT, PROFILE_EXTRACTION_ENHANCED_PROMPT
import asyncio
import re
from gpt_usage_manager import GPTUsageManager
from gpt_e_logger import append_gpt_e_html_update

# ===================== פונקציות עזר ללוגים ודיבאג =====================

def _debug_gpt_usage(model_name, prompt_tokens, completion_tokens, cached_tokens, total_tokens, call_type):
    """
    מדפיס מידע דיבאג על שימוש ב-GPT (לוגים פנימיים בלבד).
    """
    print(f"[DEBUG][{call_type}] מודל: {model_name}, prompt: {prompt_tokens}, completion: {completion_tokens}, cached: {cached_tokens}, total: {total_tokens}")

import os
import json
from datetime import datetime

def write_gpt_log(call_type, usage_log, model_name):
    """
    שומר usage log לקובץ DATA/gpt_usage_log.jsonl (שורה אחת לכל קריאה).
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(timespec="microseconds"),
        "type": call_type,
        "model": model_name,
        **usage_log
    }
    log_path = GPT_LOG_PATH  # במקום os.path.join("DATA", "gpt_usage_log.jsonl")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

# ===================== הגדרת שער החליפין =====================
USD_TO_ILS = 3.7  # שער הדולר-שקל (יש לעדכן לפי הצורך)

# הגדרת נתיב לוג אחיד מתוך תיקיית הפרויקט
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(PROJECT_ROOT, exist_ok=True)

# ===================== טעינת מחירון דינאמי לכל המודלים (יוני 2025) =====================

# טוען את המחירון מהקובץ פעם אחת בלבד
PRICING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gpt_pricing.json')
try:
    with open(PRICING_PATH, encoding='utf-8') as f:
        GPT_PRICING = json.load(f)
except Exception as e:
    print(f"[ERROR] לא הצלחתי לטעון את gpt_pricing.json: {e}")
    GPT_PRICING = {}

# פונקציה שמביאה את מחירי הטוקנים לפי שם המודל
# מחזירה מילון עם prompt/cached/completion, או None אם לא קיים
# מבצעת normalization לשם המודל (למשל gpt-4o-2024-08-06 -> gpt-4o)
def get_model_prices(model_name):
    if not model_name:
        return None
    # ניקוי גרסאות מהשם (למשל gpt-4o-2024-08-06 -> gpt-4o)
    base_name = model_name.split("-")[0]
    # חיפוש מדויק
    if model_name in GPT_PRICING:
        return GPT_PRICING[model_name]
    # חיפוש לפי base_name
    for key in GPT_PRICING:
        if model_name.startswith(key):
            return GPT_PRICING[key]
    if base_name in GPT_PRICING:
        return GPT_PRICING[base_name]
    # לא נמצא מחירון
    print(f"[ERROR] לא נמצא מחירון למודל: {model_name}")
    return None

# יצירת מופע גלובלי של מנהל usage (טעינה חד פעמית של המחירון)
gpt_usage_manager = GPTUsageManager()

# עדכון calculate_gpt_cost להשתמש במנהל החדש

def calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens=0, model_name='gpt-4o', usd_to_ils=USD_TO_ILS):
    """
    מחשב עלות GPT (USD, ILS, אגורות) לפי מספר טוקנים, כולל טוקנים רגילים, קשד ופלט, ולפי שם המודל.
    קלט: prompt_tokens, completion_tokens, cached_tokens, model_name, usd_to_ils
    פלט: dict usage אחיד עם כל הערכים.
    """
    return gpt_usage_manager.calculate(model_name, prompt_tokens, completion_tokens, cached_tokens, usd_to_ils)

# ============================הג'יפיטי ה-A - פועל תמיד ועונה תשובה למשתמש ======================= 


def get_main_response(full_messages):
    """
    שולח הודעה ל-gpt_a הראשי ומחזיר את התשובה, כולל פירוט עלות וטוקנים.
    קלט: full_messages — רשימת הודעות (כולל system prompt).
    פלט: dict עם תשובה, usage, עלות.
    # מהלך מעניין: שימוש בפרומט הראשי שמגדיר את האישיות של דניאל.
    """
    try:
        # full_messages כולל את ה-SYSTEM_PROMPT כבר בתחילתו (נבנה ב-message_handler)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=full_messages,
            temperature=1,
        )

        # --- DEBUG: Print all usage fields from API ---
        try:
            def _to_serializable(val):
                if hasattr(val, '__dict__'):
                    return {k: _to_serializable(v) for k, v in vars(val).items()}
                elif isinstance(val, (list, tuple)):
                    return [_to_serializable(x) for x in val]
                elif isinstance(val, dict):
                    return {k: _to_serializable(v) for k, v in val.items()}
                else:
                    try:
                        json.dumps(val)
                        return val
                    except Exception:
                        return str(val)
            usage_dict = {}
            for k in dir(response.usage):
                if not k.startswith("_") and not callable(getattr(response.usage, k)):
                    v = getattr(response.usage, k)
                    usage_dict[k] = _to_serializable(v)
            print(f"[DEBUG] API usage raw: {json.dumps(usage_dict, ensure_ascii=False)}")
        except Exception as e:
            print(f"[DEBUG] Failed to print API usage fields: {e}")

        # שליפת נתוני usage
        prompt_tokens = response.usage.prompt_tokens
        prompt_tokens_details = response.usage.prompt_tokens_details
        cached_tokens = prompt_tokens_details.cached_tokens
        prompt_regular = prompt_tokens - cached_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name = response.model

        # --- Smart debug ---
        _debug_gpt_usage(model_name, prompt_tokens, completion_tokens, cached_tokens, total_tokens, "main_reply")

        # חישוב עלות דינאמי לפי המודל
        cost_data = calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens, model_name)
        # כל השדות נשמרים ב-usage_log
        usage_log = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "prompt_regular": prompt_regular,
            **cost_data,
            "model": response.model
        }

        from utils import log_event_to_file
        log_event_to_file({
            "event": "gpt_main_call",
            "gpt_input": full_messages,
            "gpt_reply": response.choices[0].message.content,
            "model": response.model,
            "usage": usage_log
        })

        write_gpt_log("main_reply", usage_log, response.model)

        return {
            "bot_reply": response.choices[0].message.content,
            **usage_log
        }
    except Exception as e:
        logging.error(f"❌ שגיאה ב-gpt_a ראשי: {e}")
        raise

def get_main_response_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, get_main_response, *args, **kwargs)

# ============================הג'יפיטי ה-B - תמצית תשובה להיסטוריה ======================= 

def summarize_bot_reply(reply_text):
    """
    שולח תשובה של הבוט ל-gpt_b ומקבל תמצית קצרה להיסטוריה.
    קלט: reply_text — התשובה המלאה של הבוט.
    פלט: dict עם תמצית, usage, עלות.
    # מהלך מעניין: תמצית חכמה שמשמרת את המהות אבל מקצרת משמעותית.
    """
    try:
        system_prompt = BOT_REPLY_SUMMARY_PROMPT  # פרומט לתמצית
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": reply_text}],
            temperature=1,
        )

        # שליפת נתוני usage
        prompt_tokens = response.usage.prompt_tokens
        prompt_tokens_details = response.usage.prompt_tokens_details
        cached_tokens = prompt_tokens_details.cached_tokens
        prompt_regular = prompt_tokens - cached_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name = response.model

        # --- Smart debug ---
        _debug_gpt_usage(model_name, prompt_tokens, completion_tokens, cached_tokens, total_tokens, "summary")

        # חישוב עלות דינאמי לפי המודל
        cost_data = calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens, model_name)
        usage_log = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "prompt_regular": prompt_regular,
            **cost_data,
            "model": response.model
        }

        write_gpt_log("summary", usage_log, response.model)

        return {
            "summary": response.choices[0].message.content.strip(),
            **usage_log
        }
    except Exception as e:
        logging.error(f"❌ שגיאה ב-gpt_b תמצית: {e}")
        raise

def summarize_bot_reply_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, summarize_bot_reply, *args, **kwargs)

# ============================הג'יפיטי ה-3 - פועל תמיד ומחלץ מידע לת.ז הרגשית ======================= 

def validate_extracted_data(data):
    """
    בודק אם הנתונים שחולצו מה-GPT תקינים (dict, מפתחות מסוג str בלבד).
    קלט: data (dict)
    פלט: True/False
    """
    validated = data.copy()
    
    # בדיקת גיל הגיוני - רק מעל 80
    if FIELDS_DICT["age"] in validated:
        try:
            age = int(validated[FIELDS_DICT["age"]])
            if age > 80:
                logging.warning(f"⚠️ גיל {age} מעל 80, מסיר מהנתונים")
                del validated[FIELDS_DICT["age"]]
            else:
                validated[FIELDS_DICT["age"]] = age
        except (ValueError, TypeError):
            logging.warning(f"⚠️ גיל לא תקין: {validated[FIELDS_DICT['age']]}, מסיר מהנתונים")
            del validated[FIELDS_DICT["age"]]
    
    # הגבלת אורך שדות לחסכון בטוקנים
    for field, value in list(validated.items()):
        if isinstance(value, str):
            if len(value) > 100:
                logging.warning(f"⚠️ שדה {field} ארוך מדי ({len(value)} תווים), מקצר")
                validated[field] = value[:97] + "..."
            elif len(value.strip()) == 0:
                logging.warning(f"⚠️ שדה {field} ריק, מסיר")
                del validated[field]
    
    return validated


# ============================פונקציה שמפעילה את הג'יפיטי הרביעי לפי היגיון -לא פועל תמיד - עדכון חכם של ת.ז הרגשית ======================= 

def smart_update_profile(existing_profile, user_message):
    """
    מעדכן תעודת זהות רגשית של משתמש, כולל מיזוג חכם במידת הצורך.
    קלט: existing_profile (dict), user_message (str)
    פלט: dict ממוזג, usage (dict)
    # מהלך מעניין: בוחר אוטומטית האם להפעיל מיזוג חכם או רגיל.
    """
    print("[DEBUG][smart_update_profile] CALLED")
    try:
        logging.info("🔄 מתחיל עדכון חכם של ת.ז הרגשית")
        print(f"[DEBUG][smart_update_profile] --- START ---")
        print(f"[DEBUG][smart_update_profile] existing_profile: {existing_profile} (type: {type(existing_profile)})")
        # שלב 1: gpt_e - חילוץ מידע חדש
        new_data, extract_usage = extract_user_profile_fields_enhanced(user_message, existing_profile)
        print(f"[DEBUG][smart_update_profile] new_data: {new_data} (type: {type(new_data)})")
        print(f"[DEBUG][smart_update_profile] extract_usage: {extract_usage} (type: {type(extract_usage)})")
        # הגנה: ודא ש-new_data הוא dict עם מפתחות str בלבד
        if not isinstance(new_data, dict) or not all(isinstance(k, str) for k in new_data.keys()):
            logging.error(f"⚠️ new_data לא תקין (לפני מיזוג): {new_data}")
            print(f"[ALERT][smart_update_profile] new_data לא תקין (לפני מיזוג): {new_data}")
            new_data = {}
        logging.info(f"🤖 gpt_c חילץ: {list(new_data.keys())}")
        print(f"[DEBUG][smart_update_profile] new_data keys: {list(new_data.keys())}")
        # אם אין מידע חדש - אין מה לעדכן
        if not new_data:
            logging.info("ℹ️ אין מידע חדש, מחזיר ת.ז ללא שינוי")
            print("[DEBUG][smart_update_profile] אין מידע חדש, מחזיר ת.ז ללא שינוי")
            return existing_profile, extract_usage, None
        # עדכון פשוט - מיזוג רגיל
        updated_profile = {**existing_profile, **new_data}
        print(f"[DEBUG][smart_update_profile] updated_profile: {updated_profile}")
        if existing_profile != updated_profile:
            diff_keys = set(updated_profile.keys()) - set(existing_profile.keys())
            print(f"[DEBUG][smart_update_profile] profile diff (new keys): {diff_keys}")
        else:
            print(f"[DEBUG][smart_update_profile] profile unchanged after simple merge")
        print(f"[DEBUG][smart_update_profile] returning: profile_updated={updated_profile}, extract_usage={extract_usage}")
        return updated_profile, extract_usage, None
    except Exception as e:
        import traceback
        print(f"[ERROR][smart_update_profile] Exception: {e}")
        print(traceback.format_exc())
        return existing_profile, {}, None

def smart_update_profile_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, smart_update_profile, *args, **kwargs)

# ============================ GPT-E - מערכת הזיכרון המשופרת ============================

def update_user_summary_enhanced(existing_profile, user_message):
    """
    GPT-E: מעדכן תעודת זהות רגשית של משתמש עם סיכום קריא במקום JSON מורכב.
    קלט: existing_profile (dict), user_message (str)
    פלט: dict ממוזג, usage (dict)
    """
    print("[DEBUG][update_user_summary_enhanced] CALLED - GPT-E")
    try:
        logging.info("🔄 מתחיל עדכון משופר של ת.ז הרגשית עם GPT-E")
        print(f"[DEBUG][update_user_summary_enhanced] --- START ---")
        print(f"[DEBUG][update_user_summary_enhanced] existing_profile: {existing_profile} (type: {type(existing_profile)})")
        
        # שלב 1: GPT-E - חילוץ ועדכון בסיכום קריא
        # שימוש ב-gpt_e החדשה במקום extract_user_profile_fields_enhanced
        existing_summary = existing_profile.get("summary", "")
        gpt_e_result = gpt_e(existing_summary, user_message, "")
        
        if gpt_e_result is None:
            # אין שינוי - מחזיר את הפרופיל הקיים
            logging.info("ℹ️ אין מידע חדש, מחזיר ת.ז ללא שינוי")
            print("[DEBUG][update_user_summary_enhanced] אין מידע חדש, מחזיר ת.ז ללא שינוי")
            return existing_profile, {}
        
        # יש שינוי - מעדכן את הפרופיל
        updated_summary = gpt_e_result.get("updated_summary", "")
        full_data = gpt_e_result.get("full_data", {})
        
        # עדכון הפרופיל עם הנתונים החדשים
        updated_profile = {**existing_profile, **full_data}
        
        # וידוא שהסיכום מעודכן
        if updated_summary:
            updated_profile["summary"] = updated_summary
        
        print(f"[DEBUG][update_user_summary_enhanced] updated_profile: {updated_profile}")
        
        if existing_profile != updated_profile:
            diff_keys = set(updated_profile.keys()) - set(existing_profile.keys())
            print(f"[DEBUG][update_user_summary_enhanced] profile diff (new keys): {diff_keys}")
        else:
            print(f"[DEBUG][update_user_summary_enhanced] profile unchanged")
        
        # הכנת usage data
        usage_data = {k: v for k, v in gpt_e_result.items() if k not in ["updated_summary", "full_data"]}
        
        logging.info(f"✅ GPT-E עדכן ת.ז עם {len(full_data)} שדות חדשים")
        print(f"[DEBUG][update_user_summary_enhanced] returning: profile_updated={updated_profile}, extract_usage={usage_data}")
        return updated_profile, usage_data
        
    except Exception as e:
        import traceback
        print(f"[ERROR][update_user_summary_enhanced] Exception: {e}")
        print(traceback.format_exc())
        return existing_profile, {}

def update_user_summary_enhanced_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, update_user_summary_enhanced, *args, **kwargs)

def extract_user_profile_fields_enhanced(text, existing_profile=None, system_prompt=None, client=None):
    """
    GPT-E: שולחת את הטקסט ל-GPT-E ומחזירה dict עם שדות מידע אישי בסיכום קריא.
    קלט: text (טקסט חופשי מהמשתמש), existing_profile (dict קיים), system_prompt (פרומט ייעודי), client (אופציונלי).
    פלט: (enhanced_data: dict, usage_data: dict)
    """
    print("[DEBUG][extract_user_profile_fields_enhanced] CALLED - GPT-E")
    if system_prompt is None:
        system_prompt = PROFILE_EXTRACTION_ENHANCED_PROMPT  # פרומט GPT-E
    if client is None:
        from gpt_handler import client
    if existing_profile is None:
        existing_profile = {}
    
    try:
        # הכנת הפרומט עם הפרופיל הקיים
        profile_context = ""
        if existing_profile:
            profile_context = f"\n\nפרופיל קיים:\n{json.dumps(existing_profile, ensure_ascii=False, indent=2)}"
        
        response = client.chat.completions.create(
            model="gpt-4.1-nano",  # המודל הכי זול
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"הודעה חדשה: {text}{profile_context}"}
            ],
            temperature=0,
            max_tokens=300
        )
        content = response.choices[0].message.content.strip()
        print(f"[DEBUG][extract_user_profile_fields_enhanced] raw GPT-E content: {content}")
        
        # --- ניקוי בלוק ```json ... ``` אם קיים ---
        if content.startswith("```"):
            match = re.search(r"```(?:json)?\s*({.*?})\s*```", content, re.DOTALL)
            if match:
                content = match.group(1)
                print(f"[DEBUG][extract_user_profile_fields_enhanced] cleaned content: {content}")
        
        try:
            enhanced_data = json.loads(content)
            print(f"[DEBUG][extract_user_profile_fields_enhanced] after json.loads: {enhanced_data}")
            # החזרת full_data במקום enhanced_data ישירות
            full_data = enhanced_data.get("full_data", {})
            print(f"[DEBUG][extract_user_profile_fields_enhanced] extracted full_data: {full_data}")
        except Exception as e:
            print(f"[ERROR][extract_user_profile_fields_enhanced] JSON parsing error: {e}")
            print(f"[ERROR][extract_user_profile_fields_enhanced] content that failed to parse: {content}")
            full_data = {}
        
        # --- usage/cost ---
        prompt_tokens = response.usage.prompt_tokens
        prompt_tokens_details = getattr(response.usage, 'prompt_tokens_details', None)
        cached_tokens = getattr(prompt_tokens_details, 'cached_tokens', 0) if prompt_tokens_details else 0
        prompt_regular = prompt_tokens - cached_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name = response.model
        
        # חישוב עלות דינאמי לפי המודל
        cost_data = calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens, model_name)
        usage_data = {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens,
            'cached_tokens': cached_tokens,
            **cost_data,
            'model': response.model
        }
        
        print(f"[DEBUG][extract_user_profile_fields_enhanced] returning full_data: {full_data}")
        return full_data, usage_data
        
    except Exception as e:
        logging.error(f"❌ שגיאה קריטית ב-extract_user_profile_fields_enhanced: {e}")
        return {}, {}

def extract_user_profile_fields_enhanced_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, extract_user_profile_fields_enhanced, *args, **kwargs)

# ============================ GPT-E - הפונקציה הראשית ============================

def gpt_e(existing_summary, user_message, last_bot_message=""):
    """
    GPT-E: הפונקציה הראשית שמחליפה את GPT-C ו-GPT-D.
    מעדכנת סיכום קיים עם מידע חדש מהודעה.
    קלט: existing_summary (str), user_message (str), last_bot_message (str) - ההודעה האחרונה של הבוט
    פלט: dict עם updated_summary, full_data, ו-usage info
    """
    print("[DEBUG][gpt_e] CALLED - הפונקציה הראשית")
    try:
        logging.info("🔄 מתחיל GPT-E - עדכון סיכום עם מידע חדש")
        print(f"[DEBUG][gpt_e] --- START ---")
        print(f"[DEBUG][gpt_e] existing_summary: {existing_summary} (type: {type(existing_summary)})")
        print(f"[DEBUG][gpt_e] user_message: {user_message} (type: {type(user_message)})")
        print(f"[DEBUG][gpt_e] last_bot_message: {last_bot_message} (type: {type(last_bot_message)})")
        
        # הכנת הפרומט
        system_prompt = PROFILE_EXTRACTION_ENHANCED_PROMPT
        
        # הכנת ההודעה למשתמש עם הקשר
        if last_bot_message:
            user_message_json = json.dumps({
                "last_bot_message": last_bot_message,
                "user_reply": user_message
            }, ensure_ascii=False, indent=2)
            user_content = (
                f"סיכום קיים: {existing_summary}\n\n"
                f"הודעת משתמש בפורמט JSON:\n{user_message_json}\n\n"
                f"נתח את הערך של user_reply בלבד, תוך הבנה שהוא תגובה ל־last_bot_message.\n"
                f"חלץ רק מידע שנאמר במפורש בתוך user_reply."
            )
        else:
            user_content = (
                f"סיכום קיים: {existing_summary}\n\n"
                f"הודעה חדשה של המשתמש: {user_message}\n\n"
                f"נתח רק את ההודעה של המשתמש כפי שהיא מופיעה כאן."
            )

        response = client.chat.completions.create(
            model="gpt-4.1-nano",  # המודל הכי זול
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        print(f"[DEBUG][gpt_e] raw GPT-E response: {content}")
        
        # --- ניקוי בלוק ```json ... ``` אם קיים ---
        if content.startswith("```"):
            match = re.search(r"```(?:json)?\s*({.*?})\s*```", content, re.DOTALL)
            if match:
                content = match.group(1)
                print(f"[DEBUG][gpt_e] cleaned content: {content}")
        
        # פרסור התשובה
        try:
            result = json.loads(content)
            print(f"[DEBUG][gpt_e] parsed result: {result}")
            # בדיקה אם התשובה ריקה (אין מידע חדש)
            # במקום להחזיר None, נחזיר usage בלבד עם שדות חילוץ ריקים
            is_empty = not result.get("summary") and not result.get("full_data")
        except Exception as e:
            print(f"[ERROR][gpt_e] JSON parsing error: {e}")
            print(f"[ERROR][gpt_e] content that failed to parse: {content}")
            # אם נכשל פרסור JSON, נחזיר usage בלבד עם שדות חילוץ ריקים
            result = {"summary": "", "full_data": {}}
            is_empty = True
        
        # הכנת usage data
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cached_tokens = getattr(response.usage, 'cached_tokens', 0)
        model_name = response.model
        
        # חישוב עלות
        cost_data = calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens, model_name)
        
        # הכנת התוצאה הסופית
        final_result = {
            "updated_summary": result.get("summary", existing_summary),
            "full_data": result.get("full_data", {}),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "model": model_name,
            **cost_data
        }
        print(f"[DEBUG][gpt_e] final_result: {final_result}")
        logging.info(f"✅ GPT-E הושלם בהצלחה")
        
        # הוספת עדכון ל-HTML
        append_gpt_e_html_update(
            old_summary=existing_summary,
            user_message=user_message,
            new_summary=final_result["updated_summary"],
            tokens_used=total_tokens,
            cost=final_result.get("cost_total_usd", 0),
            model=model_name
        )
        
        return final_result
        
    except Exception as e:
        import traceback
        print(f"[ERROR][gpt_e] Exception: {e}")
        print(traceback.format_exc())
        logging.error(f"❌ שגיאה ב-GPT-E: {e}")
        return None

def gpt_e_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, gpt_e, *args, **kwargs)

