"""
gpt_d_handler.py
----------------
מנוע gpt_d: מיזוג פרטי פרופיל חדשים עם קיימים
משתמש ב-Gemini 1.5 Pro (חינמי) - ללא צורך ב-fallback.
"""

import logging
from datetime import datetime
import json
import lazy_litellm as litellm
from prompts import build_profile_merge_prompt
from config import GPT_MODELS, GPT_PARAMS, should_log_data_extraction_debug, should_log_gpt_cost_debug
from gpt_utils import normalize_usage_dict, calculate_gpt_cost, extract_json_from_text

def merge_profile_data(existing_profile, new_extracted_fields, chat_id=None, message_id=None):
    """
    מיזוג נתוני פרופיל חדשים עם קיימים באמצעות gpt_d
    משתמש ב-Gemini 1.5 Pro (חינמי) - ללא צורך ב-fallback.
    """
    try:
        metadata = {"gpt_identifier": "gpt_d", "chat_id": chat_id, "message_id": message_id}
        params = GPT_PARAMS["gpt_d"]
        model = GPT_MODELS["gpt_d"]
        
        prompt = f"""פרופיל קיים: {json.dumps(existing_profile, ensure_ascii=False, indent=2)}

מידע חדש שחולץ: {json.dumps(new_extracted_fields, ensure_ascii=False, indent=2)}

מזג את המידע ותחזיר פרופיל מעודכן."""

        completion_params = {
            "model": model,
            "messages": [{"role": "system", "content": build_profile_merge_prompt()}, {"role": "user", "content": prompt}],
            "temperature": params["temperature"],
            "metadata": metadata
        }
        
        # הוספת max_tokens רק אם הוא לא None
        if params["max_tokens"] is not None:
            completion_params["max_tokens"] = params["max_tokens"]
        
        from gpt_utils import measure_llm_latency
        with measure_llm_latency(model):
            response = litellm.completion(**completion_params)
        content_raw = response.choices[0].message.content.strip()
        content = extract_json_from_text(content_raw)
        usage = normalize_usage_dict(response.usage, response.model)
        
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
            logging.warning(f"[gpt_d] Cost calc failed: {_cost_e}")
        
        # ניסיון לפרס JSON
        try:
            if content and content.strip():
                content_clean = content.strip()
                if content_clean.startswith("{") and content_clean.endswith("}"):
                    extracted_fields = json.loads(content_clean)
                    if not isinstance(extracted_fields, dict):
                        logging.warning(f"[GPT_D] JSON parsed but not a dict: {type(extracted_fields)}")
                        extracted_fields = {}
                else:
                    logging.warning(f"[GPT_D] Content doesn't look like JSON: {content_clean[:100]}...")
                    extracted_fields = {}
            else:
                extracted_fields = {}
        except json.JSONDecodeError as e:
            logging.error(f"[GPT_D] JSON decode error: {e} | Content: {content[:200] if content else 'None'}...")
            extracted_fields = {}
        except Exception as e:
            logging.error(f"[GPT_D] Unexpected error parsing JSON: {e} | Content: {content[:200] if content else 'None'}...")
            extracted_fields = {}
        
        # הדפסת מידע חשוב על מיזוג נתונים (תמיד יופיע!)
        print(f"🔄 [GPT-D] מוזגו {len(extracted_fields)} שדות")
        if should_log_gpt_cost_debug():
            print(f"💰 [GPT-D] עלות: {usage.get('cost_total', 0):.6f}$ | טוקנים: {usage.get('total_tokens', 0)}")
        if should_log_data_extraction_debug():
            print(f"📋 [GPT-D] פרופיל מוזג: {json.dumps(extracted_fields, ensure_ascii=False, indent=2)}")
        
        return {"merged_profile": extracted_fields, "usage": usage, "model": response.model}
        
    except Exception as e:
        logging.error(f"[gpt_d] Error: {e}")
        print(f"❌ [GPT-D] שגיאה: {e}")
        return {"merged_profile": {}, "usage": {}, "model": model}

