#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🔍 בדיקת מצב קוד אפרובל במסד הנתונים
"""

import sys
from datetime import datetime
from simple_data_manager import DataManager
from utils import safe_str, get_logger

logger = get_logger(__name__)

def check_approval_code(approval_code):
    """
    בודק מצב קוד אפרובל במסד הנתונים
    """
    try:
        approval_code = str(approval_code).strip()
        
        logger.info(f"בודק קוד אפרובל: {approval_code}")
        print(f"🔍 בודק קוד אפרובל: {approval_code}")
        print("=" * 50)
        
        data_manager = DataManager()
        
        # בדיקה מפורטת של הקוד
        query = """
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
        """
        results = data_manager.execute_query(query, (approval_code,))
        
        if not results:
            print(f"❌ קוד {approval_code} לא נמצא במסד הנתונים!")
            
            # בדיקה אם יש חלק מהקוד
            similar_query = """
                SELECT code_approve, chat_id, approved 
                FROM user_profiles 
                WHERE code_approve LIKE %s
                LIMIT 5
            """
            similar_results = data_manager.execute_query(similar_query, (f"%{approval_code}%",))
            if similar_results:
                print(f"\n🔍 קודים דומים שנמצאו:")
                for sim_code, sim_chat_id, sim_approved in similar_results:
                    safe_chat_id = safe_str(sim_chat_id)
                    print(f"   {sim_code} -> chat_id={safe_chat_id}, approved={sim_approved}")
            
        else:
            print(f"✅ נמצא {len(results)} תוצאות עבור קוד {approval_code}:")
            
            for i, (chat_id, code, code_try, approved, updated_at, name, age) in enumerate(results, 1):
                safe_chat_id = safe_str(chat_id)
                print(f"\n📋 תוצאה #{i}:")
                print(f"   📱 chat_id: {safe_chat_id}")
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
                    safe_chat_id = safe_str(chat_id)
                    print(f"\n🤖 מה הבוט אמור לעשות עם chat_id {safe_chat_id}:")
                    
                    if approved:
                        print("   ✅ לתת גישה מלאה לבוט - אין סיבה לבקש סיסמה!")
                    else:
                        print("   📋 לשלוח הודעת תנאים ולבקש אישור")
                        print("   ❌ לא אמור לבקש סיסמה/קוד שוב!")
        
        return results
        
    except Exception as e:
        logger.error(f"שגיאה בבדיקת קוד: {e}")
        print(f"❌ שגיאה בבדיקת קוד: {e}")
        import traceback
        traceback.print_exc()
        return None

def check_all_codes_with_chat_id():
    """
    מציג את כל הקודים שיש להם chat_id כדי לראות הדפוס
    """
    try:
        logger.info("בודק כל הקודים עם chat_id")
        print(f"\n🔍 כל הקודים שיש להם chat_id:")
        print("=" * 60)
        
        data_manager = DataManager()
        
        query = """
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
        """
        results = data_manager.execute_query(query)
        
        if results:
            for code_approve, chat_id, approved, code_try, updated_at in results:
                safe_chat_id = safe_str(chat_id)
                status = "✅ מאושר" if approved else "⏳ ממתין לאישור"
                print(f"   {code_approve} -> {safe_chat_id} | {status} | נסיונות: {code_try}")
        else:
            print("   אין קודים עם chat_id")
        
    except Exception as e:
        logger.error(f"שגיאה בבדיקת קודים: {e}")
        print(f"❌ שגיאה: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        approval_code = sys.argv[1]
    else:
        approval_code = "15689309"  # הקוד שהמשתמש דיווח עליו
    
    results = check_approval_code(approval_code)
    check_all_codes_with_chat_id() 