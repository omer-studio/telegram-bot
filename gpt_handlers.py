#!/usr/bin/env python3
"""
gpt_handlers.py - מקום אחד לכל הטיפול ב-GPT
🎯 איחוד מערכתי: כל הפונקציות שמטפלות ב-GPT במקום אחד
🔧 פשוט ונקי: כל GPT עם הלוגיקה שלו במקום נפרד
📊 קל לתחזוקה: אם יש בעיה, אתה יודע איפה לחפש
"""

import psycopg2
import json
import time
import queue
import threading
import subprocess
import asyncio
import traceback
import re
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager

# ייבואים מרכזיים
import lazy_litellm as litellm
from simple_logger import logger
from config import (
    config, GPT_MODELS, GPT_PARAMS, GPT_FALLBACK_MODELS, GEMINI_API_KEY, DATA_DIR,
    should_log_debug_prints, should_log_gpt_cost_debug, should_log_data_extraction_debug
)
from simple_config import TimeoutConfig
from user_friendly_errors import safe_str
from prompts import (
    SYSTEM_PROMPT, BOT_REPLY_SUMMARY_PROMPT, 
    build_profile_extraction_enhanced_prompt, build_profile_merge_prompt
)

# הגדרות מרכזיות
USD_TO_ILS = 3.7  # שער הדולר-שקל

# מוני פרופיל
profile_question_counters = {}
profile_question_cooldowns = {}

# אנליטיקה למודלים
filter_decisions_log = {
    "first_20_messages": 0,
    "length": 0,
    "keywords": 0, 
    "pattern": 0,
    "default": 0
}

# ספים ומילות מפתח
LONG_MESSAGE_THRESHOLD = 50
GPT_E_RUN_EVERY_MESSAGES = 10
GPT_E_SCAN_LAST_MESSAGES = 15

# =================================
# 🛠️ פונקציות עזר כלליות
# =================================

@contextmanager
def measure_llm_latency(model_name):
    """Context manager למדידת זמן תגובה של מודל LLM"""
    start_time = time.time()
    try:
        yield
    finally:
        latency = time.time() - start_time
        logger.info(f"⚡ [LATENCY] {model_name}: {latency:.3f}s")
        if latency > 5:
            logger.warning(f"🐌 [SLOW_LATENCY] {model_name} איטי: {latency:.2f}s")
        if latency > 10:
            logger.error(f"🚨 [VERY_SLOW] {model_name} מאוד איטי: {latency:.2f}s")

def safe_get_usage_value(obj, attr_name, default=0):
    """מחלץ ערך מusage object באופן בטוח"""
    try:
        if hasattr(obj, attr_name):
            value = getattr(obj, attr_name)
            if hasattr(value, '__dict__'):
                return default
            return int(value) if value is not None else default
        return default
    except (ValueError, TypeError, AttributeError):
        return default

def normalize_usage_dict(usage, model_name=""):
    """מנרמל מילון usage של GPT לפורמט אחיד"""
    if not usage:
        return {}
    
    if hasattr(usage, '__dict__'):
        try:
            result = {
                "prompt_tokens": safe_get_usage_value(usage, 'prompt_tokens', 0),
                "completion_tokens": safe_get_usage_value(usage, 'completion_tokens', 0),
                "total_tokens": safe_get_usage_value(usage, 'total_tokens', 0),
            }
            
            # חיפוש cached_tokens
            cached_tokens = 0
            if hasattr(usage, 'prompt_tokens_details'):
                cached_tokens = safe_get_usage_value(usage.prompt_tokens_details, 'cached_tokens', 0)
            elif hasattr(usage, 'cached_tokens'):
                cached_tokens = safe_get_usage_value(usage, 'cached_tokens', 0)
            
            result["cached_tokens"] = cached_tokens
            result["model"] = model_name
            return result
        except Exception as e:
            if should_log_debug_prints():
                print(f"[DEBUG] שגיאה בנירמול usage: {e}")
            return {"model": model_name, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}
    
    if isinstance(usage, dict):
        result = dict(usage)
        result["model"] = model_name
        return result
    
    return {"model": model_name, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}

def calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens=0, model_name=None, usd_to_ils=USD_TO_ILS, completion_response=None):
    """מחשב את העלות של שימוש ב-GPT"""
    if model_name is None:
        model_name = GPT_MODELS["gpt_a"]
    
    if should_log_gpt_cost_debug():
        print(f"[DEBUG] calculate_gpt_cost - Model: {model_name}, Tokens: {prompt_tokens}p + {completion_tokens}c + {cached_tokens}cache")
    
    try:
        if completion_response:
            cost_usd = litellm.completion_cost(completion_response=completion_response)
        else:
            cost_usd = 0.0
        
        cost_ils = cost_usd * usd_to_ils
        cost_agorot = cost_ils * 100
        
        result = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_tokens": cached_tokens,
            "cost_total": cost_usd,
            "cost_total_ils": cost_ils,
            "cost_agorot": cost_agorot,
            "model": model_name
        }
        
        if should_log_gpt_cost_debug():
            print(f"[DEBUG] calculate_gpt_cost returning: {result}")
        
        return result
        
    except Exception as e:
        if should_log_gpt_cost_debug():
            print(f"[ERROR] calculate_gpt_cost failed: {e}")
        
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_tokens": cached_tokens,
            "cost_total": 0.0,
            "cost_total_ils": 0.0,
            "cost_agorot": 0.0,
            "model": model_name
        }

