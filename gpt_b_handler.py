"""
gpt_b_handler.py
----------------
מנוע gpt_b: יוצר סיכומים קצרים להיסטוריה
משתמש ב-Gemini 1.5 Pro (חינמי) - ללא צורך ב-fallback.
"""

import logging
from datetime import datetime
import json
import lazy_litellm as litellm
from prompts import BOT_REPLY_SUMMARY_PROMPT
from config import GPT_MODELS, GPT_PARAMS
from gpt_utils import normalize_usage_dict, calculate_gpt_cost

def get_summary(user_msg, bot_reply, chat_id=None, message_id=None):
    """
    יוצר סיכום קצר של הקשר השיחה עבור היסטוריה
    משתמש ב-Gemini 1.5 Pro (חינמי) - ללא צורך ב-fallback.
    """
    try:
        metadata = {"gpt_identifier": "gpt_b", "chat_id": chat_id, "message_id": message_id}
        params = GPT_PARAMS["gpt_b"]
        model = GPT_MODELS["gpt_b"]
        
        messages = [
            {"role": "system", "content": BOT_REPLY_SUMMARY_PROMPT},
            {"role": "user", "content": bot_reply}
        ]
        
        completion_params = {
            "model": model,
            "messages": messages,
            "temperature": params["temperature"],
            "metadata": metadata
        }
        
        # הוספת max_tokens רק אם הוא לא None
        if params["max_tokens"] is not None:
            completion_params["max_tokens"] = params["max_tokens"]
        
        from gpt_utils import measure_llm_latency
        with measure_llm_latency(model):
            response = litellm.completion(**completion_params)
        summary = response.choices[0].message.content.strip()
        usage = normalize_usage_dict(response.usage, response.model)
        # הוספת חישוב עלות ל-usage
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
            logging.warning(f"[gpt_b] Cost calc failed: {_cost_e}")
        result = {"summary": summary, "usage": usage, "model": response.model}
        try:
            from gpt_jsonl_logger import GPTJSONLLogger
            # בניית response מלא עם כל המידע הנדרש
            response_data = {
                "id": getattr(response, "id", ""),
                "choices": [
                    {
                        "message": {
                            "content": summary,
                            "role": "assistant"
                        }
                    }
                ],
                "usage": usage,
                "model": response.model
            }
            GPTJSONLLogger.log_gpt_call(
                log_path="data/openai_calls.jsonl",
                gpt_type="B",
                request=completion_params,
                response=response_data,
                cost_usd=usage.get("cost_total", 0),
                extra={"chat_id": chat_id, "message_id": message_id}
            )
        except Exception as log_exc:
            print(f"[LOGGING_ERROR] Failed to log GPT-B call: {log_exc}")
        return result
        
    except Exception as e:
        logging.error(f"[gpt_b] Error: {e}")
        return {"summary": f"[סיכום: {user_msg[:50]}...]", "usage": {}, "model": model} 