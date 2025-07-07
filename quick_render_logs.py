#!/usr/bin/env python3
"""
🚀 Quick Render Logs - בדיקה זריזה של לוגי RENDER
פשוט תשנה את הפרמטרים למטה ותריץ!
"""

# ⚙️ פרמטרים לשינוי - כאן תשנה מה שאתה רוצה:
HOURS_TO_CHECK = 24        # כמה שעות אחורה לבדוק
SESSIONS_LIMIT = 5         # כמה סשנים אחרונים להציג
LOGS_LIMIT = 20           # כמה לוגים להציג מכל סשן
SHOW_ERRORS_ONLY = False  # True = רק שגיאות, False = הכל
SHOW_PERFORMANCE = True   # True = הצג ביצועים, False = אל תציג
SHOW_UNREAD_ONLY = False  # True = רק לוגים שלא נקראו, False = הכל

# ===== לא לשנות מכאן למטה =====

import json
import sys
from datetime import datetime, timedelta

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    print("❌ psycopg2 לא זמין - התקן עם: pip install psycopg2-binary")
    sys.exit(1)

def load_config():
    """טעינת קונפיגורציה"""
    try:
        with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ שגיאה בטעינת קונפיגורציה: {e}")
        return {}

def get_db_connection():
    """קבלת חיבור למסד הנתונים"""
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

def quick_check():
    """בדיקה זריזה של הלוגים"""
    print("🚀 בדיקה זריזה של לוגי RENDER")
    print("=" * 50)
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # 1. הצגת סשנים אחרונים
        print(f"\n📋 {SESSIONS_LIMIT} סשנים אחרונים:")
        print("-" * 40)
        
        cur.execute("""
            SELECT 
                session_id,
                environment,
                MIN(timestamp) as start_time,
                MAX(timestamp) as end_time,
                COUNT(*) as log_count,
                COUNT(CASE WHEN log_level = 'ERROR' THEN 1 END) as error_count,
                COUNT(CASE WHEN log_level = 'WARNING' THEN 1 END) as warning_count
            FROM deployment_logs 
            WHERE timestamp > NOW() - INTERVAL '%s hours'
            GROUP BY session_id, environment
            ORDER BY start_time DESC 
            LIMIT %s
        """, (HOURS_TO_CHECK, SESSIONS_LIMIT))
        
        sessions = cur.fetchall()
        
        if not sessions:
            print(f"❌ אין סשנים ב-{HOURS_TO_CHECK} שעות האחרונות")
            return
        
        for i, session in enumerate(sessions, 1):
            session_id, env, start_time, end_time, log_count, error_count, warning_count = session
            
            # אייקון סטטוס
            status = "🔴" if error_count > 0 else "🟡" if warning_count > 0 else "🟢"
            
            print(f"{i}. {status} {session_id}")
            print(f"   📅 {start_time.strftime('%d/%m %H:%M')} | 📊 {log_count} לוגים | ❌ {error_count} שגיאות")
        
        # 2. בדיקת שגיאות
        print(f"\n🔴 שגיאות ב-{HOURS_TO_CHECK} שעות האחרונות:")
        print("-" * 40)
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_errors,
                COUNT(DISTINCT session_id) as sessions_with_errors
            FROM deployment_logs 
            WHERE log_level = 'ERROR' 
            AND timestamp > NOW() - INTERVAL '%s hours'
        """, (HOURS_TO_CHECK,))
        
        error_stats = cur.fetchone()
        total_errors, sessions_with_errors = error_stats
        
        if total_errors > 0:
            print(f"❌ {total_errors} שגיאות ב-{sessions_with_errors} סשנים")
            
            # הצגת השגיאות האחרונות
            cur.execute("""
                SELECT 
                    timestamp,
                    session_id,
                    message,
                    error_type
                FROM deployment_logs 
                WHERE log_level = 'ERROR' 
                AND timestamp > NOW() - INTERVAL '%s hours'
                ORDER BY timestamp DESC 
                LIMIT 5
            """, (HOURS_TO_CHECK,))
            
            recent_errors = cur.fetchall()
            
            for error in recent_errors:
                timestamp, session_id, message, error_type = error
                print(f"   🔴 {timestamp.strftime('%H:%M')} | {session_id[:15]}... | {message[:50]}...")
        else:
            print("✅ אין שגיאות!")
        
        # 3. לוגים אחרונים מהסשן הראשון
        if sessions:
            latest_session = sessions[0][0]  # session_id
            print(f"\n📜 לוגים אחרונים מ-{latest_session}:")
            print("-" * 40)
            
            where_clause = "WHERE session_id = %s"
            params = [latest_session]
            
            if SHOW_ERRORS_ONLY:
                where_clause += " AND log_level = 'ERROR'"
            
            # בדיקת עמודת read
            if SHOW_UNREAD_ONLY:
                # בדיקה אם עמודת read קיימת
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'deployment_logs' AND column_name = 'read'
                    )
                """)
                has_read_column = cur.fetchone()[0]
                
                if has_read_column:
                    where_clause += " AND read = FALSE"
                    print("📖 מציג רק לוגים שלא נקראו")
                else:
                    print("⚠️ אין עמודת 'read' - מציג הכל")
            
            cur.execute(f"""
                SELECT 
                    timestamp,
                    log_level,
                    message
                FROM deployment_logs 
                {where_clause}
                ORDER BY timestamp DESC 
                LIMIT %s
            """, params + [LOGS_LIMIT])
            
            logs = cur.fetchall()
            
            if logs:
                for log in logs:
                    timestamp, level, message = log
                    
                    # אייקון לפי רמה
                    level_icon = {
                        'ERROR': '🔴',
                        'WARNING': '🟡',
                        'INFO': '🔵',
                        'DEBUG': '🟣'
                    }.get(level, '⚪')
                    
                    print(f"   {level_icon} {timestamp.strftime('%H:%M:%S')} | {message[:60]}...")
            else:
                print("   📭 אין לוגים")
        
        # 4. סטטיסטיקות ביצועים
        if SHOW_PERFORMANCE:
            print(f"\n⚡ ביצועים ב-{HOURS_TO_CHECK} שעות האחרונות:")
            print("-" * 40)
            
            cur.execute("""
                SELECT 
                    AVG(performance_ms) as avg_ms,
                    MAX(performance_ms) as max_ms,
                    AVG(memory_mb) as avg_memory,
                    MAX(memory_mb) as max_memory,
                    COUNT(*) as total_logs
                FROM deployment_logs 
                WHERE timestamp > NOW() - INTERVAL '%s hours'
                AND performance_ms IS NOT NULL
            """, (HOURS_TO_CHECK,))
            
            stats = cur.fetchone()
            
            if stats and stats[0]:
                avg_ms, max_ms, avg_memory, max_memory, total_logs = stats
                print(f"   ⏱️  זמן ממוצע: {avg_ms:.1f}ms (מקס: {max_ms:.0f}ms)")
                print(f"   💾 זיכרון ממוצע: {avg_memory:.1f}MB (מקס: {max_memory:.1f}MB)")
                print(f"   📊 סה\"כ לוגים: {total_logs}")
            else:
                print("   📊 אין נתוני ביצועים")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 50)
        print("✅ בדיקה הושלמה!")
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")