def extract_json_from_text(text: str) -> str:
    """מחלץ JSON מטקסט שיכול להכיל תווים נוספים"""
    if not text:
        return ""
    
    # חיפוש JSON בתוך הטקסט
    try:
        # חיפוש אחר { ו } הראשונים והאחרונים
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]
            # בדיקה שזה JSON תקין
            json.loads(json_str)
            return json_str
        
        # אם לא מצאנו JSON, מחזירים את הטקסט כמו שהוא
        return text.strip()
        
    except json.JSONDecodeError:
        # אם זה לא JSON תקין, מחזירים את הטקסט כמו שהוא
        return text.strip()

def get_current_commit_hash() -> str:
    """קבלת hash הקומיט הנוכחי"""
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                               capture_output=True, text=True, timeout=TimeoutConfig.SUBPROCESS_TIMEOUT)
        return result.stdout.strip()[:12] if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"

# =================================
# 🎯 GPT-A Handler - התשובה הראשית
# =================================

class GPTAHandler:
    """מנהל GPT-A - התשובה הראשית של הבוט"""
    
    def __init__(self):
        self.premium_model_keywords = [
            # זוגיות ומערכות יחסים
            "נישואין", "חתונה", "זוגיות", "מערכת יחסים", "בן זוג", "בת זוג",
            "אהבה", "רגשות", "קשר", "זיקה", "משיכה", "אינטימיות", "מיניות",
            # פסיכולוגיה ובריאות נפש
            "פסיכולוגיה", "טיפול", "ייעוץ", "פסיכולוג", "מטפל", "דיכאון", "חרדה",
            "פחד", "דאגה", "בלבול", "לחץ", "סטרס", "טראומה", "בדידות",
            # דתיות ואמונה
            "דתיות", "חילוני", "דתי", "מסורתי", "אמונה", "מצוות", "הלכה",
            "כשרות", "שבת", "חג", "תפילה", "בית כנסת", "תורה", "יהדות",
            # נטייה מינית וזהות מינית
            "הומו", "גיי", "ביסקסואל", "להט״ב", "נטייה מינית", "זהות מינית",
            "בארון", "יציאה מהארון", "ארוניסט", "הקהילה הגאה"
        ]
        
        self.complex_patterns = [
            r"מה\s+עושים\s+כש|איך\s+להתמודד\s+עם|צריך\s+עצה\s+ב|לא\s+יודע\s+איך",
            r"לא\s+מרגיש\s+שלם|אני\s+תקוע|מרגיש\s+אבוד|אני\s+שונא\s+את\s+עצמי",
            r"לא\s+שלם\s+עם|קושי\s+ל[ק|כ]בל|עדיין\s+לא\s+שלם|התמודדות\s+עם",
            r"נשוי\s+ל|לא\s+מצליח\s+למצוא|יצאתי\s+אבל\s+לא\s+באמת"
        ]
    
    def should_use_premium_model(self, user_message: str, chat_history_length: int = 0) -> tuple:
        """מחליט האם להשתמש במודל המתקדם או המהיר"""
        global filter_decisions_log
        
        # בדיקה 1: 20 ההודעות הראשונות
        if chat_history_length <= 20:
            filter_decisions_log["first_20_messages"] += 1
            return True, f"20 ההודעות הראשונות ({chat_history_length}/20)", "first_20_messages"
        
        # בדיקת אורך הודעה
        word_count = len(user_message.split())
        if word_count > LONG_MESSAGE_THRESHOLD:
            filter_decisions_log["length"] += 1
            return True, f"הודעה ארוכה ({word_count} מילים)", "length"
        
        # בדיקת מילות מפתח
        user_message_lower = user_message.lower()
        found_keywords = [keyword for keyword in self.premium_model_keywords if keyword in user_message_lower]
        if found_keywords:
            filter_decisions_log["keywords"] += 1
            return True, f"מילות מפתח: {', '.join(found_keywords[:3])}", "keywords"
        
        # בדיקת דפוסי ביטויים מורכבים
        for pattern in self.complex_patterns:
            if re.search(pattern, user_message_lower):
                filter_decisions_log["pattern"] += 1
                return True, "דפוס מורכב זוהה", "pattern"
        
        # מקרה רגיל - מודל מהיר
        filter_decisions_log["default"] += 1
        return False, "מקרה רגיל - מודל מהיר", "default"
    
    def should_ask_profile_question(self, chat_id: str) -> bool:
        """בודק אם הגיע הזמן לשאול שאלת פרופיל"""
        safe_chat_id = safe_str(chat_id)
        
        if safe_chat_id not in profile_question_cooldowns:
            profile_question_cooldowns[safe_chat_id] = 0
        
        if profile_question_cooldowns[safe_chat_id] > 0:
            profile_question_cooldowns[safe_chat_id] -= 1
            return False
        
        return True
    
    def start_profile_question_cooldown(self, chat_id: str):
        """מתחיל פסק זמן של 3 הודעות אחרי שאלה"""
        safe_chat_id = safe_str(chat_id)
        profile_question_cooldowns[safe_chat_id] = 3
    
    def create_missing_fields_system_message(self, chat_id: str) -> tuple:
        """יוצר system message עם שדות חסרים"""
        try:
            safe_chat_id = safe_str(chat_id)
            
            if not self.should_ask_profile_question(safe_chat_id):
                return "", ""
            
            from profile_utils import get_user_profile
            from fields_dict import FIELDS_DICT
            
            profile_data = get_user_profile(safe_chat_id) or {}
            
            key_fields = ["name", "age", "attracted_to", "relationship_type", "self_religious_affiliation", 
                         "closet_status", "pronoun_preference", "occupation_or_role", 
                         "self_religiosity_level", "primary_conflict", "goal_in_course"]
            
            missing = [FIELDS_DICT[f]["missing_question"] for f in key_fields
                      if f in FIELDS_DICT and not str(profile_data.get(f, "")).strip() 
                      and FIELDS_DICT[f].get("missing_question", "").strip()]
            
            if len(missing) >= 2:
                missing_text = ', '.join(missing[:4])
                return f"""פרטים שהמשתמש עדיין לא סיפר לך: {missing_text}
\nתסביר לו למה אתה שואל, תבחר שאלה מתאימה ותשאל בעדינות. (שאלות בכתב מודגש)""", missing_text
            
            return "", ""
            
        except Exception as e:
            logger.error(f"שגיאה ביצירת הודעת שדות חסרים: {e}")
            return "", ""
    
    def clean_bot_response(self, bot_reply: str) -> str:
        """מנקה תשובת בוט מטקסט טכני"""
        if not bot_reply:
            return ""
        
        # ניקוי תגי HTML
        bot_reply = bot_reply.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
        bot_reply = re.sub(r'<br\s*/?>', '\n', bot_reply)
        
        # ניקוי טקסט טכני
        technical_phrases = [
            "בהתבסס על הפרומפט שלי",
            "על פי ההוראות שקיבלתי",
            "כפי שמוגדר בהוראות",
            "לפי המידע שיש לי",
            "בהתאם להגדרות שלי"
        ]
        
        for phrase in technical_phrases:
            bot_reply = bot_reply.replace(phrase, "")
        
        return bot_reply.strip()
    
    def detect_profile_question_in_response(self, bot_reply: str) -> bool:
        """בודק האם הבוט שאל שאלת פרופיל"""
        if not bot_reply:
            return False
        
        profile_questions = [
            "איך קוראים לך", "מה השם שלך", "בן כמה אתה", "מה הגיל שלך",
            "איפה אתה גר", "מה העבודה שלך", "עם מי אתה גר"
        ]
        
        for question in profile_questions:
            if question in bot_reply:
                return True
        
        return False
    
    def get_main_response_sync(self, full_messages: list, chat_id: str, message_id: str = None, 
                              use_extra_emotion: bool = True, filter_reason: str = "", 
                              match_type: str = "unknown") -> Dict[str, Any]:
        """מנוע GPT-A הראשי - גרסה סינכרונית"""
        total_start_time = time.time()
        prep_start_time = time.time()
        
        prep_time = time.time() - prep_start_time
        
        metadata = {"gpt_identifier": "gpt_a", "chat_id": chat_id, "message_id": message_id}
        params = GPT_PARAMS["gpt_a"]
        
        # בחירת מודל
        if use_extra_emotion:
            model = GPT_MODELS["gpt_a"]
            model_tier = "premium"
        else:
            model = GPT_FALLBACK_MODELS["gpt_a"]
            model_tier = "fast"
        
        completion_params = {
            "model": model,
            "messages": full_messages,
            "temperature": params["temperature"],
            "metadata": metadata
        }
        
        if params["max_tokens"] is not None:
            completion_params["max_tokens"] = params["max_tokens"]
        
        # הרצת GPT
        gpt_start_time = time.time()
        
        try:
            with measure_llm_latency(model):
                response = litellm.completion(**completion_params)
            
            gpt_duration = time.time() - gpt_start_time
            
            # עיבוד התשובה
            bot_reply = response.choices[0].message.content
            bot_reply = self.clean_bot_response(bot_reply)
            
            usage = normalize_usage_dict(response.usage, model)
            
            # הוספת חישוב עלות
            try:
                cost_info = calculate_gpt_cost(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    cached_tokens=usage.get("cached_tokens", 0),
                    model_name=model,
                    completion_response=response
                )
                usage.update(cost_info)
            except Exception as cost_e:
                logger.warning(f"[gpt_a] Cost calc failed: {cost_e}")
            
            # בדיקת שאלת פרופיל
            if chat_id and self.detect_profile_question_in_response(bot_reply):
                self.start_profile_question_cooldown(chat_id)
            
            processing_time = time.time() - gpt_start_time
            
            result = {
                "bot_reply": bot_reply,
                "usage": usage,
                "model": model,
                "used_extra_emotion": use_extra_emotion,
                "filter_reason": filter_reason,
                "match_type": match_type,
                "gpt_pure_latency": gpt_duration,
                "processing_time": processing_time
            }
            
            return result
            
        except Exception as e:
            logger.error(f"[gpt_a] שגיאה במודל {model}: {e}")
            return {
                "bot_reply": "מצטער, יש לי בעיה טכנית. אנא נסה שוב.",
                "usage": {},
                "model": model,
                "error": str(e)
            }
    
    async def send_temporary_message_after_delay(self, update, chat_id: str, delay_seconds: int = 8):
        """שולח הודעה זמנית אחרי דיליי"""
        try:
            await asyncio.sleep(delay_seconds)
            
            if asyncio.current_task().cancelled():
                return None
            
            from message_handler import send_system_message
            temp_message_text = "⏳ אני עובד על תשובה בשבילך... זה מיד אצלך..."
            await send_system_message(update, chat_id, temp_message_text)
            
            return None
            
        except asyncio.CancelledError:
            return None
        except Exception as e:
            logger.error(f"❌ [TEMP_MSG] שגיאה בשליחת הודעה זמנית: {e}")
            return None
    
    async def delete_temporary_message_and_send_new(self, update, temp_message, new_text: str):
        """מוחק הודעה זמנית ושולח תשובה חדשה"""
        from message_handler import send_message
        
        try:
            chat_id = update.message.chat_id
            await send_message(update, chat_id, new_text, is_bot_message=True, is_gpt_a_response=True)
            return True
            
        except Exception as e:
            logger.error(f"❌ [DELETE_MSG] כשל בשליחה: {e}")
            return False

