#!/usr/bin/env python3
"""
analyze_users.py
---------------
סקריפט לניתוח מעמיק של משתמשים - קריאת היסטוריה, בדיקת פרופיל, והערכת עדכון נתונים
"""

import json
from datetime import datetime
from db_manager import get_chat_history, get_user_profile, save_user_profile
from fields_dict import FIELDS_DICT, get_user_profile_fields, get_summary_fields
# 🗑️ עברנו למסד נתונים - אין צורך ב-Google Sheets!
# from sheets_handler import get_user_summary
from profile_utils import get_user_summary_fast

def analyze_user_chat_history(chat_id):
    """
    מנתח את היסטוריית הצ'אט של משתמש ומחזיר תובנות עליו
    """
    print(f"\n🔍 מנתח היסטוריה של משתמש {chat_id}")
    
    # קבלת היסטוריית הצ'אט
    history = get_chat_history(chat_id, limit=200)  # נקח עד 200 הודעות אחרונות
    
    if not history:
        print(f"❌ לא נמצאה היסטוריה עבור משתמש {chat_id}")
        return None
    
    print(f"📊 נמצאו {len(history)} הודעות")
    
    # חילוץ תובנות מההיסטוריה
    insights = {
        'total_messages': len(history),
        'first_message_date': history[0][2] if history else None,
        'last_message_date': history[-1][2] if history else None,
        'user_messages': [],
        'bot_messages': [],
        'discovered_info': {}
    }
    
    # עיבוד כל הודעה
    for user_msg, bot_msg, timestamp in history:
        if user_msg:
            insights['user_messages'].append({
                'message': user_msg,
                'timestamp': timestamp
            })
        if bot_msg:
            insights['bot_messages'].append({
                'message': bot_msg,
                'timestamp': timestamp
            })
    
    # ניתוח תוכן המשתמש לזיהוי מידע אישי
    all_user_text = ' '.join([msg['message'] for msg in insights['user_messages']])
    
    # חיפוש מידע אישי בסיסי
    insights['discovered_info'] = extract_personal_info_from_text(all_user_text)
    
    return insights

def extract_personal_info_from_text(text):
    """
    מחלץ מידע אישי מטקסט באמצעות חיפוש מילות מפתח
    """
    info = {}
    text_lower = text.lower()
    
    # חיפוש גיל
    import re
    age_patterns = [
        r'בן (\d+)',
        r'בת (\d+)', 
        r'אני (\d+)',
        r'גיל (\d+)',
        r'(\d+) שנים',
        r'(\d+) שנה'
    ]
    
    for pattern in age_patterns:
        matches = re.findall(pattern, text)
        if matches:
            try:
                age = int(matches[0])
                if 18 <= age <= 99:
                    info['age_mentioned'] = age
                    break
            except ValueError:
                continue
    
    # חיפוש מצב משפחתי
    relationship_keywords = {
        'רווק': ['רווק', 'רוק', 'לא נשוי', 'לא נשואה'],
        'נשוי': ['נשוי', 'נשואה', 'אישה', 'בעל', 'אשתי', 'בעלי'],
        'גרוש': ['גרוש', 'גרושה', 'התגרשתי'],
        'בזוגיות': ['בזוגיות', 'חבר', 'חברה', 'בן זוג', 'בת זוג']
    }
    
    for status, keywords in relationship_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                info['relationship_status_mentioned'] = status
                break
    
    # חיפוש מידע על ילדים
    children_keywords = ['ילד', 'ילדה', 'ילדים', 'בן', 'בת', 'נכד', 'נכדה']
    for keyword in children_keywords:
        if keyword in text_lower:
            info['children_mentioned'] = True
            break
    
    # חיפוש מידע דתי
    religious_keywords = {
        'חילוני': ['חילוני', 'חילונית', 'לא דתי', 'לא דתית'],
        'דתי': ['דתי', 'דתית', 'מאמין', 'מאמינה'],
        'מסורתי': ['מסורתי', 'מסורתית'],
        'חרדי': ['חרדי', 'חרדית']
    }
    
    for level, keywords in religious_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                info['religiosity_mentioned'] = level
                break
    
    # חיפוש מידע על עיסוק
    occupation_keywords = ['עובד', 'עובדת', 'סטודנט', 'סטודנטית', 'מורה', 'מנהל', 'הייטק', 'רופא', 'עורך דין', 'מהנדס']
    for keyword in occupation_keywords:
        if keyword in text_lower:
            info['occupation_mentioned'] = keyword
            break
    
    # חיפוש מידע על ארון
    closet_keywords = {
        'בארון': ['בארון', 'לא יודעים', 'סודי', 'מסתיר'],
        'יצאתי': ['יצאתי', 'יצאתי מהארון', 'כולם יודעים', 'פתוח'],
        'חלקי': ['חלקי', 'חלק יודעים', 'לא כולם יודעים']
    }
    
    for status, keywords in closet_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                info['closet_status_mentioned'] = status
                break
    
    return info

