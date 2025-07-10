from message_handler import format_text_for_telegram

# טקסט הדוגמה המדויק
original = 'היי, מה קורה?  אני רואה שכתבת רק "מה" וזה גורם לי לתהות מה עובר לך בראש עכשיו. 🤔\n\nאולי אתה מופתע?  מבולבל?  סקרן?\n\nאני כאן איתך,  מוזמן לשתף אותי במה שאתה מרגיש, גם אם זה רק מילה אחת. 💖'

print("=== טקסט מקורי ===")
print(original)

result = format_text_for_telegram(original)

print("\n=== תוצאה ===")
print(result)

print("\n=== בדיקה מה שהמשתמש רוצה ===")
expected = """היי, מה קורה?
אני רואה שכתבת רק "מה" וזה גורם לי לתהות מה עובר לך בראש עכשיו🤔

אולי אתה מופתע?
מבולבל?
סקרן?

אני כאן איתך, מוזמן לשתף אותי במה שאתה מרגיש, גם אם זה רק מילה אחת💖
"""

print(expected)

print("\n=== האם זה זהה? ===")
print("תוצאה שלנו:", repr(result))
print("מה שהמשתמש רוצה:", repr(expected)) 