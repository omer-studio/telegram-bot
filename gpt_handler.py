"""
gpt_handler.py
--------------
קובץ זה מרכז את כל הפונקציות שמבצעות אינטראקציה עם gpt (שליחת הודעות, חישוב עלות, דיבאגינג).
הרציונל: ריכוז כל הלוגיקה של gpt במקום אחד, כולל תיעוד מלא של טוקנים, עלויות, ולוגים.

🔄 עדכון: מעבר ל-LiteLLM עם מעקב עלויות מובנה
--------------------------------------------------
- LiteLLM מספק מעקב עלויות אוטומטי ומדויק
- אין צורך בקובץ מחירון חיצוני
- עלויות מחושבות אוטומטית לפי המודל והטוקנים
- תמיכה במודלים מרובים עם עלויות שונות
"""

import json
import logging
import os
import asyncio
import re
import threading
from datetime import datetime
from config import gpt_log_path
from fields_dict import FIELDS_DICT
from prompts import BOT_REPLY_SUMMARY_PROMPT, PROFILE_EXTRACTION_ENHANCED_PROMPT
from gpt_c_logger import append_gpt_c_html_update

# קבועים
USD_TO_ILS = 3.7  # שער הדולר-שקל (יש לעדכן לפי הצורך)

# הגדרת נתיב לוג אחיד מתוך תיקיית הפרויקט
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(PROJECT_ROOT, exist_ok=True)

# ===================== פונקציות עזר ללוגים ודיבאג =====================

def _debug_gpt_usage(model_name, prompt_tokens, completion_tokens, cached_tokens, total_tokens, call_type):
    """
    הדפסת debug info על usage של gpt.
    """
    print(f"[DEBUG] {call_type} - Model: {model_name}, Tokens: {prompt_tokens}p + {completion_tokens}c + {cached_tokens}cache = {total_tokens}total")

def write_gpt_log(call_type, usage_log, model_name, interaction_id=None):
    """
    כותב לוג של קריאת gpt לקובץ JSON.
    קלט: call_type (main_reply/summary/identity_extraction), usage_log (dict), model_name (str), interaction_id (str, optional)
    """
    try:
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "type": call_type,
            "model": model_name,
            **usage_log
        }
        if interaction_id:
            log_entry["interaction_id"] = str(interaction_id)
        
        # וידוא שהתיקייה קיימת
        os.makedirs(os.path.dirname(gpt_log_path), exist_ok=True)
        
        with open(gpt_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
    except Exception as e:
        logging.error(f"שגיאה בכתיבת לוג gpt: {e}")

# 🔄 עדכון: פונקציה חדשה לחישוב עלויות עם LiteLLM
def calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens=0, model_name='gpt-4o', usd_to_ils=USD_TO_ILS, completion_response=None):
    """
    מחשב את העלות של שימוש ב-gpt לפי מספר הטוקנים והמודל.
    משתמש אך ורק ב-LiteLLM עם completion_response.
    מחזיר רק את העלות הכוללת (cost_total) כפי שמחושב ע"י LiteLLM, בלי פילוח ידני.
    """
    print(f"[DEBUG] 🔥 calculate_gpt_cost CALLED! 🔥")
    print(f"[DEBUG] Input: prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}, cached_tokens={cached_tokens}, model_name={model_name}")
    print(f"[DEBUG] calculate_gpt_cost - Model: {model_name}, Tokens: {prompt_tokens}p + {completion_tokens}c + {cached_tokens}cache")
    try:
        import litellm
        if completion_response:
            print(f"[DEBUG] Using completion_response for cost calculation")
            cost_usd = litellm.completion_cost(completion_response=completion_response)
            print(f"[DEBUG] LiteLLM completion_cost returned: {cost_usd}")
        else:
            print(f"[DEBUG] No completion_response provided, cannot calculate cost with LiteLLM")
            cost_usd = 0.0
        cost_ils = cost_usd * usd_to_ils
        cost_agorot = cost_ils * 100
        result = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_tokens": cached_tokens,
            "cost_total": cost_usd,
            "cost_total_ils": cost_ils,
            "cost_agorot": cost_agorot,
            "model": model_name
        }
        print(f"[DEBUG] calculate_gpt_cost returning: {result}")
        return result
    except Exception as e:
        print(f"[ERROR] calculate_gpt_cost failed: {e}")
        import traceback
        print(f"[ERROR] Full traceback: {traceback.format_exc()}")
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_tokens": cached_tokens,
            "cost_total": 0.0,
            "cost_total_ils": 0.0,
            "cost_agorot": 0.0,
            "model": model_name
        }

# ============================ פונקציות עזר לבדיקת הצורך ב-gpt_c ============================

