#!/usr/bin/env python3
"""
🚨 RENDER MONITOR - כלל הברזל לבדיקת בעיות ברנדר
==================================================

כלל ברזל: אם יש שגיאות שלא נקראו ברנדר - תקן אותן עד שהכל נקרא!

🎯 מה הקובץ הזה עושה:
1. בודק שגיאות לא נקראות ב-24 שעות האחרונות
2. מציג את הבעיות הקריטיות עם קומיט וזמן
3. נותן הוראות טכניות מדויקות לתיקון
4. מסמן שגיאות כנקראו אחרי שנפתרו

📋 הרצה: python render_monitor.py
"""

import json
import sys
from datetime import datetime, timedelta

def load_config():
    """🎯 טעינת קונפיגורציה דרך הפונקציה המרכזית"""
    try:
        from config import get_config
        return get_config()
    except Exception as e:
        print(f"❌ שגיאה בטעינת קונפיגורציה: {e}")
        return {}

def get_db_connection():
    """קבלת חיבור למסד הנתונים"""
    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 לא זמין - הרץ ברנדר!")
        sys.exit(1)
    
    config = load_config()
    db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
    
    if not db_url:
        print("❌ לא נמצא URL למסד הנתונים")
        return None
    
    try:
        return psycopg2.connect(db_url)
    except Exception as e:
        print(f"❌ שגיאה בחיבור למסד הנתונים: {e}")
        return None

def ensure_read_column():
    """וידוא שעמודת read קיימת"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # בדיקה אם עמודת read קיימת
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'deployment_logs' AND column_name = 'read'
            )
        """)
        exists = cur.fetchone()[0]
        
        if not exists:
            print("🔧 מוסיף עמודת 'read' לטבלה...")
            cur.execute("ALTER TABLE deployment_logs ADD COLUMN read BOOLEAN DEFAULT FALSE")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deployment_logs_read ON deployment_logs(read, timestamp)")
            cur.execute("UPDATE deployment_logs SET read = FALSE WHERE read IS NULL")
            conn.commit()
            print("✅ עמודת 'read' נוספה!")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ שגיאה בהוספת עמודת read: {e}")
        return False

def check_unread_errors():
    """🚨 כלל הברזל: בדיקת שגיאות לא נקראות"""
    print("🚨 כלל הברזל - בדיקת שגיאות לא נקראות")
    print("=" * 60)
    
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        
        # שגיאות לא נקראות ב-24 שעות
        cur.execute("""
            SELECT 
                id,
                timestamp,
                session_id,
                commit_hash,
                commit_message,
                source_module,
                source_function,
                message,
                error_type,
                stack_trace
            FROM deployment_logs 
            WHERE read = FALSE 
            AND log_level = 'ERROR'
            AND timestamp >= NOW() - INTERVAL '24 hours'
            ORDER BY timestamp DESC
        """)
        
        unread_errors = cur.fetchall()
        
        if not unread_errors:
            print("✅ אין שגיאות לא נקראות ב-24 שעות!")
            return []
        
        print(f"🔴 נמצאו {len(unread_errors)} שגיאות לא נקראות!")
        print("\n📋 שגיאות שצריך לתקן:")
        print("-" * 60)
        
        critical_issues = []
        
        for i, error in enumerate(unread_errors, 1):
            error_id, ts, session, commit_hash, commit_msg, module, function, msg, error_type, stack = error
            
            print(f"\n🔴 שגיאה #{i} [ID: {error_id}]")
            print(f"   ⏰ זמן: {ts.strftime('%d/%m %H:%M:%S')}")
            print(f"   📍 מיקום: {module}.{function}")
            print(f"   🔧 קומיט: {commit_hash[:8]} - {commit_msg[:50]}...")
            print(f"   💥 שגיאה: {error_type or 'Unknown'}")
            print(f"   📝 הודעה: {msg[:100]}...")
            
            # ניתוח וקביעת פעולה טכנית
            action = analyze_error_and_get_action(error_type, msg, module, function)
            print(f"   🎯 פעולה: {action}")
            
            critical_issues.append({
                'id': error_id,
                'timestamp': ts,
                'module': module,
                'function': function,
                'error_type': error_type,
                'message': msg,
                'action': action,
                'commit': commit_hash[:8]
            })
        
        cur.close()
        conn.close()
        
        return critical_issues
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת שגיאות: {e}")
        return []

