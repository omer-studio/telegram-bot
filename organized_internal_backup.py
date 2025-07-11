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
TABLES_TO_BACKUP = ["user_profiles", "chat_messages", "interactions_log"]
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
                
                # 🚨 הגנה מפני ירידות דרסטיות ב-chat_messages
                records_diff = today_info["records_count"] - yesterday_records
                if table_name == "chat_messages" and records_diff < -10:
                    logger.error(f"🚨 ALERT: {table_name} ירד ב-{abs(records_diff)} הודעות! זה חשוד למחיקה!")
                    send_admin_notification(
                        f"🚨 **אזהרת מחיקה חשודה!**\n\n" +
                        f"📋 **טבלה:** {table_name}\n" +
                        f"📊 **אתמול:** {yesterday_records:,} הודעות\n" +
                        f"📊 **היום:** {today_info['records_count']:,} הודעות\n" +
                        f"📉 **ירידה:** {abs(records_diff):,} הודעות\n\n" +
                        f"⚠️ **chat_messages אמור רק לצבור ולא למחוק!**\n" +
                        f"🔍 **בדוק אם מישהו הריץ מחיקה או clear_user_from_database**",
                        urgent=True
                    )
                
                comparison[table_name] = {
                    "yesterday_records": yesterday_records,
                    "today_records": today_info["records_count"],
                    "records_diff": records_diff,
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

def generate_visual_backup_tree(backup_results, yesterday_comparison):
    """יוצר תצוגה ויזואלית של מבנה תיקיות הגיבוי"""
    tree = f"```\n{BACKUP_SCHEMA}/\n"
    
    # מיפוי שמות לתיקיות ויזואליות
    folder_mapping = {
        "user_profiles": "user_profile_backup",
        "chat_messages": "chat_history_backup", 
        "interactions_log": "interactions_backup"  # החליפה את gpt_calls_log
    }
    
    table_count = len(backup_results)
    for i, (table_name, info) in enumerate(backup_results.items()):
        is_last_table = (i == table_count - 1)
        folder_prefix = "└── " if is_last_table else "├── "
        
        # שם התיקיה הויזואלית
        visual_folder = folder_mapping.get(table_name, f"{table_name}_backup")
        tree += f"{folder_prefix}📁 {visual_folder}/\n"
        
        # קבלת גיבויים קודמים לאותה טבלה 
        previous_backups = get_previous_backups_for_table(table_name)
        
        # הוספת הגיבוי הנוכחי לרשימה
        all_backups = previous_backups + [info]
        all_backups = sorted(all_backups, key=lambda x: x.get('backup_date', ''), reverse=True)
        
        # הצגת עד 3 גיבויים אחרונים
        backups_to_show = all_backups[:3]
        
        for j, backup in enumerate(backups_to_show):
            is_last_backup = (j == len(backups_to_show) - 1)
            is_today = backup.get('backup_date') == datetime.now().strftime("%d_%m_%Y")
            
            if is_last_table:
                backup_prefix = "    └── " if is_last_backup else "    ├── "
            else:
                backup_prefix = "│   └── " if is_last_backup else "│   ├── "
            
            # פורמט הקובץ הויזואלי  
            file_name = f"{visual_folder.replace('_backup', '')}_backup_{backup.get('backup_date', 'unknown')}.json"
            size_info = backup.get('table_size', 'unknown')
            
            # סימון הגיבוי של היום
            today_marker = " 🆕" if is_today else ""
            
            # השוואה עם אמש
            change_info = ""
            if is_today and table_name in yesterday_comparison:
                comp = yesterday_comparison[table_name]
                if comp["has_yesterday"]:
                    records_change = comp["records_diff"]
                    if records_change > 0:
                        change_info = f" (+{records_change})"
                    elif records_change < 0:
                        change_info = f" ({records_change})"
            
            tree += f"{backup_prefix}{file_name}  ({size_info}){change_info}{today_marker}\n"
        
        # אם יש יותר גיבויים
        if len(all_backups) > 3:
            remaining = len(all_backups) - 3
            if is_last_table:
                tree += f"    └── ... ועוד {remaining} גיבויים\n"
            else:
                tree += f"│   └── ... ועוד {remaining} גיבויים\n"
    
    tree += "```"
    return tree

def get_previous_backups_for_table(table_name):
    """מקבל רשימת גיבויים קודמים לטבלה מסוימת מהמסד"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # קבלת כל הטבלאות של אותו סוג מהמסד
        cur.execute(f"""
            SELECT table_name, 
                   pg_size_pretty(pg_total_relation_size('{BACKUP_SCHEMA}.' || table_name)) as size
            FROM information_schema.tables 
            WHERE table_schema = '{BACKUP_SCHEMA}'
            AND table_name LIKE '{table_name}_backup_%'
            AND table_name != '{table_name}_backup_{datetime.now().strftime("%d_%m_%Y")}'
            ORDER BY table_name DESC
        """)
        
        backup_tables = cur.fetchall()
        previous_backups = []
        
        for backup_table_name, size in backup_tables:
            # חילוץ תאריך הגיבוי
            backup_date = backup_table_name.split("_backup_")[-1]
            
            previous_backups.append({
                "table_name": table_name,
                "backup_table_name": backup_table_name,
                "backup_date": backup_date,
                "table_size": size
            })
        
        cur.close()
        conn.close()
        
        return previous_backups
        
    except Exception as e:
        logger.warning(f"⚠️ שגיאה בקבלת גיבויים קודמים ל-{table_name}: {e}")
        return []

def send_detailed_internal_backup_notification(backup_results, total_records, yesterday_comparison):
    """שולח התראה מפורטת עם תצוגה ויזואלית של הגיבוי הפנימי המסודר"""
    try:
        backup_time = datetime.now()
        
        # כותרת ההודעה
        notification = f"🗄️ **גיבוי מסודר יומי הושלם בהצלחה**\n\n"
        notification += f"📅 **{backup_time.strftime('%d/%m/%Y %H:%M')}**\n"
        notification += f"📊 **סה\"כ:** {total_records:,} רשומות ב-{len(backup_results)} טבלאות\n"
        notification += f"🔒 **אבטחה:** גיבוי אך ורק במסד נתונים\n\n"
        
        # 🎨 תצוגה ויזואלית של מבנה התיקיות
        notification += f"📂 **מבנה גיבוי ויזואלי:**\n"
        visual_tree = generate_visual_backup_tree(backup_results, yesterday_comparison)
        notification += f"{visual_tree}\n\n"
        
        # 🔧 פרטים טכניים מדויקים עם מספר שורות
        notification += f"⚙️ **פרטים טכניים מדויקים:**\n"
        for table_name, info in backup_results.items():
            table_short = table_name.replace("_", " ").title()[:15]
            notification += f"• **{table_short}:** {info['records_count']:,} שורות\n"
        
        # השוואה עם אתמול - מספרים מדויקים
        if yesterday_comparison:
            notification += f"\n📈 **השוואה מדויקת עם אתמול:**\n"
            for table_name, comp in yesterday_comparison.items():
                if comp["has_yesterday"]:
                    diff = comp["records_diff"]
                    if diff > 0:
                        notification += f"• **{table_name.replace('_', ' ').title()}:** +{diff:,} שורות\n"
                    elif diff < 0:
                        notification += f"• **{table_name.replace('_', ' ').title()}:** {diff:,} שורות ⚠️\n"
                    else:
                        notification += f"• **{table_name.replace('_', ' ').title()}:** ללא שינוי\n"
        
        # קודי אישור
        notification += f"\n🔐 **קודי אישור:**\n"
        for table_name, info in backup_results.items():
            notification += f"• `{info['confirmation_code']}`\n"
        
        # מיקום ומדיניות
        notification += f"\n📍 **Schema:** `{BACKUP_SCHEMA}` | "
        notification += f"🗓️ **שמירה:** {BACKUP_RETENTION_DAYS} ימים | "
        notification += f"☁️ **מתמשך ב-Render**"
        
        send_admin_notification(notification)
        
    except Exception as e:
        logger.error(f"❌ שגיאה בשליחת התראה מפורטת: {e}")
        # גיבוי - הודעה קצרה אם הארוכה נכשלת
        try:
            backup_summary = f"✅ **גיבוי מסודר הושלם**\n"
            backup_summary += f"📊 {total_records:,} רשומות ב-{len(backup_results)} טבלאות\n"
            backup_summary += f"📅 {backup_time.strftime('%d/%m/%Y %H:%M')}\n"
            backup_summary += f"🔒 אך ורק במסד נתונים"
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

def cleanup_old_organized_internal_backups(days_to_keep=30, force_cleanup=False, dry_run=False):
    """מנקה גיבויים פנימיים מסודרים ישנים עם הגנות מרובות רבדים"""
    try:
        # 🛡️ LAYER 1: הגנה מפני מחיקה מוקדמת מדי
        MINIMUM_RETENTION_DAYS = 7  # מינימום 7 ימים שמירה - אסור למחוק!
        if days_to_keep < MINIMUM_RETENTION_DAYS:
            logger.error(f"🚨 BLOCKED: ניסיון מחיקת גיבויים צעירים מ-{MINIMUM_RETENTION_DAYS} ימים!")
            send_admin_notification(
                f"🚨 **אזהרת אבטחה - מחיקת גיבוי חסומה!**\n\n" +
                f"❌ **ניסיון מחיקה:** {days_to_keep} ימים\n" +
                f"🛡️ **מינימום מוגן:** {MINIMUM_RETENTION_DAYS} ימים\n" +
                f"⛔ **פעולה נחסמה** - הגנת נתונים פעילה!",
                urgent=True
            )
            return False
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # 🛡️ LAYER 2: בדיקת מספר גיבויים כללי
        cur.execute(f"""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = '{BACKUP_SCHEMA}'
            AND table_name LIKE '%_backup_%'
        """)
        total_backups = cur.fetchone()[0]
        
        if total_backups < 3:  # הגנה מפני מחיקת כל הגיבויים
            logger.error(f"🚨 BLOCKED: רק {total_backups} גיבויים - לא מוחק!")
            send_admin_notification(
                f"🚨 **הגנת גיבוי פעילה!**\n\n" +
                f"📊 **גיבויים זמינים:** {total_backups}\n" +
                f"🛡️ **מינימום נדרש:** 3 גיבויים\n" +
                f"⛔ **מחיקה חסומה** - הגנת נתונים!",
                urgent=True
            )
            return False
        
        # קבלת רשימת גיבויים למחיקה
        cur.execute(f"""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = '{BACKUP_SCHEMA}'
            AND table_name LIKE '%_backup_%'
        """)
        backup_tables = cur.fetchall()
        
        # 🛡️ LAYER 3: סימולציה ובדיקת בטיחות
        tables_to_delete = []
        tables_by_type = {}
        
        for (table_name,) in backup_tables:
            try:
                if "_backup_" in table_name:
                    backup_date_str = table_name.split("_backup_")[-1]
                    backup_date = datetime.strptime(backup_date_str, "%d_%m_%Y")
                    
                    if backup_date < cutoff_date:
                        # קיבוץ לפי סוג טבלה
                        original_table = table_name.split("_backup_")[0]
                        if original_table not in tables_by_type:
                            tables_by_type[original_table] = []
                        tables_by_type[original_table].append(table_name)
                        tables_to_delete.append(table_name)
                        
            except Exception as e:
                logger.warning(f"⚠️ שגיאה בבדיקת תאריך {table_name}: {e}")
        
        # 🛡️ LAYER 4: הגנה מפני מחיקת כל הגיבויים מסוג מסוים
        for original_table, tables_for_deletion in tables_by_type.items():
            # ספירת כמה גיבויים נשארים לאחר המחיקה
            cur.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = '{BACKUP_SCHEMA}'
                AND table_name LIKE '{original_table}_backup_%'
            """)
            total_for_type = cur.fetchone()[0]
            remaining_after_deletion = total_for_type - len(tables_for_deletion)
            
            if remaining_after_deletion < 2:  # חייב להשאיר לפחות 2 גיבויים
                logger.error(f"🚨 BLOCKED: {original_table} יישאר עם {remaining_after_deletion} גיבויים בלבד!")
                send_admin_notification(
                    f"🚨 **הגנת גיבוי ספציפית פעילה!**\n\n" +
                    f"📋 **טבלה:** {original_table}\n" +
                    f"📊 **גיבויים נוכחיים:** {total_for_type}\n" +
                    f"📉 **יישארו אחרי מחיקה:** {remaining_after_deletion}\n" +
                    f"🛡️ **מינימום נדרש:** 2 גיבויים\n" +
                    f"⛔ **מחיקה חסומה** - הגנת נתונים!",
                    urgent=True
                )
                return False
        
        if not tables_to_delete:
            logger.info("🧹 אין טבלאות גיבוי ישנות למחיקה (כל ההגנות פעילות)")
            return True
        
        # 🛡️ LAYER 5: מצב סימולציה (Dry Run)
        if dry_run:
            logger.info(f"🧪 DRY RUN: היו נמחקות {len(tables_to_delete)} טבלאות:")
            for table in tables_to_delete:
                logger.info(f"   🗑️ [SIMULATION] {table}")
            send_admin_notification(
                f"🧪 **סימולציה - מחיקת גיבויים**\n\n" +
                f"🗑️ **היו נמחקות:** {len(tables_to_delete)} טבלאות\n" +
                f"📅 **ישנות מ:** {cutoff_date.strftime('%d/%m/%Y')}\n" +
                f"💡 **זהו מצב סימולציה - שום דבר לא נמחק!**"
            )
            return True
        
        # 🛡️ LAYER 6: דרישת אישור מפורש (במצב לא כפוי)
        if not force_cleanup:
            logger.warning(f"⚠️ נדרש אישור מפורש למחיקת {len(tables_to_delete)} גיבויים")
            send_admin_notification(
                f"⚠️ **בקשת אישור מחיקת גיבויים**\n\n" +
                f"🗑️ **להמחקה:** {len(tables_to_delete)} טבלאות\n" +
                f"📅 **ישנות מ:** {cutoff_date.strftime('%d/%m/%Y')}\n" +
                f"⚡ **לאישור:** הרץ עם `force_cleanup=True`\n" +
                f"🧪 **לסימולציה:** הרץ עם `dry_run=True`\n" +
                f"🛡️ **הגנת נתונים פעילה!**",
                urgent=True
            )
            return False
        
        # 🛡️ LAYER 7: מחיקה מוגנת עם לוגים מפורטים
        deleted_tables = 0
        for table_name in tables_to_delete:
            try:
                # רישום מפורט לפני מחיקה
                cur.execute(f"SELECT COUNT(*) FROM {BACKUP_SCHEMA}.{table_name}")
                records_count = cur.fetchone()[0]
                
                logger.info(f"🗑️ מוחק גיבוי מוגן: {table_name} ({records_count:,} רשומות)")
                
                cur.execute(f"DROP TABLE {BACKUP_SCHEMA}.{table_name}")
                deleted_tables += 1
                
            except Exception as e:
                logger.error(f"❌ שגיאה במחיקת {table_name}: {e}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        # התראה מפורטת על המחיקה
        if deleted_tables > 0:
            logger.info(f"🧹 נמחקו {deleted_tables} טבלאות גיבוי (מוגן)")
            
            send_admin_notification(
                f"🧹 **ניקוי גיבויים הושלם בהצלחה**\n\n" +
                f"🗑️ **נמחקו:** {deleted_tables} טבלאות\n" +
                f"📅 **ישנות מ:** {cutoff_date.strftime('%d/%m/%Y')}\n" +
                f"💾 **שמירה:** {days_to_keep} ימים\n" +
                f"🛡️ **הגנות שעברו:** ✅ מינימום {MINIMUM_RETENTION_DAYS} ימים\n" +
                f"🗃️ **Schema:** `{BACKUP_SCHEMA}`\n" +
                f"⚡ **מצב:** כפוי (force_cleanup=True)"
            )
        
        return True
        
    except Exception as e:
        logger.error(f"❌ שגיאה בניקוי גיבויים מוגן: {e}")
        send_admin_notification(
            f"🚨 **שגיאה בניקוי גיבויים!**\n\n" +
            f"❌ **שגיאה:** {str(e)[:200]}\n" +
            f"🛡️ **הגנת נתונים:** פעילה\n" +
            f"💡 **המלצה:** בדוק הלוגים",
            urgent=True
        )
        return False

def safe_backup_cleanup(days_to_keep=30, force=False):
    """ניקוי גיבויים בטוח עם הגנות מרובות רבדים"""
    try:
        logger.info(f"🛡️ מתחיל ניקוי גיבויים מוגן (שמירה: {days_to_keep} ימים)")
        
        # תחילה - סימולציה לראות מה היה נמחק
        logger.info("🧪 מריץ סימולציה...")
        cleanup_old_organized_internal_backups(days_to_keep, force_cleanup=False, dry_run=True)
        
        # אם זה לא כפוי, רק נציג מה היה קורה ונבקש אישור
        if not force:
            logger.info("⚠️ ניקוי גיבויים דורש אישור מפורש")
            send_admin_notification(
                f"🛡️ **ניקוי גיבויים מוגן מוכן**\n\n" +
                f"📅 **לשמירה:** {days_to_keep} ימים\n" +
                f"🧪 **סימולציה הושלמה** - ראה פרטים בלוג\n" +
                f"⚡ **לביצוע:** הרץ עם `force=True`\n" +
                f"🛡️ **הגנות פעילות:** מינימום 7 ימים + 2 גיבויים לטבלה"
            )
            return False
        
        # ביצוע אמיתי עם הגנות
        logger.info("⚡ מריץ ניקוי אמיתי עם הגנות...")
        return cleanup_old_organized_internal_backups(days_to_keep, force_cleanup=True, dry_run=False)
        
    except Exception as e:
        logger.error(f"❌ שגיאה בניקוי בטוח: {e}")
        return False

def get_backup_security_status():
    """בודק מצב אבטחת הגיבויים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # סטטיסטיקות כלליות
        cur.execute(f"""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = '{BACKUP_SCHEMA}'
        """)
        total_backups = cur.fetchone()[0]
        
        # בדיקה לפי סוג טבלה
        security_status = {
            "total_backups": total_backups,
            "by_table_type": {},
            "oldest_backup": None,
            "newest_backup": None,
            "security_level": "unknown"
        }
        
        for table_name in TABLES_TO_BACKUP:
            cur.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = '{BACKUP_SCHEMA}'
                AND table_name LIKE '{table_name}_backup_%'
            """)
            count = cur.fetchone()[0]
            security_status["by_table_type"][table_name] = count
        
        # מציאת הגיבוי הישן והחדש ביותר
        cur.execute(f"""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = '{BACKUP_SCHEMA}'
            AND table_name LIKE '%_backup_%'
            ORDER BY table_name
        """)
        
        backup_tables = [row[0] for row in cur.fetchall()]
        if backup_tables:
            # חילוץ תאריכים
            dates = []
            for table in backup_tables:
                try:
                    date_str = table.split("_backup_")[-1]
                    date_obj = datetime.strptime(date_str, "%d_%m_%Y")
                    dates.append(date_obj)
                except:
                    pass
            
            if dates:
                security_status["oldest_backup"] = min(dates)
                security_status["newest_backup"] = max(dates)
                
                # הערכת רמת אבטחה
                days_coverage = (max(dates) - min(dates)).days
                min_backups_per_type = min(security_status["by_table_type"].values()) if security_status["by_table_type"] else 0
                
                if min_backups_per_type >= 7 and days_coverage >= 7:
                    security_status["security_level"] = "excellent"
                elif min_backups_per_type >= 3 and days_coverage >= 3:
                    security_status["security_level"] = "good"
                elif min_backups_per_type >= 2:
                    security_status["security_level"] = "minimal"
                else:
                    security_status["security_level"] = "critical"
        
        cur.close()
        conn.close()
        
        return security_status
        
    except Exception as e:
        logger.error(f"❌ שגיאה בבדיקת מצב אבטחה: {e}")
        return None

