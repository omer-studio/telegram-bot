"""
gpt_a_handler.py
----------------
מנוע gpt_a: לוגיקת התשובה הראשית (main response logic)
עם מנגנון הודעה זמנית ופילטר חכם לבחירת מודל
"""

from simple_logger import logger
from datetime import datetime
import json
import lazy_litellm as litellm
import asyncio
import threading
import time
import re
from prompts import SYSTEM_PROMPT
from config import GPT_MODELS, GPT_PARAMS, GPT_FALLBACK_MODELS, should_log_debug_prints
from gpt_utils import normalize_usage_dict, billing_guard, measure_llm_latency, calculate_gpt_cost
from notifications import alert_billing_issue, send_error_notification
from simple_config import TimeoutConfig
from typing import TYPE_CHECKING
from db_manager import safe_str
if TYPE_CHECKING:
    from message_handler import format_text_for_telegram, send_message_with_retry  # for type checkers only
# מערכת ביצועים מבוטלת זמנית

# ייבוא הפילטר החכם
# ===============================
# 🎯 פילטר חכם לבחירת מודל AI
# ===============================

# סף מילים למודל מתקדם
LONG_MESSAGE_THRESHOLD = 50  # מעל 50 מילים = מודל מתקדם

# ===============================
# 📊 מנגנון ספירת הודעות לשאלות פרופיל
# ===============================
# מונה הודעות לכל משתמש - מאפשר לשאול שאלות רק כל 4 הודעות
profile_question_counters = {}

# 🆕 מנגנון פסק זמן לשאלות פרופיל
# כשהבוט שואל שאלה - מתחיל פסק זמן של 3 הודעות
profile_question_cooldowns = {}

def should_ask_profile_question(chat_id: str) -> bool:
    """
    בודק אם הגיע הזמן לשאול שאלת פרופיל
    
    לוגיקה:
    - אם המשתמש לא בפסק זמן - שואלים שאלה
    - כששואלים שאלה - מתחיל פסק זמן של 3 הודעות
    - במהלך הפסק זמן - לא שואלים שאלות
    - אחרי הפסק הזמן - חוזרים לשאול
    
    Returns:
        bool: True אם צריך לשאול שאלה, False אחרת
    """
    safe_chat_id = safe_str(chat_id)
    if safe_chat_id not in profile_question_cooldowns:
        profile_question_cooldowns[safe_chat_id] = 0
    
    # אם המשתמש בפסק זמן - מקטינים את המונה
    if profile_question_cooldowns[safe_chat_id] > 0:
        profile_question_cooldowns[safe_chat_id] -= 1
        logger.info(f"📊 [PROFILE_QUESTION] בפסק זמן | chat_id={safe_chat_id} | cooldown_left={profile_question_cooldowns[safe_chat_id]}", source="gpt_a_handler")
        return False
    
    # לא בפסק זמן - אפשר לשאול
    logger.info(f"📊 [PROFILE_QUESTION] הגיע הזמן לשאול שאלת פרופיל | chat_id={safe_chat_id}", source="gpt_a_handler")
    return True

def start_profile_question_cooldown(chat_id: str):
    """מתחיל פסק זמן של 3 הודעות אחרי ששאלה נשאלה"""
    safe_chat_id = safe_str(chat_id)
    profile_question_cooldowns[safe_chat_id] = 3
    logger.info(f"📊 [PROFILE_QUESTION] פסק זמן התחיל | chat_id={safe_chat_id} | cooldown=3", source="gpt_a_handler")

def reset_profile_question_counter(chat_id: str):
    """מאפס את המונה למשתמש מסוים (למקרה של שאלה שנענתה)"""
    safe_chat_id = safe_str(chat_id)
    if safe_chat_id in profile_question_counters:
        profile_question_counters[safe_chat_id] = 0
        logger.info(f"📊 [PROFILE_QUESTION] מונה אופס | chat_id={safe_chat_id}", source="gpt_a_handler")

def get_profile_question_stats():
    """מחזיר סטטיסטיקות של מוני השאלות"""
    return {
        "total_users": len(profile_question_counters),
        "counters": profile_question_counters.copy(),
        "cooldowns": profile_question_cooldowns.copy()
    }

def did_bot_ask_profile_questions(missing_text, bot_reply, chat_id=None):
    """
    בודק האם לפחות 2 מילים מתוך missing_text מופיעות בתשובת הבוט.
    מוסיף לוגים מפורטים לצורך דיבאגינג.
    """
    safe_chat_id = safe_str(chat_id) if chat_id else "unknown"
    if not missing_text or not bot_reply:
        logger.debug(f"[PROFILE_QUESTION][DEBUG] missing_text/bot_reply ריקים | chat_id={safe_chat_id}", source="gpt_a_handler")
        return False
    
    # מפרק את missing_text למילים בודדות (ללא סימני פיסוק)
    import re
    missing_words = re.findall(r'\b\w+\b', missing_text.lower())
    bot_words = re.findall(r'\b\w+\b', bot_reply.lower())
    
    # מוצא מילים משותפות
    matches = [word for word in missing_words if word in bot_words]
    
    logger.debug(f"[PROFILE_QUESTION][DEBUG] בדיקת התאמה בין מילים | chat_id={safe_chat_id} | missing_words={missing_words[:10]} | bot_words={bot_words[:10]} | matches={matches} | count={len(matches)}", source="gpt_a_handler")
    
    return len(matches) >= 2

