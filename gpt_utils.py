import logging
import litellm
import time
import os
import json
import traceback
from contextlib import contextmanager
from datetime import datetime
from config import GEMINI_API_KEY, DATA_DIR, config, should_log_gpt_cost_debug, should_log_debug_prints, GPT_MODELS

USD_TO_ILS = 3.7  # שער הדולר-שקל (יש לעדכן לפי הצורך)

@contextmanager
def measure_llm_latency(model_name):
    """Context manager למדידת זמן תגובה של מודל LLM"""
    start_time = time.time()
    try:
        yield
    finally:
        latency = time.time() - start_time
        # רזה: רק DEBUG ללוג כללי + רישום לקובץ אם latency גבוה
        logging.debug(f"[{model_name}] latency: {latency:.2f}s")
        if latency > 10:  # רק אם איטי מאוד
            # TODO: Implement performance metric logging if needed
            pass

# 🧠 מערכת fallback חכמה - חינמי → בתשלום
class SmartGeminiManager:
    """
    🎯 מנהל חכם עבור Gemini - מתחיל עם חינמי, עובר לבתשלום כשצריך
    """
    
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        
        # 🆓 מודלים חינמיים (קודם)
        self.free_models = [
            "gemini/gemini-2.0-flash-exp",  # המהיר ביותר
            "gemini/gemini-1.5-pro",        # איכותי
            "gemini/gemini-1.5-flash"       # גיבוי
        ]
        
        # 💰 מודלים בתשלום (fallback)
        self.paid_models = [
            "gemini/gemini-2.5-pro"         # הטוב ביותר (בתשלום)
        ]
        
        self.daily_free_used = False  # האם המגבלה החינמית נגמרה היום
        self.last_reset_day = time.strftime("%Y-%m-%d")
    
    def _reset_daily_counter(self):
        """מאפס את הספירה היומית"""
        current_day = time.strftime("%Y-%m-%d")
        if current_day != self.last_reset_day:
            self.daily_free_used = False
            self.last_reset_day = current_day
            if should_log_debug_prints():
                print(f"🔄 יום חדש! מאפס מגבלות חינמיות ({current_day})")
    
    def smart_completion(self, messages, **kwargs):
        """
        🧠 ביצוע חכם - מנסה חינמי קודם, עובר לבתשלום אם צריך
        """
        self._reset_daily_counter()
        
        # 🆓 תחילה - נסה מודלים חינמיים
        if not self.daily_free_used:
            for free_model in self.free_models:
                if config.get("FREE_MODEL_DAILY_LIMIT", 100) <= config.get(f"{free_model}_usage", 0):
                    continue
                    
                try:
                    if should_log_debug_prints():
                        print(f"🆓 מנסה מודל חינמי: {free_model}")
                    
                    completion_params_copy = kwargs.copy()
                    completion_params_copy["model"] = free_model
                    
                    with measure_llm_latency(free_model):
                        response = litellm.completion(
                            messages=messages,
                            api_key=self.api_key,
                            **completion_params_copy
                        )
                    
                    # עדכון מונה השימוש
                    config[f"{free_model}_usage"] = config.get(f"{free_model}_usage", 0) + 1
                    with open(os.path.join(DATA_DIR, "free_model_limits.json"), 'w') as f:
                        json.dump(config, f)
                    
                    if should_log_debug_prints():
                        print(f"✅ הצלחה עם מודל חינמי: {free_model}")
                    return response, "free", free_model
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    if "quota" in error_msg or "rate limit" in error_msg:
                        if should_log_debug_prints():
                            print(f"🚫 מגבלה חינמית הגיעה ב-{free_model}")
                        config[f"{free_model}_usage"] = config.get("FREE_MODEL_DAILY_LIMIT", 100)
                        with open(os.path.join(DATA_DIR, "free_model_limits.json"), 'w') as f:
                            json.dump(config, f)
                        continue  # נסה מודל חינמי הבא
                    
                    elif "expired" in error_msg:
                        if should_log_debug_prints():
                            print(f"❌ בעיה עם API Key ב-{free_model}")
                        continue
                    
                    else:
                        if should_log_debug_prints():
                            print(f"⚠️ שגיאה אחרת ב-{free_model}: {e}")
                        continue
            
            # אם הגענו לכאן - כל המודלים החינמיים נגמרו
            if should_log_debug_prints():
                print("🔄 כל המודלים החינמיים מוגבלים - עובר לבתשלום")
            self.daily_free_used = True
        
        # 💰 עכשיו - נסה מודלים בתשלום (ללא חסימות!)
        if should_log_debug_prints():
            print("💰 עובר למודלים בתשלום - שירות רציף!")
        for paid_model in self.paid_models:
            try:
                if should_log_debug_prints():
                    print(f"💰 מנסה מודל בתשלום: {paid_model}")
                
                completion_params_copy = kwargs.copy()
                completion_params_copy["model"] = paid_model
                
                with measure_llm_latency(paid_model):
                    response = litellm.completion(
                        messages=messages,
                        api_key=self.api_key,
                        **completion_params_copy
                    )
                
                if should_log_debug_prints():
                    print(f"✅ הצלחה עם מודל בתשלום: {paid_model}")
                return response, "paid", paid_model
                
            except Exception as e:
                if should_log_debug_prints():
                    print(f"❌ שגיאה במודל בתשלום {paid_model}: {e}")
                continue
        
        # אם הגענו לכאן - כל המודלים נכשלו
        raise Exception("❌ כל המודלים (חינמיים ובתשלום) נכשלו!")
    
    def get_status(self):
        """מחזיר סטטוס נוכחי"""
        self._reset_daily_counter()
        return {
            "free_available": not self.daily_free_used,
            "last_reset": self.last_reset_day,
            "preferred_model": self.free_models[0] if not self.daily_free_used else self.paid_models[0]
        }

