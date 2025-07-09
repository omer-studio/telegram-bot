# מדריך לתרומה לקוד

## 🚨 כללי ברזל - אל תפר!

### 1. טיפוסים בטוחים
❌ אסור:
```python
chat_id = update.message.chat_id  # לא בטוח!
user_id = user.id  # לא בטוח!
```

✅ מותר:
```python
from user_friendly_errors import safe_str
chat_id = safe_str(update.message.chat_id)
user_id = safe_str(user.id)
```

### 2. מסד נתונים
❌ אסור:
```python
import psycopg2
conn = psycopg2.connect(DB_URL)
```

✅ מותר:
```python
from simple_data_manager import data_manager
data_manager.save_chat_message(...)
```

### 3. לוגים
❌ אסור:
```python
import logging
logging.info("הודעה")
```

✅ מותר:
```python
from simple_logger import logger
logger.info("הודעה", source="module_name")
```

### 4. שגיאות
❌ אסור:
```python
raise Exception("שגיאה")
```

✅ מותר:
```python
from user_friendly_errors import UserFriendlyError
raise UserFriendlyError("הודעה ידידותית למשתמש")
```

## 🔍 בדיקות אוטומטיות
הרץ לפני כל קומיט:
```bash
python code_enforcement.py
```

## 📞 תמיכה
אם יש שאלות - פנה למפתח הראשי
