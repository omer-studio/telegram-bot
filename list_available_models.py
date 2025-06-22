#זה קובץ שדרכו אפשר לדעת איך קוראים לשמות המודלים כדי לרשום אותם במדויק
from litellm import get_llm_provider
import os

# משתמשים במפתח שלך מהסביבה (מה־Render או משתנה אחר)
from config import OPENAI_API_KEY

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

try:
    # LiteLLM לא מספק API ישיר לרשימת מודלים, אבל נוכל לנסות מודלים נפוצים
    print("📋 המודלים הזמינים לך (LiteLLM):\n")
    
    # רשימת מודלים נפוצים של OpenAI
    common_models = [
        "gpt-4o",
        "gpt-4o-mini", 
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "gpt-4.1-nano",
        "gpt-4.1-mini"
    ]
    
    for model in common_models:
        try:
            # בדיקה אם המודל זמין
            provider = get_llm_provider(model)
            print(f"✅ {model} (Provider: {provider})")
        except Exception:
            print(f"❌ {model} - לא זמין")
            
except Exception as e:
    print("❌ שגיאה בעת ניסיון למשוך את רשימת המודלים:")
    print(e)
