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

# פונקציה ראשית - שליחת הודעה ל-gpt_a

def get_main_response(full_messages, chat_id=None, message_id=None):
    """
    שולח הודעה ל-gpt_a הראשי ומחזיר את התשובה, כולל פירוט עלות וטוקנים.
    """
    try:
        metadata = {"gpt_identifier": "gpt_a", "chat_id": chat_id, "message_id": message_id}
        params = GPT_PARAMS["gpt_a"]
        model = GPT_MODELS["gpt_a"]
        
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
        
        response = litellm.completion(**completion_params)
        bot_reply = response.choices[0].message.content.strip()
        usage = response.usage.__dict__ if hasattr(response.usage, "__dict__") else {}
        return {"bot_reply": bot_reply, "usage": usage, "model": response.model}
    except Exception as e:
        logging.error(f"[gpt_a] Error: {e}")
        return {"bot_reply": "[שגיאה במנוע הראשי]", "usage": {}, "model": GPT_MODELS["gpt_a"]} 