# =================================
# 🔄 GPT-B Handler - סיכומים
# =================================

class GPTBHandler:
    """מנהל GPT-B - יצירת סיכומים קצרים"""
    
    def get_summary(self, user_msg: str, bot_reply: str, chat_id: str, message_id: str = None) -> Dict[str, Any]:
        """יוצר סיכום קצר של הקשר השיחה"""
        try:
            start_time = time.time()
            
            metadata = {"gpt_identifier": "gpt_b", "chat_id": safe_str(chat_id), "message_id": message_id}
            params = GPT_PARAMS["gpt_b"]
            model = GPT_MODELS["gpt_b"]
            
            messages = [
                {"role": "system", "content": BOT_REPLY_SUMMARY_PROMPT},
                {"role": "user", "content": bot_reply}
            ]
            
            completion_params = {
                "model": model,
                "messages": messages,
                "temperature": params["temperature"],
                "metadata": metadata
            }
            
            if params["max_tokens"] is not None:
                completion_params["max_tokens"] = params["max_tokens"]
            
            with measure_llm_latency(model):
                response = litellm.completion(**completion_params)
            
            summary = response.choices[0].message.content.strip()
            usage = normalize_usage_dict(response.usage, response.model)
            
            gpt_duration = time.time() - start_time
            
            # הוספת חישוב עלות
            try:
                cost_info = calculate_gpt_cost(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    cached_tokens=usage.get("cached_tokens", 0),
                    model_name=response.model,
                    completion_response=response
                )
                usage.update(cost_info)
            except Exception as cost_e:
                logger.warning(f"[gpt_b] Cost calc failed: {cost_e}")
            
            return {"summary": summary, "usage": usage, "model": response.model}
            
        except Exception as e:
            logger.error(f"[gpt_b] Error: {e}")
            return {"summary": f"[סיכום: {user_msg[:50]}...]", "usage": {}, "model": model}

