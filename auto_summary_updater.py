#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
auto_summary_updater.py
=======================
🎯 עדכון אוטומטי של עמודת SUMMARY במסד הנתונים

👥 משתמשים: 1118251087, 179392777, 5676571979, 7957193610, 5526006524, 7186596694

🚀 הפעלה פשוטה:
python auto_summary_updater.py

✅ מה הסקריפט עושה:
1. מעדכן את עמודת SUMMARY לכל 6 המשתמשים
2. שומר backup של הנתונים הקודמים
3. מציג דו"ח מפורט על העדכונים
4. מבצע בדיקת תקינות לאחר העדכון
"""

import os
import json
from datetime import datetime
import traceback

# יבוא הפונקציות הנדרשות
try:
    from bot_setup import load_user_profile, save_user_profile, get_db_connection
    from config import config
except ImportError as e:
    print(f"❌ שגיאה ביבוא: {e}")
    print("💡 וודא שהקבצים bot_setup.py ו-config.py זמינים")
    exit(1)

# נתוני המשתמשים והסיכומים שלהם
USERS_SUMMARIES = {
    "5676571979": {
        "summary": "בן 60, חילוני, גרוש שנים רבות. יש ילדים מגרושה. בארון - רק בודדים יודעים. בשנים האחרונות נמשך רק לגברים, איבד תשוקה לנשים. מתמודד עם עייפות מחיפוש מתמיד, רוצה קשר קבוע ויציב. כמה לחברות אמיתית, אהבה רגשית ופיזית חופשית. רוצה יותר שמחה בחיים. סובל מבדידות ומלחץ חברתי. פעם ראשונה נוגע בנושא - אמר לעצמו 'אני הומו' בפעם הראשונה.",
        "confidence": "high",
        "source": "detailed_chat_analysis"
    },
    "1118251087": {
        "summary": "משתמש רשום במערכת. נתונים חלקיים - צריך ניתוח מעמיק נוסף לחילוץ פרופיל מלא מהיסטוריית הצ'אט.",
        "confidence": "low",
        "source": "system_data_only"
    },
    "179392777": {
        "summary": "משתמש רשום במערכת. נתונים חלקיים - צריך ניתוח מעמיק נוסף לחילוץ פרופיל מלא מהיסטוריית הצ'אט.",
        "confidence": "low",
        "source": "system_data_only"
    },
    "7957193610": {
        "summary": "משתמש רשום במערכת. נתונים חלקיים - צריך ניתוח מעמיק נוסף לחילוץ פרופיל מלא מהיסטוריית הצ'אט.",
        "confidence": "low",
        "source": "system_data_only"
    },
    "5526006524": {
        "summary": "משתמש רשום במערכת. נתונים חלקיים - צריך ניתוח מעמיק נוסף לחילוץ פרופיל מלא מהיסטוריית הצ'אט.",
        "confidence": "low",
        "source": "system_data_only"
    },
    "7186596694": {
        "summary": "משתמש רשום במערכת. נתונים חלקיים - צריך ניתוח מעמיק נוסף לחילוץ פרופיל מלא מהיסטוריית הצ'אט.",
        "confidence": "low",
        "source": "system_data_only"
    }
}

def create_backup():
    """יצירת גיבוי של הנתונים הקיימים"""
    print("💾 יוצר גיבוי של הנתונים הקיימים...")
    
    backup_data = {}
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    for user_id in USERS_SUMMARIES.keys():
        try:
            profile = load_user_profile(user_id)
            backup_data[user_id] = {
                'profile': profile,
                'timestamp': timestamp
            }
            print(f"✅ גיבוי משתמש {user_id}: {len(profile)} שדות")
        except Exception as e:
            print(f"⚠️ לא ניתן לטעון פרופיל עבור {user_id}: {e}")
            backup_data[user_id] = {
                'profile': None,
                'error': str(e),
                'timestamp': timestamp
            }
    
    backup_filename = f'backup_before_summary_update_{timestamp}.json'
    with open(backup_filename, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ גיבוי נשמר ב-{backup_filename}")
    return backup_filename

def update_user_summary(user_id, summary_data):
    """עדכון סיכום משתמש בודד"""
    try:
        # טעינת פרופיל קיים
        profile = load_user_profile(user_id)
        
        # שמירת הסיכום הקודם
        old_summary = profile.get('summary', '')
        
        # עדכון הסיכום
        profile['summary'] = summary_data['summary']
        
        # הוספת מטא-דטה
        profile['summary_updated'] = datetime.now().isoformat()
        profile['summary_confidence'] = summary_data['confidence']
        profile['summary_source'] = summary_data['source']
        
        # שמירה במסד הנתונים
        save_user_profile(user_id, profile)
        
        return {
            'success': True,
            'old_summary': old_summary,
            'new_summary': summary_data['summary'],
            'profile_fields': len(profile)
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }

def verify_updates():
    """אימות שהעדכונים בוצעו בהצלחה"""
    print("\n🔍 מבצע אימות של העדכונים...")
    
    verification_results = {}
    
    for user_id, expected_data in USERS_SUMMARIES.items():
        try:
            profile = load_user_profile(user_id)
            current_summary = profile.get('summary', '')
            
            if current_summary == expected_data['summary']:
                verification_results[user_id] = {
                    'status': 'verified',
                    'summary_length': len(current_summary),
                    'updated_time': profile.get('summary_updated', 'לא זמין')
                }
                print(f"✅ {user_id}: סיכום מאומת ({len(current_summary)} תווים)")
            else:
                verification_results[user_id] = {
                    'status': 'mismatch',
                    'expected_length': len(expected_data['summary']),
                    'actual_length': len(current_summary),
                    'expected_preview': expected_data['summary'][:100] + "...",
                    'actual_preview': current_summary[:100] + "..." if current_summary else "ריק"
                }
                print(f"❌ {user_id}: אי-התאמה בסיכום")
        
        except Exception as e:
            verification_results[user_id] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"⚠️ {user_id}: שגיאה באימות - {e}")
    
    return verification_results

def main():
    """פונקציה ראשית"""
    print("🎯 מתחיל עדכון אוטומטי של עמודת SUMMARY")
    print("=" * 60)
    
    # יצירת גיבוי
    backup_file = create_backup()
    
    # עדכון המשתמשים
    print(f"\n📝 מעדכן {len(USERS_SUMMARIES)} משתמשים...")
    
    results = {}
    success_count = 0
    
    for user_id, summary_data in USERS_SUMMARIES.items():
        print(f"\n👤 עדכון משתמש {user_id}:")
        print(f"   📄 סיכום: {summary_data['summary'][:80]}...")
        print(f"   🔍 רמת ביטחון: {summary_data['confidence']}")
        
        result = update_user_summary(user_id, summary_data)
        results[user_id] = result
        
        if result['success']:
            success_count += 1
            print(f"   ✅ עודכן בהצלחה")
            print(f"   📊 שדות בפרופיל: {result['profile_fields']}")
            
            # השוואת סיכומים
            if result['old_summary']:
                print(f"   📋 סיכום קודם: {result['old_summary'][:60]}...")
            else:
                print(f"   📋 סיכום קודם: לא היה")
        else:
            print(f"   ❌ שגיאה: {result['error']}")
    
    # אימות עדכונים
    verification_results = verify_updates()
    
    # סיכום תוצאות
    print("\n" + "=" * 60)
    print("📊 סיכום תוצאות:")
    print(f"   ✅ עדכונים מוצלחים: {success_count}/{len(USERS_SUMMARIES)}")
    print(f"   💾 גיבוי נשמר ב-{backup_file}")
    
    verified_count = sum(1 for r in verification_results.values() if r.get('status') == 'verified')
    print(f"   🔍 עדכונים מאומתים: {verified_count}/{len(USERS_SUMMARIES)}")
    
    if success_count == len(USERS_SUMMARIES) and verified_count == len(USERS_SUMMARIES):
        print("\n🎉 כל העדכונים הושלמו בהצלחה!")
        print("✅ עמודת SUMMARY עודכנה לכל המשתמשים")
    else:
        print("\n⚠️ יש בעיות בעדכון - בדוק את התוצאות למעלה")
    
    # שמירת דו"ח מפורט
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f'summary_update_report_{timestamp}.json'
    
    report_data = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'backup_file': backup_file,
            'total_users': len(USERS_SUMMARIES),
            'successful_updates': success_count,
            'verified_updates': verified_count
        },
        'update_results': results,
        'verification_results': verification_results,
        'summaries_applied': USERS_SUMMARIES
    }
    
    with open(report_filename, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 דו\"ח מפורט נשמר ב-{report_filename}")
    
    # הצגת הסיכומים החדשים
    print("\n📋 הסיכומים שעודכנו:")
    print("=" * 40)
    for user_id, summary_data in USERS_SUMMARIES.items():
        status = "✅" if results[user_id]['success'] else "❌"
        print(f"\n{status} {user_id}:")
        print(f"📄 {summary_data['summary']}")
    
    print("\n🎯 העדכון הושלם!")

if __name__ == "__main__":
    main() 