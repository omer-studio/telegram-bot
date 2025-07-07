#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🔍 חיפוש קוד 15689309 עם שם העמודה הנכון
"""

import json
import psycopg2

def load_config():
    """טעינת קונפיגורציה"""
    try:
        with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ שגיאה בטעינת קונפיגורציה: {e}")
        return {}

def search_code_15689309():
    """
    חיפוש קוד 15689309 עם שם העמודה הנכון
    """
    try:
        config = load_config()
        if not config:
            return
            
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        if not db_url:
            print("❌ לא נמצא URL למסד הנתונים")
            return
            
        print("🔍 חיפוש קוד אפרובל 15689309")
        print("=" * 50)
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # חיפוש קוד 15689309 עם שם העמודה הנכון
        cur.execute("""
            SELECT 
                id,
                chat_id, 
                code_approve, 
                code_try, 
                approved, 
                updated_at,
                name
            FROM user_profiles 
            WHERE code_approve = '15689309'
        """)
        
        results = cur.fetchall()
        
        if not results:
            print("❌ קוד 15689309 לא נמצא במסד הנתונים!")
            
            # חיפוש קודים דומים
            print("\n🔍 מחפש קודים דומים...")
            cur.execute("""
                SELECT id, code_approve, chat_id, approved, name
                FROM user_profiles 
                WHERE code_approve LIKE '%15689%'
                   OR code_approve LIKE '%89309%'
                   OR code_approve LIKE '%156893%'
                LIMIT 10
            """)
            
            similar = cur.fetchall()
            if similar:
                print("📋 קודים דומים שנמצאו:")
                for id_val, code, chat_id, approved, name in similar:
                    status = "✅ מאושר" if approved else "⏳ ממתין"
                    print(f"   ID:{id_val} | {code} -> chat_id={chat_id} | {status} | {name}")
            else:
                print("❌ לא נמצאו קודים דומים")
                
        else:
            print(f"✅ נמצא קוד 15689309!")
            for id_val, chat_id, code, code_try, approved, updated_at, name in results:
                print(f"\n📋 פרטי המשתמש (ID: {id_val}):")
                print(f"   📱 chat_id: {chat_id}")
                print(f"   🔐 code_approve: {code}")
                print(f"   🔢 code_try: {code_try}")
                print(f"   ✅ approved: {approved}")
                print(f"   🕐 updated_at: {updated_at}")
                print(f"   👤 name: {name}")
                
                # ניתוח המצב
                if chat_id and chat_id.strip():
                    if approved:
                        print("\n🎯 המצב: המשתמש מאושר לחלוטין!")
                        print("🤖 הבוט אמור: לתת גישה מלאה")
                        print("🚨 בעיה: למה הבוט מבקש סיסמה?!")
                        print(f"🔧 פתרון: בדוק למה הבוט לא מזהה את chat_id {chat_id}")
                    else:
                        print("\n🎯 המצב: המשתמש נתן קוד נכון אבל לא אישר תנאים")
                        print("🤖 הבוט אמור: לשלוח הודעת תנאים")
                        print("❌ הבוט לא אמור לבקש סיסמה!")
                else:
                    print("\n🎯 המצב: קוד קיים אבל לא משויך למשתמש")
                    print("🤖 הבוט אמור: לבקש מהמשתמש להזין את הקוד")
        
        # הצגת כל הקודים במסד
        print(f"\n🔍 כל הקודים במסד הנתונים:")
        print("=" * 60)
        
        cur.execute("""
            SELECT 
                id,
                code_approve, 
                chat_id, 
                approved, 
                code_try,
                name
            FROM user_profiles 
            WHERE code_approve IS NOT NULL 
            AND code_approve != ''
            ORDER BY updated_at DESC
        """)
        
        all_codes = cur.fetchall()
        
        if all_codes:
            for id_val, code_approve, chat_id, approved, code_try, name in all_codes:
                status = "✅ מאושר" if approved else "⏳ ממתין"
                chat_display = chat_id if chat_id else "ללא chat_id"
                print(f"   ID:{id_val} | {code_approve} -> {chat_display} | {status} | {name}")
        else:
            print("   אין קודים במסד")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    search_code_15689309() 