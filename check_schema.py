#!/usr/bin/env python3
import psycopg2
import json

def main():
    print('🔍 בדיקת מבנה טבלאות וזיהוי הבעיה...')
    
    with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    db_url = config.get('DATABASE_EXTERNAL_URL') or config.get('DATABASE_URL')

    connection = psycopg2.connect(db_url)
    cursor = connection.cursor()

    print()
    
    # בדיקת מבנה chat_messages
    print('📋 טבלת chat_messages:')
    cursor.execute('''
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'chat_messages' AND column_name = 'chat_id'
    ''')
    result = cursor.fetchone()
    if result:
        print(f'   chat_id: {result[1]} (nullable: {result[2]})')
    else:
        print('   ❌ עמודת chat_id לא נמצאה!')

    # בדיקת מבנה user_profiles  
    print('\n📋 טבלת user_profiles:')
    cursor.execute('''
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'user_profiles' AND column_name = 'chat_id'
    ''')
    result = cursor.fetchone()
    if result:
        print(f'   chat_id: {result[1]} (nullable: {result[2]})')
    else:
        print('   ❌ עמודת chat_id לא נמצאה!')

    # בדיקת מבנה gpt_calls_log
    print('\n📋 טבלת gpt_calls_log:')
    cursor.execute('''
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'gpt_calls_log' AND column_name = 'chat_id'
    ''')
    result = cursor.fetchone()
    if result:
        print(f'   chat_id: {result[1]} (nullable: {result[2]})')
    else:
        print('   ❌ עמודת chat_id לא נמצאה!')

    # דוגמאות chat_id מהנתונים האמיתיים
    print('\n🔍 דוגמאות chat_id בפועל:')
    try:
        cursor.execute('SELECT DISTINCT chat_id FROM chat_messages LIMIT 5')
        examples = cursor.fetchall()
        for ex in examples:
            print(f'   "{ex[0]}" (Python type: {type(ex[0]).__name__})')
    except Exception as e:
        print(f'   ❌ שגיאה בקריאת דוגמאות: {e}')

    # המלצה לפתרון
    print('\n💡 הפתרונות האפשריים:')
    print()
    print('1. 🎯 הפתרון הטוב ביותר - wrapper function:')
    print('   - ליצור ensure_chat_id_str() שמקבלת int או str ומחזירה str')
    print('   - לקרוא לה בכל מקום שעושה SQL query')
    print('   - כל ה-chat_id יישארו VARCHAR בטבלה (גמיש יותר)')
    print()
    print('2. 🔧 פתרון חלופי - שינוי טבלה:')
    print('   - לשנות את העמודות ל-BIGINT')
    print('   - לוודא שהקוד תמיד שולח integers')
    print('   - מסוכן יותר - עלול לשבור דברים אחרים')
    print()
    print('3. ❌ הפתרון הנוכחי str(chat_id) בכל מקום:')
    print('   - פותר את הבעיה אבל לא מרכזי')
    print('   - אם נשכח למקום אחד, הבעיה חוזרת')

    cursor.close()
    connection.close()

if __name__ == "__main__":
    main() 