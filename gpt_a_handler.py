"""
gpt_a_handler.py
----------------
מנוע gpt_a: לוגיקת התשובה הראשית (main response logic)
"""

import logging
from datetime import datetime
import json
import litellm
from prompts import SYSTEM_PROMPT
from config import GPT_MODELS, GPT_PARAMS
from gpt_utils import normalize_usage_dict
from gpt_utils import billing_guard
from notifications import alert_billing_issue

# פונקציה ראשית - שליחת הודעה ל-gpt_a

def get_main_response(full_messages, chat_id=None, message_id=None):
    """
    💎 שולח הודעה ל-gpt_a עם Gemini 2.5 Pro (הטוב ביותר).
    פשוט וישיר - תמיד המודל הטוב ביותר.
    """
    metadata = {"gpt_identifier": "gpt_a", "chat_id": chat_id, "message_id": message_id}
    params = GPT_PARAMS["gpt_a"]
    model = GPT_MODELS["gpt_a"]  # gemini/gemini-2.5-pro
    
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
                    billing_status = billing_guard.add_cost(cost_usd, response.model, "paid")
                    
                    # התראות לאדמין
                    if billing_status["warnings"]:
                        for warning in billing_status["warnings"]:
                            logging.warning(f"[💰 תקציב] {warning}")
                    
                    # התראה בטלגרם אם צריך
                    status = billing_guard.get_current_status()
                    alert_billing_issue(
                        cost_usd=cost_usd,
                        model_name=response.model,
                        tier="paid",
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
            "model": response.model
        }
        
    except Exception as e:
        logging.error(f"[gpt_a] שגיאה: {e}")
        return {
            "bot_reply": "[שגיאה במנוע הראשי - נסה שוב]", 
            "usage": {}, 
            "model": model
        } 