#!/usr/bin/env python3
"""
גישה ללוגי רנדר דרך SSH לחיפוש הודעות דיבאג
"""
import subprocess
import time
from datetime import datetime
from simple_config import TimeoutConfig

def check_ssh_logs():
    """חיפוש הודעות דיבאג בלוגי רנדר דרך SSH"""
    
    print('🔍 מתחבר ללוגי רנדר דרך SSH...')
    
    ssh_host = "srv-d0r895be5dus73fmsc8g@ssh.frankfurt.render.com"
    
    # פקודות לבדיקת לוגים שונים
    log_commands = [
        # לוגים של השירות
        "tail -n 50 /var/log/render/service.log 2>/dev/null || echo 'service.log not found'",
        "tail -n 50 /var/log/render/python.log 2>/dev/null || echo 'python.log not found'",
        "tail -n 50 /var/log/render/error.log 2>/dev/null || echo 'error.log not found'",
        
        # לוגי stdout/stderr
        "tail -n 50 /var/log/stdout.log 2>/dev/null || echo 'stdout.log not found'",
        "tail -n 50 /var/log/stderr.log 2>/dev/null || echo 'stderr.log not found'",
        
        # חיפוש כללי אחר קבצי לוג
        "find /var/log -name '*.log' -type f 2>/dev/null | head -10",
        
        # בדיקת תהליכים פעילים
        "ps aux | grep python",
        
        # חיפוש אחר DEBUG בכל הלוגים
        "grep -r 'DEBUG' /var/log/ 2>/dev/null | tail -20 || echo 'No DEBUG found in logs'",
        
        # חיפוש אחר chat_id בלוגים
        "grep -r 'chat_id' /var/log/ 2>/dev/null | tail -10 || echo 'No chat_id found in logs'",
        
        # חיפוש אחר הודעות דיבאג ספציפיות
        "grep -r 'HISTORY_DEBUG' /var/log/ 2>/dev/null | tail -10 || echo 'No HISTORY_DEBUG found'",
        "grep -r 'מתחיל טעינת נתונים' /var/log/ 2>/dev/null | tail -10 || echo 'No Hebrew debug found'"
    ]
    
    for i, cmd in enumerate(log_commands, 1):
        print(f'\n📋 בדיקה {i}: {cmd[:60]}...')
        
        try:
            # הרצת פקודת SSH
            full_cmd = f'ssh -o ConnectTimeout={TimeoutConfig.SSH_CONNECTION_TIMEOUT} -o StrictHostKeyChecking=no {ssh_host} "{cmd}"'
            
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TimeoutConfig.SSH_COMMAND_TIMEOUT
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    print(f'✅ תוצאה:')
                    # הצגת השורות הראשונות
                    lines = output.split('\n')
                    for line in lines[:20]:  # רק 20 שורות ראשונות
                        print(f'   {line}')
                    if len(lines) > 20:
                        print(f'   ... ועוד {len(lines) - 20} שורות')
                else:
                    print('📭 אין תוצאות')
            else:
                error = result.stderr.strip()
                print(f'❌ שגיאה: {error}')
                
        except subprocess.TimeoutExpired:
            print('⏰ הפקודה נגמר לה הזמן')
        except Exception as e:
            print(f'❌ שגיאה בהרצת פקודה: {e}')
        
        # השהיה קצרה בין פקודות
        time.sleep(1)

def check_recent_activity():
    """בדיקת פעילות אחרונה ללוגים"""
    
    print('\n🕐 בדיקת פעילות אחרונה...')
    
    ssh_host = "srv-d0r895be5dus73fmsc8g@ssh.frankfurt.render.com"
    
    # פקודות לבדיקת פעילות אחרונה
    activity_commands = [
        # קבצים שהשתנו ב-10 דקות האחרונות
        "find /var/log -type f -mmin -10 2>/dev/null | head -10",
        
        # תוכן חדש ב-5 דקות האחרונות
        "find /var/log -name '*.log' -type f -mmin -5 -exec tail -20 {} \\; 2>/dev/null | grep -v '^$' | tail -30",
        
        # בדיקת uptime
        "uptime",
        
        # בדיקת זמן נוכחי
        "date"
    ]
    
    for cmd in activity_commands:
        print(f'\n🔍 {cmd}')
        
        try:
            full_cmd = f'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no {ssh_host} "{cmd}"'
            
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TimeoutConfig.SSH_COMMAND_TIMEOUT
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    print(f'📋 {output}')
                else:
                    print('📭 אין תוצאות')
            else:
                print(f'❌ {result.stderr.strip()}')
                
        except Exception as e:
            print(f'❌ שגיאה: {e}')

if __name__ == "__main__":
    print('🚀 SSH לוגים צ\'קר - רנדר')
    print('=' * 50)
    
    try:
        check_ssh_logs()
        check_recent_activity()
        
        print('\n' + '=' * 50)
        print('✅ בדיקה הושלמה!')
        print('')
        print('💡 טיפים:')
        print('   • אם לא נמצאו הודעות דיבאג, יתכן שהפריסה עדיין לא הסתיימה')
        print('   • נסה לשלוח הודעה מהמשתמש ואז הרץ שוב')
        print('   • בדוק גם במסד הנתונים עם: python -c "from db import ..."')
        
    except KeyboardInterrupt:
        print('\n👋 יציאה...')
    except Exception as e:
        print(f'\n❌ שגיאה כללית: {e}') 