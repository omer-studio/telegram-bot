#!/usr/bin/env python3
"""
simple_config.py - המקום היחיד שמכיל הגדרות
פשוט, עקבי, ותחזוקה קלה
"""

import os
import json
from typing import Any, Optional

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
            
            # הגדרות ברירת מחדל
            self._config.update({
                "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
                "OPENAI_ADMIN_KEY": os.getenv("OPENAI_ADMIN_KEY", ""),
                "DATABASE_URL": os.getenv("DATABASE_URL", ""),
                "DATABASE_EXTERNAL_URL": os.getenv("DATABASE_EXTERNAL_URL", ""),
                "ADMIN_BOT_TELEGRAM_TOKEN": os.getenv("ADMIN_BOT_TELEGRAM_TOKEN", ""),
                "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
                "RENDER_API_KEY": os.getenv("RENDER_API_KEY", ""),
                "RENDER_SERVICE_ID": os.getenv("RENDER_SERVICE_ID", ""),
            })
            
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