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
    model: Optional[str] = None
) -> None:
    """
    Append a GPT-E update to the HTML log file in the data directory.
    Keeps only the latest 100 updates.
    Creates the file and directory if they do not exist.
    Shows cost in both USD and ILS if both are provided, or just one if only one is present.
    """
    html_file = os.path.join("data", "gpt_e_results.html")
    # התיקייה data תמיד קיימת לפי דרישת המשתמש
    
    # Create the HTML entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format metadata
    metadata = []
    if tokens_used is not None:
        metadata.append(f"Tokens: {tokens_used}")
    if cost is not None and cost_ils is not None:
        metadata.append(f"Cost: ${cost:.4f} / ₪{cost_ils:.3f}")
    elif cost is not None:
        metadata.append(f"Cost: ${cost:.4f}")
    elif cost_ils is not None:
        metadata.append(f"Cost: ₪{cost_ils:.3f}")
    if model is not None:
        metadata.append(f"Model: {model}")
    
    metadata_html = f"<div class='metadata'>{' | '.join(metadata)}</div>" if metadata else ""
    
    entry_html = f"""
    <div class=\"gpt-e-card\">
        <div class=\"gpt-e-meta\">
            <span>{timestamp}</span>
            {metadata_html}
        </div>
        <div class=\"gpt-e-section\"><b>Old Summary:</b><div class=\"gpt-e-summary\">{old_summary}</div></div>
        <div class=\"gpt-e-section\"><b>User Message:</b><div class=\"gpt-e-summary\">{user_message}</div></div>
        <div class=\"gpt-e-section\"><b>New Summary:</b><div class=\"gpt-e-summary\">{new_summary}</div></div>
    </div>
    """
    
    existing_entries = []
    if os.path.exists(html_file):
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
            import re
            entries = re.findall(r'<div class=\\"gpt-e-card\\">.*?</div>', content, re.DOTALL)
            existing_entries = entries[:99]  # Keep only 99 existing entries (100 total with new one)
    # else: existing_entries stays empty
    
    # Create the full HTML content
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
        .gpt-e-section {{
            margin-bottom: 10px;
        }}
        .gpt-e-summary {{
            background: #f2f4f8;
            border-radius: 5px;
            padding: 5px 8px;
            margin: 2px 0 6px 0;
            font-size: 1em;
            word-break: break-word;
        }}
        .gpt-e-card b {{
            color: #4b5fc0;
        }}
        .gpt-e-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 18px;
            border-radius: 10px;
            margin-bottom: 18px;
            box-shadow: 0 2px 6px #0002;
            text-align: center;
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
    </style>
</head>
<body>
    <div class=\"gpt-e-header\">
        <h2>GPT-E Updates Log</h2>
        <p>היסטוריית עדכונים של כל סיכומי GPT-E. כל עדכון נשמר ככרטיסיה חדשה.</p>
    </div>
    <div id=\"gpt-e-log\">
"""
    
    # Add the new entry first, then existing entries
    all_entries = [entry_html] + existing_entries
    
    # Add all entries to HTML content
    if all_entries:
        html_content += "\n".join(all_entries)
    else:
        html_content += '<div class=\"no-updates\">No updates yet.</div>'
    
    html_content += """
    </div>
</body>
</html>"""
    
    # Write the file
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content) 