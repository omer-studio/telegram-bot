#!/usr/bin/env python3

from message_handler import format_text_for_telegram

# בדיקה פשוטה
text1 = "הבנת נכון! 😊"
text2 = "מה מעסיק אותך עכשיו? 🤔"

print("🧪 בדיקות פשוטות:")
print("=" * 50)

result1 = format_text_for_telegram(text1)
print(f"קלט: {text1!r}")
print(f"פלט: {result1!r}")
print(f"תצוגה: {result1}")
print()

result2 = format_text_for_telegram(text2)
print(f"קלט: {text2!r}")
print(f"פלט: {result2!r}")
print(f"תצוגה: {result2}")
print()

# בדיקה של נקודה + אימוג'י
text3 = "זה נהדר. 💖"
result3 = format_text_for_telegram(text3)
print(f"קלט: {text3!r}")
print(f"פלט: {result3!r}")
print(f"תצוגה: {result3}") 