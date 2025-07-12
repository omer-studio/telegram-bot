#!/usr/bin/env python3
"""
🎯 Smart Render Search - חיפוש חכם ברנדר
"""

import subprocess
import psycopg2
import json
import re
from datetime import datetime
from config import config
from simple_config import TimeoutConfig

def search_ssh_logs():
    """חיפוש בלוגי SSH בדרך הפשוטה"""
    print("🔍 חיפוש בלוגי SSH...")
    
    ssh_host = "srv-d0r895be5dus73fmsc8g@ssh.frankfurt.render.com"
    
    # פקודות פשוטות לחיפוש
    simple_commands = [
        # 1. בדיקת קבצי לוג קיימים
        "ls -la /var/log/",
        
        # 2. חיפוש פשוט אחר chat_id
        "grep -r 'chat_id' /var/log/ 2>/dev/null | head -10",
        
        # 3. חיפוש אחר הודעות עבריות
        "grep -r 'התקבלה הודעה' /var/log/ 2>/dev/null | head -10",
        
        # 4. חיפוש אחר prints של message_handler
        "grep -r 'message_handler' /var/log/ 2>/dev/null | head -10",
        
        # 5. לוגים של היום
        "find /var/log -name '*.log' -type f -newermt '2025-07-11' 2>/dev/null | head -10",
        
        # 6. תוכן stdout/stderr אם יש
        "tail -n 50 /var/log/stdout.log 2>/dev/null || echo 'אין stdout'",
        "tail -n 50 /var/log/stderr.log 2>/dev/null || echo 'אין stderr'"
    ]
    
    results = []
    
    for i, cmd in enumerate(simple_commands, 1):
        print(f"\n📋 פקודה {i}: {cmd}")
        
        try:
            full_cmd = f'ssh -o ConnectTimeout={TimeoutConfig.SSH_CONNECTION_TIMEOUT} -o StrictHostKeyChecking=no {ssh_host} "{cmd}"'
        
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TimeoutConfig.SSH_COMMAND_TIMEOUT,
                encoding='utf-8',
                errors='ignore'  # תיקון בעיית encoding
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if output and output != "אין stdout" and output != "אין stderr":
                    print(f"✅ תוצאה:")
                    lines = output.split('\n')
                    for line in lines[:10]:  # רק 10 שורות
                        print(f"   {line}")
                    results.append({
                        'command': cmd,
                        'output': output
                    })
                else:
                    print("📭 אין תוצאות")
            else:
                print(f"❌ שגיאה: {result.stderr.strip()}")
                
        except Exception as e:
            print(f"❌ שגיאה: {e}")
    
    return results

