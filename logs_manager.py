"""
logs_manager.py
===============
מודול לניהול לוגים של Render ושליחת לוגים לטלגרם
הועבר מ-bot_setup.py כדי לשמור על קוד lean ומסודר
"""

import subprocess
import datetime
import asyncio
import threading

async def handle_show_logs_command(update, context):
    """מטפל בפקודת /show_logs לקריאת לוגים מרנדר"""
    try:
        # בדיקה אם המשתמש הוא אדמין
        chat_id = str(update.effective_chat.id)
        if chat_id != "111709341":
            await update.message.reply_text("❌ רק אדמין יכול להריץ פקודה זו")
            return
        
        # קבלת הפרמטרים מהפקודה
        message_text = update.message.text.strip()
        parts = message_text.split()
        
        # ברירת מחדל: 50 שורות אחרונות
        lines = 50
        log_type = "service"
        
        # פרסור פרמטרים
        if len(parts) > 1:
            try:
                lines = int(parts[1])
                lines = min(lines, 500)  # מקסימום 500 שורות
            except ValueError:
                log_type = parts[1]
        
        if len(parts) > 2:
            log_type = parts[2]
        
        await update.message.reply_text(f"📋 קורא {lines} שורות אחרונות מלוג {log_type}...")
        
        # הרצת קריאת לוגים ב-thread נפרד
        def read_logs():
            try:
                logs = get_render_logs(log_type, lines)
                
                # שליחת הלוגים לטלגרם
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_logs_to_telegram(update, logs, log_type, lines))
                loop.close()
            except Exception as e:
                print(f"❌ שגיאה בקריאת לוגים: {e}")
        
        logs_thread = threading.Thread(target=read_logs)
        logs_thread.start()
        
    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה בפקודת לוגים: {e}")

def get_render_logs(log_type="service", lines=50):
    """קורא לוגים מרנדר דרך SSH"""
    try:
        # מיפוי סוגי לוגים
        log_paths = {
            "service": "/var/log/render/service.log",
            "python": "/var/log/render/python.log", 
            "error": "/var/log/render/error.log",
            "access": "/var/log/render/access.log"
        }
        
        log_path = log_paths.get(log_type, "/var/log/render/service.log")
        ssh_host = "srv-d0r895be5dus73fmsc8g@ssh.frankfurt.render.com"
        
        # פקודת SSH לקריאת לוגים
        cmd = f"ssh {ssh_host} 'tail -n {lines} {log_path}'"
        
        print(f"📋 מריץ פקודה: {cmd}")
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"❌ שגיאה בקריאת לוגים: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return "⏰ הזמן לקריאת לוגים פג - הרנדר לא מגיב"
    except Exception as e:
        return f"❌ שגיאה בקריאת לוגים: {e}"

async def send_logs_to_telegram(update, logs, log_type, lines):
    """שולח לוגים לטלגרם (עם חלוקה לחלקים אם נדרש)"""
    try:
        if not logs or not logs.strip():
            await update.message.reply_text(f"📋 אין לוגים זמינים עבור {log_type}")
            return
        
        # הוספת כותרת
        header = f"📋 **לוגים מרנדר - {log_type}**\n"
        header += f"📊 {lines} שורות אחרונות\n"
        header += f"🕐 {datetime.datetime.now().strftime('%H:%M:%S')}\n"
        header += "=" * 40 + "\n\n"
        
        formatted_logs = header + logs
        
        # חלוקה לחלקים (טלגרם מוגבל ל-4096 תווים)
        max_length = 4000  # השארת מקום לפורמטינג
        
        if len(formatted_logs) <= max_length:
            await update.message.reply_text(f"```\n{formatted_logs}\n```", parse_mode="Markdown")
        else:
            # חלוקה לחלקים
            parts = []
            current_part = header
            
            for line in logs.split('\n'):
                if len(current_part) + len(line) + 1 > max_length:
                    parts.append(current_part)
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
            
            if current_part.strip():
                parts.append(current_part)
            
            # שליחת כל חלק
            for i, part in enumerate(parts):
                part_header = f"📋 חלק {i+1}/{len(parts)}\n" + "=" * 20 + "\n"
                await update.message.reply_text(f"```\n{part_header}{part}\n```", parse_mode="Markdown")
                
                # מניעת spam - המתנה בין חלקים
                if i < len(parts) - 1:
                    await asyncio.sleep(1)
        
        # סיכום
        await update.message.reply_text(f"✅ לוגים נשלחו בהצלחה!\n📊 סה\"כ {len(logs.split())} שורות")
        
    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה בשליחת לוגים: {e}")

