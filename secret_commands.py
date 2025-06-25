# secret_commands.py

import os
import json
from datetime import datetime
from sheets_handler import delete_row_by_chat_id
from utils import log_event_to_file, send_error_stats_report, send_usage_report  # ודא שהפונקציות קיימות! (יש כמעט בוודאות)
from notifications import send_admin_secret_command_notification  # <--- נדרש בקובץ notifications.py
from config import CHAT_HISTORY_PATH, ADMIN_NOTIFICATION_CHAT_ID, config

SECRET_CODES = {
    "#487chaCha2025": "clear_history",    # מוחק היסטוריית שיחה
    "#512SheetBooM": "clear_sheets",      # מוחק מידע מהגיליונות
    "#734TotalZap": "clear_all",          # מוחק הכל (היסטוריה + גיליונות)
    "#errors_report": "errors_report",      # מפעיל דוח שגיאות לאדמין
    "#usage_report": "usage_report",        # מפעיל דוח usage שבועי לאדמין
    "#run_gpt_e": "run_gpt_e"               # מפעיל gpt_e ידנית על chat_id
}

def handle_secret_command(chat_id, user_msg):
    """
    טיפול בפקודות סודיות למטרות בדיקה ותחזוקה.
    קלט: chat_id, user_msg
    פלט: (bool, str) - האם טופל והתשובה
    """
    print(f"[SECRET_CMD] קיבלתי הודעה לבדוק קוד סודי | chat_id={chat_id} | text={user_msg!r} | timestamp={datetime.now().isoformat()}")

    action = SECRET_CODES.get(user_msg.strip())
    if not action:
        print(f"[SECRET_CMD] לא נמצא קוד סודי תואם | chat_id={chat_id} | text={user_msg!r}")
        log_event_to_file({
            "event": "secret_command",
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "input_text": user_msg,
            "result": "no_action"
        })
        return False, None

    print(f"[SECRET_CMD] קוד סודי מזוהה: {action} | chat_id={chat_id} | timestamp={datetime.now().isoformat()}")

    if action == "clear_history":
        cleared = clear_chat_history(chat_id)
        msg = "🧹 כל ההיסטוריה שלך נמחקה! (chat_history)" if cleared else "🤷‍♂️ לא נמצאה היסטוריה למחיקה."
        print(f"[SECRET_CMD] {chat_id} ביקש clear_history — {'נמחק' if cleared else 'לא נמצא'} | timestamp={datetime.now().isoformat()}")
        log_event_to_file({
            "event": "secret_command",
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "action": "clear_history",
            "result": cleared
        })
        # --- שליחת הודעה לאדמין ---
        send_admin_secret_command_notification(
            f"❗ הופעל קוד סודי למחיקת היסטוריה בצ'אט {chat_id}.\n"
            f"נמחקה אך ורק ההיסטוריה של משתמש זה (לא של אחרים)."
        )
        return True, msg

    if action == "clear_sheets":
        deleted_sheet, deleted_state = clear_from_sheets(chat_id)
        msg = "🗑️ כל הנתונים שלך נמחקו מהגיליונות!" if (deleted_sheet or deleted_state) else "🤷‍♂️ לא נמצא מידע למחיקה בגיליונות."
        print(f"[SECRET_CMD] {chat_id} ביקש clear_sheets — sheet: {deleted_sheet}, state: {deleted_state} | timestamp={datetime.now().isoformat()}")
        log_event_to_file({
            "event": "secret_command",
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "action": "clear_sheets",
            "deleted_sheet": deleted_sheet,
            "deleted_state": deleted_state
        })
        send_admin_secret_command_notification(
            f"❗ הופעל קוד סודי למחיקת נתונים בגיליונות בצ'אט {chat_id}.\n"
            f"נמחק אך ורק מידע של משתמש זה (לא של אחרים).\n"
            f"{config['SHEET_USER_TAB']}: {'הצליח' if deleted_sheet else 'לא הצליח'}, {config['SHEET_STATES_TAB']}: {'הצליח' if deleted_state else 'לא הצליח'}"
        )
        return True, msg

    if action == "clear_all":
        cleared = clear_chat_history(chat_id)
        deleted_sheet, deleted_state = clear_from_sheets(chat_id)
        msg = "💣 הכל נמחק! (היסטוריה + גיליונות)" if (cleared or deleted_sheet or deleted_state) else "🤷‍♂️ לא נמצא שום מידע למחיקה."
        print(f"[SECRET_CMD] {chat_id} ביקש clear_all — history: {cleared}, sheet: {deleted_sheet}, state: {deleted_state} | timestamp={datetime.now().isoformat()}")
        log_event_to_file({
            "event": "secret_command",
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "action": "clear_all",
            "cleared_history": cleared,
            "deleted_sheet": deleted_sheet,
            "deleted_state": deleted_state
        })
        send_admin_secret_command_notification(
            f"❗ הופעל קוד סודי למחיקת **הכל** בצ'אט {chat_id}.\n"
            f"נמחק הכל של משתמש זה בלבד (לא של אחרים).\n"
            f"היסטוריה: {'✔️' if cleared else '❌'} | {config['SHEET_USER_TAB']}: {'✔️' if deleted_sheet else '❌'} | {config['SHEET_STATES_TAB']}: {'✔️' if deleted_state else '❌'}"
        )
        return True, msg

    if user_msg.strip() == "#errors_report":
        if str(chat_id) == str(ADMIN_NOTIFICATION_CHAT_ID):
            send_error_stats_report()
            return True, "נשלח דוח שגיאות לאדמין."
        else:
            return False, "אין לך הרשאה לפקודה זו."
    if user_msg.strip() == "#usage_report":
        if str(chat_id) == str(ADMIN_NOTIFICATION_CHAT_ID):
            send_usage_report(7)
            return True, "נשלח דוח usage שבועי לאדמין."
        else:
            return False, "אין לך הרשאה לפקודה זו."

    if user_msg.strip() == "#run_gpt_e":
        if str(chat_id) == str(ADMIN_NOTIFICATION_CHAT_ID):
            # פקודה להפעלת gpt_e ידנית
            # הפורמט: #run_gpt_e <chat_id>
            parts = user_msg.split()
            if len(parts) == 2:
                target_chat_id = parts[1]
                try:
                    from gpt_e_handler import run_gpt_e
                    result = run_gpt_e(target_chat_id)
                    
                    if result['success']:
                        changes_count = len(result.get('changes', {}))
                        tokens_used = result.get('tokens_used', 0)
                        execution_time = result.get('execution_time', 0)
                        
                        msg = f"✅ gpt_e הופעל בהצלחה על chat_id={target_chat_id}\n"
                        msg += f"📊 שינויים: {changes_count}\n"
                        msg += f"🔢 טוקנים: {tokens_used}\n"
                        msg += f"⏱️ זמן: {execution_time:.2f} שניות"
                        
                        if result.get('errors'):
                            msg += f"\n⚠️ שגיאות: {', '.join(result['errors'])}"
                    else:
                        errors = result.get('errors', ['Unknown error'])
                        msg = f"❌ gpt_e נכשל על chat_id={target_chat_id}\n"
                        msg += f"שגיאות: {', '.join(errors)}"
                    
                    # שליחת הודעה לאדמין
                    send_admin_secret_command_notification(
                        f"🔧 הופעל gpt_e ידנית על chat_id={target_chat_id}\n"
                        f"תוצאה: {'הצלחה' if result['success'] else 'כישלון'}\n"
                        f"שינויים: {len(result.get('changes', {}))}\n"
                        f"טוקנים: {result.get('tokens_used', 0)}"
                    )
                    
                    return True, msg
                    
                except Exception as e:
                    error_msg = f"❌ שגיאה בהפעלת gpt_e: {str(e)}"
                    send_admin_secret_command_notification(
                        f"❌ שגיאה בהפעלת gpt_e ידנית על chat_id={target_chat_id}\n"
                        f"שגיאה: {str(e)}"
                    )
                    return False, error_msg
            else:
                return False, "פורמט שגוי. השתמש: #run_gpt_e <chat_id>"
        else:
            return False, "אין לך הרשאה לפקודה זו."

    # 📊 דוח ביצועי concurrent handling
    if user_msg.lower() in ["/performance", "/ביצועים", "/stats"]:
        try:
            from concurrent_monitor import get_performance_report, get_performance_stats
            
            # קבלת דוח מפורט
            report = get_performance_report()
            
            # הוספת נתונים טכניים
            stats = get_performance_stats()
            technical_info = f"""
📊 **נתונים טכניים נוספים:**
   • עומס מערכת: {stats['current_active_users']}/{stats['max_concurrent_users']} ({(stats['current_active_users']/stats['max_concurrent_users']*100):.1f}%)
   • יעילות תגובה: {'🟢 מעולה' if stats['avg_response_time_current'] < 3 else '🟡 בינוני' if stats['avg_response_time_current'] < 5 else '🔴 איטי'}
   • יציבות מערכת: {'🟢 יציב' if stats['error_rate'] < 0.05 else '🟡 בינוני' if stats['error_rate'] < 0.1 else '🔴 לא יציב'}
"""
            
            return True, report + technical_info
            
        except Exception as e:
            return True, f"❌ שגיאה בקבלת דוח ביצועים: {e}"

    # 🚀 בדיקה מהירה של מצב המערכת
    if user_msg.lower() in ["/status", "/מצב"]:
        try:
            from concurrent_monitor import get_performance_stats
            stats = get_performance_stats()
            
            status_emoji = "🟢" if stats['current_active_users'] < stats['max_concurrent_users'] * 0.7 else "🟡" if stats['current_active_users'] < stats['max_concurrent_users'] * 0.9 else "🔴"
            
            quick_status = f"""
{status_emoji} **מצב המערכת - עדכון מהיר**

👥 **משתמשים פעילים:** {stats['current_active_users']}/{stats['max_concurrent_users']}
⏱️ **זמן תגובה:** {stats['avg_response_time_current']:.2f}s
🔴 **שיעור שגיאות:** {stats['error_rate']:.1%}
💻 **סה"כ בקשות היום:** {stats['total_requests']}

🔄 **סשנים פעילים:**"""
            
            if stats['active_sessions']:
                for chat_id, stage in list(stats['active_sessions'].items())[:5]:  # מקסימום 5
                    quick_status += f"\n   • {chat_id}: {stage}"
                if len(stats['active_sessions']) > 5:
                    quick_status += f"\n   • ועוד {len(stats['active_sessions']) - 5} סשנים..."
            else:
                quick_status += "\n   • אין סשנים פעילים כרגע"
            
            return True, quick_status
            
        except Exception as e:
            return True, f"❌ שגיאה בבדיקת מצב: {e}"

    print(f"[SECRET_CMD] קוד סודי לא תואם אף פעולה | chat_id={chat_id} | action={action} | timestamp={datetime.now().isoformat()}")
    log_event_to_file({
        "event": "secret_command",
        "timestamp": datetime.now().isoformat(),
        "chat_id": chat_id,
        "input_text": user_msg,
        "action": action,
        "result": "unknown_action"
    })
    return False, None

