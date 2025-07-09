#!/usr/bin/env python3
"""
☁️ מערכת גיבוי ענן למסד נתונים נפרד
שומר גיבויים במסד נתונים חיצוני כגיבוי נוסף
"""

import os
import json
import psycopg2
from datetime import datetime
from config import config
from simple_logger import logger
from admin_notifications import send_admin_notification

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

# 🌐 URL למסד גיבוי (נפרד מהמסד הראשי)
BACKUP_DB_URL = os.getenv("BACKUP_DATABASE_URL")  # מסד נתונים נפרד לגיבויים

def setup_backup_database():
    """יוצר מסד נתונים לגיבויים במסד נפרד"""
    if not BACKUP_DB_URL:
        logger.warning("⚠️ BACKUP_DATABASE_URL לא מוגדר - משתמש במסד הראשי")
        return DB_URL
    
    try:
        conn = psycopg2.connect(BACKUP_DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלת גיבויים
        cur.execute("""
            CREATE TABLE IF NOT EXISTS database_backups (
                id SERIAL PRIMARY KEY,
                backup_date DATE NOT NULL,
                table_name TEXT NOT NULL,
                backup_data JSONB NOT NULL,
                backup_size_mb DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                checksum TEXT,
                UNIQUE(backup_date, table_name)
            )
        """)
        
        # יצירת אינדקסים לביצועים
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_backups_date_table 
            ON database_backups(backup_date, table_name)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_backups_created 
            ON database_backups(created_at)
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info("✅ מסד גיבויים מוכן")
        return BACKUP_DB_URL
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהכנת מסד גיבויים: {e}")
        return DB_URL

def calculate_checksum(data):
    """מחשב checksum לנתונים לוודא שלמות"""
    import hashlib
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(json_str.encode()).hexdigest()

def backup_table_to_cloud(table_name, backup_date, data):
    """מגבה טבלה למסד ענן נפרד"""
    try:
        backup_db = setup_backup_database()
        conn = psycopg2.connect(backup_db)
        cur = conn.cursor()
        
        # חישוב נתונים
        data_size_mb = len(json.dumps(data, default=str)) / (1024 * 1024)
        checksum = calculate_checksum(data)
        
        # שמירת הגיבוי (UPSERT)
        cur.execute("""
            INSERT INTO database_backups 
            (backup_date, table_name, backup_data, backup_size_mb, checksum)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (backup_date, table_name)
            DO UPDATE SET 
                backup_data = EXCLUDED.backup_data,
                backup_size_mb = EXCLUDED.backup_size_mb,
                checksum = EXCLUDED.checksum,
                created_at = CURRENT_TIMESTAMP
        """, (backup_date, table_name, json.dumps(data, default=str), data_size_mb, checksum))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"☁️ גיבוי ענן {table_name}: {len(data)} רשומות ({data_size_mb:.2f}MB)")
        return True
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי ענן {table_name}: {e}")
        return False

def restore_from_cloud_backup(table_name, backup_date):
    """שחזור מגיבוי ענן"""
    try:
        backup_db = setup_backup_database()
        conn = psycopg2.connect(backup_db)
        cur = conn.cursor()
        
        # קריאת הגיבוי
        cur.execute("""
            SELECT backup_data, backup_size_mb, checksum, created_at
            FROM database_backups
            WHERE backup_date = %s AND table_name = %s
        """, (backup_date, table_name))
        
        result = cur.fetchone()
        if not result:
            print(f"❌ לא נמצא גיבוי ענן עבור {table_name} מתאריך {backup_date}")
            return False
        
        backup_data, size_mb, checksum, created_at = result
        
        # וידוא שלמות
        if calculate_checksum(backup_data) != checksum:
            print(f"❌ בעיה בשלמות הגיבוי עבור {table_name}")
            return False
        
        print(f"✅ נמצא גיבוי ענן תקין:")
        print(f"   📅 תאריך: {backup_date}")
        print(f"   📊 גודל: {size_mb:.2f}MB")
        print(f"   🕐 נוצר: {created_at}")
        print(f"   📝 רשומות: {len(backup_data)}")
        
        # אישור שחזור
        confirm = input("\nהאם לבצע שחזור מגיבוי הענן? (YES/no): ")
        if confirm != "YES":
            print("❌ שחזור בוטל")
            return False
        
        # ביצוע השחזור במסד הראשי
        main_conn = psycopg2.connect(DB_URL)
        main_cur = main_conn.cursor()
        
        # מחיקת נתונים נוכחיים
        main_cur.execute(f"DELETE FROM {table_name}")
        
        # שחזור הנתונים
        if backup_data:
            columns = list(backup_data[0].keys())
            placeholders = ', '.join(['%s'] * len(columns))
            
            insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            
            for row in backup_data:
                values = [row[col] for col in columns]
                main_cur.execute(insert_sql, values)
        
        main_conn.commit()
        main_cur.close()
        main_conn.close()
        
        cur.close()
        conn.close()
        
        print(f"✅ שחזור מגיבוי ענן הושלם: {len(backup_data)} רשומות")
        
        # התראה לאדמין
        send_admin_notification(
            f"🔄 **שחזור מגיבוי ענן**\n\n" +
            f"📊 **טבלה:** {table_name}\n" +
            f"📅 **תאריך גיבוי:** {backup_date}\n" +
            f"📝 **רשומות שוחזרו:** {len(backup_data)}\n" +
            f"💾 **גודל:** {size_mb:.2f}MB"
        )
        
        return True
        
    except Exception as e:
        print(f"❌ שגיאה בשחזור מגיבוי ענן: {e}")
        logger.error(f"❌ שגיאה בשחזור מגיבוי ענן: {e}")
        return False

