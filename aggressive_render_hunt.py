#!/usr/bin/env python3
"""
🚨 Aggressive Render Hunt - ציד אגרסיבי אחרי הודעות ברנדר
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

def direct_ssh_hunt():
    """חיפוש ישיר ומהיר ב-SSH"""
    print("🚀 === חיפוש ישיר ב-SSH ===")
    
    ssh_host = "srv-d0r895be5dus73fmsc8g@ssh.frankfurt.render.com"
    
    # פקודות ממוקדות לחיפוש הודעות
    focused_commands = [
        # חיפוש המילה chat_id ישירות
        "grep -r 'chat_id' /var/log/ 2>/dev/null | grep -v 'Binary file' | head -20",
        
        # חיפוש user_msg
        "grep -r 'user_msg' /var/log/ 2>/dev/null | grep -v 'Binary file' | head -20", 
        
        # חיפוש הודעות עבריות
        "grep -r 'התקבלה הודעה' /var/log/ 2>/dev/null | head -20",
        
        # חיפוש message_handler 
        "grep -r 'message_handler' /var/log/ 2>/dev/null | head -20",
        
        # חיפוש prints של user
        "grep -r 'user:' /var/log/ 2>/dev/null | head -20",
        
        # חיפוש emoji של הודעות
        "grep -r '📩' /var/log/ 2>/dev/null | head -20",
        
        # לוגים של היום
        "find /var/log -name '*.log' -newermt '2025-07-11' -exec tail -50 {} \\; 2>/dev/null | grep -E '(chat_id|user_msg|התקבלה)' | head -30",
        
        # stdout לוגים
        "tail -100 /var/log/stdout.log 2>/dev/null | grep -E '(chat_id|user_msg|התקבלה|message)' | head -20",
        
        # תיקיית app אם יש
        "find /opt/render -name '*.log' 2>/dev/null | head -10",
        
        # לוגי python אם יש
        "tail -50 /var/log/python*.log 2>/dev/null | grep -E '(chat_id|user_msg)' | head -20"
    ]
    
    found_messages = []
    
    for i, cmd in enumerate(focused_commands, 1):
        print(f"\n🔍 פקודה {i}: {cmd[:50]}...")
        
        try:
                    full_cmd = f'ssh -o ConnectTimeout={TimeoutConfig.SSH_CONNECTION_TIMEOUT} -o StrictHostKeyChecking=no {ssh_host} "{cmd}"'
        
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TimeoutConfig.SSH_COMMAND_TIMEOUT,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout.strip()
                lines = output.split('\n')
                
                print(f"✅ נמצאו {len(lines)} שורות:")
                
                for line in lines[:10]:  # רק 10 ראשונות
                    if line.strip():
                        print(f"   📝 {line[:100]}...")
                        
                        # חילוץ chat_id אם יש
                        chat_id_match = re.search(r'chat_id[=:\s]*([0-9]+)', line)
                        if chat_id_match:
                            found_messages.append({
                                'source': f'SSH_cmd_{i}',
                                'chat_id': chat_id_match.group(1),
                                'content': line.strip(),
                                'command': cmd
                            })
                
                if len(lines) > 10:
                    print(f"   ... ועוד {len(lines) - 10} שורות")
                    
                # עיבוד כל השורות (לא רק תצוגה)
                for line in lines:
                    if line.strip() and any(keyword in line for keyword in ['chat_id', 'user_msg', 'התקבלה']):
                        chat_id_match = re.search(r'chat_id[=:\s]*([0-9]+)', line)
                        if chat_id_match:
                            found_messages.append({
                                'source': f'SSH_cmd_{i}',
                                'chat_id': chat_id_match.group(1),
                                'content': line.strip(),
                                'command': cmd
                            })
            else:
                print("📭 אין תוצאות")
                
        except Exception as e:
            print(f"❌ שגיאה: {e}")
    
    return found_messages

def hunt_render_api_logs():
    """חיפוש ממוקד בלוגי API רנדר"""
    print("\n🌐 === חיפוש ממוקד בAPI רנדר ===")
    
    api_key = config.get('RENDER_API_KEY')
    service_id = config.get('RENDER_SERVICE_ID')
    
    if not api_key or not service_id:
        print("❌ חסרים נתוני API")
        return []
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }
    
    found_messages = []
    
    # חיפוש לוגים מהשעות האחרונות
    time_periods = [
        ('1 hour', 1),
        ('6 hours', 6), 
        ('24 hours', 24),
        ('3 days', 72)
    ]
    
    for period_name, hours_back in time_periods:
        print(f"\n🔍 חיפוש ב-{period_name} אחרונות...")
        
        try:
            start_time = datetime.now() - timedelta(hours=hours_back)
            
            logs_url = f"https://api.render.com/v1/services/{service_id}/logs"
            
            params = {
                'startTime': start_time.isoformat() + 'Z',
                'limit': 1000
            }
            
            response = requests.get(logs_url, headers=headers, params=params, timeout=TimeoutConfig.RENDER_LOGS_TIMEOUT)
            
            if response.status_code == 200:
                logs_data = response.json()
                logs = logs_data.get('logs', [])
                
                print(f"📋 נמצאו {len(logs)} לוגים")
                
                relevant_logs = []
                for log_entry in logs:
                    message = log_entry.get('message', '')
                    timestamp = log_entry.get('timestamp', '')
                    
                    # חיפוש מילות מפתח
                    if any(keyword in message for keyword in [
                        'chat_id', 'user_msg', 'התקבלה הודעה', 'message_handler', 
                        '📩', 'user_message', 'bot_reply', 'telegram'
                    ]):
                        relevant_logs.append({
                            'timestamp': timestamp,
                            'message': message,
                            'source': f'API_{period_name.replace(" ", "_")}'
                        })
                        
                        # חילוץ chat_id
                        chat_id_match = re.search(r'chat_id[=:\s]*([0-9]+)', message)
                        if chat_id_match:
                            found_messages.append({
                                'source': f'API_{period_name}',
                                'chat_id': chat_id_match.group(1),
                                'content': message,
                                'timestamp': timestamp
                            })
                
                print(f"🎯 רלוונטיים: {len(relevant_logs)}")
                
                # הצגת דוגמאות
                for log in relevant_logs[:5]:
                    print(f"   📝 {log['timestamp']}: {log['message'][:80]}...")
                
            else:
                print(f"❌ שגיאה: {response.status_code}")
                if response.status_code == 404:
                    print("   💡 אולי צריך מסלול API אחר")
                    break  # לא מצליח - עוצרים
                
        except Exception as e:
            print(f"❌ שגיאה ב-{period_name}: {e}")
    
    return found_messages

def hunt_deployment_logs():
    """חיפוש ממוקד בטבלת deployment_logs"""
    print("\n💾 === חיפוש ממוקד בטבלת deployment_logs ===")
    
    try:
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # בדיקה מתקדמת יותר
        search_patterns = [
            "message LIKE '%chat_id%'",
            "message LIKE '%user_msg%'", 
            "message LIKE '%התקבלה הודעה%'",
            "message LIKE '%message_handler%'",
            "message LIKE '%📩%'",
            "message LIKE '%telegram%'",
            "message LIKE '%user:%'",
            "message LIKE '%bot_reply%'"
        ]
        
        all_found = []
        
        for i, pattern in enumerate(search_patterns, 1):
            print(f"\n🔍 תבנית {i}: {pattern[:30]}...")
            
            try:
                cur.execute(f"""
                    SELECT 
                        timestamp,
                        message,
                        log_level,
                        session_id,
                        user_id
                    FROM deployment_logs 
                    WHERE timestamp >= NOW() - INTERVAL '7 days'
                    AND {pattern}
                    ORDER BY timestamp DESC
                    LIMIT 50
                """)
                
                results = cur.fetchall()
                
                print(f"📋 נמצאו {len(results)} תוצאות")
                
                for timestamp, message, log_level, session_id, user_id in results:
                    # חילוץ chat_id
                    chat_id_match = re.search(r'chat_id[=:\s]*([0-9]+)', str(message))
                    
                    result_data = {
                        'source': f'DEPLOYMENT_LOGS_pattern_{i}',
                        'timestamp': timestamp.isoformat(),
                        'message': str(message),
                        'log_level': log_level,
                        'session_id': session_id,
                        'user_id': user_id
                    }
                    
                    if chat_id_match:
                        result_data['chat_id'] = chat_id_match.group(1)
                    
                    all_found.append(result_data)
                
                # הצגת דוגמאות
                for result in results[:3]:
                    print(f"   📝 {result[0]}: {str(result[1])[:60]}...")
                    
            except Exception as e:
                print(f"❌ שגיאה בתבנית {i}: {e}")
        
        cur.close()
        conn.close()
        
        print(f"\n📊 סה\"כ נמצאו {len(all_found)} רשומות רלוונטיות")
        
        return all_found
        
    except Exception as e:
        print(f"❌ שגיאה כללית במסד: {e}")
        return []

def analyze_and_extract_new_messages(all_findings):
    """ניתוח הממצאים וחילוץ הודעות חדשות"""
    print(f"\n🔬 === ניתוח {len(all_findings)} ממצאים ===")
    
    if not all_findings:
        print("❌ אין ממצאים לניתוח")
        return
    
    # חילוץ chat_ids
    found_chat_ids = set()
    message_candidates = []
    
    for finding in all_findings:
        # חילוץ chat_id
        if 'chat_id' in finding:
            found_chat_ids.add(finding['chat_id'])
        
        # חיפוש chat_id בתוכן
        content = finding.get('content', '') or finding.get('message', '')
        chat_id_matches = re.findall(r'chat_id[=:\s]*([0-9]+)', str(content))
        found_chat_ids.update(chat_id_matches)
        
        # חיפוש הודעות משתמש
        if any(keyword in str(content).lower() for keyword in [
            'user_msg', 'התקבלה הודעה', 'user:', 'telegram'
        ]):
            message_candidates.append(finding)
    
    print(f"\n👥 chat_ids שנמצאו: {len(found_chat_ids)}")
    for chat_id in sorted(found_chat_ids):
        print(f"   👤 {chat_id}")
    
    print(f"\n💬 מועמדי הודעות: {len(message_candidates)}")
    
    # קיבוץ לפי מקור
    by_source = {}
    for finding in all_findings:
        source = finding.get('source', 'unknown')
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(finding)
    
    print(f"\n📈 פילוח לפי מקור:")
    for source, items in by_source.items():
        print(f"   📋 {source}: {len(items)} פריטים")
    
    # שמירת התוצאות
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"aggressive_render_hunt_{timestamp}.json"
    
    results = {
        'hunt_time': datetime.now().isoformat(),
        'total_findings': len(all_findings),
        'found_chat_ids': list(found_chat_ids),
        'message_candidates_count': len(message_candidates),
        'sources_breakdown': {k: len(v) for k, v in by_source.items()},
        'all_findings': all_findings
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 תוצאות נשמרו ב: {filename}")
    
    return found_chat_ids, message_candidates

def main():
    """הפונקציה הראשית"""
    print("🔥 === Aggressive Render Hunt ===")
    print(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)
    
    all_findings = []
    
    # 1. חיפוש SSH
    print("🚀 שלב 1: חיפוש SSH")
    try:
        ssh_findings = direct_ssh_hunt()
        all_findings.extend(ssh_findings)
        print(f"✅ SSH: {len(ssh_findings)} ממצאים")
    except Exception as e:
        print(f"❌ SSH נכשל: {e}")
    
    # 2. חיפוש API
    print("\n🚀 שלב 2: חיפוש API")
    try:
        api_findings = hunt_render_api_logs()
        all_findings.extend(api_findings)
        print(f"✅ API: {len(api_findings)} ממצאים")
    except Exception as e:
        print(f"❌ API נכשל: {e}")
    
    # 3. חיפוש deployment_logs
    print("\n🚀 שלב 3: חיפוש deployment_logs")
    try:
        db_findings = hunt_deployment_logs()
        all_findings.extend(db_findings)
        print(f"✅ DB: {len(db_findings)} ממצאים")
    except Exception as e:
        print(f"❌ DB נכשל: {e}")
    
    # 4. ניתוח תוצאות
    found_chat_ids, message_candidates = analyze_and_extract_new_messages(all_findings)
    
    print(f"\n🎯 === תוצאות סופיות ===")
    print(f"📊 סה\"כ ממצאים: {len(all_findings)}")
    print(f"👥 chat_ids ייחודיים: {len(found_chat_ids) if found_chat_ids else 0}")
    print(f"💬 מועמדי הודעות: {len(message_candidates) if message_candidates else 0}")
    
    if found_chat_ids:
        print(f"\n🔥 המטרה: לחלץ הודעות נוספות מהמשתמשים הנמצאים!")

if __name__ == "__main__":
    main() 