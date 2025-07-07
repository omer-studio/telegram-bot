#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ניתוח מהיר של נתוני משתמשים
מנתח את הנתונים הזמינים ויוצר המלצות לעדכון פרופילים
"""

import re
import json
from datetime import datetime

# השדות מ-FIELDS_DICT
USER_FIELDS = [
    "name", "age", "pronoun_preference", "occupation_or_role", "attracted_to", 
    "relationship_type", "parental_status", "self_religious_affiliation", 
    "self_religiosity_level", "family_religiosity", "closet_status", 
    "who_knows", "who_doesnt_know", "attends_therapy", "primary_conflict", 
    "trauma_history", "goal_in_course", "language_of_strength", 
    "coping_strategies", "fears_concerns", "future_vision", "other_insights"
]

# רשימת המשתמשים לניתוח
TARGET_USERS = [
    "1118251087", "179392777", "5676571979", 
    "7957193610", "5526006524", "7186596694"
]

def analyze_chat_text(text):
    """מנתח טקסט צ'אט ומחלץ מידע אישי"""
    insights = {}
    
    # גיל
    age_patterns = [
        r'בן (\d+)',
        r'(\d+) שנ',
        r'גיל (\d+)',
        r'אני (\d+)'
    ]
    for pattern in age_patterns:
        match = re.search(pattern, text)
        if match:
            insights["age"] = int(match.group(1))
            break
    
    # דתיות
    if any(word in text for word in ["חילוני", "לא דתי"]):
        insights["self_religiosity_level"] = "חילוני"
    elif any(word in text for word in ["דתי", "שומר מצוות"]):
        insights["self_religiosity_level"] = "דתי"
    elif "מסורתי" in text:
        insights["self_religiosity_level"] = "מסורתי"
    
    # מצב אישי
    if any(word in text for word in ["גרוש", "גירושין"]):
        insights["relationship_type"] = "גרוש"
    elif any(word in text for word in ["נשוי", "נישואין"]):
        insights["relationship_type"] = "נשוי"
    elif "רווק" in text:
        insights["relationship_type"] = "רווק"
    
    # ילדים
    children_patterns = [
        r'(\d+) ילדים',
        r'יש לי ילד',
        r'הילדים שלי',
        r'ילדי'
    ]
    for pattern in children_patterns:
        if re.search(pattern, text):
            insights["parental_status"] = "יש ילדים"
            break
    
    # מצב ארון
    if any(phrase in text for phrase in ["בארון", "לא יודעים", "סוד"]):
        insights["closet_status"] = "בארון"
    elif any(phrase in text for phrase in ["יצאתי", "כולם יודעים"]):
        insights["closet_status"] = "יצא מהארון"
    
    # משיכה מינית
    if any(phrase in text for phrase in ["רק לגברים", "נמשך לגברים"]):
        insights["attracted_to"] = "נמשך לגברים בלבד"
    elif any(phrase in text for phrase in ["רק לנשים", "נמשך לנשים"]):
        insights["attracted_to"] = "נמשך לנשים בלבד"
    elif any(phrase in text for phrase in ["גם לגברים וגם לנשים", "בי"]):
        insights["attracted_to"] = "נמשך לגברים ולנשים"
    
    # קונפליקטים עיקריים
    conflicts = []
    if any(phrase in text for phrase in ["רוצה קשר", "חיפוש", "בדידות"]):
        conflicts.append("רצון לקשר אמיתי")
    if any(phrase in text for phrase in ["עייפות", "מתיש", "תסכול"]):
        conflicts.append("עייפות מחיפושים")
    if any(phrase in text for phrase in ["פחד", "חשש", "מפחיד"]):
        conflicts.append("פחדים ביחס לזהות")
    
    if conflicts:
        insights["primary_conflict"] = "; ".join(conflicts)
    
    # מטרות
    goals = []
    if any(phrase in text for phrase in ["רוצה לדעת", "להבין", "לגלות"]):
        goals.append("הבנה עצמית")
    if any(phrase in text for phrase in ["למצוא", "קשר", "אהבה"]):
        goals.append("מציאת קשר")
    if any(phrase in text for phrase in ["לצאת", "להגיד", "בקול"]):
        goals.append("יציאה מהארון")
    
    if goals:
        insights["goal_in_course"] = "; ".join(goals)
    
    return insights

