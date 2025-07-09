#!/usr/bin/env python3
"""
יצירת GPT Log HTML פשוט ללא תלות במסד נתונים
"""
import os
import json
from datetime import datetime

def create_sample_gpt_log():
    """יצירת דוגמת GPT log עם נתונים מדומים"""
    
    # נתוני דוגמה
    sample_data = [
        {
            "ts": "2025-07-06T15:00:00.000000Z",
            "gpt_type": "A",
            "cost_usd": 0.002,
            "request": {
                "model": "gpt-4o-2024-08-06",
                "messages": [
                    {"role": "system", "content": "אתה עוזר אישי ידידותי ומועיל שמתמחה בעזרה בעברית."},
                    {"role": "user", "content": "מה השעה עכשיו?"}
                ]
            },
            "response": {
                "id": "chatcmpl-example-1",
                "choices": [{"message": {"content": "אני לא יכול לראות את השעה הנוכחית, אבל אני יכול לעזור לך עם שאלות אחרות! 😊"}}],
                "usage": {
                    "prompt_tokens": 45,
                    "completion_tokens": 25,
                    "total_tokens": 70
                }
            },
            "formatted_message": "אני לא יכול לראות את השעה הנוכחית, אבל אני יכול לעזור לך עם שאלות אחרות! 😊"
        },
        {
            "ts": "2025-07-06T15:01:30.000000Z",
            "gpt_type": "B",
            "cost_usd": 0.0015,
            "request": {
                "model": "gpt-4o-2024-08-06",
                "messages": [
                    {"role": "system", "content": "אתה מומחה לסיכום טקסטים."},
                    {"role": "user", "content": "תסכם לי את הטקסט הזה: הבוט עובד מצוין והמשתמשים מרוצים מהשירות."}
                ]
            },
            "response": {
                "id": "chatcmpl-example-2",
                "choices": [{"message": {"content": "סיכום: הבוט פועל בהצלחה ומספק שירות איכותי למשתמשים."}}],
                "usage": {
                    "prompt_tokens": 35,
                    "completion_tokens": 18,
                    "total_tokens": 53
                }
            },
            "formatted_message": "סיכום: הבוט פועל בהצלחה ומספק שירות איכותי למשתמשים."
        },
        {
            "ts": "2025-07-06T15:02:15.000000Z",
            "gpt_type": "C",
            "cost_usd": 0.001,
            "request": {
                "model": "gpt-4o-2024-08-06",
                "messages": [
                    {"role": "system", "content": "אתה מומחה לחילוץ מידע ממשתמשים."},
                    {"role": "user", "content": "שמי דני, אני בן 25 ואני גר בתל אביב."}
                ]
            },
            "response": {
                "id": "chatcmpl-example-3",
                "choices": [{"message": {"content": '{"name": "דני", "age": "25", "location": "תל אביב"}'}}],
                "usage": {
                    "prompt_tokens": 40,
                    "completion_tokens": 15,
                    "total_tokens": 55
                }
            },
            "formatted_message": '{"name": "דני", "age": "25", "location": "תל אביב"}'
        },
        {
            "ts": "2025-07-06T15:03:00.000000Z",
            "gpt_type": "D",
            "cost_usd": 0.0008,
            "request": {
                "model": "gpt-4o-2024-08-06",
                "messages": [
                    {"role": "system", "content": "אתה מומחה למיזוג פרופילי משתמשים."},
                    {"role": "user", "content": "מזג את הפרופילים: {name: דני, age: 25} + {location: תל אביב, hobby: קריאה}"}
                ]
            },
            "response": {
                "id": "chatcmpl-example-4",
                "choices": [{"message": {"content": '{"name": "דני", "age": "25", "location": "תל אביב", "hobby": "קריאה"}'}}],
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 20,
                    "total_tokens": 70
                }
            },
            "formatted_message": '{"name": "דני", "age": "25", "location": "תל אביב", "hobby": "קריאה"}'
        }
    ]
    
    # יצירת HTML
    html_content = create_html_from_data(sample_data)
    
    # שמירה לקובץ
    os.makedirs("data", exist_ok=True)
    output_path = "data/gpt_log.html"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"✅ נוצר קובץ GPT Log: {output_path}")
    print(f"📊 מכיל {len(sample_data)} רשומות דוגמה")
    print(f"🌐 פתח את הקובץ בדפדפן כדי לראות את הלוגים")

