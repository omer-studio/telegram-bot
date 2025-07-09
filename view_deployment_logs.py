#!/usr/bin/env python3
"""
📊 Deployment Logs Viewer - כלי לצפייה וניתוח לוגי פריסה
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# Import with fallback for missing modules
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    print("⚠️ psycopg2 not available - cannot view logs")
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

def load_config():
    """טעינת קונפיגורציה"""
    try:
        from config import get_config
        return get_config()
    except Exception as e:
        print(f"❌ שגיאה בטעינת קונפיגורציה: {e}")
        return {}

def get_db_connection():
    """קבלת חיבור למסד הנתונים"""
    if not PSYCOPG2_AVAILABLE:
        print("❌ psycopg2 לא זמין")
        return None
        
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

def show_recent_sessions(limit=10):
    """הצגת סשנים אחרונים"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                session_id,
                environment,
                commit_hash,
                commit_message,
                branch_name,
                MIN(timestamp) as start_time,
                MAX(timestamp) as end_time,
                COUNT(*) as log_count,
                COUNT(CASE WHEN log_level = 'ERROR' THEN 1 END) as error_count,
                COUNT(CASE WHEN log_level = 'WARNING' THEN 1 END) as warning_count
            FROM deployment_logs 
            GROUP BY session_id, environment, commit_hash, commit_message, branch_name
            ORDER BY start_time DESC 
            LIMIT %s
        """, (limit,))
        
        sessions = cur.fetchall()
        
        print(f"\n📋 {len(sessions)} סשנים אחרונים:")
        print("=" * 120)
        print(f"{'#':<3} {'Session ID':<20} {'Env':<8} {'Start Time':<20} {'Duration':<10} {'Logs':<6} {'Errors':<6} {'Commit':<10}")
        print("=" * 120)
        
        for i, session in enumerate(sessions, 1):
            session_id, env, commit_hash, commit_msg, branch, start_time, end_time, log_count, error_count, warning_count = session
            
            # חישוב משך זמן
            if start_time and end_time:
                duration = end_time - start_time
                duration_str = f"{duration.total_seconds():.0f}s"
            else:
                duration_str = "N/A"
            
            # צבע לפי מספר שגיאות
            status_icon = "🔴" if error_count > 0 else "🟡" if warning_count > 0 else "🟢"
            
            print(f"{i:<3} {session_id:<20} {env:<8} {start_time.strftime('%m-%d %H:%M:%S'):<20} {duration_str:<10} {log_count:<6} {error_count:<6} {commit_hash[:8]:<10} {status_icon}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בשליפת סשנים: {e}")

def show_session_logs(session_id: str, level_filter: str = None, limit: int = 100):
    """הצגת לוגים מסשן ספציפי"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # בניית שאילתה עם פילטר
        where_clause = "WHERE session_id = %s"
        params = [session_id]
        
        if level_filter:
            where_clause += " AND log_level = %s"
            params.append(level_filter.upper())
        
        cur.execute(f"""
            SELECT 
                timestamp,
                log_level,
                source_module,
                source_function,
                source_line,
                message,
                user_id,
                error_type,
                performance_ms,
                memory_mb,
                cpu_percent
            FROM deployment_logs 
            {where_clause}
            ORDER BY timestamp DESC 
            LIMIT %s
        """, params + [limit])
        
        logs = cur.fetchall()
        
        if not logs:
            print(f"❌ לא נמצאו לוגים לסשן {session_id}")
            return
        
        print(f"\n📜 לוגים מסשן {session_id} (מוגבל ל-{limit}):")
        if level_filter:
            print(f"🔍 מסונן לפי: {level_filter}")
        print("=" * 150)
        
        for log in logs:
            timestamp, level, module, function, line, message, user_id, error_type, perf_ms, memory_mb, cpu_percent = log
            
            # אייקון לפי רמת לוג
            level_icon = {
                'ERROR': '🔴',
                'WARNING': '🟡', 
                'INFO': '🔵',
                'DEBUG': '🟣',
                'PERFORMANCE': '⚡',
                'USER_ACTION': '👤'
            }.get(level, '⚪')
            
            # פורמט זמן
            time_str = timestamp.strftime('%H:%M:%S.%f')[:-3]
            
            # מידע נוסף
            extra_info = []
            if user_id:
                extra_info.append(f"User:{user_id}")
            if perf_ms:
                extra_info.append(f"⏱️{perf_ms}ms")
            if memory_mb:
                extra_info.append(f"💾{memory_mb}MB")
            if error_type:
                extra_info.append(f"❌{error_type}")
            
            extra_str = " | ".join(extra_info)
            
            print(f"{level_icon} {time_str} [{level:<12}] {module}:{function}:{line}")
            print(f"   📝 {message}")
            if extra_str:
                print(f"   ℹ️  {extra_str}")
            print()
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בשליפת לוגים: {e}")

