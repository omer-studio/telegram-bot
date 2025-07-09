"""
gpt_d_handler.py
----------------
מנוע gpt_d: עדכון פרופיל חכם עם מיזוג נתונים
"""

from simple_logger import logger
from datetime import datetime
import json
import time
import lazy_litellm as litellm
import asyncio
import traceback
from prompts import build_profile_merge_prompt
from config import GPT_MODELS, GPT_PARAMS, should_log_data_extraction_debug
from gpt_utils import normalize_usage_dict, measure_llm_latency, calculate_gpt_cost, extract_json_from_text
from user_friendly_errors import safe_str

def merge_profile_data(existing_profile, new_extracted_fields, chat_id, message_id=None):
    """
    מיזוג נתונים חדשים עם פרופיל קיים באמצעות GPT-D
    """
    start_time = time.time()
    
    safe_chat_id = safe_str(chat_id)
    metadata = {"gpt_identifier": "gpt_d", "chat_id": safe_chat_id, "message_id": message_id}
    params = GPT_PARAMS["gpt_d"]
    model = GPT_MODELS["gpt_d"]
    
    # הכנת הפרומפט
    merge_prompt = build_profile_merge_prompt(existing_profile, new_extracted_fields)
    
    completion_params = {
        "model": model,
        "messages": [{"role": "user", "content": merge_prompt}],
        "temperature": params["temperature"],
        "metadata": metadata
    }
    
    # הוספת max_tokens רק אם הוא לא None
    if params["max_tokens"] is not None:
        completion_params["max_tokens"] = params["max_tokens"]
    
    try:
        with measure_llm_latency(model):
            response = litellm.completion(**completion_params)
        
        content_raw = response.choices[0].message.content.strip()
        content = extract_json_from_text(content_raw)
        
        usage = normalize_usage_dict(response.usage, response.model)
        
        # ניסיון לפרס JSON
        try:
            if content and content.strip():
                content_clean = content.strip()
                if content_clean.startswith("{") and content_clean.endswith("}"):
                    merged_profile = json.loads(content_clean)
                    if not isinstance(merged_profile, dict):
                        logger.warning(f"[GPT_D] JSON parsed but not a dict: {type(merged_profile)}", source="gpt_d_handler")
                        merged_profile = existing_profile
                else:
                    logger.warning(f"[GPT_D] Content doesn't look like JSON: {content_clean[:100]}...", source="gpt_d_handler")
                    merged_profile = existing_profile
            else:
                merged_profile = existing_profile
        except json.JSONDecodeError as e:
            logger.error(f"[GPT_D] JSON decode error: {e} | Content: {content[:200] if content else 'None'}...", source="gpt_d_handler")
            merged_profile = existing_profile
        except Exception as e:
            logger.error(f"[GPT_D] Unexpected error parsing JSON: {e} | Content: {content[:200] if content else 'None'}...", source="gpt_d_handler")
            merged_profile = existing_profile
        
        # הדפסת מידע חשוב על מיזוג נתונים
        if should_log_data_extraction_debug():
            print(f"🔄 [GPT-D] מיזוג הושלם: {len(merged_profile)} שדות")
            print(f"📊 [GPT-D] נתונים קיימים: {len(existing_profile)} שדות")
            print(f"📊 [GPT-D] נתונים חדשים: {len(new_extracted_fields)} שדות")
        
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
            logger.warning(f"[gpt_d] Cost calc failed: {_cost_e}", source="gpt_d_handler")
        
        result = {"merged_profile": merged_profile, "usage": usage, "model": response.model}
        
        # רישום ל-JSONL
        try:
            from gpt_jsonl_logger import GPTJSONLLogger
            response_data = {
                "id": getattr(response, "id", ""),
                "choices": [{"message": {"content": content_raw, "role": "assistant"}}],
                "usage": usage,
                "model": response.model
            }
            GPTJSONLLogger.log_gpt_call(
                log_path="data/openai_calls.jsonl",
                gpt_type="D",
                request=completion_params,
                response=response_data,
                cost_usd=usage.get("cost_total", 0),
                extra={"chat_id": safe_chat_id, "message_id": message_id}
            )
        except Exception as log_exc:
            print(f"[LOGGING_ERROR] Failed to log GPT-D call: {log_exc}")
        
        return result
        
    except Exception as e:
        logger.error(f"[gpt_d] Error: {e}", source="gpt_d_handler")
        return {"merged_profile": existing_profile, "usage": {}, "model": model}

def combine_usage_dicts(usage1, usage2):
    """מאחד שני dictionaries של usage"""
    combined = {}
    combined.update(usage1)
    for k, v in usage2.items():
        if k in combined:
            combined[k] += v
        else:
            combined[k] = v
    return combined

# ---------------------------------------------------------------------------
# 🧵 Async helper – run in thread & persist changes
# ---------------------------------------------------------------------------

def _run_profile_merge_and_persist(chat_id: str, user_message: str, interaction_id=None, gpt_c_result=None):
    """
    Executes the profile merge and persistence in a thread-safe manner.
    1. Loads the existing profile for the given chat_id (safe – returns {}).
    2. Uses GPT-D to merge the existing profile with the new extracted fields.
    3. Persists the merged profile to the database.
    
    Args:
        chat_id (str): The user's chat ID.
        user_message (str): The user's message.
        interaction_id (str, optional): The interaction ID.
        gpt_c_result (dict, optional): The result from GPT-C.
    """
    safe_chat_id = safe_str(chat_id)
    try:
        from profile_utils import get_user_profile_fast, update_user_profile_fast
        
        # Load existing profile
        existing_profile = get_user_profile_fast(safe_chat_id)
        
        # Only proceed if we have GPT-C results
        if gpt_c_result and isinstance(gpt_c_result, dict):
            extracted_fields = gpt_c_result.get("extracted_fields", {})
            
            # Check if we need GPT-D (only if there are conflicting fields)
            if existing_profile and extracted_fields:
                for field, new_value in extracted_fields.items():
                    if field in existing_profile and existing_profile[field] and existing_profile[field] != new_value:
                        # We have a conflict - use GPT-D to merge
                        merge_result = merge_profile_data(existing_profile, extracted_fields, safe_chat_id, interaction_id)
                        updated_profile = merge_result["merged_profile"]
                        break
                else:
                    # No conflicts - simple merge
                    updated_profile = existing_profile.copy()
                    updated_profile.update(extracted_fields)
            else:
                # Simple merge
                updated_profile = (existing_profile or {}).copy()
                updated_profile.update(extracted_fields)
            
            # Persist to database
            update_user_profile_fast(safe_chat_id, updated_profile)
        
    except Exception as exc:
        logger.error(f"[GPT_D] Error in profile merge/persist for {safe_chat_id}: {exc}\n{traceback.format_exc()}", source="gpt_d_handler")

def smart_update_profile_with_gpt_d_async(chat_id: str, user_message: str, interaction_id=None, gpt_c_result=None):
    """Public async wrapper – accepts chat_id (not profile).
    
    This function was originally designed to accept an existing profile,
    but in practice, the only call-site (message_handler.py) actually passed chat_id.
    This change makes the function signature consistent with its actual usage.
    
    Args:
        chat_id (str): The user's chat ID.
        user_message (str): The user's message.
        interaction_id (str, optional): The interaction ID.
        gpt_c_result (dict, optional): The result from GPT-C.
    """
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, _run_profile_merge_and_persist, safe_str(chat_id), user_message, interaction_id, gpt_c_result) 