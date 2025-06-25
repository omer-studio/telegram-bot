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
from config import GPT_MODELS, GPT_PARAMS
from gpt_utils import normalize_usage_dict
from gpt_utils import billing_guard
from notifications import alert_billing_issue

# ייבוא הפילטר החכם
from smart_model_filter import should_use_premium_model

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

async def edit_temporary_message(update, chat_id, temp_message_id, new_text):
    """
    מחליף הודעה זמנית בתשובה האמיתית
    """
    try:
        await update.message.bot.edit_message_text(
            chat_id=chat_id,
            message_id=temp_message_id,
            text=new_text,
            parse_mode="HTML"
        )
        logging.info(f"✅ [EDIT_MSG] הודעה זמנית הוחלפה | chat_id={chat_id} | message_id={temp_message_id}")
        return True
    except Exception as e:
        logging.error(f"❌ [EDIT_MSG] שגיאה בעריכת הודעה זמנית: {e}")
        # אם העריכה נכשלה, נשלח הודעה חדשה
        try:
            await update.message.reply_text(new_text, parse_mode="HTML")
            logging.info(f"📤 [FALLBACK_MSG] נשלחה הודעה חדשה במקום עריכה | chat_id={chat_id}")
            return True
        except Exception as e2:
            logging.error(f"❌ [FALLBACK_MSG] שגיאה גם בהודעה חדשה: {e2}")
            return False

def get_main_response_sync(full_messages, chat_id=None, message_id=None, use_premium=True, filter_reason=""):
    """
    גרסה סינכרונית של get_main_response - לשימוש ב-thread
    """
    metadata = {"gpt_identifier": "gpt_a", "chat_id": chat_id, "message_id": message_id}
    params = GPT_PARAMS["gpt_a"]
    
    # בחירת מודל לפי הפילטר
    if use_premium:
        model = GPT_MODELS["gpt_a"]  # gemini/gemini-2.5-pro
        logging.info(f"🎯 [MODEL_SELECTION] משתמש במודל מתקדם: {model} | סיבה: {filter_reason}")
    else:
        model = "gemini/gemini-1.5-flash"  # מהיר ואיכותי
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
        response = litellm.completion(**completion_params)
        
        bot_reply = response.choices[0].message.content.strip()
        usage = normalize_usage_dict(response.usage, response.model)
        
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
            "filter_reason": filter_reason
        }
        
    except Exception as e:
        logging.error(f"[gpt_a] שגיאה במודל {model}: {e}")
        return {
            "bot_reply": "[שגיאה במנוע הראשי - נסה שוב]", 
            "usage": {}, 
            "model": model,
            "used_premium": use_premium,
            "filter_reason": filter_reason,
            "error": str(e)
        }

async def get_main_response_with_timeout(full_messages, chat_id=None, message_id=None, update=None):
    """
    💎 שולח הודעה ל-gpt_a עם ניהול חכם של זמני תגובה והודעות זמניות
    """
    # שלב 1: קביעת מודל לפי פילטר חכם
    user_message = full_messages[-1]["content"] if full_messages else ""
    chat_history_length = len([msg for msg in full_messages if msg["role"] in ["user", "assistant"]])
    
    use_premium, filter_reason = should_use_premium_model(user_message, chat_history_length)
    
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
            filter_reason
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
                # הודעה זמנית כבר נשלחה - מחליפים אותה
                temp_message_id = await temp_message_task
                if temp_message_id and update and chat_id:
                    success = await edit_temporary_message(
                        update, 
                        chat_id, 
                        temp_message_id, 
                        gpt_result["bot_reply"]
                    )
                    if success:
                        logging.info(f"🔄 [TIMING] GPT איטי ({gpt_duration:.1f}s) - הודעה זמנית הוחלפה")
                        # מסמנים שההודעה כבר נשלחה דרך העריכה
                        gpt_result["message_already_sent"] = True
        
        return gpt_result
        
    except Exception as e:
        logging.error(f"[gpt_a] שגיאה כללית: {e}")
        
        # ביטול הודעה זמנית במקרה של שגיאה
        if temp_message_task and not temp_message_task.done():
            temp_message_task.cancel()
        
        return {
            "bot_reply": "[שגיאה במנוע הראשי - נסה שוב]", 
            "usage": {}, 
            "model": "error",
            "used_premium": use_premium,
            "filter_reason": filter_reason,
            "error": str(e)
        }

# פונקציה ישנה לתאימות לאחור
def get_main_response(full_messages, chat_id=None, message_id=None):
    """
    💎 גרסה סינכרונית ישנה - לתאימות לאחור
    """
    user_message = full_messages[-1]["content"] if full_messages else ""
    chat_history_length = len([msg for msg in full_messages if msg["role"] in ["user", "assistant"]])
    
    use_premium, filter_reason = should_use_premium_model(user_message, chat_history_length)
    
    return get_main_response_sync(full_messages, chat_id, message_id, use_premium, filter_reason) 