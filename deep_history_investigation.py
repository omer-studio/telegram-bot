#!/usr/bin/env python3
"""
חקירה עמוקה של בעיית ההיסטוריה
סימולציה מדויקת של מה שקורה בזמן ריצה חיה
"""
import os
import sys
import traceback
import asyncio
from datetime import datetime

def deep_history_investigation():
    """חקירה עמוקה להבנת מדוע היסטוריה לא נטענת בזמן ריצה חיה"""
    
    print("🔍 **חקירה עמוקה של בעיית ההיסטוריה**")
    print("=" * 80)
    
    chat_id = '111709341'  # משתמש בעייתי
    
    # 1. בדיקת סביבת עבודה
    print(f"\n📁 **בדיקת סביבת עבודה:**")
    print(f"   📂 Working Directory: {os.getcwd()}")
    print(f"   🐍 Python Path: {sys.executable}")
    print(f"   📋 PYTHONPATH: {sys.path[:3]}")
    
    # 2. בדיקת קבצים ונתיבים
    print(f"\n📂 **בדיקת קבצים קריטיים:**")
    critical_files = [
        'chat_utils.py', 
        'profile_utils.py', 
        'etc/secrets/config.json',
        'data',  # תיקייה
    ]
    
    for file_path in critical_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path} - קיים")
            if os.path.isfile(file_path):
                try:
                    stat = os.stat(file_path)
                    print(f"      📊 Size: {stat.st_size} bytes | Modified: {datetime.fromtimestamp(stat.st_mtime)}")
                except Exception as e:
                    print(f"      ⚠️ Error reading stats: {e}")
        else:
            print(f"   ❌ {file_path} - לא קיים!")
    
    # 3. סימולציה מדויקת של קוד message_handler
    print(f"\n🔄 **סימולציה מדויקת של טעינת נתונים:**")
    
    try:
        print("🔧 [SIMULATION] מתחיל טעינת נתונים עבור משתמש 111709341...")
        
        # Step 1: Import simulation
        print("🔧 [SIMULATION] מייבא get_chat_history_messages_fast")
        try:
            from chat_utils import get_chat_history_messages_fast
            print("   ✅ Import chat_utils הצליח")
        except Exception as e:
            print(f"   ❌ Import chat_utils נכשל: {e}")
            traceback.print_exc()
            return
        
        # Step 2: Function call simulation  
        print(f"🔧 [SIMULATION] קורא להיסטוריה עבור {chat_id}")
        try:
            history_messages = get_chat_history_messages_fast(chat_id)
            print(f"   ✅ הפונקציה הושלמה: {len(history_messages) if history_messages else 0} הודעות")
            
            if history_messages:
                print(f"   📝 דוגמא - 2 הודעות ראשונות:")
                for i, msg in enumerate(history_messages[:2], 1):
                    role = msg.get('role', 'N/A')
                    content = msg.get('content', '')[:50] + '...' if len(msg.get('content', '')) > 50 else msg.get('content', '')
                    print(f"      {i}. {role}: {content}")
            else:
                print("   ⚠️ הפונקציה החזירה ריק!")
                
        except Exception as e:
            print(f"   ❌ הפונקציה נכשלה: {e}")
            print(f"   🚨 Exception type: {type(e).__name__}")
            print(f"   🚨 Full traceback:")
            traceback.print_exc()
            return
        
        # Step 3: Profile simulation
        print(f"🔧 [SIMULATION] מייבא get_user_summary_fast")
        try:
            from profile_utils import get_user_summary_fast
            print("   ✅ Import profile_utils הצליח")
        except Exception as e:
            print(f"   ❌ Import profile_utils נכשל: {e}")
            traceback.print_exc()
            return
        
        print(f"🔧 [SIMULATION] קורא לסיכום עבור {chat_id}")
        try:
            current_summary = get_user_summary_fast(chat_id)
            print(f"   ✅ הפונקציה הושלמה: '{current_summary}'")
        except Exception as e:
            print(f"   ❌ הפונקציה נכשלה: {e}")
            print(f"   🚨 Exception type: {type(e).__name__}")
            print(f"   🚨 Full traceback:")
            traceback.print_exc()
            return
        
        print("✅ [SIMULATION] כל הסימולציה עברה בהצלחה!")
        
        # 4. בדיקת שינויים אפשריים במסד הנתונים
        print(f"\n🗄️ **בדיקת מסד נתונים חי:**")
        try:
            import psycopg2
            import json
            
            with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
            
            connection = psycopg2.connect(db_url)
            cursor = connection.cursor()
            
            # בדיקת עדכונים אחרונים
            cursor.execute("""
                SELECT COUNT(*), MAX(timestamp) 
                FROM chat_messages 
                WHERE chat_id = %s
            """, (chat_id,))
            
            count, last_update = cursor.fetchone()
            print(f"   📊 הודעות במסד: {count}")
            print(f"   ⏰ עדכון אחרון: {last_update}")
            
            # בדיקת הודעות אחרונות
            cursor.execute("""
                SELECT LEFT(user_msg, 50), LEFT(bot_msg, 50), timestamp
                FROM chat_messages 
                WHERE chat_id = %s
                ORDER BY timestamp DESC 
                LIMIT 3
            """, (chat_id,))
            
            recent = cursor.fetchall()
            print(f"   📝 3 הודעות אחרונות:")
            for i, (user, bot, ts) in enumerate(recent, 1):
                print(f"      {i}. {ts} | USER: {user}... | BOT: {bot}...")
            
            cursor.close()
            connection.close()
            
        except Exception as e:
            print(f"   ❌ שגיאה בבדיקת מסד נתונים: {e}")
        
        # 5. בדיקת הבדלים בין סביבת פיתוח לייצור
        print(f"\n🌐 **בדיקת הבדלי סביבה:**")
        
        # בדיקת environment variables
        env_vars = ['PYTHONPATH', 'PATH', 'USERPROFILE', 'TEMP']
        for var in env_vars:
            value = os.environ.get(var, 'N/A')
            print(f"   🔧 {var}: {value[:100]}..." if len(str(value)) > 100 else f"   🔧 {var}: {value}")
        
        # בדיקת modules שנטענו
        loaded_modules = [name for name in sys.modules.keys() if any(x in name for x in ['chat_utils', 'profile_utils', 'telegram', 'asyncio'])]
        print(f"   📦 מודולים רלוונטיים שנטענו: {len(loaded_modules)}")
        for mod in sorted(loaded_modules)[:10]:  # רק 10 ראשונים
            print(f"      - {mod}")
        
        # 6. בדיקת permissions
        print(f"\n🔐 **בדיקת הרשאות:**")
        try:
            # בדיקת קריאה לתיקייה
            files_in_data = os.listdir('data') if os.path.exists('data') else []
            print(f"   📂 קבצים בתיקיית data: {len(files_in_data)}")
            
            # בדיקת כתיבה זמנית
            test_file = 'temp_test_permissions.txt'
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"   ✅ הרשאות כתיבה - תקינות")
            
        except Exception as e:
            print(f"   ❌ בעיה בהרשאות: {e}")
        
        print(f"\n🎯 **סיכום החקירה:**")
        print("   ✅ כל הפונקציות עובדות תקין בסימולציה!")
        print("   ⚠️ הבעיה חייבת להיות במשהו ספציפי לזמן ריצה אסינכרונית!")
        print("   🔍 המלצה: לבדוק לוגי Render בזמן אמת כשמשתמש שולח הודעה")
        
    except Exception as e:
        print(f"\n❌ **שגיאה בחקירה עצמה:** {e}")
        traceback.print_exc()