def smart_update_profile_with_gpt_d(existing_profile, user_message, interaction_id=None):
    """
    מעדכן פרופיל רגשי קיים עם gpt_d על בסיס הודעת משתמש חדשה.
    מחזיר tuple: (updated_profile, combined_usage)
    """
    # 1. חילוץ שדות חדשים מהודעת המשתמש (gpt_c)
    from gpt_c_handler import extract_user_info
    gpt_c_result = extract_user_info(user_message)
    extracted_fields = {}
    gpt_c_usage = {}
    if isinstance(gpt_c_result, dict):
        extracted_fields = gpt_c_result.get("extracted_fields", {})
        gpt_c_usage = normalize_usage_dict(gpt_c_result.get("usage", {}), gpt_c_result.get("model", GPT_MODELS["gpt_c"]))
    
    # 2. אם אין שדות חדשים, מחזירים את הפרופיל הקיים
    if not extracted_fields:
        return existing_profile, gpt_c_usage
    
    # 3. בדיקה האם יש ערך קיים בשדות שהוחלפו (רק אז נפעיל GPT-D)
    gpt_d_should_run = False
    if not isinstance(existing_profile, dict):
        existing_profile = {}
    
    for field, new_value in extracted_fields.items():
        if field in existing_profile and existing_profile[field] and existing_profile[field] != "":
            gpt_d_should_run = True
            break
    
    # 4. מיזוג בסיסי: שדות חדשים מחליפים קיימים
    merged_fields = existing_profile.copy()
    merged_fields.update(extracted_fields)
    
    # 5. הפעלת GPT-D רק אם יש ערך קיים למיזוג
    gpt_d_usage = {}
    if gpt_d_should_run:
        gpt_d_result = merge_profile_data(existing_profile, extracted_fields, message_id=interaction_id)
        gpt_d_usage = normalize_usage_dict(gpt_d_result.get("usage", {}), gpt_d_result.get("model", GPT_MODELS["gpt_d"]))
        # נסה לפרסר את התוצאה
        updated_profile = gpt_d_result.get("merged_profile", merged_fields)
    else:
        updated_profile = merged_fields
    
    # 6. איחוד usage
    combined_usage = {}
    combined_usage.update(gpt_c_usage)
    # הוספת השדות שחולצו מ-GPT-C
    combined_usage["extracted_fields"] = extracted_fields
    for k, v in gpt_d_usage.items():
        combined_usage[f"gpt_d_{k}"] = v
    
    return updated_profile, combined_usage

# ---------------------------------------------------------------------------
# 🧵 Async helper – run in thread & persist changes
# ---------------------------------------------------------------------------

def _run_profile_merge_and_persist(chat_id: str, user_message: str, interaction_id=None):
    """Background helper executed inside a ThreadPool – merges & persists profile.

    1. Loads the existing profile for the given chat_id (safe – returns {}).
    2. Runs smart_update_profile_with_gpt_d to obtain an updated profile.
    3. Persists the merged profile back to disk/Sheets via update_user_profile_fast.
    4. Returns (updated_profile, usage) just like the underlying function.
    """

    # Lazy import to avoid circular dependencies at module import time
    from profile_utils import get_user_profile_fast, update_user_profile_fast  # noqa: WPS433

    try:
        existing_profile = get_user_profile_fast(chat_id)
        # Run merge (sync, heavy – runs LLMs)
        updated_profile, usage = smart_update_profile_with_gpt_d(existing_profile, user_message, interaction_id)

        # Persist only if there is any diff
        try:
            if updated_profile and isinstance(updated_profile, dict):
                update_user_profile_fast(chat_id, updated_profile)
        except Exception as persist_exc:  # pragma: no cover – just in case
            import logging
            logging.error(f"[GPT_D] Failed to persist profile for {chat_id}: {persist_exc}")

        return updated_profile, usage

    except Exception as exc:  # pragma: no cover – keep background thread alive
        import logging, traceback  # noqa: WPS433
        logging.error(f"[GPT_D] Critical error in profile merge for {chat_id}: {exc}\n{traceback.format_exc()}")
        return {}, {}


def smart_update_profile_with_gpt_d_async(chat_id: str, user_message: str, interaction_id=None):
    """Public async wrapper – accepts chat_id (not profile).

    It delegates the heavy lifting to _run_profile_merge_and_persist which is
    executed in a background thread (so we don't block the event-loop). The
    original API expected *existing_profile* as the first argument, but the
    only call-site (message_handler.py) actually passed chat_id. This change
    aligns the signature with real usage and, importantly, ensures the merged
    profile is persisted immediately.
    """

    import asyncio  # noqa: WPS433

    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, _run_profile_merge_and_persist, str(chat_id), user_message, interaction_id) 