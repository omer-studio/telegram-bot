#!/usr/bin/env python3

import re

text = "הבנת נכון! 😊"

print(f"🔍 טקסט מקורי: {text!r}")
print(f"📏 אורך: {len(text)} תווים")

# דיבאג תו אחר תו
for i, char in enumerate(text):
    print(f"  {i:2d}: {char!r} -> {'פיסוק' if char in '.?!' else 'רגיל'}")

print("\n🧪 בדיקת רג'קסים:")

# רג'קס 1: שאלה/קריאה + רווח + אימוג'י
regex1 = r'([?!]) ([\U0001F600-\U0001F64F\U0001F300-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251])'
matches1 = re.findall(regex1, text)
print(f"רג'קס 1 (שאלה/קריאה + רווח + אימוג'י): {matches1}")

# בדיקה עם רווח ספציפי
if ' ' in text:
    space_idx = text.index(' ')
    print(f"רווח נמצא באינדקס {space_idx}")
    after_space = text[space_idx+1:space_idx+3]
    print(f"אחרי הרווח: {after_space!r}")

# ניסיון החלפה
result1 = re.sub(regex1, r'\1 \2\n', text)
print(f"תוצאה רג'קס 1: {result1!r}")

# רג'קס רגיל
regex2 = r'([?!])(\s*)'
result2 = re.sub(regex2, r'\1\n', result1)
print(f"תוצאה רג'קס 2: {result2!r}")

print(f"\n✅ תוצאה סופית: {result2!r}")
if result2 != text:
    print("✅ יש שינוי!")
    print(f"📺 תצוגה:\n{result2}")
else:
    print("❌ אין שינוי!") 