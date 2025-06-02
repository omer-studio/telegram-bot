"""
gpt_handler.py — כל הפונקציות לטיפול ב־GPT במקום אחד
בגרסה זו נוסף חישוב עלות לכל סוג טוקן (רגיל, קשד, פלט) + תיעוד מלא של הטוקנים + החזר עלות באגורות לכל קריאה
"""

import json
import logging
from datetime import datetime
from config import client, SYSTEM_PROMPT

# מחירים קבועים (נכון ליוני 2024) ל־GPT-4o
COST_PROMPT_REGULAR = 0.002 / 1000    # טוקן קלט רגיל
COST_PROMPT_CACHED = 0.0005 / 1000    # טוקן קלט קשד (cache)
COST_COMPLETION = 0.006 / 1000        # טוקן פלט
USD_TO_ILS = 3.8                      # שער דולר-שקל

def write_gpt_log(ttype, usage, model):
    """
    שומר לוג של השימוש בכל קריאה ל־GPT
    """
    log_path = "/data/gpt_usage_log.jsonl"
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": ttype,
        "model": model,
        "tokens_prompt": usage.get("prompt_tokens", 0),
        "tokens_completion": usage.get("completion_tokens", 0),
        "tokens_total": usage.get("total_tokens", 0),
        "tokens_cached": usage.get("cached_tokens", 0),  # נוסף: כמות קשד
        "cost_prompt_regular": usage.get("cost_prompt_regular", 0),
        "cost_prompt_cached": usage.get("cost_prompt_cached", 0),
        "cost_completion": usage.get("cost_completion", 0),
        "cost_total": usage.get("cost_total", 0),
        "cost_total_ils": usage.get("cost_total_ils", 0),
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logging.error(f"שגיאה בכתיבה לקובץ gpt_usage_log: {e}")

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
    מחזיר גם את כל פרטי העלות (טוקנים, קשד, מחיר מדויק)
    """
    try:
        print("🔍 נשלח ל־GPT:")
        for m in full_messages:
            print(f"{m['role']}: {m['content']}")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=full_messages,
            temperature=1,
        )

        # שליפת נתוני usage
        prompt_tokens = response.usage.prompt_tokens
        prompt_tokens_details = response.usage.prompt_tokens_details
        cached_tokens = prompt_tokens_details['cached_tokens']
        prompt_regular = prompt_tokens - cached_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        # חישוב עלות לפי הסוג
        cost_prompt_regular = prompt_regular * COST_PROMPT_REGULAR
        cost_prompt_cached = cached_tokens * COST_PROMPT_CACHED
        cost_completion = completion_tokens * COST_COMPLETION
        cost_total = cost_prompt_regular + cost_prompt_cached + cost_completion
        cost_total_ils = round(cost_total * USD_TO_ILS, 4)
        cost_gpt1 = int(round(cost_total_ils * 100))  # עלות באגורות #NEW

        print(f"🔢 פרטי שימוש: prompt={prompt_tokens} קשד={cached_tokens} רגיל={prompt_regular} פלט={completion_tokens}")
        print(f"💸 עלויות: רגיל ${cost_prompt_regular:.6f}, קשד ${cost_prompt_cached:.6f}, פלט ${cost_completion:.6f}, סהכ ${cost_total:.6f} (₪{cost_total_ils})")

        # תיעוד מלא ללוג נוסף
        usage_log = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "cost_prompt_regular": cost_prompt_regular,
            "cost_prompt_cached": cost_prompt_cached,
            "cost_completion": cost_completion,
            "cost_total": cost_total,
            "cost_total_ils": cost_total_ils,
            "cost_gpt1": cost_gpt1  # באגורות
        }

        # שורת לוג לדיבאג ולמעקב
        from utils import log_event_to_file
        log_event_to_file({
            "event": "gpt_main_call",
            "gpt_input": full_messages,
            "gpt_reply": response.choices[0].message.content,
            "model": response.model,
            "usage": usage_log
        })

        # כתיבה ללוג שימוש
        write_gpt_log("main_reply", usage_log, response.model)

        # מחזיר את כל הפרמטרים
        return (
            response.choices[0].message.content,  # bot_reply
            prompt_tokens,                        # prompt_tokens_total
            cached_tokens,                        # cached_tokens
            prompt_regular,                       # prompt_regular
            completion_tokens,                    # completion_tokens_total
            total_tokens,                         # total_tokens
            cost_prompt_regular,
            cost_prompt_cached,
            cost_completion,
            cost_total,
            cost_total_ils,                       # total_cost_ils בש"ח
            cost_gpt1,                            # cost_gpt1 באגורות
            response.model                        # model_GPT1
        )
    except Exception as e:
        logging.error(f"❌ שגיאה ב-GPT ראשי: {e}")
        raise

def summarize_bot_reply(reply_text):
    """
    GPT מקצר - תמצות תשובת הבוט
    (הוספנו גם כאן חישוב עלות מלא והחזרת עלות באגורות וקשד)
    """
    system_prompt = (
        "סכם את ההודעה שלי כאילו אני מדבר עם חבר: "
        "משפט אחד חם ואישי בסגנון חופשי (לא תיאור יבש), בגוף ראשון, כולל אמירה אישית קצרה על מהות התגובה שלי, "
        "ואז את השאלה ששאלתי אם יש, בצורה חמה וזורמת, עד 20 מילים בסך הכל. תשלב אימוג'י רלוונטי אם מתאים, כמו שמדברים בווטסאפ. "
        "אל תעשה ניתוחים טכניים או תיאור של הודעה – ממש תכתוב את זה כמו הודעת וואטסאפ קצרה, בגוף ראשון, בסגנון חופשי וקליל."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": reply_text}
            ],
            temperature=0.6,
            max_tokens=40
        )
        prompt_tokens = response.usage.prompt_tokens
        prompt_tokens_details = response.usage.prompt_tokens_details
        cached_tokens = prompt_tokens_details['cached_tokens']
        prompt_regular = prompt_tokens - cached_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        cost_prompt_regular = prompt_regular * COST_PROMPT_REGULAR
        cost_prompt_cached = cached_tokens * COST_PROMPT_CACHED
        cost_completion = completion_tokens * COST_COMPLETION
        cost_total = cost_prompt_regular + cost_prompt_cached + cost_completion
        cost_total_ils = round(cost_total * USD_TO_ILS, 4)
        cost_gpt2 = int(round(cost_total_ils * 100))  # באגורות #NEW

        usage_log = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "cost_prompt_regular": cost_prompt_regular,
            "cost_prompt_cached": cost_prompt_cached,
            "cost_completion": cost_completion,
            "cost_total": cost_total,
            "cost_total_ils": cost_total_ils,
            "cost_gpt2": cost_gpt2 # באגורות
        }

        write_gpt_log("reply_summary", usage_log, response.model)

        return (
            response.choices[0].message.content.strip(),  # bot_summary
            prompt_tokens,
            cached_tokens,         # cached_tokens_gpt2 #NEW
            prompt_regular,
            completion_tokens,
            total_tokens,
            cost_prompt_regular,
            cost_prompt_cached,
            cost_completion,
            cost_total,
            cost_total_ils,
            cost_gpt2,             # cost_gpt2 באגורות #NEW
            response.model         # model_GPT2
        )
    except Exception as e:
        logging.error(f"❌ שגיאה ב-GPT מקצר: {e}")
        raise

def extract_user_profile_fields(text):
    """
    GPT מחלץ מידע - מחלץ פרטים אישיים מההודעה
    (הוספנו גם כאן חישוב עלות מלא והחזרת עלות באגורות וקשד)
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
    usage_data = {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "cached_tokens": 0, "cost_prompt_regular": 0, "cost_prompt_cached": 0,
        "cost_completion": 0, "cost_total": 0, "cost_total_ils": 0, "cost_gpt3": 0, "model": ""
    }
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

        prompt_tokens = response.usage.prompt_tokens
        prompt_tokens_details = response.usage.prompt_tokens_details
        cached_tokens = prompt_tokens_details['cached_tokens']
        prompt_regular = prompt_tokens - cached_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        cost_prompt_regular = prompt_regular * COST_PROMPT_REGULAR
        cost_prompt_cached = cached_tokens * COST_PROMPT_CACHED
        cost_completion = completion_tokens * COST_COMPLETION
        cost_total = cost_prompt_regular + cost_prompt_cached + cost_completion
        cost_total_ils = round(cost_total * USD_TO_ILS, 4)
        cost_gpt3 = int(round(cost_total_ils * 100))  # באגורות #NEW

        usage_data = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,   # cached_tokens_gpt3 #NEW
            "cost_prompt_regular": cost_prompt_regular,
            "cost_prompt_cached": cost_prompt_cached,
            "cost_completion": cost_completion,
            "cost_total": cost_total,
            "cost_total_ils": cost_total_ils,
            "cost_gpt3": cost_gpt3,           # cost_gpt3 באגורות #NEW
            "model": response.model
        }

        # לוג למעקב
        logging.info(f"🤖 GPT מחלץ מידע החזיר: '{content}'")
        write_gpt_log("identity_extraction", usage_data, usage_data.get("model", ""))

        # ניתוח JSON מהתשובה
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
    מחשב את סך כל הטוקנים והעלות מכל שלוש הקריאות ל־GPT:
    - main_usage: קריאה ראשית (tuple)
    - summary_usage: סיכום (tuple)
    - extract_usage: חילוץ תעודת זהות (dict)
    מחזיר:
    - total_tokens: סכום טוקנים
    - cost_usd: עלות כוללת בדולרים
    - cost_ils: עלות כוללת בש"ח (עגול ל-4 ספרות)
    """
    try:
        # שליפה מהקריאה הראשית
        main_prompt = main_usage[1] if len(main_usage) > 1 else 0
        main_completion = main_usage[4] if len(main_usage) > 4 else 0
        main_total = main_usage[5] if len(main_usage) > 5 else 0
        cost_main_usd = main_usage[9] if len(main_usage) > 9 else 0
        cost_main_ils = main_usage[10] if len(main_usage) > 10 else 0

        # שליפה מהסיכום
        summary_prompt = summary_usage[1] if len(summary_usage) > 1 else 0
        summary_completion = summary_usage[4] if len(summary_usage) > 4 else 0
        summary_total = summary_usage[5] if len(summary_usage) > 5 else 0
        cost_summary_usd = summary_usage[9] if len(summary_usage) > 9 else 0
        cost_summary_ils = summary_usage[10] if len(summary_usage) > 10 else 0

        # שליפה מהחילוץ
        extract_total = extract_usage.get("total_tokens", 0)
        cost_extract_usd = extract_usage.get("cost_total", 0)
        cost_extract_ils = extract_usage.get("cost_total_ils", 0)

        # חיבור כל הטוקנים
        total_tokens = main_total + summary_total + extract_total
        cost_usd = round(cost_main_usd + cost_summary_usd + cost_extract_usd, 6)
        cost_ils = round(cost_main_ils + cost_summary_ils + cost_extract_ils, 4)

        return total_tokens, cost_usd, cost_ils

    except Exception as e:
        logging.error(f"❌ שגיאה בחישוב עלות כוללת: {e}")
        return 0, 0.0, 0.0


# -------------------------------------------------------------
# הסבר בסוף הקובץ (לשימושך):

"""
🔵 מה חדש כאן?

- אין שום פונקציה שמוסרת — הכל מקורי.
- נוספו חישובי עלות וטוקנים לכל קריאה (רגיל, קשד, פלט).
- כל קריאה שומרת לוג עם כל השדות.
- פונקציות מחזירות עכשיו את כל הערכים — אפשר לשמור אותם ל־Google Sheets ולעשות דוחות.
- נוסף החזר עלות באגורות (cost_gptX) וקשד (cached_tokens_gptX) לכל קריאה.
- בכל מקום נוסף # הסבר קצר בעברית כדי שתדע מה קורה.
- אין מחיקות — רק תוספות.

תעדכן אותי כשעברת, נמשיך לחיבור ל־Google Sheets!
"""
