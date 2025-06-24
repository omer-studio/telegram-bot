import logging

USD_TO_ILS = 3.7  # שער הדולר-שקל (יש לעדכן לפי הצורך)

def safe_get_usage_value(obj, attr_name, default=0):
    """
    מחלץ ערך מusage object באופן בטוח, כולל תמיכה בwrappers של OpenAI API החדש
    """
    try:
        if hasattr(obj, attr_name):
            value = getattr(obj, attr_name)
            # אם זה wrapper object, ננסה להמיר אותו למספר
            if hasattr(value, '__dict__'):
                return default
            return int(value) if value is not None else default
        return default
    except (ValueError, TypeError, AttributeError):
        return default

def calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens=0, model_name=None, usd_to_ils=USD_TO_ILS, completion_response=None):
    if model_name is None:
        from config import GPT_MODELS
        model_name = GPT_MODELS["gpt_a"]
    """
    מחשב את העלות של שימוש ב-gpt לפי מספר הטוקנים והמודל.
    משתמש אך ורק ב-LiteLLM עם completion_response.
    מחזיר רק את העלות הכוללת (cost_total) כפי שמחושב ע"י LiteLLM, בלי פילוח ידני.
    """
    print(f"[DEBUG] 🔥 calculate_gpt_cost CALLED! 🔥")
    print(f"[DEBUG] Input: prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}, cached_tokens={cached_tokens}, model_name={model_name}")
    print(f"[DEBUG] calculate_gpt_cost - Model: {model_name}, Tokens: {prompt_tokens}p + {completion_tokens}c + {cached_tokens}cache")
    try:
        import litellm
        if completion_response:
            print(f"[DEBUG] Using completion_response for cost calculation")
            cost_usd = litellm.completion_cost(completion_response=completion_response)
            print(f"[DEBUG] LiteLLM completion_cost returned: {cost_usd}")
        else:
            print(f"[DEBUG] No completion_response provided, cannot calculate cost with LiteLLM")
            cost_usd = 0.0
        cost_ils = cost_usd * usd_to_ils
        cost_agorot = cost_ils * 100
        result = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_tokens": cached_tokens,
            "cost_total": cost_usd,
            "cost_total_ils": cost_ils,
            "cost_agorot": cost_agorot,
            "model": model_name
        }
        print(f"[DEBUG] calculate_gpt_cost returning: {result}")
        return result
    except Exception as e:
        print(f"[ERROR] calculate_gpt_cost failed: {e}")
        import traceback
        print(f"[ERROR] Full traceback: {traceback.format_exc()}")
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_tokens": cached_tokens,
            "cost_total": 0.0,
            "cost_total_ils": 0.0,
            "cost_agorot": 0.0,
            "model": model_name
        }

def normalize_usage_dict(usage, model_name=""):
    """
    מנרמל מילון usage של gpt לפורמט אחיד (לוגים/דוחות).
    מטפל בwrappers חדשים של OpenAI API.
    """
    if not usage:
        return {}
    
    # אם זה usage object של OpenAI, נמיר אותו בבטחה
    if hasattr(usage, '__dict__'):
        try:
            result = {
                "prompt_tokens": safe_get_usage_value(usage, 'prompt_tokens', 0),
                "completion_tokens": safe_get_usage_value(usage, 'completion_tokens', 0),
                "total_tokens": safe_get_usage_value(usage, 'total_tokens', 0),
            }
            
            # נחפש cached_tokens במקומות השונים שהם יכולים להיות
            cached_tokens = 0
            if hasattr(usage, 'prompt_tokens_details'):
                cached_tokens = safe_get_usage_value(usage.prompt_tokens_details, 'cached_tokens', 0)
            elif hasattr(usage, 'cached_tokens'):
                cached_tokens = safe_get_usage_value(usage, 'cached_tokens', 0)
            
            result["cached_tokens"] = cached_tokens
            result["model"] = model_name
            return result
        except Exception as e:
            print(f"[DEBUG] שגיאה בנירמול usage: {e}")
            # fallback לנירמול פשוט
            return {"model": model_name, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}
    
    # אם זה כבר dict, פשוט נוסיף את המודל
    if isinstance(usage, dict):
        result = dict(usage)
        result["model"] = model_name
        return result
    
    # fallback
    return {"model": model_name, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0} 