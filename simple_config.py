#!/usr/bin/env python3
"""
simple_config.py - המקום היחיד שמכיל הגדרות
פשוט, עקבי, ותחזוקה קלה
"""

import os
import json
from typing import Any, Optional

# מערכת timeout מתואמת - רכז כל הtimeouts במקום אחד
# =================================================================

# 🕐 Timeout Configuration - Central Management
# =================================================================
# מטרה: סנכרון כל השכבות, הודעות מתדרגות למשתמש, מניעת session timeouts

class TimeoutConfig:
    """מערכת timeout מתואמת לכל השכבות"""
    
    # 🎯 תזמון יסודי - מדורג לפי רמת חשיבות
    TELEGRAM_API_TIMEOUT_PROGRESSIVE = [1, 2, 3, 3, 4, 5]  # Progressive timeouts לשליחת הודעות
    TEMP_MESSAGE_DELAY = 3  # הודעת ביניים אחרי 3 שניות
    USER_WARNING_INTERVALS = [15, 30, 45]  # התראות למשתמש ב-15s, 30s, 45s
    
    # 🔧 GPT Processing Timeouts
    GPT_PROCESSING_TIMEOUT = 45  # GPT יכול לרוץ עד 45 שניות
    GPT_EMERGENCY_TIMEOUT = 48   # Emergency timeout לפני concurrent cleanup
    
    # 🛡️ Concurrent Monitor Timeouts
    CONCURRENT_SESSION_TIMEOUT = 50  # Session timeout (GPT + 5s buffer)
    CONCURRENT_CLEANUP_INTERVAL = 10  # בדיקת cleanup כל 10 שניות
    CONCURRENT_WARNING_THRESHOLD = 40  # התראה משתמש ב-40 שניות
    
    # 🚨 Emergency & Recovery
    EMERGENCY_RESPONSE_TIME = 52  # זמן מקסימלי לפני emergency response
    RECOVERY_TIMEOUT = 55  # זמן מקסימלי לפני recovery mechanism
    
    # 📡 Network & API Timeouts
    TELEGRAM_SEND_TIMEOUT = 5  # שליחת הודעות Telegram
    HTTP_REQUEST_TIMEOUT = 10  # HTTP requests כללי
    DATABASE_QUERY_TIMEOUT = 30  # שאילתות DB
    
    @classmethod
    def get_timeout_summary(cls):
        """מחזיר סיכום כל הtimeouts למעקב"""
        return {
            "gpt_processing": cls.GPT_PROCESSING_TIMEOUT,
            "gpt_emergency": cls.GPT_EMERGENCY_TIMEOUT,
            "concurrent_session": cls.CONCURRENT_SESSION_TIMEOUT,
            "concurrent_cleanup": cls.CONCURRENT_CLEANUP_INTERVAL,
            "user_warnings": cls.USER_WARNING_INTERVALS,
            "emergency_response": cls.EMERGENCY_RESPONSE_TIME,
            "recovery": cls.RECOVERY_TIMEOUT
        }
    
    @classmethod
    def validate_timeout_hierarchy(cls):
        """וידוא שהtimeouts מסודרים נכון"""
        errors = []
        
        # GPT timeout < Emergency timeout < Concurrent timeout
        if cls.GPT_PROCESSING_TIMEOUT >= cls.GPT_EMERGENCY_TIMEOUT:
            errors.append("GPT_PROCESSING_TIMEOUT חייב להיות קטן מ-GPT_EMERGENCY_TIMEOUT")
        
        if cls.GPT_EMERGENCY_TIMEOUT >= cls.CONCURRENT_SESSION_TIMEOUT:
            errors.append("GPT_EMERGENCY_TIMEOUT חייב להיות קטן מ-CONCURRENT_SESSION_TIMEOUT")
        
        # User warnings צריכים להיות לפני הtimeouts
        max_warning = max(cls.USER_WARNING_INTERVALS)
        if max_warning >= cls.CONCURRENT_SESSION_TIMEOUT:
            errors.append("USER_WARNING_INTERVALS חייבים להיות לפני CONCURRENT_SESSION_TIMEOUT")
        
        # Emergency response אחרי concurrent timeout
        if cls.EMERGENCY_RESPONSE_TIME <= cls.CONCURRENT_SESSION_TIMEOUT:
            errors.append("EMERGENCY_RESPONSE_TIME חייב להיות אחרי CONCURRENT_SESSION_TIMEOUT")
        
        return errors

# 🔧 Legacy compatibility - מספק את הערכים הישנים
GPT_TIMEOUT_SECONDS = TimeoutConfig.GPT_PROCESSING_TIMEOUT
MAX_ALLOWED_TIME = TimeoutConfig.CONCURRENT_SESSION_TIMEOUT

