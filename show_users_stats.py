#!/usr/bin/env python3
"""
📊 הצגת סטטיסטיקות משתמשים
"""

import psycopg2
from datetime import datetime
from config import config

def show_users_stats():
    """הצגת סטטיסטיקות כל משתמש"""
    
    try:
        # חיבור למסד הנתונים
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        print("📊 === סטטיסטיקות משתמשים ===")
        print()
        
        # ספירת כל ההודעות
        cur.execute("SELECT COUNT(*) FROM chat_messages")
        total_messages = cur.fetchone()[0]
        print(f"📬 סך הכל הודעות במסד: {total_messages:,}")
        
        # ספירת משתמשים ייחודיים
        cur.execute("SELECT COUNT(DISTINCT chat_id) FROM chat_messages")
        total_users = cur.fetchone()[0]
        print(f"👥 סך הכל משתמשים: {total_users:,}")
        print()
        
        # פירוט לכל משתמש - רק הודעות המשתמש (לא הבוט)
        cur.execute("""
            SELECT 
                chat_id,
                COUNT(*) as user_messages_count,
                MIN(timestamp) as first_message,
                MAX(timestamp) as last_message
            FROM chat_messages 
            WHERE user_msg IS NOT NULL AND user_msg != '' 
            GROUP BY chat_id 
            ORDER BY user_messages_count DESC
        """)
        
        users_data = cur.fetchall()
        
        print("🔍 === פירוט הודעות לכל משתמש (רק הודעות המשתמש) ===")
        print()
        
        for i, (chat_id, user_messages, first_msg, last_msg) in enumerate(users_data, 1):
            print(f"{i:2d}. 👤 משתמש: {chat_id}")
            print(f"    📝 הודעות שלח: {user_messages:,}")
            print(f"    📅 הודעה ראשונה: {first_msg.strftime('%d/%m/%Y %H:%M')}")
            print(f"    📅 הודעה אחרונה: {last_msg.strftime('%d/%m/%Y %H:%M')}")
            
            # בדיקת פעילות אחרונה
            days_since_last = (datetime.now() - last_msg.replace(tzinfo=None)).days
            if days_since_last == 0:
                print(f"    🔥 פעיל היום!")
            elif days_since_last == 1:
                print(f"    ✅ פעיל אתמול")
            elif days_since_last <= 7:
                print(f"    🟢 פעיל לפני {days_since_last} ימים")
            else:
                print(f"    🟡 פעיל לפני {days_since_last} ימים")
            
            print()
        
        # סטטיסטיקות נוספות
        print("📈 === סטטיסטיקות נוספות ===")
        
        # משתמשים פעילים השבוע
        cur.execute("""
            SELECT COUNT(DISTINCT chat_id) 
            FROM chat_messages 
            WHERE timestamp >= NOW() - INTERVAL '7 days'
        """)
        active_this_week = cur.fetchone()[0]
        print(f"🟢 משתמשים פעילים השבוע: {active_this_week}")
        
        # הודעות השבוע
        cur.execute("""
            SELECT COUNT(*) 
            FROM chat_messages 
            WHERE timestamp >= NOW() - INTERVAL '7 days'
            AND user_msg IS NOT NULL AND user_msg != ''
        """)
        messages_this_week = cur.fetchone()[0]
        print(f"📝 הודעות משתמשים השבוע: {messages_this_week}")
        
        # אחוזי פעילות
        activity_rate = (active_this_week / total_users) * 100 if total_users > 0 else 0
        print(f"📊 אחוז פעילות שבועי: {activity_rate:.1f}%")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")

if __name__ == "__main__":
    show_users_stats() 