def analyze_user_5676571979():
    """ניתוח ספציפי למשתמש 5676571979"""
    print("🔍 מנתח משתמש 5676571979")
    
    # קריאת קובץ הצ'אט
    try:
        with open("chat_history_5676571979.txt", "r", encoding="utf-8") as f:
            chat_content = f.read()
        print(f"✅ נקרא קובץ צ'אט ({len(chat_content)} תווים)")
    except FileNotFoundError:
        print("❌ לא נמצא קובץ הצ'אט")
        return
    
    # ניתוח הטקסט
    insights = analyze_chat_text(chat_content)
    
    # הוספת מידע מפורש מהצ'אט
    explicit_info = {
        "age": 60,
        "self_religiosity_level": "חילוני", 
        "relationship_type": "גרוש הרבה שנים",
        "parental_status": "יש ילדים מהגרושה",
        "closet_status": "בארון - רק בודדים יודעים",
        "attracted_to": "בשנים האחרונות נמשך רק לגברים",
        "primary_conflict": "רצון לקשר קבוע ויציב; עייפות ממפגשים מזדמנים; זו הפעם הראשונה שנוגע בנושא",
        "goal_in_course": "לדעת מה לחוות ולהשיג; למצוא קשר קבוע",
        "coping_strategies": "סאונה לפעמים; ריחוק עצמי כדי לא להישאב",
        "fears_concerns": "פחד מההכיוון שהוא הולך אליו; תחושת ריקנות אחרי מפגשים",
        "future_vision": "להרגיש מאושר, מאוהב ונאהב; קשר עם חברות אמיתית ואהבה פיזית חופשית"
    }
    
    # מיזוג התובנות
    final_insights = {**insights, **explicit_info}
    
    # יצירת המלצות
    recommendations = []
    
    for field, value in final_insights.items():
        if field in USER_FIELDS:
            recommendations.append({
                "user_id": "5676571979",
                "field": field,
                "action": "add_field",
                "current_value": "לא קיים במערכת",
                "suggested_value": value,
                "confidence": "גבוה",
                "source": "ניתוח צ'אט ישיר"
            })
    
    # הוספת המלצות מיוחדות
    recommendations.append({
        "user_id": "5676571979", 
        "field": "summary",
        "action": "create_summary",
        "suggested_value": "גבר בן 60, חילוני, גרוש עם ילדים. בארון - רק בודדים יודעים. בשנים האחרונות התחדד לו שהוא נמשך רק לגברים. זו הפעם הראשונה שהוא מתמודד עם הנושא. עייף ממפגשים מזדמנים ורוצה קשר קבוע ויציב. מחפש חברות אמיתית ואהבה פיזית חופשית.",
        "confidence": "גבוה",
        "source": "ניתוח מקיף של הצ'אט"
    })
    
    return {
        "user_id": "5676571979",
        "analysis_complete": True,
        "insights_found": len(final_insights),
        "recommendations": recommendations,
        "key_themes": [
            "מעבר מיני בגיל מבוגר",
            "רצון לקשר יציב מעבר למזדמן", 
            "התמודדות ראשונית עם זהות מינית",
            "בדידות וצורך בקהילה"
        ]
    }

def main():
    """פונקציה ראשית"""
    print("🚀 מתחיל ניתוח נתוני משתמשים")
    print("=" * 50)
    
    # ניתוח משתמש 5676571979
    result = analyze_user_5676571979()
    
    print("\n📊 תוצאות הניתוח:")
    print(f"משתמש: {result['user_id']}")
    print(f"תובנות שנמצאו: {result['insights_found']}")
    print(f"המלצות: {len(result['recommendations'])}")
    
    print("\n🎯 נושאים מרכזיים:")
    for theme in result['key_themes']:
        print(f"   • {theme}")
    
    print("\n📝 המלצות עיקריות:")
    for i, rec in enumerate(result['recommendations'][:10], 1):
        print(f"   {i}. {rec['field']}: {rec['action']}")
        if 'suggested_value' in rec:
            print(f"      💡 {rec['suggested_value'][:100]}...")
    
    print("\n✅ הניתוח הושלם!")
    return result

if __name__ == "__main__":
    result = main() 