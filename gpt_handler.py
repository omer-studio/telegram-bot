"""
gpt_handler.py
--------------
קובץ זה מרכז את כל הפונקציות שמבצעות אינטראקציה עם GPT (שליחת הודעות, חישוב עלות, דיבאגינג).
הרציונל: ריכוז כל הלוגיקה של GPT במקום אחד, כולל תיעוד מלא של טוקנים, עלויות, ולוגים.
"""

import json
import logging
from datetime import datetime
from config import client, SYSTEM_PROMPT, GPT_LOG_PATH
import os
from fields_dict import FIELDS_DICT
import threading
from profile_extraction import extract_user_profile_fields
from prompts import PROFILE_EXTRACTION_PROMPT, BOT_REPLY_SUMMARY_PROMPT, SENSITIVE_PROFILE_MERGE_PROMPT, SYSTEM_PROMPT
import asyncio

# הגדרת נתיב לוג אחיד מתוך תיקיית הפרויקט
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(PROJECT_ROOT, exist_ok=True)

# ===================== קבועים מרכזיים לעלויות GPT ושער דולר =====================

# מחירים קבועים (נכון ליוני 2025) ל־GPT-4o
COST_PROMPT_REGULAR = 0.005 / 1000    # טוקן קלט רגיל
COST_PROMPT_CACHED = 0.0025 / 1000    # טוקן קלט קשד (cache)
COST_COMPLETION = 0.02 / 1000        # טוקן פלט
USD_TO_ILS = 3.6                     # שער דולר-שקל (לשינוי במקום אחד בלבד)

# --- Debug state for smart logging ---
_debug_last_cached_tokens = {}
_debug_last_gpt3_usages = []
_debug_printed_models = set()
_debug_lock = threading.Lock()

# --- Smart debug function ---
def _debug_gpt_usage(model, prompt_tokens, completion_tokens, cached_tokens, total_tokens, usage_type):
    with _debug_lock:
        # Print raw usage once per model per run
        if model not in _debug_printed_models:
            print(f"[DEBUG] שימוש ב-GPT ({usage_type}) | model: {model} | prompt: {prompt_tokens} | completion: {completion_tokens} | cached: {cached_tokens} | total: {total_tokens}")
            _debug_printed_models.add(model)
        # Track last 3 cached_tokens per model
        if model not in _debug_last_cached_tokens:
            _debug_last_cached_tokens[model] = []
        _debug_last_cached_tokens[model].append(cached_tokens)
        if len(_debug_last_cached_tokens[model]) > 3:
            _debug_last_cached_tokens[model].pop(0)
        if len(_debug_last_cached_tokens[model]) == 3 and len(set(_debug_last_cached_tokens[model])) == 1:
            print(f"⚠️ [ALERT] cached_tokens עבור המודל {model} ({usage_type}) חזר 3 פעמים ברצף אותו ערך: {cached_tokens}")
        # Check token sum
        if None not in (prompt_tokens, completion_tokens, cached_tokens, total_tokens):
            calc_total = prompt_tokens + completion_tokens + cached_tokens
            if calc_total != total_tokens:
                print(f"⚠️ [ALERT] סכום טוקנים לא תואם ({usage_type}, {model}): prompt({prompt_tokens}) + completion({completion_tokens}) + cached({cached_tokens}) = {calc_total} != total({total_tokens})")
        # Special: GPT3 always zero
        if model and 'gpt-3' in model:
            _debug_last_gpt3_usages.append((prompt_tokens, completion_tokens, cached_tokens))
            if len(_debug_last_gpt3_usages) > 3:
                _debug_last_gpt3_usages.pop(0)
            if len(_debug_last_gpt3_usages) == 3 and all(x == (0,0,0) for x in _debug_last_gpt3_usages):
                print("⚠️ [ALERT] GPT3 usage תמיד 0 בשלוש קריאות אחרונות! בדוק אינטגרציה.")

def write_gpt_log(ttype, usage, model):
    """
    שומר לוג של השימוש בכל קריאה ל־GPT
    קלט: ttype (סוג), usage (dict usage), model (שם המודל)
    פלט: אין (שומר לקובץ לוג)
    """
    log_path = GPT_LOG_PATH
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": ttype,
        "model": model,
        "tokens_prompt": usage.get("prompt_tokens", 0),
        "tokens_completion": usage.get("completion_tokens", 0),
        "tokens_total": usage.get("total_tokens", 0),
        "tokens_cached": usage.get("cached_tokens", 0),  # נוסף: כמות קשד
        "cost_prompt_regular": usage.get("cost_prompt_regular", 0),
        "cost_prompt_cached": usage.get("cost_prompt_cached", 0),
        "cost_completion": usage.get("cost_completion", 0),
        "cost_total": usage.get("cost_total", 0),
        "cost_total_ils": usage.get("cost_total_ils", 0),
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logging.error(f"שגיאה בכתיבה לקובץ gpt_usage_log: {e}")

