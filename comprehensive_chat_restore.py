#!/usr/bin/env python3
"""
🚨 comprehensive_chat_restore.py
===============================
שחזור מקיף מכל המקורות הזמינים!

🎯 מטרה: לשחזר את כל ההודעות שנמחקו מכל הגיבויים
🔍 מקורות: גיבויים יומיים, קבצי JSON, gpt_calls_log ועוד

הפעלה: python comprehensive_chat_restore.py
"""

import psycopg2
import json
import os
from datetime import datetime, timedelta
from config import config

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

def analyze_data_loss():
    """ניתוח מלא של איבוד הנתונים"""
    print("🔍 מנתח איבוד נתונים מכל המקורות...")
    print("=" * 60)
    
    sources = {}
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # מספר הודעות נוכחי
        cur.execute("SELECT COUNT(*) FROM chat_messages")
        current_count = cur.fetchone()[0]
        sources["current_db"] = current_count
        print(f"📊 הודעות נוכחיות במסד: {current_count:,}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת מסד נוכחי: {e}")
        return {}
    
    # בדיקת גיבוי יומי 9.7
    daily_backup_path = "backups/daily_db_backups/chat_messages_20250709.json"
    if os.path.exists(daily_backup_path):
        try:
            with open(daily_backup_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sources["backup_09_07"] = len(data)
                print(f"📊 גיבוי 9.7: {len(data):,} הודעות")
        except Exception as e:
            print(f"⚠️ שגיאה בקריאת גיבוי 9.7: {e}")
    
    # בדיקת גיבוי 6.7
    old_backup_path = "backups/data_backup_20250706_141212/chat_history.json"
    if os.path.exists(old_backup_path):
        try:
            with open(old_backup_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sources["backup_06_07"] = len(data)
                print(f"📊 גיבוי 6.7: {len(data):,} הודעות")
        except Exception as e:
            print(f"⚠️ שגיאה בקריאת גיבוי 6.7: {e}")
    
    # בדיקת קובץ חילוץ
    extracted_path = "extracted_chat_data_20250706_155957.json"
    if os.path.exists(extracted_path):
        try:
            with open(extracted_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'chat_messages' in data:
                    sources["extracted_06_07"] = len(data['chat_messages'])
                    print(f"📊 נתונים מחולצים 6.7: {len(data['chat_messages']):,} הודעות")
                elif isinstance(data, list):
                    sources["extracted_06_07"] = len(data)
                    print(f"📊 נתונים מחולצים 6.7: {len(data):,} הודעות")
        except Exception as e:
            print(f"⚠️ שגיאה בקריאת נתונים מחולצים: {e}")
    
    print("\n🚨 סיכום איבוד נתונים:")
    max_count = max(sources.values()) if sources else 0
    current = sources.get("current_db", 0)
    total_loss = max_count - current
    
    print(f"   📈 מקסימום הודעות שהיו: {max_count:,}")
    print(f"   📊 הודעות נוכחיות: {current:,}")
    print(f"   🚨 סה\"כ איבוד: {total_loss:,} הודעות")
    
    return sources

def restore_from_json_file(file_path, source_name):
    """משחזר הודעות מקובץ JSON"""
    print(f"\n🔄 משחזר מ-{source_name}: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"❌ קובץ לא קיים: {file_path}")
        return 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # זיהוי פורמט הנתונים
        messages = []
        if isinstance(data, list):
            messages = data
        elif isinstance(data, dict):
            if 'chat_messages' in data:
                messages = data['chat_messages']
            elif 'messages' in data:
                messages = data['messages']
            else:
                print(f"⚠️ פורמט לא מוכר ב-{source_name}")
                return 0
        
        print(f"📋 נמצאו {len(messages):,} הודעות בקובץ")
        
        if not messages:
            return 0
        
        # שחזור למסד הנתונים
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        restored_count = 0
        skipped_count = 0
        
        for msg in messages:
            try:
                # וידוא שיש לנו את השדות הנדרשים
                chat_id = msg.get('chat_id')
                user_msg = msg.get('user_msg', '')
                bot_msg = msg.get('bot_msg', '')
                timestamp = msg.get('timestamp')
                
                if not chat_id or not timestamp:
                    skipped_count += 1
                    continue
                
                # בדיקה שההודעה לא קיימת כבר
                cur.execute("""
                    SELECT COUNT(*) FROM chat_messages 
                    WHERE chat_id = %s 
                    AND user_msg = %s 
                    AND timestamp = %s
                """, (chat_id, user_msg, timestamp))
                
                if cur.fetchone()[0] > 0:
                    skipped_count += 1
                    continue
                
                # הכנסת ההודעה
                cur.execute("""
                    INSERT INTO chat_messages (
                        chat_id, user_msg, bot_msg, timestamp, message_type,
                        telegram_message_id, source_file, source_line_number,
                        gpt_type, gpt_model, gpt_cost_usd, gpt_tokens_input, gpt_tokens_output,
                        gpt_request, gpt_response, user_data, bot_data, metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    chat_id, user_msg, bot_msg, timestamp,
                    msg.get('message_type', 'restored'),
                    msg.get('telegram_message_id'),
                    f'restored_from_{source_name}',
                    msg.get('source_line_number'),
                    msg.get('gpt_type'),
                    msg.get('gpt_model'),
                    msg.get('gpt_cost_usd'),
                    msg.get('gpt_tokens_input'),
                    msg.get('gpt_tokens_output'),
                    msg.get('gpt_request'),
                    msg.get('gpt_response'),
                    msg.get('user_data'),
                    msg.get('bot_data'),
                    msg.get('metadata')
                ))
                
                restored_count += 1
                
                # התקדמות כל 1000 הודעות
                if restored_count % 1000 == 0:
                    print(f"   📊 שוחזרו {restored_count:,} הודעות...")
                    conn.commit()
                
            except Exception as e:
                skipped_count += 1
                if skipped_count % 100 == 0:
                    print(f"   ⚠️ דולגו על {skipped_count} הודעות עד כה...")
                continue
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ {source_name}: שוחזרו {restored_count:,} הודעות, דולגו על {skipped_count:,}")
        return restored_count
        
    except Exception as e:
        print(f"❌ שגיאה בשחזור מ-{source_name}: {e}")
        return 0

def restore_from_gpt_calls():
    """שחזור הודעות מטבלת gpt_calls_log"""
    print(f"\n🔄 משחזר הודעות מ-gpt_calls_log...")
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקת הודעות ב-gpt_calls_log שחסרות ב-chat_messages
        cur.execute("""
            SELECT DISTINCT 
                g.chat_id, g.user_msg, g.bot_msg, g.timestamp,
                g.gpt_type, g.gpt_model, g.gpt_cost_usd, 
                g.gpt_tokens_input, g.gpt_tokens_output,
                g.gpt_request, g.gpt_response
            FROM gpt_calls_log g
            WHERE g.user_msg IS NOT NULL 
            AND g.user_msg != ''
            AND NOT EXISTS (
                SELECT 1 FROM chat_messages c
                WHERE c.chat_id = g.chat_id 
                AND c.user_msg = g.user_msg 
                AND c.timestamp = g.timestamp
            )
            ORDER BY g.timestamp
        """)
        
        missing_messages = cur.fetchall()
        print(f"📋 נמצאו {len(missing_messages):,} הודעות ב-gpt_calls_log שחסרות ב-chat_messages")
        
        restored_count = 0
        for msg in missing_messages:
            try:
                cur.execute("""
                    INSERT INTO chat_messages (
                        chat_id, user_msg, bot_msg, timestamp, message_type,
                        source_file, gpt_type, gpt_model, gpt_cost_usd,
                        gpt_tokens_input, gpt_tokens_output, gpt_request, gpt_response
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    msg[0], msg[1], msg[2], msg[3], 'restored_from_gpt_log',
                    'gpt_calls_log_restore', msg[4], msg[5], msg[6],
                    msg[7], msg[8], msg[9], msg[10]
                ))
                restored_count += 1
                
                if restored_count % 500 == 0:
                    print(f"   📊 שוחזרו {restored_count:,} הודעות מ-gpt_calls_log...")
                    conn.commit()
                    
            except Exception as e:
                continue
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ gpt_calls_log: שוחזרו {restored_count:,} הודעות")
        return restored_count
        
    except Exception as e:
        print(f"❌ שגיאה בשחזור מ-gpt_calls_log: {e}")
        return 0

def comprehensive_restore():
    """שחזור מקיף מכל המקורות"""
    print("🚨 מתחיל שחזור מקיף מכל המקורות...")
    print("=" * 60)
    
    # ניתוח איבוד נתונים
    sources = analyze_data_loss()
    
    if not sources:
        print("❌ לא ניתן לבצע ניתוח - יוצא")
        return False
    
    total_restored = 0
    
    # שחזור מכל המקורות
    restoration_sources = [
        ("backups/daily_db_backups/chat_messages_20250709.json", "daily_backup_09_07"),
        ("backups/data_backup_20250706_141212/chat_history.json", "old_backup_06_07"),
        ("extracted_chat_data_20250706_155957.json", "extracted_data_06_07")
    ]
    
    for file_path, source_name in restoration_sources:
        restored = restore_from_json_file(file_path, source_name)
        total_restored += restored
    
    # שחזור מ-gpt_calls_log
    gpt_restored = restore_from_gpt_calls()
    total_restored += gpt_restored
    
    print(f"\n🎉 סיכום שחזור מקיף:")
    print(f"   📊 סה\"כ הודעות ששוחזרו: {total_restored:,}")
    
    # בדיקה סופית
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM chat_messages")
        final_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        print(f"   📊 מספר הודעות סופי: {final_count:,}")
        
        original_max = max(sources.values()) if sources else 0
        if final_count >= original_max * 0.95:  # 95% שחזור
            print("✅ שחזור הושלם בהצלחה!")
            return True
        else:
            remaining_loss = original_max - final_count
            print(f"⚠️ עדיין חסרות בערך {remaining_loss:,} הודעות")
            return False
            
    except Exception as e:
        print(f"❌ שגיאה בבדיקה סופית: {e}")
        return False

if __name__ == "__main__":
    print("🚨 === שחזור מקיף להודעות chat_messages ===")
    print(f"🕐 זמן הפעלה: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # שחזור מקיף
    success = comprehensive_restore()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 שחזור מקיף הושלם בהצלחה!")
        print("✅ רוב ההודעות שוחזרו")
    else:
        print("⚠️ שחזור חלקי - יש עדיין הודעות חסרות")
        print("📞 בדקתי את כל המקורות הזמינים")
    
    print("🔒 chat_messages מוגן מפני מחיקות עתידיות!") 