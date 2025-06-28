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
import re
from prompts import SYSTEM_PROMPT
from config import GPT_MODELS, GPT_PARAMS, GPT_FALLBACK_MODELS
from gpt_utils import normalize_usage_dict, billing_guard, measure_llm_latency, calculate_gpt_cost
from notifications import alert_billing_issue, send_error_notification
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from message_handler import format_text_for_telegram  # for type checkers only
# מערכת ביצועים מבוטלת זמנית

# ייבוא הפילטר החכם
# ===============================
# 🎯 פילטר חכם לבחירת מודל AI
# ===============================

# סף מילים למודל מתקדם
LONG_MESSAGE_THRESHOLD = 50  # מעל 50 מילים = מודל מתקדם

def create_missing_fields_system_message(chat_id: str) -> str:
    """יוצר system message חכם עם שדות חסרים שכדאי לשאול עליהם"""
    try:
        from sheets_core import get_user_state
        from fields_dict import FIELDS_DICT
        
        profile_data = get_user_state(chat_id).get("profile_data", {})
        
        key_fields = ["age", "attracted_to", "relationship_type", "self_religious_affiliation", 
                     "closet_status", "pronoun_preference", "occupation_or_role", 
                     "self_religiosity_level", "primary_conflict", "goal_in_course"]
        
        missing = [FIELDS_DICT[f]["missing_question"] for f in key_fields
                  if f in FIELDS_DICT and not str(profile_data.get(f, "")).strip() 
                  and FIELDS_DICT[f].get("missing_question", "").strip()]
        
        if len(missing) >= 2:
            missing_text = ', '.join(missing[:4])
            return f"""פרטים שהמשתמש עדיין לא סיפר לך וכדאי לשאול אותו בעדינות וברגישות במטרה להכיר אותו יותר טוב: {missing_text}

תסביר לו את הרציונל, תסביר לו למה אתה שואל, תגיד לו שחשוב לך להכיר אותו כדי להתאים את עצמך אליו. תתעניין בו - תבחר אחד מהשאלות שנראית לך הכי מתאימה - ורק אם זה מרגיש לך מתאים אז תשאל אותו בעדינות וברגישות ותשלב את זה באלגנטיות. (את השאלות תעשה בכתב מודגש)"""
        return ""
        
    except Exception as e:
        logging.error(f"שגיאה ביצירת הודעת שדות חסרים: {e}")
        return ""

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
    שולח הודעה זמנית אחרי דיליי מסוים ומחזיר את האובייקט Message שלה

    השינוי (החזרת האובייקט עצמו ולא רק ה-id) מאפשר לנו למחוק את ההודעה בקלות באמצעות
    await temp_message.delete()‎ בלי ״ציד״ אחר ה-bot, מה שפגע במחיקה בעבר.
    """
    await asyncio.sleep(delay_seconds)
    try:
        temp_message = await update.message.reply_text("⏳ אני עובד על תשובה בשבילך... זה מיד אצלך...")
        logging.info(
            f"📤 [TEMP_MSG] נשלחה הודעה זמנית | chat_id={chat_id} | message_id={temp_message.message_id}"
        )
        return temp_message  # מחזירים את האובייקט עצמו
    except Exception as e:
        logging.error(f"❌ [TEMP_MSG] שגיאה בשליחת הודעה זמנית: {e}")
        return None

async def delete_temporary_message_and_send_new(update, temp_message, new_text):
    """
    מוחק את ההודעה הזמנית (אם קיימת) ושולח למשתמש את התשובה האמיתית.

    ✅ שיפור: משתמשים ב-temp_message.delete()‎ – בטוח ופשוט יותר, אין צורך להתאמץ להשיג את ה-bot.
    """
    from message_handler import format_text_for_telegram  # local import to avoid circular
    formatted_text = format_text_for_telegram(new_text)

    try:
        # מחיקת ההודעה הזמנית
        if temp_message is not None:
            try:
                await temp_message.delete()
                logging.info(
                    f"🗑️ [DELETE_MSG] הודעה זמנית נמחקה | chat_id={temp_message.chat_id} | message_id={temp_message.message_id}"
                )
            except Exception as del_err:
                logging.warning(
                    f"⚠️ [DELETE_MSG] לא הצלחתי למחוק את ההודעה הזמנית: {del_err} – ממשיך לשליחה"
                )

        # שליחת ההודעה החדשה
        await update.message.reply_text(formatted_text, parse_mode="HTML")
        logging.info(f"📤 [NEW_MSG] נשלחה הודעה חדשה | chat_id={temp_message.chat_id if temp_message else 'unknown'}")
        return True

    except Exception as send_err:
        logging.error(f"❌ [DELETE_MSG] כשל במחיקה/שליחה: {send_err}")
        return False

def get_main_response_sync(full_messages, chat_id=None, message_id=None, use_premium=True, filter_reason="", match_type="unknown"):
    """
    💎 מנוע gpt_a הראשי - גרסה סינכרונית
    """
    # מדידת זמן התחלה
    total_start_time = time.time()
    
    # שלב 1: הכנת ההודעות
    prep_start_time = time.time()
    
    # לא שולחים בקשה לשאלות רגישות אם מופעל extra_emotion (use_premium == True)
    if chat_id and not use_premium:
        missing_fields_message = create_missing_fields_system_message(chat_id)
        if missing_fields_message:
            full_messages.insert(1, {"role": "system", "content": missing_fields_message})
    
    prep_time = time.time() - prep_start_time
    print(f"⚡ [TIMING] Preparation time: {prep_time:.3f}s")
    
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

    # 🔍 [DEBUG] ניתוח מפורט של המבנה שנשלח ל-GPT
    print(f"\n🔍 [GPT_REQUEST_DEBUG] === DETAILED GPT REQUEST ANALYSIS ===")
    print(f"🤖 [MODEL] {model} | Premium: {use_premium} | Reason: {filter_reason}")
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
    
    # שלב 2: קריאה ל-GPT
    gpt_start_time = time.time()
    try:
        # 🔬 תזמון הטוקן הראשון - צריך להשתמש ב-streaming לזה
        with measure_llm_latency(model):
            response = litellm.completion(**completion_params)
        gpt_end_time = time.time()
        gpt_pure_latency = gpt_end_time - gpt_start_time
        
        # שלב 3: עיבוד התשובה
        processing_start_time = time.time()
        
        # 🔬 רישום הטוקן הראשון מבוטל זמנית
        
        bot_reply = response.choices[0].message.content.strip()
        
        # ניקוי תגי HTML לא נתמכים שהמודל עלול להחזיר
        # <br> תגים לא נתמכים ב-Telegram - צריך להמיר ל-\n
        bot_reply = bot_reply.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
        # גם ניקוי תגי br עם attributes שונים
        bot_reply = re.sub(r'<br\s*/?>', '\n', bot_reply)
        
        usage = normalize_usage_dict(response.usage, response.model)
        
        # הוספת נתוני עלות מדויקים ל-usage על סמך completion_response
        try:
            cost_info = calculate_gpt_cost(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cached_tokens=usage.get("cached_tokens", 0),
                model_name=response.model,
                completion_response=response
            )
            usage.update(cost_info)
        except Exception as _cost_e:
            logging.warning(f"[gpt_a] לא הצלחתי לחשב עלות usage: {_cost_e}")
        
        processing_time = time.time() - processing_start_time
        print(f"⚡ [TIMING] Processing time: {processing_time:.3f}s")
        
        print(f"✅ [GPT_RESPONSE_DEBUG] Received {len(bot_reply)} chars from {response.model}")
        print(f"⚡ [DETAILED_TIMING] GPT pure latency: {gpt_pure_latency:.3f}s | Model: {model}")
        
        # שלב 4: חישוב עלויות
        billing_start_time = time.time()
        
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
        
        billing_time = time.time() - billing_start_time
        print(f"⚡ [TIMING] Billing time: {billing_time:.3f}s")
        
        # סיכום זמנים
        total_time = time.time() - total_start_time
        print(f"📊 [TIMING_SUMMARY] Total: {total_time:.3f}s | GPT: {gpt_pure_latency:.3f}s | Prep: {prep_time:.3f}s | Processing: {processing_time:.3f}s | Billing: {billing_time:.3f}s")
        
        return {
            "bot_reply": bot_reply, 
            "usage": usage, 
            "model": response.model,
            "used_premium": use_premium,
            "filter_reason": filter_reason,
            "match_type": match_type,
            "gpt_pure_latency": gpt_pure_latency,
            "total_time": total_time,
            "prep_time": prep_time,
            "processing_time": processing_time,
            "billing_time": billing_time
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
    temp_message = None
    
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
        
        # שלב 4: ביטול או עדכון הודעה זמנית
        if temp_message_task:
            if not temp_message_task.done():
                # GPT הסתיים לפני שההודעה הזמנית נשלחה – מבטלים אותה
                temp_message_task.cancel()
                logging.info(
                    f"✅ [TIMING] GPT מהיר ({gpt_duration:.1f}s) - הודעה זמנית בוטלה לפני שנשלחה"
                )
            else:
                # ההודעה הזמנית נשלחה – מוחקים אותה ושולחים את התשובה
                temp_message = await temp_message_task
                if temp_message and update:
                    success = await delete_temporary_message_and_send_new(
                        update,
                        temp_message,
                        gpt_result["bot_reply"]
                    )
                    if success:
                        logging.info(
                            f"🔄 [TIMING] GPT איטי ({gpt_duration:.1f}s) - הודעה זמנית נמחקה ונשלחה חדשה"
                        )
                        gpt_result["message_already_sent"] = True
                    else:
                        # אם המחיקה/שליחה נכשלו, ננסה לשלוח חירום
                        logging.warning(
                            f"⚠️ [EMERGENCY] מחיקה/שליחה נכשלו, שולח הודעת חירום"
                        )
                        try:
                            emergency_text = (
                                f"מצטער על העיכוב. התשובה שלי:\n\n{gpt_result['bot_reply'][:1000]}..."
                                if len(gpt_result['bot_reply']) > 1000
                                else gpt_result["bot_reply"]
                            )
                            from message_handler import format_text_for_telegram  # local import to avoid circular
                            formatted_emergency_text = format_text_for_telegram(emergency_text)
                            await update.message.reply_text(
                                formatted_emergency_text, parse_mode="HTML"
                            )
                            gpt_result["message_already_sent"] = True
                        except Exception as emergency_error:
                            logging.error(
                                f"❌ [EMERGENCY] גם הודעת חירום נכשלה: {emergency_error}"
                            )
        
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

# פונקציית enforce_single_question הוסרה – הכל עובר דרך המודל בהתאם להנחיות בפרומט 