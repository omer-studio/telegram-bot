#!/usr/bin/env python3
"""
🏠 מערכת גיבוי פנימית במסד הנתונים
יוצרת "תיקיות" (schemas) בתוך אותו מסד נתונים
כל יום = תיקיה חדשה עם כל הטבלאות החשובות
"""

import psycopg2
from datetime import datetime, timedelta
from config import config
from simple_logger import logger
from admin_notifications import send_admin_notification

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

# 🔒 טבלאות קריטיות לגיבוי
CRITICAL_TABLES = [
    "user_profiles",     # הלב של המערכת
    "chat_messages",     # כל היסטוריית השיחות  
    "interactions_log"   # כל הקריאות והעלויות (החליפה את gpt_calls_log)
]

def create_backup_schema(backup_date):
    """יוצר schema חדש לגיבוי (כמו תיקיה)"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        schema_name = f"backup_{backup_date}"
        
        # יצירת schema חדש
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
        
        # הוספת הערה לschema
        cur.execute(f"""
            COMMENT ON SCHEMA {schema_name} IS 
            'גיבוי אוטומטי מתאריך {backup_date} - נוצר בשעה {datetime.now().strftime("%H:%M:%S")}'
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"📁 נוצר schema גיבוי: {schema_name}")
        return schema_name
        
    except Exception as e:
        logger.error(f"❌ שגיאה ביצירת schema גיבוי: {e}")
        return None

def backup_table_to_schema(table_name, schema_name):
    """מגבה טבלה לschema הגיבוי"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # שליפת מבנה הטבלה המקורית
        cur.execute(f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        columns_info = cur.fetchall()
        
        if not columns_info:
            logger.warning(f"⚠️ טבלה {table_name} לא נמצאה")
            return False
        
        # בניית CREATE TABLE statement
        create_columns = []
        for col_name, data_type, is_nullable, col_default in columns_info:
            col_def = f"{col_name} {data_type}"
            
            if is_nullable == 'NO':
                col_def += " NOT NULL"
            
            if col_default:
                col_def += f" DEFAULT {col_default}"
            
            create_columns.append(col_def)
        
        create_table_sql = f"""
            CREATE TABLE {schema_name}.{table_name} (
                {', '.join(create_columns)}
            )
        """
        
        # יצירת טבלת גיבוי
        cur.execute(create_table_sql)
        
        # העתקת הנתונים
        cur.execute(f"""
            INSERT INTO {schema_name}.{table_name} 
            SELECT * FROM public.{table_name}
        """)
        
        rows_copied = cur.rowcount
        
        # הוספת הערה לטבלה
        cur.execute(f"""
            COMMENT ON TABLE {schema_name}.{table_name} IS 
            'גיבוי של {table_name} - {rows_copied} רשומות מתאריך {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ גיבוי {table_name}: {rows_copied} רשומות ל-{schema_name}")
        return rows_copied
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי {table_name}: {e}")
        return False

def run_internal_backup():
    """מריץ גיבוי פנימי מלא"""
    try:
        backup_date = datetime.now().strftime("%Y%m%d")
        logger.info(f"🏠 מתחיל גיבוי פנימי לתאריך {backup_date}")
        
        # יצירת schema לגיבוי היום
        schema_name = create_backup_schema(backup_date)
        if not schema_name:
            return False
        
        # גיבוי כל טבלה קריטית
        backup_results = {}
        total_rows = 0
        
        for table in CRITICAL_TABLES:
            rows_backed_up = backup_table_to_schema(table, schema_name)
            backup_results[table] = rows_backed_up
            
            if rows_backed_up:
                total_rows += rows_backed_up
        
        # סיכום
        successful_tables = len([t for t in backup_results.values() if t])
        
        if successful_tables == len(CRITICAL_TABLES):
            logger.info(f"🎉 גיבוי פנימי הושלם: {total_rows} רשומות ב-{successful_tables} טבלאות")
            
            # הוספת מטא-מידע לschema
            add_backup_metadata(schema_name, backup_results, total_rows)
            
            # התראה לאדמין
            send_admin_notification(
                f"🏠 **גיבוי פנימי הושלם**\n\n" +
                f"📁 **Schema:** `{schema_name}`\n" +
                f"📊 **סה\"כ רשומות:** {total_rows:,}\n" +
                f"📋 **טבלאות:** {successful_tables}/{len(CRITICAL_TABLES)}\n\n" +
                f"🔍 **פירוט:**\n" +
                f"👥 user_profiles: {backup_results.get('user_profiles', 0):,}\n" +
                f"💬 chat_messages: {backup_results.get('chat_messages', 0):,}\n" +
                f"🔄 interactions_log: {backup_results.get('interactions_log', 0):,}\n\n" +
                f"🔒 **הנתונים מוגנים באותו מסד נתונים**"
            )
            
            return True
        else:
            logger.error(f"❌ גיבוי פנימי נכשל: {successful_tables}/{len(CRITICAL_TABLES)} טבלאות")
            return False
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי פנימי: {e}")
        return False

