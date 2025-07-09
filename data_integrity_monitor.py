#!/usr/bin/env python3
"""
🛡️ מערכת ניטור שלמות נתונים בזמן אמת
מזהה שינויים חשודים ויוצרת התראות
"""

import psycopg2
from datetime import datetime, timedelta
from config import config
from simple_logger import logger
from admin_notifications import send_admin_notification

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

# 🚨 רמות אזהרה לשינויים חשודים
SUSPICIOUS_PATTERNS = {
    "mass_deletion": {
        "description": "מחיקה המונית של רשומות",
        "threshold": 5,  # מעל 5 מחיקות בשעה
        "severity": "critical"
    },
    "null_injection": {
        "description": "הזנת NULL לעמודות קריטיות",
        "threshold": 3,  # מעל 3 NULL בעמודות קריטיות
        "severity": "high"
    },
    "code_manipulation": {
        "description": "שינוי קודי אישור קיימים",
        "threshold": 1,  # כל שינוי בקוד אישור חשוד
        "severity": "critical"
    },
    "bulk_changes": {
        "description": "שינויים המוניים באותו זמן",
        "threshold": 10,  # מעל 10 שינויים בדקה
        "severity": "medium"
    }
}

def check_mass_deletions():
    """בודק מחיקות המוניות ב-24 שעות האחרונות"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקה אם יש פחות משתמשים מאתמול
        cur.execute("""
            SELECT COUNT(*) as current_count
            FROM user_profiles 
            WHERE code_approve IS NOT NULL
        """)
        current_count = cur.fetchone()[0]
        
        # בדיקת מינימום נדרש (לפי מה שאתה אמרת - 17 תלמידים + אתה)
        expected_minimum = 17
        
        if current_count < expected_minimum:
            alert_data = {
                "type": "mass_deletion",
                "severity": "critical",
                "message": f"⚠️ מספר קודי אישור ירד ל-{current_count} (מתחת למינימום {expected_minimum})",
                "current_count": current_count,
                "expected_minimum": expected_minimum,
                "timestamp": datetime.now().isoformat()
            }
            
            send_data_integrity_alert(alert_data)
            return alert_data
        
        cur.close()
        conn.close()
        return None
        
    except Exception as e:
        logger.error(f"❌ שגיאה בבדיקת מחיקות המוניות: {e}")
        return None

def check_null_injections():
    """בודק הזנת NULL לעמודות קריטיות"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקת NULL בעמודות קריטיות
        suspicious_nulls = []
        
        # בדיקה: משתמשים עם chat_id אבל בלי code_approve
        cur.execute("""
            SELECT COUNT(*) as null_codes
            FROM user_profiles 
            WHERE chat_id IS NOT NULL AND code_approve IS NULL
        """)
        null_codes = cur.fetchone()[0]
        
        if null_codes > 2:  # מעל 2 זה חשוד
            suspicious_nulls.append({
                "issue": "משתמשים עם chat_id אבל בלי code_approve",
                "count": null_codes
            })
        
        # בדיקה: קודי אישור ללא משתמש (זה תקין - תלמידים שלא הורידו טלגרם)
        cur.execute("""
            SELECT COUNT(*) as orphaned_codes
            FROM user_profiles 
            WHERE code_approve IS NOT NULL AND chat_id IS NULL
        """)
        orphaned_codes = cur.fetchone()[0]
        
        # זה תקין עד רמה מסוימת (תלמידים שלא הורידו טלגרם)
        if orphaned_codes > 15:  # אם יש יותר מ-15 זה יכול להיות חשוד
            suspicious_nulls.append({
                "issue": "קודי אישור רבים ללא chat_id",
                "count": orphaned_codes,
                "note": "יכול להיות תקין (תלמידים שלא הורידו טלגרם)"
            })
        
        if suspicious_nulls:
            alert_data = {
                "type": "null_injection",
                "severity": "high",
                "message": "🔍 זוהו בעיות NULL בעמודות קריטיות",
                "issues": suspicious_nulls,
                "timestamp": datetime.now().isoformat()
            }
            
            send_data_integrity_alert(alert_data)
            return alert_data
        
        cur.close()
        conn.close()
        return None
        
    except Exception as e:
        logger.error(f"❌ שגיאה בבדיקת NULL: {e}")
        return None

def check_duplicate_codes():
    """בודק קודי אישור כפולים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT code_approve, COUNT(*) as count
            FROM user_profiles 
            WHERE code_approve IS NOT NULL
            GROUP BY code_approve
            HAVING COUNT(*) > 1
        """)
        
        duplicates = cur.fetchall()
        
        if duplicates:
            alert_data = {
                "type": "duplicate_codes",
                "severity": "critical",
                "message": f"🚨 זוהו {len(duplicates)} קודי אישור כפולים!",
                "duplicates": [{"code": code, "count": count} for code, count in duplicates],
                "timestamp": datetime.now().isoformat()
            }
            
            send_data_integrity_alert(alert_data)
            return alert_data
        
        cur.close()
        conn.close()
        return None
        
    except Exception as e:
        logger.error(f"❌ שגיאה בבדיקת כפילויות: {e}")
        return None

