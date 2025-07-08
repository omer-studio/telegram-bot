#!/usr/bin/env python3
import psycopg2
import json

def main():
    print('🔍 בדיקה מעמיקה של המצב האמיתי...')

    with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    db_url = config.get('DATABASE_EXTERNAL_URL') or config.get('DATABASE_URL')

    connection = psycopg2.connect(db_url)
    cursor = connection.cursor()

    # בדיקת סטטוס המשתמש
    print('🔐 סטטוס משתמש 111709341:')
    cursor.execute('''
        SELECT code_approve, code_try, name
        FROM user_profiles 
        WHERE chat_id = '111709341'
    ''')

    user_status = cursor.fetchone()
    if user_status:
        code_approve, code_try, name = user_status
        print(f'   ✅ קוד מאושר: {code_approve}')
        print(f'   🔢 ניסיונות: {code_try}')
        print(f'   👤 שם: {name}')
    else:
        print('❌ משתמש לא נמצא!')

    # הקריאה האחרונה למשתמש - 4.8M טוקנים!
    print('\n🔍 הקריאת GPT-A האחרונה (4.8M טוקנים!!):')
    cursor.execute('''
        SELECT request_data, response_data, timestamp
        FROM gpt_calls_log 
        WHERE chat_id = '111709341' AND call_type = 'A'
        ORDER BY timestamp DESC
        LIMIT 1
    ''')

    gpt_call = cursor.fetchone()
    if gpt_call:
        request_data, response_data, ts = gpt_call
        print(f'   📅 זמן: {ts}')
        
        if request_data:
            try:
                # הנתונים יכולים להיות dict או JSON string
                if isinstance(request_data, dict):
                    req = request_data
                else:
                    req = json.loads(request_data)
                messages = req.get('messages', [])
                system_msgs = len([m for m in messages if m.get('role') == 'system'])
                user_msgs = len([m for m in messages if m.get('role') == 'user'])
                assistant_msgs = len([m for m in messages if m.get('role') == 'assistant'])
                
                print(f'   📨 בקשה: system={system_msgs}, user={user_msgs}, assistant={assistant_msgs}')
                
                # זה המפתח! אם יש assistant messages, יש היסטוריה!
                if assistant_msgs > 0:
                    print(f'   ✅ יש {assistant_msgs} הודעות היסטוריה!')
                    print('   🎉 הבעיה נפתרה! יש היסטוריה!')
                else:
                    print(f'   ❌ אין הודעות היסטוריה!')
                    
                # בואו נראה את החלק האחרון מההודעות
                print(f'\n   📋 דוגמאות הודעות (מתוך {len(messages)}):')
                for i, msg in enumerate(messages[-3:], len(messages)-2):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')[:100]
                    print(f'     {i}. {role}: "{content}..."')
                    
            except Exception as e:
                print(f'   ❌ שגיאה בניתוח בקשה: {e}')
        
        if response_data:
            try:
                # הנתונים יכולים להיות dict או JSON string
                if isinstance(response_data, dict):
                    resp = response_data
                else:
                    resp = json.loads(response_data)
                content = resp.get('choices', [{}])[0].get('message', {}).get('content', '')
                print(f'\n   🤖 תשובה: "{content[:100]}..."')
            except Exception as e:
                print(f'   ❌ שגיאה בתשובה: {e}')

    # למה הדיבאג שלי לא עובד?
    print('\n🔧 בדיקת מערכת הדיבאג:')
    cursor.execute('''
        SELECT COUNT(*) 
        FROM chat_messages 
        WHERE chat_id LIKE 'DEBUG_%' OR chat_id LIKE 'ERROR_%'
    ''')

    debug_count = cursor.fetchone()[0]
    print(f'   📊 רשומות דיבאג כרגע: {debug_count}')

    if debug_count == 0:
        print('   💡 הדיבאג לא הגיע לטבלה')
        print('   🤔 יתכן שהקוד שלי לא רץ או שיש שגיאה בשמירה')
    
    # בדיקת עדכונים אחרונים בטבלת chat_messages
    print('\n📱 עדכונים אחרונים בטבלת chat_messages:')
    cursor.execute('''
        SELECT chat_id, user_msg, gpt_response, timestamp
        FROM chat_messages 
        WHERE timestamp >= NOW() - INTERVAL '30 minutes'
        ORDER BY timestamp DESC
        LIMIT 10
    ''')
    
    recent = cursor.fetchall()
    for chat_id, user_msg, gpt_response, ts in recent:
        user_text = (user_msg or "None")[:30]
        gpt_text = (gpt_response or "None")[:30]
        print(f'   {ts} | {chat_id} | U:"{user_text}" | G:"{gpt_text}"')

    cursor.close()
    connection.close()

if __name__ == "__main__":
    main() 