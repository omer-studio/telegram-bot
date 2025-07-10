#!/usr/bin/env python3
"""
חקירת הבקשה הספציפית ל-GPT שגרמה לתשובה המוזרה
"""

import sys
sys.path.append('.')
import json
from db_tool import run_query

def main():
    print("🔍 חקירת הבקשה ל-GPT שגרמה לתשובה המוזרה...")
    
    # בדיקת הקריאה האחרונה של המשתמש 111709341 עם הודעת "הסתדר?"
    query = """
    SELECT 
        timestamp,
        call_type,
        chat_id,
        request_data,
        response_data
    FROM gpt_calls_log 
    WHERE chat_id = '111709341' 
    AND call_type = 'A'
    ORDER BY timestamp DESC 
    LIMIT 3
    """
    
    results = run_query(query)
    
    if not results:
        print("❌ לא נמצאו תוצאות")
        return
    
    print(f"📋 נמצאו {len(results)} קריאות GPT:\n")
    
    for i, result in enumerate(results, 1):
        print(f"📅 {i}. {result['timestamp']}")
        print(f"🎯 Call Type: {result['call_type']}")
        print(f"👤 Chat ID: {result['chat_id']}")
        
        request_data = result['request_data']
        response_data = result['response_data']
        
        if isinstance(request_data, dict):
            messages = request_data.get('messages', [])
            model = request_data.get('model', 'Unknown')
            
            print(f"🤖 Model: {model}")
            print(f"📝 Total messages: {len(messages)}")
            
            # פירוט הודעות לפי סוג
            system_messages = [msg for msg in messages if msg.get('role') == 'system']
            user_messages = [msg for msg in messages if msg.get('role') == 'user']
            assistant_messages = [msg for msg in messages if msg.get('role') == 'assistant']
            
            print(f"⚙️ System messages: {len(system_messages)}")
            print(f"👤 User messages: {len(user_messages)}")
            print(f"🤖 Assistant messages: {len(assistant_messages)}")
            
            # הדפסת הודעות המערכת
            print(f"\n🔍 System Messages:")
            for j, sys_msg in enumerate(system_messages, 1):
                content = sys_msg.get('content', '')
                print(f"  {j}. {content[:100]}...")
                
            # הדפסת 5 הודעות המשתמש האחרונות
            print(f"\n🔍 Last 5 User Messages:")
            for j, user_msg in enumerate(user_messages[-5:], 1):
                content = user_msg.get('content', '')
                print(f"  {j}. {content[:150]}...")
            
            # הדפסת 5 הודעות הבוט האחרונות
            print(f"\n🔍 Last 5 Assistant Messages:")
            for j, assistant_msg in enumerate(assistant_messages[-5:], 1):
                content = assistant_msg.get('content', '')
                print(f"  {j}. {content[:150]}...")
                
            # הדפסת הודעת המשתמש האחרונה (הנוכחית)
            print(f"\n🔍 Current User Message:")
            if user_messages:
                current_msg = user_messages[-1].get('content', '')
                print(f"  Current: {current_msg}")
            
            # הדפסת תשובת GPT
            print(f"\n🔍 GPT Response:")
            if isinstance(response_data, dict):
                choices = response_data.get('choices', [])
                if choices:
                    response_content = choices[0].get('message', {}).get('content', '')
                    print(f"  Response: {response_content[:200]}...")
        
        print("=" * 80)
        print()

if __name__ == "__main__":
    main() 