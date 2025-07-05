"""
gpt_e_handler.py
----------------
מנוע gpt_e: חידוד, תיקון והשלמת פרופיל רגשי על בסיס היסטוריה ופרופיל קיים.
משתמש ב-Gemini 1.5 Pro (חינמי) - ללא צורך ב-fallback.

- מופעל כל 25 ריצות gpt_c, או מעל 15 ריצות gpt_c אם עברו 24 שעות מאז הריצה האחרונה.
- מתמקד בעדכון הקונפליקט המרכזי (primary_conflict) ושדות נוספים לפי הצורך.
- שולח ל-GPT את ההיסטוריה והפרופיל, מקבל שדות חדשים/מתוקנים בלבד.
- מעדכן Google Sheets, user_state, ולוגים.
"""

import logging
import asyncio
import json
import lazy_litellm as litellm
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz

# ייבוא פונקציות עזר
from utils import get_chat_history_messages, get_israel_time
from sheets_handler import get_user_summary, update_user_profile, get_user_state, reset_gpt_c_run_count
from prompts import build_profile_extraction_enhanced_prompt, JSON_RESPONSE_INSTRUCTION, JSON_EXAMPLE
from gpt_utils import normalize_usage_dict, safe_get_usage_value, measure_llm_latency, calculate_gpt_cost, extract_json_from_text
from config import GPT_MODELS, GPT_PARAMS

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
    # תנאי 1: הגענו ל-25 ריצות gpt_c
    if gpt_c_run_count >= 25:
        logger.info(f"[gpt_e] Triggering run - gpt_c_run_count >= 25 ({gpt_c_run_count})")
        return True
    
    # תנאי 2: מעל 15 ריצות gpt_c ועברו 24 שעות מאז הריצה האחרונה
    if gpt_c_run_count > 15 and last_gpt_e_timestamp:
        try:
            last_run = datetime.fromisoformat(last_gpt_e_timestamp.replace('Z', '+00:00'))
            time_since_last_run = datetime.now(last_run.tzinfo) - last_run
            
            if time_since_last_run >= timedelta(hours=24):
                logger.info(f"[gpt_e] Triggering run - {gpt_c_run_count} gpt_c runs and {time_since_last_run.total_seconds()/3600:.1f} hours since last run")
                return True
        except Exception as e:
            logger.error(f"[gpt_e] Error parsing last_gpt_e_timestamp: {e}")
    
    return False

def build_fields_list():
    """בונה רשימת שדות מותרים מfields_dict.py"""
    from prompts import _get_filtered_profile_fields
    
    # סינון שדות לא רלוונטיים לgpt_e
    relevant_fields = _get_filtered_profile_fields()
    
    # יצירת רשימה בפורמט קריא
    fields_list = []
    for i in range(0, len(relevant_fields), 3):  # 3 שדות בכל שורה
        row = ", ".join(relevant_fields[i:i+3])
        fields_list.append(f"- {row}")
    
    return "\n".join(fields_list)

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
    fields_list = build_fields_list()
    user_prompt = f"""
אתה מקבל היסטוריה של שיחה בין משתמש לבוט, ופרופיל רגשי קיים של המשתמש.

מטרתך: לזהות מידע חדש, לתקן טעויות, ולחדד את הפרופיל הרגשי.
דגש מיוחד על עדכון השדה "primary_conflict" - הקונפליקט המרכזי שעמו המשתמש מתמודד כרגע.

היסטוריית השיחה (50 הודעות אחרונות):
{json.dumps(formatted_history, ensure_ascii=False, indent=2)}

פרופיל רגשי קיים:
{current_profile}

הנחיות:
1. זהה מידע חדש שלא נכלל בפרופיל הקיים
2. תקן טעויות או אי-דיוקים בפרופיל הקיים  
3. חדד מידע קיים עם פרטים נוספים
4. **השדה primary_conflict הוא קריטי - עדכן אותו אם יש מידע חדש על מה שהמשתמש מתמודד איתו כרגע**
5. בדוק אם הקונפליקט המרכזי השתנה או התפתח בהודעות האחרונות
6. החזר רק שדות חדשים/מתוקנים בפורמט JSON
7. אם אין מידע חדש - החזר {{}}
8. אם יש מידע אישי שלא נכנס לשום שדה - הוסף ל-"other_insights"

שדות מותרים:
{fields_list}

דגש מיוחד: השדה "primary_conflict" צריך לשקף במדויק את מה שהמשתמש מתמודד איתו כרגע על בסיס ההיסטוריה האחרונה.

{JSON_RESPONSE_INSTRUCTION}
{JSON_EXAMPLE}
"""

    return user_prompt

