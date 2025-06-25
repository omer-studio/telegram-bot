"""
gpt_a_handler.py
----------------
מנוע gpt_a: לוגיקת התשובה הראשית (main response logic)
עם מנגנון הודעה זמנית ופילטר חכם לבחירת מודל
"""

import logging
from datetime import datetime
import json
import litellm
import asyncio
import threading
import time
from prompts import SYSTEM_PROMPT
from config import GPT_MODELS, GPT_PARAMS, GPT_FALLBACK_MODELS
from gpt_utils import normalize_usage_dict
from gpt_utils import billing_guard
from notifications import alert_billing_issue, send_error_notification
# מערכת ביצועים מבוטלת זמנית

# ייבוא הפילטר החכם
# ===============================
# 🎯 פילטר חכם לבחירת מודל AI
# ===============================

# סף מילים למודל מתקדם
LONG_MESSAGE_THRESHOLD = 50  # מעל 50 מילים = מודל מתקדם



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

# דפוסי ביטויים מורכבים (regex)
COMPLEX_PATTERNS = [
    # שאלות ודילמות כלליות
    r"מה\s+עושים\s+כש",           # "מה עושים כש..."
    r"איך\s+להתמודד\s+עם",        # "איך להתמודד עם..."
    r"צריך\s+עצה\s+ב",            # "צריך עצה ב..."
    r"לא\s+יודע\s+איך",           # "לא יודע איך..."
    r"מה\s+דעתך\s+על",            # "מה דעתך על..."
    r"איך\s+אתה\s+חושב",          # "איך אתה חושב..."
    
    # רגשות ומצבי נפש קשים
    r"לא\s+מרגיש\s+שלם",          # "לא מרגיש שלם"
    r"אני\s+תקוע",                # "אני תקוע"
    r"אני\s+שונא\s+את\s+עצמי",    # "אני שונא את עצמי"
    r"לא\s+מצליח\s+לאהוב",        # "לא מצליח לאהוב את עצמי"
    r"מה\s+עובר\s+עלי",           # "מה עובר עליי"
    r"מרגיש\s+אבוד",              # "מרגיש אבוד"
    r"מרגיש\s+תקוע",              # "מרגיש תקוע"
    r"לא\s+מרגיש\s+חלק",          # "לא מרגיש חלק מהכלל"
    
    # קבלה עצמית ומאבקים פנימיים
    r"לא\s+שלם\s+עם",             # "לא שלם עם עצמי", "לא שלם עם הנטייה"
    r"קושי\s+ל[ק|כ]בל",           # "קושי לקבל את עצמי" (עם תמיכה בטעויות כתיב)
    r"עדיין\s+לא\s+שלם",          # "עדיין לא שלם עם זה"
    r"משהו\s+לא\s+יושב",          # "משהו לא יושב טוב"
    r"התמודדות\s+עם",             # "התמודדות עם הזהות שלי"
    
    # זוגיות וחיפוש
    r"נשוי\s+ל",                  # "נשוי לאישה", "נשוי לבת זוג"
    r"לא\s+מצליח\s+למצוא",        # "לא מצליח למצוא זוגיות"
    r"רוצה\s+כבר\s+להיות",        # "רוצה כבר להיות אחרי זה"
    
    # ביטויי כניעה ויאוש
    r"יצאתי\s+אבל\s+לא\s+באמת",   # "יצאתי אבל לא באמת"
    r"לא\s+יודע\s+מה\s+עובר",     # "לא יודע מה עובר עליי"
    r"בא\s+לי\s+להיות\s+חופשי",   # "בא לי להיות חופשי"
]