def safe_float(val):
    """
    ניסיון להמיר ערך ל-float, במקרה של כשל יחזיר 0.0 עם לוג אזהרה.
    קלט: ערך כלשהו
    פלט: float
    """
    try:
        return float(val)
    except (ValueError, TypeError):
        logging.warning(f"safe_float: value '{val}' could not be converted to float. Using 0.0 instead.")
        return 0.0

def calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens=0, usd_to_ils=USD_TO_ILS):
    """
    מחשב עלות GPT (USD, ILS, אגורות) לפי מספר טוקנים, כולל טוקנים רגילים, קשד ופלט.
    קלט: prompt_tokens, completion_tokens, cached_tokens (ברירת מחדל 0), usd_to_ils (שער דולר)
    פלט: dict עם כל הערכים.
    # מהלך מעניין: מחשב עלות גם לאגורות וגם לשקל, כולל הפרדה בין טוקנים רגילים וקשד.
    """
    prompt_regular = prompt_tokens - cached_tokens
    cost_prompt_regular = prompt_regular * COST_PROMPT_REGULAR
    cost_prompt_cached = cached_tokens * COST_PROMPT_CACHED
    cost_completion = completion_tokens * COST_COMPLETION
    cost_total = cost_prompt_regular + cost_prompt_cached + cost_completion
    cost_total_ils = round(cost_total * usd_to_ils, 4)
    cost_agorot = int(round(cost_total_ils * 100))
    return {
        "cost_prompt_regular": cost_prompt_regular,
        "cost_prompt_cached": cost_prompt_cached,
        "cost_completion": cost_completion,
        "cost_total": cost_total,
        "cost_total_ils": cost_total_ils,
        "cost_agorot": cost_agorot
    }

# ============================הג'יפיטי ה-1 - פועל תמיד ועונה תשובה למשתמש ======================= 


