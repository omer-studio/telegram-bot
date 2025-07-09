#!/usr/bin/env python3
"""
חיפוש הודעות דיבאג בטבלת deployment_logs
"""
import psycopg2
import json
from datetime import datetime

def main():
    print('🔍 חיפוש דיבאג בטבלת deployment_logs...')

    from config import get_config
    config = get_config()
    db_url = config.get('DATABASE_EXTERNAL_URL') or config.get('DATABASE_URL')

    connection = psycopg2.connect(db_url)
    cursor = connection.cursor()

    # בדיקת מבנה הטבלה
    print('📋 מבנה טבלת deployment_logs:')
    cursor.execute('''
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'deployment_logs'
        ORDER BY ordinal_position
    ''')
    
    columns = cursor.fetchall()
    for col_name, data_type in columns:
        print(f'   📄 {col_name}: {data_type}')

    # חיפוש כל הרשומות מהשעה האחרונה
    print('\n📊 כל הלוגים מהשעה האחרונה:')
    cursor.execute('''
        SELECT timestamp, session_id, message, log_level
        FROM deployment_logs 
        WHERE timestamp >= NOW() - INTERVAL '1 hour'
        ORDER BY timestamp DESC
    ''')
    
    recent_logs = cursor.fetchall()
    print(f'   📋 נמצאו {len(recent_logs)} לוגים')
    
    for ts, session_id, message, level in recent_logs:
        print(f'   {ts} | {session_id} | {level} | {message[:60]}...')

    # חיפוש דיבאג ספציפי
    debug_keywords = [
        'DEBUG',
        'HISTORY_DEBUG', 
        'מתחיל טעינת נתונים',
        'שגיאה בטעינת נתונים',
        'Exception.*data_err',
        'get_chat_history_messages_fast',
        'get_user_summary_fast'
    ]
    
    print('\n🔧 חיפוש הודעות דיבאג:')
    for keyword in debug_keywords:
        cursor.execute('''
            SELECT timestamp, session_id, message, log_level
            FROM deployment_logs 
            WHERE message LIKE %s
            AND timestamp >= NOW() - INTERVAL '2 hours'
            ORDER BY timestamp DESC
            LIMIT 5
        ''', (f'%{keyword}%',))
        
        debug_logs = cursor.fetchall()
        if debug_logs:
            print(f'\n🎯 נמצא "{keyword}":')
            for ts, session_id, message, level in debug_logs:
                print(f'   {ts} | {session_id} | {level}')
                print(f'   💬 {message}')
                print('-' * 50)

    # בדיקת שגיאות אחרונות
    print('\n🚨 שגיאות אחרונות (אם יש):')
    cursor.execute('''
        SELECT timestamp, session_id, message, error_type
        FROM deployment_logs 
        WHERE log_level = 'ERROR'
        AND timestamp >= NOW() - INTERVAL '2 hours'
        ORDER BY timestamp DESC
        LIMIT 10
    ''')
    
    errors = cursor.fetchall()
    if errors:
        print(f'   ❌ נמצאו {len(errors)} שגיאות:')
        for ts, session_id, message, error_type in errors:
            print(f'   {ts} | {session_id} | {error_type}')
            print(f'   💬 {message}')
            print('-' * 30)
    else:
        print('   ✅ אין שגיאות!')

    cursor.close()
    connection.close()

if __name__ == "__main__":
    main() 