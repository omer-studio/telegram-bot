#!/usr/bin/env python3
"""
manual_user_analyzer.py
======================
🎯 כלי לניתוח ידני של משתמש בודד לפי chat_id

💡 שימוש:
python manual_user_analyzer.py 5676571979
python manual_user_analyzer.py 179392777

🔍 מה הקובץ עושה:
1. מקבל chat_id כפרמטר
2. מחלץ את כל ההיסטוריה של המשתמש
3. מנתח את התוכן ומחפש מידע אישי
4. מציג ממצאים מפורטים
5. מציע עדכון פרופיל
"""

import sys
import json
import os
from datetime import datetime
import re

def extract_user_info_from_text(text):
    """חילוץ מידע אישי מטקסט"""
    info = {}
    
    # חיפוש גיל
    age_patterns = [
        r'בן (\d+)',
        r'גיל (\d+)',
        r'אני (\d+)',
        r'(\d+) שנים',
        r'בגיל (\d+)'
    ]
    
    for pattern in age_patterns:
        match = re.search(pattern, text)
        if match:
            age = int(match.group(1))
            if 15 <= age <= 80:  # גיל הגיוני
                info['age'] = str(age)
                break
    
    # חיפוש מצב משפחתי
    if any(word in text for word in ['נשוי', 'אשתי', 'רעיה']):
        info['relationship_type'] = 'נשוי'
    elif any(word in text for word in ['גרוש', 'התגרשתי', 'גרושה']):
        info['relationship_type'] = 'גרוש'
    elif any(word in text for word in ['רווק', 'לא נשוי', 'בודד']):
        info['relationship_type'] = 'רווק'
    
    # חיפוש דתיות
    if any(word in text for word in ['דתי', 'שומר מצוות', 'כשר']):
        info['self_religiosity_level'] = 'דתי'
    elif any(word in text for word in ['חילוני', 'לא דתי', 'חופשי']):
        info['self_religiosity_level'] = 'חילוני'
    elif any(word in text for word in ['מסורתי', 'מעורב']):
        info['self_religiosity_level'] = 'מסורתי'
    
    # חיפוש מצב ארון
    if any(phrase in text for phrase in ['בארון', 'בסתר', 'אף אחד לא יודע']):
        info['closet_status'] = 'בארון'
    elif any(phrase in text for phrase in ['יצאתי מהארון', 'כולם יודעים', 'פתוח']):
        info['closet_status'] = 'מחוץ לארון'
    elif any(phrase in text for phrase in ['חלק יודעים', 'בודדים יודעים']):
        info['closet_status'] = 'חלקית בארון'
    
    # חיפוש ילדים
    if any(word in text for word in ['ילדים', 'ילד', 'בן', 'בת', 'הורה']):
        info['parental_status'] = 'יש ילדים'
    
    # חיפוש קונפליקטים נפוצים
    conflicts = []
    if any(word in text for word in ['בדידות', 'לבד', 'בודד']):
        conflicts.append('בדידות')
    if any(word in text for word in ['חרדה', 'פחד', 'דאגה']):
        conflicts.append('חרדות')
    if any(word in text for word in ['משפחה', 'הורים', 'אבא', 'אמא']):
        conflicts.append('יחסים עם משפחה')
    if any(word in text for word in ['זוגיות', 'קשר', 'בן זוג']):
        conflicts.append('מציאת זוגיות')
    
    if conflicts:
        info['primary_conflict'] = ', '.join(conflicts)
    
    return info

