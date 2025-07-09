#!/usr/bin/env python3
"""
בדיקת רשומות דיבאג ופעילות אחרונה במסד נתונים
"""
import psycopg2
import json
from datetime import datetime

def main():
    print('🔍 בדיקת פעילות ודיבאג במסד הנתונים...')

    from config import get_config
    config = get_config()
    db_url = config.get('DATABASE_EXTERNAL_URL') or config.get('DATABASE_URL')

    connection = psycopg2.connect(db_url)
    cursor = connection.cursor()

    # חיפוש רשומות דיבאג
    print('🔧 חיפוש רשומות DEBUG ו-ERROR:')
    cursor.execute('''
        SELECT chat_id, user_msg, gpt_response, timestamp
        FROM chat_messages 
        WHERE chat_id LIKE 'DEBUG_%' OR chat_id LIKE 'ERROR_%'
        ORDER BY timestamp DESC
        LIMIT 20
    ''')

    debug_records = cursor.fetchall()
    if debug_records:
        print(f'📋 נמצאו {len(debug_records)} רשומות דיבאג!')
        for chat_id, user_msg, gpt_response, ts in debug_records:
            print(f'🎯 {ts} | {chat_id}')
            print(f'   💬 {user_msg}')
            gpt_text = gpt_response or "None"
            print(f'   🤖 {gpt_text[:50]}...' if len(gpt_text) > 50 else f'   🤖 {gpt_text}')
            print('-' * 50)
    else:
        print('⚠️ לא נמצאו רשומות דיבאג עדיין')

    # פעילות המשתמש 111709341 ב-30 דקות האחרונות
    print('\n📱 פעילות משתמש 111709341 ב-30 דקות האחרונות:')
    cursor.execute('''
        SELECT user_msg, gpt_response, timestamp
        FROM chat_messages 
        WHERE chat_id = '111709341'
        AND timestamp >= NOW() - INTERVAL '30 minutes'
        ORDER BY timestamp DESC
    ''')

    recent_111 = cursor.fetchall()
    if recent_111:
        print(f'📋 {len(recent_111)} הודעות:')
        for user_msg, gpt_response, ts in recent_111:
            print(f'   📅 {ts}')
            user_text = user_msg or "None"
            gpt_text = gpt_response or "None"
            print(f'   👤 "{user_text}"')
            print(f'   🤖 "{gpt_text[:50]}..." ' if gpt_text != "None" and len(gpt_text) > 50 else f'   🤖 "{gpt_text}"')
            print('-' * 30)
    else:
        print('📭 אין פעילות ב-30 דקות האחרונות')

    # פעילות כללית אחרונה
    print('\n🌍 פעילות אחרונה כללית:')
    cursor.execute('''
        SELECT chat_id, user_msg, timestamp
        FROM chat_messages 
        WHERE timestamp >= NOW() - INTERVAL '30 minutes'
        ORDER BY timestamp DESC
        LIMIT 15
    ''')

    general_recent = cursor.fetchall()
    if general_recent:
        print(f'📋 {len(general_recent)} הודעות ב-30 דקות האחרונות:')
        for chat_id, user_msg, ts in general_recent:
            user_text = user_msg or "None"
            print(f'   {ts} | {chat_id} | "{user_text}"')
    else:
        print('📭 אין פעילות ב-30 דקות האחרונות')

    # סטטוס פריסה - בדיקת הודעות מהשעה האחרונה
    print('\n🚀 בדיקת סטטוס פריסה:')
    cursor.execute('''
        SELECT COUNT(*) as total_messages,
               COUNT(CASE WHEN gpt_response IS NOT NULL THEN 1 END) as with_gpt_response,
               MAX(timestamp) as latest_message
        FROM chat_messages 
        WHERE timestamp >= NOW() - INTERVAL '1 hour'
    ''')
    
    deploy_status = cursor.fetchone()
    if deploy_status:
        total, with_gpt, latest = deploy_status
        print(f'   📊 הודעות בשעה האחרונה: {total}')
        print(f'   🤖 עם תשובת GPT: {with_gpt}')
        print(f'   📅 הודעה אחרונה: {latest}')
        
        if total == 0:
            print('   ⚠️ אין פעילות - יתכן שהפריסה לא הסתיימה')
        elif with_gpt == 0:
            print('   🚨 אין תשובות GPT - יתכן שיש בעיה')
        else:
            print('   ✅ יש פעילות תקינה')

    cursor.close()
    connection.close()

if __name__ == "__main__":
    main() 