async def handle_search_logs_command(update, context):
    """מטפל בפקודת /search_logs לחיפוש לוגים"""
    try:
        # בדיקה אם המשתמש הוא אדמין
        chat_id = str(update.effective_chat.id)
        if chat_id != "111709341":
            await update.message.reply_text("❌ רק אדמין יכול להריץ פקודה זו")
            return
        
        # קבלת הפרמטרים מהפקודה
        message_text = update.message.text.strip()
        parts = message_text.split()
        
        if len(parts) < 2:
            await update.message.reply_text(
                "❓ שימוש: /search_logs <מילת_חיפוש> [סוג_לוג] [מספר_שורות]\n"
                "דוגמה: /search_logs error service 100"
            )
            return
        
        search_term = parts[1]
        log_type = parts[2] if len(parts) > 2 else "service"
        lines = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 200
        lines = min(lines, 1000)  # מקסימום 1000 שורות
        
        await update.message.reply_text(f"🔍 מחפש '{search_term}' ב-{lines} שורות אחרונות של {log_type}...")
        
        # הרצת חיפוש לוגים ב-thread נפרד
        def search_logs():
            try:
                logs = get_render_logs(log_type, lines)
                search_results = search_logs_in_file(logs, search_term)
                
                # שליחת התוצאות לטלגרם
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_search_results_to_telegram(update, search_results, log_type, search_term))
                loop.close()
            except Exception as e:
                print(f"❌ שגיאה בחיפוש לוגים: {e}")
        
        logs_thread = threading.Thread(target=search_logs)
        logs_thread.start()
        
    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה בפקודת חיפוש לוגים: {e}")

def search_logs_in_file(file_content, search_term):
    """חיפוש לוגים בתוכן קובץ"""
    search_results = []
    for line in file_content.splitlines():
        if search_term.lower() in line.lower():
            search_results.append(line)
    return search_results

async def send_search_results_to_telegram(update, search_results, log_type, search_term):
    """שולח תוצאות חיפוש לוגים לטלגרם"""
    try:
        if not search_results:
            await update.message.reply_text(f"🔍 לא נמצאו תוצאות עבור '{search_term}' ב-{log_type}")
            return
        
        # הכנת כותרת
        header = f"🔍 **תוצאות חיפוש '{search_term}' ב-{log_type}**\n"
        header += f"📊 נמצאו {len(search_results)} תוצאות\n"
        header += f"🕐 {datetime.datetime.now().strftime('%H:%M:%S')}\n"
        header += "=" * 40 + "\n\n"
        
        # חיבור התוצאות
        results_text = "\n".join(search_results)
        formatted_results = header + results_text
        
        # חלוקה לחלקים אם נדרש
        max_length = 4000
        
        if len(formatted_results) <= max_length:
            await update.message.reply_text(f"```\n{formatted_results}\n```", parse_mode="Markdown")
        else:
            # חלוקה לחלקים
            parts = []
            current_part = header
            
            for result in search_results:
                if len(current_part) + len(result) + 1 > max_length:
                    parts.append(current_part)
                    current_part = result + '\n'
                else:
                    current_part += result + '\n'
            
            if current_part.strip():
                parts.append(current_part)
            
            # שליחת כל חלק
            for i, part in enumerate(parts):
                part_header = f"🔍 תוצאות {i+1}/{len(parts)}\n" + "=" * 20 + "\n"
                await update.message.reply_text(f"```\n{part_header}{part}\n```", parse_mode="Markdown")
                
                # המתנה בין חלקים
                if i < len(parts) - 1:
                    await asyncio.sleep(1)
        
        # סיכום
        await update.message.reply_text(f"✅ תוצאות חיפוש נשלחו!\n🔍 נמצאו {len(search_results)} תוצאות עבור '{search_term}'")
        
    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה בשליחת תוצאות חיפוש: {e}")

async def handle_deploy_logs_command(update, context):
    """מטפל בפקודת /deploy_logs לקריאת לוגי deployment"""
    try:
        # בדיקה אם המשתמש הוא אדמין
        chat_id = str(update.effective_chat.id)
        if chat_id != "111709341":
            await update.message.reply_text("❌ רק אדמין יכול להריץ פקודה זו")
            return
        
        await update.message.reply_text("📋 קורא לוגי deployment אחרונים...")
        
        # הרצת קריאת deploy logs ב-thread נפרד
        def read_deploy_logs():
            try:
                logs = get_render_logs("deploy", 100)  # 100 שורות אחרונות של deployment
                
                # שליחת הלוגים לטלגרם
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_logs_to_telegram(update, logs, "deploy", 100))
                loop.close()
            except Exception as e:
                print(f"❌ שגיאה בקריאת לוגי deployment: {e}")
        
        logs_thread = threading.Thread(target=read_deploy_logs)
        logs_thread.start()
        
    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה בפקודת לוגי deployment: {e}") 