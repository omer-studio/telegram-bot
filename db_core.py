#!/usr/bin/env python3
"""
🔧 מודול ליבה למסד נתונים עם טיפול בטוח ב-chat_id
כל הפונקציות שקשורות למסד נתונים צריכות לעבור דרך המודול הזה
"""

import psycopg2
import json
from typing import Union, Any, List, Tuple, Optional
from datetime import datetime


def ensure_chat_id_str(chat_id: Union[str, int]) -> str:
    """
    🔒 המרה בטוחה של chat_id ל-string לשימוש ב-SQL
    
    פונקציה זו מבטיחה שכל chat_id שנשלח למסד נתונים יהיה תמיד string,
    כדי להימנע משגיאות type mismatch.
    
    Args:
        chat_id: מזהה צ'אט (יכול להיות str או int)
        
    Returns:
        str: chat_id כ-string
        
    Example:
        >>> ensure_chat_id_str(111709341)
        '111709341'
        >>> ensure_chat_id_str('111709341')
        '111709341'
    """
    if chat_id is None:
        raise ValueError("chat_id cannot be None")
    
    # המרה ל-string ותיקוף שזה מספר חוקי
    chat_id_str = str(chat_id).strip()
    
    if not chat_id_str:
        raise ValueError("chat_id cannot be empty")
    
    # וידוא שזה נראה כמו chat_id תקין (רק ספרות)
    if not chat_id_str.lstrip('-').isdigit():
        raise ValueError(f"Invalid chat_id format: {chat_id_str}")
    
    return chat_id_str


def get_db_connection():
    """
    🔌 יצירת חיבור למסד נתונים
    
    Returns:
        psycopg2.connection: חיבור למסד נתונים
    """
    with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    db_url = config.get('DATABASE_EXTERNAL_URL') or config.get('DATABASE_URL')
    if not db_url:
        raise ValueError("No database URL found in config")
    
    return psycopg2.connect(db_url)


def safe_get_chat_history(chat_id: Union[str, int], limit: int = 100) -> List[Tuple[str, str, Any]]:
    """
    🔒 שליפת היסטוריית צ'אט בצורה בטוחה מבחינת טיפוסים
    
    Args:
        chat_id: מזהה צ'אט (int או str)
        limit: מספר ההודעות המקסימלי
        
    Returns:
        List[Tuple]: רשימת tuples של (user_msg, bot_msg, timestamp)
    """
    chat_id_safe = ensure_chat_id_str(chat_id)
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT user_msg, bot_msg, timestamp FROM chat_messages WHERE chat_id=%s ORDER BY timestamp DESC LIMIT %s",
                (chat_id_safe, limit)
            )
            rows = cursor.fetchall()
            return rows[::-1]  # מהישן לחדש


def safe_get_user_profile(chat_id: Union[str, int]) -> Optional[dict]:
    """
    🔒 שליפת פרופיל משתמש בצורה בטוחה מבחינת טיפוסים
    
    Args:
        chat_id: מזהה צ'אט (int או str)
        
    Returns:
        dict או None: פרופיל המשתמש או None אם לא נמצא
    """
    chat_id_safe = ensure_chat_id_str(chat_id)
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            from fields_dict import get_user_profile_fields
            
            # יצירת SQL עם כל השדות
            fields = ['chat_id'] + get_user_profile_fields()
            select_sql = f"SELECT {', '.join(fields)} FROM user_profiles WHERE chat_id=%s"
            
            cursor.execute(select_sql, (chat_id_safe,))
            row = cursor.fetchone()
            
            if row:
                # המרת השורה ל-dict
                profile_dict = {}
                for i, field in enumerate(fields):
                    profile_dict[field] = row[i]
                return profile_dict
            
            return None


def safe_get_user_message_count(chat_id: Union[str, int]) -> int:
    """
    🔒 שליפת מספר הודעות משתמש בצורה בטוחה מבחינת טיפוסים
    
    Args:
        chat_id: מזהה צ'אט (int או str)
        
    Returns:
        int: מספר ההודעות
    """
    chat_id_safe = ensure_chat_id_str(chat_id)
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT total_messages_count FROM user_profiles WHERE chat_id = %s", 
                (chat_id_safe,)
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0


def safe_save_chat_message(chat_id: Union[str, int], user_msg: str, bot_msg: str, 
                          timestamp: Optional[datetime] = None, **kwargs) -> bool:
    """
    🔒 שמירת הודעת צ'אט בצורה בטוחה מבחינת טיפוסים
    
    Args:
        chat_id: מזהה צ'אט (int או str)
        user_msg: הודעת המשתמש
        bot_msg: הודעת הבוט
        timestamp: זמן ההודעה (ברירת מחדל: עכשיו)
        **kwargs: פרמטרים נוספים
        
    Returns:
        bool: האם השמירה הצליחה
    """
    try:
        chat_id_safe = ensure_chat_id_str(chat_id)
        
        # יבוא הפונקציה המקורית עם הפרמטר הבטוח
        from db_manager import save_chat_message
        return save_chat_message(chat_id_safe, user_msg, bot_msg, timestamp, **kwargs)
        
    except Exception as e:
        print(f"❌ שגיאה בשמירת הודעה: {e}")
        return False


def safe_check_user_approved_status(chat_id: Union[str, int]) -> dict:
    """
    🔒 בדיקת סטטוס אישור משתמש בצורה בטוחה מבחינת טיפוסים
    
    Args:
        chat_id: מזהה צ'אט (int או str)
        
    Returns:
        dict: {"status": "approved"/"pending_approval"/"pending_code"/"not_found"}
    """
    try:
        chat_id_safe = ensure_chat_id_str(chat_id)
        
        from db_manager import check_user_approved_status_db
        return check_user_approved_status_db(chat_id_safe)
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת סטטוס: {e}")
        return {"status": "error"}


# 📋 רשימת כל הפונקציות הבטוחות שצריכות להחליף את הפונקציות הישנות
SAFE_FUNCTIONS = {
    'get_chat_history': safe_get_chat_history,
    'get_user_profile': safe_get_user_profile,
    'get_user_message_count': safe_get_user_message_count,
    'save_chat_message': safe_save_chat_message,
    'check_user_approved_status': safe_check_user_approved_status,
}


def test_safe_functions():
    """
    🧪 בדיקה מהירה של הפונקציות הבטוחות
    """
    print("🧪 בדיקת פונקציות בטוחות...")
    
    # בדיקת ensure_chat_id_str
    try:
        assert ensure_chat_id_str(111709341) == '111709341'
        assert ensure_chat_id_str('111709341') == '111709341'
        print("✅ ensure_chat_id_str עובד נכון")
    except Exception as e:
        print(f"❌ ensure_chat_id_str נכשל: {e}")
    
    # בדיקת חיבור למסד
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                assert result[0] == 1
        print("✅ חיבור למסד נתונים עובד")
    except Exception as e:
        print(f"❌ חיבור למסד נתונים נכשל: {e}")
    
    print("✅ כל הבדיקות עברו!")


if __name__ == "__main__":
    test_safe_functions() 