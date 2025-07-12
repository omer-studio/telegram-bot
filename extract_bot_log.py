#!/usr/bin/env python3
"""
🎯 חילוץ תוכן מלוג הבוט ברנדר
הלוג נמצא ב: /opt/render/project/src/data/bot.log
"""

import subprocess
import re
import json
from datetime import datetime
from simple_config import TimeoutConfig

def extract_bot_log():
    """חילוץ תוכן מלוג הבוט"""
    print("🎯 === חילוץ לוג הבוט מרנדר ===")
    
    ssh_host = "srv-d0r895be5dus73fmsc8g@ssh.frankfurt.render.com"
    log_path = "/opt/render/project/src/data/bot.log"
    
    # פקודות לקריאת הלוג
    read_commands = [
        # גודל הקובץ
        f"ls -lh {log_path}",
        
        # 100 שורות אחרונות
        f"tail -n 100 {log_path}",
        
        # 500 שורות אחרונות
        f"tail -n 500 {log_path}",
        
        # חיפוש chat_id בקובץ
        f"grep 'chat_id' {log_path} | tail -50",
        
        # חיפוש user_msg
        f"grep 'user_msg' {log_path} | tail -50",
        
        # חיפוש הודעות עבריות
        f"grep 'התקבלה הודעה' {log_path} | tail -50",
        
        # חיפוש message_handler
        f"grep 'message_handler' {log_path} | tail -50",
        
        # חיפוש today's date
        f"grep '2025-07-11' {log_path} | tail -50",
        
        # חיפוש yesterday  
        f"grep '2025-07-10' {log_path} | tail -50",
        
        # ספירת שורות
        f"wc -l {log_path}"
    ]
    
    all_extracted = []
    
    for i, cmd in enumerate(read_commands, 1):
        print(f"\n📋 פקודה {i}: {cmd}")
        
        try:
            full_cmd = f'ssh -o ConnectTimeout={TimeoutConfig.SSH_CONNECTION_TIMEOUT} -o StrictHostKeyChecking=no {ssh_host} "{cmd}"'
            
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TimeoutConfig.SUBPROCESS_TIMEOUT,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout.strip()
                
                if "No such file" in output:
                    print("❌ הקובץ לא נמצא")
                    continue
                
                lines = output.split('\n')
                print(f"✅ נמצאו {len(lines)} שורות")
                
                # הצגת השורות הראשונות
                for j, line in enumerate(lines[:15], 1):
                    if line.strip():
                        print(f"   {j:2d}. {line[:120]}...")
                
                if len(lines) > 15:
                    print(f"   ... ועוד {len(lines) - 15} שורות")
                
                # שמירת התוכן לעיבוד
                all_extracted.append({
                    'command': cmd,
                    'content': output,
                    'lines_count': len(lines)
                })
                
                # חילוץ הודעות ספציפיות
                if 'chat_id' in cmd or 'user_msg' in cmd or 'התקבלה' in cmd:
                    extract_messages_from_output(output, f"cmd_{i}")
                
            else:
                print("📭 אין תוצאות או שגיאה")
                if result.stderr.strip():
                    print(f"   שגיאה: {result.stderr.strip()}")
                
        except Exception as e:
            print(f"❌ שגיאה: {e}")
    
    return all_extracted

def extract_messages_from_output(output, source):
    """חילוץ הודעות מתוכן לוג"""
    print(f"\n🔍 מחלץ הודעות מ-{source}...")
    
    found_chat_ids = set()
    found_messages = []
    
    lines = output.split('\n')
    
    for line in lines:
        if not line.strip():
            continue
            
        # חיפוש chat_id
        chat_id_matches = re.findall(r'chat_id[=:\s]*([0-9]+)', line)
        found_chat_ids.update(chat_id_matches)
        
        # חיפוש הודעות משתמש
        if any(keyword in line for keyword in [
            'user_msg', 'התקבלה הודעה', 'message_handler', 'user:', 'telegram'
        ]):
            found_messages.append({
                'source': source,
                'content': line.strip(),
                'chat_ids': list(set(re.findall(r'chat_id[=:\s]*([0-9]+)', line)))
            })
    
    if found_chat_ids:
        print(f"👥 נמצאו chat_ids: {sorted(found_chat_ids)}")
    
    if found_messages:
        print(f"💬 נמצאו {len(found_messages)} הודעות פוטנציאליות")
        for msg in found_messages[:5]:  # 5 ראשונות
            print(f"   📝 {msg['content'][:80]}...")
    
    return found_chat_ids, found_messages

def check_other_logs():
    """בדיקת לוגים נוספים שעלולים להיות"""
    print("\n🔍 === בדיקת לוגים נוספים ===")
    
    ssh_host = "srv-d0r895be5dus73fmsc8g@ssh.frankfurt.render.com"
    
    # בדיקת תיקיות נוספות
    explore_commands = [
        # תיקיית data
        "ls -la /opt/render/project/src/data/",
        
        # חיפוש קבצי לוג נוספים
        "find /opt/render/project -name '*.log' -type f",
        
        # חיפוש קבצי json
        "find /opt/render/project -name '*.json' -type f | head -10",
        
        # חיפוש קבצי txt
        "find /opt/render/project -name '*.txt' -type f | head -10",
        
        # תיקיות logs אחרות
        "find /opt/render -name 'logs' -type d",
        
        # קבצים שהשתנו היום
        "find /opt/render/project -type f -newermt '2025-07-11' | head -20"
    ]
    
    for i, cmd in enumerate(explore_commands, 1):
        print(f"\n📋 בדיקה {i}: {cmd}")
        
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
                
                print(f"✅ נמצאו {len(lines)} פריטים:")
                for line in lines[:10]:
                    print(f"   📄 {line}")
                
                if len(lines) > 10:
                    print(f"   ... ועוד {len(lines) - 10}")
            else:
                print("📭 אין תוצאות")
                
        except Exception as e:
            print(f"❌ שגיאה: {e}")

def main():
    """הפונקציה הראשית"""
    print("🎯 === Bot Log Extractor ===")
    print(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 50)
    
    # 1. חילוץ לוג הבוט
    extracted_data = extract_bot_log()
    
    # 2. בדיקת לוגים נוספים
    check_other_logs()
    
    # 3. שמירת תוצאות
    if extracted_data:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"bot_log_extraction_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'extraction_time': datetime.now().isoformat(),
                'extracted_data': extracted_data
            }, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 נתונים נשמרו ב: {filename}")
    
    print(f"\n🎯 חילוץ לוג הבוט הושלם!")

if __name__ == "__main__":
    main() 