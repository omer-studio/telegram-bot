import os
import json
from datetime import datetime
from typing import Dict, Any, Optional


def append_gpt_e_html_update(
    old_summary: str,
    user_message: str,
    new_summary: str,
    tokens_used: Optional[int] = None,
    cost: Optional[float] = None,
    model: Optional[str] = None
) -> None:
    """
    Append a GPT-E update to the HTML log file in the data directory.
    Keeps only the latest 100 updates.
    Creates the file and directory if they do not exist.
    """
    html_file = os.path.join("data", "gpt_e_results.html")
    # התיקייה data תמיד קיימת לפי דרישת המשתמש
    
    # Create the HTML entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format metadata
    metadata = []
    if tokens_used is not None:
        metadata.append(f"Tokens: {tokens_used}")
    if cost is not None:
        metadata.append(f"Cost: ${cost:.4f}")
    if model is not None:
        metadata.append(f"Model: {model}")
    
    metadata_html = f"<div class='metadata'>{' | '.join(metadata)}</div>" if metadata else ""
    
    entry_html = f"""
    <div class=\"entry\">
        <div class=\"timestamp\">{timestamp}</div>
        {metadata_html}
        <div class=\"section\">
            <h3>Old Summary:</h3>
            <div class=\"content\">{old_summary}</div>
        </div>
        <div class=\"section\">
            <h3>User Message:</h3>
            <div class=\"content\">{user_message}</div>
        </div>
        <div class=\"section\">
            <h3>New Summary:</h3>
            <div class=\"content\">{new_summary}</div>
        </div>
        <hr>
    </div>
    """
    
    existing_entries = []
    if os.path.exists(html_file):
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
            import re
            entries = re.findall(r'<div class=\"entry\">.*?</div>\\s*<hr>', content, re.DOTALL)
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
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }}
        .entry {{
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            border-left: 4px solid #667eea;
        }}
        .timestamp {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
            font-weight: 500;
        }}
        .metadata {{
            background: #f8f9fa;
            padding: 8px 12px;
            border-radius: 5px;
            margin-bottom: 15px;
            font-size: 0.85em;
            color: #495057;
            border-left: 3px solid #667eea;
        }}
        .section {{
            margin-bottom: 20px;
        }}
        .section h3 {{
            color: #333;
            margin: 0 0 10px 0;
            font-size: 1.1em;
            font-weight: 600;
        }}
        .content {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #e9ecef;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            line-height: 1.4;
        }}
        hr {{
            border: none;
            height: 1px;
            background: linear-gradient(to right, transparent, #ddd, transparent);
            margin: 20px 0;
        }}
        .no-updates {{
            text-align: center;
            color: #666;
            font-style: italic;
            padding: 40px;
        }}
    </style>
</head>
<body>
    <div class=\"header\">
        <h1>GPT-E Updates Log</h1>
        <p>This file automatically logs all GPT-E summary updates. It is excluded from Git tracking (.gitignore).</p>
        <p>Shows the old summary, user message, and new summary for each update.</p>
    </div>
"""
    
    # Add the new entry first, then existing entries
    all_entries = [entry_html] + existing_entries
    
    # Add all entries to HTML content
    if all_entries:
        html_content += "\n".join(all_entries)
    else:
        html_content += '<div class=\"no-updates\">No updates yet.</div>'
    
    html_content += """
</body>
</html>"""
    
    # Write the file
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content) 