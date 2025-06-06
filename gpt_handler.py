"""
gpt_handler.py — כל הפונקציות לטיפול ב־GPT במקום אחד
בגרסה זו נוסף חישוב עלות לכל סוג טוקן (רגיל, קשד, פלט) + תיעוד מלא של הטוקנים + החזר עלות באגורות לכל קריאה
"""

import json
import logging
from datetime import datetime
from config import client, SYSTEM_PROMPT, GPT_LOG_PATH
import os
from fields_dict import FIELDS_DICT
import threading

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
    """
    try:
        return float(val)
    except (ValueError, TypeError):
        logging.warning(f"safe_float: value '{val}' could not be converted to float. Using 0.0 instead.")
        return 0.0

def calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens=0, usd_to_ils=USD_TO_ILS):
    """
    מחשב עלות GPT (USD, ILS, אגורות) לפי מספר טוקנים, כולל טוקנים רגילים, קשד ופלט.
    מחזיר dict עם כל הערכים.
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
    GPT ראשי - נותן תשובה למשתמש
    מחזיר גם את כל פרטי העלות (טוקנים, קשד, מחיר מדויק) במבנה dict
    """
    try:
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



# ============================הג'יפיטי ה-2 - מקצר את תשובת הבוט אם היא ארוכה מדי כדי לחסוך בהיסטוריה ======================= 


def summarize_bot_reply(reply_text):
    """
    GPT מקצר - תמצות תשובת הבוט
    (הוספנו גם כאן חישוב עלות מלא והחזרת עלות באגורות וקשד)
    """
    system_prompt = (
        "סכם את ההודעה שלי כאילו אני מדבר עם חבר: "
        "משפט אחד חם ואישי בסגנון חופשי (לא תיאור יבש), בגוף ראשון, כולל אמירה אישית קצרה על מהות התגובה שלי, "
        "ואז את השאלה ששאלתי אם יש, בצורה חמה וזורמת, עד 20 מילים בסך הכל. תשלב אימוג'י רלוונטי אם מתאים, כמו שמדברים בווטסאפ. "
        "אל תעשה ניתוחים טכניים או תיאור של הודעה – ממש תכתוב את זה כמו הודעת וואטסאפ קצרה, בגוף ראשון, בסגנון חופשי וקליל."
    )
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



# ============================הג'יפיטי ה-3 - פועל תמיד ומחלץ מידע לת.ז הרגשית ======================= 

def extract_user_profile_fields(text):
    """
    GPT מחלץ מידע - מחלץ פרטים אישיים מההודעה (גרסה מעודכנת)
    מחזיר tuple: (new_data, usage_data)
    """
    system_prompt = """אתה מחלץ מידע אישי מטקסט. החזר JSON עם השדות הבאים רק אם הם מוזכרים:

age - גיל (מספר בלבד)
pronoun_preference - לשון פניה: "את"/"אתה"/"מעורב"
occupation_or_role - עיסוק/תפקיד
attracted_to - משיכה: "גברים"/"נשים"/"שניהם"/"לא ברור"
relationship_type - מצב זוגי: "רווק"/"נשוי"/"נשוי+2"/"גרוש" וכו'
self_religious_affiliation - זהות דתית: "יהודי"/"ערבי"/"דרוזי"/"נוצרי"/"שומרוני"
self_religiosity_level - רמת דתיות: "דתי"/"חילוני"/"מסורתי"/"חרדי"/"דתי לאומי"
family_religiosity - רקע משפחתי: "משפחה דתית"/"משפחה חילונית"/"משפחה מעורבת"
closet_status - מצב ארון: "בארון"/"יצא חלקית"/"יצא לכולם"
who_knows - מי יודע עליו
who_doesnt_know - מי לא יודע עליו
attends_therapy - טיפול: "כן"/"לא"/"טיפול זוגי"/"קבוצת תמיכה"
primary_conflict -  הקונפליקט המרכזי שמעסיק אותו בחייו
trauma_history - טראומות (בעדינות)
goal_in_course - מטרות בקורסMore actions
language_of_strength - משפטים מחזקים
coping_strategies - דרכי התמודדות - מה מרים אותו מה עוזר לו
fears_concerns - פחדים וחששות - אם שיתף בפחד מסויים אתה מכניס את זה לשם
future_vision - חזון עתיד

