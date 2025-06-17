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
from prompts import PROFILE_EXTRACTION_PROMPT, BOT_REPLY_SUMMARY_PROMPT, SENSITIVE_PROFILE_MERGE_PROMPT, PROFILE_EXTRACTION_ENHANCED_PROMPT
import asyncio
import re
from gpt_usage_manager import GPTUsageManager

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


# ============================הג'יפיטי ה-D - מיזוג חכם של מידע רגיש ======================= 

def merge_sensitive_profile_data(existing_profile, new_data, user_message):
    """
    ממזג תעודת זהות רגשית קיימת עם מידע חדש, לפי כללים רגישים (מי יודע, טראומות וכו').
    קלט: existing_profile (dict), new_data (dict), user_message (str)
    פלט: dict ממוזג, usage (dict)
    # מהלך מעניין: מיזוג חכם של טראומות, מי יודע/לא יודע, עדכון summary.
    """
    # שדות שצריכים מיזוג מורכב
    complex_fields = [
        FIELDS_DICT["attracted_to"], FIELDS_DICT["who_knows"], FIELDS_DICT["who_doesnt_know"], FIELDS_DICT["attends_therapy"], 
        FIELDS_DICT["primary_conflict"], FIELDS_DICT["trauma_history"], FIELDS_DICT["goal_in_course"], 
        FIELDS_DICT["language_of_strength"], FIELDS_DICT["coping_strategies"], FIELDS_DICT["fears_concerns"], FIELDS_DICT["future_vision"]
    ]
    
    # בדיקה אם באמת צריך gpt_d
    needs_merge = False
    for field in complex_fields:
        if field in new_data:
            existing_value = existing_profile.get(field, "")
            if existing_value and existing_value.strip():
                needs_merge = True
                break
    
    if not needs_merge:
        logging.info("🔄 לא נדרש מיזוג מורכב, מחזיר עדכון רגיל")
        return {**existing_profile, **new_data}

    system_prompt = SENSITIVE_PROFILE_MERGE_PROMPT  # פרומט מיזוג רגיש

    usage_data = {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "cached_tokens": 0, "cost_prompt_regular": 0, "cost_prompt_cached": 0,
        "cost_completion": 0, "cost_total": 0, "cost_total_ils": 0, "model": ""
    }

    try:
        # הכנת המידע למיזוג
        merge_request = {
            "existing_profile": existing_profile,
            "new_data": new_data,
            "user_message": user_message
        }
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"מידע קיים:\n{json.dumps(existing_profile, ensure_ascii=False, indent=2)}\n\nמידע חדש:\n{json.dumps(new_data, ensure_ascii=False, indent=2)}\n\nהודעה מקורית:\n{user_message}"}
        ]

        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=messages,
            temperature=0,  # דיוק מקסימלי למידע רגיש
            max_tokens=400   # מספיק לכל השדות + summary
        )

        content = response.choices[0].message.content.strip()

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

        # חישובי עלות דינאמי לפי המודל
        prompt_tokens = response.usage.prompt_tokens
        prompt_tokens_details = response.usage.prompt_tokens_details
        cached_tokens = prompt_tokens_details.cached_tokens
        prompt_regular = prompt_tokens - cached_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name = response.model
        cost_data = calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens, model_name)
        usage_data = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            **cost_data,
            "model": response.model
        }

        logging.info(f"🤖 gpt_d מיזוג החזיר: '{content[:200]}...'")
        write_gpt_log("sensitive_merge", usage_data, response.model)

        # פרסור התשובה
        if not content.startswith("{"):
            if "{" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                content = content[start:end]

        merged_profile = json.loads(content)
        
        # validation על התוצאה הסופית
        validated_profile = validate_extracted_data(merged_profile)
        
        logging.info(f"✅ gpt_d עדכן ת.ז עם {len(validated_profile)} שדות")
        if validated_profile != merged_profile:
            logging.info(f"🔧 לאחר validation: הוסרו/תוקנו שדות")

        return {
            "prompt_tokens": prompt_tokens,
            "cached_tokens": cached_tokens,
            "prompt_regular": prompt_regular,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            **cost_data,
            "model": usage_data.get("model", "")
        }, validated_profile

    except json.JSONDecodeError as e:
        logging.error(f"❌ שגיאה בפרסור JSON במיזוג gpt_d: {e}")
        logging.error(f"📄 התוכן: '{content}'")
        
        # fallback - מיזוג פשוט במקרה של כשל
        fallback_merge = {**existing_profile, **new_data}
        logging.warning("🔧 משתמש במיזוג fallback פשוט")
        
        return {
            "prompt_tokens": 0,
            "cached_tokens": 0,
            "prompt_regular": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_prompt_regular": 0.0,
            "cost_prompt_cached": 0.0,
            "cost_completion": 0.0,
            "cost_total": 0.0,
            "cost_total_ils": 0.0,
            "cost_agorot": 0,
            "model": "fallback"
        }, fallback_merge

    except Exception as e:
        logging.error(f"❌ שגיאה כללית ב-gpt_d מיזוג: {e}")
        
        # fallback - מיזוג פשוט במקרה של כשל
        fallback_merge = {**existing_profile, **new_data}
        
        return {
            "prompt_tokens": 0,
            "cached_tokens": 0,
            "prompt_regular": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_prompt_regular": 0.0,
            "cost_prompt_cached": 0.0,
            "cost_completion": 0.0,
            "cost_total": 0.0,
            "cost_total_ils": 0.0,
            "cost_agorot": 0,
            "model": "error"
        }, fallback_merge


