"""
מחלקת AI - כל פונקציות ה-GPT במקום אחד
"""
import json
import logging

from config import client, SYSTEM_PROMPT

def safe_float(val):
    """
    ניסיון להמיר ערך ל-float, במקרה של כשל יחזיר 0.0 עם לוג אזהרה.
    """
    try:
        return float(val)
    except (ValueError, TypeError):
        logging.warning(f"safe_float: value '{val}' could not be converted to float. Using 0.0 instead.")
        return 0.0

def get_main_response(full_messages):
    """
    GPT ראשי - נותן תשובה למשתמש
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=full_messages
        )
        return (
            response.choices[0].message.content,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
            response.model
        )
    except Exception as e:
        logging.error(f"❌ שגיאה ב-GPT ראשי: {e}")
        raise

def summarize_bot_reply(reply_text):
    """
    GPT מקצר - מקצר את תשובת הבוט
    """
    system_prompt = "תמצת את משמעות ההודעה במשפט קצר (עד 10 מילים). בלי ציטוטים, בלי ניתוחים – רק תיאור יבש של מהות ההודעה."
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": reply_text}
            ],
            temperature=0.2,
            max_tokens=30
        )
        return (
            response.choices[0].message.content.strip(),
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
            response.model
        )
    except Exception as e:
        logging.error(f"❌ שגיאה ב-GPT מקצר: {e}")
        raise

def extract_user_profile_fields(text):
    """
    GPT מחלץ מידע - מחלץ פרטים אישיים מההודעה
    """
    system_prompt = """אתה מחלץ מידע אישי מטקסט.
החזר JSON עם השדות הבאים אם הם מוזכרים:

age - גיל (רק מספר)
religious_context - דתי או חילוני או מסורתי  
relationship_type - רווק או נשוי או גרוש
closet_status - בארון או יצא או חלקי

דוגמאות:
"אני בן 25" → {"age": 25}
"אני דתי ורווק" → {"religious_context": "דתי", "relationship_type": "רווק"}
"בחור דתי בן 23" → {"age": 23, "religious_context": "דתי"}

רק JSON, בלי הסברים!"""

    usage_data = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "model": ""}
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0,
            max_tokens=50
        )
        content = response.choices[0].message.content.strip()
        usage_data = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "model": response.model
        }

        logging.info(f"🤖 GPT מחלץ מידע החזיר: '{content}'")

        # אם זה לא JSON, ננסה לחלץ
        if not content.startswith("{"):
            logging.warning("⚠️ לא JSON תקין, מנסה לחלץ...")
            if "{" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                content = content[start:end]
                logging.info(f"🔧 חילצתי: '{content}'")

        result = json.loads(content)
        logging.info(f"✅ GPT מצא שדות: {result}")
        return result, usage_data

    except json.JSONDecodeError as e:
        logging.error(f"❌ שגיאה בפרסור JSON: {e}")
        logging.error(f"📄 התוכן: '{content}'")

        # פרסור ידני כ-fallback
        manual_result = {}
        if "בן " in text:
            import re
            age_match = re.search(r'בן (\d+)', text)
            if age_match:
                manual_result["age"] = int(age_match.group(1))
        if "דתי" in text:
            manual_result["religious_context"] = "דתי"
        if "רווק" in text:
            manual_result["relationship_type"] = "רווק"

        logging.info(f"🔧 פרסור ידני: {manual_result}")
        return manual_result, usage_data

    except Exception as e:
        logging.error(f"💥 שגיאה כללית ב-GPT מחלץ מידע: {e}")
        return {}, usage_data

def calculate_total_cost(main_usage, summary_usage, extract_usage):
    """
    מחשב את העלות הכוללת של כל ה-GPT calls
    """
    # שימוש בפונקציית safe_float כדי להימנע מקריסה על ערכים ריקים או לא חוקיים
    total_tokens = (
        safe_float(main_usage[2]) +
        safe_float(summary_usage[2]) +
        safe_float(extract_usage.get("total_tokens", 0))
    )
    try:
        cost_usd = round(
            safe_float(main_usage[0]) * 0.000005 + safe_float(main_usage[1]) * 0.000015 +
            safe_float(summary_usage[0]) * 0.000005 + safe_float(summary_usage[1]) * 0.000015 +
            safe_float(extract_usage.get("prompt_tokens", 0)) * 0.000005 +
            safe_float(extract_usage.get("completion_tokens", 0)) * 0.000015,
            6
        )
        cost_ils = round(cost_usd * 3.8, 4)
    except Exception as e:
        cost_usd = cost_ils = 0
        logging.error(f"[COST ERROR] {e}")

    return total_tokens, cost_usd, cost_ils

# תוכל להוסיף כאן פונקציות נוספות לפי הצורך, כולל לוגיקות עזר, בדיקות וכו'.
