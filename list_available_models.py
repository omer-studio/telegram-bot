
#זה קובץ שדרכו אפשר לדעת איך קוראים לשמות המודלים כדי לרשום אותם במדויק
import openai
import os

# משתמשים במפתח שלך מהסביבה (מה־Render או משתנה אחר)
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

try:
    models = openai.models.list()
    print("📋 המודלים הזמינים לך:\n")
    for m in models.data:
        print("✅", m.id)
except Exception as e:
    print("❌ שגיאה בעת ניסיון למשוך את רשימת המודלים:")
    print(e)