# פונקציית עזר - קובעת אם להפעיל gpt_d
def should_use_gpt_d_merge(existing_profile, new_data):
    """
    מחליט האם להפעיל מיזוג חכם (gpt_d) לפי סוג השינוי בפרופיל.
    קלט: existing_profile, new_data
    פלט: True/False
    """
    complex_fields = [
        FIELDS_DICT["attracted_to"], FIELDS_DICT["who_knows"], FIELDS_DICT["who_doesnt_know"], FIELDS_DICT["attends_therapy"], 
        FIELDS_DICT["primary_conflict"], FIELDS_DICT["trauma_history"], FIELDS_DICT["goal_in_course"], 
        FIELDS_DICT["language_of_strength"], FIELDS_DICT["coping_strategies"], FIELDS_DICT["fears_concerns"], FIELDS_DICT["future_vision"]
    ]
    print("[DEBUG][should_use_gpt_d_merge] complex_fields:")
    for idx, field in enumerate(complex_fields):
        print(f"[DEBUG][should_use_gpt_d_merge] complex_fields[{idx}] = {field} (type: {type(field)})")
        if not isinstance(field, str):
            print(f"[DEBUG][should_use_gpt_d_merge][ALERT] complex_fields[{idx}] הוא {type(field)}! ערך: {field}")
            continue  # דלג על שדות לא תקינים
        if field in new_data:  # gpt_c מצא שדה מורכב חדש
            existing_value = existing_profile.get(field, "")
            print(f"[DEBUG][should_use_gpt_d_merge] בדיקה: field='{field}', existing_value='{existing_value}'")
            if existing_value and isinstance(existing_value, str) and existing_value.strip():  # והשדה קיים בת.ז
                logging.info(f"🎯 gpt_d נדרש - שדה '{field}' מצריך מיזוג")
                print(f"[DEBUG][should_use_gpt_d_merge] נמצא שדה מורכב חדש: {field}")
                return True
    print("[DEBUG][should_use_gpt_d_merge] אין צורך ב-gpt_d - עדכון פשוט מספיק")
    logging.info("✅ אין צורך ב-gpt_d - עדכון פשוט מספיק")
    return False


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
        # שלב 1: gpt_c - חילוץ מידע חדש
        new_data, extract_usage = extract_user_profile_fields(user_message)
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
        # שלב 2: בדיקה אם צריך gpt_d
        print(f"[DEBUG][smart_update_profile] קורא ל-should_use_gpt_d_merge עם existing_profile: {existing_profile}, new_data: {new_data}")
        if should_use_gpt_d_merge(existing_profile, new_data):
            logging.info("🎯 מפעיל gpt_d למיזוג מורכב")
            print("[DEBUG][smart_update_profile] מפעיל gpt_d למיזוג מורכב!")
            # שלב 3: gpt_d - מיזוג חכם
            print(f"[DEBUG][smart_update_profile] לפני merge_sensitive_profile_data: existing_profile={existing_profile}, new_data={new_data}, user_message={user_message}")
            merge_usage, updated_profile = merge_sensitive_profile_data(existing_profile, new_data, user_message)
            print(f"[DEBUG][smart_update_profile] אחרי merge_sensitive_profile_data: updated_profile={updated_profile}, merge_usage={merge_usage}")
            logging.info(f"✅ gpt_d עדכן ת.ז עם {len(updated_profile)} שדות")
            print(f"[DEBUG][smart_update_profile] merge_usage: {merge_usage}")
            print(f"[DEBUG][smart_update_profile] updated_profile: {updated_profile}")
            # print diff
            if existing_profile != updated_profile:
                diff_keys = set(updated_profile.keys()) - set(existing_profile.keys())
                print(f"[DEBUG][smart_update_profile] profile diff (new keys): {diff_keys}")
            else:
                print(f"[DEBUG][smart_update_profile] profile unchanged after merge")
            print(f"[DEBUG][smart_update_profile] returning: profile_updated={updated_profile}, extract_usage={extract_usage}")
            return updated_profile, extract_usage, merge_usage
        else:
            logging.info("✅ עדכון פשוט ללא gpt_d")
            print("[DEBUG][smart_update_profile] עדכון פשוט ללא gpt_d")
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
        gpt_e_result = gpt_e(existing_summary, user_message)
        
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
            model="gpt-4.1-nano",
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
            match = re.search(r"```(?:json)?\\s*({.*?})\\s*```", content, re.DOTALL)
            if match:
                content = match.group(1)
                print(f"[DEBUG][extract_user_profile_fields_enhanced] cleaned content: {content}")
        
        try:
            enhanced_data = json.loads(content)
            print(f"[DEBUG][extract_user_profile_fields_enhanced] after json.loads: {enhanced_data}")
        except Exception as e:
            print(f"[ERROR][extract_user_profile_fields_enhanced] JSON parsing error: {e}")
            enhanced_data = {}
        
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
        
        print(f"[DEBUG][extract_user_profile_fields_enhanced] returning enhanced_data: {enhanced_data}")
        return enhanced_data, usage_data
        
    except Exception as e:
        logging.error(f"❌ שגיאה קריטית ב-extract_user_profile_fields_enhanced: {e}")
        return {}, {}