async def async_simulation():
    """סימולציה אסינכרונית - בדיוק כמו בזמן ריצה אמיתי"""
    print(f"\n🔄 **סימולציה אסינכרונית:**")
    
    chat_id = '111709341'
    
    try:
        print("🚀 [ASYNC] מתחיל בסביבה אסינכרונית...")
        
        # סימולציה של הקוד ממש כמו ב-message_handler
        current_summary = ""
        history_messages = []
        
        try:
            print(f"🔧 [ASYNC] מתחיל טעינת נתונים עבור {chat_id}")
            
            # קריאה מהירה מקובץ מקומי בלבד - בלי Google Sheets!
            print(f"🔧 [ASYNC] מייבא get_chat_history_messages_fast")
            from chat_utils import get_chat_history_messages_fast
            
            print(f"🔧 [ASYNC] קורא להיסטוריה עבור {chat_id}")
            history_messages = get_chat_history_messages_fast(chat_id)  
            print(f"🔧 [ASYNC] היסטוריה הוחזרה: {len(history_messages) if history_messages else 0} הודעות")
            
            # קריאה מהירה מפרופיל מקומי בלבד
            print(f"🔧 [ASYNC] מייבא get_user_summary_fast")
            from profile_utils import get_user_summary_fast
            
            print(f"🔧 [ASYNC] קורא לסיכום עבור {chat_id}")
            current_summary = get_user_summary_fast(chat_id)
            print(f"🔧 [ASYNC] סיכום הוחזר: '{current_summary}'")
            
            print(f"✅ [ASYNC] טעינת נתונים הושלמה בהצלחה עבור {chat_id}")
                
        except Exception as data_err:
            print(f"🚨 [ASYNC_DEBUG] שגיאה בטעינת נתונים עבור {chat_id}: {data_err}")
            print(f"🚨 [ASYNC_DEBUG] exception type: {type(data_err).__name__}")
            print(f"🚨 [ASYNC_DEBUG] full traceback:")
            traceback.print_exc()
            # ממשיכים בלי נתונים - עדיף תשובה מהירה מאשר נתונים מלאים
        
        # בניית הודעות
        from prompts import SYSTEM_PROMPT
        messages_for_gpt = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # הוספת סיכום משתמש אם יש (מהיר)
        if current_summary:
            messages_for_gpt.append({"role": "system", "content": f"🎯 מידע על המשתמש: {current_summary}"})
        
        # הוספת היסטוריה (מהיר)
        print(f"🔍 [ASYNC_DEBUG] history_messages לאחר טעינה: {len(history_messages) if history_messages else 0} הודעות")
        if history_messages:
            messages_for_gpt.extend(history_messages)
            print(f"✅ [ASYNC_DEBUG] הוספו {len(history_messages)} הודעות היסטוריה ל-messages_for_gpt")
        else:
            print(f"❌ [ASYNC_DEBUG] לא הוספו הודעות היסטוריה - history_messages ריק!")
        
        # הוספת ההודעה החדשה
        user_msg = "היי"
        messages_for_gpt.append({"role": "user", "content": user_msg})
        
        print(f"📤 [ASYNC] שולח {len(messages_for_gpt)} הודעות ל-GPT-A (סימולציה)")
        
        # ספירת הודעות
        system_msgs = len([m for m in messages_for_gpt if m.get('role') == 'system'])
        user_msgs = len([m for m in messages_for_gpt if m.get('role') == 'user'])  
        assistant_msgs = len([m for m in messages_for_gpt if m.get('role') == 'assistant'])
        
        print(f"📊 [ASYNC_FINAL] תוצאה סופית: system={system_msgs}, user={user_msgs}, assistant={assistant_msgs}")
        
        if user_msgs == 1 and assistant_msgs == 0:
            print(f"🚨 [ASYNC_FINAL] זוהתה בעיה - אין היסטוריה!")
        else:
            print(f"✅ [ASYNC_FINAL] יש היסטוריה - הכל תקין!")
            
    except Exception as e:
        print(f"❌ [ASYNC] שגיאה בסימולציה אסינכרונית: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("🎯 מתחיל חקירה עמוקה...")
    
    # סימולציה רגילה
    deep_history_investigation()
    
    # סימולציה אסינכרונית
    try:
        asyncio.run(async_simulation())
    except Exception as e:
        print(f"❌ שגיאה בהרצת async simulation: {e}")
    
    print("\n🏁 חקירה הושלמה!") 