# =================================
# 🔍 GPT-C Handler - חילוץ מידע
# =================================

class GPTCHandler:
    """מנהל GPT-C - חילוץ מידע מהודעות לפרופיל"""
    
    def should_run_gpt_c(self, user_message: str) -> bool:
        """בודק אם יש טעם להפעיל GPT-C"""
        if not user_message or not user_message.strip():
            return False
        
        message = user_message.strip()
        
        # ביטויים בסיסיים שלא מכילים מידע חדש
        base_phrases = [
            'היי', 'שלום', 'מה שלומך', 'תודה', 'בסדר', 'אוקיי', 'כן', 'לא',
            'אני מבין', 'וואו', 'מעניין', 'נכון', 'בהחלט', 'מעולה', 'נהדר'
        ]
        
        message_lower = message.lower()
        
        # בדיקה אם ההודעה היא בדיוק ביטוי בסיסי
        for phrase in base_phrases:
            if message_lower == phrase.lower():
                return False
        
        # בדיקה אם ההודעה מתחילה בביטוי בסיסי ואחר כך רק תווים פשוטים
        for phrase in base_phrases:
            phrase_lower = phrase.lower()
            if message_lower.startswith(phrase_lower):
                remaining = message_lower[len(phrase_lower):].strip()
                if remaining in ['', '!', '?', ':)', ':(', '...', '!!!']:
                    return False
        
        return True
    
    def extract_user_info(self, user_msg: str, chat_id: str, message_id: str = None) -> Dict[str, Any]:
        """מחלץ מידע רלוונטי מהודעת המשתמש"""
        start_time = time.time()
        
        safe_chat_id = safe_str(chat_id)
        metadata = {"gpt_identifier": "gpt_c", "chat_id": safe_chat_id, "message_id": message_id}
        params = GPT_PARAMS["gpt_c"]
        model = GPT_MODELS["gpt_c"]
        
        completion_params = {
            "model": model,
            "messages": [
                {"role": "system", "content": build_profile_extraction_enhanced_prompt()},
                {"role": "user", "content": user_msg}
            ],
            "temperature": params["temperature"],
            "metadata": metadata
        }
        
        if params["max_tokens"] is not None:
            completion_params["max_tokens"] = params["max_tokens"]
        
        try:
            with measure_llm_latency(model):
                response = litellm.completion(**completion_params)
            
            content_raw = response.choices[0].message.content.strip()
            content = extract_json_from_text(content_raw)
            usage = normalize_usage_dict(response.usage, response.model)
            
            # פרסינג JSON
            try:
                if content and content.strip():
                    content_clean = content.strip()
                    if content_clean.startswith("{") and content_clean.endswith("}"):
                        extracted_fields = json.loads(content_clean)
                        if not isinstance(extracted_fields, dict):
                            extracted_fields = {}
                    else:
                        extracted_fields = {}
                else:
                    extracted_fields = {}
            except json.JSONDecodeError as e:
                logger.error(f"[GPT_C] JSON decode error: {e}")
                extracted_fields = {}
            
            print(f"🔍 [GPT-C] חולצו {len(extracted_fields)} שדות: {list(extracted_fields.keys())}")
            
            # הוספת חישוב עלות
            try:
                cost_info = calculate_gpt_cost(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    cached_tokens=usage.get("cached_tokens", 0),
                    model_name=response.model,
                    completion_response=response
                )
                usage.update(cost_info)
            except Exception as cost_e:
                logger.warning(f"[gpt_c] Cost calc failed: {cost_e}")
            
            return {"extracted_fields": extracted_fields, "usage": usage, "model": response.model}
            
        except Exception as e:
            error_str = str(e)
            is_rate_limit = "429" in error_str or "quota" in error_str.lower()
            
            if is_rate_limit and "gpt_c" in GPT_FALLBACK_MODELS:
                # ניסיון עם fallback
                fallback_model = GPT_FALLBACK_MODELS["gpt_c"]
                logger.warning(f"[gpt_c] Rate limit, trying fallback: {fallback_model}")
                
                try:
                    completion_params["model"] = fallback_model
                    
                    with measure_llm_latency(fallback_model):
                        response = litellm.completion(**completion_params)
                    
                    content_raw = response.choices[0].message.content.strip()
                    content = extract_json_from_text(content_raw)
                    usage = normalize_usage_dict(response.usage, response.model)
                    
                    # פרסינג JSON
                    try:
                        if content and content.strip():
                            content_clean = content.strip()
                            if content_clean.startswith("{") and content_clean.endswith("}"):
                                extracted_fields = json.loads(content_clean)
                                if not isinstance(extracted_fields, dict):
                                    extracted_fields = {}
                            else:
                                extracted_fields = {}
                        else:
                            extracted_fields = {}
                    except json.JSONDecodeError as e:
                        logger.error(f"[GPT_C FALLBACK] JSON decode error: {e}")
                        extracted_fields = {}
                    
                    # הוספת חישוב עלות
                    try:
                        cost_info = calculate_gpt_cost(
                            prompt_tokens=usage.get("prompt_tokens", 0),
                            completion_tokens=usage.get("completion_tokens", 0),
                            cached_tokens=usage.get("cached_tokens", 0),
                            model_name=response.model,
                            completion_response=response
                        )
                        usage.update(cost_info)
                    except Exception as cost_e:
                        logger.warning(f"[gpt_c] Cost calc failed: {cost_e}")
                    
                    return {"extracted_fields": extracted_fields, "usage": usage, "model": response.model, "fallback_used": True}
                    
                except Exception as fallback_error:
                    logger.error(f"[gpt_c] Fallback also failed: {fallback_error}")
                    return {"extracted_fields": {}, "usage": {}, "model": fallback_model}
            else:
                logger.error(f"[gpt_c] Error: {e}")
                return {"extracted_fields": {}, "usage": {}, "model": model}

