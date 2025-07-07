#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
simple_users_analyzer.py
========================
🎯 ניתוח פשוט וישיר של 6 משתמשים מהנתונים הזמינים

👥 משתמשים: 1118251087, 179392777, 5676571979, 7957193610, 5526006524, 7186596694

🚀 הפעלה: python simple_users_analyzer.py
"""

import os
import json
import re
from datetime import datetime

# המשתמשים לניתוח
TARGET_USERS = [
    "1118251087",
    "179392777", 
    "5676571979",
    "7957193610",
    "5526006524",
    "7186596694"
]

def load_local_data():
    """טעינת כל הנתונים המקומיים הזמינים"""
    print("📂 טוען נתונים מקומיים...")
    
    data = {
        'chat_data': {},
        'profiles': {},
        'stats': {},
        'raw_texts': {}
    }
    
    # קובץ הסטטיסטיקות
    stats_file = "temp_files/user_messages_stats.json"
    if os.path.exists(stats_file):
        with open(stats_file, 'r', encoding='utf-8') as f:
            data['stats'] = json.load(f)
        print(f"✅ נטען: {stats_file}")
    
    # קובץ ההודעות המחולצות
    messages_file = "temp_files/extracted_all_messages.json"
    if os.path.exists(messages_file):
        with open(messages_file, 'r', encoding='utf-8') as f:
            messages = json.load(f)
            # סידור לפי משתמש
            for msg in messages:
                user_id = msg.get('user_id')
                if user_id in TARGET_USERS:
                    if user_id not in data['chat_data']:
                        data['chat_data'][user_id] = []
                    data['chat_data'][user_id].append(msg)
        print(f"✅ נטען: {messages_file}")
    
    # קובץ הצ'אט של המשתמש הספציפי
    text_file = "chat_history_5676571979.txt"
    if os.path.exists(text_file):
        with open(text_file, 'r', encoding='utf-8') as f:
            data['raw_texts']['5676571979'] = f.read()
        print(f"✅ נטען: {text_file}")
    
    # נתוני צ'אט עיקריים
    chat_file = "data/chat_history.json"
    if os.path.exists(chat_file):
        with open(chat_file, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
            for user_id in TARGET_USERS:
                if user_id in chat_data:
                    data['chat_data'][user_id] = chat_data[user_id]
        print(f"✅ נטען: {chat_file}")
    
    # פרופילי משתמשים
    profiles_file = "data/user_profiles.json"
    if os.path.exists(profiles_file):
        with open(profiles_file, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
            for user_id in TARGET_USERS:
                if user_id in profiles:
                    data['profiles'][user_id] = profiles[user_id]
        print(f"✅ נטען: {profiles_file}")
    
    return data

def extract_user_messages(user_id, data):
    """חילוץ כל הודעות המשתמש מכל המקורות"""
    user_messages = []
    
    # מטקסט גולמי
    if user_id in data['raw_texts']:
        user_messages.append(data['raw_texts'][user_id])
    
    # מנתוני הצ'אט
    if user_id in data['chat_data']:
        chat_info = data['chat_data'][user_id]
        
        # אם זה רשימה של הודעות
        if isinstance(chat_info, list):
            for msg in chat_info:
                if msg.get('user_message'):
                    user_messages.append(msg['user_message'])
        
        # אם זה אובייקט עם היסטוריה
        elif isinstance(chat_info, dict) and 'history' in chat_info:
            for msg in chat_info['history']:
                if msg.get('user'):
                    user_messages.append(msg['user'])
    
    # איחוד כל הטקסט
    all_text = ' '.join(user_messages)
    return all_text, len(user_messages)

def analyze_text_for_info(text):
    """ניתוח טקסט לחילוץ מידע אישי"""
    discovered = {}
    
    if not text or len(text.strip()) < 10:
        return discovered
    
    # גיל
    age_patterns = [
        r'בן (\d+)', r'אני (\d+)', r'גיל (\d+)', 
        r'בת (\d+)', r'(\d+) שנים', r'(\d+) שנה'
    ]
    for pattern in age_patterns:
        match = re.search(pattern, text)
        if match:
            age = int(match.group(1))
            if 15 <= age <= 90:
                discovered['age'] = age
                break
    
    # מצב משפחתי
    if re.search(r'נשוי|נישאתי|אשתי|הבעל שלי', text):
        discovered['relationship_status'] = 'נשוי'
    elif re.search(r'גרוש|גרושה|התגרשתי', text):
        discovered['relationship_status'] = 'גרוש'
    elif re.search(r'רווק|רווקה|לא נשוי', text):
        discovered['relationship_status'] = 'רווק'
    
    # דתיות
    if re.search(r'חילוני|חילונית|לא דתי', text):
        discovered['religiosity'] = 'חילוני'
    elif re.search(r'מסורתי|מסורתית', text):
        discovered['religiosity'] = 'מסורתי'
    elif re.search(r'דתי|דתית', text):
        discovered['religiosity'] = 'דתי'
    elif re.search(r'חרדי|חרדית', text):
        discovered['religiosity'] = 'חרדי'
    
    # מצב ארון
    if re.search(r'בארון|בסוד|חושש לספר', text):
        discovered['closet_status'] = 'בארון'
    elif re.search(r'חלק יודעים|כמה יודעים', text):
        discovered['closet_status'] = 'חלקית מחוץ לארון'
    elif re.search(r'כולם יודעים|יצאתי מהארון', text):
        discovered['closet_status'] = 'מחוץ לארון'
    
    # ילדים
    if re.search(r'יש לי ילדים|הילדים שלי|ילד שלי|ילדה שלי', text):
        discovered['has_children'] = 'יש ילדים'
    
    # קונפליקט
    conflict_words = ['מתמודד עם', 'מתקשה עם', 'הבעיה שלי', 'מה שמטריד אותי']
    for word in conflict_words:
        if word in text:
            # נסה למצוא 80 תווים אחרי
            start = text.find(word)
            if start != -1:
                conflict_snippet = text[start:start+80].strip()
                discovered['main_conflict'] = conflict_snippet
                break
    
    return discovered

def generate_user_summary(user_id, profile, discovered, stats):
    """יצירת סיכום למשתמש"""
    parts = []
    
    # גיל
    age = discovered.get('age') or profile.get('age')
    if age:
        parts.append(f"בן {age}")
    
    # מצב משפחתי  
    relationship = discovered.get('relationship_status') or profile.get('relationship_type')
    if relationship:
        parts.append(f"מצב משפחתי: {relationship}")
    
    # דתיות
    religiosity = discovered.get('religiosity') or profile.get('self_religiosity_level')
    if religiosity:
        parts.append(f"רמת דתיות: {religiosity}")
    
    # מצב ארון
    closet = discovered.get('closet_status') or profile.get('closet_status')
    if closet:
        parts.append(f"מצב ארון: {closet}")
    
    # ילדים
    children = discovered.get('has_children') or profile.get('parental_status')
    if children:
        parts.append(f"מצב הורי: {children}")
    
    # קונפליקט
    conflict = discovered.get('main_conflict') or profile.get('primary_conflict')
    if conflict:
        conflict_short = conflict[:60] + "..." if len(conflict) > 60 else conflict
        parts.append(f"קונפליקט: {conflict_short}")
    
    # פעילות
    total_msgs = stats.get('total_messages', 0)
    if total_msgs > 0:
        parts.append(f"משתמש פעיל ({total_msgs} הודעות)")
    else:
        parts.append("משתמש")
    
    # תאריך תחילה
    if stats.get('first_message'):
        try:
            first_date = datetime.fromisoformat(stats['first_message'].replace('Z', '')).strftime('%m/%y')
            parts.append(f"מתחיל {first_date}")
        except:
            pass
    
    summary = ". ".join(parts) if parts else f"משתמש {user_id}"
    
    # הגבלת אורך
    if len(summary) > 400:
        summary = summary[:397] + "..."
    
    return summary

def analyze_all_users():
    """ניתוח כל המשתמשים"""
    print("🎯 ניתוח מקיף של 6 משתמשים נבחרים")
    print("=" * 60)
    
    # טעינת נתונים
    data = load_local_data()
    
    print(f"\n📊 סיכום נתונים זמינים:")
    print(f"   💬 צ'אטים: {len(data['chat_data'])}")
    print(f"   👤 פרופילים: {len(data['profiles'])}")
    print(f"   📈 סטטיסטיקות: {len(data['stats'])}")
    print(f"   📄 טקסטים גולמיים: {len(data['raw_texts'])}")
    
    # תוצאות
    results = {}
    summaries_created = {}
    
    print(f"\n🔍 מתחיל ניתוח משתמשים:")
    print("=" * 40)
    
    # ניתוח כל משתמש
    for i, user_id in enumerate(TARGET_USERS, 1):
        print(f"\n📋 משתמש {i}/{len(TARGET_USERS)}: {user_id}")
        print("-" * 25)
        
        # חילוץ הודעות
        user_text, msg_count = extract_user_messages(user_id, data)
        print(f"📈 נמצאו {msg_count} הודעות, {len(user_text)} תווים")
        
        # ניתוח טקסט
        discovered = analyze_text_for_info(user_text)
        print(f"🔍 מידע שהתגלה: {len(discovered)} פרטים")
        for key, value in discovered.items():
            print(f"   • {key}: {value}")
        
        # פרופיל קיים
        profile = data['profiles'].get(user_id, {})
        if profile:
            filled_count = len([v for v in profile.values() if v and str(v).strip()])
            print(f"📋 פרופיל קיים: {filled_count} שדות מלאים")
        else:
            print("📋 אין פרופיל קיים")
        
        # סטטיסטיקות
        stats = data['stats'].get(user_id, {})
        if stats:
            print(f"📊 סטטיסטיקות: {stats.get('total_messages', 0)} הודעות כולל")
        
        # יצירת סיכום
        summary = generate_user_summary(user_id, profile, discovered, stats)
        print(f"📝 סיכום נוצר:")
        print(f"   \"{summary}\"")
        
        # שמירת תוצאות
        results[user_id] = {
            'discovered_info': discovered,
            'existing_profile': profile,
            'stats': stats,
            'summary': summary,
            'message_count': msg_count,
            'text_length': len(user_text)
        }
        
        summaries_created[user_id] = summary
        print(f"✅ ניתוח הושלם")
    
    # הצגת תוצאות סופיות
    print("\n" + "="*60)
    print("📊 תוצאות הניתוח המקיף")
    print("="*60)
    
    for user_id in TARGET_USERS:
        if user_id in results:
            result = results[user_id]
            print(f"\n👤 {user_id}:")
            print(f"   🔍 מידע שהתגלה: {len(result['discovered_info'])} פרטים")
            print(f"   📋 פרופיל קיים: {'✅' if result['existing_profile'] else '❌'}")
            print(f"   📈 הודעות: {result['message_count']}")
            print(f"   📝 סיכום: \"{result['summary'][:100]}...\"")
        else:
            print(f"\n👤 {user_id}: ❌ לא נמצאו נתונים")
    
    print(f"\n📊 סיכום כללי:")
    print(f"   ✅ משתמשים שנותחו: {len(results)}/{len(TARGET_USERS)}")
    print(f"   📝 סיכומים שנוצרו: {len(summaries_created)}")
    print(f"   📈 אחוז הצלחה: {(len(results)/len(TARGET_USERS)*100):.1f}%")
    
    # שמירת תוצאות
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'user_analysis_results_{timestamp}.json'
    
    output_data = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'target_users': TARGET_USERS,
            'analyzed_count': len(results)
        },
        'results': results,
        'summaries': summaries_created
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 תוצאות נשמרו ב-{filename}")
    
    # הצגת הסיכומים שנוצרו
    print(f"\n📋 הסיכומים שנוצרו עבור עמודת SUMMARY:")
    print("=" * 50)
    for user_id, summary in summaries_created.items():
        print(f"\n🆔 {user_id}:")
        print(f"📄 {summary}")
    
    print("\n🎉 הניתוח הושלם בהצלחה!")
    print("💡 עתה ניתן להעתיק את הסיכומים לעמודת SUMMARY במסד הנתונים")
    
    return results

if __name__ == "__main__":
    analyze_all_users() 