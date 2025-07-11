#!/usr/bin/env python3
"""
🚨 Ultimate Render Message Hunter
==================================
סריקה מלאה אגרסיבית של כל מקורות הרנדר לחילוץ הודעות!

מקורות:
1. SSH לרנדר - כל לוגי הקבצים
2. API רנדר - לוגי השירות
3. טבלת deployment_logs במסד נתונים
4. חיפוש הודעות chat_id/user_msg ברנדר
"""

import subprocess
import psycopg2
import requests
import json
import re
import time
from datetime import datetime, timedelta
from config import config
from simple_config import TimeoutConfig

# פרמטרים לחיפוש
HOURS_BACK = 168  # שבוע אחרון = 7*24
SSH_HOST = "srv-d0r895be5dus73fmsc8g@ssh.frankfurt.render.com"
DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

def extract_messages_from_ssh():
    """חילוץ הודעות דרך SSH מכל לוגי רנדר"""
    print("🚀 === חילוץ הודעות דרך SSH ===")
    
    extracted_messages = []
    
    # פקודות לחיפוש הודעות בלוגי רנדר
    search_commands = [
        # חיפוש chat_id בכל הלוגים
        f"find /var/log -name '*.log' -type f -mtime -{HOURS_BACK//24} -exec grep -l 'chat_id' {{}} \\; 2>/dev/null | head -20",
        
        # חיפוש user_msg בלוגים
        f"find /var/log -name '*.log' -type f -mtime -{HOURS_BACK//24} -exec grep -l 'user_msg' {{}} \\; 2>/dev/null | head -20",
        
        # חיפוש הודעות טלגרם
        f"find /var/log -name '*.log' -type f -mtime -{HOURS_BACK//24} -exec grep -l 'התקבלה הודעה' {{}} \\; 2>/dev/null | head -20",
        
        # חיפוש prints של הודעות
        f"find /var/log -name '*.log' -type f -mtime -{HOURS_BACK//24} -exec grep -l 'message_handler' {{}} \\; 2>/dev/null | head -20",
        
        # stdout/stderr לוגים
        "find /var/log -name 'stdout*' -type f -mtime -7 2>/dev/null",
        "find /var/log -name 'stderr*' -type f -mtime -7 2>/dev/null",
        
        # לוגי אפליקציה
        "ls -la /var/log/render/ 2>/dev/null",
        "ls -la /var/log/app/ 2>/dev/null",
        "ls -la /opt/render/project/src/ 2>/dev/null"
    ]
    
    print(f"🔍 מריץ {len(search_commands)} פקודות חיפוש...")
    
    for i, cmd in enumerate(search_commands, 1):
        print(f"\n📋 פקודה {i}: {cmd[:60]}...")
        
        try:
            full_cmd = f'ssh -o ConnectTimeout={TimeoutConfig.SSH_CONNECTION_TIMEOUT} -o StrictHostKeyChecking=no {SSH_HOST} "{cmd}"'
            
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TimeoutConfig.SSH_COMMAND_TIMEOUT
            )
            
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout.strip()
                print(f"✅ נמצאו קבצים:")
                
                # אם זה רשימת קבצים, קרא מהם תוכן
                if "/var/log" in output:
                    for log_file in output.split('\n')[:5]:  # רק 5 קבצים ראשונים
                        if log_file.strip():
                            print(f"   📄 {log_file}")
                            # קריאת תוכן הקובץ
                            read_cmd = f'tail -n 100 "{log_file.strip()}" 2>/dev/null | grep -E "(chat_id|user_msg|התקבלה הודעה)" | head -20'
                            content = get_ssh_content(read_cmd)
                            if content:
                                extracted_messages.extend(parse_log_content(content, f"SSH:{log_file}"))
                else:
                    print(f"   📝 {output}")
            
        except subprocess.TimeoutExpired:
            print("⏰ timeout")
        except Exception as e:
            print(f"❌ שגיאה: {e}")
        
        time.sleep(0.5)  # מנוחה קצרה
    
    return extracted_messages

def get_ssh_content(cmd):
    """קבלת תוכן דרך SSH"""
    try:
        full_cmd = f'ssh -o ConnectTimeout={TimeoutConfig.SSH_CONNECTION_TIMEOUT} -o StrictHostKeyChecking=no {SSH_HOST} "{cmd}"'
        
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        return None
        
    except Exception:
        return None