def search_deployment_logs_table():
    """חיפוש בטבלת deployment_logs"""
    print("\n💾 חיפוש בטבלת deployment_logs...")
    
    try:
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # תחילה נבדוק מה יש בטבלה
        cur.execute("""
            SELECT COUNT(*) 
            FROM deployment_logs 
            WHERE timestamp >= NOW() - INTERVAL '7 days'
        """)
        
        total_logs = cur.fetchone()[0]
        print(f"📊 סה\"כ לוגים בשבוע: {total_logs:,}")
        
        if total_logs == 0:
            print("❌ אין לוגים בשבוע האחרון")
            return []
        
        # חיפוש הודעות רלוונטיות
        cur.execute("""
            SELECT 
                timestamp,
                message,
                log_level,
                user_id
            FROM deployment_logs 
            WHERE timestamp >= NOW() - INTERVAL '7 days'
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        
        results = cur.fetchall()
        
        print(f"📋 נמצאו {len(results)} לוגים אחרונים")
        
        # חיפוש דברים מעניינים
        interesting_logs = []
        for timestamp, message, log_level, user_id in results:
            if any(keyword in str(message).lower() for keyword in [
                'chat_id', 'user_msg', 'הודעה', 'message', 'telegram'
            ]):
                interesting_logs.append({
                    'timestamp': timestamp,
                    'message': message,
                    'log_level': log_level,
                    'user_id': user_id
                })
        
        print(f"🎯 לוגים מעניינים: {len(interesting_logs)}")
        
        for log in interesting_logs[:10]:
            print(f"   {log['timestamp']} | {log['log_level']} | {str(log['message'])[:100]}...")
        
        cur.close()
        conn.close()
        
        return interesting_logs
        
    except Exception as e:
        print(f"❌ שגיאה במסד: {e}")
        return []

def search_existing_logs_simple():
    """חיפוש בלוגי רנדר שמתחתנים עם קוד קיים"""
    print("\n🔧 חיפוש עם פונקציות קיימות...")
    
    try:
        # נשתמש בפונקציה הקיימת
        from logs_manager import get_render_logs
        
        log_types = ['service', 'python', 'error', 'access']
        results = []
        
        for log_type in log_types:
            print(f"🔍 בודק לוג {log_type}...")
            
            try:
                logs = get_render_logs(log_type, 200)  # 200 שורות
                
                if logs and "שגיאה" not in logs and "timeout" not in logs:
                    print(f"✅ נמצאו לוגים ב-{log_type}")
                    
                    # חיפוש chat_id והודעות
                    lines = logs.split('\n')
                    for line in lines:
                        if any(keyword in line.lower() for keyword in [
                            'chat_id', 'user_msg', 'הודעה', 'message_handler'
                        ]):
                            results.append({
                                'log_type': log_type,
                                'content': line.strip()
                            })
                else:
                    print(f"❌ {log_type}: {logs[:100] if logs else 'ריק'}...")
                    
            except Exception as e:
                print(f"❌ שגיאה ב-{log_type}: {e}")
        
        print(f"📋 נמצאו {len(results)} שורות רלוונטיות")
        
        for result in results[:20]:  # 20 ראשונות
            print(f"   [{result['log_type']}] {result['content'][:80]}...")
        
        return results
        
    except Exception as e:
        print(f"❌ שגיאה בפונקציה קיימת: {e}")
        return []

def get_current_db_stats():
    """סטטיסטיקות נוכחיות של המסד"""
    print("\n📊 סטטיסטיקות נוכחיות של המסד...")
    
    try:
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # ספירת הודעות
        cur.execute("SELECT COUNT(*) FROM chat_messages")
        total_messages = cur.fetchone()[0]
        
        # ספירת משתמשים
        cur.execute("SELECT COUNT(DISTINCT chat_id) FROM chat_messages")
        total_users = cur.fetchone()[0]
        
        # הודעות של משתמשים בלבד
        cur.execute("""
            SELECT COUNT(*) 
            FROM chat_messages 
            WHERE user_msg IS NOT NULL AND user_msg != ''
        """)
        user_messages = cur.fetchone()[0]
        
        # משתמשים מהשבוע
        cur.execute("""
            SELECT COUNT(DISTINCT chat_id) 
            FROM chat_messages 
            WHERE timestamp >= NOW() - INTERVAL '7 days'
        """)
        active_users = cur.fetchone()[0]
        
        print(f"📬 סה\"כ הודעות: {total_messages:,}")
        print(f"👥 סה\"כ משתמשים: {total_users}")
        print(f"📝 הודעות משתמשים: {user_messages:,}")
        print(f"🟢 משתמשים פעילים השבוע: {active_users}")
        
        # פירוט לכל משתמש
        cur.execute("""
            SELECT 
                chat_id,
                COUNT(*) as user_messages_count
            FROM chat_messages 
            WHERE user_msg IS NOT NULL AND user_msg != '' 
            GROUP BY chat_id 
            ORDER BY user_messages_count DESC
        """)
        
        users_data = cur.fetchall()
        
        print(f"\n👥 פירוט משתמשים ({len(users_data)} משתמשים):")
        for i, (chat_id, count) in enumerate(users_data, 1):
            print(f"{i:2d}. 👤 {chat_id}: {count:,} הודעות")
        
        cur.close()
        conn.close()
        
        return {
            'total_messages': total_messages,
            'total_users': total_users,
            'user_messages': user_messages,
            'active_users': active_users,
            'users_data': users_data
        }
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        return None

def main():
    """הפונקציה הראשית"""
    print("🔍 === Smart Render Search ===")
    print(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 50)
    
    # 1. סטטיסטיקות נוכחיות
    current_stats = get_current_db_stats()
    
    # 2. חיפוש בSSH
    ssh_results = search_ssh_logs()
    
    # 3. חיפוש בטבלת deployment_logs  
    db_results = search_deployment_logs_table()
    
    # 4. חיפוש עם פונקציות קיימות
    existing_results = search_existing_logs_simple()
    
    # 5. סיכום
    print(f"\n🎯 === סיכום חיפוש ===")
    print(f"🔍 SSH: {len(ssh_results)} תוצאות")
    print(f"💾 DB: {len(db_results)} תוצאות") 
    print(f"🔧 קיימות: {len(existing_results)} תוצאות")
    
    # שמירת תוצאות
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"render_search_results_{timestamp}.json"
    
    results = {
        'search_time': datetime.now().isoformat(),
        'current_stats': current_stats,
        'ssh_results': ssh_results,
        'db_results': db_results,
        'existing_results': existing_results
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"💾 תוצאות נשמרו ב: {filename}")

if __name__ == "__main__":
    main() 