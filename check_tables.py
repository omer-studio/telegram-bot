#!/usr/bin/env python3
"""
בדיקת טבלאות מסד הנתונים - גרסה מעודכנת לטבלאות קריטיות בלבד
"""

import psycopg2
import json
from config import DB_URL

def check_critical_tables():
    """בודק את הטבלאות הקריטיות בלבד"""
    print("🔍 בודק טבלאות קריטיות במסד הנתונים...")
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # 🟢 טבלאות קריטיות בלבד
        critical_tables = {
            'chat_messages': 'הודעות צ\'אט',
            'user_profiles': 'פרופילי משתמשים', 
            'interactions_log': 'לוג אינטראקציות מלא (החליף את gpt_calls_log)',
            'deployment_logs': 'לוגי פריסה',
            'reminder_states': 'מצבי תזכורות',
            'bot_error_logs': 'לוגי שגיאות בוט',
            'bot_trace_logs': 'לוגי trace בוט'
        }
        
        results = {}
        
        for table_name, description in critical_tables.items():
            try:
                # בדיקת קיום הטבלה
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    )
                """, (table_name,))
                
                table_exists = cur.fetchone()[0]
                
                if table_exists:
                    # ספירת שורות
                    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row_count = cur.fetchone()[0]
                    
                    # קבלת מבנה הטבלה
                    cur.execute("""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = %s
                        ORDER BY ordinal_position
                    """, (table_name,))
                    
                    columns = cur.fetchall()
                    
                    results[table_name] = {
                        'exists': True,
                        'description': description,
                        'row_count': row_count,
                        'columns': [{'name': col[0], 'type': col[1]} for col in columns],
                        'status': '✅ תקין'
                    }
                    
                    print(f"✅ {table_name} ({description}): {row_count} שורות")
                    
                else:
                    results[table_name] = {
                        'exists': False,
                        'description': description,
                        'status': '❌ לא קיים'
                    }
                    print(f"❌ {table_name} ({description}): לא קיים")
                    
            except Exception as e:
                results[table_name] = {
                    'exists': False,
                    'description': description,
                    'error': str(e),
                    'status': f'⚠️ שגיאה: {e}'
                }
                print(f"⚠️ {table_name} ({description}): שגיאה - {e}")
        
        # 🚫 טבלאות מיותרות - רק דיווח שהושבתו
        disabled_tables = {
            'gpt_calls_log': 'לוג קריאות GPT הישן (הוחלף ב-interactions_log)',
            'gpt_usage_log': 'לוג שימוש GPT (הושבת - כפול ל-interactions_log)',
            'system_logs': 'לוגי מערכת (הושבת - יש לוגים ספציפיים)',
            'critical_users': 'משתמשים קריטיים (הושבת - מנוהל בקונפיג)',
            'billing_usage': 'נתוני חיוב (הושבת - נתונים ב-interactions_log)',
            'errors_stats': 'סטטיסטיקות שגיאות (הושבת - לא קריטי)',
            'free_model_limits': 'מגבלות מודלים (הושבת - מנוהל בקונפיג)'
        }
        
        print("\n🚫 טבלאות שהושבתו:")
        for table_name, description in disabled_tables.items():
            results[table_name] = {
                'exists': False,
                'description': description,
                'status': '🚫 הושבתה',
                'disabled': True
            }
            print(f"🚫 {table_name}: {description}")
        
        cur.close()
        conn.close()
        
        # סיכום
        active_tables = len([t for t in results.values() if t.get('exists', False)])
        disabled_count = len([t for t in results.values() if t.get('disabled', False)])
        
        print(f"\n📊 סיכום:")
        print(f"   🟢 טבלאות פעילות: {active_tables}")
        print(f"   🚫 טבלאות מושבתות: {disabled_count}")
        print(f"   📋 סה\"כ טבלאות: {len(results)}")
        
        return results
        
    except Exception as e:
        print(f"❌ שגיאה כללית בבדיקת טבלאות: {e}")
        return {}

def check_data_integrity():
    """בודק תקינות נתונים בטבלאות הקריטיות"""
    print("\n🔍 בודק תקינות נתונים...")
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        integrity_results = {}
        
        # בדיקת chat_messages
        try:
            cur.execute("SELECT COUNT(*) FROM chat_messages WHERE chat_id IS NULL OR chat_id = ''")
            null_chat_ids = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(DISTINCT chat_id) FROM chat_messages")
            unique_chats = cur.fetchone()[0]
            
            integrity_results['chat_messages'] = {
                'null_chat_ids': null_chat_ids,
                'unique_chats': unique_chats,
                'status': '✅ תקין' if null_chat_ids == 0 else f'⚠️ {null_chat_ids} הודעות ללא chat_id'
            }
            
        except Exception as e:
            integrity_results['chat_messages'] = {'error': str(e)}
        
        # 🔥 בדיקת interactions_log החדשה
        try:
            cur.execute("SELECT COUNT(*) FROM interactions_log WHERE total_cost_agorot IS NULL")
            null_costs = cur.fetchone()[0]
            
            cur.execute("SELECT SUM(total_cost_agorot) FROM interactions_log WHERE total_cost_agorot > 0")
            total_cost_agorot = cur.fetchone()[0] or 0
            total_cost_usd = total_cost_agorot / 100 if total_cost_agorot else 0
            
            integrity_results['interactions_log'] = {
                'null_costs': null_costs,
                'total_cost_agorot': int(total_cost_agorot),
                'total_cost_usd': float(total_cost_usd),
                'status': f'✅ עלות כוללת: {total_cost_agorot} אגורות (${total_cost_usd:.6f})'
            }
            
        except Exception as e:
            integrity_results['interactions_log'] = {'error': str(e)}
        
        # בדיקת user_profiles
        try:
            cur.execute("SELECT COUNT(*) FROM user_profiles WHERE chat_id IS NULL OR chat_id = ''")
            null_profiles = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(DISTINCT chat_id) FROM user_profiles")
            unique_profiles = cur.fetchone()[0]
            
            integrity_results['user_profiles'] = {
                'null_profiles': null_profiles,
                'unique_profiles': unique_profiles,
                'status': '✅ תקין' if null_profiles == 0 else f'⚠️ {null_profiles} פרופילים ללא chat_id'
            }
            
        except Exception as e:
            integrity_results['user_profiles'] = {'error': str(e)}
        
        cur.close()
        conn.close()
        
        # הדפסת תוצאות
        print("📊 תוצאות בדיקת תקינות:")
        for table, results in integrity_results.items():
            if 'error' in results:
                print(f"   ❌ {table}: שגיאה - {results['error']}")
            else:
                print(f"   {results['status']} {table}")
                for key, value in results.items():
                    if key != 'status':
                        print(f"      • {key}: {value}")
        
        return integrity_results
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת תקינות נתונים: {e}")
        return {}

if __name__ == "__main__":
    print("🔍 === בדיקת טבלאות מסד נתונים ===")
    
    # בדיקת טבלאות
    table_results = check_critical_tables()
    
    # בדיקת תקינות נתונים
    integrity_results = check_data_integrity()
    
    # שמירת תוצאות לקובץ
    try:
        results = {
            'timestamp': '2025-01-20T12:00:00',
            'tables': table_results,
            'integrity': integrity_results
        }
        
        with open('table_check_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 תוצאות נשמרו ב-table_check_results.json")
        
    except Exception as e:
        print(f"⚠️ שגיאה בשמירת תוצאות: {e}")
    
    print("\n✅ בדיקה הושלמה!") 