def extract_messages_from_render_api():
    """חילוץ הודעות דרך API רנדר"""
    print("\n🌐 === חילוץ הודעות דרך API רנדר ===")
    
    extracted_messages = []
    
    api_key = config.get('RENDER_API_KEY')
    service_id = config.get('RENDER_SERVICE_ID')
    
    if not api_key or not service_id:
        print("❌ חסרים נתוני API של רנדר")
        return extracted_messages
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }
    
    # זמן התחלה
    start_time = datetime.utcnow() - timedelta(hours=HOURS_BACK)
    
    try:
        print(f"🔍 משיכת לוגים מ-{HOURS_BACK} שעות אחורה...")
        
        logs_url = f"https://api.render.com/v1/services/{service_id}/logs"
        
        params = {
            'startTime': start_time.isoformat() + 'Z',
            'limit': 10000  # מקסימום לוגים
        }
        
        response = requests.get(logs_url, headers=headers, params=params, timeout=TimeoutConfig.RENDER_LOGS_TIMEOUT)
        
        if response.status_code == 200:
            logs_data = response.json()
            logs = logs_data.get('logs', [])
            
            print(f"📋 נמצאו {len(logs)} לוגים")
            
            # חיפוש הודעות בלוגים
            message_keywords = [
                'chat_id',
                'user_msg',
                'התקבלה הודעה',
                'message_handler',
                '📩',
                'user_message',
                'bot_reply'
            ]
            
            for log_entry in logs:
                message = log_entry.get('message', '')
                timestamp = log_entry.get('timestamp', '')
                
                for keyword in message_keywords:
                    if keyword in message:
                        extracted_messages.append({
                            'source': 'RENDER_API',
                            'timestamp': timestamp,
                            'content': message,
                            'keyword': keyword
                        })
                        break
            
            print(f"✅ חולצו {len(extracted_messages)} הודעות פוטנציאליות")
            
        else:
            print(f"❌ שגיאה בAPI: {response.status_code}")
            
    except Exception as e:
        print(f"❌ שגיאה במשיכת לוגים: {e}")
    
    return extracted_messages

