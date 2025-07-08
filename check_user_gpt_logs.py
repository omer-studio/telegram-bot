#!/usr/bin/env python3
"""
בדיקת לוגי GPT עבור משתמש ספציפי
"""
import psycopg2
import json
import os
from datetime import datetime

def analyze_user_gpt_logs(chat_id='111709341'):
    try:
        # טעינת קונפיגורציה
        config_path = 'etc/secrets/config.json'
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        print(f"🔍 מנתח לוגי GPT עבור משתמש {chat_id}...")
        connection = psycopg2.connect(db_url)
        cursor = connection.cursor()
        
        # בדיקת כמה רשומות יש למשתמש
        cursor.execute("SELECT COUNT(*) FROM gpt_calls_log WHERE chat_id = %s", (chat_id,))
        total_logs = cursor.fetchone()[0]
        print(f"📊 סך הכל רשומות GPT: {total_logs}")
        
        if total_logs == 0:
            print("❌ לא נמצאו רשומות GPT עבור המשתמש!")
            return
        
        # בדיקת סוגי הקריאות
        cursor.execute("""
            SELECT call_type, COUNT(*) 
            FROM gpt_calls_log 
            WHERE chat_id = %s 
            GROUP BY call_type 
            ORDER BY COUNT(*) DESC
        """, (chat_id,))
        
        call_types = cursor.fetchall()
        print(f"\n📋 סוגי קריאות GPT:")
        for call_type, count in call_types:
            print(f"   {call_type}: {count} קריאות")
        
        # בדיקת 10 הקריאות האחרונות עם פירוט
        cursor.execute("""
            SELECT 
                id, call_type, timestamp, tokens_input, tokens_output, 
                cost_usd, processing_time_seconds, 
                request_data::text, response_data::text
            FROM gpt_calls_log 
            WHERE chat_id = %s 
            ORDER BY timestamp DESC 
            LIMIT 10
        """, (chat_id,))
        
        recent_calls = cursor.fetchall()
        print(f"\n🔍 10 קריאות אחרונות:")
        
        for i, (log_id, call_type, ts, tokens_in, tokens_out, cost, proc_time, req_data, resp_data) in enumerate(recent_calls, 1):
            print(f"\n{i}. ID:{log_id} | {call_type} | {ts}")
            print(f"   טוקנים: {tokens_in}→{tokens_out} | עלות: ${cost:.4f} | זמן: {proc_time:.3f}s")
            
            # בדיקת request_data לאיתור היסטוריה
            try:
                if req_data and req_data != 'null':
                    request = json.loads(req_data)
                    messages = request.get('messages', [])
                    
                    # ספירת הודעות לפי role
                    user_msgs = len([m for m in messages if m.get('role') == 'user'])
                    assistant_msgs = len([m for m in messages if m.get('role') == 'assistant'])
                    system_msgs = len([m for m in messages if m.get('role') == 'system'])
                    
                    print(f"   📨 הודעות: system={system_msgs}, user={user_msgs}, assistant={assistant_msgs}")
                    
                    # אם יש רק הודעה אחת של user ואין assistant - זה אומר שלא נשלחה היסטוריה!
                    if user_msgs == 1 and assistant_msgs == 0:
                        print(f"   ⚠️ אין היסטוריה! רק הודעה נוכחית")
                    elif assistant_msgs > 0:
                        print(f"   ✅ יש היסטוריה")
                    
                    # הצגת מודל
                    model = request.get('model', 'לא ידוע')
                    print(f"   🤖 מודל: {model}")
                    
                else:
                    print(f"   ❌ אין נתוני request")
                    
            except json.JSONDecodeError:
                print(f"   ❌ שגיאה בפירוק JSON של request")
            except Exception as e:
                print(f"   ❌ שגיאה: {e}")
        
        # בדיקה כמה קריאות ללא היסטוריה (רק הודעה נוכחית)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM gpt_calls_log 
            WHERE chat_id = %s 
            AND call_type = 'A'
            AND request_data::jsonb -> 'messages' @> '[{"role": "user"}]'
            AND NOT (request_data::jsonb -> 'messages' @> '[{"role": "assistant"}]')
        """, (chat_id,))
        
        no_history_count = cursor.fetchone()[0]
        gpt_a_total = sum(count for call_type, count in call_types if call_type == 'A')
        
        print(f"\n📊 סיכום:")
        print(f"   📞 סך קריאות GPT-A: {gpt_a_total}")
        print(f"   ❌ קריאות ללא היסטוריה: {no_history_count}")
        if gpt_a_total > 0:
            percentage = (no_history_count / gpt_a_total) * 100
            print(f"   📈 אחוז ללא היסטוריה: {percentage:.1f}%")
            
            if percentage > 50:
                print(f"   🚨 בעיה סיסטמטית! יותר מ-50% מהקריאות ללא היסטוריה!")
            elif percentage > 20:
                print(f"   ⚠️ בעיה חמורה! יותר מ-20% מהקריאות ללא היסטוריה!")
            elif percentage > 5:
                print(f"   ⚠️ בעיה קלה - יותר מ-5% מהקריאות ללא היסטוריה")
            else:
                print(f"   ✅ נראה תקין - פחות מ-5% ללא היסטוריה")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_user_gpt_logs() 