def show_errors_summary(hours=24):
    """הצגת סיכום שגיאות"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # שגיאות לפי סוג
        cur.execute("""
            SELECT 
                error_type,
                COUNT(*) as count,
                MAX(timestamp) as last_seen
            FROM deployment_logs 
            WHERE log_level = 'ERROR' 
            AND timestamp > NOW() - INTERVAL '%s hours'
            AND error_type IS NOT NULL
            GROUP BY error_type
            ORDER BY count DESC
        """, (hours,))
        
        error_types = cur.fetchall()
        
        print(f"\n🔴 שגיאות ב-{hours} שעות האחרונות:")
        print("=" * 80)
        
        if error_types:
            for error_type, count, last_seen in error_types:
                print(f"❌ {error_type}: {count} פעמים (אחרון: {last_seen.strftime('%m-%d %H:%M')})")
        else:
            print("✅ אין שגיאות!")
        
        # שגיאות לפי מודול
        cur.execute("""
            SELECT 
                source_module,
                COUNT(*) as count
            FROM deployment_logs 
            WHERE log_level = 'ERROR' 
            AND timestamp > NOW() - INTERVAL '%s hours'
            GROUP BY source_module
            ORDER BY count DESC
            LIMIT 10
        """, (hours,))
        
        module_errors = cur.fetchall()
        
        if module_errors:
            print(f"\n🔴 שגיאות לפי מודול:")
            for module, count in module_errors:
                print(f"📁 {module}: {count} שגיאות")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בשליפת סיכום שגיאות: {e}")

def show_performance_stats(hours=24):
    """הצגת סטטיסטיקות ביצועים"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                AVG(performance_ms) as avg_ms,
                MAX(performance_ms) as max_ms,
                AVG(memory_mb) as avg_memory,
                MAX(memory_mb) as max_memory,
                AVG(cpu_percent) as avg_cpu,
                MAX(cpu_percent) as max_cpu,
                COUNT(*) as total_logs
            FROM deployment_logs 
            WHERE timestamp > NOW() - INTERVAL '%s hours'
            AND performance_ms IS NOT NULL
        """, (hours,))
        
        stats = cur.fetchone()
        
        if stats and stats[0]:
            avg_ms, max_ms, avg_memory, max_memory, avg_cpu, max_cpu, total_logs = stats
            
            print(f"\n⚡ סטטיסטיקות ביצועים ({hours} שעות):")
            print("=" * 50)
            print(f"⏱️  זמן תגובה ממוצע: {avg_ms:.1f}ms (מקסימום: {max_ms:.0f}ms)")
            print(f"💾 זיכרון ממוצע: {avg_memory:.1f}MB (מקסימום: {max_memory:.1f}MB)")
            print(f"🖥️  CPU ממוצע: {avg_cpu:.1f}% (מקסימום: {max_cpu:.1f}%)")
            print(f"📊 סה\"כ לוגים: {total_logs}")
        else:
            print(f"\n⚡ אין נתוני ביצועים ב-{hours} שעות האחרונות")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בשליפת סטטיסטיקות: {e}")

def show_user_activity(hours=24, limit=10):
    """הצגת פעילות משתמשים"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                user_id,
                COUNT(*) as activity_count,
                MAX(timestamp) as last_activity
            FROM deployment_logs 
            WHERE timestamp > NOW() - INTERVAL '%s hours'
            AND user_id IS NOT NULL
            GROUP BY user_id
            ORDER BY activity_count DESC
            LIMIT %s
        """, (hours, limit))
        
        users = cur.fetchall()
        
        print(f"\n👥 פעילות משתמשים ({hours} שעות):")
        print("=" * 60)
        
        if users:
            for user_id, count, last_activity in users:
                print(f"👤 {user_id}: {count} פעולות (אחרון: {last_activity.strftime('%m-%d %H:%M')})")
        else:
            print("👤 אין פעילות משתמשים")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בשליפת פעילות משתמשים: {e}")

def main():
    """תפריט ראשי"""
    if len(sys.argv) < 2:
        print("""
🚀 Deployment Logs Viewer

שימוש:
  py view_deployment_logs.py sessions [limit]     - הצגת סשנים אחרונים
  py view_deployment_logs.py logs <session_id> [level] [limit] - לוגים מסשן
  py view_deployment_logs.py errors [hours]      - סיכום שגיאות
  py view_deployment_logs.py performance [hours] - סטטיסטיקות ביצועים
  py view_deployment_logs.py users [hours]       - פעילות משתמשים

דוגמאות:
  py view_deployment_logs.py sessions 5
  py view_deployment_logs.py logs session_20250706_123456 ERROR 50
  py view_deployment_logs.py errors 12
        """)
        return
    
    command = sys.argv[1].lower()
    
    if command == "sessions":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        show_recent_sessions(limit)
    
    elif command == "logs":
        if len(sys.argv) < 3:
            print("❌ נדרש session_id")
            return
        session_id = sys.argv[2]
        level_filter = sys.argv[3] if len(sys.argv) > 3 else None
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 100
        show_session_logs(session_id, level_filter, limit)
    
    elif command == "errors":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        show_errors_summary(hours)
    
    elif command == "performance":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        show_performance_stats(hours)
    
    elif command == "users":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        show_user_activity(hours)
    
    else:
        print(f"❌ פקודה לא מוכרת: {command}")

if __name__ == "__main__":
    main() 