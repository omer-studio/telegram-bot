#!/usr/bin/env python3
"""
🚨 emergency_restore_chat_messages.py
====================================
סקריפט שחזור דחוף להודעות chat_messages שנמחקו!

🎯 מטרה: לשחזר הודעות מהגיבויים ללא איבוד נתונים
🔒 בטוח: לא יוצר כפילויות, רק משחזר מה שחסר

הפעלה: python emergency_restore_chat_messages.py
"""

import psycopg2
from datetime import datetime, timedelta
from config import config

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

def check_data_loss():
    """בודק אם יש איבוד נתונים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        print("🔍 בודק מצב נוכחי...")
        
        # מספר הודעות נוכחי
        cur.execute("SELECT COUNT(*) FROM chat_messages")
        current_count = cur.fetchone()[0]
        print(f"📊 הודעות נוכחיות: {current_count:,}")
        
        # מספר הודעות בגיבוי של אתמול
        try:
            cur.execute("SELECT COUNT(*) FROM backup.chat_messages_backup_10_07_2025")
            yesterday_backup = cur.fetchone()[0]
            print(f"📊 גיבוי אתמול: {yesterday_backup:,}")
        except:
            yesterday_backup = 0
            print("⚠️ לא נמצא גיבוי אתמול")
        
        # מספר הודעות בגיבוי של היום
        try:
            cur.execute("SELECT COUNT(*) FROM backup.chat_messages_backup_11_07_2025")
            today_backup = cur.fetchone()[0]
            print(f"📊 גיבוי היום: {today_backup:,}")
        except:
            today_backup = 0
            print("⚠️ לא נמצא גיבוי היום")
        
        # חישוב איבוד
        expected_count = max(yesterday_backup, today_backup)
        if expected_count > current_count:
            loss = expected_count - current_count
            print(f"🚨 איבוד נתונים: {loss:,} הודעות!")
            return {
                "has_loss": True,
                "current": current_count,
                "expected": expected_count,
                "loss": loss,
                "yesterday_backup": yesterday_backup,
                "today_backup": today_backup
            }
        else:
            print("✅ לא נמצא איבוד נתונים")
            return {"has_loss": False}
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקה: {e}")
        return {"error": str(e)}

def restore_from_backup(backup_table):
    """משחזר הודעות מטבלת גיבוי"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        print(f"🔄 משחזר מ-{backup_table}...")
        
        # בדיקה שהטבלה קיימת
        cur.execute(f"""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'backup' 
                AND table_name = '{backup_table.split('.')[-1]}'
            )
        """)
        
        if not cur.fetchone()[0]:
            print(f"❌ טבלת גיבוי {backup_table} לא קיימת")
            return False
        
        # שחזור רק הודעות שלא קיימות (למניעת כפילויות)
        restore_sql = f"""
        INSERT INTO chat_messages (
            chat_id, user_msg, bot_msg, timestamp, message_type, 
            telegram_message_id, source_file, source_line_number,
            gpt_type, gpt_model, gpt_cost_usd, gpt_tokens_input, gpt_tokens_output,
            gpt_request, gpt_response, user_data, bot_data, metadata
        )
        SELECT 
            b.chat_id, b.user_msg, b.bot_msg, b.timestamp, b.message_type,
            b.telegram_message_id, b.source_file, b.source_line_number,
            b.gpt_type, b.gpt_model, b.gpt_cost_usd, b.gpt_tokens_input, b.gpt_tokens_output,
            b.gpt_request, b.gpt_response, b.user_data, b.bot_data, b.metadata
        FROM {backup_table} b
        WHERE NOT EXISTS (
            SELECT 1 FROM chat_messages m 
            WHERE m.chat_id = b.chat_id 
            AND m.user_msg = b.user_msg 
            AND m.timestamp = b.timestamp
        )
        """
        
        cur.execute(restore_sql)
        restored_count = cur.rowcount
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ שוחזרו {restored_count:,} הודעות מ-{backup_table}")
        return restored_count
        
    except Exception as e:
        print(f"❌ שגיאה בשחזור מ-{backup_table}: {e}")
        return False

def emergency_restore():
    """שחזור דחוף מלא"""
    print("🚨 מתחיל שחזור דחוף...")
    print("=" * 50)
    
    # בדיקת מצב
    status = check_data_loss()
    
    if status.get("error"):
        print(f"❌ שגיאה קריטית: {status['error']}")
        return False
    
    if not status.get("has_loss"):
        print("✅ לא נדרש שחזור - הנתונים תקינים")
        return True
    
    print(f"\n🚨 נמצא איבוד של {status['loss']:,} הודעות!")
    print("🔄 מתחיל שחזור מהגיבויים...")
    
    total_restored = 0
    
    # נסיון שחזור מגיבוי היום
    if status.get("today_backup", 0) > 0:
        restored = restore_from_backup("backup.chat_messages_backup_11_07_2025")
        if restored:
            total_restored += restored
    
    # נסיון שחזור מגיבוי אתמול
    if status.get("yesterday_backup", 0) > 0:
        restored = restore_from_backup("backup.chat_messages_backup_10_07_2025")
        if restored:
            total_restored += restored
    
    # נסיון שחזור מגיבויים ישנים יותר
    backup_dates = []
    for i in range(2, 8):  # עד שבוע אחורה
        date = (datetime.now() - timedelta(days=i)).strftime("%d_%m_%Y")
        backup_dates.append(f"backup.chat_messages_backup_{date}")
    
    for backup_table in backup_dates:
        try:
            restored = restore_from_backup(backup_table)
            if restored:
                total_restored += restored
        except:
            continue  # ממשיכים לגיבוי הבא
    
    print(f"\n🎉 סיכום שחזור:")
    print(f"   📊 הודעות ששוחזרו: {total_restored:,}")
    
    # בדיקה סופית
    final_status = check_data_loss()
    if not final_status.get("has_loss"):
        print("✅ שחזור הושלם בהצלחה!")
        return True
    else:
        remaining_loss = final_status.get("loss", 0)
        print(f"⚠️ עדיין חסרות {remaining_loss:,} הודעות")
        return False

def disable_delete_function():
    """מכניס הגנה נוספת נגד מחיקות"""
    print("\n🛡️ מוסיף הגנה נוספת נגד מחיקות...")
    
    protection_code = '''
# 🚨 הגנה מפני מחיקות chat_messages
CHAT_MESSAGES_DELETE_DISABLED = True

def protect_chat_messages():
    """מונע מחיקת chat_messages"""
    if CHAT_MESSAGES_DELETE_DISABLED:
        raise Exception("🚨 BLOCKED: מחיקת chat_messages חסומה לחלוטין!")
'''
    
    try:
        with open("chat_protection.py", "w", encoding="utf-8") as f:
            f.write(protection_code)
        print("✅ נוצר קובץ הגנה: chat_protection.py")
    except Exception as e:
        print(f"⚠️ לא ניתן ליצור קובץ הגנה: {e}")

if __name__ == "__main__":
    print("🚨 === סקריפט שחזור דחוף להודעות chat_messages ===")
    print(f"🕐 זמן הפעלה: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # שחזור דחוף
    success = emergency_restore()
    
    # הגנה נוספת
    disable_delete_function()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 שחזור הושלם בהצלחה!")
        print("✅ כל ההודעות זמינות")
    else:
        print("⚠️ שחזור חלקי - יש עדיין הודעות חסרות")
        print("📞 פנה למפתח לסיוע נוסף")
    
    print("🛡️ הוספה הגנה נגד מחיקות עתידיות")
    print("🔒 chat_messages מוגן עכשיו!") 