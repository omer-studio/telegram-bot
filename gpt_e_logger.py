import os
import json
from datetime import datetime
from typing import Dict, Any, Optional

# Try to import USD_TO_ILS from gpt_handler, fallback to 3.7 if not found
try:
    from gpt_handler import USD_TO_ILS
except Exception:
    USD_TO_ILS = 3.7


def append_gpt_e_html_update(
    old_summary: str,
    user_message: str,
    new_summary: str,
    tokens_used: Optional[int] = None,
    cost: Optional[float] = None,
    cost_ils: Optional[float] = None,
    cost_agorot: Optional[float] = None,
    model: Optional[str] = None
) -> None:
    """
    Append a GPT-E update to the HTML log file in the data directory.
    Keeps only the latest 100 updates.
    Creates the file and directory if they do not exist.
    Shows cost in agorot (אגורות) exactly as in the sheets, if provided.
    Always displays Old Summary (even if empty).
    Inserts new entry at the top, preserving all previous entries.
    """
    html_file = os.path.join("data", "gpt_e_results.html")
    # התיקייה data תמיד קיימת לפי דרישת המשתמש
    
    # Create the HTML entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if there's a change in the summary
    has_change = old_summary != new_summary
    
    # Format metadata
    metadata = []
    if tokens_used is not None:
        metadata.append(f"Tokens: {tokens_used}")
    if cost_agorot is not None:
        metadata.append(f"עלות באגורות: {cost_agorot:.2f}")
    elif cost_ils is not None:
        metadata.append(f"Cost: ₪{cost_ils:.3f}")
    elif cost is not None:
        metadata.append(f"Cost: ${cost:.4f}")
    if model is not None:
        metadata.append(f"Model: {model}")
    
    metadata_html = f"<div class='metadata'>{' | '.join(metadata)}</div>" if metadata else ""
    
    # Always show Old Summary, even if empty
    old_summary_html = old_summary if old_summary is not None else "<i>(empty)</i>"
    
    # Determine card styling based on whether there's a change
    if has_change:
        card_style = "width:85%;margin:18px auto;max-width:none;background:#fff3cd;border:2px solid #ffc107;box-shadow:0 4px 12px rgba(255,193,7,0.3);"
        new_summary_style = "background:#e8f5e8;border:2px solid #28a745;border-radius:5px;padding:5px 8px;font-size:1em;word-break:break-word;flex:1;font-weight:bold;"
    else:
        card_style = "width:85%;margin:18px auto;max-width:none;"
        new_summary_style = "background:#f2f4f8;border-radius:5px;padding:5px 8px;font-size:1em;word-break:break-word;flex:1;"
    
    # NEW: Improved card layout (wider, shorter, label+value on same row, 85% width)
    entry_html = f"""
    <div class=\"gpt-e-card\" style=\"{card_style}\">
        <div class=\"gpt-e-meta\">
            <span>{timestamp}</span>
            {metadata_html}
        </div>
        <div class=\"gpt-e-section-row\" style=\"display:flex;align-items:center;margin-bottom:4px;\"><span class=\"gpt-e-label\" style=\"min-width:110px;font-weight:bold;color:#4b5fc0;margin-right:8px;flex-shrink:0;\">Old Summary:</span><div class=\"gpt-e-summary\" style=\"background:#f2f4f8;border-radius:5px;padding:5px 8px;font-size:1em;word-break:break-word;flex:1;\">{old_summary_html}</div></div>
        <div class=\"gpt-e-section-row\" style=\"display:flex;align-items:center;margin-bottom:4px;\"><span class=\"gpt-e-label\" style=\"min-width:110px;font-weight:bold;color:#4b5fc0;margin-right:8px;flex-shrink:0;\">User Message:</span><div class=\"gpt-e-summary\" style=\"background:#f2f4f8;border-radius:5px;padding:5px 8px;font-size:1em;word-break:break-word;flex:1;\">{user_message}</div></div>
        <div class=\"gpt-e-section-row\" style=\"display:flex;align-items:center;margin-bottom:4px;\"><span class=\"gpt-e-label\" style=\"min-width:110px;font-weight:bold;color:#4b5fc0;margin-right:8px;flex-shrink:0;\">New Summary:</span><div class=\"gpt-e-summary\" style=\"{new_summary_style}\">{new_summary}</div></div>
    </div>
    """
    
    # If file does not exist, create with skeleton
    if not os.path.exists(html_file):
        html_content = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>GPT-E Updates Log</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 700px;
            margin: 0 auto;
            padding: 10px;
            background-color: #f7f7fa;
        }}
        .gpt-e-card {{
            background: #fff;
            border: 1px solid #d0d7e2;
            border-radius: 10px;
            margin: 18px auto;
            max-width: 600px;
            padding: 12px 16px;
            box-shadow: 0 2px 8px #0001;
        }}
        .gpt-e-meta {{
            font-size: 0.92em;
            color: #666;
            margin-bottom: 7px;
        }}
        .gpt-e-section-row {{
            display: flex;
            align-items: flex-start;
            margin-bottom: 7px;
        }}
        .gpt-e-label {{
            min-width: 110px;
            font-weight: bold;
            color: #4b5fc0;
            margin-right: 8px;
            flex-shrink: 0;
        }}
        .gpt-e-summary {{
            background: #f2f4f8;
            border-radius: 5px;
            padding: 5px 8px;
            font-size: 1em;
            word-break: break-word;
            flex: 1;
        }}
        .gpt-e-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 18px 18px 10px 18px;
            border-radius: 10px;
            margin-bottom: 18px;
            box-shadow: 0 2px 6px #0002;
            text-align: center;
            position: relative;
        }}
        .gpt-e-header h2 {{
            margin: 0;
            font-size: 2em;
            font-weight: 400;
        }}
        .gpt-e-header p {{
            margin: 8px 0 0 0;
            opacity: 0.93;
            font-size: 1em;
        }}
        .gpt-e-clear-btn {{
            position: absolute;
            top: 16px;
            left: 16px;
            background: #fff;
            color: #764ba2;
            border: none;
            border-radius: 6px;
            padding: 7px 16px;
            font-size: 1em;
            font-weight: 500;
            cursor: pointer;
            box-shadow: 0 1px 4px #0001;
            transition: background 0.2s, color 0.2s;
        }}
        .gpt-e-clear-btn:hover {{
            background: #f2f4f8;
            color: #667eea;
        }}
    </style>
    <script>
    function clearGptELog() {{
        if (confirm('האם אתה בטוח שברצונך למחוק את כל ההיסטוריה?')) {{
            fetch(window.location.pathname + '?clear=1', {{ method: 'POST' }}).then(() => window.location.reload());
        }}
    }}
    </script>
