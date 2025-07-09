#!/usr/bin/env python3
"""
🔧 Simple Config - קונפיגורציה פשוטה ומרכזית
מרכז את כל ההגדרות במקום אחד
"""

import os
import json
from typing import Any, Optional

class TimeoutConfig:
    """🎯 הגדרות timeout מרכזיות"""
    
    # Timeouts בסיסיים
    DEFAULT_TIMEOUT = 30
    QUICK_TIMEOUT = 10
    LONG_TIMEOUT = 60
    
    # Timeouts לפעולות ספציפיות
    DATABASE_TIMEOUT = 15
    API_TIMEOUT = 25
    WEBHOOK_TIMEOUT = 10
    
    @classmethod
    def get_timeout(cls, operation: str) -> int:
        """קבלת timeout לפעולה ספציפית"""
        timeouts = {
            'database': cls.DATABASE_TIMEOUT,
            'api': cls.API_TIMEOUT,
            'webhook': cls.WEBHOOK_TIMEOUT,
            'quick': cls.QUICK_TIMEOUT,
            'long': cls.LONG_TIMEOUT
        }
        return timeouts.get(operation, cls.DEFAULT_TIMEOUT)

class SimpleConfig:
    """🎯 מחלקת קונפיגורציה פשוטה"""
    
    def __init__(self):
        self._config = {}
        self._load_config()
    
    def _load_config(self):
        """טעינת קונפיגורציה"""
        try:
            # ניסיון טעינה מפונקציה מרכזית
            from config import get_config
            self._config = get_config()
            
        except Exception as e:
            print(f"WARNING - שגיאה בטעינת קונפיגורציה: {e}")
            # הגדרות ברירת מחדל בלבד
            self._config = {
                "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
                "DATABASE_URL": os.getenv("DATABASE_URL", ""),
            }
    
    def get(self, key: str, default: Any = None) -> Any:
        """קבלת הגדרה"""
        return self._config.get(key, default)
    
    def has(self, key: str) -> bool:
        """בדיקה אם קיים"""
        return key in self._config

# יצירת instance גלובלי לתאימות לאחור
config = SimpleConfig() 