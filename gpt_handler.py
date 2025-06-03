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



# ============================הג'יפיטי ה-1 - פועל תמיד ועונה תשובה למשתמש ======================= 


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



# ============================הג'יפיטי ה-2 - מקצר את תשובת הבוט אם היא ארוכה מדי כדי לחסוך בהיסטוריה ======================= 


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



# ============================הג'יפיטי ה-3 - פועל תמיד ומחלץ מידע לת.ז הרגשית ======================= 

def extract_user_profile_fields(text):
    """
    GPT מחלץ מידע - מחלץ פרטים אישיים מההודעה (גרסה מעודכנת)
    """
    system_prompt = """אתה מחלץ מידע אישי מטקסט. החזר JSON עם השדות הבאים רק אם הם מוזכרים:

age - גיל (מספר בלבד)
pronoun_preference - לשון פניה: "את"/"אתה"/"מעורב"
occupation_or_role - עיסוק/תפקיד
attracted_to - משיכה: "גברים"/"נשים"/"שניהם"/"לא ברור"
relationship_type - מצב זוגי: "רווק"/"נשוי"/"נשוי+2"/"גרוש" וכו'
self_religious_affiliation - זהות דתית: "יהודי"/"ערבי"/"דרוזי"/"נוצרי"/"שומרוני"
self_religiosity_level - רמת דתיות: "דתי"/"חילוני"/"מסורתי"/"חרדי"/"דתי לאומי"
family_religiosity - רקע משפחתי: "משפחה דתית"/"משפחה חילונית"/"משפחה מעורבת"
closet_status - מצב ארון: "בארון"/"יצא חלקית"/"יצא לכולם"
who_knows - מי יודע עליו
who_doesnt_know - מי לא יודע עליו
attends_therapy - טיפול: "כן"/"לא"/"טיפול זוגי"/"קבוצת תמיכה"
primary_conflict - הקונפליקט המרכזי
trauma_history - טראומות (בעדינות)
goal_in_course - מטרות בקורס
language_of_strength - משפטים מחזקים
coping_strategies - דרכי התמודדות
fears_concerns - פחדים וחששות
future_vision - חזון עתיד

דוגמאות:
"אני בן 25, יהודי דתי" → {"age": 25, "self_religious_affiliation": "יהודי", "self_religiosity_level": "דתי"}
"נשוי עם שני ילדים" → {"relationship_type": "נשוי+2"}
"סיפרתי להורים, אבל לעמיתים לא" → {"who_knows": "הורים", "who_doesnt_know": "עמיתים"}

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
            max_tokens=200  # הגדלתי כי יש 20 שדות אפשריים
        )
        content = response.choices[0].message.content.strip()

        # חישובי עלות (ללא שינוי)
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
        cost_gpt3 = int(round(cost_total_ils * 100))

        usage_data = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "cost_prompt_regular": cost_prompt_regular,
            "cost_prompt_cached": cost_prompt_cached,
            "cost_completion": cost_completion,
            "cost_total": cost_total,
            "cost_total_ils": cost_total_ils,
            "cost_gpt3": cost_gpt3,
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
        
        # בדיקות היגיון וvalidation
        validated_result = validate_extracted_data(result)
        
        logging.info(f"✅ GPT מצא שדות: {result}")
        if validated_result != result:
            logging.info(f"🔧 לאחר validation: {validated_result}")
        
        return (
            validated_result,           # extracted_data (במקום result)
            prompt_tokens,              # prompt_tokens  
            cached_tokens,              # cached_tokens
            prompt_regular,             # prompt_regular
            completion_tokens,          # completion_tokens
            total_tokens,               # total_tokens
            cost_prompt_regular,        # cost_prompt_regular
            cost_prompt_cached,         # cost_prompt_cached  
            cost_completion,            # cost_completion
            cost_total,                 # cost_total
            cost_total_ils,             # cost_total_ils
            cost_gpt3,                  # cost_gpt3 באגורות
            usage_data.get("model", "") # model
        )

    except json.JSONDecodeError as e:
        logging.error(f"❌ שגיאה בפרסור JSON: {e}")
        logging.error(f"📄 התוכן: '{content}'")

        # פרסור ידני כ-fallback - מעודכן לשדות החדשים
        manual_result = {}
        
        # גיל
        if "בן " in text or "בת " in text:
            import re
            age_match = re.search(r'ב[ןת] (\d+)', text)
            if age_match:
                manual_result["age"] = int(age_match.group(1))
        
        # זהות דתית ורמת דתיות
        if "יהודי" in text:
            manual_result["self_religious_affiliation"] = "יהודי"
        elif "ערבי" in text:
            manual_result["self_religious_affiliation"] = "ערבי"
        elif "דרוזי" in text:
            manual_result["self_religious_affiliation"] = "דרוזי"
            
        if "חרדי" in text:
            manual_result["self_religiosity_level"] = "חרדי"
        elif "דתי לאומי" in text:
            manual_result["self_religiosity_level"] = "דתי לאומי"
        elif "דתי" in text:
            manual_result["self_religiosity_level"] = "דתי"
        elif "מסורתי" in text:
            manual_result["self_religiosity_level"] = "מסורתי"
        elif "חילוני" in text:
            manual_result["self_religiosity_level"] = "חילוני"
            
        # מצב זוגי
        if "רווק" in text:
            manual_result["relationship_type"] = "רווק"
        elif "נשוי" in text:
            if "שני" in text or "2" in text:
                manual_result["relationship_type"] = "נשוי+2"
            elif "שלושה" in text or "3" in text:
                manual_result["relationship_type"] = "נשוי+3"
            elif "ילדים" in text or "ילד" in text:
                manual_result["relationship_type"] = "נשוי+2"  # default
            else:
                manual_result["relationship_type"] = "נשוי"
        elif "גרוש" in text:
            manual_result["relationship_type"] = "גרוש"
            
        # מצב ארון
        if "בארון" in text:
            manual_result["closet_status"] = "בארון"
        elif "יצאתי" in text:
            manual_result["closet_status"] = "יצא חלקית"
            
        # טיפול
        if "פסיכולוג" in text or "טיפול" in text:
            manual_result["attends_therapy"] = "כן"

        logging.info(f"🔧 פרסור ידני מעודכן: {manual_result}")
        
        # validation גם על הפרסור הידני
        validated_manual = validate_extracted_data(manual_result)
        if validated_manual != manual_result:
            logging.info(f"🔧 פרסור ידני לאחר validation: {validated_manual}")
            
        return (
            validated_manual,           # extracted_data
            0,                          # prompt_tokens (fallback)
            0,                          # cached_tokens (fallback)
            0,                          # prompt_regular (fallback)  
            0,                          # completion_tokens (fallback)
            0,                          # total_tokens (fallback)
            0.0,                        # cost_prompt_regular (fallback)
            0.0,                        # cost_prompt_cached (fallback)
            0.0,                        # cost_completion (fallback)
            0.0,                        # cost_total (fallback)
            0.0,                        # cost_total_ils (fallback)
            0,                          # cost_gpt3 (fallback)
            "fallback"                  # model (fallback)
        )

    except Exception as e:
        logging.error(f"💥 שגיאה כללית ב-GPT מחלץ מידע: {e}")
        return (
            {},                         # extracted_data (ריק)
            0,                          # prompt_tokens
            0,                          # cached_tokens 
            0,                          # prompt_regular
            0,                          # completion_tokens
            0,                          # total_tokens
            0.0,                        # cost_prompt_regular
            0.0,                        # cost_prompt_cached
            0.0,                        # cost_completion  
            0.0,                        # cost_total
            0.0,                        # cost_total_ils
            0,                          # cost_gpt3
            "error"                     # model
        )


def validate_extracted_data(data):
    """
    בודק רק דברים בסיסיים - לא מגביל תוכן
    """
    validated = data.copy()
    
    # בדיקת גיל הגיוני - רק מעל 80
    if "age" in validated:
        try:
            age = int(validated["age"])
            if age > 80:
                logging.warning(f"⚠️ גיל {age} מעל 80, מסיר מהנתונים")
                del validated["age"]
            else:
                validated["age"] = age
        except (ValueError, TypeError):
            logging.warning(f"⚠️ גיל לא תקין: {validated['age']}, מסיר מהנתונים")
            del validated["age"]
    
    # הגבלת אורך שדות לחסכון בטוקנים
    for field, value in list(validated.items()):
        if isinstance(value, str):
            if len(value) > 100:
                logging.warning(f"⚠️ שדה {field} ארוך מדי ({len(value)} תווים), מקצר")
                validated[field] = value[:97] + "..."
            elif len(value.strip()) == 0:
                logging.warning(f"⚠️ שדה {field} ריק, מסיר")
                del validated[field]
    
    return validated
#===============================================================================
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
