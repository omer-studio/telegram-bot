#!/usr/bin/env python3
"""
🛡️ מערכת הגנה על מסד הנתונים
יוצרת טריגרים ומגבלות למניעת שינויים מזיקים
"""

import psycopg2
from datetime import datetime
from config import config
from simple_logger import logger
from admin_notifications import send_admin_notification

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

# 🔒 SQL לטריגרים מגינים
PROTECTION_TRIGGERS = {
    "prevent_mass_delete": """
    CREATE OR REPLACE FUNCTION prevent_mass_delete() RETURNS TRIGGER AS $$
    BEGIN
        -- אם מוחקים יותר מ-3 רשומות בו-זמנית
        IF (SELECT COUNT(*) FROM user_profiles WHERE code_approve IS NOT NULL) - 
           (SELECT COUNT(*) FROM new_table) > 3 THEN
            RAISE EXCEPTION 'מחיקה המונית נחסמה! לא ניתן למחוק יותר מ-3 קודי אישור בו-זמנית';
        END IF;
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql;
    
    DROP TRIGGER IF EXISTS prevent_mass_delete_trigger ON user_profiles;
    CREATE TRIGGER prevent_mass_delete_trigger
        AFTER DELETE ON user_profiles
        FOR EACH STATEMENT
        EXECUTE FUNCTION prevent_mass_delete();
    """,
    
    "log_critical_changes": """
    CREATE TABLE IF NOT EXISTS data_audit_log (
        id SERIAL PRIMARY KEY,
        table_name TEXT NOT NULL,
        operation TEXT NOT NULL,
        old_data JSONB,
        new_data JSONB,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_info TEXT
    );
    
    CREATE OR REPLACE FUNCTION log_user_profile_changes() RETURNS TRIGGER AS $$
    BEGIN
        -- לוג שינויים בטבלת משתמשים
        IF TG_OP = 'DELETE' THEN
            INSERT INTO data_audit_log (table_name, operation, old_data, user_info)
            VALUES ('user_profiles', 'DELETE', row_to_json(OLD), current_user);
            RETURN OLD;
        ELSIF TG_OP = 'UPDATE' THEN
            INSERT INTO data_audit_log (table_name, operation, old_data, new_data, user_info)
            VALUES ('user_profiles', 'UPDATE', row_to_json(OLD), row_to_json(NEW), current_user);
            RETURN NEW;
        ELSIF TG_OP = 'INSERT' THEN
            INSERT INTO data_audit_log (table_name, operation, new_data, user_info)
            VALUES ('user_profiles', 'INSERT', row_to_json(NEW), current_user);
            RETURN NEW;
        END IF;
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql;
    
    DROP TRIGGER IF EXISTS log_user_profile_changes_trigger ON user_profiles;
    CREATE TRIGGER log_user_profile_changes_trigger
        AFTER INSERT OR UPDATE OR DELETE ON user_profiles
        FOR EACH ROW
        EXECUTE FUNCTION log_user_profile_changes();
    """,
    
    "protect_approved_codes": """
    CREATE OR REPLACE FUNCTION protect_approved_codes() RETURNS TRIGGER AS $$
    BEGIN
        -- מניעת מחיקה של קודים מאושרים
        IF TG_OP = 'DELETE' AND OLD.approved = TRUE THEN
            RAISE EXCEPTION 'לא ניתן למחוק משתמש מאושר! קוד: %', OLD.code_approve;
        END IF;
        
        -- מניעת שינוי קוד אישור קיים
        IF TG_OP = 'UPDATE' AND OLD.code_approve IS NOT NULL AND 
           NEW.code_approve != OLD.code_approve THEN
            RAISE EXCEPTION 'לא ניתן לשנות קוד אישור קיים! קוד ישן: %, חדש: %', 
                          OLD.code_approve, NEW.code_approve;
        END IF;
        
        RETURN COALESCE(NEW, OLD);
    END;
    $$ LANGUAGE plpgsql;
    
    DROP TRIGGER IF EXISTS protect_approved_codes_trigger ON user_profiles;
    CREATE TRIGGER protect_approved_codes_trigger
        BEFORE UPDATE OR DELETE ON user_profiles
        FOR EACH ROW
        EXECUTE FUNCTION protect_approved_codes();
    """,
    
    "notify_suspicious_activity": """
    CREATE OR REPLACE FUNCTION notify_suspicious_activity() RETURNS TRIGGER AS $$
    BEGIN
        -- התראה על פעילות חשודה
        IF TG_OP = 'DELETE' THEN
            PERFORM pg_notify('suspicious_activity', 
                json_build_object(
                    'type', 'delete',
                    'table', 'user_profiles',
                    'code_approve', OLD.code_approve,
                    'chat_id', OLD.chat_id,
                    'timestamp', CURRENT_TIMESTAMP
                )::text
            );
        ELSIF TG_OP = 'UPDATE' AND OLD.code_approve IS NOT NULL AND NEW.code_approve IS NULL THEN
            PERFORM pg_notify('suspicious_activity', 
                json_build_object(
                    'type', 'null_injection',
                    'table', 'user_profiles',
                    'old_code', OLD.code_approve,
                    'timestamp', CURRENT_TIMESTAMP
                )::text
            );
        END IF;
        
        RETURN COALESCE(NEW, OLD);
    END;
    $$ LANGUAGE plpgsql;
    
    DROP TRIGGER IF EXISTS notify_suspicious_activity_trigger ON user_profiles;
    CREATE TRIGGER notify_suspicious_activity_trigger
        AFTER UPDATE OR DELETE ON user_profiles
        FOR EACH ROW
        EXECUTE FUNCTION notify_suspicious_activity();
    """
}