def extract_user_profile_fields_enhanced_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, extract_user_profile_fields_enhanced, *args, **kwargs)

# ============================ GPT-E - הפונקציה הראשית ============================

def gpt_e(existing_summary, user_message):
    """
    GPT-E: הפונקציה הראשית שמחליפה את GPT-C ו-GPT-D.
    מעדכנת סיכום קיים עם מידע חדש מהודעה.
    קלט: existing_summary (str), user_message (str)
    פלט: dict עם updated_summary, full_data, ו-usage info
    """
    print("[DEBUG][gpt_e] CALLED - הפונקציה הראשית")
    try:
        logging.info("🔄 מתחיל GPT-E - עדכון סיכום עם מידע חדש")
        print(f"[DEBUG][gpt_e] --- START ---")
        print(f"[DEBUG][gpt_e] existing_summary: {existing_summary} (type: {type(existing_summary)})")
        print(f"[DEBUG][gpt_e] user_message: {user_message} (type: {type(user_message)})")
        
        # הכנת הפרומט
        system_prompt = PROFILE_EXTRACTION_ENHANCED_PROMPT
        
        # הכנת ההודעה למשתמש
        user_content = f"סיכום קיים: {existing_summary}\n\nהודעה חדשה: {user_message}"
        
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        print(f"[DEBUG][gpt_e] raw GPT-E response: {content}")
        
        # פרסור התשובה
        try:
            result = json.loads(content)
            print(f"[DEBUG][gpt_e] parsed result: {result}")
        except Exception as e:
            print(f"[ERROR][gpt_e] JSON parsing error: {e}")
            return None
        
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

