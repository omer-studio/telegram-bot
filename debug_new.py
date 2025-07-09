#!/usr/bin/env python3

from message_handler import format_text_for_telegram

# בדיקה מפורטת
text = "הבנת נכון! 😊"

print(f"🔍 קלט: {text!r}")
print(f"📏 אורך: {len(text)}")

for i, char in enumerate(text):
    print(f"  {i}: {char!r} ({'פיסוק' if char in '.?!' else 'רגיל'})")

print()
result = format_text_for_telegram(text)
print(f"🔍 פלט: {result!r}")
print(f"📏 אורך: {len(result)}")

if result == text:
    print("❌ אין שינוי - יש באג!")
else:
    print("✅ יש שינוי!") 