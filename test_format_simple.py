from message_handler import format_text_for_telegram

# טקסט הדוגמה הבעייתי
original = 'היי, מה קורה?  אני רואה שכתבת רק "מה" וזה גורם לי לתהות מה עובר לך בראש עכשיו. 🤔\n\nאולי אתה מופתע?  מבולבל?  סקרן?\n\nאני כאן איתך,  מוזמן לשתף אותי במה שאתה מרגיש, גם אם זה רק מילה אחת. 💖'

print("=== טקסט מקורי ===")
print(repr(original))
print("\n=== טקסט מקורי (הדפסה רגילה) ===")
print(original)

result = format_text_for_telegram(original)

print("\n=== תוצאה ===")
print(repr(result))
print("\n=== תוצאה (הדפסה רגילה) ===")
print(result)

print("\n=== בדיקות ===")
print(f"יש מעברי פסקאות? {'\\n\\n' in result}")
print(f"אורך מקורי: {len(original)}")
print(f"אורך תוצאה: {len(result)}") 