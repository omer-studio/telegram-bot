#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🔍 בדיקת מצב קוד אפרובל במסד הנתונים
"""

import sys
import psycopg2
from datetime import datetime
from config import DATABASE_URL

DB_URL = DATABASE_URL

def check_approval_code(approval_code):
    """
    בודק מצב קוד אפרובל במסד הנתונים
    """
    try:
        approval_code = str(approval_code).strip()
        
        print(f"🔍 בודק קוד אפרובל: {approval_code}")
        print("=" * 50)
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקה מפורטת של הקוד
        cur.execute("""
            SELECT 
                chat_id, 
                code_approve, 
                code_try, 
                approved, 
                updated_at,
                name,
                age
            FROM user_profiles 
            WHERE code_approve = %s
        """, (approval_code,))
        
        results = cur.fetchall()
        
        if not results:
            print(f"❌ קוד {approval_code} לא נמצא במסד הנתונים!")
            
            # בדיקה אם יש חלק מהקוד
            cur.execute("""
                SELECT code_approve, chat_id, approved 
                FROM user_profiles 
                WHERE code_approve LIKE %s
                LIMIT 5
            """, (f"%{approval_code}%",))
            
            similar_results = cur.fetchall()
            if similar_results:
                print(f"\n🔍 קודים דומים שנמצאו:")
                for sim_code, sim_chat_id, sim_approved in similar_results:
                    print(f"   {sim_code} -> chat_id={sim_chat_id}, approved={sim_approved}")
            
        else:
            print(f"✅ נמצא {len(results)} תוצאות עבור קוד {approval_code}:")
            
            for i, (chat_id, code, code_try, approved, updated_at, name, age) in enumerate(results, 1):
                print(f"\n📋 תוצאה #{i}:")
                print(f"   📱 chat_id: {chat_id}")
                print(f"   🔐 code_approve: {code}")
                print(f"   🔢 code_try: {code_try}")
                print(f"   ✅ approved: {approved}")
                print(f"   🕐 updated_at: {updated_at}")
                print(f"   👤 name: {name}")
                print(f"   🎂 age: {age}")
                
                # ניתוח המצב
                if chat_id:
                    if approved:
                        print("   📊 מצב: ✅ משתמש מאושר לחלוטין")
                    else:
                        print("   📊 מצב: ⏳ משתמש נתן קוד נכון אבל לא אישר תנאים")
                else:
                    print("   📊 מצב: 🆕 קוד חדש שטרם נדרש")
        
        # בדיקה נוספת - אם יש chat_id, בדוק איך הבוט אמור להתנהג
        if results:
            for chat_id, code, code_try, approved, updated_at, name, age in results:
                if chat_id:
                    print(f"\n🤖 מה הבוט אמור לעשות עם chat_id {chat_id}:")
                    
                    if approved:
                        print("   ✅ לתת גישה מלאה לבוט - אין סיבה לבקש סיסמה!")
                    else:
                        print("   📋 לשלוח הודעת תנאים ולבקש אישור")
                        print("   ❌ לא אמור לבקש סיסמה/קוד שוב!")
        
        cur.close()
        conn.close()
        
        return results
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת קוד: {e}")
        import traceback
        traceback.print_exc()
        return None

def check_all_codes_with_chat_id():
    """
    מציג את כל הקודים שיש להם chat_id כדי לראות הדפוס
    """
    try:
        print(f"\n🔍 כל הקודים שיש להם chat_id:")
        print("=" * 60)
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                code_approve, 
                chat_id, 
                approved, 
                code_try,
                updated_at
            FROM user_profiles 
            WHERE chat_id IS NOT NULL 
            AND code_approve IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 10
        """)
        
        results = cur.fetchall()
        
        if results:
            for code_approve, chat_id, approved, code_try, updated_at in results:
                status = "✅ מאושר" if approved else "⏳ ממתין לאישור"
                print(f"   {code_approve} -> {chat_id} | {status} | נסיונות: {code_try}")
        else:
            print("   אין קודים עם chat_id")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        approval_code = sys.argv[1]
    else:
        approval_code = "15689309"  # הקוד שהמשתמש דיווח עליו
    
    results = check_approval_code(approval_code)
    check_all_codes_with_chat_id() 