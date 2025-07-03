import os
import json
from collections import deque
from datetime import datetime
from typing import Any, Dict, List

# -----------------------------------------------------------------------------
# Configuration – single source of truth (avoids duplication across the script)
# -----------------------------------------------------------------------------
JSONL_PATH = os.path.join("data", "openai_calls.jsonl")
HTML_OUT_PATH = os.path.join("data", "gpt_log.html")
MAX_LINES = 100  # number of recent calls to display
USD_TO_ILS = 3.7  # rough conversion; update in a single place if needed

# -----------------------------------------------------------------------------
# Helper utilities (isolated, side-effect free)
# -----------------------------------------------------------------------------

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
        ("תוכן התשובה", answer + formatted_html),
        ("טוקני בקשה", str(prompt_toks)),
        ("טוקני תשובה", str(completion_toks)),
        ("טוקני cache", str(cached_toks)),
        ("סך טוקנים", str(total_toks)),
    ]
    response_rows_html = "\n".join(
        f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in response_rows if v
    )
    response_block = (
        f"<table class=\"content-table\">{response_rows_html}</table>"
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
      <div id=\"{req_id}\" style=\"display:none;\">{request_block}</div>
      <button class=\"button\" onclick=\"toggle('{res_id}')\">▶ תשובה</button>
      <div id=\"{res_id}\" style=\"display:none;\">{response_block}</div>
    </td>
    <td class=\"gpt-cell gpt{gpt_type}\">G<br>P<br>T<br>{gpt_type}</td>
  </tr></table>
</div>"""


# -----------------------------------------------------------------------------
# Main driver – minimal side-effects beyond writing HTML file
# -----------------------------------------------------------------------------

def build_html() -> None:
    # Ensure output directory exists (also for JSONL path)
    os.makedirs(os.path.dirname(HTML_OUT_PATH) or ".", exist_ok=True)

    lines = tail_lines(JSONL_PATH, MAX_LINES)
    if not lines:
        print("No log entries found; output HTML will contain placeholder message.")

    entries_html: List[str] = []
    for idx, raw in enumerate(reversed(lines)):
        try:
            rec: Dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            continue  # skip invalid lines

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
        .button { cursor: pointer; color: blue; text-decoration: underline; border: none; background: none; font-size: 0.9em }
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
    </style>
    <script>function toggle(id){var e=document.getElementById(id);e.style.display=e.style.display==='none'?'block':'none';}</script>
</head><body>
<h2>100 הקריאות האחרונות ל־GPT</h2>"""

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


if __name__ == "__main__":
    build_html()