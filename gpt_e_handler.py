"""
gpt_e_handler.py
----------------
מנוע gpt_e: חידוד, תיקון והשלמת פרופיל רגשי על בסיס היסטוריה ופרופיל קיים.
משתמש ב-Gemini 1.5 Pro (חינמי) - ללא צורך ב-fallback.

- מופעל כל 50 ריצות gpt_c, או מעל 20 ריצות gpt_c אם עברו 24 שעות מאז הריצה האחרונה.
- שולח ל-GPT את ההיסטוריה והפרופיל, מקבל שדות חדשים/מתוקנים בלבד.
- מעדכן Google Sheets, user_state, ולוגים.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# ייבוא פונקציות עזר
from utils import get_chat_history_messages
from sheets_handler import get_user_summary, update_user_profile, get_user_state, reset_gpt_c_run_count
from prompts import PROFILE_EXTRACTION_ENHANCED_PROMPT
from gpt_utils import normalize_usage_dict, safe_get_usage_value

# הגדרת לוגר
logger = logging.getLogger(__name__)

def should_run_gpt_e(chat_id: str, gpt_c_run_count: int, last_gpt_e_timestamp: Optional[str]) -> bool:
    """
    בודק האם צריך להפעיל את gpt_e לפי התנאים שהוגדרו.
    
    :param chat_id: מזהה המשתמש
    :param gpt_c_run_count: מספר ריצות gpt_c מאז הפעם האחרונה ש-gpt_e רץ
    :param last_gpt_e_timestamp: טיימסטמפ של הריצה האחרונה של gpt_e
    :return: True אם צריך להפעיל gpt_e, False אחרת
    """
    # תנאי 1: הגענו ל-50 ריצות gpt_c
    if gpt_c_run_count >= 50:
        logger.info(f"[gpt_e] Triggering run - gpt_c_run_count >= 50 ({gpt_c_run_count})")
        return True
    
    # תנאי 2: מעל 20 ריצות gpt_c ועברו 24 שעות מאז הריצה האחרונה
    if gpt_c_run_count > 20 and last_gpt_e_timestamp:
        try:
            last_run = datetime.fromisoformat(last_gpt_e_timestamp.replace('Z', '+00:00'))
            time_since_last_run = datetime.now(last_run.tzinfo) - last_run
            
            if time_since_last_run >= timedelta(hours=24):
                logger.info(f"[gpt_e] Triggering run - {gpt_c_run_count} gpt_c runs and {time_since_last_run.total_seconds()/3600:.1f} hours since last run")
                return True
        except Exception as e:
            logger.error(f"[gpt_e] Error parsing last_gpt_e_timestamp: {e}")
    
    return False

def prepare_gpt_e_prompt(chat_history: List[Dict], current_profile: str) -> str:
    """
    מכין את הפרומפט ל-gpt_e עם ההיסטוריה והפרופיל הקיים.
    
    :param chat_history: רשימת הודעות מהשיחה
    :param current_profile: הפרופיל הרגשי הקיים
    :return: פרומפט מוכן לשליחה ל-GPT
    """
    # המרת היסטוריה לפורמט מתאים
    formatted_history = []
    for msg in chat_history:
        if msg.get('role') in ['user', 'assistant']:
            formatted_history.append({
                'role': msg['role'],
                'content': msg.get('text', msg.get('content', ''))
            })
    
    # יצירת פרומפט מותאם ל-gpt_e
    user_prompt = f"""
אתה מקבל היסטוריה של שיחה בין משתמש לבוט, ופרופיל רגשי קיים של המשתמש.

מטרתך: לזהות מידע חדש, לתקן טעויות, ולחדד את הפרופיל הרגשי.

היסטוריית השיחה (50 הודעות אחרונות):
{json.dumps(formatted_history, ensure_ascii=False, indent=2)}

פרופיל רגשי קיים:
{current_profile}

הנחיות:
1. זהה מידע חדש שלא נכלל בפרופיל הקיים
2. תקן טעויות או אי-דיוקים בפרופיל הקיים
3. חדד מידע קיים עם פרטים נוספים
4. החזר רק שדות חדשים/מתוקנים בפורמט JSON
5. אם אין מידע חדש - החזר {{}}
6. אם יש מידע אישי שלא נכנס לשום שדה - הוסף ל-"other_insights"

שדות מותרים:
- age, relationship_type, parental_status, occupation_or_role
- self_religious_affiliation, self_religiosity_level, family_religiosity
- closet_status, who_knows, who_doesnt_know, attracted_to
- attends_therapy, primary_conflict, trauma_history
- goal_in_course, fears_concerns, future_vision
- other_insights (מידע אישי נוסף)

