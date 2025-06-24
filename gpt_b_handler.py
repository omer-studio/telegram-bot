"""
gpt_b_handler.py
----------------
מנוע gpt_b: לוגיקת הסיכום (summary logic)
"""

import logging
import litellm
from prompts import BOT_REPLY_SUMMARY_PROMPT
from config import GPT_MODELS, GPT_PARAMS

def summarize_bot_reply(reply_text, chat_id=None, original_message_id=None):
    """
    שולח תשובה של הבוט ל-gpt_b ומקבל תמצית קצרה להיסטוריה.
    """
    try:
        metadata = {"gpt_identifier": "gpt_b", "chat_id": chat_id, "original_message_id": original_message_id}
        params = GPT_PARAMS["gpt_b"]
        model = GPT_MODELS["gpt_b"]
        
        completion_params = {
            "model": model,
            "messages": [{"role": "system", "content": BOT_REPLY_SUMMARY_PROMPT}, {"role": "user", "content": reply_text}],
            "temperature": params["temperature"],
            "metadata": metadata,
            "store": True
        }
        
        # הוספת max_tokens רק אם הוא לא None
        if params["max_tokens"] is not None:
            completion_params["max_tokens"] = params["max_tokens"]
        
        response = litellm.completion(**completion_params)
        summary = response.choices[0].message.content.strip()
        usage = response.usage.__dict__ if hasattr(response.usage, "__dict__") else {}
        return {"summary": summary, "usage": usage, "model": response.model}
    except Exception as e:
        logging.error(f"[gpt_b] Error: {e}")
        return {"summary": "[שגיאה בסיכום]", "usage": {}, "model": GPT_MODELS["gpt_b"]} 