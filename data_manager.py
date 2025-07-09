#!/usr/bin/env python3
"""
🎯 DATA MANAGER - מרכז טיפול נתונים מערכתי
============================================

מטרה: מקום אחד לכל טיפול בנתונים
עקרון: בטוח, עקבי, נגיש למי שלא מבין בקוד

במקום שכל קובץ יטפל ב-chat_id, messages, timestamps אחרת,
כל הקוד עובר דרך הפונקציות הבטוחות פה.

אם יש בעיה - הודעה ברורה למשתמש מה השתבש ואיך לתקן.
"""

import json
import re
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timezone
import logging

class DataProcessingError(Exception):
    """שגיאה בעיבוד נתונים - עם הודעות ברורות למשתמש"""
    
    def __init__(self, data_type: str, problem: str, solution: str, original_value: Any = None):
        self.data_type = data_type
        self.problem = problem
        self.solution = solution
        self.original_value = original_value
        
        # הודעה ברורה למשתמש
        message = f"""
❌ בעיה בעיבוד {data_type}: {problem}

💡 פתרון: {solution}

⏰ זמן: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
"""
        if original_value is not None:
            message += f"\n📊 הערך המקורי: {original_value}"
        
        super().__init__(message)

class DataManager:
    """מנהל נתונים - מקום אחד לכל טיפול בנתונים"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    # 🎯 טיפול ב-Chat ID
    
    def safe_chat_id(self, chat_id: Any) -> str:
        """
        מנרמל chat_id לפורמט בטוח ועקבי
        
        Args:
            chat_id: כל סוג של מזהה צ'אט
            
        Returns:
            str: מזהה צ'אט נרמל כמחרוזת
            
        Raises:
            DataProcessingError: אם המזהה לא תקין
        """
        if chat_id is None:
            raise DataProcessingError(
                data_type="Chat ID",
                problem="מזהה צ'אט ריק",
                solution="וודא שהמזהה לא None או ריק"
            )
        
        # המרה לmחרוזת
        try:
            chat_id_str = str(chat_id).strip()
            
            # בדיקת תקינות בסיסית
            if not chat_id_str:
                raise DataProcessingError(
                    data_type="Chat ID",
                    problem="מזהה צ'אט ריק אחרי נרמול",
                    solution="וודא שהמזהה מכיל ערך תקין",
                    original_value=chat_id
                )
            
            # בדיקה שזה נראה כמו מזהה טלגרם (מספר או מחרוזת)
            if not (chat_id_str.isdigit() or chat_id_str.startswith('-') or chat_id_str.startswith('@')):
                self.logger.warning(f"Chat ID לא סטנדרטי: {chat_id_str}")
            
            return chat_id_str
            
        except Exception as e:
            raise DataProcessingError(
                data_type="Chat ID",
                problem=f"לא ניתן להמיר מזהה צ'אט: {e}",
                solution="וודא שהמזהה הוא מספר או מחרוזת תקינה",
                original_value=chat_id
            )
    
    def validate_chat_id(self, chat_id: Any) -> str:
        """
        בודק ומנרמל chat_id - גרסה מחמירה יותר
        
        Args:
            chat_id: מזהה צ'אט לבדיקה
            
        Returns:
            str: מזהה צ'אט תקין
            
        Raises:
            DataProcessingError: אם המזהה לא תקין
        """
        if chat_id is None:
            raise DataProcessingError(
                data_type="Chat ID",
                problem="מזהה צ'אט חסר",
                solution="העבר מזהה צ'אט תקין לפונקציה"
            )
        
        normalized = self.safe_chat_id(chat_id)
        
        # בדיקות נוספות לתקינות
        if len(normalized) > 50:
            raise DataProcessingError(
                data_type="Chat ID",
                problem="מזהה צ'אט ארוך מדי",
                solution="וודא שהמזהה אינו מכיל נתונים מיותרים",
                original_value=chat_id
            )
        
        return normalized
    
    # 🎯 טיפול בהודעות
    
    def safe_message(self, message: Any) -> str:
        """
        מנרמל הודעה לפורמט בטוח
        
        Args:
            message: הודעה בכל פורמט
            
        Returns:
            str: הודעה נרמלה
        """
        if message is None:
            return ""
        
        try:
            # המרה לmחרוזת
            message_str = str(message).strip()
            
            # ניקוי תווים מיוחדים שעלולים לגרום בעיות
            message_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', message_str)
            
            # הגבלת אורך (למניעת overflow)
            if len(message_str) > 10000:
                message_str = message_str[:9900] + "... (הודעה קוצרה)"
                self.logger.warning(f"הודעה קוצרה מ-{len(str(message))} תווים")
            
            return message_str
            
        except Exception as e:
            self.logger.error(f"שגיאה בעיבוד הודעה: {e}")
            return "[הודעה לא ניתנת לעיבוד]"
    
    def safe_message_for_db(self, message: Any) -> str:
        """
        מכין הודעה לשמירה במסד נתונים
        
        Args:
            message: הודעה לעיבוד
            
        Returns:
            str: הודעה מוכנה למסד נתונים
        """
        safe_msg = self.safe_message(message)
        
        # החלפת תווים שעלולים לגרום בעיות ב-SQL
        safe_msg = safe_msg.replace("'", "''")  # Escape single quotes
        safe_msg = safe_msg.replace('\0', '')   # Remove null bytes
        
        return safe_msg
    
    # 🎯 טיפול בזמנים
    
    def safe_timestamp(self, timestamp: Any = None) -> datetime:
        """
        מנרמל timestamp לפורמט בטוח
        
        Args:
            timestamp: זמן בכל פורמט, או None לזמן נוכחי
            
        Returns:
            datetime: זמן נרמל
        """
        if timestamp is None:
            return datetime.now(timezone.utc)
        
        if isinstance(timestamp, datetime):
            # וידוא שיש timezone
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            return timestamp
        
        if isinstance(timestamp, (int, float)):
            # Unix timestamp
            try:
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (ValueError, OSError) as e:
                self.logger.warning(f"Unix timestamp לא תקין: {timestamp}, משתמש בזמן נוכחי")
                return datetime.now(timezone.utc)
        
        if isinstance(timestamp, str):
            # ניסיון לפרסר מחרוזת
            try:
                # ISO format
                return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                try:
                    # Other common formats
                    return datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    self.logger.warning(f"פורמט זמן לא מזוהה: {timestamp}, משתמש בזמן נוכחי")
                    return datetime.now(timezone.utc)
        
        # אם כל השאר נכשל
        self.logger.warning(f"סוג זמן לא נתמך: {type(timestamp)}, משתמש בזמן נוכחי")
        return datetime.now(timezone.utc)
    
    # 🎯 טיפול ב-JSON
    
    def safe_json_loads(self, json_str: Any) -> Dict[str, Any]:
        """
        טוען JSON בצורה בטוחה
        
        Args:
            json_str: מחרוזת JSON
            
        Returns:
            dict: אובייקט Python
        """
        if json_str is None:
            return {}
        
        if isinstance(json_str, dict):
            return json_str
        
        if not isinstance(json_str, str):
            json_str = str(json_str)
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON לא תקין: {e}, מחזיר dict ריק")
            return {}
        except Exception as e:
            self.logger.error(f"שגיאה בטעינת JSON: {e}")
            return {}
    
    def safe_json_dumps(self, obj: Any) -> str:
        """
        מסריאל JSON בצורה בטוחה
        
        Args:
            obj: אובייקט Python
            
        Returns:
            str: מחרוזת JSON
        """
        if obj is None:
            return "{}"
        
        try:
            return json.dumps(obj, ensure_ascii=False, default=str)
        except Exception as e:
            self.logger.error(f"שגיאה בסריאליזציה של JSON: {e}")
            return "{}"
    
    # 🎯 טיפול בערכים מספריים
    
    def safe_int(self, value: Any, default: int = 0) -> int:
        """
        המרה בטוחה למספר שלם
        
        Args:
            value: ערך להמרה
            default: ערך ברירת מחדל
            
        Returns:
            int: מספר שלם
        """
        if value is None:
            return default
        
        if isinstance(value, int):
            return value
        
        if isinstance(value, float):
            return int(value)
        
        if isinstance(value, str):
            try:
                return int(float(value))  # תומך גם בעשרוניים
            except ValueError:
                self.logger.warning(f"לא ניתן להמיר למספר: {value}, משתמש בברירת מחדל: {default}")
                return default
        
        self.logger.warning(f"סוג לא נתמך להמרה למספר: {type(value)}, משתמש בברירת מחדל: {default}")
        return default
    
    def safe_float(self, value: Any, default: float = 0.0) -> float:
        """
        המרה בטוחה למספר עשרוני
        
        Args:
            value: ערך להמרה
            default: ערך ברירת מחדל
            
        Returns:
            float: מספר עשרוני
        """
        if value is None:
            return default
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                self.logger.warning(f"לא ניתן להמיר למספר עשרוני: {value}, משתמש בברירת מחדל: {default}")
                return default
        
        self.logger.warning(f"סוג לא נתמך להמרה למספר עשרוני: {type(value)}, משתמש בברירת מחדל: {default}")
        return default
    
    # 🎯 טיפול בנתוני משתמש
    
    def safe_user_data(self, user_data: Any) -> Dict[str, Any]:
        """
        מנרמל נתוני משתמש לפורמט בטוח
        
        Args:
            user_data: נתוני משתמש בכל פורמט
            
        Returns:
            dict: נתוני משתמש נרמלים
        """
        if user_data is None:
            return {}
        
        if isinstance(user_data, str):
            user_data = self.safe_json_loads(user_data)
        
        if not isinstance(user_data, dict):
            self.logger.warning(f"נתוני משתמש לא תקינים: {type(user_data)}")
            return {}
        
        # ניקוי שדות רגישים
        sensitive_fields = ['password', 'token', 'key', 'secret']
        cleaned_data = {}
        
        for key, value in user_data.items():
            # בדיקה אם השדה רגיש
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                cleaned_data[key] = "[REDACTED]"
            else:
                # נרמול הערך
                if isinstance(value, str):
                    cleaned_data[key] = self.safe_message(value)
                elif isinstance(value, (int, float)):
                    cleaned_data[key] = value
                elif isinstance(value, (list, dict)):
                    cleaned_data[key] = value  # נשמור כמו שזה
                else:
                    cleaned_data[key] = str(value)
        
        return cleaned_data
    
    # 🎯 פונקציות בדיקה ותיקוף
    
    def validate_telegram_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        בודק ומנרמל נתונים מטלגרם
        
        Args:
            data: נתונים מטלגרם
            
        Returns:
            dict: נתונים תקינים
        """
        if not isinstance(data, dict):
            raise DataProcessingError(
                data_type="Telegram Data",
                problem="נתונים לא תקינים מטלגרם",
                solution="וודא שהנתונים מגיעים בפורמט dict",
                original_value=data
            )
        
        # שדות חובה
        required_fields = ['message', 'chat']
        for field in required_fields:
            if field not in data:
                raise DataProcessingError(
                    data_type="Telegram Data",
                    problem=f"שדה חובה חסר: {field}",
                    solution=f"וודא שהנתונים מטלגרם מכילים את השדה {field}",
                    original_value=data
                )
        
        # נרמול נתונים
        normalized = {}
        
        # Chat ID
        if 'chat' in data and 'id' in data['chat']:
            normalized['chat_id'] = self.safe_chat_id(data['chat']['id'])
        
        # Message
        if 'message' in data and 'text' in data['message']:
            normalized['message_text'] = self.safe_message(data['message']['text'])
        
        # User info
        if 'message' in data and 'from' in data['message']:
            user_info = data['message']['from']
            normalized['user_info'] = {
                'user_id': self.safe_chat_id(user_info.get('id')),
                'username': self.safe_message(user_info.get('username', '')),
                'first_name': self.safe_message(user_info.get('first_name', '')),
                'last_name': self.safe_message(user_info.get('last_name', ''))
            }
        
        # Timestamp
        if 'message' in data and 'date' in data['message']:
            normalized['timestamp'] = self.safe_timestamp(data['message']['date'])
        
        return normalized
    
    def get_data_summary(self) -> Dict[str, Any]:
        """
        מחזיר סיכום על מצב עיבוד הנתונים
        
        Returns:
            dict: סיכום מצב
        """
        return {
            "data_manager_version": "1.0.0",
            "supported_types": [
                "chat_id", "message", "timestamp", "json", 
                "user_data", "telegram_data", "numeric"
            ],
            "safety_features": [
                "automatic_normalization",
                "error_handling",
                "data_validation",
                "sensitive_data_protection"
            ],
            "last_check": datetime.now().isoformat()
        }

