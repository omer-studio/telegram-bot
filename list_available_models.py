#זה קובץ שדרכו אפשר לדעת איך קוראים לשמות המודלים כדי לרשום אותם במדויק
#+ מחירים + בדיקה של מודלים זמינים באמת דרך API ישיר
from litellm import get_llm_provider, model_cost
import os
from typing import List, Dict, Tuple

# משתמשים במפתח שלך מהסביבה (מה־Render או משתנה אחר)
from config import OPENAI_API_KEY, config

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

def format_price(input_cost: float, output_cost: float) -> str:
    """מעצב מחיר בצורה קומפקטית"""
    if input_cost == 0 and output_cost == 0:
        return "FREE"
    return f"${input_cost:.2f}/${output_cost:.2f}"

def truncate_text(text: str, max_length: int = 30) -> str:
    """מקצר טקסט לאורך מקסימלי"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def print_table_header(title: str, columns: List[str], widths: List[int]):
    """מדפיס כותרת טבלה"""
    total_width = sum(widths) + len(widths) - 1  # +separators
    print(f"\n{title}")
    print("=" * total_width)
    
    # כותרות עמודות
    header = ""
    for i, (col, width) in enumerate(zip(columns, widths)):
        header += f"{col:<{width}}"
        if i < len(columns) - 1:
            header += "|"
    print(header)
    
    # קו מפריד
    separator = ""
    for i, width in enumerate(widths):
        separator += "-" * width
        if i < len(widths) - 1:
            separator += "+"
    print(separator)

def print_table_row(values: List[str], widths: List[int]):
    """מדפיס שורה בטבלה"""
    row = ""
    for i, (value, width) in enumerate(zip(values, widths)):
        # וידוא שהערך לא חורג מהרוחב
        display_value = truncate_text(str(value), width)
        row += f"{display_value:<{width}}"
        if i < len(values) - 1:
            row += "|"
    print(row)

def check_gemini_models():
    """בדיקת מודלי Gemini דרך API ישיר"""
    print("🚀 בודק מודלי Gemini זמינים דרך API ישיר...")
    
    # ניסיון למצוא מפתח Gemini בכל הדרכים האפשריות
    gemini_key = None
    
    # בדיקה 1: משתני סביבה
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    # בדיקה 2: מהקונפיגורציה ישירות
    if not gemini_key:
        gemini_key = config.get("GEMINI_API_KEY") or config.get("GOOGLE_API_KEY")
    
    # בדיקה 3: אולי יש מפתח בשם אחר בקונפיגורציה
    if not gemini_key:
        for key in config.keys():
            if 'GEMINI' in key.upper() or 'GOOGLE' in key.upper():
                if key not in ['GOOGLE_SHEET_ID', 'SERVICE_ACCOUNT_DICT']:
                    gemini_key = config[key]
                    print(f"💡 מצאתי מפתח אפשרי: {key}")
                    break
    
    # בדיקה 4: אולי המפתח הוא חלק מ-SERVICE_ACCOUNT_DICT
    if not gemini_key and 'SERVICE_ACCOUNT_DICT' in config:
        # ניסיון להשתמש ב-private_key מה-service account
        service_account = config['SERVICE_ACCOUNT_DICT']
        if 'private_key' in service_account:
            print("💡 מנסה להשתמש ב-private_key מה-SERVICE_ACCOUNT_DICT")
            # נניח שזה service account credentials
            gemini_key = service_account  # נעביר את כל האובייקט
    
    if not gemini_key:
        print("❌ לא נמצא מפתח Gemini API")
        print("💡 הוסף GEMINI_API_KEY למשתני הסביבה או לקובץ הקונפיגורציה")
        print("📝 קבל מפתח מ: https://aistudio.google.com/")
        return []
    
    try:
        import google.generativeai as genai
        
        # אם זה service account dict
        if isinstance(gemini_key, dict):
            try:
                from google.oauth2 import service_account
                credentials = service_account.Credentials.from_service_account_info(gemini_key)
                genai.configure(credentials=credentials)
                print("✅ התחברתי בהצלחה ל-Gemini API עם Service Account")
            except Exception as e:
                print(f"❌ שגיאה בהתחברות עם Service Account: {e}")
                return []
        else:
            # אם זה API key רגיל
            genai.configure(api_key=gemini_key)
            print("✅ התחברתי בהצלחה ל-Gemini API עם API Key")
        
        available_models = []
        
        for model in genai.list_models():
            if hasattr(model, 'supported_generation_methods') and \
               'generateContent' in model.supported_generation_methods:
                model_name = model.name.replace('models/', '')
                available_models.append({
                    'name': model_name,
                    'display_name': model.display_name if hasattr(model, 'display_name') else model_name,
                    'description': model.description if hasattr(model, 'description') else 'לא זמין'
                })
                
        print(f"📋 נמצאו {len(available_models)} מודלי Gemini זמינים")
        return available_models
        
    except ImportError:
        print("❌ google-generativeai לא מותקן")
        print("💡 התקן עם: pip install google-generativeai")
        return []
    except Exception as e:
        print(f"❌ שגיאה בחיבור ל-Gemini API: {e}")
        print(f"🔍 סוג השגיאה: {type(e).__name__}")
        return []

def check_openai_models():
    """בדיקת מודלי OpenAI דרך API ישיר"""
    print("\n🤖 בודק מודלי OpenAI זמינים דרך API ישיר...")
    
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        models = client.models.list()
        available_models = []
        
        # סינון מודלים רלוונטיים לשיחה
        relevant_models = []
        for model in models.data:
            model_id = model.id
            # רק מודלים שמתחילים ב-gpt ומתאימים לצ'אט
            if (model_id.startswith('gpt-') and 
                ('turbo' in model_id or '4o' in model_id or model_id.startswith('gpt-4') or model_id.startswith('gpt-3.5'))):
                relevant_models.append({
                    'name': model_id,
                    'display_name': model_id,
                    'description': f"OpenAI {model_id}"
                })
        
        print(f"📋 נמצאו {len(relevant_models)} מודלי OpenAI רלוונטיים")
        return relevant_models
        
    except Exception as e:
        print(f"❌ שגיאה בחיבור ל-OpenAI API: {e}")
        return []

def check_litellm_compatibility(model_name, is_gemini=False):
    """בדיקת תאימות ומחיר ב-LiteLLM"""
    try:
        # המרה לפורמט LiteLLM
        if is_gemini:
            litellm_name = f"gemini/{model_name}"
        else:
            litellm_name = model_name
            
        # בדיקת provider
        provider = get_llm_provider(litellm_name)
        
        # בדיקת מחיר
        cost_info = model_cost.get(litellm_name, None)
        if cost_info:
            input_cost = cost_info.get("input_cost_per_token", 0) * 1000000
            output_cost = cost_info.get("output_cost_per_token", 0) * 1000000
            max_tokens = cost_info.get("max_tokens", "לא ידוע")
            cost_str = f"${input_cost:.2f} קלט / ${output_cost:.2f} פלט (למיליון טוקנים)"
            return True, provider, cost_str, max_tokens
        else:
            return True, provider, "מחיר לא זמין ב-LiteLLM", "לא ידוע"
            
    except Exception as e:
        return False, str(e), "לא זמין", "לא זמין"

def print_model_info(model, is_gemini=False):
    """מדפיס מידע מפורט על מודל"""
    compatible, provider, cost, max_tokens = check_litellm_compatibility(model['name'], is_gemini)
    
    print(f"\n✅ {model['display_name']}")
    print(f"   🆔 שם: {model['name']}")
    if 'description' in model and model['description'] != 'לא זמין':
        print(f"   📄 תיאור: {model['description'][:80]}...")
    
    if compatible:
        litellm_name = f"gemini/{model['name']}" if is_gemini else model['name']
        print(f"   ✅ תואם ל-LiteLLM: {litellm_name}")
        print(f"   📡 Provider: {provider}")
        print(f"   💰 מחיר: {cost}")
        print(f"   🔢 מקס טוקנים: {max_tokens}")
    else:
        print(f"   ❌ לא תואם ל-LiteLLM: {provider}")

def print_gemini_table(models: List[Dict]):
    """מדפיס טבלת מודלי Gemini"""
    if not models:
        return
    
    # הגדרת עמודות ורוחבים
    columns = ["Model Name", "Price ($/M)", "Tokens", "Free"]
    widths = [40, 12, 8, 6]
    
    print_table_header("🚀 Gemini Models", columns, widths)
    
    # מיון המודלים לפי חשיבות
    def model_priority(model):
        name = model['name'].lower()
        if '2.5-pro' in name: return 1
        if '2.5-flash' in name: return 2
        if '2.0-flash' in name: return 3
        if '1.5-flash-8b' in name: return 4
        if '1.5-flash' in name: return 5
        return 6
    
    sorted_models = sorted(models, key=model_priority)
    
    for model in sorted_models:
        compatible, provider, cost_str, max_tokens = check_litellm_compatibility(model['name'], is_gemini=True)
        
        # עיצוב מחיר
        if "FREE" in cost_str or "$0.00" in cost_str:
            price_display = "FREE"
            is_free = "✅"
        elif "לא זמין" in cost_str:
            price_display = "N/A"
            is_free = "?"
        else:
            price_display = cost_str.replace(" קלט / ", "/").replace(" (למיליון טוקנים)", "")
            is_free = "❌"
        
        # קיצור שם המודל אם הוא ארוך מדי
        model_name = model['name']
        if len(model_name) > 38:
            model_name = model_name[:35] + "..."
        
        tokens_display = str(max_tokens) if max_tokens != "לא ידוע" else "N/A"
        if len(tokens_display) > 6:
            tokens_display = tokens_display[:6]
        
        values = [
            model_name,
            price_display,
            tokens_display,
            is_free
        ]
        
        print_table_row(values, widths)

def print_openai_table(models: List[Dict]):
    """מדפיס טבלת מודלי OpenAI"""
    if not models:
        return
    
    # הגדרת עמודות ורוחבים
    columns = ["Model Name", "Price ($/M)", "Tokens"]
    widths = [45, 12, 8]
    
    print_table_header("🤖 OpenAI Models", columns, widths)
    
    # מיון המודלים לפי חשיבות
    def openai_priority(model):
        name = model['name'].lower()
        if '4.1' in name: return 1
        if '4o' in name and 'mini' not in name: return 2
        if '4o-mini' in name: return 3
        if 'gpt-4' in name: return 4
        if '3.5-turbo' in name: return 5
        return 6
    
    sorted_models = sorted(models, key=openai_priority)
    
    for model in sorted_models:
        compatible, provider, cost_str, max_tokens = check_litellm_compatibility(model['name'], is_gemini=False)
        
        # עיצוב מחיר
        if "לא זמין" in cost_str:
            price_display = "N/A"
        else:
            price_display = cost_str.replace(" קלט / ", "/").replace(" (למיליון טוקנים)", "")
        
        # קיצור שם המודל אם הוא ארוך מדי
        model_name = model['name']
        if len(model_name) > 43:
            model_name = model_name[:40] + "..."
        
        tokens_display = str(max_tokens) if max_tokens != "לא ידוע" else "N/A"
        if len(tokens_display) > 6:
            tokens_display = tokens_display[:6]
        
        values = [
            model_name,
            price_display,
            tokens_display
        ]
        
        print_table_row(values, widths)

def print_comparison_table(gemini_models: List[Dict], openai_models: List[Dict]):
    """מדפיס טבלת השוואה של המודלים הטובים ביותר"""
    print_table_header("💎 Top Recommended Models", 
                      ["Provider", "Model", "Price", "Notes"], 
                      [8, 30, 12, 35])
    
    # מודלי Gemini מומלצים
    recommendations = [
        ("Gemini", "gemini-1.5-flash-8b", "FREE", "החינמי הטוב ביותר"),
        ("Gemini", "gemini-2.5-flash", "$0.30/2.50", "איזון מושלם"),
        ("Gemini", "gemini-2.5-pro", "$1.25/10.0", "המתקדם - חצי מ-GPT-4o"),
        ("OpenAI", "gpt-4.1-nano", "$0.10/0.40", "החדש - זול מאוד"),
        ("OpenAI", "gpt-4o-mini", "$0.15/0.60", "פופולרי ומהיר"),
        ("OpenAI", "gpt-4o", "$2.50/10.0", "הסטנדרט הרגיל"),
    ]
    
    for provider, model, price, notes in recommendations:
        print_table_row([provider, model, price, notes], [8, 30, 12, 35])

def export_simple_report(gemini_models: List[Dict], openai_models: List[Dict]):
    """יצוא דוח פשוט ללא אמוג'ים"""
    print("\n" + "="*80)
    print("MODEL AVAILABILITY & PRICING ANALYSIS")
    print("="*80)
    
    # Gemini Models
    if gemini_models:
        print("\nGEMINI MODELS:")
        print("-" * 70)
        print("Name".ljust(35) + "Price".ljust(15) + "Tokens".ljust(10) + "Free")
        print("-" * 70)
        
        sorted_models = sorted(gemini_models, key=lambda m: (
            1 if '2.5-pro' in m['name'].lower() else
            2 if '2.5-flash' in m['name'].lower() else
            3 if '1.5-flash-8b' in m['name'].lower() else
            4 if '1.5-flash' in m['name'].lower() else 5
        ))
        
        for model in sorted_models[:10]:
            compatible, provider, cost_str, max_tokens = check_litellm_compatibility(model['name'], is_gemini=True)
            
            if "FREE" in cost_str or "$0.00" in cost_str:
                price_display = "FREE"
                is_free = "YES"
            elif "לא זמין" in cost_str:
                price_display = "N/A"
                is_free = "?"
            else:
                price_display = cost_str.replace(" קלט / ", "/").replace(" (למיליון טוקנים)", "")
                is_free = "NO"
            
            model_name = model['name'][:32] + "..." if len(model['name']) > 32 else model['name']
            tokens_display = str(max_tokens) if max_tokens != "לא ידוע" else "N/A"
            
            print(f"{model_name:<35}{price_display:<15}{tokens_display:<10}{is_free}")
    
    # OpenAI Models
    if openai_models:
        print("\nOPENAI MODELS:")
        print("-" * 60)
        print("Name".ljust(40) + "Price".ljust(15) + "Tokens")
        print("-" * 60)
        
        sorted_models = sorted(openai_models, key=lambda m: (
            1 if '4.1' in m['name'].lower() else
            2 if '4o' in m['name'].lower() and 'mini' not in m['name'].lower() else
            3 if '4o-mini' in m['name'].lower() else
            4 if 'gpt-4' in m['name'].lower() else 5
        ))
        
        for model in sorted_models[:8]:
            compatible, provider, cost_str, max_tokens = check_litellm_compatibility(model['name'], is_gemini=False)
            
            if "לא זמין" in cost_str:
                price_display = "N/A"
            else:
                price_display = cost_str.replace(" קלט / ", "/").replace(" (למיליון טוקנים)", "")
            
            model_name = model['name'][:37] + "..." if len(model['name']) > 37 else model['name']
            tokens_display = str(max_tokens) if max_tokens != "לא ידוע" else "N/A"
            
            print(f"{model_name:<40}{price_display:<15}{tokens_display}")
    
    # Top Recommendations
    print("\nTOP RECOMMENDATIONS:")
    print("-" * 70)
    print("Provider".ljust(10) + "Model".ljust(30) + "Price".ljust(15) + "Notes")
    print("-" * 70)
    
    recommendations = [
        ("Gemini", "gemini-1.5-flash-8b", "FREE", "Best free option"),
        ("Gemini", "gemini-2.5-flash", "$0.30/2.50", "Perfect balance"),
        ("Gemini", "gemini-2.5-pro", "$1.25/10.0", "Advanced - half price of GPT-4o"),
        ("OpenAI", "gpt-4.1-nano", "$0.10/0.40", "New - very cheap"),
        ("OpenAI", "gpt-4o-mini", "$0.15/0.60", "Popular and fast"),
        ("OpenAI", "gpt-4o", "$2.50/10.0", "Standard expensive"),
    ]
    
    for provider, model, price, notes in recommendations:
        model_short = model[:27] + "..." if len(model) > 27 else model
        print(f"{provider:<10}{model_short:<30}{price:<15}{notes}")
    
    print(f"\nSUMMARY:")
    print(f"Gemini Models: {len(gemini_models)}")
    print(f"OpenAI Models: {len(openai_models)}")
    print("Recommendation: Try Gemini 1.5 Flash-8B (FREE) or 2.5 Flash")
    print("All prices in $ per million tokens")