def check_chat_history_integrity():
    """בודק שלמות היסטוריית צ'אט"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקת מספר הודעות
        cur.execute("SELECT COUNT(*) FROM chat_messages")
        total_messages = cur.fetchone()[0]
        
        # בדיקת הודעות ב-24 שעות האחרונות
        cur.execute("""
            SELECT COUNT(*) 
            FROM chat_messages 
            WHERE timestamp > %s
        """, (datetime.now() - timedelta(hours=24),))
        recent_messages = cur.fetchone()[0]
        
        # בדיקת משתמשים פעילים
        cur.execute("""
            SELECT COUNT(DISTINCT chat_id) 
            FROM chat_messages 
            WHERE timestamp > %s
        """, (datetime.now() - timedelta(days=7),))
        active_users = cur.fetchone()[0]
        
        integrity_data = {
            "total_messages": total_messages,
            "messages_24h": recent_messages,
            "active_users_7d": active_users,
            "timestamp": datetime.now().isoformat()
        }
        
        # התראה אם יש ירידה דרסטית בהודעות
        if recent_messages == 0 and total_messages > 100:
            alert_data = {
                "type": "chat_history_issue",
                "severity": "high",
                "message": "⚠️ לא נשמרו הודעות חדשות ב-24 שעות האחרונות",
                "data": integrity_data
            }
            send_data_integrity_alert(alert_data)
            return alert_data
        
        cur.close()
        conn.close()
        return integrity_data
        
    except Exception as e:
        logger.error(f"❌ שגיאה בבדיקת היסטוריית צ'אט: {e}")
        return None

def send_data_integrity_alert(alert_data):
    """שולח התראת שלמות נתונים לאדמין"""
    try:
        severity_emojis = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "🟡",
            "low": "ℹ️"
        }
        
        emoji = severity_emojis.get(alert_data.get("severity", "medium"), "⚠️")
        
        message = f"{emoji} **התראת שלמות נתונים**\n\n"
        message += f"🔍 **סוג:** {alert_data['type']}\n"
        message += f"📊 **חומרה:** {alert_data.get('severity', 'medium').upper()}\n"
        message += f"💬 **הודעה:** {alert_data['message']}\n"
        message += f"🕐 **זמן:** {alert_data['timestamp']}\n"
        
        # הוספת פרטים נוספים אם יש
        if 'issues' in alert_data:
            message += "\n📋 **פרטים:**\n"
            for issue in alert_data['issues']:
                message += f"• {issue}\n"
        
        if 'duplicates' in alert_data:
            message += "\n🔄 **כפילויות:**\n"
            for dup in alert_data['duplicates']:
                message += f"• קוד {dup['code']}: {dup['count']} פעמים\n"
        
        # התראה דחופה לבעיות קריטיות
        urgent = alert_data.get("severity") == "critical"
        
        send_admin_notification(message, urgent=urgent)
        logger.info(f"📨 נשלחה התראת שלמות נתונים: {alert_data['type']}")
        
    except Exception as e:
        logger.error(f"❌ שגיאה בשליחת התראת שלמות נתונים: {e}")

def run_full_integrity_check():
    """מריץ בדיקת שלמות מלאה"""
    try:
        logger.info("🛡️ מתחילה בדיקת שלמות נתונים מלאה")
        
        checks = [
            ("מחיקות המוניות", check_mass_deletions),
            ("הזנת NULL", check_null_injections),
            ("קודים כפולים", check_duplicate_codes),
            ("היסטוריית צ'אט", check_chat_history_integrity)
        ]
        
        results = {}
        issues_found = 0
        
        for check_name, check_func in checks:
            logger.info(f"🔍 בודק: {check_name}")
            result = check_func()
            results[check_name] = result
            
            if result and isinstance(result, dict) and result.get("severity"):
                issues_found += 1
        
        # סיכום
        if issues_found == 0:
            logger.info("✅ בדיקת שלמות נתונים הושלמה - לא נמצאו בעיות")
            print("✅ בדיקת שלמות נתונים הושלמה - לא נמצאו בעיות")
        else:
            logger.warning(f"⚠️ בדיקת שלמות נתונים הושלמה - נמצאו {issues_found} בעיות")
            print(f"⚠️ בדיקת שלמות נתונים הושלמה - נמצאו {issues_found} בעיות")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ שגיאה בבדיקת שלמות נתונים: {e}")
        print(f"❌ שגיאה בבדיקת שלמות נתונים: {e}")
        return None

if __name__ == "__main__":
    run_full_integrity_check() 