# 🧪 בדיקת תקינות התצורה
timeout_validation_errors = TimeoutConfig.validate_timeout_hierarchy()
if timeout_validation_errors:
    print("⚠️ שגיאות בתצורת Timeout:")
    for error in timeout_validation_errors:
        print(f"  - {error}")
    print("📝 יש לתקן את התצורה לפני המשך!")


class SimpleConfig:
    """המקום היחיד שמכיל הגדרות - פשוט ועקבי"""
    
    def __init__(self):
        self._config = {}
        self._load_config()
    
    def _load_config(self):
        """טעינת קונפיגורציה"""
        try:
            # ניסיון טעינה מקובץ
            config_paths = [
                "etc/secrets/config.json",
                "/etc/secrets/config.json",
                os.getenv("CONFIG_PATH", "")
            ]
            
            for path in config_paths:
                if path and os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        self._config = json.load(f)
                    break
            
            # הגדרות ברירת מחדל - רק אם לא קיימות בקובץ
            env_overrides = {
                "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
                "OPENAI_ADMIN_KEY": os.getenv("OPENAI_ADMIN_KEY"),
                "DATABASE_URL": os.getenv("DATABASE_URL"),
                "DATABASE_EXTERNAL_URL": os.getenv("DATABASE_EXTERNAL_URL"),
                "ADMIN_BOT_TELEGRAM_TOKEN": os.getenv("ADMIN_BOT_TELEGRAM_TOKEN"),
                "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
                "RENDER_API_KEY": os.getenv("RENDER_API_KEY"),
                "RENDER_SERVICE_ID": os.getenv("RENDER_SERVICE_ID"),
            }
            
            # רק משנה אם יש ערך בסביבה
            for key, env_value in env_overrides.items():
                if env_value:
                    self._config[key] = env_value
            
        except Exception as e:
            print(f"⚠️ שגיאה בטעינת קונפיגורציה: {e}")
            # הגדרות ברירת מחדל בלבד
            self._config = {
                "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
                "OPENAI_ADMIN_KEY": os.getenv("OPENAI_ADMIN_KEY", ""),
                "DATABASE_URL": os.getenv("DATABASE_URL", ""),
                "DATABASE_EXTERNAL_URL": os.getenv("DATABASE_EXTERNAL_URL", ""),
                "ADMIN_BOT_TELEGRAM_TOKEN": os.getenv("ADMIN_BOT_TELEGRAM_TOKEN", ""),
                "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
                "RENDER_API_KEY": os.getenv("RENDER_API_KEY", ""),
                "RENDER_SERVICE_ID": os.getenv("RENDER_SERVICE_ID", ""),
            }
    
    def get(self, key: str, default: Any = None) -> Any:
        """קבלת הגדרה - פונקציה אחת פשוטה"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """הגדרת ערך"""
        self._config[key] = value
    
    def has(self, key: str) -> bool:
        """בדיקה אם קיים"""
        return key in self._config
    
    def get_database_url(self) -> Optional[str]:
        """קבלת URL למסד נתונים"""
        return self._config.get("DATABASE_EXTERNAL_URL") or self._config.get("DATABASE_URL")
    
    def get_telegram_token(self) -> str:
        """קבלת טוקן טלגרם"""
        return self._config.get("TELEGRAM_BOT_TOKEN", "")
    
    def get_openai_key(self) -> str:
        """קבלת מפתח OpenAI"""
        return self._config.get("OPENAI_API_KEY", "")
    
    def get_admin_key(self) -> str:
        """קבלת מפתח אדמין"""
        return self._config.get("OPENAI_ADMIN_KEY", "")
    
    def get_gemini_key(self) -> str:
        """קבלת מפתח Gemini"""
        return self._config.get("GEMINI_API_KEY", "")
    
    def get_render_config(self) -> dict:
        """קבלת הגדרות Render"""
        return {
            "API_KEY": self._config.get("RENDER_API_KEY", ""),
            "SERVICE_ID": self._config.get("RENDER_SERVICE_ID", ""),
            "BASE_URL": "https://api.render.com/v1"
        }
    
    def validate_required_keys(self) -> list:
        """בדיקת מפתחות נדרשים"""
        required_keys = [
            "TELEGRAM_BOT_TOKEN",
            "OPENAI_API_KEY", 
            "DATABASE_URL"
        ]
        
        missing = []
        for key in required_keys:
            if not self.get(key):
                missing.append(key)
        
        return missing

# יצירת instance גלובלי - המקום היחיד שמכיל הגדרות
config = SimpleConfig() 