def send_backup_security_report():
    """שולח דוח אבטחת גיבויים לאדמין"""
    try:
        status = get_backup_security_status()
        storage = get_backup_storage_info()
        
        if not status or not storage:
            send_admin_notification("❌ **שגיאה בדוח אבטחת גיבויים** - לא ניתן לקבל נתונים")
            return
        
        # אייקונים לפי רמת אבטחה
        security_icons = {
            "excellent": "🟢",
            "good": "🟡", 
            "minimal": "🟠",
            "critical": "🔴",
            "unknown": "⚪"
        }
        
        icon = security_icons.get(status["security_level"], "⚪")
        
        report = f"{icon} **דוח אבטחת גיבויים**\n\n"
        report += f"🛡️ **רמת אבטחה:** {status['security_level'].upper()}\n"
        report += f"📊 **סה\"כ גיבויים:** {status['total_backups']}\n"
        report += f"💾 **גודל כולל:** {storage['total_backup_size']}\n\n"
        
        report += f"📋 **פירוט לפי טבלה:**\n"
        for table, count in status["by_table_type"].items():
            table_icon = "✅" if count >= 3 else "⚠️" if count >= 2 else "❌"
            report += f"{table_icon} **{table.replace('_', ' ').title()}:** {count} גיבויים\n"
        
        if status["oldest_backup"] and status["newest_backup"]:
            days_coverage = (status["newest_backup"] - status["oldest_backup"]).days
            report += f"\n📅 **כיסוי זמן:** {days_coverage} ימים\n"
            report += f"📆 **מ:** {status['oldest_backup'].strftime('%d/%m/%Y')}\n"
            report += f"📆 **עד:** {status['newest_backup'].strftime('%d/%m/%Y')}\n"
        
        # המלצות
        report += f"\n💡 **המלצות אבטחה:**\n"
        if status["security_level"] == "critical":
            report += "🚨 **דחוף:** יש פחות מ-2 גיבויים לטבלה!\n"
        elif status["security_level"] == "minimal":
            report += "⚠️ **זהירות:** מומלץ להגדיל מספר גיבויים\n"
        else:
            report += "✅ **מצוין:** רמת הגנה טובה\n"
        
        report += f"🗃️ **Schema:** `{BACKUP_SCHEMA}`"
        
        send_admin_notification(report)
        
    except Exception as e:
        logger.error(f"❌ שגיאה בשליחת דוח אבטחה: {e}")

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
        elif command == "info":
            info = get_backup_storage_info()
            if info:
                print(f"🗃️ Schema: {info['backup_schema']}")
                print(f"📊 טבלאות גיבוי: {info['backup_tables_count']}")
                print(f"💾 גודל גיבוי: {info['total_backup_size']}")
                print(f"🗄️ גודל מסד כללי: {info['total_db_size']}")
        
        # 🛡️ פקודות ניקוי מוגנות
        elif command == "cleanup":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            print(f"🛡️ מריץ ניקוי מוגן (שמירה: {days} ימים)")
            print("⚠️ זוהי פעולה מוגנת - רק סימולציה!")
            cleanup_old_organized_internal_backups(days, force_cleanup=False, dry_run=True)
            
        elif command == "cleanup-force":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            print(f"⚡ מריץ ניקוי כפוי (שמירה: {days} ימים)")
            print("🚨 זוהי פעולה אמיתית עם הגנות!")
            cleanup_old_organized_internal_backups(days, force_cleanup=True, dry_run=False)
            
        elif command == "safe-cleanup":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            force = len(sys.argv) > 3 and sys.argv[3] == "force"
            print(f"🛡️ מריץ ניקוי בטוח מלא (שמירה: {days} ימים)")
            safe_backup_cleanup(days, force)
            
        # 🔍 פקודות בדיקה ודיווח
        elif command == "security":
            print("🔍 בודק מצב אבטחת גיבויים...")
            status = get_backup_security_status()
            if status:
                print(f"🛡️ רמת אבטחה: {status['security_level']}")
                print(f"📊 סה\"כ גיבויים: {status['total_backups']}")
                for table, count in status["by_table_type"].items():
                    icon = "✅" if count >= 3 else "⚠️" if count >= 2 else "❌"
                    print(f"{icon} {table}: {count} גיבויים")
            else:
                print("❌ שגיאה בבדיקת אבטחה")
                
        elif command == "security-report":
            print("📧 שולח דוח אבטחה לאדמין...")
            send_backup_security_report()
            print("✅ דוח נשלח")
            
        # 🧪 פקודות בדיקה
        elif command == "dry-run":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            print(f"🧪 מריץ סימולציה מלאה (שמירה: {days} ימים)")
            cleanup_old_organized_internal_backups(days, force_cleanup=False, dry_run=True)
            
        else:
            print("🛡️ מערכת גיבוי מוגנת - פקודות זמינות:")
            print("=" * 50)
            print("📦 גיבוי:")
            print("  backup              - צור גיבוי חדש")
            print("  list                - הצג רשימת גיבויים")
            print("  info                - מידע על אחסון")
            print()
            print("🛡️ ניקוי מוגן:")
            print("  cleanup [days]      - סימולציה בלבד (ברירת מחדל: 30)")
            print("  cleanup-force [days]- ניקוי אמיתי עם הגנות")
            print("  safe-cleanup [days] [force] - ניקוי בטוח מלא")
            print("  dry-run [days]      - סימולציה מפורטת")
            print()
            print("🔍 בדיקות אבטחה:")
            print("  security            - בדוק מצב אבטחה")
            print("  security-report     - שלח דוח לאדמין")
            print()
            print("🛡️ הגנות פעילות:")
            print("  • מינימום 7 ימים שמירה")
            print("  • מינימום 2 גיבויים לטבלה")
            print("  • מינימום 3 גיבויים כללי")
            print("  • סימולציה לפני מחיקה")
            print("  • דרישת אישור מפורש")
    else:
        # גיבוי רגיל
        run_organized_internal_backup() 