"""
smart_model_filter.py
--------------------
פילטר חכם לבחירת מודל AI - מחליט מתי להשתמש במודל מתקדם ויקר ומתי במהיר וחסכוני
"""

import logging
import re

# ===============================
# 🎯 הגדרות פילטר מודל חכם
# ===============================

# סף מילים למודל מתקדם
LONG_MESSAGE_THRESHOLD = 50  # מעל 50 מילים = מודל מתקדם

# סף היסטוריה למצב מורכב
COMPLEX_HISTORY_THRESHOLD = 10  # מעל 10 הודעות = מצב מורכב

# מילות מפתח שמצדיקות מודל מתקדם
PREMIUM_MODEL_KEYWORDS = [
    # זוגיות ומערכות יחסים
    "נישואין", "חתונה", "זוגיות", "מערכת יחסים", "בן זוג", "בת זוג", "חברה", "חבר",
    "אהבה", "רגשות", "קשר", "זיקה", "משיכה", "אינטימיות", "מיניות", "פרידה", "גירושין",
    
    # פסיכולוגיה ובריאות נפש
    "פסיכולוגיה", "טיפול", "ייעוץ", "פסיכולוג", "מטפל", "מדכא", "דיכאון", "חרדה", 
    "פחד", "דאגה", "בלבול", "לחץ", "סטרס", "טראומה", "פציעה נפשית",
    
    # דתיות ואמונה
    "דתיות", "חילוני", "דתי", "מסורתי", "אמונה", "מצוות", "הלכה", "רב", "רבנות",
    "כשרות", "שבת", "חג", "תפילה", "בית כנסת", "תורה", "תלמוד", "יהדות",
    
    # משפחה וחיי חברה
    "משפחה", "הורים", "ילדים", "הריון", "לידה", "חינוך", "גיל", "זקנה", "סבא", "סבתא",
    "אבא", "אמא", "בן", "בת", "אח", "אחות", "דוד", "דודה", "בן דוד", "בת דוד",
    
    # עבודה וקריירה
    "עבודה", "קריירה", "השכלה", "לימודים", "אוניברסיטה", "מקצוע", "כלכלה", "שכר",
    "מנהל", "עובד", "מעסיק", "ראיון עבודה", "קורות חיים", "השכלה גבוהה",
    
    # בריאות רפואית
    "בריאות", "רופא", "חולה", "מחלה", "תרופה", "ניתוח", "בית חולים", "קופת חולים",
    "כאב", "כואב", "רפואה", "אבחון", "טיפול רפואי", "מחלה כרונית",
    
    # החלטות ודילמות
    "בעיה", "קושי", "החלטה", "דילמה", "ברירה", "אפשרות", "עתיד", "תכנון", "יעד", "חלום",
    "לבחור", "להחליט", "נבוך", "מבולבל", "לא יודע", "עזרה", "חשוב", "קריטי"
]

# דפוסי ביטויים מורכבים (regex)
COMPLEX_PATTERNS = [
    r"מה\s+עושים\s+כש",  # "מה עושים כש..."
    r"איך\s+להתמודד\s+עם",  # "איך להתמודד עם..."
    r"צריך\s+עצה\s+ב",  # "צריך עצה ב..."
    r"לא\s+יודע\s+איך",  # "לא יודע איך..."
    r"מה\s+דעתך\s+על",  # "מה דעתך על..."
    r"איך\s+אתה\s+חושב",  # "איך אתה חושב..."
]

def should_use_premium_model(user_message, chat_history_length=0):
    """
    מחליט האם להשתמש במודל המתקדם (Gemini 2.5 Pro) או במהיר יותר (Gemini Flash)
    
    קריטריונים למודל מתקדם:
    1. הודעה ארוכה (מעל X מילים)
    2. מילות מפתח רלוונטיות
    3. דפוסי ביטויים מורכבים
    4. היסטוריה ארוכה (מעל X הודעות) - מצב מורכב
    
    Returns:
        tuple: (should_use_premium: bool, reason: str)
    """
    
    # בדיקת אורך הודעה
    word_count = len(user_message.split())
    if word_count > LONG_MESSAGE_THRESHOLD:
        logging.info(f"🎯 [PREMIUM_FILTER] הודעה ארוכה: {word_count} מילים -> Gemini 2.5 Pro")
        return True, f"הודעה ארוכה ({word_count} מילים)"
    
    # בדיקת מילות מפתח
    user_message_lower = user_message.lower()
    found_keywords = [keyword for keyword in PREMIUM_MODEL_KEYWORDS if keyword in user_message_lower]
    if found_keywords:
        logging.info(f"🎯 [PREMIUM_FILTER] מילות מפתח נמצאו: {found_keywords[:3]} -> Gemini 2.5 Pro")
        return True, f"מילות מפתח: {', '.join(found_keywords[:3])}"
    
    # בדיקת דפוסי ביטויים מורכבים
    for pattern in COMPLEX_PATTERNS:
        if re.search(pattern, user_message_lower):
            logging.info(f"🎯 [PREMIUM_FILTER] דפוס מורכב נמצא: {pattern} -> Gemini 2.5 Pro")
            return True, f"דפוס מורכב זוהה"
    
    # בדיקת היסטוריה מורכבת
    if chat_history_length > COMPLEX_HISTORY_THRESHOLD:
        logging.info(f"🎯 [PREMIUM_FILTER] היסטוריה מורכבת: {chat_history_length} הודעות -> Gemini 2.5 Pro")
        return True, f"היסטוריה מורכבת ({chat_history_length} הודעות)"
    
    # אחרת, מודל מהיר
    logging.info(f"🚀 [PREMIUM_FILTER] מקרה רגיל -> Gemini Flash (מהיר)")
    return False, "מקרה רגיל - מודל מהיר"

