#!/usr/bin/env python3
"""
בדיקת הודעות אחרונות מהמסד נתונים
"""

import sys
sys.path.append('.')

from db_tool import טבלה_הודעות, טבלה_gpt_לוגים

def main():
    print("🔍 בדיקת הודעות אחרונות...")
    
    # בדיקת 20 הודעות האחרונות
    try:
        results = טבלה_הודעות(limit=20)
        print(f"📋 נמצאו {len(results)} הודעות:\n")
        
        for i, msg in enumerate(results, 1):
            timestamp = msg.get("timestamp", "Unknown")
            chat_id = msg.get("chat_id", "Unknown")
            user_msg = msg.get("user_msg", "")
            bot_msg = msg.get("bot_msg", "")
            
            print(f"📅 {i}. {timestamp}")
            print(f"👤 Chat ID: {chat_id}")
            print(f"💬 User: {user_msg[:80]}..." if user_msg and len(user_msg) > 80 else f"💬 User: {user_msg}")
            print(f"🤖 Bot: {bot_msg[:80]}..." if bot_msg and len(bot_msg) > 80 else f"🤖 Bot: {bot_msg}")
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ שגיאה בטעינת הודעות: {e}")
    
    print("\n🔍 בדיקת לוגי GPT אחרונים...")
    
    # בדיקת 10 לוגי GPT האחרונים
    try:
        gpt_results = טבלה_gpt_לוגים(limit=10)
        print(f"📋 נמצאו {len(gpt_results)} לוגי GPT:\n")
        
        for i, gpt_log in enumerate(gpt_results, 1):
            timestamp = gpt_log.get("timestamp", "Unknown")
            chat_id = gpt_log.get("chat_id", "Unknown")
            call_type = gpt_log.get("call_type", "Unknown")
            request_data = gpt_log.get("request_data", {})
            
            print(f"📅 {i}. {timestamp}")
            print(f"👤 Chat ID: {chat_id}")
            print(f"🎯 Call Type: {call_type}")
            
            # בדיקת הודעות מהbאקשה
            if isinstance(request_data, dict):
                messages = request_data.get("messages", [])
                print(f"📝 Messages count: {len(messages)}")
                
                # הדפסת הודעה אחרונה של משתמש
                user_messages = [msg for msg in messages if msg.get("role") == "user"]
                if user_messages:
                    last_user_msg = user_messages[-1].get("content", "")
                    print(f"👤 Last user message: {last_user_msg[:100]}...")
                
                # בדיקת system prompts
                system_messages = [msg for msg in messages if msg.get("role") == "system"]
                print(f"⚙️ System messages count: {len(system_messages)}")
                
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ שגיאה בטעינת לוגי GPT: {e}")

if __name__ == "__main__":
    main() 