def create_missing_fields_system_message(chat_id: str) -> tuple:
    """יוצר system message חכם עם שדות חסרים שכדאי לשאול עליהם
    מחזיר tuple: (system_message, missing_text)"""
    try:
        safe_chat_id = safe_str(chat_id)
        from db_manager import get_user_profile
        try:
            from fields_dict import FIELDS_DICT
        except ImportError:
            FIELDS_DICT = {"dummy": "dummy"}
        if not should_ask_profile_question(safe_chat_id):
            logger.info(f"📊 [PROFILE_QUESTION] לא הגיע הזמן לשאול שאלת פרופיל | chat_id={safe_chat_id}", source="gpt_a_handler")
            return "", ""
        profile_data = get_user_profile(safe_chat_id) or {}
        key_fields = ["name", "age", "attracted_to", "relationship_type", "self_religious_affiliation", 
                     "closet_status", "pronoun_preference", "occupation_or_role", 
                     "self_religiosity_level", "primary_conflict", "goal_in_course"]
        missing = [FIELDS_DICT[f]["missing_question"] for f in key_fields
                  if f in FIELDS_DICT and not str(profile_data.get(f, "")).strip() 
                  and FIELDS_DICT[f].get("missing_question", "").strip()]
        if len(missing) >= 2:
            missing_text = ', '.join(missing[:4])
            logger.info(f"📊 [PROFILE_QUESTION] שולח שאלת פרופיל | chat_id={safe_chat_id} | missing_fields={len(missing)} | missing_text={missing_text}", source="gpt_a_handler")
            return f"""פרטים שהמשתמש עדיין לא סיפר לך וחשוב מאוד לשאול אותו בעדינות וברגישות במטרה להכיר אותו יותר טוב: {missing_text}
\nראשית תסביר לו את הרציונל, תסביר לו למה אתה שואל, תגיד לו שחשוב לך להכיר אותו כדי להתאים את עצמך אליו. תתעניין בו - תבחר אחד מהשאלות שנראית לך הכי מתאימה - ורק אם זה מרגיש לך מתאים אז תשאל אותו בעדינות וברגישות ותשלב את זה באלגנטיות. (את השאלות תעשה בכתב מודגש)""", missing_text
        logger.info(f"📊 [PROFILE_QUESTION] אין מספיק שדות חסרים לשאלה | chat_id={safe_chat_id} | missing_fields={len(missing)}", source="gpt_a_handler")
        return "", ""
    except Exception as e:
        logger.error(f"שגיאה ביצירת הודעת שדות חסרים: {e}", source="gpt_a_handler")
        return "", ""

# מילות מפתח שמצדיקות מודל מתקדם
PREMIUM_MODEL_KEYWORDS = [
    # זוגיות ומערכות יחסים
    "נישואין", "חתונה", "זוגיות", "מערכת יחסים", "בן זוג", "בת זוג", "חברה", "חבר",
    "אהבה", "רגשות", "קשר", "זיקה", "משיכה", "אינטימיות", "מיניות", "פרידה", "גירושין",
    "גרוש", "נפרד", "נשוי", "נשואה", "מגורשת", "מגורש",
    
    # פסיכולוגיה ובריאות נפש
    "פסיכולוגיה", "טיפול", "ייעוץ", "פסיכולוג", "מטפל", "מדכא", "דיכאון", "חרדה", 
    "פחד", "דאגה", "בלבול", "לחץ", "סטרס", "טראומה", "פציעה נפשית", "בדידות",
    "כאב", "אובדן", "התעללות", "נפגע", "סבל", "בריונות", "אשמה", "בושה",
    "תקוע", "שיפוט עצמי", "הסתרה", "מורכב", "קשה לי", "לא שלם", "אבוד",
    
    # דתיות ואמונה
    "דתיות", "חילוני", "דתי", "מסורתי", "אמונה", "מצוות", "הלכה", "רב", "רבנות",
    "כשרות", "שבת", "חג", "תפילה", "בית כנסת", "תורה", "תלמוד", "יהדות",
    "דתלש", "דתל״ש", "דתי לשעבר", "חזרה בשאלה", "ישיבה", "טיפולי המרה",
    
    # משפחה וחיי חברה
    "משפחה", "הורים", "ילדים", "הריון", "לידה", "חינוך", "גיל", "זקנה", "סבא", "סבתא",
    "אבא", "אמא", "בן", "בת", "אח", "אחות", "דוד", "דודה", "בן דוד", "בת דוד",
    "משפחה מורחבת", "משפחה ביולוגית", "נכדים", "ההורים", "חיים כפולים",
    
    # עבודה וקריירה
    "עבודה", "קריירה", "השכלה", "לימודים", "אוניברסיטה", "מקצוע", "כלכלה", "שכר",
    "מנהל", "עובד", "מעסיק", "ראיון עבודה", "קורות חיים", "השכלה גבוהה",
    
    # בריאות רפואית
    "בריאות", "רופא", "חולה", "מחלה", "תרופה", "ניתוח", "בית חולים", "קופת חולים",
    "כאב", "כואב", "רפואה", "אבחון", "טיפול רפואי", "מחלה כרונית", "איידס", "HIV", "מחלות",
    
    # החלטות ודילמות
    "בעיה", "קושי", "החלטה", "דילמה", "ברירה", "אפשרות", "עתיד", "תכנון", "יעד", "חלום",
    "לבחור", "להחליט", "נבוך", "מבולבל", "לא יודע", "עזרה", "חשוב", "קריטי",
    "חסום", "לא מצליח", "מפחד", "לא מעז", "מתבייש", "דחיקה", "הימנעות",
    
    # נטייה מינית וזהות מינית - LGBTQ+
    "הומו", "גיי", "ביסקסואל", "להט״ב", "להטב", "הקהילה הגאה", "נטייה מינית", "זהות מינית",
    "בארון", "יציאה מהארון", "ארוניסט", "דיסקרטי", "ארון", "הארון", "בי", "דו", "נמשך",
    "הומופוביה", "הומופוביה פנימית", "הומופוביה עצמית", "לא מקבל את עצמי",
    "מתחנגל", "אוכל בתחת", "קוקסינל", "נשי", "גברי", "טרנס", "קווירי",
    "על הרצף", "סקס", "אנאלי", "אוראלי", "מפחד",
    
    # גיל ומעברים
    "בגיל מאוחר", "מפספס", "הרכבת עוברת", "זמן טס", "לא צעיר", "כבר בן", "כבר בת",
    "נמאס", "למות", "רוצה להיות חופשי", "מרגיש צעיר", "אמצע החיים"
]

