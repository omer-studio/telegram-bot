#!/usr/bin/env python3
"""
בדיקת לוגי רנדר במסד הנתונים
"""
import psycopg2
import json
from datetime import datetime

def main():
    print('🔍 בודק טבלת לוגי רנדר במסד נתונים...')

    from config import get_config
    config = get_config()
    db_url = config.get('DATABASE_EXTERNAL_URL') or config.get('DATABASE_URL')

    connection = psycopg2.connect(db_url)
    cursor = connection.cursor()

    # בדיקה אילו טבלות יש
    print('📋 טבלות במסד הנתונים:')
    cursor.execute('''
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    ''')

    tables = cursor.fetchall()
    for table in tables:
        print(f'   📁 {table[0]}')

    # חיפוש טבלות שקשורות ללוגים
    log_tables = [t[0] for t in tables if 'log' in t[0].lower()]
    print(f'\n🔍 טבלות לוגים: {log_tables}')

    # בדיקת render_logs אם קיימת
    table_names = [t[0] for t in tables]
    
    if 'render_logs' in table_names:
        print('\n📊 בודק טבלת render_logs:')
        cursor.execute('SELECT COUNT(*) FROM render_logs')
        count = cursor.fetchone()[0]
        print(f'   📋 סה"כ רשומות: {count}')
        
        if count > 0:
            # לוגים אחרונים
            cursor.execute('''
                SELECT timestamp, message, level 
                FROM render_logs 
                ORDER BY timestamp DESC 
                LIMIT 20
            ''')
            
            recent_logs = cursor.fetchall()
            print('\n📝 20 לוגים אחרונים:')
            for ts, msg, level in recent_logs:
                msg_short = msg[:80] + '...' if len(msg) > 80 else msg
                print(f'   {ts} | {level} | {msg_short}')
                
            # חיפוש דיבאג
            cursor.execute('''
                SELECT timestamp, message, level 
                FROM render_logs 
                WHERE message LIKE '%DEBUG%' 
                   OR message LIKE '%מתחיל טעינת נתונים%'
                   OR message LIKE '%שגיאה בטעינת נתונים%'
                   OR message LIKE '%HISTORY_DEBUG%'
                ORDER BY timestamp DESC 
                LIMIT 10
            ''')
            
            debug_logs = cursor.fetchall()
            if debug_logs:
                print('\n🔧 הודעות דיבאג:')
                for ts, msg, level in debug_logs:
                    print(f'   {ts} | {level} | {msg}')
            else:
                print('\n⚠️ אין הודעות דיבאג בטבלת render_logs')
        else:
            print('\n📭 טבלת render_logs ריקה')
    else:
        print('\n❌ טבלת render_logs לא קיימת')
    
    # בדיקת טבלות לוגים אחרות
    if 'deployment_logs' in table_names:
        print('\n📊 בודק טבלת deployment_logs:')
        cursor.execute('SELECT COUNT(*) FROM deployment_logs')
        count = cursor.fetchone()[0]
        print(f'   📋 סה"כ רשומות: {count}')
        
        if count > 0:
            cursor.execute('''
                SELECT timestamp, message 
                FROM deployment_logs 
                ORDER BY timestamp DESC 
                LIMIT 10
            ''')
            
            recent_logs = cursor.fetchall()
            print('\n📝 10 לוגים אחרונים:')
            for ts, msg in recent_logs:
                msg_short = msg[:80] + '...' if len(msg) > 80 else msg
                print(f'   {ts} | {msg_short}')

    cursor.close()
    connection.close()

if __name__ == "__main__":
    main() 