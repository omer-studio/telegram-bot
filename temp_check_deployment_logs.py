#!/usr/bin/env python3
"""
בדיקה האם deployment_logs נשמרים במסד הנתונים
"""
import os
import sys
import psycopg2
from datetime import datetime, timedelta

def check_deployment_logs():
    """בדיקה פשוטה של deployment_logs"""
    try:
        # חיבור למסד הנתונים
        # נטען מ-config.py
        try:
            from config import DB_URL
            database_url = DB_URL
        except ImportError:
            database_url = os.getenv('DATABASE_URL')
            
        if not database_url:
            print("❌ לא נמצא DATABASE_URL")
            return False
            
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # בדיקה שהטבלה קיימת
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'deployment_logs'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            print("❌ טבלת deployment_logs לא קיימת")
            return False
            
        print("✅ טבלת deployment_logs קיימת")
        
        # ספירה כללית
        cursor.execute("SELECT COUNT(*) FROM deployment_logs")
        total_count = cursor.fetchone()[0]
        print(f"📊 סך הכל רשומות: {total_count}")
        
        # בדיקת רשומות מהיום האחרון
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_logs 
            WHERE created_at >= NOW() - INTERVAL '1 day'
        """)
        recent_count = cursor.fetchone()[0]
        print(f"📅 רשומות מהיום האחרון: {recent_count}")
        
        # דוגמאות מהרשומות האחרונות
        cursor.execute("""
            SELECT created_at, LEFT(message, 100) as message_preview
            FROM deployment_logs 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        recent_logs = cursor.fetchall()
        
        print("\n🔍 דוגמאות מהרשומות האחרונות:")
        for log in recent_logs:
            print(f"  {log[0]} | {log[1]}...")
            
        # בדיקת רשומות מהשעה האחרונה
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_logs 
            WHERE created_at >= NOW() - INTERVAL '1 hour'
        """)
        last_hour_count = cursor.fetchone()[0]
        print(f"\n⏰ רשומות מהשעה האחרונה: {last_hour_count}")
        
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        return False

if __name__ == "__main__":
    print("🔍 בדיקת deployment_logs במסד הנתונים...")
    success = check_deployment_logs()
    
    if success:
        print("\n✅ הבדיקה הסתיימה בהצלחה")
    else:
        print("\n❌ הבדיקה נכשלה") 