# פתרון שגיאת חיבור OpenAI

## 🔍 איבחון הבעיה

השגיאה שהתקבלה:
```
[STARTUP] בעיה בבדיקת תקינות: {'config_loaded': True, 'sheets_connected': True, 'openai_connected': False, 'log_files_writable': True}
```

**הסיבה:** מפתח OpenAI API לא מוגדר או לא תקין.

## 🛠️ הפתרון

### שלב 1: קבלת מפתח OpenAI API

1. היכנס ל-[OpenAI Platform](https://platform.openai.com/)
2. התחבר או הירשם לחשבון
3. עבור אל [API Keys](https://platform.openai.com/account/api-keys)
4. לחץ על "Create new secret key"
5. העתק את המפתח (מתחיל ב-`sk-`)

### שלב 2: הוספת המפתח לקובץ התצורה

ערוך את הקובץ `/workspace/etc/secrets/config.json`:

```json
{
  "TELEGRAM_BOT_TOKEN": "המפתח_של_הבוט_בטלגרם",
  "OPENAI_API_KEY": "sk-YOUR_ACTUAL_OPENAI_API_KEY_HERE",
  "ADMIN_BOT_TELEGRAM_TOKEN": "המפתח_של_בוט_הניהול",
  "DATABASE_URL": "כתובת_מסד_הנתונים"
}
```

### שלב 3: וריפיקציה

הרץ את הפקודה הבאה כדי לבדוק שהמפתח עובד:

```bash
python3 -c "
import os
import sys
sys.path.append('/workspace')
from config import OPENAI_API_KEY
print('API Key configured:', OPENAI_API_KEY[:10] + '...' if len(OPENAI_API_KEY) > 10 else 'NOT_SET')
"
```

### שלב 4: בדיקת חיבור OpenAI

```bash
python3 -c "
import os
import sys
sys.path.append('/workspace')
from config import OPENAI_API_KEY
os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY
from lazy_litellm import completion
try:
    response = completion(
        model='gpt-3.5-turbo',
        messages=[{'role': 'user', 'content': 'test'}],
        max_tokens=5
    )
    print('✅ OpenAI connection successful!')
except Exception as e:
    print(f'❌ OpenAI connection failed: {e}')
"
```

## 🚀 הפעלה מחדש

לאחר עדכון הקובץ, הפעל מחדש את הבוט:

```bash
python3 main.py
```

## 🔧 פתרון בעיות נוספות

### אם השגיאה נמשכת:

1. **בדוק קרדיט ב-OpenAI**: ודא שיש יתרה בחשבון
2. **בדוק הרשאות המפתח**: ודא שהמפתח פעיל
3. **בדוק חיבור לאינטרנט**: ודא שיש חיבור יציב
4. **בדוק לוגים**: הרץ `tail -f data/bot.log` לפרטים נוספים

### משתני סביבה אלטרנטיביים:

אם אתה מעדיף להגדיר משתנה סביבה:

```bash
export OPENAI_API_KEY="sk-YOUR_ACTUAL_OPENAI_API_KEY_HERE"
python3 main.py
```

## 📋 רשימת בדיקה

- [ ] יצירת מפתח OpenAI API
- [ ] הוספת המפתח לקובץ התצורה
- [ ] בדיקת תקינות החיבור
- [ ] הפעלת הבוט מחדש
- [ ] וריפיקציה שהשגיאה נעלמה

## 💡 טיפים

1. **אבטחה**: אל תשתף את מפתח ה-API בקבצים ציבוריים
2. **גיבוי**: שמור עותק של קובץ התצורה במקום בטוח
3. **מעקב עלויות**: עקוב אחר השימוש ב-OpenAI Platform
4. **עדכונים**: בדוק מעת לעת שהמפתח עדיין פעיל

---

**הערה:** אם הבעיה נמשכת, בדוק את הלוגים לפרטים נוספים או צור קשר עם התמיכה הטכנית.