def add_backup_metadata(schema_name, backup_results, total_rows):
    """מוסיף טבלת מטא-מידע לגיבוי"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלת מטא-מידע
        cur.execute(f"""
            CREATE TABLE {schema_name}.backup_metadata (
                backup_date DATE NOT NULL,
                backup_time TIMESTAMP NOT NULL,
                table_name TEXT NOT NULL,
                rows_count INTEGER NOT NULL,
                backup_size_estimate TEXT,
                created_by TEXT DEFAULT 'internal_backup_system'
            )
        """)
        
        # הוספת נתוני מטא לכל טבלה
        backup_time = datetime.now()
        backup_date = backup_time.date()
        
        for table_name, rows_count in backup_results.items():
            if rows_count:
                # אומדן גודל
                if table_name == "chat_messages":
                    size_estimate = f"~{rows_count * 0.5:.1f}KB"
                elif table_name == "interactions_log":
                    size_estimate = f"~{rows_count * 5:.1f}KB"  # טבלה יותר מפורטת
                else:
                    size_estimate = f"~{rows_count * 0.1:.1f}KB"
                
                cur.execute(f"""
                    INSERT INTO {schema_name}.backup_metadata 
                    (backup_date, backup_time, table_name, rows_count, backup_size_estimate)
                    VALUES (%s, %s, %s, %s, %s)
                """, (backup_date, backup_time, table_name, rows_count, size_estimate))
        
        # הוספת רשומת סיכום
        cur.execute(f"""
            INSERT INTO {schema_name}.backup_metadata 
            (backup_date, backup_time, table_name, rows_count, backup_size_estimate)
            VALUES (%s, %s, %s, %s, %s)
        """, (backup_date, backup_time, "TOTAL_SUMMARY", total_rows, f"~{total_rows * 0.8:.1f}KB"))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"📋 נוסף מטא-מידע לגיבוי {schema_name}")
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהוספת מטא-מידע: {e}")

def list_internal_backups():
    """מציג רשימת גיבויים פנימיים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # חיפוש schemas של גיבוי
        cur.execute("""
            SELECT schema_name, 
                   obj_description(oid, 'pg_namespace') as description
            FROM information_schema.schemata s
            JOIN pg_namespace n ON n.nspname = s.schema_name
            WHERE schema_name LIKE 'backup_%'
            ORDER BY schema_name DESC
        """)
        
        backups = cur.fetchall()
        
        if not backups:
            print("📁 לא נמצאו גיבויים פנימיים")
            return
        
        print("🏠 גיבויים פנימיים זמינים:")
        print("=" * 60)
        
        for schema_name, description in backups:
            backup_date = schema_name.replace("backup_", "")
            
            # פירמוט תאריך
            try:
                date_obj = datetime.strptime(backup_date, "%Y%m%d")
                formatted_date = date_obj.strftime("%d/%m/%Y")
            except:
                formatted_date = backup_date
            
            print(f"\n📅 {formatted_date} (Schema: {schema_name})")
            
            if description:
                print(f"   📝 {description}")
            
            # הצגת פרטי טבלאות
            try:
                cur.execute(f"""
                    SELECT table_name, 
                           obj_description(oid, 'pg_class') as table_comment
                    FROM information_schema.tables t
                    LEFT JOIN pg_class c ON c.relname = t.table_name
                    WHERE table_schema = '{schema_name}' 
                      AND table_name != 'backup_metadata'
                    ORDER BY table_name
                """)
                
                tables = cur.fetchall()
                for table_name, table_comment in tables:
                    if table_comment:
                        rows_count = table_comment.split(" - ")[1].split(" רשומות")[0] if " - " in table_comment else "?"
                        print(f"   📊 {table_name}: {rows_count} רשומות")
                    else:
                        print(f"   📊 {table_name}")
            except:
                pass
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בצפייה בגיבויים: {e}")
        logger.error(f"❌ שגיאה בצפייה בגיבויים: {e}")