</head>
<body>
    <div class=\"gpt-e-header\">
        <button class=\"gpt-e-clear-btn\" onclick=\"clearGptELog()\">נקה הכל</button>
        <h2>GPT-E Updates Log</h2>
        <p>היסטוריית עדכונים של כל סיכומי GPT-E. כל עדכון נשמר ככרטיסיה חדשה.</p>
    </div>
    <div id=\"gpt-e-log\">
{entry_html}
    </div>
</body>
</html>"""
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return

    # If file exists, insert new entry after <div id="gpt-e-log">
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the insertion point
    insert_point = content.find('<div id="gpt-e-log">')
    if insert_point == -1:
        # fallback: just append at the end
        insert_point = len(content)
        before = content
        after = ''
    else:
        insert_point += len('<div id="gpt-e-log">')
        before = content[:insert_point]
        after = content[insert_point:]

    # Insert the new entry at the top
    new_content = before + '\n' + entry_html + after

    # Limit to 100 cards
    import re
    cards = re.findall(r'<div class=\\?"gpt-e-card\\?">.*?</div>', new_content, re.DOTALL)
    if len(cards) > 100:
        # Keep only the first 100
        # Remove all after the 100th
        split = new_content.split('<div id="gpt-e-log">', 1)
        if len(split) == 2:
            head, rest = split
            # Find the 100th card's end
            card_positions = [m.start() for m in re.finditer(r'<div class=\\?"gpt-e-card\\?">', rest)]
            if len(card_positions) > 100:
                cut_pos = card_positions[100]
                rest = rest[:cut_pos]
            new_content = head + '<div id="gpt-e-log">' + rest

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(new_content) 

def clear_gpt_e_html_log():
    """
    Clears all entries from the HTML log except the header and the 'gpt-e-log' div.
    """
    html_file = os.path.join("data", "gpt_e_results.html")
    if not os.path.exists(html_file):
        return
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    # Find the header and the start of the log div
    start = content.find('<div id="gpt-e-log">')
    if start == -1:
        return
    end = content.find('</div>', start)
    if end == -1:
        return
    # Keep everything up to the opening of the log div, then close it immediately
    new_content = content[:start] + '<div id="gpt-e-log">\n    </div>\n</body>\n</html>'
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(new_content) 