# יצירת instance גלובלי
smart_manager = SmartGeminiManager()

def safe_get_usage_value(obj, attr_name, default=0):
    """
    מחלץ ערך מusage object באופן בטוח, כולל תמיכה בwrappers של OpenAI API החדש
    """
    try:
        if hasattr(obj, attr_name):
            value = getattr(obj, attr_name)
            # אם זה wrapper object, ננסה להמיר אותו למספר
            if hasattr(value, '__dict__'):
                return default
            return int(value) if value is not None else default
        return default
    except (ValueError, TypeError, AttributeError):
        return default

def calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens=0, model_name=None, usd_to_ils=USD_TO_ILS, completion_response=None):
    if model_name is None:
        from config import GPT_MODELS
        model_name = GPT_MODELS["gpt_a"]
    """
    מחשב את העלות של שימוש ב-gpt לפי מספר הטוקנים והמודל.
    משתמש אך ורק ב-LiteLLM עם completion_response.
    מחזיר רק את העלות הכוללת (cost_total) כפי שמחושב ע"י LiteLLM, בלי פילוח ידני.
    """
    if should_log_gpt_cost_debug():
        print(f"[DEBUG] 🔥 calculate_gpt_cost CALLED! 🔥")
        print(f"[DEBUG] Input: prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}, cached_tokens={cached_tokens}, model_name={model_name}")
        print(f"[DEBUG] calculate_gpt_cost - Model: {model_name}, Tokens: {prompt_tokens}p + {completion_tokens}c + {cached_tokens}cache")
    try:
        if completion_response:
            if should_log_gpt_cost_debug():
                print(f"[DEBUG] Using completion_response for cost calculation")
            cost_usd = litellm.completion_cost(completion_response=completion_response)
            if should_log_gpt_cost_debug():
                print(f"[DEBUG] LiteLLM completion_cost returned: {cost_usd}")
        else:
            if should_log_gpt_cost_debug():
                print(f"[DEBUG] No completion_response provided, cannot calculate cost with LiteLLM")
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
        if should_log_debug_prints():
            print(f"[ERROR] Full traceback: {traceback.format_exc()}")
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

