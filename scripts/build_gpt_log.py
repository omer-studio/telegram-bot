import os
import json
from collections import deque
from datetime import datetime
from typing import Any, Dict, List
from argparse import ArgumentParser
import sys
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

# הוספת נתיב לקובץ הקונפיגורציה
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# -----------------------------------------------------------------------------
# Configuration – single source of truth (avoids duplication across the script)
# -----------------------------------------------------------------------------
HTML_OUT_PATH = os.path.join("data", "gpt_log.html")
MAX_LINES = 100  # number of recent calls to display
USD_TO_ILS = 3.7  # rough conversion; update in a single place if needed

# Google Drive upload configuration (optional)
DRIVE_FOLDER_ID = "1TdmdXbjOcarkWksddq5KlFlu6ZhSnWax"  # single source of truth
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

# -----------------------------------------------------------------------------
# Helper utilities (isolated, side-effect free)
# -----------------------------------------------------------------------------

def get_gpt_calls_from_sql(limit: int = MAX_LINES) -> List[Dict[str, Any]]:
    """קריאת נתוני GPT מ-SQL או מקבצי JSONL (fallback)."""
    
    # ניסיון קריאה מ-SQL
    try:
        from config import config
        import os
        
        # חיבור למסד הנתונים עם DATABASE_EXTERNAL_URL לחיבור מהמחשב המקומי
        database_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        connection = psycopg2.connect(database_url)
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # שאילתה לקריאת הנתונים האחרונים מטבלה gpt_calls_log
        query = """
        SELECT 
            timestamp as created_at,
            call_type as gpt_type,
            request_data,
            response_data,
            tokens_input,
            tokens_output,
            cost_usd,
            chat_id,
            processing_time_seconds
        FROM gpt_calls_log
        ORDER BY timestamp DESC
        LIMIT %s
        """
        
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        
        # המרת התוצאות למבנה הנדרש
        results = []
        for row in rows:
            # פירוק נתוני request/response JSON
            request_data = row.get('request_data', {})
            response_data = row.get('response_data', {})
            
            # חילוץ מודל מ-request_data
            model = request_data.get('model', 'unknown-model') if isinstance(request_data, dict) else 'unknown-model'
            
            # חילוץ הודעות מ-request_data
            messages = request_data.get('messages', []) if isinstance(request_data, dict) else []
            
            # חילוץ תוכן התשובה
            response_content = ""
            if isinstance(response_data, dict):
                choices = response_data.get('choices', [])
                if choices and len(choices) > 0:
                    message = choices[0].get('message', {})
                    response_content = message.get('content', '')
            
            # בניית המבנה הנדרש
            entry = {
                "ts": row['created_at'].isoformat() + "Z",
                "gpt_type": row['gpt_type'],
                "cost_usd": float(row['cost_usd']) if row['cost_usd'] else 0.0,
                "request": {
                    "model": model,
                    "messages": messages
                },
                "response": {
                    "id": response_data.get('id', 'unknown') if isinstance(response_data, dict) else 'unknown',
                    "choices": [{"message": {"content": response_content}}],
                    "usage": {
                        "prompt_tokens": int(row['tokens_input']) if row['tokens_input'] else 0,
                        "completion_tokens": int(row['tokens_output']) if row['tokens_output'] else 0,
                        "total_tokens": int(row['tokens_input'] or 0) + int(row['tokens_output'] or 0)
                    }
                },
                "formatted_message": response_content
            }
            results.append(entry)
        
        cursor.close()
        connection.close()
        
        print(f"✅ קרא {len(results)} רשומות מ-SQL")
        return results
        
    except Exception as e:
        print(f"⚠️  שגיאה בקריאה מ-SQL: {e}")
        print("🔄 מנסה לקרוא מקבצי JSONL...")
        
        # Fallback לקבצי JSONL
        try:
            jsonl_paths = [
                "data/openai_calls.jsonl",
                "server_data/openai_calls.jsonl",
                "openai_calls.jsonl"
            ]
            
            results = []
            for path in jsonl_paths:
                if os.path.exists(path):
                    print(f"📂 נמצא קובץ JSONL: {path}")
                    lines = tail_lines(path, limit)
                    for line in lines:
                        try:
                            entry = json.loads(line.strip())
                            results.append(entry)
                        except json.JSONDecodeError:
                            continue
                    break
            
            if results:
                print(f"✅ קרא {len(results)} רשומות מקבצי JSONL")
                return results[:limit]
            else:
                print("⚠️ לא נמצאו קבצי JSONL")
                
        except Exception as jsonl_e:
            print(f"⚠️ שגיאה בקריאת JSONL: {jsonl_e}")
        
        print("🔄 יצירת נתוני דוגמה...")
        return []

