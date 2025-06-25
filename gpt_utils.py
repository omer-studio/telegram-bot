import logging
import litellm
import time
from config import GEMINI_API_KEY

USD_TO_ILS = 3.7  # שער הדולר-שקל (יש לעדכן לפי הצורך)

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
            print(f"🔄 יום חדש! מאפס מגבלות חינמיות ({current_day})")
    
    def smart_completion(self, messages, **kwargs):
        """
        🧠 ביצוע חכם - מנסה חינמי קודם, עובר לבתשלום אם צריך
        """
        self._reset_daily_counter()
        
        # 🆓 תחילה - נסה מודלים חינמיים
        if not self.daily_free_used:
            for free_model in self.free_models:
                try:
                    print(f"🆓 מנסה מודל חינמי: {free_model}")
                    response = litellm.completion(
                        model=free_model,
                        messages=messages,
                        api_key=self.api_key,
                        **kwargs
                    )
                    print(f"✅ הצלחה עם מודל חינמי: {free_model}")
                    return response, "free", free_model
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    if "quota" in error_msg or "rate limit" in error_msg:
                        print(f"🚫 מגבלה חינמית הגיעה ב-{free_model}")
                        continue  # נסה מודל חינמי הבא
                    
                    elif "expired" in error_msg:
                        print(f"❌ בעיה עם API Key ב-{free_model}")
                        continue
                    
                    else:
                        print(f"⚠️ שגיאה אחרת ב-{free_model}: {e}")
                        continue
            
            # אם הגענו לכאן - כל המודלים החינמיים נגמרו
            print("🔄 כל המודלים החינמיים מוגבלים - עובר לבתשלום")
            self.daily_free_used = True
        
        # 💰 עכשיו - נסה מודלים בתשלום (ללא חסימות!)
        print("💰 עובר למודלים בתשלום - שירות רציף!")
        for paid_model in self.paid_models:
            try:
                print(f"💰 מנסה מודל בתשלום: {paid_model}")
                response = litellm.completion(
                    model=paid_model,
                    messages=messages,
                    api_key=self.api_key,
                    **kwargs
                )
                print(f"✅ הצלחה עם מודל בתשלום: {paid_model}")
                return response, "paid", paid_model
                
            except Exception as e:
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
    print(f"[DEBUG] 🔥 calculate_gpt_cost CALLED! 🔥")
    print(f"[DEBUG] Input: prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}, cached_tokens={cached_tokens}, model_name={model_name}")
    print(f"[DEBUG] calculate_gpt_cost - Model: {model_name}, Tokens: {prompt_tokens}p + {completion_tokens}c + {cached_tokens}cache")
    try:
        import litellm
        if completion_response:
            print(f"[DEBUG] Using completion_response for cost calculation")
            cost_usd = litellm.completion_cost(completion_response=completion_response)
            print(f"[DEBUG] LiteLLM completion_cost returned: {cost_usd}")
        else:
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
        print(f"[DEBUG] calculate_gpt_cost returning: {result}")
        return result
    except Exception as e:
        print(f"[ERROR] calculate_gpt_cost failed: {e}")
        import traceback
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
            print(f"⚠️ שגיאה בשמירת נתוני שימוש: {e}")
    
    def _get_current_keys(self):
        """מחזיר מפתחות תאריך נוכחיים"""
        from datetime import datetime
        now = datetime.now()
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