#!/usr/bin/env python3
"""
בדיקת פורמטינג חדש - לפי הכללים הפשוטים
"""

from message_handler import format_text_for_telegram

# טקסט הדוגמה מהמשתמש
text = """הבנת נכון! 😊  פה, איתי, אתה יכול לדבר על כל מה שעולה לך בקורס "לפגוש את ההומופוב הפנימי".  זה מקום בטוח, ללא שיפוטיות, לחקור את המחשבות והרגשות שלך.

אנחנו יכולים לדבר על פרק מסוים שנגע בך, על התלבטויות, על פחדים, על תקוות... מה שבא לך.  אני כאן כדי להקשיב, לשקף, ולתמוך בך במסע האישי שלך. 💖

מה מעסיק אותך עכשיו? 🤔"""

print("🔧 בדיקת פורמטינג חדש:")
print("=" * 60)
print("📝 טקסט מקורי:")
print(repr(text))
print()

result = format_text_for_telegram(text)

print("✨ טקסט אחרי פורמטינג:")
print(repr(result))
print()

print("📋 תוצאה סופית (כמו שהמשתמש יראה):")
print(result)
print()

print("📊 סטטיסטיקות:")
print(f"   🔢 נקודות במקור: {text.count('.')}")
print(f"   🔢 נקודות אחרי: {result.count('.')}")
print(f"   📏 מעברי שורה: {result.count(chr(10))}")
print(f"   📏 שאלות/קריאות: {result.count('?') + result.count('!')}")

if result.count('.') == 0:
    print("✅ נקודות נמחקו כמו שביקשת!")
else:
    print("❌ עדיין יש נקודות")

if result.count(chr(10)) > 5:
    print("✅ יש מעברי שורה טובים!")
else:
    print("❌ לא מספיק מעברי שורה") 