def tail_lines(path: str, n: int) -> List[str]:
    """Return up to *n* last lines from *path* efficiently (without full read)."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return list(deque(fh, maxlen=n))


def fmt_datetime(ts_iso: str) -> str:
    """Convert ISO timestamp → `DD/MM/YY HH:MM` (UTC assumed)."""
    try:
        dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%y %H:%M")
    except ValueError:
        return ts_iso  # fallback to original


def get(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Safely fetch a nested key using dot-notation (e.g. 'response.usage.total_tokens')."""
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                idx = int(part.strip("[]"))
                cur = cur[idx]
            except (ValueError, IndexError):
                return default
        elif isinstance(cur, dict):
            cur = cur.get(part, default)
        else:
            return default
    return cur


# -----------------------------------------------------------------------------
# HTML generation helpers
# -----------------------------------------------------------------------------

def html_escape(text: str) -> str:
    """Minimal HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_messages_table(messages: List[Dict[str, str]]) -> str:
    """Render list[ {role, content} ] to inner HTML table string."""
    rows = [
        "<tr><th>תפקיד</th><th>תוכן</th></tr>"
    ]
    for m in messages:
        role = html_escape(str(m.get("role", "")))
        content = html_escape(str(m.get("content", ""))).replace("\n", "<br>")
        rows.append(f"<tr><td>{role}</td><td>{content}</td></tr>")
    return (
        '<table class="messages-table">' + "\n".join(rows) + "</table>"
    )


def render_entry(idx: int, rec: Dict[str, Any]) -> str:
    """Return full HTML `<div class="entry …">…` for a single record."""

    ts_fmt = fmt_datetime(rec["ts"])
    cost_agorot = int(round(rec["cost_usd"] * USD_TO_ILS * 100))

    usage: Dict[str, int] = get(rec, "response.usage", {}) or {}
    prompt_toks = int(usage.get("prompt_tokens", 0))
    completion_toks = int(usage.get("completion_tokens", 0))
    total_toks = int(usage.get("total_tokens", 0))
    cached_toks = max(total_toks - prompt_toks - completion_toks, 0)

    model = get(rec, "request.model", "unknown-model")
    gpt_type = rec["gpt_type"]  # mandatory per spec (A/B/C/D)

    # Unique IDs per entry for toggles
    req_id = f"req{idx}"
    res_id = f"res{idx}"

    # Request messages table
    messages = get(rec, "request.messages", [])
    messages_html = render_messages_table(messages)

    request_block = f"""
    <table class=\"content-table\">
      <tr><th>מודל</th><td>{html_escape(model)}</td></tr>
      <tr><th colspan=\"2\">הודעות</th></tr>
      <tr><td colspan=\"2\">{messages_html}</td></tr>
    </table>"""

    # Response block
    resp_id = html_escape(get(rec, "response.id", ""))
    answer = html_escape(
        get(rec, "response.choices[0].message.content", "").replace("\n", "<br>")
    )
    formatted_msg = get(rec, "formatted_message")
    formatted_html = (
        f'<div class="telegram-message">{html_escape(formatted_msg)}</div>'
        if formatted_msg
        else ""
    )

    response_rows = [
        ("מזהה", resp_id),
        ("מודל", html_escape(model)),
        ("טוקני בקשה", str(prompt_toks)),
        ("טוקני תשובה", str(completion_toks)),
        ("טוקני cache", str(cached_toks)),
        ("סך טוקנים", str(total_toks)),
    ]
    response_rows_html = "\n".join(
        f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in response_rows if v
    )
    
    # הוסף את תוכן התשובה בנפרד
    answer_content = ""
    if answer:
        answer_content += f"<tr><th>תוכן התשובה</th><td>{answer}</td></tr>"
    if formatted_html:
        answer_content += f"<tr><th>הודעה מעוצבת</th><td>{formatted_html}</td></tr>"
    response_block = (
        f"<table class=\"content-table\">{response_rows_html}{answer_content}</table>"
    )

    return f"""
