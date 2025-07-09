"""
gpt_c_handler.py
----------------
מנוע gpt_c: חילוץ מידע מהודעות משתמש לעדכון פרופיל
"""

from simple_logger import logger
from datetime import datetime
import json
import time
import lazy_litellm as litellm
import re
from prompts import build_profile_extraction_enhanced_prompt
from config import GPT_MODELS, GPT_PARAMS, GPT_FALLBACK_MODELS, should_log_data_extraction_debug, should_log_gpt_cost_debug
from gpt_utils import normalize_usage_dict, measure_llm_latency, calculate_gpt_cost, extract_json_from_text

def extract_user_info(user_msg, chat_id=None, message_id=None):
    """
    מחלץ מידע רלוונטי מהודעת המשתמש לעדכון הפרופיל שלו
    כולל מערכת fallback למקרה של rate limit ב-Gemini.
    """
    start_time = time.time()  # מדידת זמן התחלה
    
    # בדיקה קריטית - אם אין chat_id תקין, לא מפעילים GPT-C
    if not chat_id:
        logger.error("[GPT_C] chat_id is None - skipping GPT-C execution")
        print("❌ [GPT-C] chat_id is None - skipping GPT-C execution")
        return {"extracted_fields": {}, "usage": {}, "model": "none"}
    
    metadata = {"gpt_identifier": "gpt_c", "chat_id": chat_id, "message_id": message_id}
    params = GPT_PARAMS["gpt_c"]
    model = GPT_MODELS["gpt_c"]
    
    completion_params = {
        "model": model,
        "messages": [{"role": "system", "content": build_profile_extraction_enhanced_prompt()}, {"role": "user", "content": user_msg}],
        "temperature": params["temperature"],
        "metadata": metadata
    }
    
    # הוספת max_tokens רק אם הוא לא None
    if params["max_tokens"] is not None:
        completion_params["max_tokens"] = params["max_tokens"]
    
    # ניסיון עם המודל הראשי
    try:
        with measure_llm_latency(model):
            response = litellm.completion(**completion_params)
        content_raw = response.choices[0].message.content.strip()
        content = extract_json_from_text(content_raw)

        usage = normalize_usage_dict(response.usage, response.model)
        
        # ניסיון לפרס JSON עם לוגים מפורטים
        try:
            if content and content.strip():
                content_clean = content.strip()
                if content_clean.startswith("{") and content_clean.endswith("}"):
                    extracted_fields = json.loads(content_clean)
                    if not isinstance(extracted_fields, dict):
                        logger.warning(f"[GPT_C] JSON parsed but not a dict: {type(extracted_fields)}")
                        extracted_fields = {}
                else:
                    logger.warning(f"[GPT_C] Content doesn't look like JSON: {content_clean[:100]}...")
                    extracted_fields = {}
            else:
                extracted_fields = {}
        except json.JSONDecodeError as e:
            logger.error(f"[GPT_C] JSON decode error: {e} | Content: {content[:200] if content else 'None'}...")
            extracted_fields = {}
        except Exception as e:
            logger.error(f"[GPT_C] Unexpected error parsing JSON: {e} | Content: {content[:200] if content else 'None'}...")
            extracted_fields = {}
        
        # הדפסת מידע חשוב על חילוץ נתונים (תמיד יופיע!)
        print(f"🔍 [GPT-C] חולצו {len(extracted_fields)} שדות: {list(extracted_fields.keys())}")
        if should_log_gpt_cost_debug():
            print(f"💰 [GPT-C] עלות: {usage.get('cost_total', 0):.6f}$ | טוקנים: {usage.get('total_tokens', 0)}")
        if should_log_data_extraction_debug():
            print(f"📋 [GPT-C] נתונים שחולצו: {json.dumps(extracted_fields, ensure_ascii=False, indent=2)}")
        
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
            logger.warning(f"[gpt_c] Cost calc failed: {_cost_e}")
        
        # חישוב זמן עיבוד טהור
        gpt_duration = time.time() - start_time
        
        # 💾 שמירת מטריקות זמן GPT-C למסד הנתונים
        try:
            from db_manager import save_system_metrics
            save_system_metrics(
                metric_type="gpt_timing",
                chat_id=str(chat_id) if chat_id else None,
                gpt_latency_seconds=gpt_duration,
                additional_data={
                    "message_id": message_id,
                    "gpt_type": "C",
                    "model": response.model,
                    "tokens_used": usage.get("total_tokens", 0),
                    "cost_usd": usage.get("cost_total", 0),
                    "operation": "extract_user_info",
                    "extracted_fields_count": len(extracted_fields)
                }
            )
        except Exception as save_err:
            logger.warning(f"Could not save GPT-C timing metrics: {save_err}")
        
        result = {"extracted_fields": extracted_fields, "usage": usage, "model": response.model}
        try:
            from gpt_jsonl_logger import GPTJSONLLogger
            # בניית response מלא עם כל המידע הנדרש
            response_data = {
                "id": getattr(response, "id", ""),
                "choices": [
                    {
                        "message": {
                            "content": content_raw,
                            "role": "assistant"
                        }
                    }
                ],
                "usage": usage,
                "model": response.model
            }
            GPTJSONLLogger.log_gpt_call(
                log_path="data/openai_calls.jsonl",
                gpt_type="C",
                request=completion_params,
                response=response_data,
                cost_usd=usage.get("cost_total", 0),
                extra={
                    "chat_id": chat_id, 
                    "message_id": message_id,
                    "gpt_pure_latency": time.time() - start_time,
                    "processing_time_seconds": time.time() - start_time
                }
            )
        except Exception as log_exc:
            print(f"[LOGGING_ERROR] Failed to log GPT-C call: {log_exc}")
        return result
        
    except Exception as e:
        error_str = str(e)
        is_rate_limit = "429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower()
        
        if is_rate_limit and "gpt_c" in GPT_FALLBACK_MODELS:
            # ניסיון עם מודל fallback
            fallback_model = GPT_FALLBACK_MODELS["gpt_c"]
            logger.warning(f"[gpt_c] Rate limit for {model}, trying fallback: {fallback_model}")
            
            try:
                completion_params["model"] = fallback_model
                completion_params["metadata"]["fallback_used"] = True
                
                with measure_llm_latency(fallback_model):
                    response = litellm.completion(**completion_params)
                content_raw = response.choices[0].message.content.strip()
                content = extract_json_from_text(content_raw)

                usage = normalize_usage_dict(response.usage, response.model)
                
                # ניסיון לפרס JSON עם לוגים מפורטים (fallback)
                try:
                    if content and content.strip():
                        content_clean = content.strip()
                        if content_clean.startswith("{") and content_clean.endswith("}"):
                            extracted_fields = json.loads(content_clean)
                            if not isinstance(extracted_fields, dict):
                                logger.warning(f"[GPT_C FALLBACK] JSON parsed but not a dict: {type(extracted_fields)}")
                                extracted_fields = {}
                        else:
                            logger.warning(f"[GPT_C FALLBACK] Content doesn't look like JSON: {content_clean[:100]}...")
                            extracted_fields = {}
                    else:
                        extracted_fields = {}
                except json.JSONDecodeError as e:
                    logger.error(f"[GPT_C FALLBACK] JSON decode error: {e} | Content: {content[:200] if content else 'None'}...")
                    extracted_fields = {}
                except Exception as e:
                    logger.error(f"[GPT_C FALLBACK] Unexpected error parsing JSON: {e} | Content: {content[:200] if content else 'None'}...")
                    extracted_fields = {}
                
                logger.info(f"[gpt_c] Fallback successful: {fallback_model}")
                
                # הדפסת מידע חשוב על חילוץ נתונים (תמיד יופיע!)
                print(f"🔍 [GPT-C FALLBACK] חולצו {len(extracted_fields)} שדות: {list(extracted_fields.keys())}")
                if should_log_gpt_cost_debug():
                    print(f"💰 [GPT-C FALLBACK] עלות: {usage.get('cost_total', 0):.6f}$ | טוקנים: {usage.get('total_tokens', 0)}")
                if should_log_data_extraction_debug():
                    print(f"📋 [GPT-C FALLBACK] נתונים שחולצו: {json.dumps(extracted_fields, ensure_ascii=False, indent=2)}")
                
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
                    logger.warning(f"[gpt_c] Cost calc failed: {_cost_e}")
                
                result = {"extracted_fields": extracted_fields, "usage": usage, "model": response.model, "fallback_used": True}
                try:
                    from gpt_jsonl_logger import GPTJSONLLogger
                    # בניית response מלא עם כל המידע הנדרש
                    response_data = {
                        "id": getattr(response, "id", ""),
                        "choices": [
                            {
                                "message": {
                                    "content": content_raw,
                                    "role": "assistant"
                                }
                            }
                        ],
                        "usage": usage,
                        "model": response.model
                    }
                    GPTJSONLLogger.log_gpt_call(
                        log_path="data/openai_calls.jsonl",
                        gpt_type="C",
                        request=completion_params,
                        response=response_data,
                        cost_usd=usage.get("cost_total", 0),
                                                 extra={
                             "chat_id": chat_id, 
                             "message_id": message_id,
                             "gpt_pure_latency": time.time() - start_time,
                             "processing_time_seconds": time.time() - start_time
                         }
                    )
                except Exception as log_exc:
                    print(f"[LOGGING_ERROR] Failed to log GPT-C call: {log_exc}")
                return result
                
            except Exception as fallback_error:
                logger.error(f"[gpt_c] Fallback also failed: {fallback_error}")
                print(f"❌ [GPT-C] שגיאה גם ב-fallback: {fallback_error}")
                result = {"extracted_fields": {}, "usage": {}, "model": fallback_model}
                try:
                    from gpt_jsonl_logger import GPTJSONLLogger
                    # בניית response ריק במקרה שגיאה
                    response_data = {
                        "id": "",
                        "choices": [
                            {
                                "message": {
                                    "content": f"[שגיאה: {fallback_error}]",
                                    "role": "assistant"
                                }
                            }
                        ],
                        "usage": {},
                        "model": fallback_model
                    }
                    GPTJSONLLogger.log_gpt_call(
                        log_path="data/openai_calls.jsonl",
                        gpt_type="C",
                        request=completion_params,
                        response=response_data,
                        cost_usd=0,
                        extra={
                            "chat_id": chat_id, 
                            "message_id": message_id,
                            "gpt_pure_latency": 0,
                            "processing_time_seconds": 0
                        }
                    )
                except Exception as log_exc:
                    print(f"[LOGGING_ERROR] Failed to log GPT-C call: {log_exc}")
                return result
        else:
            logger.error(f"[gpt_c] Error (not rate limit): {e}")
            print(f"❌ [GPT-C] שגיאה: {e}")
            result = {"extracted_fields": {}, "usage": {}, "model": model}
            try:
                from gpt_jsonl_logger import GPTJSONLLogger
                # בניית response ריק במקרה שגיאה
                response_data = {
                    "id": "",
                    "choices": [
                        {
                            "message": {
                                "content": f"[שגיאה: {e}]",
                                "role": "assistant"
                            }
                        }
                    ],
                    "usage": {},
                    "model": model
                }
                GPTJSONLLogger.log_gpt_call(
                    log_path="data/openai_calls.jsonl",
                    gpt_type="C",
                    request=completion_params,
                    response=response_data,
                    cost_usd=0,
                    extra={
                        "chat_id": chat_id, 
                        "message_id": message_id,
                        "gpt_pure_latency": 0,
                        "processing_time_seconds": 0
                    }
                )
            except Exception as log_exc:
                print(f"[LOGGING_ERROR] Failed to log GPT-C call: {log_exc}")
            return result

