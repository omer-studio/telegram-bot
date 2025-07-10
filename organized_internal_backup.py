#!/usr/bin/env python3
"""
🗄️ מערכת גיבוי פנימי מסודרת במסד הנתונים
יוצרת schema "backup" עם טבלאות מסודרות לכל תאריך
כמו תיקיות אבל במסד נתונים - מתמשך ב-Render!
"""

import psycopg2
from datetime import datetime, timedelta
from config import config
from simple_logger import logger
from admin_notifications import send_admin_notification

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

# 🎯 הגדרות גיבוי פנימי מסודר
TABLES_TO_BACKUP = ["user_profiles", "chat_messages", "gpt_calls_log"]
BACKUP_SCHEMA = "backup"
BACKUP_RETENTION_DAYS = 30

def create_backup_schema():
    """יוצר את ה-schema לגיבוי אם לא קיים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת schema אם לא קיים
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {BACKUP_SCHEMA}")
        conn.commit()
        
        cur.close()
        conn.close()
        
        logger.info(f"✅ Schema {BACKUP_SCHEMA} מוכן")
        return True
        
    except Exception as e:
        logger.error(f"❌ שגיאה ביצירת backup schema: {e}")
        return False

def backup_table_to_internal_organized(table_name, backup_date):
    """מגבה טבלה לטבלת גיבוי מסודרת במסד נתונים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # שם הטבלה המסודרת
        backup_table_name = f"{table_name}_backup_{backup_date}"
        full_backup_table = f"{BACKUP_SCHEMA}.{backup_table_name}"
        
        # מחיקת הטבלה אם קיימת (גיבוי מחדש)
        cur.execute(f"DROP TABLE IF EXISTS {full_backup_table}")
        
        # יצירת הטבלה החדשה עם נתוני הגיבוי
        cur.execute(f"""
            CREATE TABLE {full_backup_table} AS 
            SELECT *, 
                   '{backup_date}' as backup_date,
                   '{datetime.now().isoformat()}' as backup_timestamp
            FROM {table_name}
        """)
        
        # קבלת מספר הרשומות שנוספו
        cur.execute(f"SELECT COUNT(*) FROM {full_backup_table}")
        records_count = cur.fetchone()[0]
        
        # קבלת גודל הטבלה
        cur.execute(f"""
            SELECT pg_size_pretty(pg_total_relation_size('{full_backup_table}'))
        """)
        table_size = cur.fetchone()[0]
        
        conn.commit()
        cur.close()
        conn.close()
        
        backup_info = {
            "table_name": table_name,
            "backup_table_name": backup_table_name,
            "full_backup_table": full_backup_table,
            "records_count": records_count,
            "table_size": table_size,
            "backup_date": backup_date,
            "confirmation_code": f"IB-{table_name.upper()[:3]}-{backup_date}-{records_count:04d}",
            "backup_timestamp": datetime.now()
        }
        
        logger.info(f"✅ {table_name} → {backup_table_name}: {records_count} רשומות ({table_size})")
        return backup_info
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי {table_name}: {e}")
        return None

def run_organized_internal_backup():
    """מריץ גיבוי פנימי מסודר מלא"""
    try:
        backup_date = datetime.now().strftime("%d_%m_%Y")
        logger.info(f"🗄️ מתחיל גיבוי פנימי מסודר לתאריך {backup_date}")
        
        # יצירת schema הגיבוי
        if not create_backup_schema():
            return False
        
        # גיבוי כל טבלה
        backup_results = {}
        total_records = 0
        
        for table_name in TABLES_TO_BACKUP:
            backup_info = backup_table_to_internal_organized(table_name, backup_date)
            
            if backup_info:
                backup_results[table_name] = backup_info
                total_records += backup_info["records_count"]
        
        # בדיקת הצלחה
        if len(backup_results) == len(TABLES_TO_BACKUP):
            logger.info(f"🎉 גיבוי פנימי מסודר הושלם: {total_records} רשומות ב-{len(backup_results)} טבלאות")
            
            # השוואה ליום קודם
            yesterday_comparison = compare_with_yesterday_internal(backup_date, backup_results)
            
            # שליחת התראה מפורטת
            send_detailed_internal_backup_notification(backup_results, total_records, yesterday_comparison)
            
            return True
        else:
            logger.error(f"❌ גיבוי פנימי מסודר נכשל: {len(backup_results)}/{len(TABLES_TO_BACKUP)} טבלאות")
            return False
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי פנימי מסודר: {e}")
        return False