# 🔒 אילוצים (constraints) נוספים
PROTECTION_CONSTRAINTS = {
    "unique_codes": """
    ALTER TABLE user_profiles 
    ADD CONSTRAINT unique_code_approve 
    UNIQUE (code_approve);
    """,
    
    "valid_chat_id": """
    ALTER TABLE user_profiles 
    ADD CONSTRAINT valid_chat_id 
    CHECK (chat_id IS NULL OR chat_id::text ~ '^[0-9]+$');
    """,
    
    "required_fields": """
    ALTER TABLE user_profiles 
    ADD CONSTRAINT code_or_chat_required 
    CHECK (code_approve IS NOT NULL OR chat_id IS NOT NULL);
    """
}

def setup_database_protection():
    """מתקין את כל מערכות ההגנה על המסד נתונים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        logger.info("🛡️ מתקין מערכת הגנה על מסד הנתונים")
        
        # התקנת טריגרים
        logger.info("🔧 יוצר טריגרים מגינים...")
        for trigger_name, trigger_sql in PROTECTION_TRIGGERS.items():
            try:
                cur.execute(trigger_sql)
                logger.info(f"✅ טריגר {trigger_name} הותקן בהצלחה")
            except Exception as e:
                logger.error(f"❌ שגיאה בהתקנת טריגר {trigger_name}: {e}")
        
        # התקנת אילוצים
        logger.info("🔧 יוצר אילוצים מגינים...")
        for constraint_name, constraint_sql in PROTECTION_CONSTRAINTS.items():
            try:
                cur.execute(constraint_sql)
                logger.info(f"✅ אילוץ {constraint_name} הותקן בהצלחה")
            except Exception as e:
                # אילוצים יכולים להיכשל אם כבר קיימים
                if "already exists" in str(e).lower():
                    logger.info(f"ℹ️ אילוץ {constraint_name} כבר קיים")
                else:
                    logger.error(f"❌ שגיאה בהתקנת אילוץ {constraint_name}: {e}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info("✅ מערכת הגנה על מסד הנתונים הותקנה בהצלחה")
        
        # התראה לאדמין
        send_admin_notification(
            "🛡️ **מערכת הגנה על מסד הנתונים הותקנה**\n\n" +
            "✅ טריגרים מגינים פעילים\n" +
            "✅ אילוצים מגינים פעילים\n" +
            "✅ לוג שינויים פעיל\n" +
            "✅ התראות אוטומטיות פעילות\n\n" +
            "🔒 המסד נתונים מוגן מפני שינויים מזיקים"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהתקנת מערכת הגנה: {e}")
        return False

def remove_database_protection():
    """מסיר את מערכת ההגנה (למקרי חירום)"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        logger.info("⚠️ מסיר מערכת הגנה על מסד הנתונים")
        
        # הסרת טריגרים
        triggers_to_remove = [
            "prevent_mass_delete_trigger",
            "log_user_profile_changes_trigger",
            "protect_approved_codes_trigger", 
            "notify_suspicious_activity_trigger"
        ]
        
        for trigger in triggers_to_remove:
            try:
                cur.execute(f"DROP TRIGGER IF EXISTS {trigger} ON user_profiles")
                logger.info(f"🗑️ טריגר {trigger} הוסר")
            except Exception as e:
                logger.error(f"❌ שגיאה בהסרת טריגר {trigger}: {e}")
        
        # הסרת אילוצים
        constraints_to_remove = [
            "unique_code_approve",
            "valid_chat_id",
            "code_or_chat_required"
        ]
        
        for constraint in constraints_to_remove:
            try:
                cur.execute(f"ALTER TABLE user_profiles DROP CONSTRAINT IF EXISTS {constraint}")
                logger.info(f"🗑️ אילוץ {constraint} הוסר")
            except Exception as e:
                logger.error(f"❌ שגיאה בהסרת אילוץ {constraint}: {e}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info("⚠️ מערכת הגנה על מסד הנתונים הוסרה")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהסרת מערכת הגנה: {e}")
        return False