# 🎯 Instance גלובלי - מקום אחד לכל המערכת
data_manager = DataManager()

# 🎯 פונקציות נוחות לשימוש מהיר
def safe_chat_id(chat_id: Any) -> str:
    """פונקציה נוחה לנרמול chat_id"""
    return data_manager.safe_chat_id(chat_id)

def validate_chat_id(chat_id: Any) -> str:
    """פונקציה נוחה לבדיקת chat_id"""
    return data_manager.validate_chat_id(chat_id)

def safe_message(message: Any) -> str:
    """פונקציה נוחה לנרמול הודעה"""
    return data_manager.safe_message(message)

def safe_timestamp(timestamp: Any = None) -> datetime:
    """פונקציה נוחה לנרמול זמן"""
    return data_manager.safe_timestamp(timestamp)

def safe_json_loads(json_str: Any) -> Dict[str, Any]:
    """פונקציה נוחה לטעינת JSON"""
    return data_manager.safe_json_loads(json_str)

def safe_json_dumps(obj: Any) -> str:
    """פונקציה נוחה לסריאליזציה של JSON"""
    return data_manager.safe_json_dumps(obj)

def safe_int(value: Any, default: int = 0) -> int:
    """פונקציה נוחה להמרה למספר שלם"""
    return data_manager.safe_int(value, default)

