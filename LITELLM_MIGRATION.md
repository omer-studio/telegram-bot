# מעבר ל-LiteLLM - תיעוד

## סקירה כללית

המערכת עברה מ-OpenAI ישיר ל-LiteLLM כדי לאפשר גמישות רבה יותר בבחירת מודלים וספקים.

## מה השתנה

### 1. requirements.txt
- נוספה `litellm>=1.30.0`
- נשמר `openai>=1.30.0` לתאימות

### 2. config.py
- הוחלף `from openai import OpenAI` ב-`from litellm import completion`
- נוצר wrapper שמדמה את הקליינט המקורי של OpenAI
- נשמרה תאימות מלאה עם הקוד הקיים

### 3. list_available_models.py
- הוחלף `openai.models.list()` ב-`litellm.get_llm_provider()`
- נוספה בדיקה של מודלים נפוצים

### 4. gpt_handler.py
- לא השתנה - משתמש בקליינט המעודכן מ-config.py
- כל הפונקציונליות נשמרה

## יתרונות המעבר

### 1. גמישות במודלים
```python
# לפני - רק OpenAI
model = "gpt-4o"

# אחרי - כל ספק
model = "gpt-4o"  # OpenAI
model = "claude-3-sonnet"  # Anthropic
model = "gemini-pro"  # Google
```

### 2. Fallback אוטומטי
```python
# LiteLLM יכול לנסות מודלים אחרים אם אחד לא זמין
response = completion(
    model="gpt-4o",
    messages=messages,
    fallbacks=["gpt-3.5-turbo", "claude-3-haiku"]
)
```

### 3. מעקב עלויות משופר
LiteLLM מספק מידע מפורט יותר על עלויות ושימוש.

### 4. תמיכה במודלים מקומיים
```python
# בעתיד - מודלים מקומיים
model = "llama2"  # מודל מקומי
```

## בדיקת המעבר

הרץ את קובץ הבדיקה:
```bash
python test_litellm_migration.py
```

## שימוש עתידי

### החלפת מודל
```python
# במקום gpt-4o, נסה מודל אחר
response = client.chat.completions.create(
    model="claude-3-sonnet",  # Anthropic
    messages=messages
)
```

### הוספת ספק חדש
1. הוסף את ה-API key ל-config.json
2. שנה את המודל בקוד
3. LiteLLM יטפל בשאר

### Fallback אוטומטי
```python
# אם gpt-4o לא זמין, נסה gpt-3.5-turbo
response = completion(
    model="gpt-4o",
    messages=messages,
    fallbacks=["gpt-3.5-turbo"]
)
```

## תאימות

- ✅ כל הפונקציות הקיימות עובדות
- ✅ כל הלוגים נשמרים
- ✅ חישוב עלויות נשאר זהה
- ✅ API זהה - אין צורך בשינוי קוד אחר

## פתרון בעיות

### שגיאה: "No module named 'litellm'"
```bash
pip install litellm
```

### שגיאה: "Invalid API key"
בדוק שה-OPENAI_API_KEY מוגדר נכון ב-config.json

### שגיאה: "Model not found"
בדוק את שם המודל - LiteLLM משתמש באותם שמות כמו OpenAI

## סיכום

המעבר ל-LiteLLM הושלם בהצלחה! המערכת עכשיו גמישה יותר ומאפשרת:
- שימוש במודלים מספקים שונים
- Fallback אוטומטי
- מעקב עלויות משופר
- תמיכה עתידית במודלים מקומיים

כל הפונקציונליות הקיימת נשמרה ללא שינוי. 