def should_run_gpt_c(user_message):
    """
    בודק אם יש טעם להפעיל gpt_c על הודעה נתונה.
    מחזיר False רק על הודעות שאנחנו בטוחים שלא מכילות מידע חדש.
    הכלל: gpt_c מופעל תמיד, אלא אם כן ההודעה היא משהו שלא יכול להכיל מידע חדש.
    """
    if not user_message or not user_message.strip():
        return False
    message = user_message.strip()
    # ביטויים בסיסיים שלא יכולים להכיל מידע חדש
    base_phrases = [
        'היי', 'שלום', 'מה שלומך', 'מה נשמע', 'מה קורה', 'מה המצב',
        'תודה', 'תודה רבה', 'תודה לך', 'תודה מאוד', 'תודה ענקית', 'תודהה',
        'בסדר', 'אוקיי', 'אוקי', 'בסדר גמור', 'בסדר מושלם', 'אוקייי',
        'אני מבין', 'אה', 'וואו', 'מעניין', 'נכון', 'אכן', 'אה אה',
        'כן', 'לא', 'אולי', 'יכול להיות', 'אפשרי',
        'אני לא יודע', 'לא יודע', 'לא בטוח', 'לא יודע מה להגיד', 'אין לי מושג',
        'בהחלט', 'בטח', 'כמובן', 'ברור', 'ודאי', 'בוודאי',
        'מעולה', 'נהדר', 'מדהים', 'פנטסטי', 'מושלם',
        'אה אוקיי', 'אה בסדר', 'אה הבנתי', 'אה נכון',
        'כן לא', 'כן אולי', 'אולי כן', 'אולי לא',
        'אה אוקיי תודה', 'אה בסדר תודה', 'אה הבנתי תודה',
        'טוב', 'טוב מאוד', 'טוב מאד', 'לא רע', 'לא רע בכלל',
        'בסדר גמור', 'בסדר מושלם', 'בסדר לגמרי', 'בסדר לחלוטין',
        'מצוין', 'מצויין', 'מעולה', 'נהדר', 'מדהים', 'פנטסטי',
        'אני בסדר', 'אני טוב', 'אני מצוין', 'אני מעולה',
        'הכל טוב', 'הכל בסדר', 'הכל מצוין', 'הכל מעולה',
        'סבבה', 'סבבה גמורה', 'סבבה מושלמת',
        'קול', 'קול לגמרי', 'קול לחלוטין',
        'אחלה', 'אחלה גמורה', 'אחלה מושלמת',
        'יופי', 'יופי גמור', 'יופי מושלם',
        'מעולה', 'מעולה גמורה', 'מעולה מושלמת',
        'נהדר', 'נהדר לגמרי', 'נהדר לחלוטין',
        'מדהים', 'מדהים לגמרי', 'מדהים לחלוטין',
        'פנטסטי', 'פנטסטי לגמרי', 'פנטסטי לחלוטין',
        'מושלם', 'מושלם לגמרי', 'מושלם לחלוטין',
        'אני אוקיי', 'אני בסדר גמור', 'אני בסדר מושלם',
        'אני טוב מאוד', 'אני טוב מאד', 'אני טוב לגמרי',
        'אני מצוין לגמרי', 'אני מעולה לגמרי', 'אני נהדר לגמרי',
        'אני מדהים לגמרי', 'אני פנטסטי לגמרי', 'אני מושלם לגמרי',
        'טוב אחי', 'בסדר אחי', 'מעולה אחי', 'נהדר אחי', 'מדהים אחי',
        'סבבה אחי', 'קול אחי', 'אחלה אחי', 'יופי אחי', 'מושלם אחי',
        'אני בסדר אחי', 'אני טוב אחי', 'אני מעולה אחי', 'אני נהדר אחי',
        'הכל טוב אחי', 'הכל בסדר אחי', 'הכל מעולה אחי',
        'אחי', 'אח', 'אחיי', 'אחייי', 'אחיייי',
        'אחי טוב', 'אחי בסדר', 'אחי מעולה', 'אחי נהדר', 'אחי מדהים',
        'אחי סבבה', 'אחי קול', 'אחי אחלה', 'אחי יופי', 'אחי מושלם'
    ]
    # אימוג'י בלבד
    emoji_only = ['👍', '👎', '❤️', '😊', '😢', '😡', '🤔', '😅', '😂', '😭']
    # נקודות בלבד
    dots_only = ['...', '....', '.....', '......']
    # סימני קריאה בלבד
    exclamation_only = ['!!!', '!!!!', '!!!!!']
    # בדיקה אם ההודעה היא בדיוק ביטוי בסיסי
    message_lower = message.lower()
    for phrase in base_phrases:
        if message_lower == phrase.lower():
            return False
    # בדיקה אם ההודעה היא ביטוי בסיסי + תווים נוספים
    for phrase in base_phrases:
        phrase_lower = phrase.lower()
        # בדיקה אם ההודעה מתחילה בביטוי הבסיסי
        if message_lower.startswith(phrase_lower):
            # מה שנשאר אחרי הביטוי הבסיסי
            remaining = message_lower[len(phrase_lower):].strip()
            # אם מה שנשאר הוא רק תווים מותרים, אז לא להפעיל gpt_c
            if remaining in ['', '!', '?', ':)', ':(', '!:)', '?:(', '!:(', '?:)', '...', '....', '.....', '......', '!!!', '!!!!', '!!!!!']:
                return False
            # אם מה שנשאר הוא רק אימוג'י או שילוב של תווים מותרים
            # הסרת רווחים מהתחלה ומהסוף
            remaining_clean = remaining.strip()
            # בדיקה אם מה שנשאר הוא רק תווים מותרים
            allowed_chars = r'^[!?:\.\s\(\)]+$'
            if re.match(allowed_chars, remaining_clean):
                return False
    # בדיקה אם ההודעה היא רק אימוג'י
    if message in emoji_only:
        return False
    # בדיקה אם ההודעה היא רק נקודות
    if message in dots_only:
        return False
    # בדיקה אם ההודעה היא רק סימני קריאה
    if message in exclamation_only:
        return False
    # בדיקה אם ההודעה היא ביטוי + אימוג'י
    for phrase in base_phrases:
        phrase_lower = phrase.lower()
        if message_lower.startswith(phrase_lower):
            remaining = message_lower[len(phrase_lower):].strip()
            # בדיקה אם מה שנשאר הוא רק אימוג'י
            if remaining in ['👍', '👎', '❤️', '😊', '😢', '😡', '🤔', '😅', '😂', '😭']:
                return False
    # אם הגענו לכאן, ההודעה יכולה להכיל מידע חדש
    return True 