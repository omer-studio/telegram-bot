#!/usr/bin/env python3

import re

# בדיקת רג'קס
text = 'הבנת נכון! 😊'
emoji_regex = r'[\U0001F600-\U0001F64F\U0001F300-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]'

print(f"טקסט: {text!r}")

# בדיקה אם האימוג'י נתפס
matches = re.findall(emoji_regex, text)
print(f"אימוג'ים שנמצאו: {matches}")

# בדיקת הרג'קס המלא
full_regex = r'([?!])(\s*)(' + emoji_regex + ')'
matches2 = re.findall(full_regex, text)
print(f"רג'קס מלא: {matches2}")

# בדיקה אם substitution עובד
result = re.sub(full_regex, r'\1 \3\n', text)
print(f"תוצאה: {result!r}")

# בדיקה ישירה של האימוג'י
emoji_char = '😊'
print(f"האימוג'י: {emoji_char!r}")
print(f"Unicode של האימוג'י: {ord(emoji_char):#x}")
print(f"האם האימוג'י תואם לרג'קס: {bool(re.match(emoji_regex, emoji_char))}") 