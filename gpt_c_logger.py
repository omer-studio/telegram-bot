"""
gpt_c_logger.py
---------------
קובץ זה אחראי על יצירת לוג HTML של כל עדכוני gpt_c (חילוץ תעודת זהות רגשית).
הלוג נשמר בקובץ HTML עם עיצוב יפה וניתן לצפייה בדפדפן.
"""

import os
import json
from utils import get_israel_time
from typing import Optional
from config import DATA_DIR


def append_gpt_c_html_update(
    old_summary: str,
    user_message: str,
    new_summary: str,
    extracted_data: dict,
    cost_agorot: Optional[float] = None,
    model_name: str = "gpt-4.1-nano",
    chat_id: Optional[str] = None,
    message_id: Optional[str] = None
):
    """
    מוסיף עדכון חדש ללוג HTML של gpt_c.
    
    Args:
        old_summary: הסיכום הישן
        user_message: הודעת המשתמש
        new_summary: הסיכום החדש
        extracted_data: הנתונים שחולצו
        cost_agorot: עלות באגורות
        model_name: שם המודל
        chat_id: מזהה הצ'אט
        message_id: מזהה ההודעה
    """
    html_file = os.path.join(DATA_DIR, "gpt_c_results.html")
    # התיקייה data תמיד קיימת לפי דרישת המשתמש
    
    # יצירת תוכן HTML חדש
    timestamp = get_israel_time().strftime("%Y-%m-%d %H:%M:%S")
    
    # המרת הנתונים ל-JSON יפה
    extracted_json = json.dumps(extracted_data, ensure_ascii=False, indent=2)
    
    # יצירת כרטיסיה חדשה
    new_entry = f"""
    <div class="gpt_c-entry">
        <div class="gpt_c-header-entry">
            <span class="gpt_c-timestamp">{timestamp}</span>
            <span class="gpt_c-model">{model_name}</span>
            {f'<span class="gpt_c-chat-id">Chat: {chat_id}</span>' if chat_id else ''}
            {f'<span class="gpt_c-msg-id">Msg: {message_id}</span>' if message_id else ''}
            {f'<span class="gpt_c-cost">{cost_agorot:.2f} אגורות</span>' if cost_agorot is not None else ''}
        </div>
        <div class="gpt_c-content">
            <div class="gpt_c-section">
                <h4>הודעת המשתמש:</h4>
                <p class="gpt_c-user-msg">{user_message}</p>
            </div>
            <div class="gpt_c-section">
                <h4>סיכום ישן:</h4>
                <p class="gpt_c-old-summary">{old_summary if old_summary else "אין סיכום קודם"}</p>
            </div>
            <div class="gpt_c-section">
                <h4>סיכום חדש:</h4>
                <p class="gpt_c-new-summary">{new_summary if new_summary else "לא נוצר סיכום חדש"}</p>
            </div>
            <div class="gpt_c-section">
                <h4>נתונים שחולצו:</h4>
                <pre class="gpt_c-extracted-data">{extracted_json}</pre>
            </div>
        </div>
    </div>
    """
    
    # קריאת התוכן הקיים או יצירת קובץ חדש
    if os.path.exists(html_file):
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>gpt_c Updates Log</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            direction: rtl;
        }}
        .gpt_c-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }}
        .gpt_c-clear-btn {{
            background: #ff4757;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        .gpt_c-clear-btn:hover {{
            background: #ff3742;
        }}
        .gpt_c-entry {{
            background: white;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .gpt_c-header-entry {{
            background: #f8f9fa;
            padding: 15px;
            border-bottom: 1px solid #e9ecef;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
        }}
        .gpt_c-timestamp {{
            background: #007bff;
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: bold;
        }}
        .gpt_c-model {{
            background: #28a745;
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
        }}
        .gpt_c-chat-id {{
            background: #ffc107;
            color: #212529;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
        }}
        .gpt_c-msg-id {{
            background: #17a2b8;
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
        }}
        .gpt_c-cost {{
            background: #dc3545;
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: bold;
        }}
        .gpt_c-content {{
            padding: 20px;
        }}
        .gpt_c-section {{
            margin-bottom: 20px;
        }}
        .gpt_c-section h4 {{
            color: #495057;
            margin-bottom: 10px;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 5px;
        }}
        .gpt_c-user-msg {{
            background: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            border-right: 4px solid #2196f3;
            margin: 0;
        }}
        .gpt_c-old-summary {{
            background: #fff3e0;
            padding: 15px;
            border-radius: 5px;
            border-right: 4px solid #ff9800;
            margin: 0;
        }}
        .gpt_c-new-summary {{
            background: #e8f5e8;
            padding: 15px;
            border-radius: 5px;
            border-right: 4px solid #4caf50;
            margin: 0;
        }}
        .gpt_c-extracted-data {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #dee2e6;
            overflow-x: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            white-space: pre-wrap;
        }}
        .gpt_c-log {{
            max-width: 1200px;
            margin: 0 auto;
        }}
    </style>
    <script>
    function clearGptCLog() {{
        if (confirm('האם אתה בטוח שברצונך למחוק את כל ההיסטוריה?')) {{
            fetch(window.location.pathname + '?clear=1', {{ method: 'POST' }}).then(() => window.location.reload());
        }}
    }}
    </script>
</head>
<body>
    <div class="gpt_c-header">
        <button class="gpt_c-clear-btn" onclick="clearGptCLog()">נקה הכל</button>
        <h2>gpt_c Updates Log</h2>
        <p>היסטוריית עדכונים של כל סיכומי gpt_c. כל עדכון נשמר ככרטיסיה חדשה.</p>
    </div>
    <div class="gpt_c-log">
        <!-- כאן יוכנסו העדכונים -->
    </div>
</body>
</html>
        """
    
    # הכנסת העדכון החדש בתחילת הקובץ (אחרי הכותרת)
    if "<!-- כאן יוכנסו העדכונים -->" in content:
        new_content = content.replace("<!-- כאן יוכנסו העדכונים -->", new_entry + "\n        <!-- כאן יוכנסו העדכונים -->")
    else:
        # אם אין תגית הכנסה, נכניס בתחילת ה-div
        new_content = content.replace('<div class="gpt_c-log">', f'<div class="gpt_c-log">\n        {new_entry}')
    
    # כתיבה לקובץ
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(new_content) 

def clear_gpt_c_html_log():
    """
    מנקה את כל העדכונים מהלוג HTML, משאיר רק את הכותרת.
    """
    html_file = os.path.join(DATA_DIR, "gpt_c_results.html")
    if not os.path.exists(html_file):
        return
    
    # קריאת התוכן הקיים
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # ניקוי כל העדכונים, השארת הכותרת בלבד
    if "<!-- כאן יוכנסו העדכונים -->" in content:
        # מצא את המיקום של תגית ההכנסה
        insert_pos = content.find("<!-- כאן יוכנסו העדכונים -->")
        # חתוך עד לתגית ההכנסה
        header_content = content[:insert_pos + len("<!-- כאן יוכנסו העדכונים -->")]
        # הוסף את התגית הסוגרת
        new_content = header_content + "\n    </div>\n</body>\n</html>"
    else:
        # אם אין תגית הכנסה, נחזור לתבנית הבסיסית
        new_content = f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>gpt_c Updates Log</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            direction: rtl;
        }}
        .gpt_c-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }}
        .gpt_c-clear-btn {{
            background: #ff4757;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        .gpt_c-clear-btn:hover {{
            background: #ff3742;
        }}
        .gpt_c-log {{
            max-width: 1200px;
            margin: 0 auto;
        }}
    </style>
    <script>
    function clearGptCLog() {{
        if (confirm('האם אתה בטוח שברצונך למחוק את כל ההיסטוריה?')) {{
            fetch(window.location.pathname + '?clear=1', {{ method: 'POST' }}).then(() => window.location.reload());
        }}
    }}
    </script>
</head>
<body>
    <div class="gpt_c-header">
        <button class="gpt_c-clear-btn" onclick="clearGptCLog()">נקה הכל</button>
        <h2>gpt_c Updates Log</h2>
        <p>היסטוריית עדכונים של כל סיכומי gpt_c. כל עדכון נשמר ככרטיסיה חדשה.</p>
    </div>
    <div class="gpt_c-log">
        <!-- כאן יוכנסו העדכונים -->
    </div>
</body>
</html>
        """
    
    # כתיבה לקובץ
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(new_content) 

 