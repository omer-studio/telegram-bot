#!/usr/bin/env python3
"""
🕐 בדיקת תפקוד יומית אוטומטית של הבוט

זה הסקריפט שירוץ כל יום כדי לוודא שהבוט עובד תקין ושאין משתמשים תקועים
ברשימת ההתאוששות.

אמור להיקרא מ-cron job או מ-scheduler אוטומטי.
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timedelta

def setup_environment():
    """מגדיר את הסביבה לבדיקה"""
    try:
        # הוספת הנתיב הנוכחי לPATH
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        # בדיקה שכל הקבצים הנדרשים קיימים
        required_files = [
            "notifications.py",
            "auto_rollback.py", 
            "gpt_a_handler.py",
            "config.py"
        ]
        
        missing_files = []
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)
        
        if missing_files:
            print(f"❌ קבצים חסרים: {missing_files}")
            return False
        
        print("✅ סביבה הוגדרה בהצלחה")
        return True
        
    except Exception as e:
        print(f"❌ שגיאה בהגדרת סביבה: {e}")
        return False

def check_recovery_users_status():
    """
    בודק את סטטוס רשימת המשתמשים להתאוששות
    
    Returns:
        dict: דוח על מצב הרשימה
    """
    try:
        from notifications import _load_critical_error_users, send_admin_notification
        from utils import get_israel_time
        
        users_data = _load_critical_error_users()
        current_time = get_israel_time()
        
        # סטטיסטיקות
        total_users = len(users_data)
        unrecovered_users = []
        old_unrecovered = []
        recent_errors = []
        
        for chat_id, user_info in users_data.items():
            if not user_info.get("recovered", False):
                unrecovered_users.append(chat_id)
                
                # בדיקה אם זה ישן מדי (יותר מ-24 שעות)
                try:
                    error_time = datetime.fromisoformat(user_info["timestamp"])
                    if hasattr(error_time, 'tzinfo') and error_time.tzinfo is None:
                        import pytz
                        israel_tz = pytz.timezone('Asia/Jerusalem')
                        error_time = israel_tz.localize(error_time)
                    
                    time_diff = current_time - error_time
                    if time_diff.total_seconds() > 86400:  # 24 שעות
                        old_unrecovered.append({
                            "chat_id": chat_id,
                            "hours_ago": int(time_diff.total_seconds() / 3600),
                            "error": user_info.get("error_message", "לא ידוע")[:50]
                        })
                    elif time_diff.total_seconds() < 3600:  # פחות משעה
                        recent_errors.append({
                            "chat_id": chat_id,
                            "minutes_ago": int(time_diff.total_seconds() / 60),
                            "error": user_info.get("error_message", "לא ידוע")[:50]
                        })
                        
                except Exception as e:
                    print(f"⚠️ שגיאה בעיבוד זמן למשתמש {chat_id}: {e}")
        
        report = {
            "timestamp": current_time.isoformat(),
            "total_users": total_users,
            "unrecovered_count": len(unrecovered_users),
            "old_unrecovered_count": len(old_unrecovered),
            "recent_errors_count": len(recent_errors),
            "status": "healthy",
            "warnings": [],
            "details": {
                "old_unrecovered": old_unrecovered,
                "recent_errors": recent_errors
            }
        }
        
        # בדיקת אזהרות
        if len(old_unrecovered) > 0:
            report["warnings"].append(f"יש {len(old_unrecovered)} משתמשים לא מטופלים יותר מ-24 שעות")
            report["status"] = "warning"
        
        if len(unrecovered_users) > 5:
            report["warnings"].append(f"יש {len(unrecovered_users)} משתמשים כולל לא מטופלים")
            report["status"] = "warning"
        
        if len(recent_errors) > 3:
            report["warnings"].append(f"יש {len(recent_errors)} שגיאות חדשות בשעה האחרונה")
            report["status"] = "warning"
        
        return report
        
    except Exception as e:
        return {
            "error": f"שגיאה בבדיקת רשימת התאוששות: {e}",
            "status": "error"
        }

async def test_bot_basic_functionality():
    """
    בודק תפקוד בסיסי של הבוט
    
    Returns:
        dict: דוח על תפקוד הבוט
    """
    try:
        from auto_rollback import check_critical_bot_functionality
        
        is_healthy, error_details = check_critical_bot_functionality()
        
        return {
            "status": "healthy" if is_healthy else "error",
            "details": error_details,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "details": f"שגיאה בבדיקת תפקוד בסיסי: {e}",
            "timestamp": datetime.now().isoformat()
        }

def send_daily_health_report(recovery_report, bot_functionality_report):
    """
    שולח דוח בריאות יומי לאדמין
    
    Args:
        recovery_report (dict): דוח רשימת התאוששות
        bot_functionality_report (dict): דוח תפקוד בוט
    """
    try:
        from notifications import send_admin_notification
        from utils import get_israel_time
        
        current_time = get_israel_time()
        
        # קביעת סטטוס כללי
        overall_status = "healthy"
        if (recovery_report.get("status") == "error" or 
            bot_functionality_report.get("status") == "error"):
            overall_status = "error"
        elif (recovery_report.get("status") == "warning" or 
              bot_functionality_report.get("status") == "warning"):
            overall_status = "warning"
        
        # בניית ההודעה
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️",
            "error": "🚨"
        }
        
        message = f"""📊 דוח בריאות יומי של הבוט
