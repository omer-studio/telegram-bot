#!/usr/bin/env python3
"""
הוספת דיבאג לחיפוש מדוע היסטוריה לא נטענת
"""
import sys
import os

def add_debug_to_chat_utils():
    """מוסיף דיבאג ל-chat_utils.py"""
    
    chat_utils_file = "chat_utils.py"
    
    # קריאת הקובץ הנוכחי
    with open(chat_utils_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # חיפוש הפונקציה get_chat_history_messages_fast
    target_function = "def get_chat_history_messages_fast("
    
    if target_function not in content:
        print("❌ לא נמצאה הפונקציה get_chat_history_messages_fast")
        return
    
    # הוספת דיבאג לתחילת הפונקציה
    new_debug_line = """    # 🔍 DEBUG: הוספת דיבאג מפורט
    import traceback
    print(f"[HISTORY_DEBUG] get_chat_history_messages_fast נקראה עבור chat_id={chat_id}")
    print(f"[HISTORY_DEBUG] stack trace: {''.join(traceback.format_stack()[-3:-1])}")
    
"""
    
    # מציאת המקום להוספת הדיבאג (אחרי השורה הראשונה של הפונקציה)
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        if target_function in line:
            # מוצא את השורה הראשונה אחרי הפונקציה שמתחילה ב-try:
            for j in range(i+1, len(lines)):
                if lines[j].strip() == "try:":
                    # מוסיף את הדיבאג אחרי try:
                    lines.insert(j+1, new_debug_line)
                    break
            break
    
    # כתיבה חזרה לקובץ
    new_content = '\n'.join(lines)
    
    # יצירת גיבוי
    backup_file = f"{chat_utils_file}.backup"
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # כתיבת הקובץ החדש
    with open(chat_utils_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ נוסף דיבאג ל-{chat_utils_file}")
    print(f"📁 גיבוי נשמר ב-{backup_file}")

def restore_chat_utils():
    """משחזר את chat_utils.py מהגיבוי"""
    
    chat_utils_file = "chat_utils.py"
    backup_file = f"{chat_utils_file}.backup"
    
    if not os.path.exists(backup_file):
        print("❌ לא נמצא קובץ גיבוי")
        return
    
    # שחזור מהגיבוי
    with open(backup_file, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    with open(chat_utils_file, 'w', encoding='utf-8') as f:
        f.write(original_content)
    
    # מחיקת הגיבוי
    os.remove(backup_file)
    
    print(f"✅ שוחזר {chat_utils_file} מהגיבוי")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_chat_utils()
    else:
        add_debug_to_chat_utils()
        print("\n🚀 כעת הרץ את הבוט ושלח הודעה מהמשתמש 111709341")
        print("🔍 בדוק את הלוגים לראות מה קורה עם טעינת ההיסטוריה")
        print("📝 להסרת הדיבאג: python debug_live_history.py restore") 