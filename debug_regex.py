#!/usr/bin/env python3

import re

# רג'קס לזיהוי אימוג'ים
emoji_pattern = re.compile(
    r"[\U0001F600-\U0001F64F"
    r"\U0001F300-\U0001F6FF"
    r"\U0001F700-\U0001F77F"
    r"\U0001F780-\U0001F7FF"
    r"\U0001F800-\U0001F8FF"
    r"\U0001F900-\U0001F9FF"
    r"\U0001FA00-\U0001FA6F"
    r"\U0001FA70-\U0001FAFF"
    r"\U00002702-\U000027B0"
    r"\U000024C2-\U0001F251]"
)

# טקסט בדיקה
text = "הבנת נכון! 😊"

print("🔍 דיבאג רג'קס:")
print("=" * 50)
print(f"טקסט מקורי: {text!r}")
print(f"יש אימוג'י: {bool(emoji_pattern.search(text))}")

# בדיקת הרג'קס השאלה/קריאה + אימוג'י
pattern1 = r'([?!])(\s+)(' + emoji_pattern.pattern + r')'
matches1 = re.findall(pattern1, text)
print(f"רג'קס 1 (\\s+): {pattern1}")
print(f"תוצאות: {matches1}")

# נסה עם \s*
pattern2 = r'([?!])(\s*)(' + emoji_pattern.pattern + r')'
matches2 = re.findall(pattern2, text)
print(f"רג'קס 2 (\\s*): {pattern2}")  
print(f"תוצאות: {matches2}")

# נסה ללא קבוצת רווחים
pattern3 = r'([?!])\s*(' + emoji_pattern.pattern + r')'
matches3 = re.findall(pattern3, text)
print(f"רג'קס 3 (ללא קבוצה): {pattern3}")
print(f"תוצאות: {matches3}")

# בדיקה ידנית עם replace
print("\n🔧 בדיקת החלפה:")
result1 = re.sub(r'([?!])(\s+)(' + emoji_pattern.pattern + r')', r'\1 \3\n', text)
print(f"תוצאה עם \\s+: {result1!r}")

result2 = re.sub(r'([?!])(\s*)(' + emoji_pattern.pattern + r')', r'\1 \3\n', text)
print(f"תוצאה עם \\s*: {result2!r}")

result3 = re.sub(r'([?!])\s*(' + emoji_pattern.pattern + r')', r'\1 \2\n', text)
print(f"תוצאה ללא קבוצה: {result3!r}")

# בדיקה האם יש רווח
print(f"\nרווחים בין ! ל-😊:")
for i, char in enumerate(text):
    if char == '!':
        print(f"אחרי !: {text[i+1:i+3]!r}")
        break 