# =================================
# 🔄 GPT-D Handler - מיזוג פרופיל
# =================================

class GPTDHandler:
    """מנהל GPT-D - מיזוג נתונים בפרופיל"""
    
    def merge_profile_data(self, existing_profile: Dict, new_extracted_fields: Dict, 
                          chat_id: str, message_id: str = None) -> Dict[str, Any]:
        """מיזוג נתונים חדשים עם פרופיל קיים"""
        start_time = time.time()
        
        safe_chat_id = safe_str(chat_id)
        metadata = {"gpt_identifier": "gpt_d", "chat_id": safe_chat_id, "message_id": message_id}
        params = GPT_PARAMS["gpt_d"]
        model = GPT_MODELS["gpt_d"]
        
        merge_prompt = build_profile_merge_prompt(existing_profile, new_extracted_fields)
        
        completion_params = {
            "model": model,
            "messages": [{"role": "user", "content": merge_prompt}],
            "temperature": params["temperature"],
            "metadata": metadata
        }
        
        if params["max_tokens"] is not None:
            completion_params["max_tokens"] = params["max_tokens"]
        
        try:
            with measure_llm_latency(model):
                response = litellm.completion(**completion_params)
            
            content_raw = response.choices[0].message.content.strip()
            content = extract_json_from_text(content_raw)
            usage = normalize_usage_dict(response.usage, response.model)
            
            # פרסינג JSON
            try:
                if content and content.strip():
                    content_clean = content.strip()
                    if content_clean.startswith("{") and content_clean.endswith("}"):
                        merged_profile = json.loads(content_clean)
                        if not isinstance(merged_profile, dict):
                            merged_profile = existing_profile
                    else:
                        merged_profile = existing_profile
                else:
                    merged_profile = existing_profile
            except json.JSONDecodeError as e:
                logger.error(f"[GPT_D] JSON decode error: {e}")
                merged_profile = existing_profile
            
            if should_log_data_extraction_debug():
                print(f"🔄 [GPT-D] מיזוג הושלם: {len(merged_profile)} שדות")
            
            # הוספת חישוב עלות
            try:
                cost_info = calculate_gpt_cost(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    cached_tokens=usage.get("cached_tokens", 0),
                    model_name=response.model,
                    completion_response=response
                )
                usage.update(cost_info)
            except Exception as cost_e:
                logger.warning(f"[gpt_d] Cost calc failed: {cost_e}")
            
            return {"merged_profile": merged_profile, "usage": usage, "model": response.model}
            
        except Exception as e:
            logger.error(f"[gpt_d] Error: {e}")
            return {"merged_profile": existing_profile, "usage": {}, "model": model}
    
    def smart_update_profile_async(self, chat_id: str, user_message: str, 
                                  interaction_id: str = None, gpt_c_result: Dict = None):
        """עדכון חכם של פרופיל באסינכרון"""
        async def _update_profile():
            try:
                from profile_utils import get_user_profile_fast, update_user_profile_fast
                
                safe_chat_id = safe_str(chat_id)
                existing_profile = get_user_profile_fast(safe_chat_id)
                
                if gpt_c_result and isinstance(gpt_c_result, dict):
                    extracted_fields = gpt_c_result.get("extracted_fields", {})
                    
                    # בדיקת קונפליקטים
                    if existing_profile and extracted_fields:
                        has_conflicts = False
                        for field, new_value in extracted_fields.items():
                            if field in existing_profile and existing_profile[field] and existing_profile[field] != new_value:
                                has_conflicts = True
                                break
                        
                        if has_conflicts:
                            # יש קונפליקט - השתמש ב-GPT-D
                            merge_result = self.merge_profile_data(existing_profile, extracted_fields, safe_chat_id, interaction_id)
                            updated_profile = merge_result["merged_profile"]
                        else:
                            # אין קונפליקט - מיזוג פשוט
                            updated_profile = existing_profile.copy()
                            updated_profile.update(extracted_fields)
                    else:
                        # מיזוג פשוט
                        updated_profile = (existing_profile or {}).copy()
                        updated_profile.update(extracted_fields)
                    
                    # שמירה למסד נתונים
                    update_user_profile_fast(safe_chat_id, updated_profile)
                    
            except Exception as e:
                logger.error(f"[GPT_D] Error in profile update: {e}")
        
        # הרצה באסינכרון
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: asyncio.run(_update_profile()))