async def run_gpt_e(chat_id: str) -> Dict[str, Any]:
    """
    מבצע חידוד ותיקון פרופיל רגשי למשתמש לפי ההנחיות.
    
    :param chat_id: מזהה המשתמש
    :return: מילון עם תוצאות הריצה (success, changes, errors)
    """
    start_time = get_israel_time()
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
        chat_history = get_chat_history_messages(chat_id, limit=15)
        
        if not chat_history:
            result['errors'].append("No chat history found")
            logger.warning(f"[gpt_e] No chat history found for chat_id={chat_id}")
            return result
        
        logger.info(f"[gpt_e] Retrieved {len(chat_history)} messages from chat history")
        
        # שלב 2: שליפת פרופיל קיים
        logger.info(f"[gpt_e] Fetching current profile for chat_id={chat_id}")
        current_profile = get_user_summary(chat_id)
        
        # דיבאג מפורט של הפרופיל הנוכחי
        print(f"[DEBUG] gpt_e_profile | chat={chat_id} | profile='{current_profile[:35]}{'...' if len(current_profile) > 35 else ''}'")
        
        if not current_profile:
            current_profile = "אין פרופיל קיים"
            logger.info(f"[gpt_e] No existing profile found for chat_id={chat_id}")
        
        # שלב 3: הכנת פרומפט
        user_prompt = prepare_gpt_e_prompt(chat_history, current_profile)
        
        # שלב 4: שליחה ל-GPT
        logger.info(f"[gpt_e] Sending request to GPT for chat_id={chat_id}")
        
        try:
            metadata = {"gpt_identifier": "gpt_e", "chat_id": chat_id}
            params = GPT_PARAMS["gpt_e"]
            model = GPT_MODELS["gpt_e"]
            
            completion_params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": build_profile_extraction_enhanced_prompt()},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": params["temperature"],
                "max_tokens": params["max_tokens"],
                "metadata": metadata
            }
            
            with measure_llm_latency(model):
                response = litellm.completion(**completion_params)
            
            # חילוץ התוכן מהתגובה
            content_raw = response.choices[0].message.content
            if content_raw is None:
                result['errors'].append("Empty response content from GPT")
                logger.error(f"[gpt_e] Empty response content from GPT for chat_id={chat_id}")
                return result
            
            content_raw = content_raw.strip()
            content = extract_json_from_text(content_raw)
            logger.info(f"[gpt_e] Received response from GPT: {content[:200] if content else 'None'}...")
            
            # נירמול usage באופן בטוח
            usage = normalize_usage_dict(response.usage, response.model)
            
            # חילוץ cached_tokens בבטחה
            cached_tokens = safe_get_usage_value(response.usage, 'cached_tokens', 0)
            if cached_tokens == 0 and hasattr(response.usage, 'prompt_tokens_details'):
                cached_tokens = safe_get_usage_value(response.usage.prompt_tokens_details, 'cached_tokens', 0)
            
            # עדכון ה-usage עם cached_tokens
            usage["cached_tokens"] = cached_tokens
            
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
                logger.warning(f"[gpt_e] Cost calc failed: {_cost_e}")
            
            result['tokens_used'] = response.usage.total_tokens
            result['cost_data'] = usage
            
            try:
                from gpt_jsonl_logger import GPTJSONLLogger
                GPTJSONLLogger.log_gpt_call(
                    log_path="data/openai_calls.jsonl",
                    gpt_type="E",
                    request=completion_params if 'completion_params' in locals() else {},
                    response=response.model_dump() if 'response' in locals() and hasattr(response, 'model_dump') else {},
                    cost_usd=usage.get("cost_total", 0) if 'usage' in locals() else 0,
                    extra={"chat_id": chat_id}
                )
            except Exception as log_exc:
                print(f"[LOGGING_ERROR] Failed to log GPT-E call: {log_exc}")
            
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
                try:
                    changes = json.loads(content)
                except json.JSONDecodeError as e:
                    logging.error(f"[GPT_E] JSON decode error: {e} | Content: {content[:200]}")
                    changes = {}
            else:
                # חיפוש JSON בתוך הטקסט
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx]
                    try:
                        changes = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logging.error(f"[GPT_E] JSON decode error: {e} | Content: {json_str[:200]}")
                        changes = {}
                else:
                    changes = {}
            
            logger.info(f"[gpt_e] Parsed changes: {changes}")
            
            # שלב 6: עדכון הפרופיל אם יש שינויים
            if changes and isinstance(changes, dict):
                # הסרת שדות ריקים
                changes = {k: v for k, v in changes.items() if v and v != ""}
                
                if changes:
                    logger.info(f"[gpt_e] Updating profile with changes: {changes}")
                    # הדפסת מידע חשוב על עדכון נתונים (תמיד יופיע!)
                    print(f"🔄 [GPT-E] מעדכן {len(changes)} שדות: {list(changes.keys())}")
                    if 'cost_data' in result and result['cost_data']:
                        print(f"💰 [GPT-E] עלות: {result['cost_data'].get('cost_total', 0):.6f}$ | טוקנים: {result['cost_data'].get('total_tokens', 0)}")
                    
                    # הדגשה מיוחדת לעדכון primary_conflict
                    if 'primary_conflict' in changes:
                        print(f"🎯 [GPT-E] עדכון קונפליקט מרכזי: {changes['primary_conflict'][:100]}...")
                    
                    # 🔧 הסרה: לא מעדכנים כאן כדי למנוע כפילות עם _handle_profile_updates
                    # await update_user_profile(chat_id, changes)
                    
                    result['changes'] = changes
                    logger.info(f"[gpt_e] Changes prepared for profile update: {changes}")
                    print(f"✅ [GPT-E] השינויים מוכנים לעדכון פרופיל")
                else:
                    logger.info(f"[gpt_e] No meaningful changes found for chat_id={chat_id}")
            else:
                logger.info(f"[gpt_e] No changes to apply for chat_id={chat_id}")
                
        except Exception as e:
            result['errors'].append(f"Failed to parse changes: {e}")
            logger.error(f"[gpt_e] Error parsing changes for chat_id={chat_id}: {e}")
            return result
        
        # שלב 7: עדכון סטטיסטיקות
        result['success'] = True
        result['execution_time'] = (get_israel_time() - start_time).total_seconds()
        
        logger.info(f"[gpt_e] Completed successfully for chat_id={chat_id} in {result['execution_time']:.2f}s")
        
    except Exception as e:
        result['errors'].append(f"Unexpected error: {str(e)}")
        logger.error(f"[gpt_e] Unexpected error for chat_id={chat_id}: {e}", exc_info=True)
    
    return result