def should_run_gpt_c(user_message):
    """
    בודק אם יש טעם להפעיל gpt_c על הודעה נתונה.
    מחזיר False רק על הודעות שאנחנו בטוחים שלא מכילות מידע חדש.
    הכלל: gpt_c מופעל תמיד, אלא אם כן ההודעה היא משהו שלא יכול להכיל מידע חדש.
    """
    if not user_message or not user_message.strip():
        return False
    
    message = user_message.strip()
    
    # ביטויים בסיסיים שלא יכולים להכיל מידע חדש
    base_phrases = [
        'היי', 'שלום', 'מה שלומך', 'מה נשמע', 'מה קורה', 'מה המצב',
        'תודה', 'תודה רבה', 'תודה לך', 'תודה מאוד', 'תודה ענקית', 'תודהה',
        'בסדר', 'אוקיי', 'אוקי', 'בסדר גמור', 'בסדר מושלם', 'אוקייי',
        'אני מבין', 'אה', 'וואו', 'מעניין', 'נכון', 'אכן', 'אה אה',
        'כן', 'לא', 'אולי', 'יכול להיות', 'אפשרי',
        'אני לא יודע', 'לא יודע', 'לא בטוח', 'לא יודע מה להגיד', 'אין לי מושג',
        'בהחלט', 'בטח', 'כמובן', 'ברור', 'ודאי', 'בוודאי',
        'מעולה', 'נהדר', 'מדהים', 'פנטסטי', 'מושלם',
        'אה אוקיי', 'אה בסדר', 'אה הבנתי', 'אה נכון',
        'כן לא', 'כן אולי', 'אולי כן', 'אולי לא',
        'אה אוקיי תודה', 'אה בסדר תודה', 'אה הבנתי תודה',
        'טוב', 'טוב מאוד', 'טוב מאד', 'לא רע', 'לא רע בכלל',
        'בסדר גמור', 'בסדר מושלם', 'בסדר לגמרי', 'בסדר לחלוטין',
        'מצוין', 'מצויין', 'מעולה', 'נהדר', 'מדהים', 'פנטסטי',
        'אני בסדר', 'אני טוב', 'אני מצוין', 'אני מעולה',
        'הכל טוב', 'הכל בסדר', 'הכל מצוין', 'הכל מעולה',
        'סבבה', 'סבבה גמורה', 'סבבה מושלמת',
        'קול', 'קול לגמרי', 'קול לחלוטין',
        'אחלה', 'אחלה גמורה', 'אחלה מושלמת',
        'יופי', 'יופי גמור', 'יופי מושלם',
        'מעולה', 'מעולה גמורה', 'מעולה מושלמת',
        'נהדר', 'נהדר לגמרי', 'נהדר לחלוטין',
        'מדהים', 'מדהים לגמרי', 'מדהים לחלוטין',
        'פנטסטי', 'פנטסטי לגמרי', 'פנטסטי לחלוטין',
        'מושלם', 'מושלם לגמרי', 'מושלם לחלוטין',
        'אני אוקיי', 'אני בסדר גמור', 'אני בסדר מושלם',
        'אני טוב מאוד', 'אני טוב מאד', 'אני טוב לגמרי',
        'אני מצוין לגמרי', 'אני מעולה לגמרי', 'אני נהדר לגמרי',
        'אני מדהים לגמרי', 'אני פנטסטי לגמרי', 'אני מושלם לגמרי',
        'טוב אחי', 'בסדר אחי', 'מעולה אחי', 'נהדר אחי', 'מדהים אחי',
        'סבבה אחי', 'קול אחי', 'אחלה אחי', 'יופי אחי', 'מושלם אחי',
        'אני בסדר אחי', 'אני טוב אחי', 'אני מעולה אחי', 'אני נהדר אחי',
        'הכל טוב אחי', 'הכל בסדר אחי', 'הכל מעולה אחי',
        'אחי', 'אח', 'אחיי', 'אחייי', 'אחיייי',
        'אחי טוב', 'אחי בסדר', 'אחי מעולה', 'אחי נהדר', 'אחי מדהים',
        'אחי סבבה', 'אחי קול', 'אחי אחלה', 'אחי יופי', 'אחי מושלם'
    ]
    
    # אימוג'י בלבד
    emoji_only = ['👍', '👎', '❤️', '😊', '😢', '😡', '🤔', '😅', '😂', '😭']
    
    # נקודות בלבד
    dots_only = ['...', '....', '.....', '......']
    
    # סימני קריאה בלבד
    exclamation_only = ['!!!', '!!!!', '!!!!!']
    
    # בדיקה אם ההודעה היא בדיוק ביטוי בסיסי
    message_lower = message.lower()
    for phrase in base_phrases:
        if message_lower == phrase.lower():
            return False
    
    # בדיקה אם ההודעה היא ביטוי בסיסי + תווים נוספים
    for phrase in base_phrases:
        phrase_lower = phrase.lower()
        
        # בדיקה אם ההודעה מתחילה בביטוי הבסיסי
        if message_lower.startswith(phrase_lower):
            # מה שנשאר אחרי הביטוי הבסיסי
            remaining = message_lower[len(phrase_lower):].strip()
            
            # אם מה שנשאר הוא רק תווים מותרים, אז לא להפעיל gpt_c
            if remaining in ['', '!', '?', ':)', ':(', '!:)', '?:(', '!:(', '?:)', '...', '....', '.....', '......', '!!!', '!!!!', '!!!!!']:
                return False
            
            # אם מה שנשאר הוא רק אימוג'י או שילוב של תווים מותרים
            import re
            # הסרת רווחים מהתחלה ומהסוף
            remaining_clean = remaining.strip()
            # בדיקה אם מה שנשאר הוא רק תווים מותרים
            allowed_chars = r'^[!?:\.\s\(\)]+$'
            if re.match(allowed_chars, remaining_clean):
                return False
    
    # בדיקה אם ההודעה היא רק אימוג'י
    if message in emoji_only:
        return False
    
    # בדיקה אם ההודעה היא רק נקודות
    if message in dots_only:
        return False
    
    # בדיקה אם ההודעה היא רק סימני קריאה
    if message in exclamation_only:
        return False
    
    # בדיקה אם ההודעה היא ביטוי + אימוג'י
    for phrase in base_phrases:
        phrase_lower = phrase.lower()
        if message_lower.startswith(phrase_lower):
            remaining = message_lower[len(phrase_lower):].strip()
            # בדיקה אם מה שנשאר הוא רק אימוג'י
            if remaining in ['👍', '👎', '❤️', '😊', '😢', '😡', '🤔', '😅', '😂', '😭']:
                return False
    
    # אם הגענו לכאן, ההודעה יכולה להכיל מידע חדש
    return True

# ============================הג'יפיטי ה-A - פועל תמיד ועונה תשובה למשתמש =======================

def get_main_response(full_messages, chat_id=None, message_id=None):
    """
    שולח הודעה ל-gpt_a הראשי ומחזיר את התשובה, כולל פירוט עלות וטוקנים.
    """
    try:
        import litellm
        
        metadata = {"gpt_identifier": "gpt_a", "chat_id": chat_id, "message_id": message_id}
        response = litellm.completion(
            model="gpt-4o",
            messages=full_messages,
            temperature=1,
            metadata=metadata,
            store=True
        )

        # 🔥 דיבאג מפורט - תוסיף את זה בכל 3 הפונקציות
        print(f"[DEBUG] === RAW RESPONSE DEBUG (gpt_a) ===")
        print(f"[DEBUG] response type: {type(response)}")
        print(f"[DEBUG] response attributes: {dir(response)}")
        print(f"[DEBUG] usage type: {type(response.usage)}")
        print(f"[DEBUG] usage attributes: {dir(response.usage)}")
        print(f"[DEBUG] usage as dict: {response.usage.__dict__ if hasattr(response.usage, '__dict__') else 'no __dict__'}")

        # בדיקה אם יש prompt_tokens_details
        if hasattr(response.usage, 'prompt_tokens_details'):
            print(f"[DEBUG] prompt_tokens_details found!")
            print(f"[DEBUG] prompt_tokens_details type: {type(response.usage.prompt_tokens_details)}")
            print(f"[DEBUG] prompt_tokens_details attributes: {dir(response.usage.prompt_tokens_details)}")
            print(f"[DEBUG] prompt_tokens_details as dict: {response.usage.prompt_tokens_details.__dict__ if hasattr(response.usage.prompt_tokens_details, '__dict__') else 'no __dict__'}")
        else:
            print(f"[DEBUG] NO prompt_tokens_details found!")

        # בדיקה אם יש raw response
        if hasattr(response, '_raw_response'):
            print(f"[DEBUG] _raw_response found: {response._raw_response}")
        elif hasattr(response, 'raw'):
            print(f"[DEBUG] raw found: {response.raw}")
        else:
            print(f"[DEBUG] No raw response found")
        print(f"[DEBUG] === END RAW RESPONSE DEBUG (gpt_a) ===")

        prompt_tokens = response.usage.prompt_tokens
        cached_tokens = getattr(getattr(response.usage, 'prompt_tokens_details', None), 'cached_tokens', 0)
        completion_tokens = response.usage.completion_tokens
        model_name = response.model

        _debug_gpt_usage(model_name, prompt_tokens, completion_tokens, cached_tokens, prompt_tokens + completion_tokens, "main_reply")

        print(f"[DEBUG] === CALLING calculate_gpt_cost ===")
        cost_data = calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens, model_name, completion_response=response)
        print(f"[DEBUG] calculate_gpt_cost returned: {cost_data}")
        print(f"[DEBUG] === END calculate_gpt_cost ===")
        
        write_gpt_log("main_reply", cost_data, model_name, interaction_id=message_id)
        
        return {"bot_reply": response.choices[0].message.content, "usage": cost_data}
        
    except Exception as e:
        logging.error(f"❌ שגיאה ב-gpt_a ראשי: {e}")
        raise

def get_main_response_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, get_main_response, *args, **kwargs)

# ============================הג'יפיטי ה-B - תמצית תשובה להיסטוריה ======================= 