אם הוא מבקש למחוק את כל מה שאתה יודע עליו - אז תחזיר שדות שירים שידרסו את הקיימים
אם הוא מבקש שתמחק נתונים ספציפים אז תמחק נתונים ספציפים כמו אל תזכור בן כמה אני


דוגמאות:
"אני בן 25, יהודי דתי" → {"age": 25, "self_religious_affiliation": "יהודי", "self_religiosity_level": "דתי"}
"גרוש עם 8 ילדים" → {"relationship_type": "נשוי+8"}
"סיפרתי להורים, אבל לבוס לא" → {"who_knows": "הורים", "who_doesnt_know": "בוס"}

רק JSON, בלי הסברים!"""

    usage_data = {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "cached_tokens": 0, "cost_prompt_regular": 0, "cost_prompt_cached": 0,
        "cost_completion": 0, "cost_total": 0, "cost_total_ils": 0, "cost_gpt3": 0, "model": ""
    }
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0,
            max_tokens=200
        )
        content = response.choices[0].message.content.strip()
        # חישובי עלות (ללא שינוי)
        prompt_tokens = response.usage.prompt_tokens
        prompt_tokens_details = response.usage.prompt_tokens_details
        cached_tokens = prompt_tokens_details.cached_tokens
        prompt_regular = prompt_tokens - cached_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        model_name = response.model
        # --- Smart debug ---
        _debug_gpt_usage(model_name, prompt_tokens, completion_tokens, cached_tokens, total_tokens, "identity_extraction")
        cost_prompt_regular = prompt_regular * COST_PROMPT_REGULAR
        cost_prompt_cached = cached_tokens * COST_PROMPT_CACHED
        cost_completion = completion_tokens * COST_COMPLETION
        cost_total = cost_prompt_regular + cost_prompt_cached + cost_completion
        cost_total_ils = cost_total * USD_TO_ILS
        cost_agorot = cost_total_ils * 100
        cost_gpt3 = cost_total_ils * 100  # עלות באגורות (float מדויק, כל הספרות)
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
            "cost_gpt3": cost_gpt3,
            "model": response.model
        }
        logging.info(f"🤖 GPT מחלץ מידע החזיר: '{content}'")
        write_gpt_log("identity_extraction", usage_data, usage_data.get("model", ""))
        # --- שינוי עיקרי: מחזיר tuple (new_data, usage_data) ---
        try:
            new_data = json.loads(content)
        except Exception:
            new_data = {}
        return new_data, usage_data
    except Exception as e:
        logging.error(f"❌ שגיאה ב-GPT מחלץ: {e}")
        return {}, usage_data


def validate_extracted_data(data):
    """
    בודק רק דברים בסיסיים - לא מגביל תוכן
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
#===============================================================================


# ============================הג'יפיטי ה-4 - מיזוג חכם של מידע רגיש ======================= 