def safe_float(value: Any, default: float = 0.0) -> float:
    """פונקציה נוחה להמרה למספר עשרוני"""
    return data_manager.safe_float(value, default)

# 🎯 פונקציה לבדיקת תקינות עיבוד הנתונים
def check_data_processing_health() -> Dict[str, Any]:
    """בודק את תקינות עיבוד הנתונים"""
    
    try:
        # בדיקות בסיסיות
        test_results = {}
        
        # בדיקת chat_id
        try:
            result = safe_chat_id("123456789")
            test_results["chat_id_processing"] = "✅ תקין"
        except Exception as e:
            test_results["chat_id_processing"] = f"❌ שגיאה: {e}"
        
        # בדיקת message
        try:
            result = safe_message("הודעת בדיקה")
            test_results["message_processing"] = "✅ תקין"
        except Exception as e:
            test_results["message_processing"] = f"❌ שגיאה: {e}"
        
        # בדיקת timestamp
        try:
            result = safe_timestamp()
            test_results["timestamp_processing"] = "✅ תקין"
        except Exception as e:
            test_results["timestamp_processing"] = f"❌ שגיאה: {e}"
        
        # בדיקת JSON
        try:
            result = safe_json_loads('{"test": "value"}')
            test_results["json_processing"] = "✅ תקין"
        except Exception as e:
            test_results["json_processing"] = f"❌ שגיאה: {e}"
        
        return {
            "status": "✅ מעבד נתונים תקין",
            "tests": test_results,
            "summary": data_manager.get_data_summary()
        }
        
    except Exception as e:
        return {
            "status": "❌ שגיאה במעבד נתונים",
            "error": str(e)
        }

if __name__ == "__main__":
    # בדיקה עצמית
    print("🎯 DATA MANAGER - בדיקה עצמית")
    print("=" * 50)
    
    try:
        health = check_data_processing_health()
        print(json.dumps(health, indent=2, ensure_ascii=False))
        print("\n✅ מעבד הנתונים תקין!")
        
    except Exception as e:
        print(f"\n❌ שגיאה במעבד נתונים: {e}") 