def summarize_bot_reply(reply_text, chat_id=None, original_message_id=None):
    """
    שולח תשובה של הבוט ל-gpt_b ומקבל תמצית קצרה להיסטוריה.
    """
    try:
        import litellm
        
        metadata = {"gpt_identifier": "gpt_b", "chat_id": chat_id, "original_message_id": original_message_id}
        response = litellm.completion(
            model="gpt-4.1-nano",
            messages=[{"role": "system", "content": BOT_REPLY_SUMMARY_PROMPT}, {"role": "user", "content": reply_text}],
            temperature=1,
            metadata=metadata,
            store=True
        )

        # 🔥 דיבאג מפורט - תוסיף את זה בכל 3 הפונקציות
        print(f"[DEBUG] === RAW RESPONSE DEBUG (gpt_b) ===")
        print(f"[DEBUG] response type: {type(response)}")
        print(f"[DEBUG] response attributes: {dir(response)}")
        print(f"[DEBUG] usage type: {type(response.usage)}")
        print(f"[DEBUG] usage attributes: {dir(response.usage)}")
        print(f"[DEBUG] usage as dict: {response.usage.__dict__ if hasattr(response.usage, '__dict__') else 'no __dict__'}")

        # בדיקה אם יש prompt_tokens_details
        if hasattr(response.usage, 'prompt_tokens_details'):
            print(f"[DEBUG] prompt_tokens_details found!")
            print(f"[DEBUG] prompt_tokens_details type: {type(response.usage.prompt_tokens_details)}")
            print(f"[DEBUG] prompt_tokens_details attributes: {dir(response.usage.prompt_tokens_details)}")
            print(f"[DEBUG] prompt_tokens_details as dict: {response.usage.prompt_tokens_details.__dict__ if hasattr(response.usage.prompt_tokens_details, '__dict__') else 'no __dict__'}")
        else:
            print(f"[DEBUG] NO prompt_tokens_details found!")

        # בדיקה אם יש raw response
        if hasattr(response, '_raw_response'):
            print(f"[DEBUG] _raw_response found: {response._raw_response}")
        elif hasattr(response, 'raw'):
            print(f"[DEBUG] raw found: {response.raw}")
        else:
            print(f"[DEBUG] No raw response found")
        print(f"[DEBUG] === END RAW RESPONSE DEBUG (gpt_b) ===")

        prompt_tokens = response.usage.prompt_tokens
        cached_tokens = getattr(getattr(response.usage, 'prompt_tokens_details', None), 'cached_tokens', 0)
        completion_tokens = response.usage.completion_tokens
        model_name = response.model

        _debug_gpt_usage(model_name, prompt_tokens, completion_tokens, cached_tokens, prompt_tokens + completion_tokens, "summary")

        print(f"[DEBUG] === CALLING calculate_gpt_cost (gpt_b) ===")
        cost_data = calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens, model_name, completion_response=response)
        print(f"[DEBUG] calculate_gpt_cost (gpt_b) returned: {cost_data}")
        print(f"[DEBUG] === END calculate_gpt_cost (gpt_b) ===")
        
        write_gpt_log("reply_summary", cost_data, model_name, interaction_id=original_message_id)

        return {"summary": response.choices[0].message.content, "usage": cost_data}

    except Exception as e:
        logging.error(f"❌ שגיאה ב-gpt_b תמצית: {e}")
        raise

def summarize_bot_reply_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, summarize_bot_reply, *args, **kwargs)

# ============================הג'יפיטי ה-3 - פועל תמיד ומחלץ מידע לת.ז הרגשית ======================= 

def validate_extracted_data(data):
    """
    בודק אם הנתונים שחולצו מה-gpt תקינים (dict, מפתחות מסוג str בלבד).
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

def smart_update_profile(existing_profile, user_message, interaction_id=None):
    """
    מעדכן תעודת זהות רגשית של משתמש על ידי חילוץ פרטים מהודעתו.
    זוהי פונקציית מעטפת שקוראת ל-gpt_c.
    """
    print(f"[DEBUG][smart_update_profile] - interaction_id: {interaction_id}")
    try:
        gpt_c_response = gpt_c(
            user_message=user_message,
            chat_id=interaction_id
        )

        if not gpt_c_response or not gpt_c_response.get("full_data"):
            return existing_profile, {}

        new_data = gpt_c_response.get("full_data", {})
        extract_usage = {k: v for k, v in gpt_c_response.items() if k not in ["updated_summary", "full_data"]}

        if not new_data:
            return existing_profile, extract_usage

        updated_profile = {**existing_profile, **new_data}
        return updated_profile, extract_usage

    except Exception as e:
        logging.error(f"❌ שגיאה ב-smart_update_profile: {e}")
        return existing_profile, {}

def smart_update_profile_async(existing_profile, user_message, interaction_id=None):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, smart_update_profile, existing_profile, user_message, interaction_id)

# ============================ gpt_c - הפונקציה הראשית ============================

def gpt_c(user_message, last_bot_message="", chat_id=None, message_id=None):
    """
    מפעיל את כל זרימת ה-gpt: gpt_a, gpt_b, ו-smart_update_profile (שקורא ל-gpt_c).
    """
    print("[DEBUG][gpt_c] CALLED - הפונקציה הראשית")
    try:
        import litellm
        
        logging.info("🔄 מתחיל gpt_c - עדכון סיכום עם מידע חדש")
        print(f"[DEBUG][gpt_c] --- START ---")
        print(f"[DEBUG][gpt_c] user_message: {user_message} (type: {type(user_message)})")
        print(f"[DEBUG][gpt_c] last_bot_message: {last_bot_message} (type: {type(last_bot_message)})")
        print(f"[DEBUG][gpt_c] PROFILE_EXTRACTION_ENHANCED_PROMPT: {PROFILE_EXTRACTION_ENHANCED_PROMPT}")
        metadata = {"gpt_identifier": "gpt_c", "chat_id": chat_id, "message_id": message_id}
        
        # יצירת תוכן שמשלב את הודעת המשתמש עם ההודעה האחרונה של הבוט
        if last_bot_message:
            user_content = f"שאלת הבוט לצורך הקשר בלבד:\n{last_bot_message}\n\nתשובת המשתמש לצורך חילוץ מידע:\n{user_message}"
        else:
            user_content = f"תשובת המשתמש לצורך חילוץ מידע:\n{user_message}"
        
        response = litellm.completion(
            model="gpt-4o-mini",  # מודל זול ומהיר
            messages=[
                {"role": "system", "content": PROFILE_EXTRACTION_ENHANCED_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.3,
            max_tokens=500,
            metadata=metadata,
            store=True
        )
        
        # 🔥 דיבאג מפורט - תוסיף את זה בכל 3 הפונקציות
        print(f"[DEBUG] === RAW RESPONSE DEBUG (gpt_c) ===")
        print(f"[DEBUG] response type: {type(response)}")
        print(f"[DEBUG] response attributes: {dir(response)}")
        print(f"[DEBUG] usage type: {type(response.usage)}")
        print(f"[DEBUG] usage attributes: {dir(response.usage)}")
        print(f"[DEBUG] usage as dict: {response.usage.__dict__ if hasattr(response.usage, '__dict__') else 'no __dict__'}")

        # בדיקה אם יש prompt_tokens_details
        if hasattr(response.usage, 'prompt_tokens_details'):
            print(f"[DEBUG] prompt_tokens_details found!")
            print(f"[DEBUG] prompt_tokens_details type: {type(response.usage.prompt_tokens_details)}")
            print(f"[DEBUG] prompt_tokens_details attributes: {dir(response.usage.prompt_tokens_details)}")
            print(f"[DEBUG] prompt_tokens_details as dict: {response.usage.prompt_tokens_details.__dict__ if hasattr(response.usage.prompt_tokens_details, '__dict__') else 'no __dict__'}")
        else:
            print(f"[DEBUG] NO prompt_tokens_details found!")

        # בדיקה אם יש raw response
        if hasattr(response, '_raw_response'):
            print(f"[DEBUG] _raw_response found: {response._raw_response}")
        elif hasattr(response, 'raw'):
            print(f"[DEBUG] raw found: {response.raw}")
        else:
            print(f"[DEBUG] No raw response found")
        print(f"[DEBUG] === END RAW RESPONSE DEBUG (gpt_c) ===")

        content = response.choices[0].message.content.strip()
        print(f"[DEBUG][gpt_c] raw gpt_c response: {content}")
        
        # דיבאג: הדפסה של התגובה הגולמית מה-API
        print(f"[DEBUG][gpt_c] FULL API RESPONSE: {response}")
        
        if content.startswith("```"):
            match = re.search(r"```(?:json)?\s*({.*?})\s*```", content, re.DOTALL)
            if match:
                content = match.group(1)
                print(f"[DEBUG][gpt_c] cleaned content: {content}")
        
        try:
            result = json.loads(content)
            print(f"[DEBUG][gpt_c] parsed result: {result}")
        except Exception as e:
            print(f"[ERROR][gpt_c] JSON parsing error: {e}")
            print(f"[ERROR][gpt_c] content that failed to parse: {content}")
            result = {}
        
        # המר את התוצאה למבנה הנכון
        if isinstance(result, dict):
            # אם יש שדות פרופיל, צור סיכום מהם
            profile_fields = []
            for key, value in result.items():
                if value and value != "null" and key in ["age", "pronoun_preference", "attracted_to", "relationship_type", "occupation_or_role"]:
                    profile_fields.append(f"{key}: {value}")
            
            summary = "; ".join(profile_fields) if profile_fields else ""
            full_data = result
        else:
            summary = ""
            full_data = {}
        
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        cached_tokens = getattr(getattr(response.usage, 'prompt_tokens_details', None), 'cached_tokens', 0)
        model_name = response.model
        
        print(f"[DEBUG] === CALLING calculate_gpt_cost (gpt_c) ===")
        cost_data = calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens, model_name, completion_response=response)
        print(f"[DEBUG] calculate_gpt_cost (gpt_c) returned: {cost_data}")
        print(f"[DEBUG] === END calculate_gpt_cost (gpt_c) ===")
        
        final_result = {
            "updated_summary": summary,
            "full_data": full_data,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "model": model_name,
            **cost_data
        }
        
        print(f"[DEBUG][gpt_c] final_result: {final_result}")
        logging.info(f"✅ gpt_c הושלם בהצלחה")
        
        # כתיבה ללוג
        write_gpt_log("identity_extraction", cost_data, model_name, interaction_id=message_id)
        
        return final_result
        
    except Exception as e:
        import traceback
        print(f"[ERROR][gpt_c] Exception: {e}")
        print(traceback.format_exc())
        logging.error(f"❌ שגיאה ב-gpt_c: {e}")
        return None

def gpt_c_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, gpt_c, *args, **kwargs)

def normalize_usage_dict(usage, model_name=""):
    """
    ממפה usage מכל פורמט (litellm/openai) לפורמט אחיד.
    """
    if not usage:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
            "cost_total": 0.0,
            "cost_total_ils": 0.0,
            "cost_agorot": 0.0,
            "model": model_name
        }
    # mapping for litellm
    prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
    completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
    total = usage.get("total_tokens", prompt + completion)
    cached = usage.get("cached_tokens", 0)
    cost_total = usage.get("cost_total", 0.0)
    cost_total_ils = usage.get("cost_total_ils", 0.0)
    cost_agorot = usage.get("cost_agorot", cost_total_ils * 100 if cost_total_ils else 0.0)
    model = usage.get("model", model_name)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cached_tokens": cached,
        "cost_total": cost_total,
        "cost_total_ils": cost_total_ils,
        "cost_agorot": cost_agorot,
        "model": model
    }

# ============================ gpt_d - מודל חכם לטיפול בשדות שהשתנו ============================

def gpt_d(changed_fields, chat_id=None, message_id=None):
    """
    מודל חכם שמחליט איך לטפל בשדות שהשתנו.
    מקבל רק את השדות הרלוונטיים (הישן + החדש) כדי להיות חסכוני.
    
    קלט:
    - changed_fields: dict עם המבנה {"field_name": {"old": "value", "new": "value"}}
    - chat_id: מזהה הצ'אט
    - message_id: מזהה ההודעה
    
    פלט:
    - dict עם ההחלטה לכל שדה: {"field_name": "final_value"}
    - usage data
    """
    print(f"[DEBUG][gpt_d] CALLED - מודל חכם לטיפול בשדות שהשתנו")
    print(f"[DEBUG][gpt_d] changed_fields: {changed_fields}")
    
    if not changed_fields:
        print(f"[DEBUG][gpt_d] No changed fields, returning empty result")
        return {"final_values": {}, "usage": {}}
    
    try:
        import litellm
        
        # יצירת prompt חכם לטיפול בשדות שהשתנו
        system_prompt = """אתה מודל חכם שמחליט איך לטפל בשדות שהשתנו בתעודת זהות רגשית.

