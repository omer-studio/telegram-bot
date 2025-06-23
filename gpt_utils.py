import logging

USD_TO_ILS = 3.7  # שער הדולר-שקל (יש לעדכן לפי הצורך)

def calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens=0, model_name='gpt-4o', usd_to_ils=USD_TO_ILS, completion_response=None):
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
    """
    if not usage:
        return {}
    if hasattr(usage, "__dict__"):
        usage = usage.__dict__
    result = dict(usage)
    result["model"] = model_name
    return result 