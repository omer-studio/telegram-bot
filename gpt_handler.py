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
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": PROFILE_EXTRACTION_ENHANCED_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0,
            max_tokens=300,
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

