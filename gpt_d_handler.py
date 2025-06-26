"""
gpt_d_handler.py
----------------
מנוע gpt_d: מיזוג פרטי פרופיל חדשים עם קיימים
משתמש ב-Gemini 1.5 Pro (חינמי) - ללא צורך ב-fallback.
"""

import logging
from datetime import datetime
import json
import litellm
from prompts import PROFILE_MERGE_PROMPT
from config import GPT_MODELS, GPT_PARAMS, should_log_data_extraction_debug, should_log_gpt_cost_debug
from gpt_utils import normalize_usage_dict

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
            "messages": [{"role": "system", "content": PROFILE_MERGE_PROMPT}, {"role": "user", "content": prompt}],
            "temperature": params["temperature"],
            "metadata": metadata,
            "store": True
        }
        
        # הוספת max_tokens רק אם הוא לא None
        if params["max_tokens"] is not None:
            completion_params["max_tokens"] = params["max_tokens"]
        
        from gpt_utils import measure_llm_latency
        with measure_llm_latency(model):
            response = litellm.completion(**completion_params)
        content = response.choices[0].message.content.strip()
        usage = normalize_usage_dict(response.usage, response.model)
        
        # ניסיון לפרס JSON
        try:
            if content and content.strip().startswith("{"):
                extracted_fields = json.loads(content)
            else:
                extracted_fields = {}
        except json.JSONDecodeError:
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
    # 3. מיזוג עם gpt_d
    changed_fields = extracted_fields.copy()
    if not isinstance(existing_profile, dict):
        existing_profile = {}
    # מיזוג: שדות חדשים מחליפים קיימים
    merged_fields = existing_profile.copy()
    merged_fields.update(changed_fields)
    gpt_d_result = merge_profile_data(existing_profile, changed_fields, message_id=interaction_id)
    gpt_d_usage = normalize_usage_dict(gpt_d_result.get("usage", {}), gpt_d_result.get("model", GPT_MODELS["gpt_d"]))
    # נסה לפרסר את התוצאה
    updated_profile = gpt_d_result.get("merged_profile", merged_fields)
    # 4. איחוד usage
    combined_usage = {}
    combined_usage.update(gpt_c_usage)
    for k, v in gpt_d_usage.items():
        combined_usage[f"gpt_d_{k}"] = v
    return updated_profile, combined_usage

def smart_update_profile_with_gpt_d_async(existing_profile, user_message, interaction_id=None):
    import asyncio
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, smart_update_profile_with_gpt_d, existing_profile, user_message, interaction_id) 