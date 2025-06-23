"""
gpt_d_handler.py
----------------
מנוע gpt_d: מיזוג/איכות פרופיל (profile merge/quality)
"""

import logging
import litellm
from prompts import PROFILE_MERGE_PROMPT
import json
from gpt_c_handler import gpt_c
from gpt_utils import normalize_usage_dict

def gpt_d(changed_fields, chat_id=None, message_id=None):
    """
    מפעיל את gpt_d למיזוג/איכות פרופיל רגשי.
    """
    try:
        metadata = {"gpt_identifier": "gpt_d", "chat_id": chat_id, "message_id": message_id}
        user_content = f"שדות לעדכון:\n{changed_fields}"
        response = litellm.completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROFILE_MERGE_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            max_tokens=300,
            metadata=metadata,
            store=True
        )
        content = response.choices[0].message.content.strip()
        usage = response.usage.__dict__ if hasattr(response.usage, "__dict__") else {}
        return {"content": content, "usage": usage, "model": response.model}
    except Exception as e:
        logging.error(f"[gpt_d] Error: {e}")
        return {"content": "[שגיאה במיזוג]", "usage": {}, "model": "gpt-4o-mini"}

def smart_update_profile_with_gpt_d(existing_profile, user_message, interaction_id=None):
    """
    מעדכן פרופיל רגשי קיים עם gpt_d על בסיס הודעת משתמש חדשה.
    מחזיר tuple: (updated_profile, combined_usage)
    """
    # 1. חילוץ שדות חדשים מהודעת המשתמש (gpt_c)
    gpt_c_result = gpt_c(user_message)
    extracted_fields = {}
    gpt_c_usage = {}
    if isinstance(gpt_c_result, dict):
        content = gpt_c_result.get("content", "")
        try:
            extracted_fields = json.loads(content) if content and content.strip().startswith("{") else {}
        except Exception as e:
            extracted_fields = {}
        gpt_c_usage = normalize_usage_dict(gpt_c_result.get("usage", {}), gpt_c_result.get("model", "gpt-4o-mini"))
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
    gpt_d_result = gpt_d(changed_fields, message_id=interaction_id)
    gpt_d_usage = normalize_usage_dict(gpt_d_result.get("usage", {}), gpt_d_result.get("model", "gpt-4o-mini"))
    # נסה לפרסר את התוצאה
    updated_profile = merged_fields
    content = gpt_d_result.get("content", "")
    try:
        if content and content.strip().startswith("{"):
            updated_profile = json.loads(content)
    except Exception as e:
        pass
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