⏰ {current_time.strftime('%d/%m/%Y %H:%M:%S')}

{status_emoji[overall_status]} **סטטוס כללי: {overall_status.upper()}**

🔧 **תפקוד בוט:**
{status_emoji[bot_functionality_report.get('status', 'error')]} {bot_functionality_report.get('details', 'לא זמין')}

👥 **רשימת התאוששות:**
{status_emoji[recovery_report.get('status', 'error')]} סה"כ משתמשים: {recovery_report.get('total_users', 0)}
• לא מטופלים: {recovery_report.get('unrecovered_count', 0)}
• ישנים (+24 שעות): {recovery_report.get('old_unrecovered_count', 0)}
• חדשים (-1 שעה): {recovery_report.get('recent_errors_count', 0)}"""

        # הוספת אזהרות
        if recovery_report.get("warnings"):
            message += "\n\n⚠️ **אזהרות:**"
            for warning in recovery_report["warnings"]:
                message += f"\n• {warning}"
        
        # הוספת פרטים אם יש בעיות
        if overall_status != "healthy":
            if recovery_report.get("details", {}).get("old_unrecovered"):
                message += "\n\n🔍 **משתמשים ישנים לא מטופלים:**"
                for user in recovery_report["details"]["old_unrecovered"][:3]:
                    message += f"\n• {user['chat_id']} ({user['hours_ago']} שעות): {user['error']}"
                if len(recovery_report["details"]["old_unrecovered"]) > 3:
                    message += f"\n... ועוד {len(recovery_report['details']['old_unrecovered']) - 3}"
        
        # שליחת ההודעה
        urgent = overall_status == "error"
        send_admin_notification(message, urgent=urgent)
        
        print(f"✅ דוח יומי נשלח לאדמין (סטטוס: {overall_status})")
        
    except Exception as e:
        print(f"❌ שגיאה בשליחת דוח יומי: {e}")

async def main():
    """
    הפונקציה הראשית לבדיקה יומית
    """
    print("🕐 מתחיל בדיקת בריאות יומית של הבוט...")
    print("=" * 50)
    
    # הגדרת סביבה
    if not setup_environment():
        print("❌ כשל בהגדרת סביבה - יוצא")
        return False
    
    # בדיקת רשימת התאוששות
    print("🔍 בודק רשימת משתמשים להתאוששות...")
    recovery_report = check_recovery_users_status()
    
    if recovery_report.get("error"):
        print(f"❌ בדיקת רשימת התאוששות נכשלה: {recovery_report['error']}")
    else:
        print(f"✅ בדיקת רשימת התאוששות הושלמה - סטטוס: {recovery_report['status']}")
        if recovery_report.get("warnings"):
            for warning in recovery_report["warnings"]:
                print(f"⚠️ {warning}")
    
    # בדיקת תפקוד בוט
    print("🔍 בודק תפקוד בסיסי של הבוט...")
    bot_report = await test_bot_basic_functionality()
    
    if bot_report["status"] == "error":
        print(f"❌ בדיקת תפקוד בוט נכשלה: {bot_report['details']}")
    else:
        print(f"✅ בדיקת תפקוד בוט הושלמה - סטטוס: {bot_report['status']}")
    
    # שליחת דוח לאדמין
    print("📤 שולח דוח יומי לאדמין...")
    send_daily_health_report(recovery_report, bot_report)
    
    # סיכום
    overall_healthy = (recovery_report.get("status") != "error" and 
                      bot_report["status"] != "error")
    
    if overall_healthy:
        print("🎉 בדיקה יומית הושלמה בהצלחה - הבוט תקין!")
    else:
        print("⚠️ בדיקה יומית זיהתה בעיות - ראה דוח מפורט באדמין")
    
    print("=" * 50)
    return overall_healthy

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"🚨 שגיאה קריטית בבדיקה יומית: {e}")
        sys.exit(1)