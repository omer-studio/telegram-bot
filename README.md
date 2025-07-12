# Telegram GPT Bot — Daniel

בוט טלגרם חכם מבוסס GPT-4o, עם ניהול משתמשים, לוגים, Google Sheets, דוחות אוטומטיים, והרשאות מתקדמות.

**🔄 עדכון אחרון:** ארכיטקטורה מודולרית חדשה עם handlers נפרדים וקונפיגורציה מרכזית

**🚨 תיקון קריטי אבטחה (29/12/2024):** 
- ✅ **תוקנה חשיפת מידע פרטי למשתמש** - הסרת הודעות "[עדכון פרופיל]" מההיסטוריה שנשלחת ל-GPT
- ✅ **תוקנה כפילות הודעות** - הסרת race condition ב-update_chat_history 
- ✅ **הוספת 3 שכבות אבטחה** - בדיקות CRITICAL SECURITY ב-send_message ו-send_message_with_retry
- ✅ **פילטר אבטחה ב-get_chat_history_messages** - מונע הודעות פנימיות מלהגיע ל-GPT
- ✅ **הגנה מרובדת** - כל הודעה שמתחילה ב-"[" ומכילה מילים כמו "עדכון", "debug", "admin" חסומה

**🔧 תיקון אחרון:** הוספה החרגה לברכות זמן - אם המשתמש כותב "היי", "שלום", "אהלן" או ברכות דומות, הבוט ישלח ברכת זמן מתאימה (בוקר טוב/צהריים טובים וכו') גם אם עברו פחות מ-2 שעות מהשיחה האחרונה. זה מזהה תחילת שיחה חדשה. נוסף דיבאג מפורט שמראה איזה summary נשלח ומאיפה הוא מגיע (בשורה אחת לטרמינל מסודר).

**🚀 שיפור נוסף:** שימוש בביטוי רגולרי חכם לזיהוי ברכות בסיסיות - במקום רשימה ארוכה של גרסאות, הבוט מזהה את המילים הבסיסיות + עד 2 תווים נוספים (אימוג'י, סימן קריאה וכו'). זה מכסה כל גרסה אפשרית של "היי", "שלום", "אהלן" וכו'.

---

## ⚠️ הערה חשובה לפיתוח

**🚫 אסור ליצור עוד קבצי README!**

- **כל התיעוד** צריך להיות בקובץ README.md הראשי הזה בלבד
- **אין ליצור** קבצים כמו IMPLEMENTATION_SUMMARY.md, PERFORMANCE_ANALYSIS_README.md וכו'
- **כל עדכון או תוספת** צריכים להתווסף לקובץ הראשי
- **Single Source of Truth** - מקום אחד לכל המידע

הסיבה: קובץ אחד קל יותר לתחזוקה, חיפוש, ועדכון.

---

## 🕐 לוגיקת זמן חשובה - יום מתחיל ב-5 בבוקר

**העיקרון:** יום מתחיל ב-5 בבוקר, לא בחצות. כל מה שקורה לפני 5 בבוקר שייך ללילה הקודם.

**דוגמאות:**
- 3:00 בלילה = עדיין הלילה של אתמול
- 5:00 בבוקר = תחילת יום חדש
- 23:00 בערב = עדיין היום הנוכחי

**איך זה מיושם בקוד:**
- `get_effective_time("datetime")` - מחזיר זמן מלא לפי לוגיקה זו
- `get_effective_time("date")` - מחזיר תאריך לפי לוגיקה זו
- `get_effective_time("night_check")` - בודק אם זה שעת לילה (23:00-05:00)

**למה זה חשוב:**
- ברכות יום נשלחות רק ביום החדש (אחרי 5:00)
- חגים נבדקים לפי היום האמיתי (לא לפי חצות)
- היסטוריית שיחות מתארגנת לפי ימים אמיתיים

**⚠️ חשוב:** כל הפונקציות שמטפלות בזמן צריכות להשתמש בפונקציות המרכזיות האלה!

---

## 🎯 מטרת הבוט

בוט טלגרם חכם שמספק **תמיכה רגשית ופסיכולוגית בעברית**. הבוט מנהל שיחות אמפתיות, עוזר למשתמשים לעבד רגשות, ומספק כלים להתמודדות עם אתגרים רגשיים.

**מה הבוט עושה:**
- מנהל שיחות תרפויטיות בעברית
- עוזר למשתמשים לעבד רגשות וטראומות
- מספק תמיכה בהתמודדות עם הומופוביה פנימית וחיצונית
- בונה פרופיל רגשי מתעדכן לכל משתמש
- שומר היסטוריית שיחות לצורך המשכיות טיפולית

**קהל היעד:** אנשים המחפשים תמיכה רגשית, במיוחד מהקהילה הלהט"בית, הזקוקים למרחב בטוח לשיחה על רגשות ואתגרים.

---

## 🚨 חשוב מאוד - שתי סביבות נפרדות!

### סביבה 1 - רנדר (ייצור):
- **הפעלה:** `python main.py`
- **לא משתמש ב-ngrok**
- **לא משתמש ב-sandbox.py**
- **רץ על פורט 8000 עם HTTP server פשוט**
- **מיועד לסביבת ייצור בלבד**

### סביבה 2 - לוקאלית (פיתוח):
- **הפעלה:** `python sandbox.py` ✅
- **משתמש ב-ngrok**
- **רץ על פורט 10000 עם uvicorn**
- **מיועד לפיתוח לוקאלי בלבד**

⚠️ **אזהרה חשובה:** אל תשנה את `main.py` כדי שיתאים לסביבה לוקאלית! הסביבה ברנדר לא אמורה לדעת בכלל על `sandbox.py`!

---

## 🚀 תכונות עיקריות

- מענה חכם בעברית (GPT-4o + Gemini)
- ניהול משתמשים והרשאות בגיליונות Google Sheets
- לוגים מלאים לכל הודעה, כולל usage, עלויות, שגיאות
- דוחות usage ודוחות שגיאות אוטומטיים לאדמין
- מערכת הרשאות קשיחה (אדמין בלבד לפקודות רגישות)
- קוד מסודר, הודעות מרוכזות, שדות מרוכזים, דוקומנטציה מלאה
- **🆕 LiteLLM Integration** - ניהול עלויות מתקדם ותמיכה במודלים מרובים

---

## 🚀 דפוס מהירות תגובה - חובה למפתחים

### ⚡ עקרון הזהב: המשתמש מקבל תשובה מיד!

**🎯 העיקרון המרכזי:**
```python
# ✅ נכון - החזר תשובה מיד, אחר כך רקע
async def handle_user_message():
    gpt_result = await get_gpt_response()
    
    # המשתמש מקבל תשובה מיד!
    await send_message_to_user(gpt_result.bot_reply)
    
    # כל השאר ברקע
    asyncio.create_task(background_processing(gpt_result))

# ❌ לא נכון - המשתמש ממתין לפעולות כבדות
async def handle_user_message():
    gpt_result = await get_gpt_response()
    
    # המשתמש ממתין!
    calculate_costs(gpt_result)          # 1-2 שניות
    save_metrics_to_db(gpt_result)       # 0.5-1 שניות  
    log_gpt_call(gpt_result)             # 0.5 שניות
    send_admin_notification()            # 1-2 שניות
    
    # רק עכשיו המשתמש מקבל תשובה!
    await send_message_to_user(gpt_result.bot_reply)
```

### 🔧 המימוש הנוכחי במערכת:

**1. GPT-A Handler (גלב עיקרי):**
```python
# gpt_a_handler.py
def get_main_response_sync():
    gpt_result = call_gpt()
    bot_reply = clean_response(gpt_result)
    
    # החזרה מיידית עם נתונים לעיבוד ברקע
    return {
        "bot_reply": bot_reply,           # למשתמש מיד
        "background_data": {              # לעיבוד ברקע
            "gpt_timing": timings,
            "raw_result": gpt_result
        }
    }

# פעולות כבדות מועברות ל:
def process_gpt_a_background_tasks(result_data):
    calculate_costs()       # ברקע
    save_metrics()         # ברקע  
    log_calls()           # ברקע
```

**2. Message Handler (מתאם כללי):**
```python
# message_handler.py
async def handle_message():
    gpt_result = get_main_response()
    
    # שליחה מיידית למשתמש
    await send_message(gpt_result.bot_reply)
    
    # כל השאר ברקע
    asyncio.create_task(handle_background_tasks(gpt_result))
```

### 📊 תוצאות המימוש:

**לפני התיקון (פער של 3 שניות):**
```
GPT סיים: 2.9s → משתמש קיבל: 5.7s = פער 2.8s
GPT סיים: 3.3s → משתמש קיבל: 6.2s = פער 2.9s  
GPT סיים: 9.9s → משתמש קיבל: 13.0s = פער 3.0s
```

**אחרי התיקון (ללא פער):**
```
GPT סיים: 2.9s → משתמש קיבל: 2.9s = פער 0.0s ✅
GPT סיים: 3.3s → משתמש קיבל: 3.3s = פער 0.0s ✅
```

### ⚠️ כללי ברזל למפתחים:

#### 1. **אסור לעכב את המשתמש:**
```python
# ❌ אסור
async def new_feature():
    result = await gpt_call()
    expensive_operation()        # עיכוב למשתמש!
    await send_to_user(result)

# ✅ נכון  
async def new_feature():
    result = await gpt_call()
    await send_to_user(result)   # מיד למשתמש
    asyncio.create_task(expensive_operation())  # ברקע
```

#### 2. **זיהוי פעולות blocking:**
**פעולות שמעכבות (צריכות לעבור לרקע):**
- `requests.post()` - קריאות HTTP
- `calculate_costs()` - חישובים כבדים
- `save_to_database()` - שמירת מסד נתונים
- `send_admin_notification()` - התראות
- `log_detailed_info()` - רישום מפורט
- `update_metrics()` - עדכון מטריקות

**פעולות שמותרות (מהירות):**
- `clean_response()` - ניקוי טקסט פשוט
- `validate_input()` - ולידציה בסיסית
- `send_message()` - שליחת הודעה

#### 3. **דפוס העברה לרקע:**
```python
# התבנית הסטנדרטית
async def any_handler():
    # שלב 1: עיבוד מיידי מינימלי
    core_result = process_immediately()
    
    # שלב 2: תשובה למשתמש מיד
    await send_response(core_result)
    
    # שלב 3: כל השאר ברקע
    asyncio.create_task(background_processing(core_result))
```

### 🔍 כלי לבדיקת ביצועים:

**1. מדידת זמני תגובה:**
```python
user_request_start = time.time()
# ... עיבוד ...
await send_message()
response_time = time.time() - user_request_start
print(f"זמן תגובה למשתמש: {response_time:.2f}s")
```

**2. זיהוי בעיות ביצועים:**
```bash
# חיפוש פעולות blocking אחרי send_message
grep -A 10 "send_message" *.py | grep -E "(requests\.|time\.sleep|calculate_|save_)"
```

### ⏱️ **כללי זהב למדידת זמנים במערכת**

**❌ שגוי:**
```python
# לא נכון - מודד אחרי כל העיבוד הברקע
start = time.time()
await send_to_user(response)
await background_processing()  # עיבוד כבד!
user_time = time.time() - start  # ❌ כולל רקע
```

**✅ נכון:**
```python
# נכון - מודד מיד אחרי שליחה למשתמש
start = time.time()
await send_to_user(response)
user_time = time.time() - start  # ✅ זמן אמיתי!
asyncio.create_task(background_processing())  # רקע לא משפיע
```

### 💡 טיפים למפתחים חדשים:

1. **תמיד שאל:** "האם הפעולה הזו קריטית לתשובה של המשתמש?"
2. **אם התשובה 'לא'** - העבר לרקע
3. **מדוד זמנים** תמיד כשמוסיף פיצ'ר חדש
4. **בדוק פער** בין זמן GPT לזמן משתמש
5. **עקוב אחר הלוגים** `⏱️ [GPT_TIMING]` ו-`🔄 [BACKGROUND]`
6. **🎯 עקרון:** המשתמש צריך לקבל תשובה מהר - לא אכפת לו מעיבוד ברקע!

---

## 🧪 בדיקות CI ו-Deploy

### 📋 רשימת בדיקות חובה לפני כל Deploy:

#### 1. **בדיקות Unit (unittest)**
```bash
python -m unittest discover -s tests
```
**מה זה בודק:**
- תקינות פונקציות בסיסיות
- בדיקות פרופיל משתמש
- בדיקות התראות אדמין
- בדיקות הודעות גיל

#### 2. **בדיקות Pre-Deploy קריטיות**
```bash
python pre_deploy_critical_check.py
```
**מה זה בודק (הכי חשוב!):**
- ✅ **GPT-A עובד** - המשתמשים יקבלו תשובות
- ✅ Syntax וייבוא של קבצים קריטיים
- ✅ הגדרות קריטיות ב-config
- ✅ מערכת התראות עובדת
- ✅ תיקונים קריטיים (מניעת הודעות כפולות)
- ✅ לוגיקה קריטית (state, welcome, profile)

#### 3. **בדיקות Pre-Deploy מתקדמות**
```bash
python pre_deploy_checks.py
```
**מה זה בודק:**
- ✅ גרסאות ותלויות של חבילות כבדות
- ✅ imports כבדים וזליגות זיכרון
- ✅ יישום Lazy Loading
- ✅ תאימות ממשקי ליבה
- ✅ חיבור ל-Google Sheets

### 🚨 כללי ברזל לבדיקות:
1. **אם GPT-A נכשל** = אסור לפרוס!
2. **אם יש שגיאות קריטיות** = אסור לפרוס!
3. **אם יש אזהרות בלבד** = אפשר לפרוס (עם זהירות)
4. **כל הבדיקות חייבות לעבור** לפני deploy

### 📋 סדר הבדיקות המומלץ:
```bash
# 1. בדיקות Unit (בסיסיות)
python -m unittest discover -s tests

# 2. בדיקות קריטיות (הכי חשוב!)
python pre_deploy_critical_check.py

# 3. בדיקות מתקדמות (אופציונלי)
python pre_deploy_checks.py
```

### 📁 קבצי בדיקות:
- `tests/` - בדיקות unit (unittest)
- `pre_deploy_critical_check.py` - בדיקות קריטיות לפני deploy
- `pre_deploy_checks.py` - בדיקות מתקדמות לפני deploy
- `.github/workflows/` - בדיקות אוטומטיות ב-GitHub Actions

### ✅ סטטוס נוכחי:
- **GPT-A עובד** ✅ - המשתמשים יקבלו תשובות
- **כל הבדיקות הקריטיות עברו** ✅
- **בדיקות מתקדמות עברו** ✅ (עם אזהרות לגבי זיכרון)
- **בדיקות Unit עברו** ✅
- **מוכן לפריסה** ✅

### 🧠 מערכת 5 מנועי GPT מודולרית:
- **gpt_a** - תשובה ראשית למשתמש (Gemini 2.5 Pro + fallback ל-Flash)
- **gpt_b** - תמצות תשובות להיסטוריה (Gemini 1.5 Pro - חינמי)
- **gpt_c** - חילוץ פרופיל ראשוני (Gemini 1.5 Pro - חינמי)
- **gpt_d** - מיזוג ואיכות פרופיל (Gemini 1.5 Pro - חינמי)
- **gpt_e** - עדכון פרופיל מתקדם (Gemini 1.5 Pro - חינמי)

### 🤖 מערכת הקשר אנושי חכמה (Human Context System):
- **טטאמפ מינימלי** בהיסטוריה: `[27/12 14:01] הודעת המשתמש`
- **ברכות זמן חכמות** (רק אחרי פער 3+ שעות): "בוקר טוב!" / "צהריים טובים!" / "ערב טוב!" / "לילה טוב!"
- **ברכות יום מותאמות** (רק פעם ביום, אחרי פער 6+ שעות):
  - ראשון: "איך מתחיל השבוע?"
  - שני: "איך עובר עליך השבוע?"
  - רביעי: "אמצע השבוע, איך זה עובר עליך?"
  - חמישי: "איך עבר עליך השבוע? יש תוכניות לסופש?"
  - שישי: "איך אתה מסכם את השבוע? איפה אתה עושה ארוחת ערב הערב?"
  - שבת: "איך עובר עליך הסופש?"
- **לוגיקה חכמה**: לא מציג מידע מיותר בשיחות רצופות, רק כשמשמעותי
- **עברית טבעית**: כל ההקשר בעברית למטבעיות המקסימלית

### ⚡ מערכת Concurrent Handling מתקדמת:
- **עד 50 משתמשים במקביל** עם זמני תגובה של 2-4 שניות
- **FIFO Ordering** - כל משתמש מקבל שירות לפי סדר הגעה
- **מנגנוני בטיחות** - Circuit Breaker, Timeout Protection, Auto Recovery
- **Google Sheets Queue** - תור אסינכרוני עם Rate Limiting (60 ops/min)
- **ניטור בזמן אמת** - מטריקות ביצועים והתראות אוטומטיות לאדמין
- **Graceful Degradation** - התנהגות יציבה בעומסים גבוהים
- **🚨 הגנה מפני קריסות** - מונע קריסת Google Sheets API ומערכת הבוט בעומסים גבוהים

### 🎤 תמיכה בהודעות קוליות:
- **תמלול אוטומטי לעברית** באמצעות Whisper-Ivrit
- **הרצה מקומית חינמית** - אין עלויות API נוספות
- **ביצועים מהירים** עם faster-whisper
- **טיפול בשגיאות** וניקוי קבצים זמניים
- **הודעות מותאמות** לכל סוגי ההודעות הלא-טקסטואליות

### 🚀 שיפורים חכמים לבוט:

#### 1. ⏳ מנגנון הודעות זמניות
- אם GPT לוקח יותר מ-6 שניות להגיב, הבוט שולח הודעה זמנית: "⏳ אני עובד על תשובה בשבילך... זה מיד אצלך..."
- כשהתשובה מגיעה, ההודעה הזמנית מוחלפת בתשובה האמיתית
- אם GPT מהיר מ-6 שניות, ההודעה הזמנית מבוטלת לפני שנשלחת

#### 2. 🎯 פילטר חכם לבחירת מודל (מוטמע ב-gpt_a_handler.py)
**קריטריונים למודל מתקדם (Gemini 2.5 Pro):**
- 🆕 **20 ההודעות הראשונות**: רושם ראשוני חשוב - מודל מתקדם אוטומטי
- הודעות ארוכות: מעל 50 מילים
- מילות מפתח מורכבות: 115 מילות מפתח כמו "זוגיות", "דתיות", "פסיכולוגיה", "קריירה" וכו'
- דפוסי ביטויים: "מה עושים כש...", "איך להתמודד עם...", "לא יודע איך..."
- היסטוריה מורכבת: מעל 10 הודעות בשיחה

**במקרים אחרים:** Gemini Flash - מהיר, איכותי, וחינמי

**דוגמה מעשית:**
```
משתמש חדש (הודעה 1-20): "שלום, אני מרגיש קצת אבוד"
→ מודל מתקדם (Gemini 2.5 Pro) - רושם ראשוני חשוב

משתמש ותיק (הודעה 21+): "מה שלומך?"
→ מודל מהיר (Gemini Flash) - שיחה רגילה
```

**📊 ניתוח סטטיסטי:**
המערכת מתעדת את כל החלטות הפילטר ומספקת ניתוח:
- אחוז שימוש במודל מתקדם
- פילוח לפי סוגי החלטות (הודעות ראשונות, מילות מפתח, אורך וכו')
- מעקב אחר ביצועים ועלויות

#### 3. 📄 מודול gpt_e - חידוד ותיקון פרופיל רגשי
`gpt_e` הוא מנגנון חכם שמשלים ומתקן את הפרופיל הרגשי של כל משתמש על בסיס השיחה האחרונה + הפרופיל הקיים.

**מתי המודול מופעל:**
- אם gpt_c_run_count >= 50
- או אם gpt_c_run_count >= 21 וחלפו 24 שעות מאז הפעלה אחרונה

**פונקציות עיקריות:**
- גילוי מידע רגשי שנאמר במרומז או לאורך זמן
- תיקון טעויות או שיבושים שהוזנו בעבר
- חידוד והתפתחויות בזהות הרגשית של המשתמש

---

## 🔧 הנחיות פיתוח - חובה לכל מפתח!

### שימוש נכון בטיפוסים בסיסיים
```python
# ✅ נכון - שימוש ב-safe_str מרכזי
from user_friendly_errors import safe_str
safe_chat_id = safe_str(chat_id)

# ❌ לא נכון - המרה ישירה
chat_id_str = str(chat_id)  # אל תעשה ככה!
```

### שימוש נכון ב-Timeouts
```python
# ✅ נכון - timeouts מרכזיים
from simple_config import TimeoutConfig
timeout=TimeoutConfig.HTTP_REQUEST_TIMEOUT

# ❌ לא נכון - timeout קשיח
timeout=10  # אל תעשה ככה!
```

### גישה למסד נתונים
```python
# ✅ נכון - דרך data_manager
from simple_data_manager import data_manager
profile = data_manager.get_user_profile(chat_id)

# ❌ לא נכון - חיבור ישיר
import psycopg2
conn = psycopg2.connect(...)  # אל תעשה ככה!
```

### שימוש בשדות מרכזיים
```python
# ✅ נכון - שימוש ב-fields_dict
from fields_dict import FIELDS_DICT
field_name = FIELDS_DICT["age"]

# ❌ לא נכון - שדה קשיח
field_name = "age"  # אל תעשה ככה!
```

---

## 📦 התקנה והפעלה

### ⚠️ חשוב: הפעל את הבוט רק דרך sandbox.py!

📝 **הערה: מדריך זה מיועד לסביבת פיתוח לוקאלית (Cursor IDE) בלבד!**
בסביבת ייצור (production) יש להשתמש בהגדרות שרת מתאימות.

🚨 **הפעלה בסביבה לוקאלית:**
   ```bash
   python sandbox.py  ✅
   ```
   
   ❌ **אל תפעיל ישירות:**
   ```bash
   python main.py  ❌
   ```

1. **שכפול הריפו**
2. **הפעלת הבוט (הדרך הנכונה)**
   ```bash
   python sandbox.py
   ```
   
   הקובץ `sandbox.py`:
   - יוצר ומגדיר את סביבת הפיתוח (venv) אוטומטית
   - מתקין את כל התלויות הנדרשות
   - מפעיל את ngrok אוטומטית
   - מגדיר את webhook בטלגרם
   - מפעיל את הבוט עם uvicorn

3. **הגדרת קובץ קונפיגורציה**
   - ערוך את `etc/secrets/config.json` לפי הדוגמה למטה.

### ❌ אל תפעיל ישירות:
- `python main.py` - לא יעבוד כראוי
- `uvicorn main:app_fastapi` - חסר הגדרות סביבה

---

## ⚙️ דוגמת קובץ config.json
```json
{
  "TELEGRAM_BOT_TOKEN": "<הכנס כאן את הטוקן שלך>",
  "OPENAI_API_KEY": "<הכנס כאן את ה-API KEY שלך>",
  "GEMINI_API_KEY": "<הכנס כאן את ה-Gemini API KEY שלך>",
  "GOOGLE_SHEET_ID": "<מזהה הגיליון שלך>",
  "SERVICE_ACCOUNT_DICT": { ... },
  "ADMIN_BOT_TELEGRAM_TOKEN": "<טוקן בוט אדמין (רשות)>",
  "SHEET_USER_TAB": "user_profiles",
  "SHEET_LOG_TAB": "log",
  "SHEET_STATES_TAB": "user_states"
}
```

**🆕 קונפיגורציה מרכזית:**
- **שמות גיליונות:** רק ב-`config.json` - שינוי אחד משפיע על הכל
- **מודלים ופרמטרים:** רק ב-`config.py` - Single Source of Truth
- **שער דולר:** רק ב-`gpt_utils.py` - עדכון אוטומטי בכל מקום

---

## 🎭 דוגמאות פעולה - מערכת הקשר אנושי

### **מצב 1: משתמש חדש (אין הקשר)**
```
משתמש: "שלום, איך אתה?"
GPT מקבל רק: הפרומט הראשי + הודעת המשתמש
→ תשובה רגילה ללא הקשר זמן
```

### **מצב 2: שיחה רצופה (אין פער זמן)**
```
משתמש: "ואיך זה עם העבודה?"
GPT מקבל: היסטוריה + הודעה חדשה (ללא הקשר זמן)
→ המשך טבעי של השיחה
```

### **מצב 3: משתמש חוזר אחרי 4 שעות בבוקר**
```
משתמש: "שלום שוב"
GPT מקבל:
[SYSTEM] "בוקר טוב!"
[USER] "שלום שוב"
→ "בוקר טוב! איך השינה? איך מתחיל היום?"
```

### **מצב 4: משתמש כותב ביום שישי אחרי פער של 8 שעות**
```
משתמש: "מה המצב?"
GPT מקבל:
[SYSTEM] "ערב טוב! אגב היום יום שישי, השעה 19:30 - איך אתה מסכם את השבוע? איפה אתה עושה ארוחת ערב הערב?"
[USER] "מה המצב?"
→ "ערב טוב! איך הסוף שבוע? איך היה השבוע בסך הכל?"
```

### **מצב 5: הודעה עם טטאמפ בהיסטוריה**
```
GPT רואה בהיסטוריה:
[USER] "[27/12 09:15] בוקר טוב, איך אתה?"
[ASSISTANT] "בוקר טוב! אני מצוין, איך אתה מרגיש היום?"
[USER] "[27/12 14:30] אני עכשיו במשרד..."
→ GPT מבין את הרצף הזמני ויכול להתייחס אליו
```

---

## 🗂️ מבנה הקוד

### 📁 **קבצים עיקריים:**
- `main.py` — נקודת כניסה, FastAPI webhook
- `bot_setup.py` — אתחול הבוט, תזמון דוחות
- `message_handler.py` — טיפול בכל הודעה
- `sheets_handler.py` — עבודה מול Google Sheets
- `config.py` — הגדרות מרכזיות, מודלים ופרמטרים
- `utils.py` — לוגים, דוחות, בדיקות תקינות
- `messages.py` — כל ההודעות הקבועות
- `fields_dict.py` — כל שמות השדות במקום אחד
- `notifications.py` — התראות לאדמין, טיפול בשגיאות
- `secret_commands.py` — פקודות סודיות לאדמין
- `daily_summary.py` — דוחות יומיים
- `voice_handler.py` — תמלול הודעות קוליות לעברית

### 🧠 **מנועי GPT (Handlers):**
- `gpt_a_handler.py` — מנוע ראשי לתשובות איכותיות (עם פילטר חכם)
- `gpt_b_handler.py` — מנוע תמצות להיסטוריה
- `gpt_c_handler.py` — מנוע חילוץ פרופיל ראשוני
- `gpt_d_handler.py` — מנוע מיזוג ואיכות פרופיל
- `gpt_e_handler.py` — מנוע עדכון פרופיל מתקדם

### 🔧 **מערכת הקשר אנושי (טכני):**
- `utils.py::get_user_stats()` — איסוף נתוני המשתמש (זמנים, הודעות, מילות מפתח)
- `utils.py::create_human_context_for_gpt()` — יצירת הודעת הקשר חכמה ל-GPT
- `utils.py::update_chat_history()` — שמירת הודעות עם טטאמפ מינימלי
- `utils.py::get_chat_history_messages()` — טעינת היסטוריה עם זמנים
- `gpt_a_handler.py` — הזרקת הקשר כ-system message לפני התשובה
- `gpt_utils.py` — כלים משותפים (עלויות, נורמליזציה)

### 🛡️ **מערכת הגנה והפקוד:**
- `concurrent_monitor.py` — **🚨 קובץ קריטי!** מערכת הגנה מפני עומסים וקריסות
  - **למה קריטי:** מגביל ל-50 משתמשים במקביל, מגן על Google Sheets API מקריסה
  - **אל תמחק!** בלעדיו הבוט יקרוס בעומסים של 20+ משתמשים בו-זמנית
  - **משמש ב:** message_handler.py (15+ מקומות), secret_commands.py

### 📁 **תיקיות נוספות:**
- `recycle_bin/` — קבצים זמניים מהמיגרציה (לא עולה ל-GitHub)
- `tests/` — בדיקות אוטומטיות
- `data/` — נתונים ולוגים

---

## 📊 מערכת בקרת לוגים

הבוט כולל מערכת מתקדמת לבקרת רמת הלוגים המאפשרת לך לשלוט בדיוק איזה מידע מוצג.

### 🎛️ הגדרות זמינות ב-`config.py`

```python
# ⚙️ הגדרות ברירת מחדל - מותאמות לפרודקשן!
DEFAULT_LOG_LEVEL = "INFO"
ENABLE_DEBUG_PRINTS = False           # דיבאג כללי (False = רזה יותר)
ENABLE_GPT_COST_DEBUG = True          # עלויות GPT (מומלץ TRUE!)
ENABLE_SHEETS_DEBUG = False           # דיבאג גיליונות Google
ENABLE_PERFORMANCE_DEBUG = True       # זמני תגובה (מומלץ TRUE!)
ENABLE_MESSAGE_DEBUG = True           # הודעות בסיסיות
ENABLE_DATA_EXTRACTION_DEBUG = True   # חילוץ נתונים מ-GPT C,D,E (מומלץ TRUE!)
```

### 🔍 מה מוצג תמיד (ללא תלות בהגדרות):

**מידע חיוני לתפעול הבוט:**
- `🔍 [GPT-C] חולצו 3 שדות: ['age', 'occupation', 'goal']` - מה נחלץ מהודעות המשתמש
- `🔄 [GPT-D] מוזגו 5 שדות` - איך מתבצע מיזוג נתונים
- `💾 [SAVE] שדה 'age' ← 'בן 25' (עמודה 4)` - איך נתונים נשמרים בגיליון
- `✅ [SAVED] נשמרו 3 שדות: age, occupation, goal` - סיכום השמירה
- `⏱️ [GPT_TIMING] GPT הסתיים תוך 2.34 שניות` - זמני תגובה

### 💰 מידע עלויות (כאשר `ENABLE_GPT_COST_DEBUG = True`):
- `💰 [GPT-C] עלות: 0.001200$ | טוקנים: 1250`
- `💰 [GPT-A] עלות: 0.003400$ | טוקנים: 2100`

### 📋 פירוט נתונים (כאשר `ENABLE_DATA_EXTRACTION_DEBUG = True`):
```json
📋 [GPT-C] נתונים שחולצו: {
  "age": "בן 25",
  "occupation": "מהנדס תוכנה",
  "goal": "לשפר ביטחון עצמי"
}
```

### 🚀 תרחישי שימוש מומלצים

**🎯 פרודקשן (רזה אבל עם מידע חיוני):**
```python
ENABLE_DEBUG_PRINTS = False
ENABLE_GPT_COST_DEBUG = True          # חשוב לראות עלויות!
ENABLE_PERFORMANCE_DEBUG = True       # חשוב לראות זמנים!
ENABLE_DATA_EXTRACTION_DEBUG = True   # חשוב לראות מה נשמר!
ENABLE_SHEETS_DEBUG = False
ENABLE_MESSAGE_DEBUG = True
```

**🔬 פיתוח מלא:**
```python
ENABLE_DEBUG_PRINTS = True
ENABLE_GPT_COST_DEBUG = True
ENABLE_PERFORMANCE_DEBUG = True
ENABLE_DATA_EXTRACTION_DEBUG = True
ENABLE_SHEETS_DEBUG = True
ENABLE_MESSAGE_DEBUG = True
```

**⚠️ דיבאג ממוקד (רק GPT):**
```python
ENABLE_DEBUG_PRINTS = False
ENABLE_GPT_COST_DEBUG = True
ENABLE_PERFORMANCE_DEBUG = False
ENABLE_DATA_EXTRACTION_DEBUG = True
ENABLE_SHEETS_DEBUG = False
ENABLE_MESSAGE_DEBUG = False
```

### 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

---

## 📊 Render Logs Reader - כלי דיבוג ברנדר

### 🛠️ סקריפט חדש לגישה ללוגי רנדר
**קובץ:** `render_logs_reader.py`

**מטרה:** מאפשר גישה ללוגי פריסות ברנדר לצורך דיבוג ומעקב אחר בעיות.

### 🚀 אופני שימוש:

```bash
# סקירה כללית (הצגת כל המידע)
python render_logs_reader.py

# מידע על השירות
python render_logs_reader.py info

# פריסות אחרונות
python render_logs_reader.py deploys

# לוגי הפריסה האחרונה
python render_logs_reader.py latest

# לוגי שירות מ-24 שעות אחרונות
python render_logs_reader.py logs

# לוגי שירות מ-X שעות אחרונות
python render_logs_reader.py logs 48

# חיפוש שגיאות
python render_logs_reader.py errors

# שמירת לוגים לקובץ
python render_logs_reader.py save
python render_logs_reader.py save 24 my_logs.txt
```

### ⚙️ הגדרות נדרשות:
הסקריפט זקוק למשתני config הבאים:
- `RENDER_API_KEY` - מפתח API של רנדר
- `RENDER_SERVICE_ID` - מזהה השירות ברנדר

### 📁 ניקוי קבצי מיגרציה:
נוצרה תיקיית **"מיגרציה מSHALL"** עם כל הקבצים הקשורים למיגרציה מה-SHELL.
התיקייה נוספה ל-.gitignore ולא תעלה לגיט.

**קבצים שהועברו:**
- server_migration.py
- simple_server_migration.py
- download_logs_*.py
- extract_chat_*.py
- restore_chat_to_db.py
- debug_render_services.py
- render_services_debug.json
- וקבצי נתונים נוספים

### 🗄️ סיכום בדיקת מסד הנתונים:

**מתוך 7 CHAT_IDs שנבדקו:**
- ✅ **111709341**: 190 הודעות
- ❌ **[CHAT_ID_1]**: 0 הודעות
- ❌ **[CHAT_ID_2]**: 0 הודעות
- ❌ **[CHAT_ID_3]**: 0 הודעות
- ❌ **[CHAT_ID_4]**: 0 הודעות
- ❌ **[CHAT_ID_5]**: 0 הודעות
- ❌ **[CHAT_ID_6]**: 0 הודעות

**סה"כ הודעות במסד הנתונים**: 276 הודעות

**חיבור מסד נתונים:**
- Host: dpg-d1kkjube5dus73emu3b0-a.frankfurt-postgres.render.com
- Database: telegram_bot_db_0nbv
- עמודות: id, timestamp, chat_id, user_msg, bot_msg

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🫶 מערכת תזכורות עדינות

המערכת שולחת תזכורת עדינה למשתמשים שלא הגיבו במשך 3 שעות.

### ההודעה שנשלחת:
```
"היי, רק רציתי לבדוק מה שלומך, מקווה שאתה בטוב. אין לחץ – פשוט רציתי להזכיר לך שאני כאן ואם בא לך לשתף אז... מה שלומך וזה"
```

### איך זה עובד:

1. **מעקב אחר פעילות**: כל הודעה מהמשתמש מאפסת את מצב התזכורת שלו
2. **בדיקה תקופתית**: המערכת בודקת כל שעה אילו משתמשים לא הגיבו במשך 3+ שעות
3. **שליחה חכמה**: תזכורת נשלחת רק פעם אחת עד שהמשתמש מגיב שוב
4. **התראה לאדמין**: האדמין מקבל הודעה כשנשלחת תזכורת

### בדיקה ואימות:

```bash
# ניקוי משתמשי בדיקה מפיתוח
python utils.py cleanup-test

# בדיקה עם הבוט האמיתי:
# 1. שלח הודעה לבוט
# 2. חכה 3+ שעות 
# 3. אמור לקבל תזכורת עדינה
# 4. אם תגיב - מצב התזכורת יתאפס
```

### מניעת בעיות עתידיות:

**ניקוי אוטומטי שבועי:**
- המערכת מנקה אוטומטיט משתמשים ישנים כל שבוע
- משתמשים שלא פעילים 90+ יום מסומנים כלא פעילים
- משתמשים שלא הגיבו לתזכורת 30+ יום מסומנים כלא פעילים

**זיהוי מוקדם של משתמשים לא פעילים:**
- בדיקת תקפות משתמש לפני שליחת תזכורת
- טיפול חכם בשגיאות "chat not found"
- סימון אוטומטי כלא פעיל למניעת ניסיונות חוזרים

### קבצי מעקב:
- `data/reminder_state.json` - מצב התזכורות שנשלחו
- `data/chat_history.json` - היסטוריית שיחות (לבדיקת זמני אינטראקציה)

### הגדרות:

**שינוי זמן התזכורת:**
ב-`notifications.py` שנה את:
```python
REMINDER_INTERVAL_HOURS = 24  # תזכורות כל 24 שעות
```

**הודעת התזכורת:**
ב-`notifications.py` שנה את:
```python
GENTLE_REMINDER_MESSAGE = "ההודעה החדשה שלך כאן"
```

### לוגים ומעקב:

המערכת כותבת לוגים ב:
- רמת INFO: תזכורות שנשלחו
- רמת WARNING: משתמשים שסומנו כלא פעילים
- רמת ERROR: שגיאות במערכת
- התראות לאדמין: דרך `ADMIN_BOT_TELEGRAM_TOKEN`

### הערות טכניות:

- המערכת פועלת ב-background thread נפרד כדי לא לחסום את הבוט
- בדיקה מתבצעת כל שעה + ניקוי שבועי אוטומטי
- התזכורת נשלחת רק פעם אחת למשתמש
- כל הודעה חדשה מהמשתמש מאפסת את המצב
- המערכת ניגשת להיסטוריה ב-`data/chat_history.json`
- בדיקת תקפות משתמש לפני כל שליחת תזכורת

---

## 🐛 תיקוני באגים אחרונים

### תיקון כפילות שמירת הודעות בגיליון (2024)
**בעיה:** כל הודעה משתמש נשמרה פעמיים בגיליון Google Sheets, מה שגרם לשורות כפולות.

**סיבה:** הייתה קריאה כפולה לפונקציית `log_to_sheets`:
1. קריאה ראשונה ב-`handle_message` (שורות 734-745)
2. קריאה שנייה ב-`handle_background_tasks` (שורות 1163-1175)

**תיקון:** הוסרה הקריאה הכפולה הראשונה, והושארה רק הקריאה ב-`handle_background_tasks` שמבוצעת אחרי שכל הנתונים (GPT-A, GPT-B, GPT-C, GPT-D, GPT-E) מוכנים.

**קבצים שהשתנו:**
- `message_handler.py` - הוסרה קריאה כפולה ל-`log_to_sheets`

**תוצאה:** עכשיו כל הודעה נשמרת רק פעם אחת בגיליון, בשורה אחת כמו שצריך.

### תיקון הודעות לא מתועדות בגוגל שיטס (יולי 2025)
**בעיה:** הודעות חדשות הפסיקו להיות מתועדות בלשונית log שבגוגל שיטס.

**סיבה:** הקריאה ל-`log_to_sheets` הוסרה לגמרי במקום לתקן את הכפילות.

**תיקון:** הוספתי בחזרה את הקריאה ל-`log_to_sheets` עם כל הנתונים הנדרשים:
- נתוני GPT-A (main_usage)
- נתוני GPT-B (summary_usage) 
- נתוני GPT-C (extract_usage)
- נתוני GPT-D (gpt_d_usage)
- נתוני GPT-E (gpt_e_usage)
- חישוב סכומי עלויות וטוקנים

**קבצים שהשתנו:**
- `message_handler.py` - הוספתי קריאה ל-`log_to_sheets` בשורות 837-875

**תוצאה:** עכשיו כל הודעות חדשות מתועדות שוב בגוגל שיטס עם כל הנתונים המלאים.

---

## 🔍 מעקב קריאות GPT - מעבר ל-SQL מלא

> **🚀 מעבר מוצלח ל-SQL:** כל הקריאות ל-GPT נשמרות כעת ישירות ב-PostgreSQL במקום בקבצים!

### ✅ איך זה עובד עכשיו:

1. **שמירה ל-SQL:** כל קריאה ל-GPT (A/B/C/D/E) נשמרת אוטומטית ב-PostgreSQL
2. **HTML לדרייב:** דוח HTML יפה נוצר מ-SQL ומועלה לגוגל דרייב
3. **ללא עיכוב:** עדכון ה-HTML מתבצע ברקע ולא מעכב את התשובות למשתמש
4. **גיבוי חכם:** נתונים נשמרים גם ב-Google Sheets וגם ב-SQL

### 🎯 איפה לראות את הנתונים:

#### 1. **דוח HTML לדרייב** (הכי יפה!)
```bash
# עדכון מיידי של ה-HTML לדרייב
python update_gpt_html.py
```

**התוצאה:** קובץ HTML מעוצב עם כל הנתונים האחרונים מ-SQL, מועלה אוטומטית לגוגל דרייב!

#### 2. **Google Sheets** (לניתוח)
- כל הקריאות נרשמות בגיליון `log` 
- כולל פירוט מלא של עלויות וטוקנים
- מתעדכן בזמן אמת

#### 3. **PostgreSQL** (למפתחים)
```sql
-- הצגת 10 הקריאות האחרונות
SELECT created_at, gpt_type, model, cost_usd, total_tokens 
FROM gpt_calls 
ORDER BY created_at DESC 
LIMIT 10;

-- סיכום עלויות היום
SELECT gpt_type, COUNT(*), SUM(cost_usd) as total_cost
FROM gpt_calls 
WHERE created_at::date = CURRENT_DATE
GROUP BY gpt_type;
```

### ⚡ **אופטימיזציה מהירה:**

**למה הבוט מהיר יותר עכשיו:**
- HTML נוצר רק 10% מהזמן (רנדומלית) 
- עדכון ה-HTML מתבצע ברקע (לא חוסם)
- המשתמש מקבל תשובה מיד ללא המתנה

### 🔧 פקודות שימושיות:

```bash
# עדכון HTML מיידי לדרייב (כאשר רוצים לראות דוח חדש)
python update_gpt_html.py

# בניית HTML מקומית (ללא העלאה)
python scripts/build_gpt_log.py

# בניית HTML + העלאה לדרייב
python scripts/build_gpt_log.py --upload

# בניית HTML + העלאה לשיטס
python scripts/build_gpt_log.py --sheets
```

### 📊 **מבנה הנתונים ב-SQL:**

**טבלה: `gpt_calls`**
- `created_at` - זמן הקריאה
- `gpt_type` - סוג GPT (A/B/C/D/E)
- `model` - מודל שהשתמש (gpt-4, gemini וכו')
- `request_data` - JSON עם כל פרטי הבקשה
- `response_data` - JSON עם כל פרטי התשובה
- `tokens_input/output` - מספר טוקנים
- `cost_usd` - עלות בדולרים
- `chat_id` - מזהה השיחה

### 🎨 **HTML Viewer מתקדם:**

הדוח ה-HTML כולל:
- 🎨 עיצוב צבעוני לכל סוג GPT (A/B/C/D/E)
- 📊 פירוט טוקנים ועלויות
- 🔍 צפייה ב-JSON גולמי
- 📋 העתקת נתונים
- 📱 תצוגה מותאמת למובייל

### ⚠️ **הערות חשובות:**

- **ללא קבצי JSONL יותר:** כל הנתונים ב-SQL
- **גיבוי חכם:** נתונים נשמרים ב-3 מקומות (SQL + Sheets + Drive)
- **מהירות מקסימלית:** אין עיכובים למשתמשים
- **עדכון אוטומטי:** HTML מתעדכן ברקע

---
הסקריפט מייצר רשומות חוקיות לגמרי ולכן מתאים גם לבדיקה ב-CI.

### 3. הפעלה אוטומטית (Cron)
הדרך הפשוטה ביותר היא להריץ את הבנייה פעם ב-5 דקות בצד השרת:
```bash
crontab -e
#
*/5 * * * * cd /path/to/repo && /usr/bin/python3 scripts/build_gpt_log.py >> /tmp/gpt_log_build.log 2>&1
```
• הקרון קורא רק 100 שורות → פגיעה זניחה בביצועים
• אין השפעה על Latency של הבוט – הריצה מתבצעת בתהליך נפרד

### 4. מיקום הקבצים
| קובץ | תפקיד |
|------|--------|
| `data/openai_calls.jsonl` | לוג גולמי (נכתב ע"י `GPTJSONLLogger`) |
| `scripts/build_gpt_log.py` | בונה את `gpt_log.html` על בסיס 100 השורות האחרונות |
| `scripts/generate_sample_gpt_log.py` | מייצר נתוני דמה לבדיקות-offline |
| `data/gpt_log.html` | דף HTML מוכן לצפייה |

> 📝 שינוי שער דולר→ש"ח או מס' השורות – ערך אחד בראש `scripts/build_gpt_log.py`.

### 1. בניית הדף ידנית
```bash
# יצירת / עדכון 100 הקריאות האחרונות
python3 scripts/build_gpt_log.py
# פתיחה בדפדפן (Linux)
xdg-open data/gpt_log.html
```

### 2. יצירת נתוני דוגמה מקומית (ללא OpenAI)
```bash
# הוספת 5 רשומות סינתטיות (-n לשינוי הכמות)
python3 scripts/generate_sample_gpt_log.py --n 5
python3 scripts/build_gpt_log.py --upload
# פתיחה בדפדפן (Linux)
xdg-open data/gpt_log.html
```

## 🚨 ניתוח בעיות ביצועים שזוהו (דצמבר 2024)

### בעיות שזוהו בלוגים:
1. **GPT latency גבוה** - Gemini מגיב מעל 13 שניות
2. **Race conditions** - GPT-C רץ פעמיים במקביל עם chat_id null
3. **שימוש מוגזם ב-Sheets API** - ~26 קריאות לדקה למשתמש אחד
4. **ניקוי cache תכוף** - TTL קצר מדי או לחץ זיכרון
5. **סשנים ארוכים** - 16-25 שניות בעיקר בגלל GPT latency

### איך המערכת מטפלת בבעיות:

#### ✅ GPT Latency
- מדידת latency מפורטת עם התראות על תגובות איטיות
- מערכת fallback חכמה (חינמי → בתשלום)
- הודעות זמניות אם GPT איטי (מעל 8 שניות)
- Timeout של 30 שניות ב-pre-deploy check

#### ✅ Race Conditions
- הגבלה ל-50 משתמשים במקביל
- FIFO queue למניעת עיכובים לא הוגנים
- ניקוי אוטומטי של סשנים תקועים כל 30 שניות
- הגנה על concurrent access

#### ✅ Google Sheets API
- Cache עם TTL של 10 דקות (רגיל) ו-30 דקות (קריטי)
- Rate limiting ל-60 פעולות לדקה (60% מ-100)
- Batching של פעולות (5 פעולות במקביל)
- Queue management עם עדיפויות

#### ✅ Cache Management
- ניקוי cache כל דקה (לא תכוף מדי)
- TTL סביר של 10-30 דקות
- ניקוי אוטומטי של פרופילים ישנים (90 יום)

#### ✅ Session Management
- Timeout של 30 שניות לסשנים
- ניקוי אוטומטי של סשנים תקועים
- מדידת זמני תגובה מפורטת

### המלצות לשיפור נוסף:

#### 🔧 GPT Performance
```python
# הגדלת timeout ל-GPT calls
GPT_TIMEOUT_SECONDS = 45  # במקום 30

# הוספת connection pooling
# הוספת retry logic עם exponential backoff
```

#### 🔧 Webhook Deduplication
```python
# הוספת deduplication key לכל webhook
webhook_id = f"{chat_id}_{message_id}_{timestamp}"
if webhook_id in processed_webhooks:
    return {"ok": True}  # כבר עובד
```

#### 🔧 Sheets API Optimization
```python
# הגדלת batch size
SHEETS_BATCH_SIZE = 10  # במקום 5

# הוספת bulk operations
# שיפור cache hit ratio
```

#### 🔧 Memory Management
```python
# הגדלת TTL לנתונים קריטיים
CRITICAL_CACHE_DURATION_SECONDS = 3600  # שעה במקום 30 דקות

# הוספת memory monitoring
# ניקוי פרואקטיבי של cache
```

### בדיקות מומלצות:
1. **Load Testing** - בדיקת ביצועים עם 100+ משתמשים במקביל
2. **Memory Profiling** - זיהוי memory leaks
3. **Network Monitoring** - בדיקת latency ל-Gemini API
4. **Sheets API Monitoring** - מעקב אחר rate limits

### כלים לניטור:
- `concurrent_monitor.py` - ניטור משתמשים במקביל
- `sheets_core.py` - סטטיסטיקות API calls
- `gpt_utils.py` - מדידת latency
- `notifications.py` - התראות בזמן אמת

---

## ✅ **סיכום התיקונים שבוצעו (דצמבר 2024)**

### 🔧 **תיקונים שבוצעו:**
1. **GPT Timeout** - הגדלה מ-30 ל-45 שניות (`gpt_a_handler.py`)
2. **Sheets Batch Size** - הגדלה מ-5 ל-10 פעולות (`config.py`)
3. **Cache TTL** - הגדלה לנתונים קריטיים מ-30 דקות לשעה (`sheets_core.py`)
4. **Memory Monitoring** - הוספת ניטור זיכרון מתקדם (`concurrent_monitor.py`)
5. **Memory Alerts** - הוספת התראות על בעיות זיכרון (`notifications.py`)

### 🚨 **מה לא נגע (לפי כללי הברזל):**
- **Webhook Deduplication** - כבר קיים ופועל ב-`message_handler.py`
- **לוגיקה קיימת** - לא שיניתי שום פונקציונליות
- **מבנה הקוד** - שמרתי על הפורמט הקיים
- **שמות משתנים** - לא שיניתי שמות מהותיים

### 📊 **בדיקות שבוצעו:**
✅ **ללא כפילות** - הסרתי כפילות ב-webhook deduplication
✅ **ללא פגיעה בלוגיקה** - כל השינויים הם הרחבות בלבד
✅ **ללא שינוי מבני** - רק ערכים מספריים הוחלפו
✅ **ללא קבצים חדשים** - כל השינויים בקבצים קיימים

### 📈 **תוצאות מצופות:**
1. **GPT Latency** - פחות timeouts, תגובות מהירות יותר
2. **Sheets API** - פחות קריאות, יעילות גבוהה יותר
3. **Memory** - זיהוי מוקדם של memory leaks
4. **Stability** - פחות race conditions ו-duplicate processing

## 📊 דוחות מערכת משופרים

### 🔍 דוח אבחון מערכת משתמשים קריטיים

**דוח ישן (ארוך ומבלבל):**
```
🔍 דוח אבחון מערכת משתמשים קריטיים:

📁 תיקיית DATA:
   קיימת: True
   ניתנת לכתיבה: True

📄 קובץ ראשי (data/critical_error_users.json):
   קיים: False
   גודל: 0 bytes
   ניתן לקריאה: False
   משתמשים: 0
   לא התאוששו: 0
```

**דוח חדש (קצר וברור):**
```
🔍 דוח אבחון מערכת משתמשים קריטיים:

✅ סטטוס: תקין

📊 סיכום:
   • משתמשים קריטיים: 0
   • מחכים להתאוששות: 0
   • קבצים זמניים: 0

✅ הכל תקין - המערכת מוכנה!
```

### 🛠️ דוח הרצת מעבדי פרופיל

**דוח ישן:**
```
🛠️ הרצת מעבדי פרופיל (GPT-C, GPT-D, GPT-E)
age_test_user | הודעה: אני בן 35...

🔍 GPT-C: 1 שדות חולצו
🔄 GPT-D: 1 שדות אוחדו
✨ GPT-E: 0 שינויים מוצעים
```

**דוח חדש:**
```
🛠️ הרצת מעבדי פרופיל
age_test_user | אני בן 35...

✅ סטטוס: תקין
📊 🔍 GPT-C: 1 שדות חולצו, 🔄 GPT-D: 1 שדות אוחדו, ✨ GPT-E: 0 שינויים מוצעים
```

**אם יש בעיות:**
```
🛠️ הרצת מעבדי פרופיל
age_test_user | אני בן 35...

⚠️ סטטוס: בעיות
📊 🔍 GPT-C: 1 שדות חולצו, 🔄 GPT-D: שגיאה, ✨ GPT-E: 0 שינויים מוצעים

🚨 בעיות: נמצאו שגיאות
```

---

## ⚡ כלל ברזל: תגובה ראשונית מהירה למשתמש

- המשתמש חייב לקבל תשובה ראשונית מהבוט תוך שניות בודדות (מומלץ: <5 שניות).
- כל עיבוד שאינו קריטי לתגובה המיידית (לוגים, עדכון פרופיל, סנכרון ל-Google Sheets, סיכומים וכו') יתבצע תמיד ברקע בלבד.
- אם יש עיכוב או תקלה — נשלחת למשתמש הודעת ביניים אוטומטית ("⏳ אני עובד על תשובה בשבילך...").
- כל שלב עיבוד נמדד, נרשם ללוגים, ואם יש חריגה — נשלחת התראה מפורטת לאדמין.

### 🧪 בדיקת CI ייעודית
- קיימת בדיקת CI שמוודאת שהתגובה הראשונית למשתמש תמיד מהירה, גם אם יש עיבוד איטי ברקע.
- כל שינוי בקוד עובר בדיקה זו — אם התגובה הראשונית איטית (למשל, בגלל עיבוד איטי או קריאה חיצונית לפני שליחת תשובה), ה־CI ייכשל והקוד לא יעלה לייצור.
- כך מובטח שהמשתמש לעולם לא יחכה זמן רב לתגובה, גם אם יש עומס או תקלות חיצוניות.

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:** שימוש ב-GPT
- **`data/bot_trace_log.jsonl`:** מעקב אירועים

---

## 🎛️ בדיקת מצב הלוגים

**פקודה פשוטה:**

```bash
# הצגת מצב נוכחי
python utils.py log-status
```

**דוגמת תפוקה:**
```
🎛️  מצב הלוגים הנוכחי:
========================================
📊 רמת לוג כללית:     INFO
🐛 דיבאג כללי:        ❌
💰 עלויות GPT:        ✅
📋 חילוץ נתונים:      ✅
⏱️  ביצועים:           ✅
💬 הודעות:            ✅
📊 גיליונות:          ❌
========================================
💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה
```

### 🔧 עקיפה עם משתני סביבה

```bash
# Windows PowerShell
$env:ENABLE_GPT_COST_DEBUG="false"; python main.py

# Linux/Mac
ENABLE_GPT_COST_DEBUG=false python main.py

# הגדרה קבועה במשתני הסביבה של המערכת
export ENABLE_DATA_EXTRACTION_DEBUG=true
```

### 📁 קבצי לוג:
- **קונסול:** פלט מבוקר למסך
- **`data/bot.log`:** לוג מרכזי
- **`data/gpt_usage_log.jsonl`:**