def clear_chat_history(chat_id):
    path = CHAT_HISTORY_PATH
    print(f"[CLEAR_HISTORY] מנסה למחוק היסטוריה | chat_id={chat_id} | path={path} | timestamp={datetime.now().isoformat()}")
    if not os.path.exists(path):
        print(f"[CLEAR_HISTORY] קובץ היסטוריה לא קיים | path={path}")
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if str(chat_id) in data:
            data.pop(str(chat_id))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[CLEAR_HISTORY] נמחקה היסטוריה בהצלחה | chat_id={chat_id} | timestamp={datetime.now().isoformat()}")
            return True
        print(f"[CLEAR_HISTORY] לא נמצאה היסטוריה למחיקה | chat_id={chat_id}")
        return False
    except Exception as e:
        print(f"[ERROR-clear_chat_history] {e} | chat_id={chat_id}")
        log_event_to_file({
            "event": "clear_history_error",
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "error": str(e)
        })
        return False

def clear_from_sheets(chat_id):
    print(f"[CLEAR_SHEETS] מנסה למחוק מהגיליונות | chat_id={chat_id} | timestamp={datetime.now().isoformat()}")
    deleted_sheet = delete_row_by_chat_id(sheet_name=config["SHEET_USER_TAB"], chat_id=chat_id)
    print(f"[CLEAR_SHEETS] נמחק ב-{config['SHEET_USER_TAB']}: {deleted_sheet} | chat_id={chat_id}")
    deleted_state = delete_row_by_chat_id(sheet_name=config["SHEET_STATES_TAB"], chat_id=chat_id)
    print(f"[CLEAR_SHEETS] נמחק ב-{config['SHEET_STATES_TAB']}: {deleted_state} | chat_id={chat_id}")
    return deleted_sheet, deleted_state

# דוגמה להוספת קוד סודי חדש:
# פשוט הוסף ל-SECRET_CODES עוד שורה, ותכתוב פונקציה חדשה עם אותו מבנה
# למשל:
# SECRET_CODES["#999SuperErase"] = "super_erase"
# ואז תוסיף:
# def super_erase(chat_id):
#     ... פה קוד למחיקה מיוחדת ...