<div class=\"entry gpt{gpt_type}\">
  <table class=\"entry-table\"> <tr>
    <td class=\"content-cell\">
      <div class=\"meta\">
        <b>זמן:</b> {ts_fmt} |
        <b>עלות:</b> <span class=\"cost\">{cost_agorot} אגורות</span> |
        <b>מודל:</b> {html_escape(model)} |
        <b>טוקנים:</b> {total_toks} (prompt: {prompt_toks}, completion: {completion_toks}, cached: {cached_toks})
      </div>
      <button class=\"button\" onclick=\"toggle('{req_id}')\">▶ בקשה</button>
      <button class=\"copy-button\" onclick=\"showJsonModal('JSON גולמי - בקשה', {json.dumps(rec['request'], ensure_ascii=False)})\">📋 העתק JSON גולמי</button>
      <div id=\"{req_id}\" style=\"display:none;\">{request_block}</div>
      <button class=\"button\" onclick=\"toggle('{res_id}')\">▶ תשובה</button>
      <button class=\"copy-button\" onclick=\"showJsonModal('JSON גולמי - תשובה', {json.dumps(rec['response'], ensure_ascii=False)})\">📋 העתק JSON גולמי</button>
      <div id=\"{res_id}\" style=\"display:none;\">{response_block}</div>
    </td>
    <td class=\"gpt-cell gpt{gpt_type}\">G<br>P<br>T<br>{gpt_type}</td>
  </tr></table>
</div>"""


# -----------------------------------------------------------------------------
# Main driver – minimal side-effects beyond writing HTML file
# -----------------------------------------------------------------------------

def build_html() -> None:
    # Ensure output directory exists
    os.makedirs(os.path.dirname(HTML_OUT_PATH) or ".", exist_ok=True)

    # קריאת נתונים מ-SQL במקום מקבצים 🚀
    print("📊 קריאת נתוני GPT מ-SQL...")
    sql_records = get_gpt_calls_from_sql(MAX_LINES)
    
    if not sql_records:
        print("⚠️  לא נמצאו נתונים ב-SQL, יצירת נתוני דוגמה...")
        sql_records = [
            {
                "ts": "2025-07-05T10:00:00.000000Z",
                "gpt_type": "A",
                "request": {
                    "model": "gpt-4o-2024-08-06",
                    "messages": [
                        {"role": "system", "content": "אתה עוזר אישי ידידותי ומועיל."},
                        {"role": "user", "content": "מה השעה עכשיו?"}
                    ]
                },
                "response": {
                    "id": "sample-1",
                    "choices": [{"message": {"content": "אני לא יכול לראות את השעה הנוכחית, אבל אני יכול לעזור לך עם שאלות אחרות! 😊"}}],
                    "usage": {"prompt_tokens": 25, "completion_tokens": 15, "total_tokens": 40}
                },
                "cost_usd": 0.001,
                "formatted_message": "אני לא יכול לראות את השעה הנוכחית, אבל אני יכול לעזור לך עם שאלות אחרות! 😊"
            },
            {
                "ts": "2025-07-05T10:01:00.000000Z",
                "gpt_type": "B",
                "request": {
                    "model": "gpt-4o-2024-08-06",
                    "messages": [
                        {"role": "system", "content": "אתה מומחה טכני."},
                        {"role": "user", "content": "איך אני מתקין Python?"}
                    ]
                },
                "response": {
                    "id": "sample-2",
                    "choices": [{"message": {"content": "כדי להתקין Python:\n1. הורד מהאתר הרשמי python.org\n2. הרץ את הקובץ המותקן\n3. סמן 'Add Python to PATH'\n4. לחץ Install"}}],
                    "usage": {"prompt_tokens": 30, "completion_tokens": 45, "total_tokens": 75}
                },
                "cost_usd": 0.002,
                "formatted_message": "כדי להתקין Python:\n1. הורד מהאתר הרשמי python.org\n2. הרץ את הקובץ המותקן\n3. סמן 'Add Python to PATH'\n4. לחץ Install"
            },
            {
                "ts": "2025-07-05T10:02:00.000000Z",
                "gpt_type": "C",
                "request": {
                    "model": "gpt-4o-2024-08-06",
                    "messages": [
                        {"role": "system", "content": "אתה עוזר יצירתי."},
                        {"role": "user", "content": "כתוב לי שיר קצר על הטכנולוגיה"}
                    ]
                },
                "response": {
                    "id": "sample-3",
                    "choices": [{"message": {"content": "במסכים זוהרים\nמילים מתעופפות\nהעתיד כבר כאן\nבכל לחיצה מתחדשת"}}],
                    "usage": {"prompt_tokens": 35, "completion_tokens": 25, "total_tokens": 60}
                },
                "cost_usd": 0.0015,
                "formatted_message": "במסכים זוהרים\nמילים מתעופפות\nהעתיד כבר כאן\nבכל לחיצה מתחדשת"
            }
        ]
    
    entries_html: List[str] = []
    for idx, rec in enumerate(sql_records):
        # Validation – mandatory fields
        mandatory_paths = [
            "ts",
            "cost_usd",
            "request.model",
            "request.messages",
            "response.usage.prompt_tokens",
            "response.usage.completion_tokens",
            "response.usage.total_tokens",
            "gpt_type",
        ]
        if not all(get(rec, p) for p in mandatory_paths):
            continue  # skip incomplete records

        try:
            entries_html.append(render_entry(idx, rec))
        except Exception:
            # Guard against any unexpected key errors; skip faulty record
            continue

    # ---------------------------------------------------------------------
    # Assemble final HTML document
    # ---------------------------------------------------------------------
    head_and_styles = """<!DOCTYPE html>