def main():
    """פונקציה ראשית"""
    print("=" * 100)
    print("📊 Model Availability & Pricing Analysis")
    print("=" * 100)
    
    # הדפסת מידע על המפתחות שנמצאו
    print("🔍 Available API Keys:")
    api_keys_found = []
    for key in config.keys():
        if any(word in key.upper() for word in ['API', 'KEY', 'TOKEN', 'GOOGLE', 'GEMINI']):
            if key == 'SERVICE_ACCOUNT_DICT':
                api_keys_found.append(f"   ✅ {key}: Service Account")
            else:
                api_keys_found.append(f"   ✅ {key}: {str(config[key])[:15]}...")
    
    for key_info in api_keys_found:
        print(key_info)
    
    # בדיקת מודלי Gemini
    print(f"\n{'='*50}")
    print("🚀 Checking Gemini API...")
    gemini_models = check_gemini_models()
    
    # בדיקת מודלי OpenAI
    print(f"\n{'='*50}")
    print("🤖 Checking OpenAI API...")
    openai_models = check_openai_models()
    
    # הצגת טבלאות
    if gemini_models:
        print_gemini_table(gemini_models[:15])  # 15 הראשונים
        if len(gemini_models) > 15:
            print(f"\n... + {len(gemini_models) - 15} more Gemini models available")
    
    if openai_models:
        print_openai_table(openai_models[:12])  # 12 הראשונים
        if len(openai_models) > 12:
            print(f"\n... + {len(openai_models) - 12} more OpenAI models available")
    
    # טבלת השוואה
    if gemini_models or openai_models:
        print_comparison_table(gemini_models, openai_models)
    
    # גרסה פשוטה לייצוא
    export_simple_report(gemini_models, openai_models)
    
    # סיכום
    print(f"\n{'='*100}")
    print("📈 Summary:")
    print(f"   📊 Gemini Models Found: {len(gemini_models)}")
    print(f"   📊 OpenAI Models Found: {len(openai_models)}")
    print(f"   💡 Recommendation: Try Gemini 1.5 Flash-8B (FREE) or 2.5 Flash for best value")
    print(f"   🔗 Prices in $ per million tokens")

if __name__ == "__main__":
    main()