# דפוסי ביטויים מורכבים (regex) - רזה וחד
COMPLEX_PATTERNS = [
    # שאלות מורכבות
    r"מה\s+עושים\s+כש|איך\s+להתמודד\s+עם|צריך\s+עצה\s+ב|לא\s+יודע\s+איך",
    # מצבי נפש קשים  
    r"לא\s+מרגיש\s+שלם|אני\s+תקוע|מרגיש\s+אבוד|אני\s+שונא\s+את\s+עצמי",
    # קבלה עצמית
    r"לא\s+שלם\s+עם|קושי\s+ל[ק|כ]בל|עדיין\s+לא\s+שלם|התמודדות\s+עם",
    # זוגיות ובדידות
    r"נשוי\s+ל|לא\s+מצליח\s+למצוא|יצאתי\s+אבל\s+לא\s+באמת"
]

# משתנה גלובלי לעקיבה אחר ההחלטות
filter_decisions_log = {
    "first_20_messages": 0,
    "length": 0,
    "keywords": 0, 
    "pattern": 0,
    "default": 0
}

def log_filter_decision(match_type):
    """רושם החלטת פילטר לצורך ניתוח"""
    global filter_decisions_log
    if match_type in filter_decisions_log:
        filter_decisions_log[match_type] += 1

def get_filter_analytics():
    """מחזיר ניתוח של החלטות הפילטר"""
    global filter_decisions_log
    total = sum(filter_decisions_log.values())
    if total == 0:
        return {"message": "עדיין לא נרשמו החלטות פילטר"}
    
    percentages = {k: round((v/total)*100, 1) for k, v in filter_decisions_log.items()}
    
    return {
        "total_decisions": total,
        "breakdown": filter_decisions_log.copy(),
        "percentages": percentages,
        "premium_usage": round(((total - filter_decisions_log["default"])/total)*100, 1) if total > 0 else 0
    }

def should_use_extra_emotion_model(user_message, chat_history_length=0):
    """
    מחליט האם להשתמש במודל המתקדם או במהיר יותר
    
    קריטריונים למודל מתקדם:
    1. 🆕 20 ההודעות הראשונות של משתמש חדש (רושם ראשוני חשוב)
    2. הודעה ארוכה (מעל X מילים)
    3. מילות מפתח רלוונטיות
    4. דפוסי ביטויים מורכבים
    
    Returns:
        tuple: (use_extra_emotion: bool, reason: str, match_type: str)
    """
    # 🆕 בדיקה 1: 20 ההודעות הראשונות - רושם ראשוני חשוב
    if chat_history_length <= 20:
        logger.info(f"🎯 [PREMIUM_FILTER] 20 ההודעות הראשונות: {chat_history_length} הודעות -> מודל מתקדם (רושם ראשוני)")
        result = True, f"20 ההודעות הראשונות ({chat_history_length}/20) - רושם ראשוני חשוב", "first_20_messages"
        log_filter_decision(result[2])
        return result
    
    # בדיקת אורך הודעה
    word_count = len(user_message.split())
    if word_count > LONG_MESSAGE_THRESHOLD:
        logger.info(f"🎯 [PREMIUM_FILTER] הודעה ארוכה: {word_count} מילים -> מודל מתקדם")
        result = True, f"הודעה ארוכה ({word_count} מילים)", "length"
        log_filter_decision(result[2])
        return result
    
    # בדיקת מילות מפתח
    user_message_lower = user_message.lower()
    found_keywords = [keyword for keyword in PREMIUM_MODEL_KEYWORDS if keyword in user_message_lower]
    if found_keywords:
        logger.info(f"🎯 [PREMIUM_FILTER] מילות מפתח נמצאו: {found_keywords[:3]} -> מודל מתקדם")
        result = True, f"מילות מפתח: {', '.join(found_keywords[:3])}", "keywords"
        log_filter_decision(result[2])
        return result
    
    # בדיקת דפוסי ביטויים מורכבים
    for pattern in COMPLEX_PATTERNS:
        if re.search(pattern, user_message_lower):
            logger.info(f"🎯 [PREMIUM_FILTER] דפוס מורכב נמצא: {pattern} -> מודל מתקדם")
            result = True, f"דפוס מורכב זוהה", "pattern"
            log_filter_decision(result[2])
            return result
    
    # אחרת, מודל מהיר
    logger.info(f"🚀 [PREMIUM_FILTER] מקרה רגיל -> מודל מהיר")
    result = False, "מקרה רגיל - מודל מהיר", "default"
    log_filter_decision(result[2])
    return result