def analyze_user_profile(chat_id):
    """
    מנתח את הפרופיל הקיים של המשתמש
    """
    print(f"\n📋 מנתח פרופיל קיים של משתמש {chat_id}")
    
    profile = get_user_profile(chat_id)
    
    if not profile:
        print(f"❌ לא נמצא פרופיל קיים עבור משתמש {chat_id}")
        return None
    
    print(f"✅ נמצא פרופיל קיים")
    
    # בדיקת שדות מלאים ריקים
    filled_fields = []
    empty_fields = []
    
    for field in get_user_profile_fields():
        if field in profile and profile[field] and str(profile[field]).strip():
            filled_fields.append(field)
        else:
            empty_fields.append(field)
    
    analysis = {
        'profile_exists': True,
        'filled_fields': filled_fields,
        'empty_fields': empty_fields,
        'completion_rate': len(filled_fields) / len(get_user_profile_fields()) * 100,
        'summary_exists': bool(profile.get('summary', '').strip()),
        'profile_data': profile
    }
    
    print(f"📊 שדות מלאים: {len(filled_fields)}/{len(get_user_profile_fields())} ({analysis['completion_rate']:.1f}%)")
    print(f"📝 סיכום קיים: {'✅' if analysis['summary_exists'] else '❌'}")
    
    return analysis

def compare_history_with_profile(chat_id, history_insights, profile_analysis):
    """
    משווה בין המידע שהתגלה בהיסטוריה לבין הפרופיל הקיים
    """
    print(f"\n🔄 משווה היסטוריה עם פרופיל עבור משתמש {chat_id}")
    
    if not history_insights or not profile_analysis:
        print("❌ לא ניתן לבצע השוואה - חסר מידע")
        return None
    
    discrepancies = []
    missing_updates = []
    
    discovered_info = history_insights['discovered_info']
    profile_data = profile_analysis['profile_data']
    
    # בדיקת גיל
    if 'age_mentioned' in discovered_info:
        discovered_age = discovered_info['age_mentioned']
        profile_age = profile_data.get('age')
        
        if not profile_age:
            missing_updates.append({
                'field': 'age',
                'discovered_value': discovered_age,
                'current_value': None,
                'recommendation': f'להוסיף גיל: {discovered_age}'
            })
        elif int(profile_age) != discovered_age:
            discrepancies.append({
                'field': 'age',
                'discovered_value': discovered_age,
                'current_value': profile_age,
                'recommendation': f'לעדכן גיל מ-{profile_age} ל-{discovered_age}'
            })
    
    # בדיקת מצב משפחתי
    if 'relationship_status_mentioned' in discovered_info:
        discovered_status = discovered_info['relationship_status_mentioned']
        profile_status = profile_data.get('relationship_type')
        
        if not profile_status:
            missing_updates.append({
                'field': 'relationship_type',
                'discovered_value': discovered_status,
                'current_value': None,
                'recommendation': f'להוסיף מצב משפחתי: {discovered_status}'
            })
        elif discovered_status.lower() not in str(profile_status).lower():
            discrepancies.append({
                'field': 'relationship_type',
                'discovered_value': discovered_status,
                'current_value': profile_status,
                'recommendation': f'לבדוק התאמה: נמצא "{discovered_status}" אך בפרופיל "{profile_status}"'
            })
    
    # בדיקת מידע דתי
    if 'religiosity_mentioned' in discovered_info:
        discovered_religiosity = discovered_info['religiosity_mentioned']
        profile_religiosity = profile_data.get('self_religiosity_level')
        
        if not profile_religiosity:
            missing_updates.append({
                'field': 'self_religiosity_level',
                'discovered_value': discovered_religiosity,
                'current_value': None,
                'recommendation': f'להוסיף רמת דתיות: {discovered_religiosity}'
            })
        elif discovered_religiosity.lower() not in str(profile_religiosity).lower():
            discrepancies.append({
                'field': 'self_religiosity_level',
                'discovered_value': discovered_religiosity,
                'current_value': profile_religiosity,
                'recommendation': f'לבדוק התאמה: נמצא "{discovered_religiosity}" אך בפרופיל "{profile_religiosity}"'
            })
    
    # בדיקת מידע על ארון
    if 'closet_status_mentioned' in discovered_info:
        discovered_closet = discovered_info['closet_status_mentioned']
        profile_closet = profile_data.get('closet_status')
        
        if not profile_closet:
            missing_updates.append({
                'field': 'closet_status',
                'discovered_value': discovered_closet,
                'current_value': None,
                'recommendation': f'להוסיף מצב ארון: {discovered_closet}'
            })
        elif discovered_closet.lower() not in str(profile_closet).lower():
            discrepancies.append({
                'field': 'closet_status',
                'discovered_value': discovered_closet,
                'current_value': profile_closet,
                'recommendation': f'לבדוק התאמה: נמצא "{discovered_closet}" אך בפרופיל "{profile_closet}"'
            })
    
    comparison = {
        'discrepancies': discrepancies,
        'missing_updates': missing_updates,
        'needs_update': len(discrepancies) > 0 or len(missing_updates) > 0
    }
    
    print(f"⚠️  סתירות: {len(discrepancies)}")
    print(f"➕ עדכונים חסרים: {len(missing_updates)}")
    print(f"🔄 נדרש עדכון: {'✅' if comparison['needs_update'] else '❌'}")
    
    return comparison