def run_cloud_backup():
    """מריץ גיבוי ענן מלא"""
    try:
        logger.info("☁️ מתחיל גיבוי ענן")
        
        # קריאת הנתונים מהמסד הראשי
        from daily_backup import CRITICAL_TABLES, backup_table_to_json
        
        backup_date = datetime.now().strftime("%Y-%m-%d")
        successful_backups = 0
        
        for table in CRITICAL_TABLES:
            try:
                # קריאת הנתונים
                conn = psycopg2.connect(DB_URL)
                cur = conn.cursor()
                
                cur.execute(f"SELECT * FROM {table}")
                rows = cur.fetchall()
                
                # שליפת שמות העמודות
                cur.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}' 
                    ORDER BY ordinal_position
                """)
                columns = [row[0] for row in cur.fetchall()]
                
                # המרה ל-JSON
                data = []
                for row in rows:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        row_dict[col] = value
                    data.append(row_dict)
                
                cur.close()
                conn.close()
                
                # גיבוי לענן
                if backup_table_to_cloud(table, backup_date, data):
                    successful_backups += 1
                
            except Exception as e:
                logger.error(f"❌ שגיאה בגיבוי ענן {table}: {e}")
        
        if successful_backups == len(CRITICAL_TABLES):
            logger.info(f"☁️ גיבוי ענן הושלם בהצלחה: {successful_backups}/{len(CRITICAL_TABLES)} טבלאות")
            
            # התראה לאדמין
            send_admin_notification(
                f"☁️ **גיבוי ענן הושלם**\n\n" +
                f"✅ **טבלאות נוגבו:** {successful_backups}/{len(CRITICAL_TABLES)}\n" +
                f"📅 **תאריך:** {backup_date}\n" +
                f"🔒 **מיקום:** מסד נתונים נפרד"
            )
            
            return True
        else:
            logger.warning(f"⚠️ גיבוי ענן חלקי: {successful_backups}/{len(CRITICAL_TABLES)} טבלאות")
            return False
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי ענן: {e}")
        return False

def list_cloud_backups():
    """מציג רשימת גיבויים ענן זמינים"""
    try:
        backup_db = setup_backup_database()
        conn = psycopg2.connect(backup_db)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT backup_date, table_name, backup_size_mb, created_at
            FROM database_backups
            ORDER BY backup_date DESC, table_name
        """)
        
        backups = cur.fetchall()
        
        if not backups:
            print("📋 אין גיבויים ענן זמינים")
            return
        
        print("☁️ גיבויים ענן זמינים:")
        print("=" * 80)
        
        current_date = None
        for backup_date, table_name, size_mb, created_at in backups:
            if backup_date != current_date:
                current_date = backup_date
                print(f"\n📅 {backup_date}:")
            
            print(f"   📊 {table_name}: {size_mb:.2f}MB (נוצר: {created_at.strftime('%H:%M:%S')})")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בצפייה בגיבויים ענן: {e}")
        logger.error(f"❌ שגיאה בצפייה בגיבויים ענן: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "backup":
            run_cloud_backup()
        elif command == "list":
            list_cloud_backups()
        elif command == "restore":
            if len(sys.argv) < 4:
                print("שימוש: python cloud_backup.py restore <table_name> <backup_date>")
                print("דוגמה: python cloud_backup.py restore user_profiles 2025-01-09")
            else:
                table_name = sys.argv[2]
                backup_date = sys.argv[3]
                restore_from_cloud_backup(table_name, backup_date)
        else:
            print("שימוש: python cloud_backup.py [backup|list|restore]")
    else:
        # גיבוי רגיל
        run_cloud_backup() 