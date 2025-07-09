#!/usr/bin/env python3
"""
בדיקת פורמטינג חדש - לפי הכללים הפשוטים
"""

from message_handler import format_text_for_telegram

def test_problem_case():
    """בדיקת המקרה הבעייתי המדויק"""
    print("🧪 בדיקת המקרה הבעייתי:")
    print("=" * 60)
    
    # המקרה הבעייתי
    test_text = "הבנת נכון! 😊"
    print(f"📝 טקסט מקורי: {test_text!r}")
    result = format_text_for_telegram(test_text)
    print(f"✅ תוצאה: {result!r}")
    
    # בדיקה שהתוצאה נכונה
    expected = "הבנת נכון! 😊\n"
    if result == expected:
        print("✅ SUCCESS: האימוג'י נשאר עם הפיסוק!")
    else:
        print(f"❌ FAIL: קיוויתי {expected!r}, קיבלתי {result!r}")
    
    return result == expected

def test_more_cases():
    """בדיקות נוספות"""
    print("\n🔍 בדיקות נוספות:")
    print("=" * 60)
    
    test_cases = [
        # (input, expected_output, description)
        ("איך אתה? 🤔", "איך אתה? 🤔\n", "שאלה + אימוג'י"),
        ("זה נכון.", "זה נכון\n", "נקודה רגילה (נמחקת)"),
        ("אמת! זה נכון.", "אמת!\nזה נכון\n", "קריאה + נקודה"),
        ("שלום 👋 איך אתה?", "שלום 👋 איך אתה?\n", "אימוג'י + שאלה"),
        ("מעולה! 😊 זה נכון.", "מעולה! 😊\nזה נכון\n", "קריאה+אימוג'י + נקודה"),
    ]
    
    success_count = 0
    
    for i, (input_text, expected, description) in enumerate(test_cases, 1):
        result = format_text_for_telegram(input_text)
        success = result == expected
        status = "✅" if success else "❌"
        
        print(f"{status} Test {i}: {description}")
        print(f"   Input:    {input_text!r}")
        print(f"   Expected: {expected!r}")
        print(f"   Got:      {result!r}")
        
        if success:
            success_count += 1
        print()
    
    print(f"📊 תוצאות: {success_count}/{len(test_cases)} הצליחו")
    return success_count == len(test_cases)

def test_original_example():
    """בדיקת הטקסט המקורי המלא"""
    print("\n📋 בדיקת הטקסט המקורי המלא:")
    print("=" * 60)
    
    original = """הבנת נכון! 😊  פה, איתי, אתה יכול לדבר על כל מה שעולה לך בקורס "לפגוש את ההומופוב הפנימי".  זה מקום בטוח, ללא שיפוטיות, לחקור את המחשבות והרגשות שלך.

אנחנו יכולים לדבר על פרק מסוים שנגע בך, על התלבטויות, על פחדים, על תקוות... מה שבא לך.  אני כאן כדי להקשיב, לשקף, ולתמוך בך במסע האישי שלך. 💖

מה מעסיק אותך עכשיו? 🤔"""
    
    print(f"📝 מקור:")
    print(original)
    print()
    
    result = format_text_for_telegram(original)
    print(f"✨ תוצאה:")
    print(result)
    print()
    
    print(f"📊 סטטיסטיקות:")
    print(f"   נקודות במקור: {original.count('.')}")
    print(f"   נקודות בתוצאה: {result.count('.')}")
    print(f"   מעברי שורה: {result.count(chr(10))}")
    print(f"   אימוג'ים בתוצאה: {len([c for c in result if ord(c) > 128])}")
    
    # בדיקה שהאימוג'ים נשארו עם הפיסוק
    if "! 😊\n" in result and "? 🤔\n" in result and "💖\n" in result:
        print("✅ כל האימוג'ים נשארו עם הפיסוק!")
        return True
    else:
        print("❌ יש אימוג'ים שנפרדו מהפיסוק")
        return False

if __name__ == "__main__":
    print("🔧 בדיקת פורמטינג חדש עם placeholders:")
    print("=" * 80)
    
    # בדיקות
    problem_ok = test_problem_case()
    more_ok = test_more_cases()  
    original_ok = test_original_example()
    
    print("\n" + "=" * 80)
    print("🎯 סיכום סופי:")
    print(f"   בעיה מקורית: {'✅' if problem_ok else '❌'}")
    print(f"   בדיקות נוספות: {'✅' if more_ok else '❌'}")
    print(f"   טקסט מקורי: {'✅' if original_ok else '❌'}")
    
    if problem_ok and more_ok and original_ok:
        print("\n🎉 כל הבדיקות עברו בהצלחה! הפתרון עובד!")
    else:
        print("\n❌ יש בעיות שצריך לתקן") 