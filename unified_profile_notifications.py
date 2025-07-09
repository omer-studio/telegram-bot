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
    changes: Optional[Dict] = None,
    user_message: Optional[str] = None,
    detailed: bool = False,
    cost: Optional[float] = None,
    processing_time: Optional[float] = None
) -> bool:
    """
    🎯 פונקציה אחת לכל התראות עדכון פרופיל
    
    Args:
        chat_id: ID המשתמש
        changes: שינויים שזוהו בפרופיל (Dict)
        user_message: ההודעה המקורית של המשתמש (אופציונלי)
        detailed: האם לשלוח דוח מפורט (True/False)
        cost: עלות העיבוד (אופציונלי)
        processing_time: זמן העיבוד בשניות (אופציונלי)
    
    Returns:
        bool: True אם נשלח בהצלחה, False אחרת
    """
    try:
        safe_id = safe_str(chat_id)
        
        # בדיקה בסיסית
        if not changes:
            logger.debug(f"[PROFILE_NOTIFY] אין שינויים למשתמש {safe_id} - לא נשלחת הודעה", source="unified_profile_notifications")
            return True
        
        # בניית הודעה בסיסית
        notification = f"✅ עדכון פרופיל למשתמש {safe_id[-6:]}... ✅\n\n"
        
        # ספירת שינויים
        total_changes = len(changes)
        notification += f"🔄 **סה״כ שינויים: {total_changes}**\n"
        
        # פירוט שינויים (עד 5 ראשונים)
        changes_list = list(changes.items())[:5]
        for field, value in changes_list:
            # קיצור ערכים ארוכים
            display_value = str(value)[:50]
            if len(str(value)) > 50:
                display_value += "..."
            notification += f"• **{field}:** {display_value}\n"
        
        # אם יש יותר מ-5 שינויים
        if total_changes > 5:
            notification += f"• ...ועוד {total_changes - 5} שינויים\n"
        
        # הוספת פרטים נוספים אם התבקש דוח מפורט
        if detailed:
            notification += "\n📊 **פרטים נוספים:**\n"
            
            if user_message:
                short_msg = user_message[:100] + "..." if len(user_message) > 100 else user_message
                notification += f"💬 הודעה: {short_msg}\n"
            
            if cost is not None:
                notification += f"💰 עלות: ${cost:.4f}\n"
            
            if processing_time is not None:
                notification += f"⏱️ זמן עיבוד: {processing_time:.2f} שניות\n"
        
        # הוספת זמן
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        notification += f"\n⏰ {current_time}"
        
        # שליחה לאדמין דרך הפונקציה המרכזית
        from notifications import send_admin_notification_raw
        success = send_admin_notification_raw(notification)
        
        if success:
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
    """דוגמה להשימוש בפונקציה החדשה"""
    
    # דוגמה 1: עדכון פשוט
    changes_basic = {
        'age': 25,
        'location': 'תל אביב'
    }
    
    send_profile_update_notification(
        chat_id="123456",
        changes=changes_basic
    )
    
    # דוגמה 2: עדכון מפורט
    changes_detailed = {
        'age': 25,
        'location': 'תל אביב',
        'occupation': 'מתכנת',
        'interests': 'טכנולוגיה, ספורט'
    }
    
    send_profile_update_notification(
        chat_id="123456",
        changes=changes_detailed,
        user_message="אני בן 25 ואני עובד כמתכנת בתל אביב",
        detailed=True,
        cost=0.0025,
        processing_time=1.8
    )
    
    print("✅ דוגמאות הושלמו!")

if __name__ == "__main__":
    main() 