def compare_with_yesterday_internal(today_date, today_results):
    """משווה את הגיבוי של היום עם אמש במסד נתונים"""
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%d_%m_%Y")
        comparison = {}
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        for table_name, today_info in today_results.items():
            yesterday_table = f"{BACKUP_SCHEMA}.{table_name}_backup_{yesterday}"
            
            # בדיקה אם הטבלה של אמש קיימת
            cur.execute(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = '{BACKUP_SCHEMA}' 
                    AND table_name = '{table_name}_backup_{yesterday}'
                )
            """)
            table_exists = cur.fetchone()[0]
            
            if table_exists:
                # קבלת מספר הרשומות מאמש
                cur.execute(f"SELECT COUNT(*) FROM {yesterday_table}")
                yesterday_records = cur.fetchone()[0]
                
                # קבלת גודל הטבלה מאמש
                cur.execute(f"""
                    SELECT pg_size_pretty(pg_total_relation_size('{yesterday_table}'))
                """)
                yesterday_size = cur.fetchone()[0]
                
                comparison[table_name] = {
                    "yesterday_records": yesterday_records,
                    "today_records": today_info["records_count"],
                    "records_diff": today_info["records_count"] - yesterday_records,
                    "yesterday_size": yesterday_size,
                    "today_size": today_info["table_size"],
                    "has_yesterday": True
                }
            else:
                comparison[table_name] = {
                    "yesterday_records": 0,
                    "today_records": today_info["records_count"],
                    "records_diff": today_info["records_count"],
                    "yesterday_size": "0 bytes",
                    "today_size": today_info["table_size"],
                    "has_yesterday": False
                }
        
        cur.close()
        conn.close()
        
        return comparison
        
    except Exception as e:
        logger.warning(f"⚠️ שגיאה בהשוואה עם אמש: {e}")
        return {}

def send_detailed_internal_backup_notification(backup_results, total_records, yesterday_comparison):
    """שולח התראה מפורטת על הגיבוי הפנימי המסודר"""
    try:
        backup_time = datetime.now()
        
        # כותרת ההודעה - קומפקטית יותר
        notification = f"🗄️ **גיבוי מסודר יומי הושלם בהצלחה**\n\n"
        notification += f"📅 **{backup_time.strftime('%d/%m/%Y %H:%M')}**\n"
        notification += f"📊 **סה\"כ:** {total_records:,} רשומות ב-{len(backup_results)} טבלאות\n"
        notification += f"🏗️ **Schema:** `{BACKUP_SCHEMA}`\n\n"
        
        # פירוט קומפקטי לכל טבלה
        notification += f"📋 **פירוט טבלאות:**\n"
        for table_name, info in backup_results.items():
            # שם קצר לטבלה
            table_short = table_name.replace("_", " ").title()[:15]
            notification += f"• **{table_short}:** {info['records_count']:,} רשומות ({info['table_size']})\n"
            
            # השוואה עם אמש - קומפקטית
            if table_name in yesterday_comparison:
                comp = yesterday_comparison[table_name]
                if comp["has_yesterday"]:
                    records_change = comp["records_diff"]
                    
                    if records_change > 0:
                        notification += f"  📈 +{records_change} מאתמול\n"
                    elif records_change < 0:
                        notification += f"  📉 {records_change} מאתמול\n"
                    else:
                        notification += f"  ➖ ללא שינוי\n"
                else:
                    notification += f"  🆕 גיבוי ראשון\n"
        
        # קודי אישור
        notification += f"\n🔐 **קודי אישור:**\n"
        for table_name, info in backup_results.items():
            notification += f"• `{info['confirmation_code']}`\n"
        
        # מיקום ומדיניות - קומפקטי
        notification += f"\n📍 **מיקום:** PostgreSQL/{BACKUP_SCHEMA}\n"
        notification += f"🗓️ **שמירה:** {BACKUP_RETENTION_DAYS} ימים\n"
        notification += f"☁️ **מתמשך ב-Render** - לא נמחק!"
        
        send_admin_notification(notification)
        
    except Exception as e:
        logger.error(f"❌ שגיאה בשליחת התראה מפורטת: {e}")
        # גיבוי - הודעה קצרה אם הארוכה נכשלת
        try:
            backup_summary = f"✅ **גיבוי מסודר הושלם**\n"
            backup_summary += f"📊 {total_records:,} רשומות ב-{len(backup_results)} טבלאות\n"
            backup_summary += f"📅 {backup_time.strftime('%d/%m/%Y %H:%M')}"
            send_admin_notification(backup_summary)
        except Exception as e2:
            logger.error(f"❌ שגיאה גם בהודעה הקצרה: {e2}")

def list_organized_internal_backups():
    """מציג רשימת גיבויים פנימיים מסודרים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # קבלת כל הטבלאות ב-schema הגיבוי
        cur.execute(f"""
            SELECT table_name, 
                   pg_size_pretty(pg_total_relation_size('{BACKUP_SCHEMA}.' || table_name)) as size
            FROM information_schema.tables 
            WHERE table_schema = '{BACKUP_SCHEMA}'
            ORDER BY table_name DESC
        """)
        
        backup_tables = cur.fetchall()
        
        if not backup_tables:
            print("📭 אין גיבויים פנימיים מסודרים")
            return
        
        print("🗄️ גיבויים פנימיים מסודרים זמינים:")
        print("=" * 60)
        
        # קיבוץ לפי טבלה מקורית
        grouped_backups = {}
        for table_name, size in backup_tables:
            # חילוץ שם הטבלה המקורית
            if "_backup_" in table_name:
                original_table = table_name.split("_backup_")[0]
                if original_table not in grouped_backups:
                    grouped_backups[original_table] = []
                grouped_backups[original_table].append((table_name, size))
        
        for original_table, backups in grouped_backups.items():
            print(f"\n📂 {original_table}:")
            
            for backup_table, size in backups[:10]:  # הצג עד 10 אחרונים
                # חילוץ תאריך הגיבוי
                backup_date = backup_table.split("_backup_")[-1]
                
                # קבלת מספר הרשומות
                cur.execute(f"SELECT COUNT(*) FROM {BACKUP_SCHEMA}.{backup_table}")
                records_count = cur.fetchone()[0]
                
                # קבלת זמן הגיבוי
                cur.execute(f"""
                    SELECT backup_timestamp FROM {BACKUP_SCHEMA}.{backup_table} 
                    LIMIT 1
                """)
                result = cur.fetchone()
                backup_timestamp = result[0] if result else "unknown"
                
                print(f"   📄 {backup_table}")
                print(f"      📅 {backup_date} | 📊 {records_count:,} רשומות | 💾 {size}")
                print(f"      🕐 {backup_timestamp}")
            
            if len(backups) > 10:
                print(f"   ... ועוד {len(backups) - 10} גיבויים")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בצפייה בגיבויים: {e}")
        logger.error(f"❌ שגיאה בצפייה בגיבויים: {e}")

