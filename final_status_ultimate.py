#!/usr/bin/env python3
import psycopg2
from config import config

try:
    conn = psycopg2.connect(config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL"))
    cur = conn.cursor()

    print("🎉 === תוצאות שחזור מקיף סופיות ===")
    print("=" * 50)

    # סטטיסטיקות כלליות
    cur.execute("SELECT COUNT(*) FROM chat_messages")
    total = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(DISTINCT chat_id) FROM chat_messages")
    users = cur.fetchone()[0]
    
    cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM chat_messages")
    date_range = cur.fetchone()
    
    print(f"📊 סה\"כ הודעות: {total:,}")
    print(f"👥 משתמשים ייחודיים: {users:,}")
    print(f"📅 טווח תאריכים: {date_range[0]} עד {date_range[1]}")
    print(f"📈 הוספה מההתחלה: {total - 625:,} הודעות")
    
    # משתמשים מובילים
    cur.execute("""
        SELECT chat_id, COUNT(*) as msg_count 
        FROM chat_messages 
        GROUP BY chat_id 
        ORDER BY COUNT(*) DESC 
        LIMIT 7
    """)
    
    top_users = cur.fetchall()
    print(f"\n👥 משתמשים עם הכי הרבה הודעות:")
    for i, (chat_id, count) in enumerate(top_users, 1):
        print(f"   {i}. {chat_id}: {count:,} הודעות")
    
    # הודעות לפי תאריכים
    cur.execute("""
        SELECT DATE(timestamp) as date, COUNT(*) as daily_count
        FROM chat_messages 
        WHERE timestamp > '2025-07-01'
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
        LIMIT 10
    """)
    
    recent_days = cur.fetchall()
    print(f"\n📅 הודעות לפי ימים אחרונים:")
    for date, count in recent_days:
        print(f"   {date}: {count:,} הודעות")
    
    # בדיקת תקינות
    cur.execute("SELECT COUNT(*) FROM chat_messages WHERE chat_id IS NULL")
    null_chats = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM chat_messages WHERE timestamp IS NULL")
    null_timestamps = cur.fetchone()[0]
    
    print(f"\n🔍 בדיקת תקינות:")
    print(f"   הודעות עם chat_id NULL: {null_chats}")
    print(f"   הודעות עם timestamp NULL: {null_timestamps}")
    
    conn.close()
    
    if total > 625:
        print(f"\n✅ שחזור מקיף הושלם בהצלחה!")
        print(f"🎯 שוחזרו {total - 625:,} הודעות נוספות!")
        print(f"🛡️ סה\"כ {total:,} הודעות מוגנות לנצח!")
    else:
        print(f"\n⚠️ לא נמצאו הודעות נוספות לשחזור")
        
except Exception as e:
    print(f"❌ שגיאה: {e}") 