def normalize_usage_dict(usage, model_name=""):
    """
    מנרמל מילון usage של gpt לפורמט אחיד (לוגים/דוחות).
    מטפל בwrappers חדשים של OpenAI API.
    """
    if not usage:
        return {}
    
    # אם זה usage object של OpenAI, נמיר אותו בבטחה
    if hasattr(usage, '__dict__'):
        try:
            result = {
                "prompt_tokens": safe_get_usage_value(usage, 'prompt_tokens', 0),
                "completion_tokens": safe_get_usage_value(usage, 'completion_tokens', 0),
                "total_tokens": safe_get_usage_value(usage, 'total_tokens', 0),
            }
            
            # נחפש cached_tokens במקומות השונים שהם יכולים להיות
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
            # fallback לנירמול פשוט
            return {"model": model_name, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}
    
    # אם זה כבר dict, פשוט נוסיף את המודל
    if isinstance(usage, dict):
        result = dict(usage)
        result["model"] = model_name
        return result
    
    # fallback
    return {"model": model_name, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}

# ========================================
# 🛡️ מערכת הגנה על חיוב (מקור: billing_protection.py)
# ========================================

class BillingProtection:
    """
    🛡️ מערכת הגנה מפני חיובים מופרזים
    """
    
    def __init__(self, daily_limit_usd=5.0, monthly_limit_usd=50.0):
        self.daily_limit_usd = daily_limit_usd      # מגבלה יומית: $5
        self.monthly_limit_usd = monthly_limit_usd  # מגבלה חודשית: $50
        
        self.usage_file = "data/billing_usage.json"
        self._ensure_data_dir()
        self.usage_data = self._load_usage()
    
    def _ensure_data_dir(self):
        """וודא שתיקיית data קיימת"""
        import os
        os.makedirs("data", exist_ok=True)
    
    def _load_usage(self):
        """טען נתוני שימוש מקובץ"""
        import os
        import json
        if os.path.exists(self.usage_file):
            try:
                with open(self.usage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        # ברירת מחדל
        return {
            "daily": {},    # {"2025-01-20": 1.25}
            "monthly": {},  # {"2025-01": 15.30}
            "alerts_sent": {}
        }
    
    def _save_usage(self):
        """שמור נתוני שימוש לקובץ"""
        import json
        try:
            with open(self.usage_file, 'w', encoding='utf-8') as f:
                json.dump(self.usage_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            if should_log_debug_prints():
                print(f"⚠️ שגיאה בשמירת נתוני שימוש: {e}")
    
    def _get_current_keys(self):
        """מחזיר מפתחות תאריך נוכחיים"""
        from utils import get_israel_time
        now = get_israel_time()
        daily_key = now.strftime("%Y-%m-%d")
        monthly_key = now.strftime("%Y-%m")
        return daily_key, monthly_key
    
    def add_cost(self, cost_usd, model_name, tier_type="unknown"):
        """
        🔄 מוסיף עלות לספירה ובודק מגבלות
        
        Args:
            cost_usd: עלות בדולרים
            model_name: שם המודל
            tier_type: "free" או "paid"
        
        Returns:
            dict: מידע על סטטוס המגבלות
        """
        daily_key, monthly_key = self._get_current_keys()
        
        # עדכון שימוש יומי
        if daily_key not in self.usage_data["daily"]:
            self.usage_data["daily"][daily_key] = 0.0
        self.usage_data["daily"][daily_key] += cost_usd
        
        # עדכון שימוש חודשי
        if monthly_key not in self.usage_data["monthly"]:
            self.usage_data["monthly"][monthly_key] = 0.0
        self.usage_data["monthly"][monthly_key] += cost_usd
        
        # 🔧 תיקון זליגת זיכרון: הגבלת מספר רשומות ישנות
        # שמירה על מקסימום 60 ימים של נתונים יומיים
        if len(self.usage_data["daily"]) > 60:
            old_keys = sorted(self.usage_data["daily"].keys())[:-30]  # שמור רק 30 ימים אחרונים
            for old_key in old_keys:
                del self.usage_data["daily"][old_key]
        
        # שמירה על מקסימום 12 חודשים של נתונים חודשיים  
        if len(self.usage_data["monthly"]) > 12:
            old_keys = sorted(self.usage_data["monthly"].keys())[:-6]  # שמור רק 6 חודשים אחרונים
            for old_key in old_keys:
                del self.usage_data["monthly"][old_key]
        
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
        
        # שמירה
        self._save_usage()
        
        return status
    
    def get_current_status(self):
        """מחזיר סטטוס נוכחי ללא הוספת עלות"""
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
    
    def get_alert_level(self):
        """
        📊 מחזיר רמת התראה (לא חוסם, רק מתריע!)
        """
        status = self.get_current_status()
        
        # רמות התראה
        if (status["daily_usage"] >= self.daily_limit_usd or 
            status["monthly_usage"] >= self.monthly_limit_usd):
            return "critical", "🚨 עברת את המגבלה!"
        
        elif (status["daily_usage"] >= self.daily_limit_usd * 0.8 or 
              status["monthly_usage"] >= self.monthly_limit_usd * 0.8):
            return "warning", "⚠️ מתקרב למגבלה (80%+)"
        
        elif (status["daily_usage"] >= self.daily_limit_usd * 0.5 or 
              status["monthly_usage"] >= self.monthly_limit_usd * 0.5):
            return "info", "📊 שימוש בינוני (50%+)"
        
        return "ok", "✅ שימוש תקין"
    
    def print_status(self):
        """הדפס סטטוס נוכחי"""
        status = self.get_current_status()
        
        if should_log_debug_prints():
            print("💰 סטטוס תקציב:")
            print(f"📅 יומי: ${status['daily_usage']:.2f} / ${status['daily_limit']:.2f} ({status['daily_percent']:.1f}%)")
            print(f"📆 חודשי: ${status['monthly_usage']:.2f} / ${status['monthly_limit']:.2f} ({status['monthly_percent']:.1f}%)")
            
            if status['daily_percent'] > 80:
                print("⚠️ אזהרה: שימוש יומי גבוה!")
            if status['monthly_percent'] > 80:
                print("⚠️ אזהרה: שימוש חודשי גבוה!")

# יצירת instance גלובלי
billing_guard = BillingProtection(
    daily_limit_usd=5.0,    # $5 ליום
    monthly_limit_usd=50.0  # $50 לחודש
)

def _load_daily_limits():
    """טוען מגבלות יומיות ומאפס אם יום חדש."""
    from utils import get_israel_time
    today_str = get_israel_time().strftime("%Y-%m-%d")
    limits_file = os.path.join(DATA_DIR, "free_model_limits.json")
    
    try:
        with open(limits_file, 'r') as f:
            daily_limits = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        daily_limits = {}
    
    if daily_limits.get("date") != today_str:
        daily_limits = {"date": today_str}
        with open(limits_file, 'w') as f:
            json.dump(daily_limits, f)
        if should_log_debug_prints():
            print(f"🔄 יום חדש! מאפס מגבלות חינמיות ({today_str})")
    
    return daily_limits, limits_file

def _try_single_model(model, full_messages, completion_params, is_paid=False):
    """מנסה מודל יחיד ומחזיר תגובה או None אם נכשל."""
    try:
        if should_log_debug_prints():
            symbol = "💰" if is_paid else "🆓"
            print(f"{symbol} מנסה מודל: {model}")
        
        completion_params_copy = completion_params.copy()
        completion_params_copy["model"] = model
        
        with measure_llm_latency(model):
            response = litellm.completion(messages=full_messages, **completion_params_copy)
        
        if should_log_debug_prints():
            print(f"✅ הצלחה עם מודל: {model}")
        return response
        
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ שגיאה במודל {model}: {e}")
        return None, e

def try_free_models_first(full_messages, **completion_params):
    """מנסה קודם מודלים חינמיים, אחר כך עובר לבתשלום - גרסה רזה."""
    free_models = config.get("FREE_MODELS", [])
    paid_models = config.get("PAID_MODELS", [])
    daily_limits, limits_file = _load_daily_limits()
    
    # ניסיון עם מודלים חינמיים
    for free_model in free_models:
        if daily_limits.get(free_model, 0) >= config.get("FREE_MODEL_DAILY_LIMIT", 100):
            continue
            
        response, error = _try_single_model(free_model, full_messages, completion_params, is_paid=False)
        if response:
            # עדכון מונה השימוש
            daily_limits[free_model] = daily_limits.get(free_model, 0) + 1
            with open(limits_file, 'w') as f:
                json.dump(daily_limits, f)
            return response
        
        # טיפול בשגיאות מודל חינמי
        error_msg = str(error).lower()
        if "quota" in error_msg or "rate limit" in error_msg:
            daily_limits[free_model] = config.get("FREE_MODEL_DAILY_LIMIT", 100)
            with open(limits_file, 'w') as f:
                json.dump(daily_limits, f)
    
    # מעבר למודלים בתשלום
    if should_log_debug_prints():
        print("🔄 עובר למודלים בתשלום")
    logging.info("💰 עובר למודלים בתשלום - שירות רציף!")
    
    for paid_model in paid_models:
        response, _ = _try_single_model(paid_model, full_messages, completion_params, is_paid=True)
        if response:
            return response
    
    raise Exception("כל המודלים (חינמיים ובתשלום) נכשלו")

def normalize_usage_data(usage_data):
    """מנרמל נתוני usage למבנה אחיד"""
    try:
        if hasattr(usage_data, 'prompt_tokens'):
            return {
                "prompt_tokens": getattr(usage_data, 'prompt_tokens', 0),
                "completion_tokens": getattr(usage_data, 'completion_tokens', 0),
                "total_tokens": getattr(usage_data, 'total_tokens', 0),
                "prompt_tokens_details": getattr(usage_data, 'prompt_tokens_details', {}),
                "completion_tokens_details": getattr(usage_data, 'completion_tokens_details', {})
            }
        elif isinstance(usage_data, dict):
            return usage_data
        else:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    except Exception as e:
        if should_log_debug_prints():
            print(f"[DEBUG] שגיאה בנירמול usage: {e}")
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

def save_usage_data(usage_data, model_name, cost_agorot=None, chat_id=None, user_message=None, bot_response=None):
    """שומר נתוני שימוש לקובץ לוג מרכזי"""
    try:
        usage_log_path = os.path.join(DATA_DIR, "gpt_usage_log.jsonl")
        
        from utils import get_israel_time
        log_entry = {
            "timestamp": get_israel_time().isoformat(),
            "model": model_name,
            "usage": normalize_usage_data(usage_data),
            "cost_agorot": cost_agorot,
            "chat_id": str(chat_id) if chat_id else None,
            "user_message_length": len(user_message) if user_message else 0,
            "bot_response_length": len(bot_response) if bot_response else 0
        }
        
        with open(usage_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
    except Exception as e:
        if should_log_debug_prints():
            print(f"⚠️ שגיאה בשמירת נתוני שימוש: {e}")

def print_budget_status():
    """מדפיס סטטוס תקציב נוכחי - רק אם מופעל דיבאג"""
    if not should_log_gpt_cost_debug():
        return
        
    try:
        status = billing_guard.get_current_status()
        print("💰 סטטוס תקציב:")
        print(f"📅 יומי: ${status['daily_usage']:.2f} / ${status['daily_limit']:.2f} ({status['daily_percent']:.1f}%)")
        print(f"📆 חודשי: ${status['monthly_usage']:.2f} / ${status['monthly_limit']:.2f} ({status['monthly_percent']:.1f}%)")
        
        if status['daily_percent'] > 80:
            print("⚠️ אזהרה: שימוש יומי גבוה!")
        if status['monthly_percent'] > 80:
            print("⚠️ אזהרה: שימוש חודשי גבוה!")
    except Exception as e:
        logging.error(f"שגיאה בהדפסת סטטוס תקציב: {e}")

# יצירת instance גלובלי
smart_manager = SmartGeminiManager()