החזר JSON בלבד:
"""

    return user_prompt

def run_gpt_e(chat_id: str) -> Dict[str, Any]:
    """
    מבצע חידוד ותיקון פרופיל רגשי למשתמש לפי ההנחיות.
    
    :param chat_id: מזהה המשתמש
    :return: מילון עם תוצאות הריצה (success, changes, errors)
    """
    start_time = datetime.now()
    logger.info(f"[gpt_e] Starting run_gpt_e for chat_id={chat_id} at {start_time.isoformat()}")
    
    result = {
        'success': False,
        'changes': {},
        'errors': [],
        'tokens_used': 0,
        'execution_time': 0
    }
    
    try:
        # שלב 1: שליפת היסטוריית שיחה
        logger.info(f"[gpt_e] Fetching chat history for chat_id={chat_id}")
        chat_history = get_chat_history_messages(chat_id, limit=50)
        
        if not chat_history:
            result['errors'].append("No chat history found")
            logger.warning(f"[gpt_e] No chat history found for chat_id={chat_id}")
            return result
        
        logger.info(f"[gpt_e] Retrieved {len(chat_history)} messages from chat history")
        
        # שלב 2: שליפת פרופיל קיים
        logger.info(f"[gpt_e] Fetching current profile for chat_id={chat_id}")
        current_profile = get_user_summary(chat_id)
        
        if not current_profile:
            current_profile = "אין פרופיל קיים"
            logger.info(f"[gpt_e] No existing profile found for chat_id={chat_id}")
        
        # שלב 3: הכנת פרומפט
        user_prompt = prepare_gpt_e_prompt(chat_history, current_profile)
        
        # שלב 4: שליחה ל-GPT
        logger.info(f"[gpt_e] Sending request to GPT for chat_id={chat_id}")
        
        try:
            import litellm
            from config import GPT_MODELS, GPT_PARAMS
            
            metadata = {"gpt_identifier": "gpt_e", "chat_id": chat_id}
            params = GPT_PARAMS["gpt_e"]
            model = GPT_MODELS["gpt_e"]
            
            completion_params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": PROFILE_EXTRACTION_ENHANCED_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": params["temperature"],
                "max_tokens": params["max_tokens"],
                "metadata": metadata,
                "store": True
            }
            
            response = litellm.completion(**completion_params)
            
            # חילוץ התוכן מהתגובה
            content = response.choices[0].message.content.strip()
            logger.info(f"[gpt_e] Received response from GPT: {content[:200]}...")
            
            # נירמול usage באופן בטוח
            usage = normalize_usage_dict(response.usage, response.model)
            
            # חילוץ cached_tokens בבטחה
            cached_tokens = safe_get_usage_value(response.usage, 'cached_tokens', 0)
            if cached_tokens == 0 and hasattr(response.usage, 'prompt_tokens_details'):
                cached_tokens = safe_get_usage_value(response.usage.prompt_tokens_details, 'cached_tokens', 0)
            
            # עדכון ה-usage עם cached_tokens
            usage["cached_tokens"] = cached_tokens
            
            result['tokens_used'] = response.usage.total_tokens
            result['cost_data'] = usage
            
        except Exception as e:
            result['errors'].append(f"GPT API error: {str(e)}")
            logger.error(f"[gpt_e] GPT API error for chat_id={chat_id}: {e}")
            return result
        
        if not content:
            result['errors'].append("Empty response from GPT")
            logger.error(f"[gpt_e] Empty response from GPT for chat_id={chat_id}")
            return result

        # שלב 5: ניתוח התגובה
        # ניסיון לחלץ JSON מהתגובה
        try:
            # חיפוש JSON בתגובה
            if content.startswith('{') and content.endswith('}'):
                changes = json.loads(content)
            else:
                # חיפוש JSON בתוך הטקסט
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx]
                    changes = json.loads(json_str)
                else:
                    changes = {}
            
            logger.info(f"[gpt_e] Parsed changes: {changes}")
            
            # שלב 6: עדכון הפרופיל אם יש שינויים
            if changes and isinstance(changes, dict):
                # הסרת שדות ריקים
                changes = {k: v for k, v in changes.items() if v and v != ""}
                
                if changes:
                    logger.info(f"[gpt_e] Updating profile with changes: {changes}")
                    update_user_profile(chat_id, changes)
                    result['changes'] = changes
                    logger.info(f"[gpt_e] Profile updated successfully for chat_id={chat_id}")
                else:
                    logger.info(f"[gpt_e] No meaningful changes found for chat_id={chat_id}")
            else:
                logger.info(f"[gpt_e] No changes to apply for chat_id={chat_id}")
                
        except json.JSONDecodeError as e:
            result['errors'].append(f"Failed to parse JSON response: {e}")
            logger.error(f"[gpt_e] JSON parsing error for chat_id={chat_id}: {e}")
            return result
        
        # שלב 7: עדכון סטטיסטיקות
        result['success'] = True
        result['execution_time'] = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"[gpt_e] Completed successfully for chat_id={chat_id} in {result['execution_time']:.2f}s")
        
    except Exception as e:
        result['errors'].append(f"Unexpected error: {str(e)}")
        logger.error(f"[gpt_e] Unexpected error for chat_id={chat_id}: {e}", exc_info=True)
    
    return result

def update_user_state_after_gpt_e(chat_id: str, result: Dict[str, Any]) -> None:
    """
    מעדכן את מצב המשתמש לאחר ריצת gpt_e.
    
    :param chat_id: מזהה המשתמש
    :param result: תוצאות הריצה
    """
    try:
        if result['success']:
            # איפוס מונה gpt_c_run_count ועדכון last_gpt_e_timestamp
            success = reset_gpt_c_run_count(chat_id)
            
            if success:
                logger.info(f"[gpt_e] Updated user state for chat_id={chat_id} after successful run")
            else:
                logger.error(f"[gpt_e] Failed to update user state for chat_id={chat_id}")
        else:
            logger.warning(f"[gpt_e] Not updating user state for chat_id={chat_id} due to failed run")
        
    except Exception as e:
        logger.error(f"[gpt_e] Error updating user state for chat_id={chat_id}: {e}")

def log_gpt_e_run(chat_id: str, result: Dict[str, Any]) -> None:
    """
    מתעד את ריצת gpt_e בלוגים.
    
    :param chat_id: מזהה המשתמש
    :param result: תוצאות הריצה
    """
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'chat_id': chat_id,
        'success': result['success'],
        'changes_count': len(result.get('changes', {})),
        'tokens_used': result.get('tokens_used', 0),
        'execution_time': result.get('execution_time', 0),
        'errors': result.get('errors', [])
    }
    
    if result.get('changes'):
        log_entry['changes'] = result['changes']
    
    logger.info(f"[gpt_e] Run log: {json.dumps(log_entry, ensure_ascii=False)}")

def execute_gpt_e_if_needed(chat_id: str, gpt_c_run_count: int, last_gpt_e_timestamp: str = None) -> Optional[Dict[str, Any]]:
    """
    בודק אם צריך להפעיל gpt_e ומפעיל אם כן.
    
    התנאים להפעלה:
    1. gpt_c_run_count >= 50
    2. או gpt_c_run_count >= 21 AND עברו 24 שעות מאז הריצה האחרונה
    
    :param chat_id: מזהה המשתמש
    :param gpt_c_run_count: מספר ריצות gpt_c מאז הריצה האחרונה של gpt_e
    :param last_gpt_e_timestamp: טיימסטמפ של הריצה האחרונה של gpt_e
    :return: תוצאות הריצה אם הופעל, None אם לא הופעל
    """
    logger.info(f"[gpt_e] Checking conditions for chat_id={chat_id}, gpt_c_run_count={gpt_c_run_count}")
    
    # בדיקה אם יש צורך להפעיל gpt_e
    should_run = False
    reason = ""
    
    # תנאי 1: 50 ריצות או יותר
    if gpt_c_run_count >= 50:
        should_run = True
        reason = f"gpt_c_run_count >= 50 (current: {gpt_c_run_count})"
    
    # תנאי 2: 21-49 ריצות + 24 שעות
    elif gpt_c_run_count >= 21:
        if last_gpt_e_timestamp:
            try:
                from datetime import datetime
                last_run = datetime.fromisoformat(last_gpt_e_timestamp.replace('Z', '+00:00'))
                now = datetime.now(last_run.tzinfo) if last_run.tzinfo else datetime.now()
                hours_since_last = (now - last_run).total_seconds() / 3600
                
                if hours_since_last >= 24:
                    should_run = True
                    reason = f"gpt_c_run_count >= 21 ({gpt_c_run_count}) AND 24+ hours passed ({hours_since_last:.1f}h)"
                else:
                    logger.info(f"[gpt_e] Not enough time passed: {hours_since_last:.1f}h < 24h")
            except Exception as e:
                logger.error(f"[gpt_e] Error parsing timestamp {last_gpt_e_timestamp}: {e}")
                # אם יש שגיאה בפענוח הטיימסטמפ, נפעיל gpt_e
                should_run = True
                reason = f"Error parsing timestamp, running gpt_e as fallback"
        else:
            # אין טיימסטמפ קודם, נפעיל gpt_e
            should_run = True
            reason = f"No previous gpt_e timestamp, running gpt_e"
    
    if should_run:
        logger.info(f"[gpt_e] Conditions met for chat_id={chat_id}: {reason}")
        result = run_gpt_e(chat_id)
        
        # עדכון מצב המשתמש ולוגים
        if result['success']:
            update_user_state_after_gpt_e(chat_id, result)
        
        log_gpt_e_run(chat_id, result)
        
        return result
    else:
        logger.info(f"[gpt_e] Conditions not met for chat_id={chat_id}, gpt_c_run_count={gpt_c_run_count}")
        return None 