def analyze_error_and_get_action(error_type, message, module, function):
    """ניתוח שגיאה וקביעת פעולה טכנית"""
    
    # Database errors
    if "psycopg2" in message or "database" in message.lower():
        return "בדוק חיבור DB, אולי connection timeout או query כבד"
    
    # Memory errors
    if "memory" in message.lower() or "MemoryError" in message:
        return "זליגת זיכרון - בדוק לולאות או משתנים גדולים"
    
    # API errors
    if "timeout" in message.lower() or "TimeoutError" in error_type:
        return "API timeout - הגדל timeout או בדוק שרת חיצוני"
    
    if "openai" in message.lower() or "gemini" in message.lower():
        return "בעיית API AI - בדוק API key או rate limiting"
    
    # Google Sheets errors
    if "sheets" in message.lower() or "gspread" in message.lower():
        return "בעיית Google Sheets - בדוק הרשאות או rate limit"
    
    # Permission errors
    if "permission" in message.lower() or "unauthorized" in message.lower():
        return "בעיית הרשאות - בדוק API keys או הרשאות גיליונות"
    
    # Import errors
    if "ModuleNotFoundError" in error_type or "ImportError" in error_type:
        return "חסרה חבילה - בדוק requirements.txt או התקנה"
    
    # JSON/Data errors
    if "json" in message.lower() or "JSONDecodeError" in error_type:
        return "בעיית JSON - בדוק פורמט נתונים או API response"
    
    # File errors
    if "FileNotFoundError" in error_type or "file" in message.lower():
        return "קובץ חסר - בדוק נתיבים או העלאת קבצים"
    
    # Generic network
    if "connection" in message.lower() or "network" in message.lower():
        return "בעיית רשת - בדוק חיבור אינטרנט או שרת חיצוני"
    
    # Function specific
    if module == "message_handler.py":
        return "בעיה בטיפול בהודעות - בדוק לוגיקת הודעות או concurrent"
    
    if module == "gpt_a_handler.py":
        return "בעיה ב-GPT A - המשתמשים לא מקבלים תשובות!"
    
    if "notification" in module:
        return "בעיית התראות - אדמין לא מקבל התראות"
    
    # Default
    return f"בדוק {module}.{function} - תיעד ותקן לפי stack trace"

def mark_errors_as_read(error_ids):
    """סימון שגיאות כנקראו"""
    if not error_ids:
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # סימון כנקרא
        cur.execute(f"""
            UPDATE deployment_logs 
            SET read = TRUE 
            WHERE id = ANY(%s)
        """, (error_ids,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ {len(error_ids)} שגיאות סומנו כנקראו")
        
    except Exception as e:
        print(f"❌ שגיאה בסימון שגיאות: {e}")

def show_summary():
    """הצגת סיכום כללי"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # סטטיסטיקות כלליות
        cur.execute("""
            SELECT 
                COUNT(*) as total_logs,
                COUNT(CASE WHEN log_level = 'ERROR' THEN 1 END) as total_errors,
                COUNT(CASE WHEN log_level = 'ERROR' AND read = FALSE THEN 1 END) as unread_errors
            FROM deployment_logs 
            WHERE timestamp >= NOW() - INTERVAL '24 hours'
        """)
        
        stats = cur.fetchone()
        total_logs, total_errors, unread_errors = stats
        
        print(f"\n📊 סיכום 24 שעות:")
        print(f"   📋 סה\"כ לוגים: {total_logs:,}")
        print(f"   🔴 סה\"כ שגיאות: {total_errors}")
        print(f"   👁️ שגיאות לא נקראו: {unread_errors}")
        
        if unread_errors == 0:
            print("✅ כל השגיאות נקראו - הכל בסדר!")
        else:
            print(f"⚠️ {unread_errors} שגיאות ממתינות לטיפול")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בהצגת סיכום: {e}")

def main():
    """פונקציה ראשית - כלל הברזל"""
    print("🚨 RENDER MONITOR - כלל הברזל")
    print("=" * 60)
    print("חוק: אם יש שגיאות לא נקראות ברנדר - תקן עד שהכל נקרא!")
    print("")
    
    # וידוא עמודת read
    if not ensure_read_column():
        print("❌ לא ניתן להמשיך ללא עמודת read")
        return
    
    # בדיקת שגיאות לא נקראות
    critical_issues = check_unread_errors()
    
    if not critical_issues:
        show_summary()
        print("\n🎉 כלל הברזל מתקיים - אין בעיות!")
        return
    
    # הצגת הוראות תיקון
    print(f"\n🎯 הוראות תיקון ל-{len(critical_issues)} בעיות:")
    print("=" * 60)
    
    for i, issue in enumerate(critical_issues, 1):
        print(f"\n{i}. {issue['module']}.{issue['function']} ({issue['commit']})")
        print(f"   📝 {issue['action']}")
    
    # שאלה אם לסמן כנקרא
    print(f"\n❓ האם טיפלת בכל הבעיות? (y/n): ", end="")
    try:
        choice = input().lower()
        if choice in ['y', 'yes', 'כן']:
            error_ids = [issue['id'] for issue in critical_issues]
            mark_errors_as_read(error_ids)
            print("\n✅ כל השגיאות סומנו כנקראו!")
            show_summary()
        else:
            print("\n⚠️ השגיאות נותרו לא נקראות - תקן ותריץ שוב!")
    except:
        print("\n⚠️ השגיאות נותרו לא נקראות")

if __name__ == "__main__":
    main() 