def load_user_chat_history(chat_id):
    """טעינת היסטוריית צ'אט של משתמש"""
    
    # ניסיון 1: קובץ JSON ראשי
    main_file = "temp_files/extracted_all_messages.json"
    if os.path.exists(main_file):
        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                all_messages = json.load(f)
            
            user_messages = [msg for msg in all_messages if str(msg.get('user_id')) == str(chat_id)]
            if user_messages:
                print(f"✅ נמצאו {len(user_messages)} הודעות ב-extracted_all_messages.json")
                return user_messages
        except Exception as e:
            print(f"⚠️ בעיה בקריאת {main_file}: {e}")
    
    # ניסיון 2: קבצי היסטוריה נפרדים
    history_files = [
        f"chat_history_{chat_id}.txt",
        f"temp_files/chat_history_{chat_id}.json",
        "temp_files/restored_chat_history.json"
    ]
    
    for file_path in history_files:
        if os.path.exists(file_path):
            try:
                if file_path.endswith('.txt'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # חילוץ הודעות מטקסט
                    user_messages = []
                    lines = content.split('\n')
                    for line in lines:
                        if 'USER:' in line:
                            msg_text = line.split('USER:')[1].strip()
                            user_messages.append({'user_message': msg_text, 'source': 'txt_file'})
                    
                    if user_messages:
                        print(f"✅ נמצאו {len(user_messages)} הודעות ב-{file_path}")
                        return user_messages
                
                elif file_path.endswith('.json'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # אם זה אובייקט עם chat_id
                    if str(chat_id) in data:
                        user_data = data[str(chat_id)]
                        if 'history' in user_data:
                            messages = user_data['history']
                            user_messages = [{'user_message': msg.get('user', ''), 'timestamp': msg.get('timestamp', '')} 
                                           for msg in messages if msg.get('user')]
                            if user_messages:
                                print(f"✅ נמצאו {len(user_messages)} הודעות ב-{file_path}")
                                return user_messages
                
            except Exception as e:
                print(f"⚠️ בעיה בקריאת {file_path}: {e}")
                continue
    
    print(f"❌ לא נמצאה היסטוריה עבור משתמש {chat_id}")
    return []

def analyze_single_user(chat_id):
    """ניתוח מקיף של משתמש בודד"""
    
    print("=" * 60)
    print(f"🔍 ניתוח מקיף של משתמש {chat_id}")
    print("=" * 60)
    
    # שלב 1: טעינת היסטוריה
    print("\n📚 שלב 1: טעינת היסטוריית צ'אט...")
    messages = load_user_chat_history(chat_id)
    
    if not messages:
        print("❌ אין היסטוריה זמינה לניתוח")
        return
    
    # שלב 2: חילוץ טקסט
    print(f"\n📝 שלב 2: חילוץ טקסט מ-{len(messages)} הודעות...")
    all_text = " ".join([msg.get('user_message', '') for msg in messages])
    print(f"📊 סה\"כ {len(all_text)} תווים, {len(all_text.split())} מילים")
    
    # שלב 3: ניתוח מידע
    print(f"\n🔍 שלב 3: ניתוח חכם של התוכן...")
    discovered_info = extract_user_info_from_text(all_text)
    
    # שלב 4: הצגת תוצאות
    print(f"\n📊 שלב 4: תוצאות הניתוח")
    print("-" * 40)
    
    if discovered_info:
        print("✅ מידע שהתגלה:")
        for field, value in discovered_info.items():
            field_name = {
                'age': 'גיל',
                'relationship_type': 'מצב משפחתי',
                'self_religiosity_level': 'רמת דתיות',
                'closet_status': 'מצב ארון',
                'parental_status': 'מצב הורי',
                'primary_conflict': 'קונפליקטים עיקריים'
            }.get(field, field)
            
            print(f"   🔹 {field_name}: {value}")
    else:
        print("❌ לא התגלה מידע ברור מהטקסט")
    
    # שלב 5: דוגמאות הודעות
    print(f"\n💬 שלב 5: דוגמאות הודעות המשתמש")
    print("-" * 40)
    
    sample_messages = messages[:5]  # 5 הודעות ראשונות
    for i, msg in enumerate(sample_messages, 1):
        msg_text = msg.get('user_message', '')[:100]
        timestamp = msg.get('timestamp', 'לא ידוע')[:19]  # רק תאריך ושעה
        print(f"   {i}. [{timestamp}] {msg_text}...")
    
    if len(messages) > 5:
        print(f"   ... ועוד {len(messages) - 5} הודעות")
    
    # שלב 6: סיכום והמלצות
    print(f"\n🎯 שלב 6: סיכום והמלצות")
    print("-" * 40)
    
    # ציון איכות הניתוח
    info_score = len(discovered_info)
    message_score = min(len(messages) / 20, 5)  # עד 5 נקודות לכמות הודעות
    text_score = min(len(all_text) / 1000, 3)   # עד 3 נקודות לכמות טקסט
    
    total_score = info_score + message_score + text_score
    
    if total_score >= 8:
        quality = "מעולה 🌟"
    elif total_score >= 5:
        quality = "טוב ✅"
    elif total_score >= 2:
        quality = "בסיסי 📊"
    else:
        quality = "חלש ⚠️"
    
    print(f"📈 איכות הניתוח: {quality} (ציון: {total_score:.1f}/10)")
    print(f"📊 בסיס הניתוח: {len(messages)} הודעות, {len(all_text)} תווים")
    
    if discovered_info:
        print("✅ ההמלצה: המידע מספיק לעדכון פרופיל")
        print("💡 כדי לעדכן במסד הנתונים, הוסף את הנתונים האלה ל-comprehensive_6_users_analyzer.py")
    else:
        print("❌ ההמלצה: נדרש ניתוח ידני נוסף או יותר היסטוריה")
    
    print("=" * 60)
    
    return discovered_info

def main():
    """פונקציה ראשית"""
    
    # בדיקת פרמטרים
    if len(sys.argv) != 2:
        print("❌ שימוש: python manual_user_analyzer.py <chat_id>")
        print("📝 דוגמה: python manual_user_analyzer.py 5676571979")
        sys.exit(1)
    
    chat_id = sys.argv[1]
    
    # וידוא שזה מספר
    if not chat_id.isdigit():
        print("❌ chat_id חייב להיות מספר")
        sys.exit(1)
    
    print(f"🚀 מתחיל ניתוח עבור משתמש {chat_id}")
    print(f"🕐 זמן: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ביצוע הניתוח
    result = analyze_single_user(chat_id)
    
    if result:
        print(f"\n🎉 הניתוח הושלם בהצלחה!")
        print(f"📋 נמצאו {len(result)} פרטי מידע")
    else:
        print(f"\n📝 הניתוח הושלם, אך לא נמצא מידע מובנה")

if __name__ == "__main__":
    main() 