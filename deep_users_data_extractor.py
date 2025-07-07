#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
deep_users_data_extractor.py
============================
🔍 חילוץ נתונים מעמיק של 5 המשתמשים הנותרים

👥 משתמשים: 1118251087, 179392777, 7957193610, 5526006524, 7186596694

🚀 הפעלה: python deep_users_data_extractor.py

✅ מה הסקריפט עושה:
1. מחפש נתונים בכל הקבצים הזמינים
2. מנתח הודעות, פרופילים וסטטיסטיקות
3. חולץ מידע אישי בעזרת regex
4. יוצר סיכומים מפורטים
5. מעדכן את הקובץ auto_summary_updater.py
"""

import os
import json
import re
from datetime import datetime
import glob

# משתמשים לחיפוש
TARGET_USERS = [
    "1118251087",
    "179392777", 
    "7957193610",
    "5526006524",
    "7186596694"
]

def search_all_files():
    """חיפוש נתונים בכל הקבצים הזמינים"""
    print("🔍 מחפש נתונים בכל הקבצים...")
    
    # סוגי קבצים לחיפוש
    file_patterns = [
        "*.json",
        "*.txt", 
        "data/*.json",
        "temp_files/*.json",
        "chat_history_*.txt",
        "extracted_*.json",
        "user_*.json"
    ]
    
    found_files = []
    for pattern in file_patterns:
        found_files.extend(glob.glob(pattern))
    
    print(f"📂 נמצאו {len(found_files)} קבצים לבדיקה")
    
    user_data = {user_id: {'files': [], 'messages': [], 'profile': {}} for user_id in TARGET_USERS}
    
    for file_path in found_files:
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # חיפוש במבנים שונים
                check_json_for_users(data, user_data, file_path)
                
            elif file_path.endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # בדיקה אם הקובץ מכיל נתונים על המשתמשים
                for user_id in TARGET_USERS:
                    if user_id in content:
                        user_data[user_id]['files'].append(file_path)
                        user_data[user_id]['raw_content'] = content
                        
        except Exception as e:
            print(f"⚠️ שגיאה בקריאת {file_path}: {e}")
    
    return user_data

def check_json_for_users(data, user_data, file_path):
    """בדיקת JSON עבור נתוני משתמשים"""
    
    # בדיקה ברמה העליונה
    if isinstance(data, dict):
        for user_id in TARGET_USERS:
            if user_id in data:
                user_data[user_id]['files'].append(file_path)
                user_data[user_id]['profile'].update(data[user_id])
    
    # בדיקה ברשימת הודעות
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and 'user_id' in item:
                user_id = str(item['user_id'])
                if user_id in TARGET_USERS:
                    user_data[user_id]['files'].append(file_path)
                    user_data[user_id]['messages'].append(item)
    
    # בדיקה רקורסיבית
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                check_json_for_users(value, user_data, file_path)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                check_json_for_users(item, user_data, file_path)

def analyze_user_messages(user_id, messages):
    """ניתוח הודעות משתמש"""
    if not messages:
        return {}
    
    discovered = {}
    all_text = ' '.join([msg.get('user_message', '') for msg in messages])
    
    # גיל
    age_patterns = [
        r'בן (\d+)', r'אני (\d+)', r'גיל (\d+)', 
        r'בת (\d+)', r'(\d+) שנים', r'(\d+) שנה'
    ]
    for pattern in age_patterns:
        match = re.search(pattern, all_text)
        if match:
            age = int(match.group(1))
            if 15 <= age <= 90:
                discovered['age'] = age
                break
    
    # מצב משפחתי
    if re.search(r'נשוי|נישאתי|אשתי|הבעל שלי', all_text):
        discovered['relationship_status'] = 'נשוי'
    elif re.search(r'גרוש|גרושה|התגרשתי', all_text):
        discovered['relationship_status'] = 'גרוש'
    elif re.search(r'רווק|רווקה|לא נשוי', all_text):
        discovered['relationship_status'] = 'רווק'
    
    # דתיות
    if re.search(r'חילוני|חילונית|לא דתי', all_text):
        discovered['religiosity'] = 'חילוני'
    elif re.search(r'מסורתי|מסורתית', all_text):
        discovered['religiosity'] = 'מסורתי'
    elif re.search(r'דתי|דתית', all_text):
        discovered['religiosity'] = 'דתי'
    elif re.search(r'חרדי|חרדית', all_text):
        discovered['religiosity'] = 'חרדי'
    
    # מצב ארון
    if re.search(r'בארון|בסוד|חושש לספר', all_text):
        discovered['closet_status'] = 'בארון'
    elif re.search(r'חלק יודעים|כמה יודעים', all_text):
        discovered['closet_status'] = 'חלקית מחוץ לארון'
    elif re.search(r'כולם יודעים|יצאתי מהארון', all_text):
        discovered['closet_status'] = 'מחוץ לארון'
    
    # מטרות
    if re.search(r'מחפש קשר|רוצה בן זוג|מחפש אהבה', all_text):
        discovered['goal'] = 'מחפש קשר'
    elif re.search(r'מחפש חברים|רוצה חברות', all_text):
        discovered['goal'] = 'מחפש חברות'
    
    # קונפליקטים
    conflict_keywords = ['מתמודד', 'מתקשה', 'הבעיה', 'קשה לי', 'סובל']
    for keyword in conflict_keywords:
        if keyword in all_text:
            start = all_text.find(keyword)
            conflict_snippet = all_text[start:start+100].strip()
            discovered['main_conflict'] = conflict_snippet
            break
    
    # סטטיסטיקות
    discovered['message_count'] = len(messages)
    discovered['total_text_length'] = len(all_text)
    
    return discovered

def generate_improved_summary(user_id, profile, discovered, messages):
    """יצירת סיכום משופר"""
    parts = []
    
    # מידע בסיסי
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
    
    # מטרות
    goal = discovered.get('goal') or profile.get('goal_in_course')
    if goal:
        parts.append(f"מטרה: {goal}")
    
    # קונפליקט
    conflict = discovered.get('main_conflict') or profile.get('primary_conflict')
    if conflict:
        conflict_short = conflict[:50] + "..." if len(conflict) > 50 else conflict
        parts.append(f"אתגר: {conflict_short}")
    
    # פעילות
    msg_count = discovered.get('message_count', 0)
    if msg_count > 0:
        parts.append(f"פעיל ({msg_count} הודעות)")
    
    # בדיקה אם יש מספיק נתונים
    if len(parts) < 3:
        return f"משתמש {user_id} - נתונים חלקיים, צריך ניתוח נוסף מהיסטוריית הצ'אט המלאה."
    
    summary = ". ".join(parts)
    
    # הגבלת אורך
    if len(summary) > 400:
        summary = summary[:397] + "..."
    
    return summary

def update_auto_summary_file(improved_summaries):
    """עדכון קובץ auto_summary_updater.py עם סיכומים מעודכנים"""
    print("📝 מעדכן את קובץ auto_summary_updater.py...")
    
    # קריאת הקובץ הקיים
    try:
        with open('auto_summary_updater.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # הכנת הסיכומים החדשים
        new_summaries_dict = {}
        
        # העתקת הסיכומים הקיימים
        for user_id, data in improved_summaries.items():
            if data['summary'] and 'צריך ניתוח נוסף' not in data['summary']:
                new_summaries_dict[user_id] = {
                    "summary": data['summary'],
                    "confidence": "medium",
                    "source": "deep_analysis"
                }
            else:
                new_summaries_dict[user_id] = {
                    "summary": data['summary'],
                    "confidence": "low",
                    "source": "minimal_data"
                }
        
        # שמירת הקובץ המעודכן
        updated_filename = f'auto_summary_updater_improved_{datetime.now().strftime("%Y%m%d_%H%M%S")}.py'
        
        # החלפת המילון בקובץ
        import ast
        import re
        
        # מציאת ועדכון המילון USERS_SUMMARIES
        pattern = r'USERS_SUMMARIES = \{[^}]+\}'
        new_dict_str = f"USERS_SUMMARIES = {json.dumps(new_summaries_dict, ensure_ascii=False, indent=4)}"
        
        # החלפה בקובץ
        updated_content = re.sub(pattern, new_dict_str, content, flags=re.DOTALL)
        
        with open(updated_filename, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"✅ קובץ מעודכן נשמר ב-{updated_filename}")
        return updated_filename
        
    except Exception as e:
        print(f"❌ שגיאה בעדכון הקובץ: {e}")
        return None

def main():
    """פונקציה ראשית"""
    print("🔍 מתחיל חילוץ נתונים מעמיק")
    print("=" * 60)
    
    # חיפוש נתונים
    user_data = search_all_files()
    
    print(f"\n📊 תוצאות חיפוש:")
    for user_id in TARGET_USERS:
        data = user_data[user_id]
        print(f"👤 {user_id}: {len(data['files'])} קבצים, {len(data['messages'])} הודעות")
    
    # ניתוח והכנת סיכומים
    print(f"\n🔍 מנתח נתונים ויוצר סיכומים...")
    improved_summaries = {}
    
    for user_id in TARGET_USERS:
        data = user_data[user_id]
        
        # ניתוח הודעות
        discovered = analyze_user_messages(user_id, data['messages'])
        
        # יצירת סיכום
        summary = generate_improved_summary(user_id, data['profile'], discovered, data['messages'])
        
        improved_summaries[user_id] = {
            'summary': summary,
            'discovered_info': discovered,
            'profile_data': data['profile'],
            'files_found': data['files'],
            'message_count': len(data['messages'])
        }
        
        print(f"✅ {user_id}: {summary[:80]}...")
    
    # שמירת תוצאות
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_filename = f'deep_analysis_results_{timestamp}.json'
    
    with open(results_filename, 'w', encoding='utf-8') as f:
        json.dump(improved_summaries, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 תוצאות נשמרו ב-{results_filename}")
    
    # עדכון קובץ העדכון האוטומטי
    updated_file = update_auto_summary_file(improved_summaries)
    
    # הצגת תוצאות סופיות
    print("\n📋 סיכומים מעודכנים:")
    print("=" * 50)
    
    for user_id, data in improved_summaries.items():
        print(f"\n👤 {user_id}:")
        print(f"📄 {data['summary']}")
        print(f"🔍 מידע שהתגלה: {len(data['discovered_info'])} פרטים")
        print(f"📊 מקורות: {len(data['files_found'])} קבצים, {data['message_count']} הודעות")
    
    print(f"\n🎯 החילוץ הושלם!")
    if updated_file:
        print(f"📝 הפעל עכשיו: python {updated_file}")
    else:
        print("📝 הפעל עכשיו: python auto_summary_updater.py")

if __name__ == "__main__":
    main() 