def generate_user_summary(chat_id, history_insights, profile_analysis):
    """
    מייצר סיכום משתמש מבוסס על ההיסטוריה והפרופיל
    """
    print(f"\n📝 מייצר סיכום עבור משתמש {chat_id}")
    
    if not history_insights:
        print("❌ לא ניתן לייצר סיכום - חסרה היסטוריה")
        return None
    
    # בסיס הסיכום
    summary_parts = []
    
    # מידע בסיסי
    if history_insights['total_messages'] > 0:
        summary_parts.append(f"משתמש פעיל עם {history_insights['total_messages']} הודעות")
    
    # מידע שהתגלה מההיסטוריה
    discovered = history_insights['discovered_info']
    
    if 'age_mentioned' in discovered:
        summary_parts.append(f"בן {discovered['age_mentioned']}")
    
    if 'relationship_status_mentioned' in discovered:
        summary_parts.append(f"מצב משפחתי: {discovered['relationship_status_mentioned']}")
    
    if 'religiosity_mentioned' in discovered:
        summary_parts.append(f"רמת דתיות: {discovered['religiosity_mentioned']}")
    
    if 'closet_status_mentioned' in discovered:
        summary_parts.append(f"מצב ארון: {discovered['closet_status_mentioned']}")
    
    if 'occupation_mentioned' in discovered:
        summary_parts.append(f"עיסוק: {discovered['occupation_mentioned']}")
    
    # מידע מהפרופיל הקיים
    if profile_analysis and profile_analysis['profile_exists']:
        profile_data = profile_analysis['profile_data']
        
        # הוספת מידע חשוב מהפרופיל
        important_fields = ['name', 'primary_conflict', 'goal_in_course', 'fears_concerns']
        for field in important_fields:
            if field in profile_data and profile_data[field]:
                field_label = FIELDS_DICT[field]['label']
                summary_parts.append(f"{field_label}: {profile_data[field]}")
    
    # חישוב תאריכים
    if history_insights['first_message_date']:
        first_date = history_insights['first_message_date']
        summary_parts.append(f"תחילת שיחה: {first_date.strftime('%d/%m/%Y')}")
    
    summary = ". ".join(summary_parts)
    
    print(f"📝 סיכום נוצר: {len(summary)} תווים")
    
    return summary

