#!/usr/bin/env python3
"""
simple_logger.py - מערכת לוגים אחידה ופשוטה
כל הלוגים במערכת עוברים דרך כאן - אחיד, ברור, ונגיש
"""

import logging
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
from db_manager import safe_str

class SimpleLogger:
    """מערכת לוגים אחידה - כל הלוגים במערכת עוברים דרך כאן"""
    
    def __init__(self):
        self.logger = logging.getLogger('telegram_bot')
        self.logger.setLevel(logging.INFO)
        
        # יצירת handler אם לא קיים
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _format_message(self, message: str, source: str = "", **kwargs) -> str:
        """עיצוב הודעה אחיד - ברור ונגיש"""
        formatted = f"[{source}] {message}" if source else message
        
        if kwargs:
            # הוספת פרטים נוספים בצורה ברורה
            details = []
            for key, value in kwargs.items():
                if key == 'chat_id':
                    # טיפול בטוח ב-chat_id
                    safe_id = safe_str(value)
                    details.append(f"user={safe_id}")
                else:
                    details.append(f"{key}={value}")
            
            if details:
                formatted += f" | {' | '.join(details)}"
        
        return formatted
    
    def info(self, message: str, source: str = "", **kwargs):
        """לוג מידע - ברור ונגיש"""
        formatted_msg = self._format_message(message, source, **kwargs)
        self.logger.info(formatted_msg)
    
    def error(self, message: str, source: str = "", **kwargs):
        """לוג שגיאה - ברור ונגיש"""
        formatted_msg = self._format_message(message, source, **kwargs)
        self.logger.error(formatted_msg)
    
    def warning(self, message: str, source: str = "", **kwargs):
        """לוג אזהרה - ברור ונגיש"""
        formatted_msg = self._format_message(message, source, **kwargs)
        self.logger.warning(formatted_msg)
    
    def debug(self, message: str, source: str = "", **kwargs):
        """לוג דיבאג - ברור ונגיש"""
        formatted_msg = self._format_message(message, source, **kwargs)
        self.logger.debug(formatted_msg)
    
    def log_user_action(self, action: str, chat_id: Any, details: Dict = None):
        """לוג פעולת משתמש - ברור ונגיש למשתמש הלא-טכני"""
        safe_id = safe_str(chat_id)
        message = f"משתמש {safe_id}: {action}"
        
        if details:
            # הוספת פרטים בצורה קריאה
            detail_str = ", ".join([f"{k}={v}" for k, v in details.items()])
            message += f" ({detail_str})"
        
        self.info(message, source="user_action")
    
    def log_system_event(self, event: str, details: Dict = None):
        """לוג אירוע מערכת - ברור ונגיש למשתמש הלא-טכני"""
        message = f"אירוע מערכת: {event}"
        
        if details:
            detail_str = ", ".join([f"{k}={v}" for k, v in details.items()])
            message += f" ({detail_str})"
        
        self.info(message, source="system")
    
    def log_error_with_context(self, error: Exception, context: str = "", user_id: str = ""):
        """לוג שגיאה עם הקשר - ברור ונגיש למשתמש הלא-טכני"""
        error_type = type(error).__name__
        error_msg = str(error)
        
        message = f"שגיאה: {error_type} - {error_msg}"
        
        if context:
            message += f" (הקשר: {context})"
        
        if user_id:
            safe_id = safe_str(user_id)
            message += f" (משתמש: {safe_id})"
        
        self.error(message, source="error_handler")

# יצירת מופע גלובלי - המקום היחיד ללוגים במערכת
logger = SimpleLogger() 