def get_main_response(full_messages):
    """
    שולח הודעה ל-GPT הראשי ומחזיר את התשובה, כולל פירוט עלות וטוקנים.
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

        # חישוב עלות לפי המחירון המרכזי
        cost_prompt_regular = prompt_regular * COST_PROMPT_REGULAR
        cost_prompt_cached = cached_tokens * COST_PROMPT_CACHED
        cost_completion = completion_tokens * COST_COMPLETION
        cost_total = cost_prompt_regular + cost_prompt_cached + cost_completion
        cost_total_ils = cost_total * USD_TO_ILS
        cost_agorot = cost_total_ils * 100
        # כל השדות נשמרים ב-usage_log
        usage_log = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "prompt_regular": prompt_regular,
            "cost_prompt_regular": cost_prompt_regular,
            "cost_prompt_cached": cost_prompt_cached,
            "cost_completion": cost_completion,
            "cost_total": cost_total,
            "cost_total_ils": cost_total_ils,
            "cost_agorot": cost_agorot,
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
        logging.error(f"❌ שגיאה ב-GPT ראשי: {e}")
        raise

def get_main_response_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, get_main_response, *args, **kwargs)

# ============================הג'יפיטי ה-2 - מקצר את תשובת הבוט אם היא ארוכה מדי כדי לחסוך בהיסטוריה ======================= 


def summarize_bot_reply(reply_text):
    """
    מסכם את תשובת הבוט למשפט קצר וחם, בסגנון וואטסאפ.
    קלט: reply_text (טקסט תשובת הבוט)
    פלט: סיכום קצר (str), usage (dict)
    # מהלך מעניין: שימוש בפרומט תמצות שמוגדר ב-prompts.py.
    """
    system_prompt = BOT_REPLY_SUMMARY_PROMPT  # פרומט תמצות תשובה
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": reply_text}],
            temperature=1,
        )
        prompt_tokens = response.usage.prompt_tokens
        prompt_tokens_details = response.usage.prompt_tokens_details
        cached_tokens = prompt_tokens_details.cached_tokens
        prompt_regular = prompt_tokens - cached_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name = response.model

        # --- Smart debug ---
        _debug_gpt_usage(model_name, prompt_tokens, completion_tokens, cached_tokens, total_tokens, "reply_summary")

        cost_prompt_regular = prompt_regular * COST_PROMPT_REGULAR
        cost_prompt_cached = cached_tokens * COST_PROMPT_CACHED
        cost_completion = completion_tokens * COST_COMPLETION
        cost_total = cost_prompt_regular + cost_prompt_cached + cost_completion
        cost_total_ils = cost_total * USD_TO_ILS
        cost_agorot = cost_total_ils * 100
        # כל השדות נשמרים ב-usage_log
        usage_log = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "prompt_regular": prompt_regular,
            "cost_prompt_regular": cost_prompt_regular,
            "cost_prompt_cached": cost_prompt_cached,
            "cost_completion": cost_completion,
            "cost_total": cost_total,
            "cost_total_ils": cost_total_ils,
            "cost_agorot": cost_agorot,
            "model": response.model
        }
        write_gpt_log("reply_summary", usage_log, response.model)
        return {
            "bot_summary": response.choices[0].message.content.strip(),
            **usage_log
        }
    except Exception as e:
        logging.error(f"❌ שגיאה ב-GPT מקצר: {e}")
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


# ============================הג'יפיטי ה-4 - מיזוג חכם של מידע רגיש ======================= 

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
    
    # בדיקה אם באמת צריך GPT4
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
            model="gpt-4o",
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

        # חישובי עלות
        prompt_tokens = response.usage.prompt_tokens
        prompt_tokens_details = response.usage.prompt_tokens_details
        cached_tokens = prompt_tokens_details.cached_tokens
        prompt_regular = prompt_tokens - cached_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        cost_prompt_regular = prompt_regular * COST_PROMPT_REGULAR
        cost_prompt_cached = cached_tokens * COST_PROMPT_CACHED
        cost_completion = completion_tokens * COST_COMPLETION
        cost_total = cost_prompt_regular + cost_prompt_cached + cost_completion
        cost_total_ils = cost_total * USD_TO_ILS
        cost_agorot = int(round(cost_total_ils * 100))

        usage_data = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "cost_prompt_regular": cost_prompt_regular,
            "cost_prompt_cached": cost_prompt_cached,
            "cost_completion": cost_completion,
            "cost_total": cost_total,
            "cost_total_ils": cost_total_ils,
            "cost_agorot": cost_agorot,
            "model": response.model
        }

        logging.info(f"🤖 GPT4 מיזוג החזיר: '{content[:200]}...'")
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
        
        logging.info(f"✅ GPT4 עדכן ת.ז עם {len(validated_profile)} שדות")
        if validated_profile != merged_profile:
            logging.info(f"🔧 לאחר validation: הוסרו/תוקנו שדות")

        return {
            "prompt_tokens": prompt_tokens,
            "cached_tokens": cached_tokens,
            "prompt_regular": prompt_regular,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_prompt_regular": cost_prompt_regular,
            "cost_prompt_cached": cost_prompt_cached,
            "cost_completion": cost_completion,
            "cost_total": cost_total,
            "cost_total_ils": cost_total_ils,
            "cost_agorot": cost_agorot,
            "model": usage_data.get("model", "")
        }, validated_profile

    except json.JSONDecodeError as e:
        logging.error(f"❌ שגיאה בפרסור JSON במיזוג GPT4: {e}")
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
        logging.error(f"❌ שגיאה כללית ב-GPT4 מיזוג: {e}")
        
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


# פונקציית עזר - קובעת אם להפעיל GPT4
def should_use_gpt4_merge(existing_profile, new_data):
    """
    מחליט האם להפעיל מיזוג חכם (GPT4) לפי סוג השינוי בפרופיל.
    קלט: existing_profile, new_data
    פלט: True/False
    """
    complex_fields = [
        FIELDS_DICT["attracted_to"], FIELDS_DICT["who_knows"], FIELDS_DICT["who_doesnt_know"], FIELDS_DICT["attends_therapy"], 
        FIELDS_DICT["primary_conflict"], FIELDS_DICT["trauma_history"], FIELDS_DICT["goal_in_course"], 
        FIELDS_DICT["language_of_strength"], FIELDS_DICT["coping_strategies"], FIELDS_DICT["fears_concerns"], FIELDS_DICT["future_vision"]
    ]
    print("[DEBUG][should_use_gpt4_merge] complex_fields:")
    for idx, field in enumerate(complex_fields):
        print(f"[DEBUG][should_use_gpt4_merge] complex_fields[{idx}] = {field} (type: {type(field)})")
        if not isinstance(field, str):
            print(f"[DEBUG][should_use_gpt4_merge][ALERT] complex_fields[{idx}] הוא {type(field)}! ערך: {field}")
            continue  # דלג על שדות לא תקינים
        if field in new_data:  # GPT3 מצא שדה מורכב חדש
            existing_value = existing_profile.get(field, "")
            print(f"[DEBUG][should_use_gpt4_merge] בדיקה: field='{field}', existing_value='{existing_value}'")
            if existing_value and isinstance(existing_value, str) and existing_value.strip():  # והשדה קיים בת.ז
                logging.info(f"🎯 GPT4 נדרש - שדה '{field}' מצריך מיזוג")
                print(f"[DEBUG][should_use_gpt4_merge] נמצא שדה מורכב חדש: {field}")
                return True
    print("[DEBUG][should_use_gpt4_merge] אין צורך ב-GPT4 - עדכון פשוט מספיק")
    logging.info("✅ אין צורך ב-GPT4 - עדכון פשוט מספיק")
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
        # שלב 1: GPT3 - חילוץ מידע חדש
        new_data, extract_usage = extract_user_profile_fields(user_message)
        print(f"[DEBUG][smart_update_profile] new_data: {new_data} (type: {type(new_data)})")
        print(f"[DEBUG][smart_update_profile] extract_usage: {extract_usage} (type: {type(extract_usage)})")
        # הגנה: ודא ש-new_data הוא dict עם מפתחות str בלבד
        if not isinstance(new_data, dict) or not all(isinstance(k, str) for k in new_data.keys()):
            logging.error(f"⚠️ new_data לא תקין (לפני מיזוג): {new_data}")
            print(f"[ALERT][smart_update_profile] new_data לא תקין (לפני מיזוג): {new_data}")
            new_data = {}
        logging.info(f"🤖 GPT3 חילץ: {list(new_data.keys())}")
        print(f"[DEBUG][smart_update_profile] new_data keys: {list(new_data.keys())}")
        # אם אין מידע חדש - אין מה לעדכן
        if not new_data:
            logging.info("ℹ️ אין מידע חדש, מחזיר ת.ז ללא שינוי")
            print("[DEBUG][smart_update_profile] אין מידע חדש, מחזיר ת.ז ללא שינוי")
            return existing_profile, extract_usage, None
        # שלב 2: בדיקה אם צריך GPT4
        print(f"[DEBUG][smart_update_profile] קורא ל-should_use_gpt4_merge עם existing_profile: {existing_profile}, new_data: {new_data}")
        if should_use_gpt4_merge(existing_profile, new_data):
            logging.info("🎯 מפעיל GPT4 למיזוג מורכב")
            print("[DEBUG][smart_update_profile] מפעיל GPT4 למיזוג מורכב!")
            # שלב 3: GPT4 - מיזוג חכם
            print(f"[DEBUG][smart_update_profile] לפני merge_sensitive_profile_data: existing_profile={existing_profile}, new_data={new_data}, user_message={user_message}")
            merge_usage, updated_profile = merge_sensitive_profile_data(existing_profile, new_data, user_message)
            print(f"[DEBUG][smart_update_profile] אחרי merge_sensitive_profile_data: updated_profile={updated_profile}, merge_usage={merge_usage}")
            logging.info(f"✅ GPT4 עדכן ת.ז עם {len(updated_profile)} שדות")
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
            logging.info("✅ עדכון פשוט ללא GPT4")
            print("[DEBUG][smart_update_profile] עדכון פשוט ללא GPT4")
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

def get_combined_usage_data(extract_usage, merge_usage=None):
    """
    מאחד usage של חילוץ ומיזוג (אם יש), מחזיר usage כולל לכל התהליך.
    קלט: extract_usage (dict), merge_usage (dict או None)
    פלט: dict usage כולל
    """
    # נתוני GPT3
    if not isinstance(extract_usage, dict):
        raise ValueError("extract_usage חייב להיות dict!")
    extract_data = extract_usage.copy()
    
    # אם GPT4 רץ - הוסף את הנתונים שלו
    if merge_usage:
        if not isinstance(merge_usage, dict):
            raise ValueError("merge_usage חייב להיות dict!")
        merge_data = merge_usage.copy()
        return {**extract_data, **merge_data}
    else:
        return extract_data