<html lang=\"he\"><head><meta charset=\"UTF-8\"><title>GPT Log Viewer</title>
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
        .copy-button { cursor: pointer; color: #0066cc; text-decoration: underline; border: none; background: none; font-size: 0.85em; margin: 2px; padding: 2px 6px; border-radius: 3px; }
        .copy-button:hover { background: #e6f3ff; }
        .cost { color: #0066cc; font-weight: bold; }
        .content-table { border-collapse: collapse; width: 100%; margin-top: 10px; background: #fff; }
        .content-table th, .content-table td { border: 1px solid #ddd; padding: 8px; text-align: right; }
        .content-table th { background: #f5f5f5; font-weight: bold; width: 120px; }
        .content-table td { word-break: break-word; }
        .messages-table { border-collapse: collapse; width: 100%; margin: 5px 0; table-layout: fixed; }
        .messages-table th, .messages-table td { border: 1px solid #ddd; padding: 6px; text-align: right; font-size: 0.85em; }
        .messages-table th { background: #f9f9f9; }
        .messages-table th:first-child, .messages-table td:first-child { width: 60px; max-width: 60px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .messages-table th:last-child, .messages-table td:last-child { width: calc(100% - 60px); }
        .messages-table tr:nth-child(even) { background: #fafafa; }
        .messages-table tr:nth-child(odd) { background: #fff; }
        .legend { margin-top: 30px; padding: 15px; background: #f5f5f5; border-radius: 6px; border: 1px solid #ddd; }
        .legend h3 { margin-top: 0; color: #333; }
        .legend-item { display: inline-block; margin: 5px 10px; }
        .legend-color { width: 20px; height: 15px; display: inline-block; margin-left: 5px; vertical-align: middle; border-radius: 3px; }
        .telegram-message { background: #dcf8c6; border-radius: 12px 12px 4px 12px; padding: 8px 12px; margin: 5px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; line-height: 1.35; max-width: 100%; word-wrap: break-word; color: #303030; position: relative; white-space: pre-line; }
        .telegram-message::after { content: ''; position: absolute; bottom: 0; right: -2px; width: 0; height: 0; border: 6px solid transparent; border-top-color: #dcf8c6; border-right: 0; transform: rotate(45deg); }
        .json-modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }
        .json-content { background-color: #fefefe; margin: 5% auto; padding: 20px; border: 1px solid #888; width: 90%; max-width: 800px; max-height: 80%; overflow-y: auto; border-radius: 8px; }
        .json-text { background: #f5f5f5; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; word-break: break-all; font-size: 12px; max-height: 400px; overflow-y: auto; }
        .close { color: #aaa; float: left; font-size: 28px; font-weight: bold; cursor: pointer; }
        .close:hover { color: #000; }
        .copy-success { color: green; font-size: 12px; margin-left: 10px; }
    </style>
    <script>
        function toggle(id){var e=document.getElementById(id);e.style.display=e.style.display==='none'?'block':'none';}
        
        function showJsonModal(title, jsonData) {
            var modal = document.getElementById('jsonModal');
            var modalTitle = document.getElementById('jsonModalTitle');
            var jsonText = document.getElementById('jsonText');
            
            modalTitle.textContent = title;
            jsonText.textContent = JSON.stringify(jsonData, null, 2);
            modal.style.display = 'block';
        }
        
        function closeJsonModal() {
            document.getElementById('jsonModal').style.display = 'none';
        }
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                // הצג הודעת הצלחה
                var copyBtn = event.target;
                var originalText = copyBtn.textContent;
                copyBtn.textContent = '✓ הועתק!';
                copyBtn.style.color = 'green';
                setTimeout(function() {
                    copyBtn.textContent = originalText;
                    copyBtn.style.color = '#0066cc';
                }, 2000);
            }).catch(function(err) {
                console.error('שגיאה בהעתקה: ', err);
                // נסה שיטה חלופית
                var textArea = document.createElement("textarea");
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.select();
                try {
                    document.execCommand('copy');
                    var copyBtn = event.target;
                    var originalText = copyBtn.textContent;
                    copyBtn.textContent = '✓ הועתק!';
                    copyBtn.style.color = 'green';
                    setTimeout(function() {
                        copyBtn.textContent = originalText;
                        copyBtn.style.color = '#0066cc';
                    }, 2000);
                } catch (err) {
                    alert('שגיאה בהעתקה. נסה שוב.');
                }
                document.body.removeChild(textArea);
            });
        }
        
        function copyJsonData(jsonData) {
            copyToClipboard(JSON.stringify(jsonData, null, 2));
        }
        
        // סגירת modal בלחיצה מחוץ לתוכן
        window.onclick = function(event) {
            var modal = document.getElementById('jsonModal');
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
    </script>
</head><body>
<h2>100 הקריאות האחרונות ל־GPT</h2>

<!-- JSON Modal -->
<div id="jsonModal" class="json-modal">
    <div class="json-content">
        <span class="close" onclick="closeJsonModal()">&times;</span>
        <h3 id="jsonModalTitle">JSON גולמי</h3>
        <button class="copy-button" onclick="copyToClipboard(document.getElementById('jsonText').textContent)">📋 העתק JSON</button>
        <div id="jsonText" class="json-text"></div>
    </div>
</div>"""

    legend = """
<div class=\"legend\">
  <h3>מקרא וצבעי GPT</h3>
  <div class=\"legend-item\">GPTA <span class=\"legend-color\" style=\"background: #fff0e6; border: 1px solid #d4a574;\"></span></div>
  <div class=\"legend-item\">GPTB <span class=\"legend-color\" style=\"background: #eef7ff; border: 1px solid #87ceeb;\"></span></div>
  <div class=\"legend-item\">GPTC <span class=\"legend-color\" style=\"background: #f3eeff; border: 1px solid #dda0dd;\"></span></div>
  <div class=\"legend-item\">GPTD <span class=\"legend-color\" style=\"background: #efffef; border: 1px solid #90ee90;\"></span></div>
</div>"""

    html_body = "\n".join(entries_html) if entries_html else "<p>No valid GPT log entries found.</p>"

    full_html = head_and_styles + html_body + legend + "</body></html>"

    with open(HTML_OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(full_html)
    print(f"✅ Wrote {HTML_OUT_PATH} with {len(entries_html)} entries.")
    
    # העלאה אוטומטית ל-Sheets
    try:
        upload_to_sheets(HTML_OUT_PATH)
    except Exception as e:
        print(f"⚠️  Auto-upload to Sheets failed: {e}")


# -----------------------------------------------------------------------------
# Optional: upload the generated HTML to Google Drive
# -----------------------------------------------------------------------------

def upload_to_drive(html_path: str, folder_id: str = DRIVE_FOLDER_ID) -> None:
    """Upload (or update) the HTML file in a specific Drive folder via service account creds from config.

    Requires SERVICE_ACCOUNT_DICT in config.py with the required scopes.
    """
    try:
        from googleapiclient.discovery import build  # type: ignore
        from googleapiclient.http import MediaFileUpload  # type: ignore
        from google.oauth2.service_account import Credentials  # type: ignore
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import SERVICE_ACCOUNT_DICT
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise SystemExit(
            "google-api-python-client not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        ) from exc
    except ImportError as exc:
        raise SystemExit(f"Failed to import SERVICE_ACCOUNT_DICT from config: {exc}")

    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_DICT, scopes=SCOPES)
    drive_service = build("drive", "v3", credentials=creds)

    file_name = os.path.basename(html_path)
    # Search for existing file in the folder
    response = (
        drive_service.files()
        .list(
            q=f"name='{file_name}' and '{folder_id}' in parents and mimeType='text/html'",
            spaces="drive",
            fields="files(id, name)",
        )
        .execute()
    )
    files = response.get("files", [])

    media = MediaFileUpload(html_path, mimetype="text/html", resumable=True)
    if files:
        file_id = files[0]["id"]
        drive_service.files().update(fileId=file_id, media_body=media).execute()
        print("☁️  Updated existing gpt_log.html in Drive.")
    else:
        metadata = {"name": file_name, "parents": [folder_id], "mimeType": "text/html"}
        file = (
            drive_service.files()
            .create(body=metadata, media_body=media, fields="id")
            .execute()
        )
        print(f"☁️  Uploaded new gpt_log.html to Drive (ID: {file.get('id')}).")


def upload_to_sheets(html_path: str) -> None:
    """Upload HTML content to Google Sheets for easy viewing and synchronization.
    
    Creates a new sheet with the HTML content formatted for easy reading.
    """
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import setup_google_sheets, SERVICE_ACCOUNT_DICT
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
    except ImportError as exc:
        raise SystemExit(f"Failed to import required modules: {exc}")

    try:
        # קרא את תוכן ה-HTML
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # הגדר את Google Sheets
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_DICT, scope)
        gs_client = gspread.authorize(creds)
        
        # שם הגיליון החדש
        sheet_name = f"GPT_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # צור גיליון חדש
        new_spreadsheet = gs_client.create(sheet_name)
        sheet_id = new_spreadsheet.id
        
        # הכנס את התוכן HTML כטקסט רגיל (ללא עיצוב)
        import re
        text_content = re.sub(r'<[^>]+>', '', html_content)
        text_content = re.sub(r'\s+', ' ', text_content).strip()
        
        # חלק את התוכן לשורות
        lines = text_content.split('.')
        
        # הכנס את השורות לגיליון
        worksheet = new_spreadsheet.sheet1
        data = []
        for i, line in enumerate(lines[:100]):  # הגבל ל-100 שורות
            if line.strip():
                data.append([f"שורה {i+1}", line.strip()])
        
        if data:
            worksheet.update('A1:B100', data)
        
        print(f"📊 Uploaded GPT log to Google Sheets: {sheet_name}")
        print(f"🔗 Sheet URL: https://docs.google.com/spreadsheets/d/{sheet_id}")
        
    except Exception as e:
        print(f"❌ Error uploading to Sheets: {e}")


def upload_jsonl_to_drive(jsonl_path: str, folder_id: str = DRIVE_FOLDER_ID) -> None:
    """Upload (or update) the JSONL file in a specific Drive folder.
    
    This allows real-time viewing of the raw GPT log data.
    """
    try:
        from googleapiclient.discovery import build  # type: ignore
        from googleapiclient.http import MediaFileUpload  # type: ignore
        from google.oauth2.service_account import Credentials  # type: ignore
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import SERVICE_ACCOUNT_DICT
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise SystemExit(
            "google-api-python-client not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        ) from exc
    except ImportError as exc:
        raise SystemExit(f"Failed to import SERVICE_ACCOUNT_DICT from config: {exc}")

    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_DICT, scopes=SCOPES)
    drive_service = build("drive", "v3", credentials=creds)

    file_name = os.path.basename(jsonl_path)
    # Search for existing file in the folder
    response = (
        drive_service.files()
        .list(
            q=f"name='{file_name}' and '{folder_id}' in parents and mimeType='application/json'",
            spaces="drive",
            fields="files(id, name)",
        )
        .execute()
    )
    files = response.get("files", [])

    media = MediaFileUpload(jsonl_path, mimetype="application/json", resumable=True)
    if files:
        file_id = files[0]["id"]
        drive_service.files().update(fileId=file_id, media_body=media).execute()
        print(f"📁 Updated existing {file_name} in Drive.")
    else:
        metadata = {"name": file_name, "parents": [folder_id], "mimeType": "application/json"}
        file = (
            drive_service.files()
            .create(body=metadata, media_body=media, fields="id")
            .execute()
        )
        print(f"📁 Uploaded new {file_name} to Drive (ID: {file.get('id')}).")


if __name__ == "__main__":
    parser = ArgumentParser(description="Build GPT HTML log from SQL database (and optionally upload to Drive/Sheets)")
    parser.add_argument("--upload", action="store_true", help="Also upload/update the HTML file on Google Drive")
    parser.add_argument("--sheets", action="store_true", help="Also upload HTML content to Google Sheets")
    args = parser.parse_args()

    build_html()
    if args.upload:
        upload_to_drive(HTML_OUT_PATH)
    if args.sheets:
        upload_to_sheets(HTML_OUT_PATH)