def test_protection_system():
    """בודק שמערכת ההגנה עובדת"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        logger.info("🧪 בודק מערכת הגנה על מסד הנתונים")
        
        # בדיקה 1: ניסיון הוספת קוד כפול
        test_results = []
        
        try:
            cur.execute("INSERT INTO user_profiles (code_approve) VALUES ('1234')")
            test_results.append("❌ הגנה מפני קודים כפולים לא עובדת")
        except Exception as e:
            if "unique" in str(e).lower():
                test_results.append("✅ הגנה מפני קודים כפולים עובדת")
            else:
                test_results.append(f"❓ שגיאה לא צפויה: {e}")
        
        # בדיקה 2: ניסיון הזנת chat_id לא תקין
        try:
            cur.execute("INSERT INTO user_profiles (chat_id) VALUES ('invalid_chat_id')")
            test_results.append("❌ הגנה מפני chat_id לא תקין לא עובדת")
        except Exception as e:
            if "valid_chat_id" in str(e).lower():
                test_results.append("✅ הגנה מפני chat_id לא תקין עובדת")
            else:
                test_results.append(f"❓ שגיאה לא צפויה: {e}")
        
        # בדיקה 3: בדיקת קיום טריגרים
        cur.execute("""
            SELECT trigger_name 
            FROM information_schema.triggers 
            WHERE event_object_table = 'user_profiles'
        """)
        
        active_triggers = [row[0] for row in cur.fetchall()]
        expected_triggers = [
            "prevent_mass_delete_trigger",
            "log_user_profile_changes_trigger", 
            "protect_approved_codes_trigger",
            "notify_suspicious_activity_trigger"
        ]
        
        for trigger in expected_triggers:
            if trigger in active_triggers:
                test_results.append(f"✅ טריגר {trigger} פעיל")
            else:
                test_results.append(f"❌ טריגר {trigger} לא פעיל")
        
        conn.rollback()  # ביטול כל השינויים
        cur.close()
        conn.close()
        
        # סיכום תוצאות
        working_count = len([r for r in test_results if r.startswith("✅")])
        total_count = len(test_results)
        
        logger.info(f"🧪 תוצאות בדיקת הגנה: {working_count}/{total_count} עובדים")
        
        for result in test_results:
            logger.info(result)
            print(result)
        
        return working_count == total_count
        
    except Exception as e:
        logger.error(f"❌ שגיאה בבדיקת מערכת הגנה: {e}")
        return False

def view_audit_log(limit=50):
    """מציג את לוג השינויים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT changed_at, table_name, operation, old_data, new_data, user_info
            FROM data_audit_log
            ORDER BY changed_at DESC
            LIMIT %s
        """, (limit,))
        
        rows = cur.fetchall()
        
        if not rows:
            print("📋 אין שינויים בלוג")
            return
        
        print(f"📋 {len(rows)} שינויים אחרונים:")
        print("=" * 80)
        
        for row in rows:
            changed_at, table_name, operation, old_data, new_data, user_info = row
            print(f"🕐 {changed_at}")
            print(f"📊 {table_name} - {operation}")
            print(f"👤 {user_info}")
            
            if old_data and operation in ['UPDATE', 'DELETE']:
                print(f"📤 לפני: {old_data}")
            if new_data and operation in ['UPDATE', 'INSERT']:
                print(f"📥 אחרי: {new_data}")
            
            print("-" * 40)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ שגיאה בצפייה בלוג: {e}")
        print(f"❌ שגיאה בצפייה בלוג: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "setup":
            setup_database_protection()
        elif command == "remove":
            print("⚠️ האם אתה בטוח שאתה רוצה להסיר את מערכת ההגנה?")
            confirm = input("הקלד 'YES' כדי לאשר: ")
            if confirm == "YES":
                remove_database_protection()
            else:
                print("❌ הסרת מערכת הגנה בוטלה")
        elif command == "test":
            test_protection_system()
        elif command == "log":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
            view_audit_log(limit)
        else:
            print("שימוש: python setup_database_protection.py [setup|remove|test|log]")
    else:
        # התקנה רגילה
        setup_database_protection() 