async def send_temporary_message_after_delay(update, chat_id, delay_seconds=8):
    """
    שולח הודעה זמנית אחרי דיליי מסוים ומחזיר את האובייקט Message שלה

    השינוי (החזרת האובייקט עצמו ולא רק ה-id) מאפשר לנו למחוק את ההודעה בקלות באמצעות
    await temp_message.delete()‎ בלי ״ציד״ אחר ה-bot, מה שפגע במחיקה בעבר.
    """
    try:
        # בדיקה אם המשימה בוטלה לפני השינה
        await asyncio.sleep(delay_seconds)
        
        # בדיקה נוספת אחרי השינה - אם המשימה בוטלה, לא נשלח הודעה
        if asyncio.current_task().cancelled():
            logger.info(f"📤 [TEMP_MSG] משימה בוטלה לפני שליחת הודעה זמנית | chat_id={safe_str(chat_id)}", source="gpt_a_handler")
            return None
            
        from message_handler import send_system_message  # local import to avoid circular
        temp_message_text = "⏳ אני עובד על תשובה בשבילך... זה מיד אצלך..."
        await send_system_message(update, chat_id, temp_message_text)
        
        # נחזיר None כי send_system_message לא מחזיר את האובייקט
        logger.info(f"📤 [TEMP_MSG] נשלחה הודעה זמנית | chat_id={safe_str(chat_id)}", source="gpt_a_handler")
        return None  # לא מחזירים אובייקט כי send_system_message לא מחזיר
    except asyncio.CancelledError:
        logger.info(f"📤 [TEMP_MSG] משימה בוטלה בזמן שליחת הודעה זמנית | chat_id={safe_str(chat_id)}", source="gpt_a_handler")
        return None
    except Exception as e:
        logger.error(f"❌ [TEMP_MSG] שגיאה בשליחת הודעה זמנית: {e}")
        return None

async def delete_temporary_message_and_send_new(update, temp_message, new_text):
    """
    מוחק את ההודעה הזמנית (אם קיימת) ושולח למשתמש את התשובה האמיתית.

    ✅ שיפור: משתמשים ב-send_message עם is_gpt_a_response=True – בטוח ופשוט יותר.
    """
    from message_handler import send_message  # local import to avoid circular

    try:
        # מחיקת ההודעה הזמנית - לא רלוונטי כי send_message לא מחזיר אובייקט
        if temp_message is not None:
            logger.info(f"🗑️ [DELETE_MSG] הודעה זמנית לא נמחקה (לא רלוונטי עם send_message)")

        # שליחת ההודעה החדשה
        chat_id = update.message.chat_id
        await send_message(update, chat_id, new_text, is_bot_message=True, is_gpt_a_response=True)
        logger.info(f"📤 [NEW_MSG] נשלחה הודעה חדשה | chat_id={safe_str(chat_id)}", source="gpt_a_handler")
        return True

    except Exception as send_err:
        logger.error(f"❌ [DELETE_MSG] כשל בשליחה: {send_err}")
        return False

def _execute_gpt_call(completion_params, full_messages):
    """הפעלת קריאה ל-GPT באופן סינכרוני"""
    try:
        response = litellm.completion(**completion_params)
        
        # חילוץ התשובה
        bot_reply = response.choices[0].message.content
        
        # חילוץ נתוני שימוש
        usage = normalize_usage_dict(response.usage) if hasattr(response, 'usage') else {}
        
        return {
            "bot_reply": bot_reply,
            "usage": usage,
            "model": completion_params["model"],
            "model_dump": response
        }
    except Exception as e:
        logger.error(f"[gpt_a] שגיאה במודל {completion_params['model']}: {e}")
        raise e