def create_html_from_data(data):
    """יצירת HTML מנתוני GPT"""
    
    # html_escape moved to utils.py to prevent duplication
    from utils import html_escape
    
    def format_datetime(ts_iso):
        try:
            dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%y %H:%M")
        except ValueError:
            return ts_iso
    
    def render_messages_table(messages):
        rows = ["<tr><th>תפקיד</th><th>תוכן</th></tr>"]
        for m in messages:
            role = html_escape(m.get("role", ""))
            content = html_escape(m.get("content", "")).replace("\n", "<br>")
            rows.append(f"<tr><td>{role}</td><td>{content}</td></tr>")
        return '<table class="messages-table">' + "\n".join(rows) + "</table>"
    
    def render_entry(idx, rec):
        ts_fmt = format_datetime(rec["ts"])
        cost_agorot = int(round(rec["cost_usd"] * 3.7 * 100))
        
        usage = rec.get("response", {}).get("usage", {})
        prompt_toks = usage.get("prompt_tokens", 0)
        completion_toks = usage.get("completion_tokens", 0)
        total_toks = usage.get("total_tokens", 0)
        
        model = rec.get("request", {}).get("model", "unknown")
        gpt_type = rec["gpt_type"]
        
        req_id = f"req{idx}"
        res_id = f"res{idx}"
        
        messages = rec.get("request", {}).get("messages", [])
        messages_html = render_messages_table(messages)
        
        request_block = f"""
        <table class="content-table">
          <tr><th>מודל</th><td>{html_escape(model)}</td></tr>
          <tr><th colspan="2">הודעות</th></tr>
          <tr><td colspan="2">{messages_html}</td></tr>
        </table>"""
        
        answer = html_escape(rec.get("formatted_message", "")).replace("\n", "<br>")
        
        response_block = f"""
        <table class="content-table">
          <tr><th>מודל</th><td>{html_escape(model)}</td></tr>
          <tr><th>טוקני בקשה</th><td>{prompt_toks}</td></tr>
          <tr><th>טוקני תשובה</th><td>{completion_toks}</td></tr>
          <tr><th>סך טוקנים</th><td>{total_toks}</td></tr>
          <tr><th>תוכן התשובה</th><td>{answer}</td></tr>
        </table>"""
        
        return f"""
<div class="entry gpt{gpt_type}">
  <table class="entry-table">
    <tr>
      <td class="content-cell">
        <div class="meta">
          <b>זמן:</b> {ts_fmt} |
          <b>עלות:</b> <span class="cost">{cost_agorot} אגורות</span> |
          <b>מודל:</b> {html_escape(model)} |
          <b>טוקנים:</b> {total_toks} (prompt: {prompt_toks}, completion: {completion_toks})
        </div>
        <button class="button" onclick="toggle('{req_id}')">▶ בקשה</button>
        <div id="{req_id}" style="display:none;">{request_block}</div>
        <button class="button" onclick="toggle('{res_id}')">▶ תשובה</button>
        <div id="{res_id}" style="display:none;">{response_block}</div>
      </td>
      <td class="gpt-cell gpt{gpt_type}">G<br>P<br>T<br>{gpt_type}</td>
    </tr>
  </table>
</div>"""
    
    # יצירת HTML מלא
    entries_html = [render_entry(idx, rec) for idx, rec in enumerate(data)]
    
    html_template = """<!DOCTYPE html>
<html lang="he">
<head>
    <meta charset="UTF-8">
    <title>GPT Log Viewer</title>
    <style>
        body { font-family: sans-serif; direction: rtl; padding: 20px; background: #f9f9f9 }
        .entry { border: 1px solid #ccc; margin-bottom: 15px; border-radius: 6px; }
        .entry.gptA { background: #fff9f5; }
        .entry.gptB { background: #f8fbff; }
        .entry.gptC { background: #faf8ff; }
        .entry.gptD { background: #f8fff8; }
        .entry-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
        .entry-table td { vertical-align: middle; }
        .content-cell { padding: 10px; width: calc(100% - 25px); }
        .gpt-cell { width: 25px; text-align: center; font-size: 0.6em; font-weight: bold; padding: 15px 5px; border-left: 2px solid #ccc; line-height: 1.3; vertical-align: middle; }
        .gpt-cell.gptA { background: #fff0e6; color: #8b5a2b; border-left-color: #d4a574; }
        .gpt-cell.gptB { background: #eef7ff; color: #4682b4; border-left-color: #87ceeb; }
        .gpt-cell.gptC { background: #f3eeff; color: #8a2be2; border-left-color: #dda0dd; }
        .gpt-cell.gptD { background: #efffef; color: #228b22; border-left-color: #90ee90; }
        .meta { font-size: 0.9em; color: #666 }
        .button { cursor: pointer; color: blue; text-decoration: underline; border: none; background: none; font-size: 0.9em; margin: 2px; }
        .cost { color: #0066cc; font-weight: bold; }
        .content-table { border-collapse: collapse; width: 100%; margin-top: 10px; background: #fff; }
        .content-table th, .content-table td { border: 1px solid #ddd; padding: 8px; text-align: right; }
        .content-table th { background: #f5f5f5; font-weight: bold; width: 120px; }
        .content-table td { word-break: break-word; }
        .messages-table { border-collapse: collapse; width: 100%; margin: 5px 0; }
        .messages-table th, .messages-table td { border: 1px solid #ddd; padding: 6px; text-align: right; font-size: 0.85em; }
        .messages-table th { background: #f9f9f9; }
        .legend { margin-top: 30px; padding: 15px; background: #f5f5f5; border-radius: 6px; border: 1px solid #ddd; }
        .legend h3 { margin-top: 0; color: #333; }
        .legend-item { display: inline-block; margin: 5px 10px; }
        .legend-color { width: 20px; height: 15px; display: inline-block; margin-left: 5px; vertical-align: middle; border-radius: 3px; }
    </style>
    <script>
        function toggle(id) {
            var e = document.getElementById(id);
            e.style.display = e.style.display === 'none' ? 'block' : 'none';
        }
    </script>
</head>
<body>
    <h2>GPT Log Viewer - נתוני דוגמה</h2>
    <p style="background: #fff3cd; padding: 10px; border-radius: 5px; border: 1px solid #ffeaa7;">
        🔍 <strong>זהו לוג דוגמה</strong> - בפריסה בRender יהיו כאן נתונים אמיתיים מהמסד נתונים
    </p>
    
    {entries}
    
    <div class="legend">
        <h3>מקרא וצבעי GPT</h3>
        <div class="legend-item">GPTA <span class="legend-color" style="background: #fff0e6; border: 1px solid #d4a574;"></span> - תגובות ראשיות</div>
        <div class="legend-item">GPTB <span class="legend-color" style="background: #eef7ff; border: 1px solid #87ceeb;"></span> - סיכומים</div>
        <div class="legend-item">GPTC <span class="legend-color" style="background: #f3eeff; border: 1px solid #dda0dd;"></span> - חילוץ מידע</div>
        <div class="legend-item">GPTD <span class="legend-color" style="background: #efffef; border: 1px solid #90ee90;"></span> - מיזוג פרופילים</div>
    </div>
</body>
</html>"""
    
    return html_template.format(entries="\n".join(entries_html))

if __name__ == "__main__":
    create_sample_gpt_log() 