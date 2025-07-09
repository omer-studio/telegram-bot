#!/usr/bin/env python3
"""
🔄 Unified Profile Notifications - פתרון מערכתי לכפילויות
==========================================================

🎯 מטרה: להחליף את 4 הפונקציות הכפולות בפונקציה אחת חכמה ופשוטה

❌ הבעיה שנפתרת:
- send_admin_profile_change_notification
- send_admin_profile_notification  
- _send_admin_profile_overview_notification
- קריאות כפולות מ-message_handler

✅ הפתרון: פונקציה אחת שמטפלת בכל הסוגים
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from db_manager import safe_str
from simple_logger import logger

def send_profile_update_notification(
    chat_id: str,
    user_message: str,
    gpt_c_changes: Optional[List[Dict]] = None,
    gpt_d_changes: Optional[List[Dict]] = None,
    gpt_e_changes: Optional[List[Dict]] = None,
    gpt_e_counter: Optional[str] = None,
    summary: Optional[str] = None,
    table_name: str = "user_profiles"
) -> bool:
    """
    🎯 פונקציה אחת לכל התראות עדכון פרופיל - לפי המפרט המדויק של עומר
    
    Args:
        chat_id: ID המשתמש
        user_message: ההודעה המקורית של המשתמש במלואה (לא מצונזר!)
        gpt_c_changes: שינויים מ-GPT-C (List[Dict])
        gpt_d_changes: שינויים מ-GPT-D (List[Dict])  
        gpt_e_changes: שינויים מ-GPT-E (List[Dict])
        gpt_e_counter: מצב הקאונטר של GPT-E (למשל "5/12")
        summary: תוכן שדה SUMMARY במלואו
        table_name: שם הטבלה במסד הנתונים
    
    Returns:
        bool: True אם נשלח בהצלחה, False אחרת
    """
    try:
        safe_id = safe_str(chat_id)
        
        # בניית ההודעה לפי המפרט המדויק של עומר
        notification = f"✅ עדכון פרופיל למשתמש {safe_id} ✅\n"
        
        # תוכן ההודעה של המשתמש במלואו (לא מצונזר!)
        notification += f"{user_message}\n\n"
        
        # GPT-C
        notification += "<b>GPT-C:</b> "
        if gpt_c_changes and len(gpt_c_changes) > 0:
            notification += "\n"
            for change in gpt_c_changes:
                field = change.get('field', 'unknown')
                old_val = change.get('old_value', 'ריק') or 'ריק'
                new_val = change.get('new_value', '')
                notification += f"  ➕ {field}: [{old_val}] → [{new_val}]\n"
        else:
            notification += "אין שינויים\n"
        
        # GPT-D  
        notification += "\n<b>GPT-D:</b> שדות "
        if gpt_d_changes and len(gpt_d_changes) > 0:
            notification += "\n"
            for change in gpt_d_changes:
                field = change.get('field', 'unknown')
                old_val = change.get('old_value', 'ריק') or 'ריק'
                new_val = change.get('new_value', '')
                notification += f"  ➕ {field}: [{old_val}] → [{new_val}]\n"
        else:
            notification += "אין שינויים\n"
        
        # GPT-E
        notification += "\nGPT-E: "
        if gpt_e_changes and len(gpt_e_changes) > 0:
            notification += "\n"
            for change in gpt_e_changes:
                field = change.get('field', 'unknown')
                old_val = change.get('old_value', 'ריק') or 'ריק'
                new_val = change.get('new_value', '')
                notification += f"  ➕ {field}: [{old_val}] → [{new_val}]\n"
        else:
            notification += "אין שינויים"
            
        # הוספת קאונטר GPT-E
        if gpt_e_counter:
            notification += f" {gpt_e_counter}"
        notification += "\n"
        
        # שדה SUMMARY
        notification += "\n\nשדה SUMMARY: "
        if summary:
            notification += f"{summary}\n"
        else:
            notification += "ריק\n"
        
        # זמן וטבלה
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        notification += f"\n⏰ {current_time} - עודכן במסד נתונים בטבלת {table_name}"
        
        # שליחה לאדמין דרך הפונקציה המרכזית
        from notifications import send_admin_notification_raw
        success = send_admin_notification_raw(notification)
        
        if success:
            total_changes = len(gpt_c_changes or []) + len(gpt_d_changes or []) + len(gpt_e_changes or [])
            logger.info(f"[PROFILE_NOTIFY] ✅ הודעת עדכון פרופיל נשלחה למשתמש {safe_id} ({total_changes} שינויים)", source="unified_profile_notifications")
        else:
            logger.error(f"[PROFILE_NOTIFY] ❌ שגיאה בשליחת הודעת עדכון פרופיל למשתמש {safe_id}", source="unified_profile_notifications")
        
        return success
        
    except Exception as e:
        logger.error(f"[PROFILE_NOTIFY] ❌ שגיאה בהתראת עדכון פרופיל למשתמש {safe_str(chat_id)}: {e}", source="unified_profile_notifications")
        return False

def migrate_old_calls_to_new_system():
    """
    🔄 מדריך למעבר מהפונקציות הישנות לחדשה
    
    ⬇️ הפונקציות הישנות שצריך להחליף:
    
    1. send_admin_profile_change_notification(message)
       ↓ החלף ב:
       send_profile_update_notification(chat_id, changes={'custom': message})
    
    2. send_admin_profile_notification(chat_id, changes)  
       ↓ החלף ב:
       send_profile_update_notification(chat_id, changes)
    
    3. _send_admin_profile_overview_notification(chat_id, user_msg, ...)
       ↓ החלף ב:
       send_profile_update_notification(chat_id, changes, user_msg, detailed=True, cost, processing_time)
    
    ✅ יתרונות:
    - פונקציה אחת במקום 4
    - אין כפילויות
    - קל לתחזוקה
    - הודעות עקביות
    """
    pass

def create_compatibility_wrappers():
    """
    🔧 יצירת wrappers לתאימות לאחור (זמני)
    בשביל שהקוד הישן לא יקרוס בזמן המעבר
    """
    
    def send_admin_profile_change_notification_wrapper(message: str) -> bool:
        """Wrapper זמני לפונקציה הישנה"""
        return send_profile_update_notification(
            chat_id="unknown",
            changes={'manual_message': message}
        )
    
    def send_admin_profile_notification_wrapper(chat_id: str, changes: Dict) -> bool:
        """Wrapper זמני לפונקציה הישנה"""
        return send_profile_update_notification(chat_id, changes)
    
    def send_admin_profile_overview_wrapper(chat_id: str, user_msg: str, **kwargs) -> bool:
        """Wrapper זמני לפונקציה הישנה המפורטת"""
        # חילוץ שינויים מכל הפרמטרים
        changes = {}
        
        gpt_c_changes = kwargs.get('gpt_c_changes', [])
        gpt_d_changes = kwargs.get('gpt_d_changes', [])
        gpt_e_changes = kwargs.get('gpt_e_changes', [])
        
        # איחוד כל השינויים
        all_changes = gpt_c_changes + gpt_d_changes + gpt_e_changes
        for change in all_changes:
            if isinstance(change, dict) and 'field' in change:
                changes[change['field']] = change.get('new_value', 'updated')
        
        return send_profile_update_notification(
            chat_id=chat_id,
            changes=changes,
            user_message=user_msg,
            detailed=True
        )
    
    return {
        'send_admin_profile_change_notification': send_admin_profile_change_notification_wrapper,
        'send_admin_profile_notification': send_admin_profile_notification_wrapper,
        '_send_admin_profile_overview_notification': send_admin_profile_overview_wrapper
    }

# ========================================
# נקודת כניסה ראשית
# ========================================

def main():
    """דוגמה להשימוש בפונקציה החדשה - לפי המפרט של עומר"""
    
    # דוגמה 1: עדכון עם שינויים ב-GPT-C בלבד
    gpt_c_changes = [
        {'field': 'age', 'old_value': '30', 'new_value': '25'},
        {'field': 'location', 'old_value': 'ריק', 'new_value': 'תל אביב'}
    ]
    
    send_profile_update_notification(
        chat_id="123456",
        user_message="אני בן 25 ואני גר בתל אביב וזה הדבר החדש שקרה לי השבוע",
        gpt_c_changes=gpt_c_changes,
        summary="משתמש בן 25 מתל אביב שחילק פרטים אישיים",
        table_name="user_profiles"
    )
    
    # דוגמה 2: עדכון מפורט עם כל ה-GPTs
    gpt_c_changes_full = [
        {'field': 'age', 'old_value': '30', 'new_value': '25'},
        {'field': 'self_religiosity_level', 'old_value': 'ריק', 'new_value': 'חילוני'},
        {'field': 'closet_status', 'old_value': 'ריק', 'new_value': 'חצי בחוץ'}
    ]
    
    gpt_d_changes_full = [
        {'field': 'occupation', 'old_value': 'ריק', 'new_value': 'מתכנת'}
    ]
    
    gpt_e_changes_full = [
        {'field': 'emotional_state', 'old_value': 'ריק', 'new_value': 'מעורב'}
    ]
    
    send_profile_update_notification(
        chat_id="5676571979",
        user_message="היי, אני בן 25, חילוני, עובד כמתכנת בתל אביב. אני חצי בחוץ מהארון, רק אמא וכמה חברים יודעים. המטרה שלי בקורס זה לעבור תהליך שאני אשלים עם עצמי. הפחד הכי גדול שלי זה אשמה, ובעתיד אני רוצה לחיות ביושרה ואושר פנימי וחיצוני.",
        gpt_c_changes=gpt_c_changes_full,
        gpt_d_changes=gpt_d_changes_full,
        gpt_e_changes=gpt_e_changes_full,
        gpt_e_counter="7/12",
        summary="משתמש גבר בן 25, חילוני, מתכנת מתל אביב. נמצא בחצי מהדרך מהארון. מטרתו בקורס: השלמה עם עצמו. פחד עיקרי: אשמה. חזון עתיד: חיים ביושרה ואושר.",
        table_name="user_profiles"
    )
    
    print("✅ דוגמאות הושלמו לפי המפרט של עומר!")

if __name__ == "__main__":
    main() 