def get_main_response_sync(full_messages, chat_id=None, message_id=None, use_extra_emotion=True, filter_reason="", match_type="unknown"):
    """
    💎 מנוע gpt_a הראשי - גרסה סינכרונית
    """
    # מדידת זמן התחלה
    total_start_time = time.time()
    
    # שלב 1: הכנת ההודעות
    prep_start_time = time.time()
    
    # ההוספה של השדות החסרים מתבצעת כעת ב-message_handler.py
    # כדי להימנע מכפילויות, הסרנו את הקוד מכאן
    
    prep_time = time.time() - prep_start_time
    print(f"⚡ [TIMING] Preparation time: {prep_time:.3f}s")
    
    metadata = {"gpt_identifier": "gpt_a", "chat_id": chat_id, "message_id": message_id}
    params = GPT_PARAMS["gpt_a"]
    
    # 🔬 מדידת ביצועים מבוטלת זמנית
    measurement_id = None
    
    # בחירת מודל לפי הפילטר
    if use_extra_emotion:
        model = GPT_MODELS["gpt_a"]  # המודל המתקדם מ-config
        model_tier = "premium"
        logger.info(f"🎯 [MODEL_SELECTION] משתמש במודל מתקדם: {model} | סיבה: {filter_reason}")
    else:
        model = GPT_FALLBACK_MODELS["gpt_a"]  # המודל המהיר מ-config
        model_tier = "fast"
        logger.info(f"🚀 [MODEL_SELECTION] משתמש במודל מהיר: {model} | סיבה: {filter_reason}")
    
    completion_params = {
        "model": model,
        "messages": full_messages,
        "temperature": params["temperature"],
        "metadata": metadata
    }
    
    # הוספת max_tokens רק אם הוא לא None
    if params["max_tokens"] is not None:
        completion_params["max_tokens"] = params["max_tokens"]

    # 🔍 [DEBUG] ניתוח מפורט של המבנה שנשלח ל-GPT
    print(f"\n🔍 [GPT_REQUEST_DEBUG] === DETAILED GPT REQUEST ANALYSIS ===")
    print(f"🤖 [MODEL] {model} | ExtraEmotion: {use_extra_emotion} | Reason: {filter_reason}")
    print(f"📊 [PARAMS] Temperature: {params['temperature']} | Max Tokens: {params.get('max_tokens', 'None')}")
    print(f"📝 [MESSAGES_COUNT] Total messages: {len(full_messages)}")
    
    # ניתוח הודעות לפי סוג
    system_count = 0
    user_count = 0
    assistant_count = 0
    
    for i, msg in enumerate(full_messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        content_length = len(content)
        
        if role == "system":
            system_count += 1
            print(f"⚙️ [SYSTEM_{system_count}] Position: {i} | Length: {content_length} chars")
        elif role == "user":
            user_count += 1
            print(f"👤 [USER_{user_count}] Position: {i} | Length: {content_length} chars")
        elif role == "assistant":
            assistant_count += 1
            print(f"🤖 [ASSISTANT_{assistant_count}] Position: {i} | Length: {content_length} chars")
    
    print(f"📈 [SUMMARY] System: {system_count} | User: {user_count} | Assistant: {assistant_count}")
    print(f"🚀 [SENDING] Request to {model}...")
    print(f"🔍 [GPT_REQUEST_DEBUG] === END ANALYSIS ===\n")
    
    # שלב 2: הפעלת GPT ב-thread נפרד
    gpt_start_time = time.time()
    log_memory_usage("before_gpt_call")
    
    try:
        # 🚨 הגדלת timeout ל-45 שניות (במקום 30) לטיפול ב-latency גבוה
        GPT_TIMEOUT_SECONDS = TimeoutConfig.GPT_PROCESSING_TIMEOUT
        
        # הרצת GPT ישירות (ללא רקורסיה)
        gpt_result = _execute_gpt_call(completion_params, full_messages)
        
        gpt_duration = time.time() - gpt_start_time
        log_memory_usage("after_gpt_call")
        logger.info(f"⏱️ [GPT_TIMING] GPT הסתיים תוך {gpt_duration:.2f} שניות")
        
        # שלב 3: עיבוד התשובה
        processing_start_time = time.time()
        
        # 🔬 רישום הטוקן הראשון מבוטל זמנית
        
        bot_reply = gpt_result["bot_reply"]
        
        # 🆕 ניקוי תשובה מטקסט טכני ומאחורי הקלעים
        bot_reply = clean_bot_response(bot_reply)
        
        # ניקוי תגי HTML לא נתמכים שהמודל עלול להחזיר
        # <br> תגים לא נתמכים ב-Telegram - צריך להמיר ל-\n
        bot_reply = bot_reply.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
        # גם ניקוי תגי br עם attributes שונים
        bot_reply = re.sub(r'<br\s*/?>', '\n', bot_reply)
        
        usage = gpt_result["usage"]
        
        # הוספת נתוני עלות מדויקים ל-usage על סמך completion_response
        try:
            cost_info = calculate_gpt_cost(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cached_tokens=usage.get("cached_tokens", 0),
                model_name=gpt_result["model"],
                completion_response=gpt_result
            )
            usage.update(cost_info)
        except Exception as _cost_e:
            logger.warning(f"[gpt_a] לא הצלחתי לחשב עלות usage: {_cost_e}")
        
        processing_time = time.time() - processing_start_time
        print(f"⚡ [TIMING] Processing time: {processing_time:.3f}s")
        
        if should_log_debug_prints():
            print(f"[GPT_A_RESPONSE] {len(bot_reply)} chars from {gpt_result['model']}")
        print(f"⚡ [DETAILED_TIMING] GPT pure latency: {gpt_duration:.3f}s | Model: {gpt_result['model']}")
        
        # שלב 4: חישוב עלויות
        billing_start_time = time.time()
        
        #  מעקב אחר חיוב
        if 'cost_info' in locals():
            cost_usd = cost_info.get("cost_total", 0.0)
            if cost_usd and cost_usd > 0:
                billing_status = billing_guard.add_cost(cost_usd, gpt_result["model"], "paid" if use_extra_emotion else "free")
                
                # התראות לאדמין
                if billing_status.get("warnings"):
                    for warning in billing_status["warnings"]:
                        logger.warning(f"[💰 תקציב] {warning}")
                
                # התראה בטלגרם אם צריך
                status = billing_guard.get_current_status()
                alert_billing_issue(
                    cost_usd=cost_usd,
                    model_name=gpt_result["model"],
                    tier="paid" if use_extra_emotion else "free",
                    daily_usage=status["daily_usage"],
                    monthly_usage=status["monthly_usage"],
                    daily_limit=status["daily_limit"],
                    monthly_limit=status["monthly_limit"]
                )
            
        billing_time = time.time() - billing_start_time
        print(f"⚡ [TIMING] Billing time: {billing_time:.3f}s")
        
        # סיכום זמנים
        total_time = time.time() - total_start_time
        print(f"📊 [TIMING_SUMMARY] Total: {total_time:.3f}s | GPT: {gpt_duration:.3f}s | Prep: {prep_time:.3f}s | Processing: {processing_time:.3f}s | Billing: {billing_time:.3f}s")
        
        # 💾 שמירת מטריקות זמן מפורטות למסד הנתונים
        try:
            from db_manager import save_system_metrics
            save_system_metrics(
                metric_type="gpt_timing",
                chat_id=str(chat_id) if chat_id else None,
                gpt_latency_seconds=gpt_duration,
                prep_time_seconds=prep_time,
                processing_time_seconds=processing_time,
                billing_time_seconds=billing_time,
                response_time_seconds=total_time,
                additional_data={
                    "message_id": message_id,
                    "gpt_type": "A",
                    "model": gpt_result["model"],
                    "extra_emotion": use_extra_emotion,
                    "filter_reason": filter_reason,
                    "match_type": match_type,
                    "tokens_used": usage.get("total_tokens", 0),
                    "cost_usd": usage.get("cost_total", 0)
                }
            )
        except Exception as save_err:
            logger.warning(f"Could not save GPT timing metrics: {save_err}")
        
        # 🆕 בדיקה אם התשובה מכילה שאלת פרופיל והתחלת פסק זמן
        if chat_id and detect_profile_question_in_response(bot_reply):
            start_profile_question_cooldown(chat_id)
            logger.info(f"✅ [PROFILE_QUESTION] הופעל פסק זמן! | chat_id={safe_str(chat_id)}", source="gpt_a_handler")
        
        result = {
            "bot_reply": bot_reply, 
            "usage": usage, 
            "model": gpt_result["model"],
            "used_extra_emotion": use_extra_emotion,
            "filter_reason": filter_reason,
            "match_type": match_type,
            "gpt_pure_latency": gpt_duration,
            "total_time": total_time,
            "prep_time": prep_time,
            "processing_time": processing_time,
            "billing_time": billing_time
        }
        try:
            from gpt_jsonl_logger import GPTJSONLLogger
            # בניית response מלא עם כל המידע הנדרש
            response_data = {
                "id": getattr(gpt_result.get("model_dump"), "id", ""),
                "choices": [
                    {
                        "message": {
                            "content": gpt_result["bot_reply"],
                            "role": "assistant"
                        }
                    }
                ],
                "usage": gpt_result["usage"],
                "model": gpt_result["model"]
            }
            GPTJSONLLogger.log_gpt_call(
                log_path="data/openai_calls.jsonl",
                gpt_type="A",
                request=completion_params,
                response=response_data,
                cost_usd=usage.get("cost_total", 0),
                extra={
                    "chat_id": chat_id, 
                    "message_id": message_id,
                    "gpt_pure_latency": gpt_duration,
                    "total_time": total_time,
                    "prep_time": prep_time,
                    "processing_time": processing_time,
                    "billing_time": billing_time
                }
            )
        except Exception as log_exc:
            print(f"[LOGGING_ERROR] Failed to log GPT-A call: {log_exc}")
        return result
        
    except Exception as e:
        logger.error(f"[gpt_a] שגיאה במודל {gpt_result['model']}: {e}")
        
        # שליחת הודעת שגיאה טכנית לאדמין
        send_error_notification(
            error_message=f"שגיאה כללית ב-get_main_response_sync: {str(e)}",
            chat_id=chat_id,
            user_msg=full_messages[-1]["content"] if full_messages else "לא זמין", 
            error_type="gpt_a_engine_error"
        )
        
        error_reply = "מצטער, יש לי בעיה טכנית זמנית. העברתי את הפרטים לעומר שיבדוק את זה. נסה שוב בעוד כמה דקות 🔧"
        # 🐛 DEBUG: שליחת הודעת שגיאה
        print("=" * 80)
        print("❌ ERROR MESSAGE DEBUG")
        print("=" * 80)
        print(f"📝 ERROR TEXT: {repr(error_reply)}")
        print(f"📊 LENGTH: {len(error_reply)} chars")
        print(f"📊 NEWLINES: {error_reply.count(chr(10))}")
        print(f"📊 DOTS: {error_reply.count('.')}")
        print(f"📊 QUESTIONS: {error_reply.count('?')}")
        print(f"📊 EXCLAMATIONS: {error_reply.count('!')}")
        print("=" * 80)
        
        # 🆕 בדיקה אם התשובה מכילה שאלת פרופיל והתחלת פסק זמן (גם במקרה שגיאה)
        if chat_id and detect_profile_question_in_response(error_reply):
            start_profile_question_cooldown(chat_id)
        
        return {
            "bot_reply": error_reply, 
            "usage": {}, 
            "model": gpt_result["model"],
            "used_extra_emotion": use_extra_emotion,
            "filter_reason": filter_reason,
            "match_type": match_type,
            "error": str(e)
        }

async def get_main_response_with_timeout(full_messages, chat_id=None, message_id=None, update=None):
    """
    💎 שולח הודעה ל-gpt_a עם ניהול חכם של זמני תגובה
    """
    # שלב 1: קביעת מודל לפי פילטר חכם
    user_message = full_messages[-1]["content"] if full_messages else ""
    
    # 🆕 קבלת מספר ההודעות האמיתי מההיסטוריה
    chat_history_length = 0
    if chat_id:
        try:
            from chat_utils import get_user_stats
            user_stats = get_user_stats(chat_id)
            chat_history_length = user_stats.get("total_messages", 0)
        except Exception as e:
            logger.warning(f"שגיאה בקבלת מספר הודעות מההיסטוריה: {e}")
            # fallback לספירה מ-full_messages
            chat_history_length = len([msg for msg in full_messages if msg["role"] in ["user", "assistant"]])
    else:
        # אם אין chat_id, נשתמש בספירה מ-full_messages
        chat_history_length = len([msg for msg in full_messages if msg["role"] in ["user", "assistant"]])
    
    use_extra_emotion, filter_reason, match_type = should_use_extra_emotion_model(user_message, chat_history_length)
    
    # שלב 2: הפעלת GPT ב-thread נפרד עם timeout אמיתי
    gpt_start_time = time.time()
    
    try:
        # 🚨 הגדלת timeout ל-45 שניות (במקום 30) לטיפול ב-latency גבוה
        GPT_TIMEOUT_SECONDS = TimeoutConfig.GPT_PROCESSING_TIMEOUT
        
        # 🔧 תיקון קריטי: יישום timeout אמיתי במקום רק הגדרה
        # הרצת GPT ב-thread עם timeout מתקדם
        loop = asyncio.get_event_loop()
        gpt_task = loop.run_in_executor(
            None, 
            get_main_response_sync, 
            full_messages, 
            chat_id, 
            message_id, 
            use_extra_emotion, 
            filter_reason,
            match_type
        )
        
        # יישום timeout אמיתי עם asyncio.wait_for
        gpt_result = await asyncio.wait_for(gpt_task, timeout=GPT_TIMEOUT_SECONDS)
        
        gpt_duration = time.time() - gpt_start_time
        logger.info(f"⏱️ [GPT_TIMING] GPT הסתיים תוך {gpt_duration:.2f} שניות")
        
        # 🆕 בדיקה אם התשובה מכילה שאלת פרופיל והתחלת פסק זמן
        if chat_id and detect_profile_question_in_response(gpt_result["bot_reply"]):
            start_profile_question_cooldown(chat_id)
        
        # מדידה מפורטת של הזמנים
        print(f"📊 [TIMING_BREAKDOWN] Total GPT time: {gpt_duration:.3f}s")
        if 'gpt_pure_latency' in gpt_result:
            pure_latency = gpt_result.get('gpt_pure_latency', 0)
            total_time = gpt_result.get('total_time', 0)
            prep_time = gpt_result.get('prep_time', 0)
            processing_time = gpt_result.get('processing_time', 0)
            billing_time = gpt_result.get('billing_time', 0)
            
            print(f"📊 [TIMING_BREAKDOWN] Pure GPT latency: {pure_latency:.3f}s")
            print(f"📊 [TIMING_BREAKDOWN] Preparation: {prep_time:.3f}s | Processing: {processing_time:.3f}s | Billing: {billing_time:.3f}s")
            print(f"📊 [TIMING_BREAKDOWN] Total internal time: {total_time:.3f}s | Thread overhead: {gpt_duration - total_time:.3f}s")
        
        # שלב 3: שליחת הודעה זמנית אם GPT איטי
        if gpt_duration >= 8.0 and update:
            try:
                from message_handler import send_system_message
                temp_message_text = "⏳ אני עובד על תשובה בשבילך... זה מיד אצלך..."
                await send_system_message(update, chat_id, temp_message_text)
                logger.info(f"📤 [TEMP_MSG] נשלחה הודעה זמנית | chat_id={safe_str(chat_id)}", source="gpt_a_handler")
            except Exception as temp_err:
                logger.warning(f"⚠️ [TEMP_MSG] לא הצלחתי לשלוח הודעה זמנית: {temp_err}")
        
        return gpt_result
        
    except asyncio.TimeoutError:
        logger.error(f"[gpt_a] Timeout - GPT לא הגיב תוך {GPT_TIMEOUT_SECONDS} שניות")
        
        # שליחת התראה לאדמין על timeout
        send_error_notification(
            error_message=f"GPT timeout - לא הגיב תוך {GPT_TIMEOUT_SECONDS} שניות",
            chat_id=chat_id,
            user_msg=full_messages[-1]["content"] if full_messages else "לא זמין", 
            error_type="gpt_a_timeout_error"
        )
        
        return {
            "bot_reply": "מצטער, אני עסוק כרגע. נסה שוב בעוד כמה דקות 🔄", 
            "usage": {}, 
            "model": "timeout",
            "used_extra_emotion": use_extra_emotion,
            "filter_reason": filter_reason,
            "match_type": match_type,
            "error": "timeout"
        }
        
    except Exception as e:
        logger.error(f"[gpt_a] שגיאה כללית: {e}")
        
        # שליחת הודעת שגיאה טכנית לאדמין
        send_error_notification(
            error_message=f"שגיאה כללית ב-get_main_response_with_timeout: {str(e)}",
            chat_id=chat_id,
            user_msg=full_messages[-1]["content"] if full_messages else "לא זמין", 
            error_type="gpt_a_timeout_error"
        )
        
        # 🆕 בדיקה אם התשובה מכילה שאלת פרופיל והתחלת פסק זמן (גם במקרה שגיאה)
        error_reply = "מצטער, יש לי בעיה טכנית זמנית. העברתי את הפרטים לעומר שיבדוק את זה. נסה שוב בעוד כמה דקות 🔧"
        if chat_id and detect_profile_question_in_response(error_reply):
            start_profile_question_cooldown(chat_id)
        
        return {
            "bot_reply": "מצטער, יש לי בעיה טכנית זמנית. העברתי את הפרטים לעומר שיבדוק את זה. נסה שוב בעוד כמה דקות 🔧", 
            "usage": {}, 
            "model": "error",
            "used_extra_emotion": use_extra_emotion,
            "filter_reason": filter_reason,
            "match_type": match_type,
            "error": str(e)
        }

# פונקציה ישנה לתאימות לאחור
def get_main_response(full_messages, chat_id=None, message_id=None):
    """
    💎 גרסה סינכרונית ישנה - לתאימות לאחור
    """
    user_message = full_messages[-1]["content"] if full_messages else ""
    
    # 🆕 קבלת מספר ההודעות האמיתי מההיסטוריה
    chat_history_length = 0
    if chat_id:
        try:
            from chat_utils import get_user_stats
            user_stats = get_user_stats(chat_id)
            chat_history_length = user_stats.get("total_messages", 0)
        except Exception as e:
            logger.warning(f"שגיאה בקבלת מספר הודעות מההיסטוריה: {e}")
            # fallback לספירה מ-full_messages
            chat_history_length = len([msg for msg in full_messages if msg["role"] in ["user", "assistant"]])
    else:
        # אם אין chat_id, נשתמש בספירה מ-full_messages
        chat_history_length = len([msg for msg in full_messages if msg["role"] in ["user", "assistant"]])
    
    use_extra_emotion, filter_reason, match_type = should_use_extra_emotion_model(user_message, chat_history_length)
    
    return get_main_response_sync(full_messages, chat_id, message_id, use_extra_emotion, filter_reason, match_type)

def detect_profile_question_in_response(bot_reply: str) -> bool:
    """
    מזהה אם התשובה של הבוט מכילה שאלת פרופיל
    
    בודק:
    - האם יש שאלות עם סימן שאלה
    - האם יש מילות מפתח של שאלות פרופיל
    - האם יש טקסט מודגש (שאלות פרופיל נכתבות במודגש)
    
    Returns:
        bool: True אם זוהתה שאלת פרופיל, False אחרת
    """
    if not bot_reply:
        return False
    
    # מילות מפתח של שאלות פרופיל
    profile_keywords = [
        "גיל", "בן כמה", "בת כמה", "כמה שנים",
        "למי את/ה נמשך", "נטייה מינית", "הומו", "לסבית", "ביסקסואל",
        "מערכת יחסים", "זוגיות", "נשוי", "נשואה", "רווק", "רווקה",
        "דתי", "חילוני", "מסורתי", "אמונה", "דתיות",
        "בארון", "יציאה מהארון", "מי יודע", "מי לא יודע",
        "עבודה", "מקצוע", "תפקיד", "לימודים", "אוניברסיטה",
        "בעיה עיקרית", "קונפליקט", "מטרה", "יעד"
    ]
    
    # בדיקה 1: סימן שאלה
    has_question_mark = "?" in bot_reply
    
    # בדיקה 2: מילות מפתח
    has_profile_keywords = any(keyword in bot_reply for keyword in profile_keywords)
    
    # בדיקה 3: טקסט מודגש (שאלות פרופיל נכתבות במודגש)
    has_bold_text = "<b>" in bot_reply and "</b>" in bot_reply
    
    # בדיקה 4: משפטים שמתחילים במילות שאלה
    question_starters = ["מה", "איך", "מתי", "איפה", "למה", "האם", "האם את/ה", "האם אתה"]
    has_question_starters = any(starter in bot_reply for starter in question_starters)
    
    # אם יש לפחות 2 אינדיקטורים - זו כנראה שאלת פרופיל
    indicators = sum([has_question_mark, has_profile_keywords, has_bold_text, has_question_starters])
    
    is_profile_question = indicators >= 2
    
    if is_profile_question:
        logger.info(f"📊 [PROFILE_QUESTION] זוהתה שאלת פרופיל בתשובה | indicators={indicators} | has_question_mark={has_question_mark} | has_keywords={has_profile_keywords} | has_bold={has_bold_text} | has_starters={has_question_starters}")
    
    return is_profile_question

# 🆕 פונקציה לניקוי תשובות מטקסט טכני
def clean_bot_response(bot_reply: str) -> str:
    """
    מנקה את תשובת הבוט מטקסט טכני ומאחורי הקלעים
    """
    if not bot_reply:
        return bot_reply
    
    # ניקוי Self-correction ו-Thinking Process
    patterns_to_remove = [
        # Self-correction
        r'---\s*Self-correction.*?(?=\n\n|\n---|\Z)',
        r'---\s*Self-correction.*',
        
        # Thinking Process
        r'---\s*\[Thinking Process\].*?(?=\n\n|\n---|\Z)',
        r'---\s*\[Thinking Process\].*',
        
        # כל הטקסט אחרי ---
        r'---\s*.*?(?=\n\n|\Z)',
        r'---\s*.*',
        
        # הערות טכניות
        r'\(המערכת תמשיך כרגיל.*?\)',
        r'\(.*?המערכת.*?\)',
        
        # טקסט באנגלית טכני
        r'This adheres to the safety protocol\..*',
        r'The instruction states.*',
        r'While it\'s not a direct.*',
        r'Given the context.*',
        r'It\'s safer to err.*',
        
        # ניקוי שורות ריקות כפולות
        r'\n\s*\n\s*\n+',
    ]
    
    cleaned_reply = bot_reply
    
    for pattern in patterns_to_remove:
        cleaned_reply = re.sub(pattern, '', cleaned_reply, flags=re.DOTALL | re.IGNORECASE)
    
    # ניקוי שורות ריקות בתחילת ובסוף
    cleaned_reply = cleaned_reply.strip()
    
    # אם התשובה ריקה אחרי הניקוי, נחזיר תשובה ברירת מחדל
    if not cleaned_reply.strip():
        return "אני כאן איתך. מה עולה לך כרגע? 🤔"
    
    return cleaned_reply

# 🧠 Memory logging helper
def log_memory_usage(stage: str):
    """Log current memory usage"""
    try:
        import psutil
        import os
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        logger.info(f"[MEMORY] GPT-A {stage}: {memory_mb:.1f} MB")
        
        # 💾 שמירת מדידת זיכרון למסד הנתונים
        try:
            from db_manager import save_system_metrics
            save_system_metrics(
                metric_type="memory",
                memory_mb=memory_mb,
                memory_stage=f"gpt_a_{stage}",
                additional_data={"component": "gpt_a", "stage": stage}
            )
        except Exception as save_err:
            logger.warning(f"Could not save memory metrics: {save_err}")
            
    except Exception as e:
        logger.warning(f"Could not log memory usage: {e}")