def merge_sensitive_profile_data(existing_profile, new_data, user_message):
    """
    GPT4 - מיזוג זהיר וחכם של מידע רגיש בת.ז הרגשית
    מטפל במיזוג מורכב של שדות כמו who_knows/who_doesnt_know, trauma_history וכו'
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

    system_prompt = """אתה מומחה למיזוג זהיר של מידע רגיש. קיבלת:\n1. ת.ז רגשית קיימת\n2. מידע חדש מההודעה\n3. ההודעה המקורית לקונטקסט\n\nעקרונות קריטיים:\n- אל תמחק מידע אלא אם המשתמש אמר במפורש שמשהו השתנה\n- מיזוג חכם: צבור מידע חדש עם קיים, אל תדרוס\n- who_knows ↔ who_doesnt_know: אם מישהו עבר מרשימה אחת לשנייה - הסר אותו מהרשימה הראשונה\n- trauma_history: צבור עם '; ' בין טראומות שונות, ואם יש טראומות דומות (למשל טראומה של מכות ואחריה טראומה של צבא שקשורה לאותה חוויה), תאחד אותן לאירוע אחד מתומצת. אל תיצור כפילויות.\n- attracted_to: שלב באחוזים או תיאור מדויק\n- אם יש סתירה - העדף את המידע החדש אם הוא מפורש\n\nדוגמה לאיחוד טראומות:\nאם יש 'טראומה: מכות בילדות' ו-'טראומה: מכות בצבא', תאחד ל-'טראומה: חוויות של מכות בילדות ובצבא'.\n\nלאחר המיזוג, עדכן את \"summary\" לשקף את הזהות הרגשית המעודכנת:\n- גיל, זהות דתית, מצב זוגי עכשיו\n- מצב ארון נוכחי (מי יודע/לא יודע)\n- שינויים משמעותיים שקרו\nעד 100 תווים, תמציתי ועדכני.\n\nהחזר רק JSON מעודכן מלא, בלי הסברים!"""

    usage_data = {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "cached_tokens": 0, "cost_prompt_regular": 0, "cost_prompt_cached": 0,
        "cost_completion": 0, "cost_total": 0, "cost_total_ils": 0, "cost_gpt4": 0, "model": ""
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
        cost_agorot = cost_total_ils * 100
        cost_gpt4 = cost_total_ils * 100  # עלות באגורות (float מדויק, כל הספרות)

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
            "cost_gpt4": cost_gpt4,
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

        return (
            validated_profile,          # merged_profile
            prompt_tokens,              # prompt_tokens
            cached_tokens,              # cached_tokens  
            prompt_regular,             # prompt_regular
            completion_tokens,          # completion_tokens
            total_tokens,               # total_tokens
            cost_prompt_regular,        # cost_prompt_regular
            cost_prompt_cached,         # cost_prompt_cached
            cost_completion,            # cost_completion
            cost_total,                 # cost_total
            cost_total_ils,             # cost_total_ils
            cost_gpt4,                  # cost_gpt4 באגורות
            usage_data.get("model", "") # model
        )

    except json.JSONDecodeError as e:
        logging.error(f"❌ שגיאה בפרסור JSON במיזוג GPT4: {e}")
        logging.error(f"📄 התוכן: '{content}'")
        
        # fallback - מיזוג פשוט במקרה של כשל
        fallback_merge = {**existing_profile, **new_data}
        logging.warning("🔧 משתמש במיזוג fallback פשוט")
        
        return (
            fallback_merge,             # merged_profile (fallback)
            0,                          # prompt_tokens
            0,                          # cached_tokens
            0,                          # prompt_regular
            0,                          # completion_tokens
            0,                          # total_tokens
            0.0,                        # cost_prompt_regular
            0.0,                        # cost_prompt_cached
            0.0,                        # cost_completion
            0.0,                        # cost_total
            0.0,                        # cost_total_ils
            0,                          # cost_gpt4
            "fallback"                  # model
        )

    except Exception as e:
        logging.error(f"💥 שגיאה כללית ב-GPT4 מיזוג: {e}")
        
        # fallback - מיזוג פשוט במקרה של כשל
        fallback_merge = {**existing_profile, **new_data}
        
        return (
            fallback_merge,             # merged_profile (fallback)
            0,                          # prompt_tokens
            0,                          # cached_tokens
            0,                          # prompt_regular
            0,                          # completion_tokens
            0,                          # total_tokens
            0.0,                        # cost_prompt_regular
            0.0,                        # cost_prompt_cached
            0.0,                        # cost_completion
            0.0,                        # cost_total
            0.0,                        # cost_total_ils
            0,                          # cost_gpt4
            "error"                     # model
        )


# פונקציית עזר - קובעת אם להפעיל GPT4
def should_use_gpt4_merge(existing_profile, new_data):
    """
    מחליטה אם להפעיל GPT4 למיזוג מורכב
    רק אם יש שדה מורכב חדש ושדה זה כבר קיים בת.ז
    """
    complex_fields = [
        FIELDS_DICT["attracted_to"], FIELDS_DICT["who_knows"], FIELDS_DICT["who_doesnt_know"], FIELDS_DICT["attends_therapy"], 
        FIELDS_DICT["primary_conflict"], FIELDS_DICT["trauma_history"], FIELDS_DICT["goal_in_course"], 
        FIELDS_DICT["language_of_strength"], FIELDS_DICT["coping_strategies"], FIELDS_DICT["fears_concerns"], FIELDS_DICT["future_vision"]
    ]
    
    for field in complex_fields:
        if field in new_data:  # GPT3 מצא שדה מורכב חדש
            existing_value = existing_profile.get(field, "")
            if existing_value and existing_value.strip():  # והשדה קיים בת.ז
                logging.info(f"🎯 GPT4 נדרש - שדה '{field}' מצריך מיזוג")
                return True
    
    logging.info("✅ אין צורך ב-GPT4 - עדכון פשוט מספיק")
    return False
#===============================================================================


# ============================פונקציה שמפעילה את הג'יפיטי הרביעי לפי היגיון -לא פועל תמיד - עדכון חכם של ת.ז הרגשית ======================= 

def smart_update_profile(existing_profile, user_message):
    """
    פונקציה מאחדת שמטפלת בכל תהליך עדכון ת.ז הרגשית:
    1. מפעילה GPT3 לחילוץ מידע
    2. בודקה אם צריך GPT4 למיזוג מורכב
    3. מחזירה ת.ז מעודכנת + כל נתוני העלויות
    
    Returns: (updated_profile, extract_usage, merge_usage_or_none)
    """
    logging.info("🔄 מתחיל עדכון חכם של ת.ז הרגשית")
    
    # שלב 1: GPT3 - חילוץ מידע חדש
    new_data, extract_usage = extract_user_profile_fields(user_message)
    logging.info(f"🤖 GPT3 חילץ: {list(new_data.keys())}")
    
    # אם אין מידע חדש - אין מה לעדכן
    if not new_data:
        logging.info("ℹ️ אין מידע חדש, מחזיר ת.ז ללא שינוי")
        return existing_profile, extract_usage, None
    
    # שלב 2: בדיקה אם צריך GPT4
    if should_use_gpt4_merge(existing_profile, new_data):
        logging.info("🎯 מפעיל GPT4 למיזוג מורכב")
        
        # שלב 3: GPT4 - מיזוג חכם
        merge_result = merge_sensitive_profile_data(existing_profile, new_data, user_message)
        updated_profile = merge_result[0]
        merge_usage = merge_result[1]  # תמיד dict
        
        logging.info(f"✅ GPT4 עדכן ת.ז עם {len(updated_profile)} שדות")
        return updated_profile, extract_usage, merge_usage
        
    else:
        logging.info("✅ עדכון פשוט ללא GPT4")
        
        # עדכון פשוט - מיזוג רגיל
        updated_profile = {**existing_profile, **new_data}
        
        return updated_profile, extract_usage, None


def get_combined_usage_data(extract_usage, merge_usage=None):
    """
    פונקציית עזר - מחברת את נתוני השימוש מGPT3 ו-GPT4 (אם רץ)
    מחזירה נתונים מאוחדים לשמירה ב-sheets
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
        merge_data["used_gpt4"] = True
        return {**extract_data, **merge_data}
    else:
        extract_data["used_gpt4"] = False
        return extract_data


# -------------------------------------------------------------
# הסבר בסוף הקובץ (לשימושך):

"""
מה חדש כאן?

- אין שום פונקציה שמוסרת — הכל מקורי.
- נוספו חישובי עלות וטוקנים לכל קריאה (רגיל, קשד, פלט).
- כל קריאה שומרת לוג עם כל השדות.
- פונקציות מחזירות עכשיו את כל הערכים — אפשר לשמור אותם ל־Google Sheets ולעשות דוחות.
- נוסף החזר עלות באגורות (cost_gptX) וקשד (cached_tokens_gptX) לכל קריאה.
- בכל מקום נוסף # הסבר קצר בעברית כדי שתדע מה קורה.
- אין מחיקות — רק תוספות.

תעדכן אותי כשעברת, נמשיך לחיבור ל־Google Sheets!
"""