# =================================
# 📊 GPT-E Handler - עדכון מקיף
# =================================

class GPTEHandler:
    """מנהל GPT-E - עדכון פרופיל מקיף"""
    
    def should_run_gpt_e(self, chat_id: str, total_messages: int) -> bool:
        """בודק אם צריך להריץ GPT-E"""
        if total_messages > 0 and total_messages % GPT_E_RUN_EVERY_MESSAGES == 0:
            return True
        return False
    
    async def run_gpt_e(self, chat_id: str) -> Dict[str, Any]:
        """מריץ GPT-E עבור משתמש"""
        safe_chat_id = safe_str(chat_id)
        start_time = datetime.now()
        
        try:
            # שלב 1: אספת היסטוריית שיחות
            from chat_utils import get_chat_history_messages
            chat_history = get_chat_history_messages(safe_chat_id, limit=GPT_E_SCAN_LAST_MESSAGES)
            
            if not chat_history:
                return {"success": False, "error": "No chat history found"}
            
            # שלב 2: אספת פרופיל נוכחי
            try:
                from profile_utils import get_user_summary_fast
                current_profile = get_user_summary_fast(safe_chat_id) or ""
            except ImportError:
                current_profile = ""
            
            # שלב 3: הרצת GPT-E
            metadata = {"gpt_identifier": "gpt_e", "chat_id": safe_chat_id}
            params = GPT_PARAMS["gpt_e"]
            model = GPT_MODELS["gpt_e"]
            
            prompt = f"היסטוריית השיחה: {json.dumps(chat_history, ensure_ascii=False)}\n\nפרופיל נוכחי: {current_profile}\n\nעדכן את הפרופיל על סמך ההיסטוריה."
            
            completion_params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": params["temperature"],
                "metadata": metadata
            }
            
            if params["max_tokens"] is not None:
                completion_params["max_tokens"] = params["max_tokens"]
            
            response = litellm.completion(**completion_params)
            
            content_raw = response.choices[0].message.content.strip()
            content = extract_json_from_text(content_raw)
            usage = normalize_usage_dict(response.usage, response.model)
            
            # הוספת חישוב עלות
            try:
                cost_info = calculate_gpt_cost(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    cached_tokens=usage.get("cached_tokens", 0),
                    model_name=response.model,
                    completion_response=response
                )
                usage.update(cost_info)
            except Exception as cost_e:
                logger.warning(f"[gpt_e] Cost calc failed: {cost_e}")
            
            # שלב 4: עיבוד תוצאות
            if not content or not content.strip():
                return {"success": False, "error": "Empty response from GPT"}
            
            # פרסינג JSON
            try:
                if content.strip().startswith("{") and content.strip().endswith("}"):
                    changes = json.loads(content.strip())
                else:
                    changes = {}
            except json.JSONDecodeError as e:
                logger.error(f"[gpt_e] JSON decode error: {e}")
                changes = {}
            
            # שלב 5: עדכון פרופיל
            if changes and isinstance(changes, dict):
                try:
                    from db_wrapper import update_user_summary_wrapper as update_user_summary_fast
                    new_profile = changes.get("updated_profile", "")
                    if new_profile and new_profile.strip():
                        update_user_summary_fast(safe_chat_id, new_profile)
                except Exception as update_e:
                    logger.error(f"[gpt_e] Failed to update profile: {update_e}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": True,
                "changes": changes,
                "usage": usage,
                "model": response.model,
                "execution_time": execution_time,
                "timestamp": start_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"[gpt_e] Error: {e}")
            return {"success": False, "error": str(e)}
    
    async def execute_gpt_e_if_needed(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """מריץ GPT-E אם צריך"""
        safe_chat_id = safe_str(chat_id)
        
        try:
            from chat_utils import get_user_stats_and_history
            stats, _ = get_user_stats_and_history(safe_chat_id)
            total_messages = stats.get("total_messages", 0)
            
            if self.should_run_gpt_e(safe_chat_id, total_messages):
                result = await self.run_gpt_e(safe_chat_id)
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"[gpt_e] Error in execute_gpt_e_if_needed: {e}")
            return None

# =================================
# 🛡️ מערכת הגנת חיוב
# =================================

