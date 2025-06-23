"""
gpt_a_handler.py
----------------
מנוע gpt_a: לוגיקת התשובה הראשית (main response logic)
"""

import logging
from datetime import datetime
import json
import litellm
from prompts import BOT_MAIN_PROMPT

# פונקציה ראשית - שליחת הודעה ל-gpt_a

def get_main_response(full_messages, chat_id=None, message_id=None):
    """
    שולח הודעה ל-gpt_a הראשי ומחזיר את התשובה, כולל פירוט עלות וטוקנים.
    """
    try:
        metadata = {"gpt_identifier": "gpt_a", "chat_id": chat_id, "message_id": message_id}
        response = litellm.completion(
            model="gpt-4o",
            messages=full_messages,
            temperature=1,
            metadata=metadata,
            store=True
        )
        bot_reply = response.choices[0].message.content.strip()
        usage = response.usage.__dict__ if hasattr(response.usage, "__dict__") else {}
        return {"bot_reply": bot_reply, "usage": usage, "model": response.model}
    except Exception as e:
        logging.error(f"[gpt_a] Error: {e}")
        return {"bot_reply": "[שגיאה במנוע הראשי]", "usage": {}, "model": "gpt-4o"} 