def get_filter_stats():
    """
    מחזיר סטטיסטיקות על הגדרות הפילטר הנוכחיות
    """
    return {
        "long_message_threshold": LONG_MESSAGE_THRESHOLD,
        "complex_history_threshold": COMPLEX_HISTORY_THRESHOLD,
        "keywords_count": len(PREMIUM_MODEL_KEYWORDS),
        "patterns_count": len(COMPLEX_PATTERNS),
        "keywords_preview": PREMIUM_MODEL_KEYWORDS[:10],
        "patterns_preview": COMPLEX_PATTERNS[:3]
    }

def update_filter_settings(long_threshold=None, history_threshold=None, new_keywords=None):
    """
    מעדכן הגדרות פילטר בזמן ריצה (אם נדרש)
    """
    global LONG_MESSAGE_THRESHOLD, COMPLEX_HISTORY_THRESHOLD, PREMIUM_MODEL_KEYWORDS
    
    if long_threshold is not None:
        LONG_MESSAGE_THRESHOLD = long_threshold
        logging.info(f"🔧 [FILTER_UPDATE] סף הודעה ארוכה עודכן ל-{long_threshold}")
    
    if history_threshold is not None:
        COMPLEX_HISTORY_THRESHOLD = history_threshold
        logging.info(f"🔧 [FILTER_UPDATE] סף היסטוריה מורכבת עודכן ל-{history_threshold}")
    
    if new_keywords is not None:
        PREMIUM_MODEL_KEYWORDS.extend(new_keywords)
        logging.info(f"🔧 [FILTER_UPDATE] נוספו {len(new_keywords)} מילות מפתח חדשות")

# ===============================
# 🧪 פונקציות בדיקה ודיבוג
# ===============================

def test_filter_with_message(message, history_length=0):
    """
    בדיקה מהירה של הפילטר עם הודעה נתונה
    """
    use_premium, reason = should_use_premium_model(message, history_length)
    return {
        "message": message[:50] + "..." if len(message) > 50 else message,
        "word_count": len(message.split()),
        "history_length": history_length,
        "use_premium": use_premium,
        "reason": reason,
        "model_recommended": "Gemini 2.5 Pro" if use_premium else "Gemini Flash"
    }

if __name__ == "__main__":
    # בדיקות מהירות
    test_messages = [
        "שלום, איך הולך?",
        "אני צריך עצה בנושא זוגיות - יש לי בעיה מורכבת עם החברה שלי",
        "מה דעתך על החלטה קריטית שאני צריך לקבל בקריירה?",
        "יש לי דילמה קשה בנושא דתיות ואני מבולבל מה לעשות כי זה משפיע על כל המשפחה שלי ואני לא יודע איך להתמודד עם הלחץ",
        "תודה!"
    ]
    
    print("🧪 בדיקת פילטר מודל חכם:")
    print("=" * 70)
    
    for i, msg in enumerate(test_messages, 1):
        result = test_filter_with_message(msg, history_length=i*2)
        print(f"\n{i}. {result['message']}")
        print(f"   📊 מילים: {result['word_count']} | היסטוריה: {result['history_length']}")
        print(f"   🤖 מודל: {result['model_recommended']} | סיבה: {result['reason']}")
    
    print("\n" + "=" * 70)
    stats = get_filter_stats()
    print(f"📈 סטטיסטיקות פילטר:")
    print(f"   • סף הודעה ארוכה: {stats['long_message_threshold']} מילים")
    print(f"   • סף היסטוריה מורכבת: {stats['complex_history_threshold']} הודעות")
    print(f"   • מילות מפתח: {stats['keywords_count']}")
    print(f"   • דפוסים: {stats['patterns_count']}") 