class BillingProtection:
    """מערכת הגנה מפני חיובים מופרזים"""
    
    def __init__(self, daily_limit_usd: float = 5.0, monthly_limit_usd: float = 50.0):
        self.daily_limit_usd = daily_limit_usd
        self.monthly_limit_usd = monthly_limit_usd
        self.usage_data = self._load_usage()
    
    def _load_usage(self) -> Dict:
        """טען נתוני שימוש"""
        return {
            "daily": {},
            "monthly": {},
            "alerts_sent": {}
        }
    
    def _get_current_keys(self) -> tuple:
        """מחזיר מפתחות תאריך נוכחיים"""
        from utils import get_israel_time
        now = get_israel_time()
        daily_key = now.strftime("%Y-%m-%d")
        monthly_key = now.strftime("%Y-%m")
        return daily_key, monthly_key
    
    def add_cost(self, cost_usd: float, model_name: str, tier_type: str = "unknown") -> Dict:
        """מוסיף עלות לספירה ובודק מגבלות"""
        daily_key, monthly_key = self._get_current_keys()
        
        # עדכון שימוש
        if daily_key not in self.usage_data["daily"]:
            self.usage_data["daily"][daily_key] = 0.0
        if monthly_key not in self.usage_data["monthly"]:
            self.usage_data["monthly"][monthly_key] = 0.0
        
        self.usage_data["daily"][daily_key] += cost_usd
        self.usage_data["monthly"][monthly_key] += cost_usd
        
        # בדיקת מגבלות
        daily_usage = self.usage_data["daily"][daily_key]
        monthly_usage = self.usage_data["monthly"][monthly_key]
        
        status = {
            "daily_usage": daily_usage,
            "daily_limit": self.daily_limit_usd,
            "daily_percent": (daily_usage / self.daily_limit_usd) * 100,
            "monthly_usage": monthly_usage,
            "monthly_limit": self.monthly_limit_usd,
            "monthly_percent": (monthly_usage / self.monthly_limit_usd) * 100,
            "cost_added": cost_usd,
            "model": model_name,
            "tier": tier_type,
            "warnings": []
        }
        
        # הוספת אזהרות
        if daily_usage >= self.daily_limit_usd:
            status["warnings"].append("🚨 עברת את המגבלה היומית!")
        elif daily_usage >= self.daily_limit_usd * 0.8:
            status["warnings"].append("⚠️ השימוש היומי מעל 80%")
        
        if monthly_usage >= self.monthly_limit_usd:
            status["warnings"].append("🚨 עברת את המגבלה החודשית!")
        elif monthly_usage >= self.monthly_limit_usd * 0.8:
            status["warnings"].append("⚠️ השימוש החודשי מעל 80%")
        
        return status
    
    def get_current_status(self) -> Dict:
        """מחזיר סטטוס נוכחי"""
        daily_key, monthly_key = self._get_current_keys()
        
        daily_usage = self.usage_data["daily"].get(daily_key, 0.0)
        monthly_usage = self.usage_data["monthly"].get(monthly_key, 0.0)
        
        return {
            "daily_usage": daily_usage,
            "daily_limit": self.daily_limit_usd,
            "daily_remaining": max(0, self.daily_limit_usd - daily_usage),
            "monthly_usage": monthly_usage,
            "monthly_limit": self.monthly_limit_usd,
            "monthly_remaining": max(0, self.monthly_limit_usd - monthly_usage),
            "daily_percent": (daily_usage / self.daily_limit_usd) * 100,
            "monthly_percent": (monthly_usage / self.monthly_limit_usd) * 100
        }

# =================================
# 🧠 מנהל Gemini חכם
# =================================

class SmartGeminiManager:
    """מנהל חכם עבור Gemini - מתחיל עם חינמי, עובר לבתשלום"""
    
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.free_models = [
            "gemini/gemini-2.0-flash-exp",
            "gemini/gemini-1.5-pro",
            "gemini/gemini-1.5-flash"
        ]
        self.paid_models = [
            "gemini/gemini-2.5-pro"
        ]
        self.daily_free_used = False
        self.last_reset_day = time.strftime("%Y-%m-%d")
    
    def _reset_daily_counter(self):
        """מאפס את הספירה היומית"""
        current_day = time.strftime("%Y-%m-%d")
        if current_day != self.last_reset_day:
            self.daily_free_used = False
            self.last_reset_day = current_day
    
    def smart_completion(self, messages: list, **kwargs) -> tuple:
        """ביצוע חכם - מנסה חינמי קודם"""
        self._reset_daily_counter()
        
        # נסה מודלים חינמיים
        if not self.daily_free_used:
            for free_model in self.free_models:
                try:
                    completion_params = kwargs.copy()
                    completion_params["model"] = free_model
                    
                    with measure_llm_latency(free_model):
                        response = litellm.completion(
                            messages=messages,
                            api_key=self.api_key,
                            **completion_params
                        )
                    
                    return response, "free", free_model
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    if "quota" in error_msg or "rate limit" in error_msg:
                        continue
                    else:
                        continue
            
            self.daily_free_used = True
        
        # נסה מודלים בתשלום
        for paid_model in self.paid_models:
            try:
                completion_params = kwargs.copy()
                completion_params["model"] = paid_model
                
                with measure_llm_latency(paid_model):
                    response = litellm.completion(
                        messages=messages,
                        api_key=self.api_key,
                        **completion_params
                    )
                
                return response, "paid", paid_model
                
            except Exception as e:
                continue
        
        raise Exception("❌ כל המודלים נכשלו!")
    
    def get_status(self) -> Dict:
        """מחזיר סטטוס נוכחי"""
        self._reset_daily_counter()
        return {
            "free_available": not self.daily_free_used,
            "last_reset": self.last_reset_day,
            "preferred_model": self.free_models[0] if not self.daily_free_used else self.paid_models[0]
        }

# =================================
# 🎯 מנהל GPT מרכזי
# =================================

