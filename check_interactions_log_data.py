#!/usr/bin/env python3
"""
🔍 בדיקה מקיפה של נתוני טבלת interactions_log
בודק שכל הנתונים נכונים ואין כפילויות
"""

import sys
import os
sys.path.append('.')

def check_interactions_log_data():
    """בדיקה מקיפה של נתוני טבלת interactions_log"""
    
    try:
        # ייבוא מודולים
        from config import config
        import psycopg2
        from decimal import Decimal
        
        print("🔍 בודק נתוני טבלת interactions_log...")
        print("=" * 60)
        
        # חיבור למסד הנתונים (כמו ב-comprehensive_deploy_check.py)
        print("🔍 מתחבר למסד הנתונים...")
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        if not db_url:
            print("❌ לא נמצא URL למסד הנתונים")
            return
            
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # בדיקה 1: סיכום כללי
        print("📊 1. סיכום כללי:")
        cur.execute("SELECT COUNT(*) FROM interactions_log")
        total_count = cur.fetchone()[0]
        print(f"   📈 סה\"כ אינטראקציות: {total_count}")
        
        # בדיקה 2: בדיקת נתוני בסיס
        print("\n📋 2. בדיקת נתוני בסיס:")
        
        # רשומות עם chat_id ריק
        cur.execute("SELECT COUNT(*) FROM interactions_log WHERE chat_id IS NULL")
        null_chat_id = cur.fetchone()[0]
        print(f"   ❌ רשומות עם chat_id ריק: {null_chat_id}")
        
        # רשומות עם user_msg ריק
        cur.execute("SELECT COUNT(*) FROM interactions_log WHERE user_msg IS NULL OR user_msg = ''")
        null_user_msg = cur.fetchone()[0]
        print(f"   ❌ רשומות עם user_msg ריק: {null_user_msg}")
        
        # רשומות עם bot_msg ריק
        cur.execute("SELECT COUNT(*) FROM interactions_log WHERE bot_msg IS NULL OR bot_msg = ''")
        null_bot_msg = cur.fetchone()[0]
        print(f"   ❌ רשומות עם bot_msg ריק: {null_bot_msg}")
        
        # בדיקה 3: בדיקת נתוני GPT-A (הבסיסי)
        print("\n🤖 3. בדיקת נתוני GPT-A:")
        
        # רשומות עם GPT-A מודל
        cur.execute("SELECT COUNT(*) FROM interactions_log WHERE gpt_a_model IS NOT NULL")
        gpt_a_with_model = cur.fetchone()[0]
        print(f"   ✅ רשומות עם GPT-A מודל: {gpt_a_with_model}")
        
        # רשומות עם GPT-A עלות
        cur.execute("SELECT COUNT(*) FROM interactions_log WHERE gpt_a_cost_agorot > 0")
        gpt_a_with_cost = cur.fetchone()[0]
        print(f"   💰 רשומות עם GPT-A עלות: {gpt_a_with_cost}")
        
        # רשומות עם GPT-A טוקנים
        cur.execute("SELECT COUNT(*) FROM interactions_log WHERE gpt_a_tokens_input > 0")
        gpt_a_with_tokens = cur.fetchone()[0]
        print(f"   🔢 רשומות עם GPT-A טוקנים: {gpt_a_with_tokens}")
        
        # בדיקה 4: בדיקת נתוני GPT-B עד GPT-E
        print("\n🤖 4. בדיקת נתוני GPT-B עד GPT-E:")
        
        for gpt_type in ['b', 'c', 'd', 'e']:
            cur.execute(f"SELECT COUNT(*) FROM interactions_log WHERE gpt_{gpt_type}_activated = true")
            activated_count = cur.fetchone()[0]
            print(f"   ✅ GPT-{gpt_type.upper()} מופעל: {activated_count}")
        
        # בדיקה 5: בדיקת עלויות
        print("\n💰 5. בדיקת עלויות:")
        
        # סה"כ עלות
        cur.execute("SELECT SUM(total_cost_agorot) FROM interactions_log WHERE total_cost_agorot > 0")
        total_cost_agorot = cur.fetchone()[0] or 0
        total_cost_shekels = total_cost_agorot / 100
        print(f"   💰 סה\"כ עלות: {total_cost_agorot} אגורות ({total_cost_shekels:.2f} שקלים)")
        
        # עלות ממוצעת
        cur.execute("SELECT AVG(total_cost_agorot) FROM interactions_log WHERE total_cost_agorot > 0")
        avg_cost_agorot = cur.fetchone()[0] or 0
        avg_cost_shekels = avg_cost_agorot / 100
        print(f"   📊 עלות ממוצעת: {avg_cost_agorot:.2f} אגורות ({avg_cost_shekels:.4f} שקלים)")
        
        # בדיקה 6: בדיקת זמנים
        print("\n⏰ 6. בדיקת זמנים:")
        
        # זמן תגובה ממוצע
        cur.execute("SELECT AVG(user_to_bot_response_time) FROM interactions_log WHERE user_to_bot_response_time > 0")
        avg_response_time = cur.fetchone()[0] or 0
        print(f"   ⚡ זמן תגובה ממוצע: {avg_response_time:.2f} שניות")
        
        # זמן עיבוד ברקע ממוצע
        cur.execute("SELECT AVG(background_processing_time) FROM interactions_log WHERE background_processing_time > 0")
        avg_background_time = cur.fetchone()[0] or 0
        print(f"   🔄 זמן עיבוד ברקע ממוצע: {avg_background_time:.2f} שניות")
        
        # בדיקה 7: בדיקת היסטוריה
        print("\n📜 7. בדיקת היסטוריה:")
        
        # הודעות היסטוריה ממוצעות
        cur.execute("SELECT AVG(history_user_messages_count) FROM interactions_log WHERE history_user_messages_count >= 0")
        avg_user_history = cur.fetchone()[0] or 0
        print(f"   👤 הודעות משתמש ממוצעות: {avg_user_history:.1f}")
        
        cur.execute("SELECT AVG(history_bot_messages_count) FROM interactions_log WHERE history_bot_messages_count >= 0")
        avg_bot_history = cur.fetchone()[0] or 0
        print(f"   🤖 הודעות בוט ממוצעות: {avg_bot_history:.1f}")
        
        # בדיקה 8: בדיקת כפילויות
        print("\n🔍 8. בדיקת כפילויות:")
        
        # כפילויות לפי telegram_message_id
        cur.execute("""
            SELECT telegram_message_id, COUNT(*) as count 
            FROM interactions_log 
            WHERE telegram_message_id IS NOT NULL 
            GROUP BY telegram_message_id 
            HAVING COUNT(*) > 1
        """)
        duplicates = cur.fetchall()
        print(f"   🔄 כפילויות לפי telegram_message_id: {len(duplicates)}")
        if duplicates:
            for msg_id, count in duplicates[:5]:  # הצג רק 5 הראשונים
                print(f"      📨 {msg_id}: {count} פעמים")
        
        # כפילויות לפי user_msg + chat_id + timestamp
        cur.execute("""
            SELECT chat_id, user_msg, COUNT(*) as count 
            FROM interactions_log 
            GROUP BY chat_id, user_msg, DATE(timestamp)
            HAVING COUNT(*) > 1
        """)
        content_duplicates = cur.fetchall()
        print(f"   🔄 כפילויות לפי תוכן: {len(content_duplicates)}")
        if content_duplicates:
            for chat_id, user_msg, count in content_duplicates[:3]:  # הצג רק 3 הראשונים
                print(f"      👤 {chat_id}: {user_msg[:50]}... ({count} פעמים)")
        
        # בדיקה 9: בדיקת עקביות נתונים
        print("\n🔧 9. בדיקת עקביות נתונים:")
        
        # בדיקה שעלות כוללת = סכום עלויות חלקיות
        cur.execute("""
            SELECT COUNT(*) FROM interactions_log 
            WHERE total_cost_agorot != COALESCE(gpt_a_cost_agorot, 0) + 
                                      COALESCE(gpt_b_cost_agorot, 0) + 
                                      COALESCE(gpt_c_cost_agorot, 0) + 
                                      COALESCE(gpt_d_cost_agorot, 0) + 
                                      COALESCE(gpt_e_cost_agorot, 0)
            AND total_cost_agorot > 0
        """)
        cost_inconsistencies = cur.fetchone()[0]
        print(f"   ❌ אי-עקביות בעלויות: {cost_inconsistencies}")
        
        # בדיקה שGPT-A תמיד מופעל בעוד שהאחרים לא תמיד
        cur.execute("SELECT COUNT(*) FROM interactions_log WHERE gpt_a_model IS NULL")
        missing_gpt_a = cur.fetchone()[0]
        print(f"   ❌ רשומות ללא GPT-A: {missing_gpt_a}")
        
        # בדיקה 10: הצגת דוגמאות
        print("\n📄 10. דוגמאות רשומות:")
        
        cur.execute("""
            SELECT 
                serial_number,
                chat_id,
                SUBSTRING(user_msg, 1, 50) as user_msg_short,
                SUBSTRING(bot_msg, 1, 50) as bot_msg_short,
                gpt_a_model,
                total_cost_agorot,
                user_to_bot_response_time,
                history_user_messages_count,
                history_bot_messages_count,
                timestamp
            FROM interactions_log 
            ORDER BY serial_number DESC 
            LIMIT 3
        """)
        
        recent_records = cur.fetchall()
        
        for record in recent_records:
            print(f"   📝 רשומה #{record[0]}:")
            print(f"      👤 משתמש: {record[1]}")
            print(f"      💬 הודעה: {record[2]}...")
            print(f"      🤖 תגובה: {record[3]}...")
            print(f"      🧠 מודל: {record[4]}")
            print(f"      💰 עלות: {record[5]} אגורות")
            print(f"      ⏱️ זמן תגובה: {record[6]:.2f}s")
            print(f"      📊 היסטוריה: {record[7]} משתמש, {record[8]} בוט")
            print(f"      📅 זמן: {record[9]}")
            print()
        
        # סגירת חיבור
        cur.close()
        conn.close()
        
        print("✅ בדיקה הושלמה!")
        
        # סיכום
        print("\n🎯 סיכום:")
        issues = []
        
        if null_chat_id > 0:
            issues.append(f"❌ {null_chat_id} רשומות עם chat_id ריק")
        if null_user_msg > 0:
            issues.append(f"❌ {null_user_msg} רשומות עם user_msg ריק")
        if null_bot_msg > 0:
            issues.append(f"❌ {null_bot_msg} רשומות עם bot_msg ריק")
        if len(duplicates) > 0:
            issues.append(f"❌ {len(duplicates)} כפילויות לפי telegram_message_id")
        if len(content_duplicates) > 0:
            issues.append(f"❌ {len(content_duplicates)} כפילויות לפי תוכן")
        if cost_inconsistencies > 0:
            issues.append(f"❌ {cost_inconsistencies} אי-עקביות בעלויות")
        if missing_gpt_a > 0:
            issues.append(f"❌ {missing_gpt_a} רשומות ללא GPT-A")
        
        if issues:
            print("🚨 נמצאו בעיות:")
            for issue in issues:
                print(f"   {issue}")
        else:
            print("✅ כל הנתונים נראים תקינים!")
            
    except Exception as e:
        print(f"❌ שגיאה בבדיקת נתונים: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_interactions_log_data()