def check_unread_logs():
    """בדיקת לוגים לא נקראים"""
    print("📖 בדיקת לוגים לא נקראים")
    print("=" * 50)
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # בדיקה אם עמודת read קיימת
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'deployment_logs' AND column_name = 'read'
            )
        """)
        has_read_column = cur.fetchone()[0]
        
        if not has_read_column:
            print("❌ אין עמודת 'read' בטבלה")
            print("💡 הרץ: python add_read_column.py")
            return
        
        # סה"כ לוגים לא נקראים
        cur.execute("SELECT COUNT(*) FROM deployment_logs WHERE read = FALSE")
        total_unread = cur.fetchone()[0]
        
        # לוגים לא נקראים ב-24 שעות
        cur.execute("""
            SELECT COUNT(*) FROM deployment_logs 
            WHERE read = FALSE AND timestamp >= NOW() - INTERVAL '24 hours'
        """)
        unread_24h = cur.fetchone()[0]
        
        print(f"📊 סה\"כ לוגים לא נקראים: {total_unread:,}")
        print(f"🔥 לוגים לא נקראים ב-24 שעות: {unread_24h:,}")
        
        if unread_24h > 0:
            # לוגים לא נקראים לפי רמה
            cur.execute("""
                SELECT 
                    log_level,
                    COUNT(*) as count
                FROM deployment_logs 
                WHERE read = FALSE 
                AND timestamp >= NOW() - INTERVAL '24 hours'
                GROUP BY log_level
                ORDER BY count DESC
            """)
            
            level_counts = cur.fetchall()
            
            print("\n📈 לוגים לא נקראים לפי רמה:")
            for level, count in level_counts:
                icon = {'ERROR': '🔴', 'WARNING': '🟡', 'INFO': '🔵', 'DEBUG': '🟣'}.get(level, '⚪')
                print(f"   {icon} {level}: {count:,}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--unread":
        check_unread_logs()
    else:
        print(f"""
🔧 הגדרות נוכחיות:
   • שעות לבדיקה: {HOURS_TO_CHECK}
   • סשנים להציג: {SESSIONS_LIMIT}
   • לוגים להציג: {LOGS_LIMIT}
   • רק שגיאות: {'כן' if SHOW_ERRORS_ONLY else 'לא'}
   • הצג ביצועים: {'כן' if SHOW_PERFORMANCE else 'לא'}
   • רק לא נקראים: {'כן' if SHOW_UNREAD_ONLY else 'לא'}
""")
        
        quick_check() 