def restore_from_internal_backup(backup_date, table_name=None):
    """שחזור מגיבוי פנימי"""
    try:
        schema_name = f"backup_{backup_date}"
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקה שהschema קיים
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata 
            WHERE schema_name = %s
        """, (schema_name,))
        
        if not cur.fetchone():
            print(f"❌ גיבוי מתאריך {backup_date} לא נמצא")
            return False
        
        # רשימת טבלאות לשחזור
        tables_to_restore = [table_name] if table_name else CRITICAL_TABLES
        
        print(f"🔄 שחזור מגיבוי {backup_date}")
        print(f"📊 טבלאות לשחזור: {', '.join(tables_to_restore)}")
        
        # אישור אחרון
        confirm = input("\n⚠️ האם אתה בטוח? זה ימחק את הנתונים הנוכחיים! (YES/no): ")
        if confirm != "YES":
            print("❌ שחזור בוטל")
            return False
        
        restored_tables = 0
        for table in tables_to_restore:
            try:
                # בדיקה שהטבלה קיימת בגיבוי
                cur.execute(f"""
                    SELECT COUNT(*) FROM {schema_name}.{table}
                """)
                backup_rows = cur.fetchone()[0]
                
                # מחיקת נתונים נוכחיים
                cur.execute(f"DELETE FROM public.{table}")
                
                # שחזור הנתונים
                cur.execute(f"""
                    INSERT INTO public.{table} 
                    SELECT * FROM {schema_name}.{table}
                """)
                
                restored_rows = cur.rowcount
                restored_tables += 1
                
                print(f"✅ {table}: {restored_rows} רשומות שוחזרו")
                
            except Exception as e:
                print(f"❌ שגיאה בשחזור {table}: {e}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        if restored_tables > 0:
            print(f"\n🎉 שחזור הושלם: {restored_tables} טבלאות")
            
            # התראה לאדמין
            send_admin_notification(
                f"🔄 **שחזור מגיבוי פנימי**\n\n" +
                f"📅 **תאריך גיבוי:** {backup_date}\n" +
                f"📊 **טבלאות שוחזרו:** {restored_tables}\n" +
                f"🔒 **מקור:** Schema {schema_name}"
            )
            
            return True
        else:
            print("❌ שחזור נכשל")
            return False
        
    except Exception as e:
        print(f"❌ שגיאה בשחזור: {e}")
        logger.error(f"❌ שגיאה בשחזור: {e}")
        return False

def cleanup_old_internal_backups(days_to_keep=30):
    """מחיקת גיבויים פנימיים ישנים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.strftime("%Y%m%d")
        
        # חיפוש schemas ישנים
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata 
            WHERE schema_name LIKE 'backup_%' 
              AND schema_name < %s
            ORDER BY schema_name
        """, (f"backup_{cutoff_str}",))
        
        old_schemas = [row[0] for row in cur.fetchall()]
        
        if not old_schemas:
            logger.info("🧹 אין גיבויים ישנים למחיקה")
            return
        
        deleted_schemas = 0
        for schema in old_schemas:
            try:
                cur.execute(f"DROP SCHEMA {schema} CASCADE")
                deleted_schemas += 1
                logger.info(f"🗑️ נמחק גיבוי ישן: {schema}")
            except Exception as e:
                logger.error(f"❌ שגיאה במחיקת {schema}: {e}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        if deleted_schemas > 0:
            logger.info(f"🧹 נמחקו {deleted_schemas} גיבויים ישנים")
            
            send_admin_notification(
                f"🧹 **ניקוי גיבויים ישנים**\n\n" +
                f"🗑️ **נמחקו:** {deleted_schemas} גיבויים\n" +
                f"📅 **ישנים מ:** {cutoff_date.strftime('%d/%m/%Y')}\n" +
                f"💾 **שמירת:** {days_to_keep} ימים אחרונים"
            )
        
    except Exception as e:
        logger.error(f"❌ שגיאה בניקוי גיבויים ישנים: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "backup":
            run_internal_backup()
        elif command == "list":
            list_internal_backups()
        elif command == "restore":
            if len(sys.argv) < 3:
                print("שימוש: python internal_backup_system.py restore <backup_date> [table_name]")
                print("דוגמה: python internal_backup_system.py restore 20250109")
                print("דוגמה: python internal_backup_system.py restore 20250109 user_profiles")
            else:
                backup_date = sys.argv[2]
                table_name = sys.argv[3] if len(sys.argv) > 3 else None
                restore_from_internal_backup(backup_date, table_name)
        elif command == "cleanup":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            cleanup_old_internal_backups(days)
        else:
            print("שימוש: python internal_backup_system.py [backup|list|restore|cleanup]")
    else:
        # גיבוי רגיל
        run_internal_backup() 