"""
gpt_b_handler.py
----------------
מנוע gpt_b: לוגיקת הסיכום (summary logic)
"""

import logging
import litellm
from prompts import BOT_REPLY_SUMMARY_PROMPT

def summarize_bot_reply(reply_text, chat_id=None, original_message_id=None):
    """
    שולח תשובה של הבוט ל-gpt_b ומקבל תמצית קצרה להיסטוריה.
    """
    try:
        metadata = {"gpt_identifier": "gpt_b", "chat_id": chat_id, "original_message_id": original_message_id}
        response = litellm.completion(
            model="gpt-4.1-nano",
            messages=[{"role": "system", "content": BOT_REPLY_SUMMARY_PROMPT}, {"role": "user", "content": reply_text}],
            temperature=1,
            metadata=metadata,
            store=True
        )
        summary = response.choices[0].message.content.strip()
        usage = response.usage.__dict__ if hasattr(response.usage, "__dict__") else {}
        return {"summary": summary, "usage": usage, "model": response.model}
    except Exception as e:
        logging.error(f"[gpt_b] Error: {e}")
        return {"summary": "[שגיאה בסיכום]", "usage": {}, "model": "gpt-4.1-nano"} 