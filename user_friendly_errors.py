#!/usr/bin/env python3
"""
user_friendly_errors.py - שגיאות ברורות למשתמש
"""

import traceback
import sys
from typing import Any, Optional, Dict
from datetime import datetime

class UserFriendlyError(Exception):
    """שגיאה ידידותית למשתמש - במקום traceback מפחיד"""
    
    def __init__(self, message: str, user_message: str = "", error_code: str = "", 
                 what_to_do: str = "", technical_details: str = ""):
        self.message = message
        self.user_message = user_message
        self.error_code = error_code
        self.what_to_do = what_to_do
        self.technical_details = technical_details
        
        # Import זמני כדי למנוע circular import
        try:
            from utils import get_israel_time
            self.timestamp = get_israel_time()
        except ImportError:
            self.timestamp = datetime.now()
        
        # הודעה ברורה למשתמש
        full_message = f"❌ {message}"
        if user_message:
            full_message += f"\n\nהודעה: {user_message}"
        if error_code:
            full_message += f"\n\nקוד שגיאה: {error_code}"
        if what_to_do:
            full_message += f"\n\nמה לעשות: {what_to_do}"
        
        super().__init__(full_message)

def safe_operation(operation_name: str, fallback_message: str = ""):
    """דקורטור לטיפול בטוח בפעולות - במקום crash"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # במקום crash - הודעה ידידותית
                error_msg = f"שגיאה ב-{operation_name}"
                user_msg = fallback_message or f"הפעולה '{operation_name}' נכשלה"
                
                print(f"🚨 {error_msg}")
                print(f"📝 {user_msg}")
                
                # Import זמני כדי למנוע circular import
                try:
                    from utils import get_israel_time
                    timestamp = get_israel_time()
                except ImportError:
                    timestamp = datetime.now()
                    
                print(f"⏰ זמן: {timestamp.strftime('%H:%M:%S')}")
                
                # לוג טכני למפתח (אם נדרש)
                if hasattr(sys, '_debug') and sys._debug:
                    print(f"🔧 פרטים טכניים: {str(e)}")
                
                return None  # במקום crash - החזרת None
        return wrapper
    return decorator

def handle_database_error(operation: str, chat_id: Any = None, user_msg: str = ""):
    """טיפול בשגיאות מסד נתונים - הודעה ידידותית למשתמש"""
    
    error_messages = {
        "connection": "לא ניתן להתחבר למסד הנתונים",
        "save": "לא ניתן לשמור הודעה",
        "load": "לא ניתן לטעון נתונים",
        "update": "לא ניתן לעדכן נתונים"
    }
    
    user_friendly_msg = error_messages.get(operation, f"שגיאה ב-{operation}")
    
    if chat_id:
        user_friendly_msg += f" עבור משתמש {chat_id}"
    
    if user_msg:
        user_friendly_msg += f" (הודעה: {user_msg[:50]}...)"
    
    print(f"💾 {user_friendly_msg}")
    
    # Import זמני כדי למנוע circular import
    try:
        from utils import get_israel_time
        timestamp = get_israel_time()
    except ImportError:
        timestamp = datetime.now()
        
    print(f"⏰ זמן: {timestamp.strftime('%H:%M:%S')}")
    print("🔄 המערכת תנסה שוב בעוד כמה שניות...")
    
    return False

def handle_type_error(value: Any, expected_type: str, context: str = ""):
    """טיפול בשגיאות טיפוסים - הודעה ידידותית למשתמש"""
    
    user_friendly_msg = f"ערך לא תקין: {value} (צפוי: {expected_type})"
    
    if context:
        user_friendly_msg += f" בהקשר: {context}"
    
    print(f"🔧 {user_friendly_msg}")
    
    # Import זמני כדי למנוע circular import
    try:
        from utils import get_israel_time
        timestamp = get_israel_time()
    except ImportError:
        timestamp = datetime.now()
        
    print(f"⏰ זמן: {timestamp.strftime('%H:%M:%S')}")
    print("🔄 המערכת תנסה לתקן אוטומטית...")
    
    return None

def log_user_friendly_error(error: Exception, context: str = "", user_id: str = ""):
    """לוג שגיאה ידידותי למשתמש - במקום traceback מפחיד"""
    
    error_type = type(error).__name__
    error_msg = str(error)
    
    print(f"🚨 שגיאה: {error_type}")
    print(f"📝 הודעה: {error_msg}")
    
    if context:
        print(f"📍 הקשר: {context}")
    
    if user_id:
        print(f"👤 משתמש: {user_id}")
    
    # Import זמני כדי למנוע circular import
    try:
        from utils import get_israel_time
        timestamp = get_israel_time()
    except ImportError:
        timestamp = datetime.now()
        
    print(f"⏰ זמן: {timestamp.strftime('%H:%M:%S')}")
    
    # הוראות פשוטות למשתמש
    print("💡 מה לעשות:")
    print("   1. נסה שוב בעוד דקה")
    print("   2. אם הבעיה נמשכת - פנה לתמיכה")
    print("   3. קוד שגיאה: " + str(hash(error_msg))[:8])

# פונקציות עזר לטיפול בטוח
def safe_int(value: Any, default: int = 0) -> int:
    """המרה בטוחה ל-int"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_str(value: Any, default: str = "") -> str:
    """המרה בטוחה ל-str"""
    try:
        return str(value) if value is not None else default
    except Exception:
        return default

def safe_chat_id(chat_id, require_valid=True):
    """
    🎯 פונקציה מאוחדת לטיפול ב-chat_id - מחליפה 3 פונקציות כפולות
    
    :param chat_id: הערך להמרה
    :param require_valid: אם True - זורק שגיאה עבור ערך לא תקין, אם False - מחזיר bool
    :return: safe_str(chat_id).strip() או bool (תלוי ב-require_valid)
    
    מחליף:
    - db_manager.normalize_chat_id() 
    - db_manager.validate_chat_id()
    - utils.is_valid_chat_id()
    """
    try:
        if chat_id is None:
            if require_valid:
                raise ValueError("chat_id cannot be None")
            return False
            
        safe_id = safe_str(chat_id).strip()
        
        # בדיקת תקינות - צריך להיות לא ריק אחרי strip
        is_valid = bool(safe_id)
        
        if require_valid:
            if not is_valid:
                raise ValueError(f"Invalid chat_id: {chat_id}")
            return safe_id
        else:
            return is_valid
            
    except Exception as e:
        if require_valid:
            raise ValueError(f"Error processing chat_id {chat_id}: {e}")
        return False

def safe_dict(value: Any, default: Dict = None) -> Dict:
    """המרה בטוחה ל-dict"""
    try:
        return dict(value) if value is not None else (default or {})
    except Exception:
        return default or {} 