def extract_messages_from_deployment_logs():
    """חילוץ הודעות מטבלת deployment_logs"""
    print("\n💾 === חילוץ הודעות מטבלת deployment_logs ===")
    
    extracted_messages = []
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקה אם הטבלה קיימת
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'deployment_logs'
            )
        """)
        
        if not cur.fetchone()[0]:
            print("❌ טבלת deployment_logs לא קיימת")
            return extracted_messages
        
        # חיפוש הודעות בטבלה
        cur.execute(f"""
            SELECT 
                timestamp,
                message,
                log_level,
                session_id,
                user_id
            FROM deployment_logs 
            WHERE timestamp >= NOW() - INTERVAL '{HOURS_BACK} hours'
            AND (
                message LIKE '%chat_id%' OR
                message LIKE '%user_msg%' OR
                message LIKE '%התקבלה הודעה%' OR
                message LIKE '%message_handler%' OR
                message LIKE '%📩%'
            )
            ORDER BY timestamp DESC
        """)
        
        results = cur.fetchall()
        
        print(f"📋 נמצאו {len(results)} הודעות רלוונטיות בטבלה")
        
        for timestamp, message, log_level, session_id, user_id in results:
            extracted_messages.append({
                'source': 'DEPLOYMENT_LOGS',
                'timestamp': timestamp.isoformat(),
                'content': message,
                'log_level': log_level,
                'session_id': session_id,
                'user_id': user_id
            })
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בגישה למסד: {e}")
    
    return extracted_messages

def parse_log_content(content, source):
    """פירוק תוכן לוגים לחילוץ הודעות"""
    messages = []
    
    # תבניות לחיפוש chat_id והודעות
    patterns = [
        r'chat_id[=:]\s*([0-9]+)',
        r'user_msg[=:]\s*["\']([^"\']+)["\']',
        r'התקבלה הודעה.*?chat_id[=:]\s*([0-9]+)',
        r'📩.*?([0-9]+)',
    ]
    
    lines = content.split('\n')
    
    for line in lines:
        if any(keyword in line for keyword in ['chat_id', 'user_msg', 'התקבלה הודעה']):
            # חילוץ timestamp אם יש
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})', line)
            timestamp = timestamp_match.group(1) if timestamp_match else 'unknown'
            
            messages.append({
                'source': source,
                'timestamp': timestamp,
                'content': line.strip(),
                'raw_line': line
            })
    
    return messages

def analyze_and_save_results(all_messages):
    """ניתוח ושמירת התוצאות"""
    print(f"\n📊 === ניתוח {len(all_messages)} הודעות שנמצאו ===")
    
    if not all_messages:
        print("❌ לא נמצאו הודעות")
        return
    
    # קיבוץ לפי מקור
    by_source = {}
    for msg in all_messages:
        source = msg['source']
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(msg)
    
    print("\n📈 פילוח לפי מקור:")
    for source, messages in by_source.items():
        print(f"   📋 {source}: {len(messages)} הודעות")
    
    # חיפוש chat_id וhודעות משתמשים
    found_chat_ids = set()
    user_messages = []
    
    for msg in all_messages:
        content = msg['content']
        
        # חיפוש chat_id
        chat_id_match = re.search(r'chat_id[=:\s]*([0-9]+)', content)
        if chat_id_match:
            found_chat_ids.add(chat_id_match.group(1))
        
        # חיפוש הודעות משתמש
        if 'user_msg' in content or 'התקבלה הודעה' in content:
            user_messages.append(msg)
    
    print(f"\n👥 chat_ids שנמצאו: {len(found_chat_ids)}")
    for chat_id in sorted(found_chat_ids):
        print(f"   👤 {chat_id}")
    
    print(f"\n💬 הודעות משתמשים שנמצאו: {len(user_messages)}")
    
    # שמירת התוצאות
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # קובץ מלא
    filename = f"render_messages_extraction_{timestamp}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump({
            'extraction_time': datetime.now().isoformat(),
            'total_messages': len(all_messages),
            'sources': {k: len(v) for k, v in by_source.items()},
            'found_chat_ids': list(found_chat_ids),
            'messages': all_messages
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 התוצאות נשמרו ב: {filename}")
    
    # קובץ סיכום
    summary_filename = f"render_messages_summary_{timestamp}.txt"
    with open(summary_filename, 'w', encoding='utf-8') as f:
        f.write(f"🚀 סיכום חילוץ הודעות מרנדר\n")
        f.write(f"תאריך: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
        f.write(f"📊 סה\"כ הודעות: {len(all_messages)}\n")
        f.write(f"👥 chat_ids נמצאו: {len(found_chat_ids)}\n")
        f.write(f"💬 הודעות משתמש: {len(user_messages)}\n\n")
        
        f.write("📈 פילוח לפי מקור:\n")
        for source, messages in by_source.items():
            f.write(f"   {source}: {len(messages)} הודעות\n")
        
        f.write(f"\n👥 chat_ids:\n")
        for chat_id in sorted(found_chat_ids):
            f.write(f"   {chat_id}\n")
        
        f.write(f"\n💬 דוגמאות הודעות:\n")
        for msg in user_messages[:20]:  # 20 ראשונות
            f.write(f"   {msg['timestamp']} | {msg['source']} | {msg['content'][:100]}...\n")
    
    print(f"📄 סיכום נשמר ב: {summary_filename}")
    
    return found_chat_ids, user_messages

def main():
    """הפונקציה הראשית"""
    print("🚨 === Ultimate Render Message Hunter ===")
    print(f"🕐 חיפוש מ-{HOURS_BACK} שעות אחורה")
    print("=" * 60)
    
    all_messages = []
    
    # 1. חילוץ דרך SSH
    try:
        ssh_messages = extract_messages_from_ssh()
        all_messages.extend(ssh_messages)
        print(f"✅ SSH: {len(ssh_messages)} הודעות")
    except Exception as e:
        print(f"❌ SSH נכשל: {e}")
    
    # 2. חילוץ דרך API
    try:
        api_messages = extract_messages_from_render_api()
        all_messages.extend(api_messages)
        print(f"✅ API: {len(api_messages)} הודעות")
    except Exception as e:
        print(f"❌ API נכשל: {e}")
    
    # 3. חילוץ ממסד נתונים
    try:
        db_messages = extract_messages_from_deployment_logs()
        all_messages.extend(db_messages)
        print(f"✅ DB: {len(db_messages)} הודעות")
    except Exception as e:
        print(f"❌ DB נכשל: {e}")
    
    # 4. ניתוח תוצאות
    found_chat_ids, user_messages = analyze_and_save_results(all_messages)
    
    print(f"\n🎯 === תוצאות סופיות ===")
    print(f"📊 סה\"כ הודעות שנמצאו: {len(all_messages)}")
    print(f"👥 chat_ids ייחודיים: {len(found_chat_ids)}")
    print(f"💬 הודעות משתמש פוטנציאליות: {len(user_messages)}")
    
    if found_chat_ids:
        print(f"\n👤 chat_ids שנמצאו:")
        for chat_id in sorted(found_chat_ids):
            print(f"   {chat_id}")
    
    print(f"\n🔥 Hunt completed! עכשיו יש לנו עוד מקורות לחילוץ הודעות!")

if __name__ == "__main__":
    main() 