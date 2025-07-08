#!/usr/bin/env python3
"""
דיבאג טעינת היסטוריה עבור משתמש ספציפי
"""
import psycopg2
import json
import os
import sys

# Add path to project
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_history_loading(chat_id='111709341'):
    print(f"🔍 מדבג טעינת היסטוריה עבור משתמש {chat_id}...")
    
    # בדיקה 1: האם המשתמש מאושר?
    try:
        config_path = 'etc/secrets/config.json'
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        connection = psycopg2.connect(db_url)
        cursor = connection.cursor()
        
        # בדיקת סטטוס אישור
        cursor.execute("SELECT approved, code_approve FROM user_profiles WHERE chat_id = %s", (chat_id,))
        user_status = cursor.fetchone()
        
        if user_status:
            approved, code = user_status
            print(f"✅ משתמש נמצא: approved={approved}, code={code}")
        else:
            print(f"❌ משתמש לא נמצא ב-user_profiles!")
            return
            
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת סטטוס: {e}")
        return
    
    # בדיקה 2: כמה הודעות יש במסד?
    try:
        from db_manager import get_chat_history
        rows = get_chat_history(chat_id, 15)
        print(f"📊 get_chat_history החזירה: {len(rows)} שורות")
        
        if len(rows) > 0:
            print(f"   דוגמא - שורה אחרונה: user='{rows[-1][0]}' bot='{rows[-1][1][:50]}...'")
        
    except Exception as e:
        print(f"❌ שגיאה ב-get_chat_history: {e}")
        import traceback
        traceback.print_exc()
    
    # בדיקה 3: איך get_chat_history_messages_fast עובדת?
    try:
        from chat_utils import get_chat_history_messages_fast
        print(f"\n🔧 בדיקת get_chat_history_messages_fast...")
        messages = get_chat_history_messages_fast(chat_id)
        print(f"📊 get_chat_history_messages_fast החזירה: {len(messages)} הודעות")
        
        if len(messages) > 0:
            user_count = len([m for m in messages if m.get('role') == 'user'])
            assistant_count = len([m for m in messages if m.get('role') == 'assistant'])
            print(f"   📨 פילוח: user={user_count}, assistant={assistant_count}")
            
            # הצגת 3 הודעות אחרונות
            print(f"   📝 3 הודעות אחרונות:")
            for i, msg in enumerate(messages[-3:], 1):
                role = msg.get('role', 'N/A')
                content = msg.get('content', '')[:50]
                print(f"      {i}. {role}: {content}...")
        else:
            print(f"   ❌ לא הוחזרו הודעות!")
            
    except Exception as e:
        print(f"❌ שגיאה ב-get_chat_history_messages_fast: {e}")
        import traceback
        traceback.print_exc()
    
    # בדיקה 4: איך זה נראה בcode של message_handler?
    try:
        print(f"\n🔧 סימולציה של message_handler...")
        
        # חיקוי הקוד מ-message_handler
        from profile_utils import get_user_summary_fast
        current_summary = get_user_summary_fast(chat_id)
        print(f"📋 סיכום משתמש: '{current_summary}'")
        
        from chat_utils import get_chat_history_messages_fast
        history_messages = get_chat_history_messages_fast(chat_id)
        print(f"📨 היסטוריה נטענה: {len(history_messages)} הודעות")
        
        # בניית messages_for_gpt כמו בקוד האמיתי
        messages_for_gpt = [{"role": "system", "content": "מוקדם להגדיר - זה רק טסט"}]
        
        if current_summary:
            messages_for_gpt.append({"role": "system", "content": f"🎯 מידע על המשתמש: {current_summary}"})
        
        if history_messages:
            messages_for_gpt.extend(history_messages)
            print(f"✅ היסטוריה נוספה ל-messages_for_gpt")
        else:
            print(f"❌ לא נוספה היסטוריה ל-messages_for_gpt!")
        
        # הוספת הודעה נוכחית (סימולציה)
        messages_for_gpt.append({"role": "user", "content": "דיברנו כבר לא?"})
        
        print(f"📊 סך הכל messages_for_gpt: {len(messages_for_gpt)}")
        for i, msg in enumerate(messages_for_gpt):
            role = msg.get('role', 'N/A')
            content = msg.get('content', '')[:50]
            print(f"   {i+1}. {role}: {content}...")
            
        # ספירה לפי role
        system_count = len([m for m in messages_for_gpt if m.get('role') == 'system'])
        user_count = len([m for m in messages_for_gpt if m.get('role') == 'user'])
        assistant_count = len([m for m in messages_for_gpt if m.get('role') == 'assistant'])
        
        print(f"\n📊 פילוח סופי:")
        print(f"   system: {system_count}")
        print(f"   user: {user_count}")
        print(f"   assistant: {assistant_count}")
        
        if user_count == 1 and assistant_count == 0:
            print(f"🚨 זה בדיוק מה שקורה! רק הודעה נוכחית ואין היסטוריה!")
        
    except Exception as e:
        print(f"❌ שגיאה בסימולציה: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_history_loading() 