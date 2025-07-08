#!/usr/bin/env python3
"""
חקירה מקיפה של בעיית ההיסטוריה
בדיקה אם הבעיה ספציפית למשתמש 111709341 או כללית
"""
import psycopg2
import json
import os
from datetime import datetime, timedelta

def comprehensive_history_analysis():
    try:
        print("🔍 מתחיל חקירה מקיפה של בעיית ההיסטוריה...")
        
        # טעינת קונפיגורציה
        config_path = 'etc/secrets/config.json'
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        connection = psycopg2.connect(db_url)
        cursor = connection.cursor()
        
        print("📊 שלב 1: סטטיסטיקות כלליות של המערכת")
        print("=" * 50)
        
        # סך הכל משתמשים מאושרים
        cursor.execute("SELECT COUNT(*) FROM user_profiles WHERE approved = TRUE")
        approved_users = cursor.fetchone()[0]
        print(f"👥 סך משתמשים מאושרים: {approved_users}")
        
        # סך הכל הודעות GPT-A ביומיים האחרונים
        cursor.execute("""
            SELECT COUNT(*) 
            FROM gpt_calls_log 
            WHERE call_type = 'A' 
            AND timestamp >= NOW() - INTERVAL '2 days'
        """)
        total_gpt_a_calls = cursor.fetchone()[0]
        print(f"📞 סך קריאות GPT-A ביומיים: {total_gpt_a_calls}")
        
        print("\n📊 שלב 2: בדיקת בעיית היסטוריה ברמת המערכת")
        print("=" * 50)
        
        # ספירת קריאות ללא היסטוריה (רק system + user, בלי assistant)
        cursor.execute("""
            SELECT 
                chat_id,
                COUNT(*) as total_calls,
                COUNT(CASE 
                    WHEN request_data::jsonb -> 'messages' @> '[{"role": "user"}]'
                    AND NOT (request_data::jsonb -> 'messages' @> '[{"role": "assistant"}]')
                    THEN 1 
                END) as no_history_calls
            FROM gpt_calls_log 
            WHERE call_type = 'A' 
            AND timestamp >= NOW() - INTERVAL '2 days'
            AND chat_id IS NOT NULL
            GROUP BY chat_id
            HAVING COUNT(*) >= 3
            ORDER BY COUNT(*) DESC
        """)
        
        user_stats = cursor.fetchall()
        
        print(f"🔍 נמצאו {len(user_stats)} משתמשים עם 3+ קריאות GPT-A ביומיים האחרונים:")
        
        problematic_users = []
        total_calls_all = 0
        total_no_history_all = 0
        
        for chat_id, total_calls, no_history_calls in user_stats:
            total_calls_all += total_calls
            total_no_history_all += no_history_calls
            
            percentage = (no_history_calls / total_calls) * 100 if total_calls > 0 else 0
            
            print(f"  👤 {chat_id}: {no_history_calls}/{total_calls} ללא היסטוריה ({percentage:.1f}%)")
            
            # רישום משתמשים בעייתיים (יותר מ-30% ללא היסטוריה)
            if percentage > 30 and total_calls >= 5:
                problematic_users.append({
                    'chat_id': chat_id,
                    'total_calls': total_calls,
                    'no_history_calls': no_history_calls,
                    'percentage': percentage
                })
        
        system_percentage = (total_no_history_all / total_calls_all) * 100 if total_calls_all > 0 else 0
        print(f"\n📈 סיכום מערכת: {total_no_history_all}/{total_calls_all} ללא היסטוריה ({system_percentage:.1f}%)")
        
        print("\n📊 שלב 3: זיהוי משתמשים בעייתיים")
        print("=" * 50)
        
        if problematic_users:
            print(f"🚨 נמצאו {len(problematic_users)} משתמשים בעייתיים (>30% ללא היסטוריה):")
            for user in problematic_users:
                print(f"  🚨 {user['chat_id']}: {user['percentage']:.1f}% ללא היסטוריה ({user['no_history_calls']}/{user['total_calls']})")
        else:
            print("✅ לא נמצאו משתמשים בעייתיים נוספים!")
        
        print("\n📊 שלב 4: בדיקה עמיקה של משתמש 111709341")
        print("=" * 50)
        
        target_user = '111709341'
        
        # בדיקת היסטוריה במסד נתונים
        cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE chat_id = %s", (target_user,))
        chat_messages_count = cursor.fetchone()[0]
        print(f"💬 הודעות ב-chat_messages: {chat_messages_count}")
        
        # בדיקת פרופיל משתמש
        cursor.execute("SELECT approved, code_approve FROM user_profiles WHERE chat_id = %s", (target_user,))
        user_profile = cursor.fetchone()
        if user_profile:
            approved, code = user_profile
            print(f"👤 סטטוס פרופיל: approved={approved}, code={code}")
        else:
            print("❌ לא נמצא פרופיל למשתמש!")
        
        # בדיקת קריאות GPT אחרונות
        cursor.execute("""
            SELECT 
                timestamp, 
                tokens_input, 
                tokens_output,
                LEFT(request_data::text, 200) as request_preview
            FROM gpt_calls_log 
            WHERE chat_id = %s AND call_type = 'A'
            ORDER BY timestamp DESC 
            LIMIT 5
        """, (target_user,))
        
        recent_calls = cursor.fetchall()
        print(f"\n🔍 5 קריאות GPT-A אחרונות של {target_user}:")
        
        for i, (timestamp, tokens_in, tokens_out, request_preview) in enumerate(recent_calls, 1):
            print(f"  {i}. {timestamp} | {tokens_in}→{tokens_out} טוקנים")
            
            # ניתוח מהיר של ההודעות
            try:
                request_data = json.loads(request_preview + '...')  # ייתכן שנחתך
                messages = request_data.get('messages', [])
                user_msgs = len([m for m in messages if m.get('role') == 'user'])
                assistant_msgs = len([m for m in messages if m.get('role') == 'assistant'])
                system_msgs = len([m for m in messages if m.get('role') == 'system'])
                
                print(f"     📨 הודעות: system={system_msgs}, user={user_msgs}, assistant={assistant_msgs}")
                
                if user_msgs == 1 and assistant_msgs == 0:
                    print(f"     ⚠️ אין היסטוריה!")
                else:
                    print(f"     ✅ יש היסטוריה")
                    
            except:
                print(f"     ❓ לא הצלחתי לנתח את ההודעות")
        
        print("\n📊 שלב 5: בדיקת תקינות פונקציות")
        print("=" * 50)
        
        # בדיקה ישירה של הפונקציות
        try:
            from chat_utils import get_chat_history_messages_fast
            print("🔧 בודק get_chat_history_messages_fast...")
            
            history_result = get_chat_history_messages_fast(target_user)
            print(f"📊 התוצאה: {len(history_result) if history_result else 0} הודעות")
            
            if history_result and len(history_result) > 0:
                print("✅ הפונקציה עובדת תקין!")
                print(f"   דוגמא - 2 הודעות אחרונות:")
                for i, msg in enumerate(history_result[-2:], 1):
                    role = msg.get('role', 'N/A')
                    content = msg.get('content', '')[:50]
                    print(f"     {i}. {role}: {content}...")
            else:
                print("❌ הפונקציה מחזירה ריק!")
                
        except Exception as e:
            print(f"🚨 שגיאה בפונקציה: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
        
        try:
            from profile_utils import get_user_summary_fast
            print("\n🔧 בודק get_user_summary_fast...")
            
            summary_result = get_user_summary_fast(target_user)
            print(f"📊 התוצאה: '{summary_result}'")
            
            if summary_result:
                print("✅ הפונקציה עובדת תקין!")
            else:
                print("⚠️ הפונקציה מחזירה None/ריק")
                
        except Exception as e:
            print(f"🚨 שגיאה בפונקציה: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
        
        print("\n📊 שלב 6: סיכום והמלצות")
        print("=" * 50)
        
        if system_percentage > 20:
            print("🚨 בעיה מערכתית! יותר מ-20% מהקריאות ללא היסטוריה!")
        elif len(problematic_users) > 1:
            print("⚠️ בעיה חלקית - מספר משתמשים מושפעים")
        elif len(problematic_users) == 1 and problematic_users[0]['chat_id'] == target_user:
            print("🎯 בעיה ספציפית למשתמש 111709341 בלבד")
        else:
            print("✅ המערכת נראית תקינה ברובה")
        
        print(f"\n📋 דוח מהיר:")
        print(f"   • סך משתמשים מאושרים: {approved_users}")
        print(f"   • סך קריאות GPT-A ביומיים: {total_gpt_a_calls}")
        print(f"   • אחוז ללא היסטוריה במערכת: {system_percentage:.1f}%")
        print(f"   • משתמשים בעייתיים: {len(problematic_users)}")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"❌ שגיאה בחקירה: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    comprehensive_history_analysis() 