def analyze_single_user(chat_id):
    """
    מנתח משתמש בודד במלואו
    """
    print(f"\n" + "="*60)
    print(f"🔍 מתחיל ניתוח מעמיק של משתמש {chat_id}")
    print("="*60)
    
    # שלב 1: ניתוח היסטוריה
    history_insights = analyze_user_chat_history(chat_id)
    
    # שלב 2: ניתוח פרופיל קיים
    profile_analysis = analyze_user_profile(chat_id)
    
    # שלב 3: השוואה
    comparison = compare_history_with_profile(chat_id, history_insights, profile_analysis)
    
    # שלב 4: יצירת סיכום
    suggested_summary = generate_user_summary(chat_id, history_insights, profile_analysis)
    
    # שלב 5: הצגת תוצאות
    print(f"\n📊 תוצאות ניתוח עבור משתמש {chat_id}")
    print("-" * 50)
    
    if history_insights:
        print(f"📈 סה״כ הודעות: {history_insights['total_messages']}")
        if history_insights['first_message_date']:
            print(f"📅 תחילת שיחה: {history_insights['first_message_date'].strftime('%d/%m/%Y %H:%M')}")
        if history_insights['last_message_date']:
            print(f"📅 הודעה אחרונה: {history_insights['last_message_date'].strftime('%d/%m/%Y %H:%M')}")
    
    if profile_analysis:
        print(f"📋 שלמות פרופיל: {profile_analysis['completion_rate']:.1f}%")
        print(f"📝 סיכום קיים: {'✅' if profile_analysis['summary_exists'] else '❌'}")
    
    if comparison:
        print(f"⚠️  סתירות: {len(comparison['discrepancies'])}")
        print(f"➕ עדכונים חסרים: {len(comparison['missing_updates'])}")
        
        if comparison['discrepancies']:
            print("\n🔍 סתירות שנמצאו:")
            for disc in comparison['discrepancies']:
                print(f"  • {disc['field']}: {disc['recommendation']}")
        
        if comparison['missing_updates']:
            print("\n➕ עדכונים מוצעים:")
            for update in comparison['missing_updates']:
                print(f"  • {update['field']}: {update['recommendation']}")
    
    if suggested_summary:
        print(f"\n📝 סיכום מוצע:")
        print(f"  {suggested_summary}")
    
    return {
        'chat_id': chat_id,
        'history_insights': history_insights,
        'profile_analysis': profile_analysis,
        'comparison': comparison,
        'suggested_summary': suggested_summary
    }

def main():
    """
    מנתח את כל המשתמשים הנדרשים
    """
    users_to_analyze = [
        "1118251087",
        "179392777", 
        "5676571979",
        "7957193610",
        "5526006524",
        "7186596694"
    ]
    
    print("🚀 מתחיל ניתוח מעמיק של משתמשים")
    print(f"👥 {len(users_to_analyze)} משתמשים לניתוח")
    
    all_results = []
    
    for chat_id in users_to_analyze:
        try:
            result = analyze_single_user(chat_id)
            all_results.append(result)
        except Exception as e:
            print(f"❌ שגיאה בניתוח משתמש {chat_id}: {e}")
            continue
    
    # סיכום כללי
    print("\n" + "="*60)
    print("📊 סיכום כללי")
    print("="*60)
    
    users_need_update = 0
    total_discrepancies = 0
    total_missing_updates = 0
    
    for result in all_results:
        if result['comparison'] and result['comparison']['needs_update']:
            users_need_update += 1
            total_discrepancies += len(result['comparison']['discrepancies'])
            total_missing_updates += len(result['comparison']['missing_updates'])
    
    print(f"👥 משתמשים שנותחו: {len(all_results)}")
    print(f"🔄 משתמשים שדורשים עדכון: {users_need_update}")
    print(f"⚠️  סה״כ סתירות: {total_discrepancies}")
    print(f"➕ סה״כ עדכונים חסרים: {total_missing_updates}")
    
    # שמירת תוצאות לקובץ
    with open('user_analysis_results.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 תוצאות נשמרו בקובץ user_analysis_results.json")
    
    return all_results

if __name__ == "__main__":
    main() 