async def update_user_state_after_gpt_e(chat_id: str, result: Dict[str, Any]) -> None:
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
        'timestamp': get_israel_time().isoformat(),
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

async def execute_gpt_e_if_needed(chat_id: str) -> Optional[Dict[str, Any]]:
    """
    בודק אם צריך להפעיל gpt_e (כל 10 הודעות משתמש) ומפעיל אם כן.
    :param chat_id: מזהה המשתמש
    :return: תוצאות הריצה אם הופעל, None אם לא הופעל
    """
    from chat_utils import get_user_stats_and_history
    logger.info(f"[gpt_e] Checking if should run for chat_id={chat_id} (every 10 user messages)")
    try:
        stats, _ = get_user_stats_and_history(chat_id)
        total_messages = stats.get("total_messages", 0)
        if total_messages > 0 and total_messages % 10 == 0:
            logger.info(f"[gpt_e] Triggered for chat_id={chat_id} (user sent {total_messages} messages)")
            result = await run_gpt_e(chat_id)
            if result['success']:
                await update_user_state_after_gpt_e(chat_id, result)
            log_gpt_e_run(chat_id, result)
            return result
        else:
            logger.info(f"[gpt_e] Not running for chat_id={chat_id} (user sent {total_messages} messages)")
            return None
    except Exception as e:
        logger.error(f"[gpt_e] Error in execute_gpt_e_if_needed: {e}")
        return None 