# משתנה גלובלי לעקיבה אחר ההחלטות
filter_decisions_log = {
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

def should_use_premium_model(user_message, chat_history_length=0):
    """
    מחליט האם להשתמש במודל המתקדם או במהיר יותר
    
    קריטריונים למודל מתקדם:
    1. הודעה ארוכה (מעל X מילים)
    2. מילות מפתח רלוונטיות
    3. דפוסי ביטויים מורכבים
    
    Returns:
        tuple: (should_use_premium: bool, reason: str, match_type: str)
    """
    import re
    
    # בדיקת אורך הודעה
    word_count = len(user_message.split())
    if word_count > LONG_MESSAGE_THRESHOLD:
        logging.info(f"🎯 [PREMIUM_FILTER] הודעה ארוכה: {word_count} מילים -> מודל מתקדם")
        result = True, f"הודעה ארוכה ({word_count} מילים)", "length"
        log_filter_decision(result[2])
        return result
    
    # בדיקת מילות מפתח
    user_message_lower = user_message.lower()
    found_keywords = [keyword for keyword in PREMIUM_MODEL_KEYWORDS if keyword in user_message_lower]
    if found_keywords:
        logging.info(f"🎯 [PREMIUM_FILTER] מילות מפתח נמצאו: {found_keywords[:3]} -> מודל מתקדם")
        result = True, f"מילות מפתח: {', '.join(found_keywords[:3])}", "keywords"
        log_filter_decision(result[2])
        return result
    
    # בדיקת דפוסי ביטויים מורכבים
    for pattern in COMPLEX_PATTERNS:
        if re.search(pattern, user_message_lower):
            logging.info(f"🎯 [PREMIUM_FILTER] דפוס מורכב נמצא: {pattern} -> מודל מתקדם")
            result = True, f"דפוס מורכב זוהה", "pattern"
            log_filter_decision(result[2])
            return result
    
    # אחרת, מודל מהיר
    logging.info(f"🚀 [PREMIUM_FILTER] מקרה רגיל -> מודל מהיר")
    result = False, "מקרה רגיל - מודל מהיר", "default"
    log_filter_decision(result[2])
    return result

async def send_temporary_message_after_delay(update, chat_id, delay_seconds=5):
    """
    שולח הודעה זמנית אחרי דיליי מסוים ומחזיר את ה-message_id שלה
    """
    await asyncio.sleep(delay_seconds)
    try:
        temp_message = await update.message.reply_text("⏳ אני עובד על תשובה בשבילך... זה מיד אצלך...")
        logging.info(f"📤 [TEMP_MSG] נשלחה הודעה זמנית | chat_id={chat_id} | message_id={temp_message.message_id}")
        return temp_message.message_id
    except Exception as e:
        logging.error(f"❌ [TEMP_MSG] שגיאה בשליחת הודעה זמנית: {e}")
        return None

async def delete_temporary_message_and_send_new(update, chat_id, temp_message_id, new_text):
    """
    מוחק הודעה זמנית ושולח הודעה חדשה
    """
    try:
        # מחיקת ההודעה הזמנית
        await update.message.bot.delete_message(
            chat_id=chat_id,
            message_id=temp_message_id
        )
        logging.info(f"🗑️ [DELETE_MSG] הודעה זמנית נמחקה | chat_id={chat_id} | message_id={temp_message_id}")
        
        # שליחת הודעה חדשה
        await update.message.reply_text(new_text, parse_mode="HTML")
        logging.info(f"📤 [NEW_MSG] נשלחה הודעה חדשה | chat_id={chat_id}")
        return True
        
    except Exception as e:
        logging.error(f"❌ [DELETE_MSG] שגיאה במחיקת הודעה זמנית: {e}")
        # אם המחיקה נכשלה, נשלח הודעה חדשה בלי למחוק
        try:
            await update.message.reply_text(new_text, parse_mode="HTML")
            logging.info(f"📤 [FALLBACK_MSG] נשלחה הודעה חדשה (ללא מחיקה) | chat_id={chat_id}")
            return True
        except Exception as e2:
            logging.error(f"❌ [FALLBACK_MSG] שגיאה גם בהודעה חדשה: {e2}")
            return False

def get_main_response_sync(full_messages, chat_id=None, message_id=None, use_premium=True, filter_reason="", match_type="unknown"):
    """
    גרסה סינכרונית של get_main_response - לשימוש ב-thread
    כולל מדידת ביצועים לאבחון צוואר בקבוק
    """
    metadata = {"gpt_identifier": "gpt_a", "chat_id": chat_id, "message_id": message_id}
    params = GPT_PARAMS["gpt_a"]
    
    # 🔬 מדידת ביצועים מבוטלת זמנית
    measurement_id = None
    
    # בחירת מודל לפי הפילטר
    if use_premium:
        model = GPT_MODELS["gpt_a"]  # המודל המתקדם מ-config
        model_tier = "premium"
        logging.info(f"🎯 [MODEL_SELECTION] משתמש במודל מתקדם: {model} | סיבה: {filter_reason}")
    else:
        model = GPT_FALLBACK_MODELS["gpt_a"]  # המודל המהיר מ-config
        model_tier = "fast"
        logging.info(f"🚀 [MODEL_SELECTION] משתמש במודל מהיר: {model} | סיבה: {filter_reason}")
    
    completion_params = {
        "model": model,
        "messages": full_messages,
        "temperature": params["temperature"],
        "metadata": metadata,
        "store": True
    }
    
    # הוספת max_tokens רק אם הוא לא None
    if params["max_tokens"] is not None:
        completion_params["max_tokens"] = params["max_tokens"]
    
    try:
        import litellm
        
        # 🔬 תזמון הטוקן הראשון - צריך להשתמש ב-streaming לזה
        response = litellm.completion(**completion_params)
        
        # 🔬 רישום הטוקן הראשון מבוטל זמנית
        
        bot_reply = response.choices[0].message.content.strip()
        usage = normalize_usage_dict(response.usage, response.model)
        
        # 🔬 מדידת ביצועים מבוטלת זמנית
        
        # 📊 מעקב אחר חיוב
        if hasattr(response, 'usage'):
            try:
                cost_usd = litellm.completion_cost(completion_response=response)
                if cost_usd > 0:
                    billing_status = billing_guard.add_cost(cost_usd, response.model, "paid" if use_premium else "free")
                    
                    # התראות לאדמין
                    if billing_status["warnings"]:
                        for warning in billing_status["warnings"]:
                            logging.warning(f"[💰 תקציב] {warning}")
                    
                    # התראה בטלגרם אם צריך
                    status = billing_guard.get_current_status()
                    alert_billing_issue(
                        cost_usd=cost_usd,
                        model_name=response.model,
                        tier="paid" if use_premium else "free",
                        daily_usage=status["daily_usage"],
                        monthly_usage=status["monthly_usage"],
                        daily_limit=status["daily_limit"],
                        monthly_limit=status["monthly_limit"]
                    )
                
            except Exception as cost_error:
                logging.error(f"[💰] שגיאה בחישוב עלות: {cost_error}")
        
        return {
            "bot_reply": bot_reply, 
            "usage": usage, 
            "model": response.model,
            "used_premium": use_premium,
            "filter_reason": filter_reason,
            "match_type": match_type
        }
        
    except Exception as e:
        logging.error(f"[gpt_a] שגיאה במודל {model}: {e}")
        
        # 🔬 רישום שגיאה מבוטל זמנית
        
        # שליחת הודעת שגיאה טכנית לאדמין
        send_error_notification(
            error_message=f"שגיאה במנוע הראשי (gpt_a) - מודל: {model}, שגיאה: {str(e)}",
            chat_id=chat_id,
            user_msg=full_messages[-1]["content"] if full_messages else "לא זמין",
            error_type="gpt_a_engine_error"
        )
        
        return {
            "bot_reply": "מצטער, יש לי בעיה טכנית זמנית. העברתי את הפרטים לעומר שיבדוק את זה. נסה שוב בעוד כמה דקות 🔧", 
            "usage": {}, 
            "model": model,
            "used_premium": use_premium,
            "filter_reason": filter_reason,
            "match_type": match_type,
            "error": str(e)
        }

async def get_main_response_with_timeout(full_messages, chat_id=None, message_id=None, update=None):
    """
    💎 שולח הודעה ל-gpt_a עם ניהול חכם של זמני תגובה והודעות זמניות
    """
    # שלב 1: קביעת מודל לפי פילטר חכם
    user_message = full_messages[-1]["content"] if full_messages else ""
    chat_history_length = len([msg for msg in full_messages if msg["role"] in ["user", "assistant"]])
    
    use_premium, filter_reason, match_type = should_use_premium_model(user_message, chat_history_length)
    
    # שלב 2: הכנת טיימר להודעה זמנית
    temp_message_task = None
    temp_message_id = None
    
    if update and chat_id:
        # התחלת טיימר להודעה זמנית (אחרי 5 שניות)
        temp_message_task = asyncio.create_task(
            send_temporary_message_after_delay(update, chat_id, delay_seconds=5)
        )
    
    # שלב 3: הפעלת GPT ב-thread נפרד
    gpt_start_time = time.time()
    
    try:
        # הרצת GPT ב-thread כדי שלא לחסום את האירועים
        loop = asyncio.get_event_loop()
        gpt_result = await loop.run_in_executor(
            None, 
            get_main_response_sync, 
            full_messages, 
            chat_id, 
            message_id, 
            use_premium, 
            filter_reason,
            match_type
        )
        
        gpt_duration = time.time() - gpt_start_time
        logging.info(f"⏱️ [GPT_TIMING] GPT הסתיים תוך {gpt_duration:.2f} שניות")
        
        # שלב 4: ביטול או עדכון הודעה זמנית
        if temp_message_task:
            if not temp_message_task.done():
                # GPT הסתיים לפני 5 שניות - מבטלים הודעה זמנית
                temp_message_task.cancel()
                logging.info(f"✅ [TIMING] GPT מהיר ({gpt_duration:.1f}s) - הודעה זמנית בוטלה")
            else:
                # הודעה זמנית כבר נשלחה - מוחקים ושולחים חדשה
                temp_message_id = await temp_message_task
                if temp_message_id and update and chat_id:
                    success = await delete_temporary_message_and_send_new(
                        update, 
                        chat_id, 
                        temp_message_id, 
                        gpt_result["bot_reply"]
                    )
                    if success:
                        logging.info(f"🔄 [TIMING] GPT איטי ({gpt_duration:.1f}s) - הודעה זמנית נמחקה ונשלחה חדשה")
                        # מסמנים שההודעה כבר נשלחה דרך המחיקה והשליחה
                        gpt_result["message_already_sent"] = True
        
        return gpt_result
        
    except Exception as e:
        logging.error(f"[gpt_a] שגיאה כללית: {e}")
        
        # ביטול הודעה זמנית במקרה של שגיאה
        if temp_message_task and not temp_message_task.done():
            temp_message_task.cancel()
        
        # שליחת הודעת שגיאה טכנית לאדמין
        send_error_notification(
            error_message=f"שגיאה כללית ב-get_main_response_with_timeout: {str(e)}",
            chat_id=chat_id,
            user_msg=full_messages[-1]["content"] if full_messages else "לא זמין", 
            error_type="gpt_a_timeout_error"
        )
        
        return {
            "bot_reply": "מצטער, יש לי בעיה טכנית זמנית. העברתי את הפרטים לעומר שיבדוק את זה. נסה שוב בעוד כמה דקות 🔧", 
            "usage": {}, 
            "model": "error",
            "used_premium": use_premium,
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
    chat_history_length = len([msg for msg in full_messages if msg["role"] in ["user", "assistant"]])
    
    use_premium, filter_reason, match_type = should_use_premium_model(user_message, chat_history_length)
    
    return get_main_response_sync(full_messages, chat_id, message_id, use_premium, filter_reason, match_type) 