def cleanup_old_organized_internal_backups(days_to_keep=30):
    """מנקה גיבויים פנימיים מסודרים ישנים"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_date_str = cutoff_date.strftime("%d_%m_%Y")
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # קבלת כל הטבלאות ב-schema הגיבוי
        cur.execute(f"""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = '{BACKUP_SCHEMA}'
            AND table_name LIKE '%_backup_%'
        """)
        
        backup_tables = cur.fetchall()
        deleted_tables = 0
        
        for (table_name,) in backup_tables:
            try:
                # חילוץ תאריך הגיבוי
                if "_backup_" in table_name:
                    backup_date_str = table_name.split("_backup_")[-1]
                    
                    # המרת תאריך לפורמט datetime
                    backup_date = datetime.strptime(backup_date_str, "%d_%m_%Y")
                    
                    # בדיקה אם הטבלה ישנה מדי
                    if backup_date < cutoff_date:
                        cur.execute(f"DROP TABLE {BACKUP_SCHEMA}.{table_name}")
                        deleted_tables += 1
                        logger.info(f"🗑️ נמחקה טבלה ישנה: {table_name}")
                        
            except Exception as e:
                logger.warning(f"⚠️ שגיאה בבדיקת תאריך {table_name}: {e}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        if deleted_tables > 0:
            logger.info(f"🧹 נמחקו {deleted_tables} טבלאות גיבוי ישנות")
            
            send_admin_notification(
                f"🧹 **ניקוי גיבויים פנימיים מסודרים**\n\n" +
                f"🗑️ **נמחקו:** {deleted_tables} טבלאות\n" +
                f"📅 **ישנות מ:** {cutoff_date.strftime('%d/%m/%Y')}\n" +
                f"💾 **שמירת:** {days_to_keep} ימים אחרונים\n" +
                f"🗃️ **Schema:** `{BACKUP_SCHEMA}`"
            )
        else:
            logger.info("🧹 אין טבלאות גיבוי ישנות למחיקה")
        
    except Exception as e:
        logger.error(f"❌ שגיאה בניקוי גיבויים: {e}")

def get_backup_storage_info():
    """מחזיר מידע על שטח הגיבוי במסד נתונים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # גודל schema הגיבוי
        cur.execute(f"""
            SELECT 
                pg_size_pretty(
                    sum(pg_total_relation_size('{BACKUP_SCHEMA}.' || table_name))
                ) as total_backup_size
            FROM information_schema.tables 
            WHERE table_schema = '{BACKUP_SCHEMA}'
        """)
        
        result = cur.fetchone()
        total_backup_size = result[0] if result and result[0] else "0 bytes"
        
        # מספר טבלאות גיבוי
        cur.execute(f"""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = '{BACKUP_SCHEMA}'
        """)
        
        backup_tables_count = cur.fetchone()[0]
        
        # גודל מסד נתונים כללי
        cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
        total_db_size = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return {
            "total_backup_size": total_backup_size,
            "backup_tables_count": backup_tables_count,
            "total_db_size": total_db_size,
            "backup_schema": BACKUP_SCHEMA
        }
        
    except Exception as e:
        logger.error(f"❌ שגיאה בקבלת מידע אחסון: {e}")
        return None

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "backup":
            run_organized_internal_backup()
        elif command == "list":
            list_organized_internal_backups()
        elif command == "cleanup":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            cleanup_old_organized_internal_backups(days)
        elif command == "info":
            info = get_backup_storage_info()
            if info:
                print(f"🗃️ Schema: {info['backup_schema']}")
                print(f"📊 טבלאות גיבוי: {info['backup_tables_count']}")
                print(f"💾 גודל גיבוי: {info['total_backup_size']}")
                print(f"🗄️ גודל מסד כללי: {info['total_db_size']}")
        else:
            print("שימוש: python organized_internal_backup.py [backup|list|cleanup|info]")
    else:
        # גיבוי רגיל
        run_organized_internal_backup() 