class GPTManager:
    """מנהל מרכזי לכל הטיפול ב-GPT"""
    
    def __init__(self):
        self.gpt_a = GPTAHandler()
        self.gpt_b = GPTBHandler()
        self.gpt_c = GPTCHandler()
        self.gpt_d = GPTDHandler()
        self.gpt_e = GPTEHandler()
        self.billing_guard = BillingProtection()
        self.smart_gemini = SmartGeminiManager()
    
    def get_filter_analytics(self) -> Dict:
        """מחזיר ניתוח של החלטות הפילטר"""
        global filter_decisions_log
        total = sum(filter_decisions_log.values())
        
        if total == 0:
            return {"message": "עדיין לא נרשמו החלטות פילטר"}
        
        percentages = {k: round((v/total)*100, 1) for k, v in filter_decisions_log.items()}
        
        return {
            "total_decisions": total,
            "breakdown": filter_decisions_log.copy(),
            "percentages": percentages,
            "premium_usage": round(((total - filter_decisions_log["default"])/total)*100, 1) if total > 0 else 0
        }
    
    def get_profile_question_stats(self) -> Dict:
        """מחזיר סטטיסטיקות של מוני השאלות"""
        return {
            "total_users": len(profile_question_counters),
            "counters": profile_question_counters.copy(),
            "cooldowns": profile_question_cooldowns.copy()
        }
    
    def process_message_with_all_gpts(self, user_message: str, chat_id: str, full_messages: list,
                                    message_id: str = None, chat_history_length: int = 0) -> Dict[str, Any]:
        """עיבוד הודעה עם כל ה-GPTs הרלוונטיים"""
        results = {}
        
        try:
            # GPT-A - תשובה ראשית
            use_premium, reason, match_type = self.gpt_a.should_use_premium_model(user_message, chat_history_length)
            gpt_a_result = self.gpt_a.get_main_response_sync(
                full_messages, chat_id, message_id, use_premium, reason, match_type
            )
            results["gpt_a"] = gpt_a_result
            
            # GPT-B - סיכום (אם נדרש)
            if gpt_a_result.get("bot_reply"):
                gpt_b_result = self.gpt_b.get_summary(
                    user_message, gpt_a_result["bot_reply"], chat_id, message_id
                )
                results["gpt_b"] = gpt_b_result
            
            # GPT-C - חילוץ מידע (אם רלוונטי)
            if self.gpt_c.should_run_gpt_c(user_message):
                gpt_c_result = self.gpt_c.extract_user_info(user_message, chat_id, message_id)
                results["gpt_c"] = gpt_c_result
                
                # GPT-D - מיזוג פרופיל (אם נדרש)
                if gpt_c_result.get("extracted_fields"):
                    self.gpt_d.smart_update_profile_async(chat_id, user_message, message_id, gpt_c_result)
                    results["gpt_d"] = {"status": "running_async"}
            
            return results
            
        except Exception as e:
            logger.error(f"[GPT_MANAGER] Error processing message: {e}")
            return {"error": str(e)}

# =================================
# 🚀 יצירת instance גלובלי
# =================================

# יצירת מנהל GPT גלובלי
gpt_manager = GPTManager()

# פונקציות נוחות לגישה מהירה
def get_main_response_sync(full_messages: list, chat_id: str, message_id: str = None, 
                          use_extra_emotion: bool = True, filter_reason: str = "", 
                          match_type: str = "unknown") -> Dict[str, Any]:
    """פונקציה נוחה ל-GPT-A"""
    return gpt_manager.gpt_a.get_main_response_sync(
        full_messages, chat_id, message_id, use_extra_emotion, filter_reason, match_type
    )

def get_summary(user_msg: str, bot_reply: str, chat_id: str, message_id: str = None) -> Dict[str, Any]:
    """פונקציה נוחה ל-GPT-B"""
    return gpt_manager.gpt_b.get_summary(user_msg, bot_reply, chat_id, message_id)

def extract_user_info(user_msg: str, chat_id: str, message_id: str = None) -> Dict[str, Any]:
    """פונקציה נוחה ל-GPT-C"""
    return gpt_manager.gpt_c.extract_user_info(user_msg, chat_id, message_id)

def should_use_extra_emotion_model(user_message: str, chat_history_length: int = 0) -> tuple:
    """פונקציה נוחה לבדיקת מודל מתקדם"""
    return gpt_manager.gpt_a.should_use_premium_model(user_message, chat_history_length)

def should_run_gpt_c(user_message: str) -> bool:
    """פונקציה נוחה לבדיקת GPT-C"""
    return gpt_manager.gpt_c.should_run_gpt_c(user_message)

async def execute_gpt_e_if_needed(chat_id: str) -> Optional[Dict[str, Any]]:
    """פונקציה נוחה ל-GPT-E"""
    return await gpt_manager.gpt_e.execute_gpt_e_if_needed(chat_id)

def get_filter_analytics() -> Dict:
    """פונקציה נוחה לאנליטיקה"""
    return gpt_manager.get_filter_analytics()

def get_profile_question_stats() -> Dict:
    """פונקציה נוחה לסטטיסטיקות"""
    return gpt_manager.get_profile_question_stats()

# =================================
# 🎯 נקודת כניסה עיקרית
# =================================

if __name__ == "__main__":
    print("🤖 gpt_handlers.py - מאחד כל הטיפול ב-GPT")
    print("=" * 60)
    
    # בדיקת התחברות
    try:
        print("✅ GPT Manager מוכן")
        print(f"📊 סטטוס Gemini: {gpt_manager.smart_gemini.get_status()}")
        print(f"💰 סטטוס חיוב: {gpt_manager.billing_guard.get_current_status()}")
        
        # אנליטיקה
        analytics = get_filter_analytics()
        if "total_decisions" in analytics:
            print(f"📈 החלטות פילטר: {analytics['total_decisions']}")
        
        profile_stats = get_profile_question_stats()
        print(f"👥 משתמשים עם מוני שאלות: {profile_stats['total_users']}")
        
    except Exception as e:
        print(f"❌ שגיאה באתחול: {e}")
    
    print("\n🚀 gpt_handlers.py מוכן לשימוש!") 