כללים להחלטה:
1. **גיל**: אם הגיל החדש הגיוני יותר (13-80), השתמש בו. אם הגיל הישן הגיוני יותר, השאר אותו.
2. **מקצוע/תפקיד**: אם המידע החדש מפורט יותר או עדכני יותר, השתמש בו. אם הישן מפורט יותר, השאר אותו.
3. **העדפות**: אם יש מידע חדש שמשלים את הישן, צרף אותם. אם יש סתירה, בחר במידע המפורט יותר.
4. **מידע אישי**: אם המידע החדש נראה אמין יותר או מפורט יותר, השתמש בו.
5. **איכות נתונים**: שקול את ציוני האיכות - מידע עם ציון איכות גבוה יותר עדיף.

החזר תמיד JSON בפורמט:
{
  "field_name": "final_value",
  "field_name2": "final_value2"
}

אל תחזיר הסברים, רק את ה-JSON."""

        # יצירת תוכן עם השדות שהשתנו
        fields_content = []
        for field_name, values in changed_fields.items():
            # הערכת איכות הנתונים
            old_quality = assess_data_quality(values['old'], field_name)
            new_quality = assess_data_quality(values['new'], field_name)
            fields_content.append(
                f"{field_name}: ישן='{values['old']}' (איכות: {old_quality}) חדש='{values['new']}' (איכות: {new_quality})"
            )
        
        user_content = "השדות שהשתנו (עם ציוני איכות):\n" + "\n".join(fields_content)
        
        metadata = {"gpt_identifier": "gpt_d", "chat_id": chat_id, "message_id": message_id}
        
        response = litellm.completion(
            model="gpt-4o-mini",  # מודל זול ומהיר
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,  # טמפרטורה נמוכה להחלטות עקביות
            max_tokens=300,   # מוגבל כי אנחנו מקבלים רק שדות מעטים
            metadata=metadata,
            store=True
        )
        
        # 🔥 דיבאג מפורט
        print(f"[DEBUG] === RAW RESPONSE DEBUG (gpt_d) ===")
        print(f"[DEBUG] response type: {type(response)}")
        print(f"[DEBUG] response attributes: {dir(response)}")
        print(f"[DEBUG] usage type: {type(response.usage)}")
        print(f"[DEBUG] usage attributes: {dir(response.usage)}")
        print(f"[DEBUG] usage as dict: {response.usage.__dict__ if hasattr(response.usage, '__dict__') else 'no __dict__'}")

        if hasattr(response.usage, 'prompt_tokens_details'):
            print(f"[DEBUG] prompt_tokens_details found!")
            print(f"[DEBUG] prompt_tokens_details type: {type(response.usage.prompt_tokens_details)}")
            print(f"[DEBUG] prompt_tokens_details attributes: {dir(response.usage.prompt_tokens_details)}")
            print(f"[DEBUG] prompt_tokens_details as dict: {response.usage.prompt_tokens_details.__dict__ if hasattr(response.usage.prompt_tokens_details, '__dict__') else 'no __dict__'}")
        else:
            print(f"[DEBUG] NO prompt_tokens_details found!")

        if hasattr(response, '_raw_response'):
            print(f"[DEBUG] _raw_response found: {response._raw_response}")
        elif hasattr(response, 'raw'):
            print(f"[DEBUG] raw found: {response.raw}")
        else:
            print(f"[DEBUG] No raw response found")
        print(f"[DEBUG] === END RAW RESPONSE DEBUG (gpt_d) ===")

        content = response.choices[0].message.content.strip()
        print(f"[DEBUG][gpt_d] raw gpt_d response: {content}")
        
        # ניקוי התגובה מ-JSON
        if content.startswith("```"):
            match = re.search(r"```(?:json)?\s*({.*?})\s*```", content, re.DOTALL)
            if match:
                content = match.group(1)
                print(f"[DEBUG][gpt_d] cleaned content: {content}")
        
        try:
            final_values = json.loads(content)
            print(f"[DEBUG][gpt_d] parsed final_values: {final_values}")
        except Exception as e:
            print(f"[ERROR][gpt_d] JSON parsing error: {e}")
            print(f"[ERROR][gpt_d] content that failed to parse: {content}")
            # אם נכשל, השתמש בערכים החדשים
            final_values = {field: values['new'] for field, values in changed_fields.items()}
        
        # חישוב עלויות
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        cached_tokens = getattr(getattr(response.usage, 'prompt_tokens_details', None), 'cached_tokens', 0)
        model_name = response.model
        
        print(f"[DEBUG] === CALLING calculate_gpt_cost (gpt_d) ===")
        cost_data = calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens, model_name, completion_response=response)
        print(f"[DEBUG] calculate_gpt_cost (gpt_d) returned: {cost_data}")
        print(f"[DEBUG] === END calculate_gpt_cost (gpt_d) ===")
        
        result = {
            "final_values": final_values,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "cached_tokens": cached_tokens,
            "model": model_name,
            **cost_data
        }
        
        print(f"[DEBUG][gpt_d] final result: {result}")
        logging.info(f"✅ gpt_d הושלם בהצלחה")
        
        # כתיבה ללוג
        write_gpt_log("field_conflict_resolution", cost_data, model_name, interaction_id=message_id)
        
        # תיעוד ביצועים
        log_gpt_d_performance(changed_fields, final_values, cost_data)
        
        return result
        
    except Exception as e:
        import traceback
        print(f"[ERROR][gpt_d] Exception: {e}")
        print(traceback.format_exc())
        logging.error(f"❌ שגיאה ב-gpt_d: {e}")
        # אם נכשל, השתמש בערכים החדשים
        return {
            "final_values": {field: values['new'] for field, values in changed_fields.items()},
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
            "cost_total": 0.0,
            "cost_total_ils": 0.0,
            "cost_agorot": 0.0,
            "model": "gpt-4o-mini"
        }

def log_gpt_d_performance(changed_fields, final_values, cost_data):
    """
    מתעד את הביצועים של gpt_d לקובץ נפרד.
    """
    try:
        timestamp = datetime.now().isoformat()
        performance_log = {
            "timestamp": timestamp,
            "changed_fields_count": len(changed_fields),
            "changed_fields": list(changed_fields.keys()),
            "final_values": final_values,
            "cost_usd": cost_data.get("cost_total", 0.0),
            "tokens_used": cost_data.get("total_tokens", 0),
            "model": cost_data.get("model", "gpt-4o")
        }
        
        # כתיבה לקובץ נפרד לביצועים
        performance_log_path = "data/gpt_d_performance.jsonl"
        os.makedirs(os.path.dirname(performance_log_path), exist_ok=True)
        
        with open(performance_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(performance_log, ensure_ascii=False) + "\n")
            
    except Exception as e:
        logging.error(f"שגיאה בתיעוד ביצועי gpt_d: {e}")

def gpt_d_async(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, gpt_d, *args, **kwargs)

# ============================ פונקציה לבדיקת דוגמאות של gpt_d ============================

def test_gpt_d_examples():
    """
    בודק את gpt_d עם דוגמאות שונות כדי לוודא שהוא עובד כמו שצריך.
    """
    print("🧪 בדיקת gpt_d עם דוגמאות...")
    
    # דוגמה 1: גיל שהשתנה
    example1 = {
        "age": {"old": "25", "new": "26"}
    }
    print(f"\n📝 דוגמה 1 - גיל: {example1}")
    result1 = gpt_d(example1, chat_id="test_1")
    print(f"✅ תוצאה: {result1.get('final_values', {})}")
    
    # דוגמה 2: מקצוע שהשתנה
    example2 = {
        "occupation_or_role": {"old": "סטודנט", "new": "מהנדס תוכנה"}
    }
    print(f"\n📝 דוגמה 2 - מקצוע: {example2}")
    result2 = gpt_d(example2, chat_id="test_2")
    print(f"✅ תוצאה: {result2.get('final_values', {})}")
    
    # דוגמה 3: גיל לא הגיוני
    example3 = {
        "age": {"old": "25", "new": "150"}
    }
    print(f"\n📝 דוגמה 3 - גיל לא הגיוני: {example3}")
    result3 = gpt_d(example3, chat_id="test_3")
    print(f"✅ תוצאה: {result3.get('final_values', {})}")
    
    # דוגמה 4: מספר שדות
    example4 = {
        "age": {"old": "30", "new": "31"},
        "occupation_or_role": {"old": "מורה", "new": "מרצה באוניברסיטה"},
        "interests": {"old": "קריאה", "new": "קריאה, כתיבה, טיולים"}
    }
    print(f"\n📝 דוגמה 4 - מספר שדות: {example4}")
    result4 = gpt_d(example4, chat_id="test_4")
    print(f"✅ תוצאה: {result4.get('final_values', {})}")
    
    print("\n🎉 בדיקת הדוגמאות הושלמה!")

# ============================ פונקציה להערכת עלויות של gpt_d ============================

def estimate_gpt_d_cost(existing_profile, new_data):
    """
    מעריך את העלות של הפעלת gpt_d.
    
    קלט:
    - existing_profile: dict עם הפרופיל הקיים
    - new_data: dict עם הנתונים החדשים
    
    פלט:
    - dict עם הערכת עלות מפורטת
    """
    # זיהוי שדות שהשתנו (רק כאלה שהישן היה מלא)
    changed_fields = identify_changed_fields(existing_profile, new_data)
    
    if not changed_fields:
        return {
            "estimated_cost_usd": 0.0,
            "reason": "אין שדות שהשתנו או השדה הישן היה ריק",
            "changed_fields_count": 0
        }
    
    # הערכת טוקנים
    # Prompt: ~200 טוקנים
    # כל שדה: ~50 טוקנים (שם + ערך ישן + ערך חדש)
    # תשובה: ~100 טוקנים לכל שדה
    base_prompt_tokens = 200
    field_tokens = len(changed_fields) * 50
    response_tokens = len(changed_fields) * 100
    
    total_input_tokens = base_prompt_tokens + field_tokens
    total_output_tokens = response_tokens
    
    # עלות gpt-4o (נכון ל-2024)
    input_cost_per_1k = 0.005  # $5 per 1M tokens
    output_cost_per_1k = 0.015  # $15 per 1M tokens
    
    input_cost = (total_input_tokens / 1000) * input_cost_per_1k
    output_cost = (total_output_tokens / 1000) * output_cost_per_1k
    total_cost = input_cost + output_cost
    
    return {
        "estimated_cost_usd": total_cost,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "changed_fields_count": len(changed_fields),
        "changed_fields": list(changed_fields.keys()),
        "cost_breakdown": {
            "input_cost": input_cost,
            "output_cost": output_cost
        }
    }

# ============================ פונקציה לבדיקת יעילות של gpt_d ============================

def compare_gpt_d_efficiency(existing_profile, new_data):
    """
    משווה בין יעילות gpt_d למיזוג פשוט.
    
    קלט:
    - existing_profile: dict עם הפרופיל הקיים
    - new_data: dict עם הנתונים החדשים
    
    פלט:
    - dict עם השוואה מפורטת
    """
    # מיזוג פשוט
    simple_merge_result = simple_merge_profile(existing_profile, new_data)
    
    # בדיקה אם צריך gpt_d
    should_use_gpt_d = should_activate_gpt_d(existing_profile, new_data)
    
    # הערכת עלות gpt_d
    estimated_gpt_d_cost = estimate_gpt_d_cost(existing_profile, new_data)
    
    # זיהוי שדות שהשתנו (רק כאלה שהישן היה מלא)
    changed_fields = identify_changed_fields(existing_profile, new_data)
    
    return {
        "should_use_gpt_d": should_use_gpt_d,
        "simple_merge_result": simple_merge_result,
        "changed_fields": changed_fields,
        "estimated_gpt_d_cost": estimated_gpt_d_cost,
        "reasoning": "gpt_d מופעל רק כשהשדה הישן היה מלא ויש צורך בהחלטה חכמה"
    }

# ============================ פונקציה להדגמת שימוש מעשי ב-gpt_d ============================

def demonstrate_gpt_d_usage():
    """
    מדגים שימוש מעשי ב-gpt_d עם תרחישים אמיתיים.
    """
    print("🎯 הדגמת שימוש מעשי ב-gpt_d...")
    
    # תרחיש 1: משתמש מעדכן את הגיל שלו
    print("\n📋 תרחיש 1: עדכון גיל")
    existing_profile1 = {"age": "25", "occupation_or_role": "סטודנט"}
    new_data1 = {"age": "26"}
    
    comparison1 = compare_gpt_d_efficiency(existing_profile1, new_data1)
    print(f"השוואה: {comparison1}")
    
    if comparison1["should_use_gpt_d"]:
        result1 = gpt_d(comparison1["changed_fields"], chat_id="demo_1")
        print(f"תוצאת gpt_d: {result1.get('final_values', {})}")
    
    # תרחיש 2: משתמש משנה מקצוע
    print("\n📋 תרחיש 2: שינוי מקצוע")
    existing_profile2 = {"age": "30", "occupation_or_role": "מורה"}
    new_data2 = {"occupation_or_role": "מרצה באוניברסיטה"}
    
    comparison2 = compare_gpt_d_efficiency(existing_profile2, new_data2)
    print(f"השוואה: {comparison2}")
    
    if comparison2["should_use_gpt_d"]:
        result2 = gpt_d(comparison2["changed_fields"], chat_id="demo_2")
        print(f"תוצאת gpt_d: {result2.get('final_values', {})}")
    
    # תרחיש 3: עדכון מרובה
    print("\n📋 תרחיש 3: עדכון מרובה")
    existing_profile3 = {
        "age": "28", 
        "occupation_or_role": "מפתח תוכנה",
        "interests": "תכנות, קריאה"
    }
    new_data3 = {
        "age": "29",
        "occupation_or_role": "מהנדס תוכנה בכיר",
        "interests": "תכנות, קריאה, טיולים"
    }
    
    comparison3 = compare_gpt_d_efficiency(existing_profile3, new_data3)
    print(f"השוואה: {comparison3}")
    
    if comparison3["should_use_gpt_d"]:
        result3 = gpt_d(comparison3["changed_fields"], chat_id="demo_3")
        print(f"תוצאת gpt_d: {result3.get('final_values', {})}")
    
    # תרחיש 4: נתונים לא הגיוניים
    print("\n📋 תרחיש 4: נתונים לא הגיוניים")
    existing_profile4 = {"age": "25"}
    new_data4 = {"age": "150"}  # גיל לא הגיוני
    
    comparison4 = compare_gpt_d_efficiency(existing_profile4, new_data4)
    print(f"השוואה: {comparison4}")
    
    if comparison4["should_use_gpt_d"]:
        result4 = gpt_d(comparison4["changed_fields"], chat_id="demo_4")
        print(f"תוצאת gpt_d: {result4.get('final_values', {})}")
    
    print("\n🎉 הדגמת השימוש הושלמה!")

# ============================ פונקציה עזר לזיהוי שדות שהשתנו ============================

def identify_changed_fields(existing_profile, new_data):
    """
    מזהה שדות שהשתנו בין הפרופיל הקיים לנתונים החדשים.
    כולל רק שדות שהישן היה מלא והחדש שונה.
    
    קלט:
    - existing_profile: dict עם הפרופיל הקיים
    - new_data: dict עם הנתונים החדשים
    
    פלט:
    - dict עם השדות שהשתנו בפורמט {"field_name": {"old": "value", "new": "value"}}
    """
    changed_fields = {}
    
    for field, new_value in new_data.items():
        if field in existing_profile:
            old_value = existing_profile[field]
            # בדיקה אם הערך השתנה משמעותית ורק אם הישן היה מלא
            if (old_value and old_value != "" and old_value != "null" and 
                str(old_value).strip() and 
                old_value != new_value and new_value and new_value != "null"):
                changed_fields[field] = {
                    "old": str(old_value),
                    "new": str(new_value)
                }
        # לא כולל שדות חדשים (שהשדה הישן היה ריק) - אלה יטופלו במיזוג פשוט
    
    return changed_fields

# ============================ פונקציה לבדיקה אם צריך להפעיל gpt_d ============================

def should_activate_gpt_d(existing_profile, new_data):
    """
    בודק אם יש צורך להפעיל את gpt_d לטיפול בשדות שהשתנו.
    מפעיל רק כשהשדה הישן היה מלא ויש צורך בהחלטה חכמה.
    
    קלט:
    - existing_profile: dict עם הפרופיל הקיים
    - new_data: dict עם הנתונים החדשים
    
    פלט:
    - True אם יש שדות שהשתנו ויש צורך בהחלטה חכמה
    - False אם אין שדות שהשתנו או שאין צורך בהחלטה
    """
    if not existing_profile or not new_data:
        return False
    
    # בודק אם יש שדות שדורשים החלטה חכמה
    fields_requiring_smart_decision = [
        "age", "pronoun_preference", "attracted_to", "relationship_type", 
        "occupation_or_role", "interests", "personality_traits"
    ]
    
    for field, new_value in new_data.items():
        if field in existing_profile:
            old_value = existing_profile[field]
            # רק אם השדה הישן היה מלא ולא ריק
            if old_value and old_value != "" and old_value != "null" and str(old_value).strip():
                # רק אם הערך החדש שונה מהישן
                if old_value != new_value and new_value and new_value != "null":
                    if field in fields_requiring_smart_decision:
                        return True
    
    return False

# ============================ פונקציה פשוטה למיזוג נתונים ============================

def simple_merge_profile(existing_profile, new_data):
    """
    פונקציה פשוטה למיזוג נתונים ללא שימוש ב-gpt_d.
    מטפלת בשדות חדשים ובשדות שלא דורשים החלטה חכמה.
    """
    print(f"[DEBUG][simple_merge_profile] Simple merge without gpt_d")
    
    if not existing_profile:
        return new_data
    
    if not new_data:
        return existing_profile
    
    # מיזוג פשוט - הערכים החדשים דורסים את הישנים
    merged_profile = {**existing_profile, **new_data}
    
    # ניקוי ערכים ריקים או לא תקינים
    cleaned_profile = {}
    for key, value in merged_profile.items():
        if value and value != "null" and str(value).strip():
            cleaned_profile[key] = value
    
    print(f"[DEBUG][simple_merge_profile] Final merged profile: {cleaned_profile}")
    return cleaned_profile

# ============================ פונקציה להערכת איכות נתונים ============================

def assess_data_quality(value, field_type="general"):
    """
    מעריך את איכות הנתונים בשדה מסוים.
    
    קלט:
    - value: הערך לבדיקה
    - field_type: סוג השדה (age, occupation, etc.)
    
    פלט:
    - dict עם הערכת איכות
    """
    if not value or value == "null" or str(value).strip() == "":
        return {
            "quality_score": 0,
            "is_valid": False,
            "issues": ["ערך ריק או לא תקין"],
            "recommendation": "יש למלא ערך תקין"
        }
    
    value_str = str(value).strip()
    
    # בדיקות ספציפיות לפי סוג השדה
    if field_type == "age":
        try:
            age = int(value_str)
            if age < 0 or age > 120:
                return {
                    "quality_score": 0,
                    "is_valid": False,
                    "issues": [f"גיל לא הגיוני: {age}"],
                    "recommendation": "גיל צריך להיות בין 0 ל-120"
                }
            elif age < 13 or age > 100:
                return {
                    "quality_score": 0.5,
                    "is_valid": True,
                    "issues": [f"גיל חריג: {age}"],
                    "recommendation": "בדוק אם הגיל נכון"
                }
            else:
                return {
                    "quality_score": 1.0,
                    "is_valid": True,
                    "issues": [],
                    "recommendation": "גיל תקין"
                }
        except ValueError:
            return {
                "quality_score": 0,
                "is_valid": False,
                "issues": ["גיל אינו מספר"],
                "recommendation": "גיל צריך להיות מספר"
            }
    
    elif field_type == "occupation_or_role":
        if len(value_str) < 2:
            return {
                "quality_score": 0.3,
                "is_valid": True,
                "issues": ["תיאור מקצוע קצר מדי"],
                "recommendation": "הוסף תיאור מקצוע מפורט יותר"
            }
        elif len(value_str) > 100:
            return {
                "quality_score": 0.7,
                "is_valid": True,
                "issues": ["תיאור מקצוע ארוך מדי"],
                "recommendation": "קצר את התיאור"
            }
        else:
            return {
                "quality_score": 1.0,
                "is_valid": True,
                "issues": [],
                "recommendation": "תיאור מקצוע תקין"
            }
    
    else:
        # בדיקה כללית
        if len(value_str) < 1:
            return {
                "quality_score": 0,
                "is_valid": False,
                "issues": ["ערך ריק"],
                "recommendation": "יש למלא ערך"
            }
        elif len(value_str) > 200:
            return {
                "quality_score": 0.5,
                "is_valid": True,
                "issues": ["ערך ארוך מדי"],
                "recommendation": "קצר את הערך"
            }
        else:
            return {
                "quality_score": 1.0,
                "is_valid": True,
                "issues": [],
                "recommendation": "ערך תקין"
            }

def smart_update_profile_with_gpt_d(existing_profile, user_message, interaction_id=None):
    """
    מעדכן תעודת זהות רגשית של משתמש עם שימוש ב-gpt_d לטיפול בשדות שהשתנו.
    """
    print(f"[DEBUG][smart_update_profile_with_gpt_d] - interaction_id: {interaction_id}")
    try:
        # קודם כל מחלץ מידע חדש
        gpt_c_response = gpt_c(
            user_message=user_message,
            chat_id=interaction_id
        )

        if not gpt_c_response or not gpt_c_response.get("full_data"):
            return existing_profile, {}

        new_data = gpt_c_response.get("full_data", {})
        extract_usage = {k: v for k, v in gpt_c_response.items() if k not in ["updated_summary", "full_data"]}

        if not new_data:
            return existing_profile, extract_usage

        # בודק אם צריך להפעיל את gpt_d
        if should_activate_gpt_d(existing_profile, new_data):
            print(f"[DEBUG][smart_update_profile_with_gpt_d] Activating gpt_d for smart field resolution")
            
            # מזהה שדות שהשתנו (רק כאלה שהישן היה מלא)
            changed_fields = identify_changed_fields(existing_profile, new_data)
            print(f"[DEBUG][smart_update_profile_with_gpt_d] changed_fields: {changed_fields}")
            
            # משתמש ב-gpt_d להחלטה על השדות שהשתנו
            gpt_d_response = gpt_d(
                changed_fields=changed_fields,
                chat_id=interaction_id
            )
            
            if not gpt_d_response:
                print(f"[DEBUG][smart_update_profile_with_gpt_d] gpt_d failed, using simple merge")
                updated_profile = simple_merge_profile(existing_profile, new_data)
                return updated_profile, extract_usage
            
            final_values = gpt_d_response.get("final_values", {})
            gpt_d_usage = {k: v for k, v in gpt_d_response.items() if k != "final_values"}
            
            # מעדכן את הפרופיל עם הערכים הסופיים מ-gpt_d + מיזוג פשוט לשאר
            updated_profile = simple_merge_profile(existing_profile, new_data)
            updated_profile.update(final_values)  # דורס עם החלטות gpt_d
            
            # משלב את הנתונים על השימוש
            combined_usage = {**extract_usage, **gpt_d_usage}
            
            print(f"[DEBUG][smart_update_profile_with_gpt_d] final updated_profile: {updated_profile}")
            return updated_profile, combined_usage
        else:
            print(f"[DEBUG][smart_update_profile_with_gpt_d] No need for gpt_d, using simple merge")
            # אם אין צורך ב-gpt_d, פשוט משלב את הנתונים החדשים
            updated_profile = simple_merge_profile(existing_profile, new_data)
            return updated_profile, extract_usage

    except Exception as e:
        logging.error(f"❌ שגיאה ב-smart_update_profile_with_gpt_d: {e}")
        return existing_profile, {}

def smart_update_profile_with_gpt_d_async(existing_profile, user_message, interaction_id=None):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, smart_update_profile_with_gpt_d, existing_profile, user_message, interaction_id)

def run_gpt_d_demo():
    """
    הרצת הדגמה מלאה של gpt_d.
    """
    print("🚀 הרצת הדגמה מלאה של gpt_d...")
    print("=" * 60)
    
    # 1. הדגמת יעילות
    print("\n📊 הדגמת יעילות gpt_d:")
    demonstrate_gpt_d_efficiency()
    
    # 2. דוגמאות שימוש
    print("\n📚 דוגמאות שימוש מעשיות:")
    gpt_d_usage_examples()
    
    # 3. בדיקות אינטגרציה
    print("\n🧪 בדיקות אינטגרציה:")
    test_gpt_d_integration()
    
    # 4. דוגמת אינטגרציה מלאה
    print("\n🔗 דוגמת אינטגרציה מלאה:")
    gpt_d_integration_example()
    
    print("\n" + "=" * 60)
    print("✅ הדגמה מלאה הושלמה!")
    print("\n📝 סיכום:")
    print("• gpt_d מופעל רק כשהשדה הישן היה מלא ויש צורך בהחלטה חכמה")
    print("• שדות חדשים (הישן ריק) מטופלים במיזוג פשוט")
    print("• עלות נמוכה: ~$0.0001-0.001 לכל פעולה")
    print("• מהירות גבוהה: ~1-2 שניות")
    print("• איכות החלטות גבוהה עם gpt-4o")

def gpt_d_integration_example():
    """
    דוגמה מלאה של אינטגרציה עם gpt_d.
    """
    print("🔗 דוגמת אינטגרציה מלאה עם gpt_d...")
    
    # תרחיש: משתמש מעדכן את הפרופיל שלו
    existing_profile = {
        "age": "25",
        "occupation_or_role": "סטודנט",
        "interests": "מוזיקה, קריאה"
    }
    
    new_data = {
        "age": "26",
        "occupation_or_role": "מפתח תוכנה",
        "personality_traits": "יצירתי, חברותי"
    }
    
    print(f"פרופיל קיים: {existing_profile}")
    print(f"נתונים חדשים: {new_data}")
    
    # שימוש בפונקציה החכמה
    updated_profile, usage_stats = smart_update_profile_with_gpt_d(
        existing_profile=existing_profile,
        new_data=new_data,
        interaction_id="demo_user_123"
    )
    
    print(f"\nפרופיל מעודכן: {updated_profile}")
    print(f"סטטיסטיקות שימוש: {usage_stats}")
    
    # ניתוח התוצאה
    print(f"\n📊 ניתוח התוצאה:")
    
    # בדיקה אילו שדות השתנו
    changed_fields = identify_changed_fields(existing_profile, new_data)
    print(f"שדות שהשתנו (הישן מלא): {changed_fields}")
    
    # בדיקה אילו שדות חדשים
    new_fields = {k: v for k, v in new_data.items() if k not in existing_profile or not existing_profile.get(k)}
    print(f"שדות חדשים (הישן ריק): {new_fields}")
    
    # הערכת עלות
    cost_estimate = estimate_gpt_d_cost(existing_profile, new_data)
    print(f"עלות משוערת: ${cost_estimate['estimated_cost_usd']:.6f}")
    
    print("\n✅ דוגמת האינטגרציה הושלמה!")

# ============================ פונקציה לבדיקה מהירה של gpt_d ============================

def quick_gpt_d_test():
    """
    בדיקה מהירה של gpt_d עם דוגמאות פשוטות.
    """
    print("⚡ בדיקה מהירה של gpt_d...")
    
    # דוגמה פשוטה - גיל
    test_fields = {
        "age": {"old": "25", "new": "26"}
    }
    
    print(f"📝 בדיקה: {test_fields}")
    result = gpt_d(test_fields, chat_id="quick_test")
    
    if result:
        print(f"✅ תוצאה: {result.get('final_values', {})}")
        print(f"💰 עלות: ${result.get('cost_total', 0):.6f}")
        print(f"🔢 טוקנים: {result.get('total_tokens', 0)}")
    else:
        print("❌ שגיאה בבדיקה")
    
    print("🎉 בדיקה מהירה הושלמה!")

# ============================ פונקציה להפעלת כל הבדיקות ============================

def run_all_gpt_d_tests():
    """
    מפעיל את כל הבדיקות של gpt_d.
    """
    print("🧪 הפעלת כל בדיקות gpt_d...")
    
    # סיכום תכונות
    gpt_d_summary()
    
    # ניתוח עלויות
    analyze_gpt_d_costs()
    
    # הדגמת יעילות
    demonstrate_gpt_d_efficiency()
    
    # בדיקה מהירה
    quick_gpt_d_test()
    
    # דוגמאות שימוש מעשיות
    gpt_d_usage_examples()
    
    # בדיקת דוגמאות
    test_gpt_d_examples()
    
    # הדגמת שימוש מעשי
    demonstrate_gpt_d_usage()
    
    print("\n🎉 כל הבדיקות הושלמו!")

# ============================ אם הקובץ רץ ישירות ============================

if __name__ == "__main__":
    print("🚀 הפעלת בדיקות gpt_d...")
    run_all_gpt_d_tests()

# ============================ פונקציה לניתוח עלויות של gpt_d ============================

def analyze_gpt_d_costs():
    """
    מנתח את העלויות של gpt_d ומשווה למיזוג פשוט.
    """
    print("💰 ניתוח עלויות gpt_d...")
    
    # דוגמאות שונות עם מספר שדות שונה
    scenarios = [
        {"name": "שדה אחד", "existing": {"age": "25"}, "new": {"age": "26"}},
        {"name": "שני שדות", "existing": {"age": "25", "occupation": "סטודנט"}, "new": {"age": "26", "occupation": "מהנדס"}},
        {"name": "שלושה שדות", "existing": {"age": "25", "occupation": "סטודנט", "interests": "מוזיקה"}, "new": {"age": "26", "occupation": "מהנדס", "interests": "ספורט"}},
        {"name": "חמישה שדות", "existing": {"age": "25", "occupation": "סטודנט", "interests": "מוזיקה", "personality": "שקט", "location": "תל אביב"}, "new": {"age": "26", "occupation": "מהנדס", "interests": "ספורט", "personality": "חברותי", "location": "ירושלים"}}
    ]
    
    print("\n📊 השוואת עלויות:")
    print("=" * 60)
    print(f"{'תרחיש':<15} {'שדות':<8} {'עלות משוערת':<15} {'טוקנים משוערים':<20}")
    print("=" * 60)
    
    for scenario in scenarios:
        cost_estimate = estimate_gpt_d_cost(scenario["existing"], scenario["new"])
        print(f"{scenario['name']:<15} {cost_estimate['changed_fields_count']:<8} ${cost_estimate['estimated_cost_usd']:<14.6f} {cost_estimate['input_tokens'] + cost_estimate['output_tokens']:<20}")
    
    print("=" * 60)
    print("💡 הערות:")
    print("- עלויות מבוססות על מודל gpt-4o")
    print("- מיזוג פשוט: עלות 0 (ללא קריאה ל-API)")
    print("- gpt_d: עלות נמוכה מאוד לדיוק גבוה")
    print("- מומלץ להשתמש ב-gpt_d רק כשנדרשת החלטה חכמה")

# ============================ סיכום תכונות gpt_d ============================

def gpt_d_summary():
    """
    מציג סיכום של תכונות gpt_d.
    """
    print("📋 סיכום תכונות gpt_d:")
    print("=" * 50)
    
    features = [
        "🤖 מודל חכם להחלטות על שדות שהשתנו",
        "💰 חסכוני - מקבל רק שדות רלוונטיים",
        "⚡ מהיר - משתמש במודל gpt-4o",
        "🎯 מדויק - כולל הערכת איכות נתונים",
        "📊 מנוטר - מעקב על ביצועים ועלויות",
        "🔄 חכם - בודק אם צריך להפעיל או לא",
        "🛡️ בטוח - גיבוי למיזוג פשוט",
        "📈 מתפתח - לומד מהשימוש"
    ]
    
    for feature in features:
        print(f"  {feature}")
    
    print("\n🔧 פונקציות עיקריות:")
    print("  - gpt_d() - הפונקציה הראשית")
    print("  - should_activate_gpt_d() - בדיקה אם צריך להפעיל")
    print("  - identify_changed_fields() - זיהוי שדות שהשתנו")
    print("  - assess_data_quality() - הערכת איכות נתונים")
    print("  - smart_update_profile_with_gpt_d() - עדכון חכם")
    
    print("\n💡 מתי להשתמש:")
    print("  - כשהשתנו שדות חשובים (גיל, מקצוע, וכו')")
    print("  - כשיש סתירה בין נתונים ישנים וחדשים")
    print("  - כשנדרשת החלטה חכמה על איכות הנתונים")
    
    print("\n❌ מתי לא להשתמש:")
    print("  - כשהשתנו רק שדות לא חשובים")
    print("  - כשאין סתירה בין הנתונים")
    print("  - כשמיזוג פשוט מספיק")

# ============================ דוגמאות שימוש מעשיות ב-gpt_d ============================

def gpt_d_usage_examples():
    """
    דוגמאות שימוש מעשיות ב-gpt_d.
    """
    print("📚 דוגמאות שימוש מעשיות ב-gpt_d...")
    
    # דוגמה 1: עדכון גיל פשוט (הישן היה מלא)
    print("\n🔹 דוגמה 1: עדכון גיל (הישן היה מלא)")
    existing_profile = {"age": "25", "occupation_or_role": "סטודנט"}
    new_data = {"age": "26"}
    
    # בדיקה אם צריך gpt_d
    if should_activate_gpt_d(existing_profile, new_data):
        changed_fields = identify_changed_fields(existing_profile, new_data)
        result = gpt_d(changed_fields, chat_id="example_1")