"""
profile_extraction.py
---------------------
קובץ זה מרכז את כל הלוגיקה של חילוץ תעודת זהות רגשית (מידע אישי) מהמשתמש באמצעות GPT.
הרציונל: ריכוז כל שלבי החילוץ, ניקוי, בדיקה ומיזוג של מידע אישי במקום אחד.
שימוש:
  from profile_extraction import extract_user_profile_fields

כל הפונקציות מתועדות בעברית ומסודרות היטב.
"""

import logging
import json
import re
from prompts import PROFILE_EXTRACTION_PROMPT
from config import client

# --- פונקציה עיקרית: חילוץ תעודת זהות רגשית ---
def extract_user_profile_fields(text, system_prompt=None, client=None): # שולחת את הטקסט ל-GPT ומחזירה dict עם שדות מידע אישי (גיל, דת, עיסוק וכו')
    """
    שולחת את הטקסט ל-GPT (identity_extraction) ומחזירה dict עם שדות מידע אישי (גיל, דת, עיסוק וכו').
    קלט: text (טקסט חופשי מהמשתמש), system_prompt (פרומט ייעודי, ברירת מחדל: PROFILE_EXTRACTION_PROMPT), client (אופציונלי).
    פלט: (new_data: dict, usage_data: dict)
    # מהלך מעניין: ניקוי אוטומטי של בלוק ```json ... ``` מהתשובה של GPT, בדיקת תקינות, ולוגים מפורטים.
    """
    print("[DEBUG][extract_user_profile_fields] CALLED")
    if system_prompt is None:
        system_prompt = PROFILE_EXTRACTION_PROMPT  # פרומט חילוץ תעודת זהות
    if client is None:
        from gpt_handler import client
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0,
            max_tokens=200
        )
        content = response.choices[0].message.content.strip()
        print(f"[DEBUG][extract_user_profile_fields] raw GPT content: {content}")
        # --- ניקוי בלוק ```json ... ``` אם קיים ---
        if content.startswith("```"):
            match = re.search(r"```(?:json)?\\s*({.*?})\\s*```", content, re.DOTALL)
            if match:
                logging.debug(f"[DEBUG][extract_user_profile_fields] found ```json block, extracting only JSON...")
                content = match.group(1)
                print(f"[DEBUG][extract_user_profile_fields] cleaned content: {content}")
        logging.info(f"[DEBUG] GPT3 identity_extraction raw: '{content}'")
        try:
            new_data = json.loads(content)
            print(f"[DEBUG][extract_user_profile_fields] after json.loads: {new_data} (type: {type(new_data)})")
            if isinstance(new_data, dict):
                print(f"[DEBUG][extract_user_profile_fields] new_data keys: {list(new_data.keys())}")
                if not new_data:
                    print("[ALERT][extract_user_profile_fields] new_data is an EMPTY dict!")
            else:
                print("[ALERT][extract_user_profile_fields] new_data is NOT a dict!")
        except Exception as e:
            import traceback
            print(f"[ERROR][extract_user_profile_fields] Exception: {e}")
            print(traceback.format_exc())
            new_data = {}
        # --- usage/cost ---
        usage_data = {}
        try:
            usage_data = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens,
                'cached_tokens': getattr(response.usage.prompt_tokens_details, 'cached_tokens', 0),
                'model': response.model
            }
        except Exception as ex:
            logging.warning(f"[DEBUG] לא הצלחתי לחלץ usage_data: {ex}")
        print(f"[DEBUG][extract_user_profile_fields] returning new_data: {new_data}")
        return new_data, usage_data
    except Exception as critical_error:
        logging.error(f"❌ שגיאה קריטית ב-extract_user_profile_fields: {critical_error}")
        return {}, {}

# --- פונקציות עזר נוספות (אם יש) ---
# כאן אפשר להוסיף בעתיד פונקציות למיזוג תעודת זהות, בדיקות תקינות, וכו'. 