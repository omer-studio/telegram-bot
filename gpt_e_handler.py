"""
gpt_e_handler.py
----------------
מנוע gpt_e: עדכון פרופיל משתמש מקיף על סמך היסטוריית שיחות
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

import lazy_litellm as litellm

from simple_logger import logger
from config import (
    GPT_MODELS,
    GPT_PARAMS,
    should_log_data_extraction_debug,
    should_log_gpt_cost_debug
)

# קבועים מקומיים
GPT_E_RUN_EVERY_MESSAGES = 10  # כל כמה הודעות להפעיל GPT-E
GPT_E_SCAN_LAST_MESSAGES = 15  # כמה הודעות אחרונות לסרוק
from gpt_utils import normalize_usage_dict, calculate_gpt_cost, extract_json_from_text
from prompts import build_profile_extraction_enhanced_prompt
from db_manager import safe_str

# יבוא מותנה לפונקציות DB
try:
    from profile_utils import get_user_summary_fast
    from db_wrapper import update_user_summary_wrapper as update_user_summary_fast, reset_gpt_c_run_count_wrapper
    from chat_utils import get_chat_history_messages, get_user_stats_and_history
except ImportError as e:
    logger.error(f"[gpt_e] Failed to import required modules: {e}", source="gpt_e_handler")


def should_run_gpt_e(chat_id: str, total_messages: int) -> bool:
    """
    בודק אם צריך להריץ gpt_e עבור משתמש מסוים
    :param chat_id: מזהה המשתמש
    :param total_messages: מספר ההודעות הכולל של המשתמש
    :return: True אם צריך להריץ, False אחרת
    """
    safe_chat_id = safe_str(chat_id)
    
    # הפעלה כל X הודעות
    if total_messages > 0 and total_messages % GPT_E_RUN_EVERY_MESSAGES == 0:
        logger.info(f"[gpt_e] Should run for chat_id={safe_chat_id} (every {GPT_E_RUN_EVERY_MESSAGES} messages)", source="gpt_e_handler")
        return True
    
    return False


async def run_gpt_e(chat_id: str) -> Dict[str, Any]:
    """
    מריץ gpt_e עבור משתמש מסוים
    :param chat_id: מזהה המשתמש
    :return: תוצאת הרצה
    """
    safe_chat_id = safe_str(chat_id)
    start_time = datetime.now()
    
    logger.info(f"[gpt_e] Starting run_gpt_e for chat_id={safe_chat_id} at {start_time.isoformat()}", source="gpt_e_handler")
    
    try:
        # שלב 1: אספת היסטוריית שיחות
        logger.info(f"[gpt_e] Fetching chat history for chat_id={safe_chat_id}", source="gpt_e_handler")
        chat_history = get_chat_history_messages(safe_chat_id, limit=GPT_E_SCAN_LAST_MESSAGES)
        
        if not chat_history:
            logger.warning(f"[gpt_e] No chat history found for chat_id={safe_chat_id}", source="gpt_e_handler")
            return {"success": False, "error": "No chat history found"}
        
        # שלב 2: אספת פרופיל נוכחי
        logger.info(f"[gpt_e] Fetching current profile for chat_id={safe_chat_id}", source="gpt_e_handler")
        current_profile = get_user_summary_fast(safe_chat_id)
        
        if should_log_data_extraction_debug():
            print(f"[DEBUG] gpt_e_profile | chat={safe_chat_id} | profile='{current_profile[:35]}{'...' if len(current_profile) > 35 else ''}'")
        
        if not current_profile:
            logger.info(f"[gpt_e] No existing profile found for chat_id={safe_chat_id}", source="gpt_e_handler")
            current_profile = ""
        
        # שלב 3: בניית פרומפט ושליחת בקשה ל-GPT
        logger.info(f"[gpt_e] Sending request to GPT for chat_id={safe_chat_id}", source="gpt_e_handler")
        
        # בניית הפרומפט
        metadata = {"gpt_identifier": "gpt_e", "chat_id": safe_chat_id}
        params = GPT_PARAMS["gpt_e"]
        model = GPT_MODELS["gpt_e"]
        
        prompt = f"היסטוריית השיחה: {json.dumps(chat_history, ensure_ascii=False)}\n\nפרופיל נוכחי: {current_profile}\n\nעדכן את הפרופיל על סמך ההיסטוריה."
        
        completion_params = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": params["temperature"],
            "metadata": metadata
        }
        
        # הוספת max_tokens רק אם הוא לא None
        if params["max_tokens"] is not None:
            completion_params["max_tokens"] = params["max_tokens"]
        
        # שליחת בקשה ל-GPT
        response = litellm.completion(**completion_params)
        
        if not response.choices or not response.choices[0].message.content:
            logger.error(f"[gpt_e] Empty response content from GPT for chat_id={safe_chat_id}", source="gpt_e_handler")
            return {"success": False, "error": "Empty response from GPT"}
        
        content_raw = response.choices[0].message.content.strip()
        content = extract_json_from_text(content_raw)
        usage = normalize_usage_dict(response.usage, response.model)
        
        # הוספת חישוב עלות
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
            logger.warning(f"[gpt_e] Cost calc failed: {_cost_e}", source="gpt_e_handler")
        
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
                gpt_type="E",
                request=completion_params,
                response=response_data,
                cost_usd=usage.get("cost_total", 0),
                extra={"chat_id": safe_chat_id}
            )
        except Exception as log_exc:
            print(f"[LOGGING_ERROR] Failed to log GPT-E call: {log_exc}")
        
        # שלב 4: עיבוד תוצאות
        if not content or not content.strip():
            logger.error(f"[gpt_e] Empty response from GPT for chat_id={safe_chat_id}", source="gpt_e_handler")
            return {"success": False, "error": "Empty response from GPT"}
        
        # ניסיון לפרס JSON
        try:
            if content.strip().startswith("{") and content.strip().endswith("}"):
                changes = json.loads(content.strip())
            else:
                logger.warning(f"[gpt_e] Response doesn't look like JSON for chat_id={safe_chat_id}: {content[:100]}...", source="gpt_e_handler")
                changes = {}
        except json.JSONDecodeError as e:
            logger.error(f"[gpt_e] JSON decode error for chat_id={safe_chat_id}: {e} | Content: {content[:200]}...", source="gpt_e_handler")
            changes = {}
        
        # שלב 5: עדכון פרופיל
        if changes and isinstance(changes, dict):
            # עדכון הפרופיל במסד הנתונים
            try:
                new_profile = changes.get("updated_profile", "")
                if new_profile and new_profile.strip():
                    update_user_summary_fast(safe_chat_id, new_profile)
                    logger.info(f"[gpt_e] Updated profile for chat_id={safe_chat_id}", source="gpt_e_handler")
                else:
                    logger.info(f"[gpt_e] No meaningful changes found for chat_id={safe_chat_id}", source="gpt_e_handler")
            except Exception as update_e:
                logger.error(f"[gpt_e] Failed to update profile for chat_id={safe_chat_id}: {update_e}", source="gpt_e_handler")
        else:
            logger.info(f"[gpt_e] No changes to apply for chat_id={safe_chat_id}", source="gpt_e_handler")
        
        # חישוב זמן ביצוע
        execution_time = (datetime.now() - start_time).total_seconds()
        
        result = {
            "success": True,
            "changes": changes,
            "usage": usage,
            "model": response.model,
            "execution_time": execution_time,
            "timestamp": start_time.isoformat()
        }
        
        logger.info(f"[gpt_e] Completed successfully for chat_id={safe_chat_id} in {result['execution_time']:.2f}s", source="gpt_e_handler")
        return result
        
    except Exception as e:
        logger.error(f"[gpt_e] Unexpected error for chat_id={safe_chat_id}: {e}", exc_info=True, source="gpt_e_handler")
        return {"success": False, "error": str(e)}


async def update_user_state_after_gpt_e(chat_id: str, result: Dict[str, Any]) -> None:
    """
    מעדכן מצב משתמש אחרי הרצת gpt_e
    :param chat_id: מזהה המשתמש
    :param result: תוצאת הרצת gpt_e
    """
    safe_chat_id = safe_str(chat_id)
    try:
        if result.get("success", False):
            # איפוס מונה gpt_c
            success = reset_gpt_c_run_count_wrapper(safe_chat_id)
            if success:
                logger.info(f"[gpt_e] Updated user state for chat_id={safe_chat_id} after successful run", source="gpt_e_handler")
            else:
                logger.error(f"[gpt_e] Failed to update user state for chat_id={safe_chat_id}", source="gpt_e_handler")
        else:
            logger.warning(f"[gpt_e] Not updating user state for chat_id={safe_chat_id} due to failed run", source="gpt_e_handler")
    except Exception as e:
        logger.error(f"[gpt_e] Error updating user state for chat_id={safe_chat_id}: {e}", source="gpt_e_handler")

def log_gpt_e_run(chat_id: str, result: Dict[str, Any]) -> None:
    """
    רושם הרצת gpt_e למסד הנתונים
    :param chat_id: מזהה המשתמש
    :param result: תוצאת הרצת gpt_e
    """
    safe_chat_id = safe_str(chat_id)
    try:
        log_data = {
            'chat_id': safe_chat_id,
            'success': result.get('success', False),
            'execution_time': result.get('execution_time', 0),
            'model': result.get('model', ''),
            'usage': result.get('usage', {}),
            'changes': result.get('changes', {}),
            'timestamp': result.get('timestamp', datetime.now().isoformat())
        }
        
        # כאן אפשר להוסיף שמירה למסד הנתונים
        if should_log_data_extraction_debug():
            print(f"[DEBUG] gpt_e_log: {json.dumps(log_data, ensure_ascii=False, indent=2)}")
            
    except Exception as e:
        logger.error(f"[gpt_e] Error logging run for chat_id={safe_chat_id}: {e}", source="gpt_e_handler")


async def execute_gpt_e_if_needed(chat_id: str) -> Optional[Dict[str, Any]]:
    """
    מריץ gpt_e אם צריך
    :param chat_id: מזהה המשתמש
    :return: תוצאת הרצה או None
    """
    safe_chat_id = safe_str(chat_id)
    logger.info(f"[gpt_e] Checking if should run for chat_id={safe_chat_id} (every {GPT_E_RUN_EVERY_MESSAGES} user messages)", source="gpt_e_handler")
    
    stats, _ = get_user_stats_and_history(safe_chat_id)
    total_messages = stats.get("total_messages", 0)
    
    if should_run_gpt_e(safe_chat_id, total_messages):
        logger.info(f"[gpt_e] Triggered for chat_id={safe_chat_id} (user sent {total_messages} messages)", source="gpt_e_handler")
        result = await run_gpt_e(safe_chat_id)
        
        await update_user_state_after_gpt_e(safe_chat_id, result)
        log_gpt_e_run(safe_chat_id, result)
        
        return result
    else:
        logger.info(f"[gpt_e] Not running for chat_id={safe_chat_id} (user sent {total_messages} messages)", source="gpt_e_handler")
        return None 