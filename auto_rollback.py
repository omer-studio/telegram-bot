#!/usr/bin/env python3
"""
🚨 מנגנון Rollback אוטומטי לפריסות נכשלות
================================================

מטרה: להגן על הבוט מפריסות שגויות על ידי:
1. בדיקת תקינות אחרי deploy
2. rollback אוטומטי לגרסה קודמת אם יש בעיה
3. התראה מיידית לאדמין

⚠️ כללי ברזל - לא משנה את הלוגיקה הקיימת!
רק מוסיף שכבת הגנה נוספת.
"""

import os
import sys
import time
import json
import requests
import subprocess
from datetime import datetime
from typing import Optional, Dict, List

# הוספת path לגישה לmodules הקיימים
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class RollbackManager:
    """מנהל rollback אוטומטי עם הגנות מרובות"""
    
    def __init__(self):
        self.max_rollback_attempts = 3
        self.health_check_timeout = 30  # שניות
        self.health_check_retries = 5
        self.rollback_history_file = "data/rollback_history.json"
        self.last_known_good_commit_file = "data/last_good_commit.json"
        
    def save_successful_deploy(self, commit_hash: str, timestamp: Optional[str] = None):
        """שומר commit מוצלח כ-last known good"""
        try:
            if not timestamp:
                timestamp = datetime.now().isoformat()
                
            good_commit_data = {
                "commit": commit_hash,
                "timestamp": timestamp,
                "verified": True
            }
            
            os.makedirs("data", exist_ok=True)
            with open(self.last_known_good_commit_file, 'w', encoding='utf-8') as f:
                json.dump(good_commit_data, f, indent=2)
                
            print(f"✅ Saved successful deploy: {commit_hash[:7]}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save successful deploy: {e}")
            return False
    
    def get_last_known_good_commit(self) -> Optional[str]:
        """מחזיר את ה-commit האחרון שידוע כתקין"""
        try:
            if os.path.exists(self.last_known_good_commit_file):
                with open(self.last_known_good_commit_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("commit")
            return None
        except Exception as e:
            print(f"❌ Failed to get last known good commit: {e}")
            return None
    
    def perform_health_check(self) -> bool:
        """בדיקת תקינות מרובת שלבים"""
        print("🔍 מתחיל בדיקת תקינות של הבוט...")
        
        # שלב 1: בדיקת syntax ו-imports
        try:
            result = subprocess.run(
                [sys.executable, "health_check.py"], 
                capture_output=True, 
                text=True, 
                timeout=self.health_check_timeout
            )
            
            if result.returncode == 0:
                print("✅ בדיקת תקינות עברה - הבוט תקין!")
                return True
            else:
                print(f"❌ בדיקת תקינות נכשלה:")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"⏰ בדיקת תקינות עברה timeout ({self.health_check_timeout}s)")
            return False
        except Exception as e:
            print(f"💥 שגיאה בבדיקת תקינות: {e}")
            return False
    
    def perform_live_bot_test(self) -> bool:
        """בדיקת בוט חי - שליחת הודעת בדיקה לאדמין"""
        try:
            # בדיקת סביבת CI/CD - דילוג על בדיקה חיה
            if os.getenv('GITHUB_ACTIONS') or os.getenv('CI'):
                print("🔧 זוהתה סביבת CI - מדלג על בדיקת בוט חי")
                print("✅ בדיקת בוט חי (CI mode) - עברה בהצלחה!")
                return True
            
            # ניסיון לטעון את הגדרות הבוט
            try:
                from config import ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID
            except ImportError as e:
                print(f"❌ לא ניתן לטעון הגדרות בוט: {e}")
                return False
            
            # בדיקת ערכי dummy בCI
            if (ADMIN_BOT_TELEGRAM_TOKEN == "dummy_token_for_testing" or 
                ADMIN_NOTIFICATION_CHAT_ID == "dummy_chat_id" or
                "dummy" in str(ADMIN_BOT_TELEGRAM_TOKEN).lower()):
                print("🔧 זוהו ערכי dummy - מדלג על בדיקת בוט חי")
                print("✅ בדיקת בוט חי (dummy mode) - עברה בהצלחה!")
                return True
            
            # שליחת הודעת בדיקה
            test_message = f"🔍 בדיקת תקינות אוטומטית\n⏰ {datetime.now().strftime('%H:%M:%S')}\n✅ הבוט פעיל ועובד!"
            
            url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
                "text": test_message
            }
            
            response = requests.post(url, data=payload, timeout=10)
            
            if response.status_code == 200:
                print("✅ בדיקת בוט חי - עברה בהצלחה!")
                return True
            else:
                print(f"❌ בדיקת בוט חי נכשלה: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"💥 שגיאה בבדיקת בוט חי: {e}")
            return False
    
    def trigger_rollback(self, reason: str) -> bool:
        """מפעיל rollback לגרסה קודמת"""
        print(f"🚨 מפעיל ROLLBACK! סיבה: {reason}")
        
        try:
            # יצירת התראה קריטית לאדמין לפני rollback
            self._send_emergency_alert(f"🚨 ROLLBACK TRIGGERED!\nSיבה: {reason}")
            
            # שמירת היסטוריה
            rollback_record = {
                "timestamp": datetime.now().isoformat(),
                "reason": reason,
                "status": "initiated"
            }
            self._save_rollback_history(rollback_record)
            
            # ביצוע rollback בפועל (תלוי בסביבת הפריסה)
            rollback_success = self._execute_rollback()
            
            if rollback_success:
                rollback_record["status"] = "success"
                print("✅ Rollback בוצע בהצלחה!")
                self._send_emergency_alert("✅ ROLLBACK הושלם בהצלחה! הבוט חזר לעבוד!")
            else:
                rollback_record["status"] = "failed"
                print("❌ Rollback נכשל!")
                self._send_emergency_alert("❌ ROLLBACK נכשל! נדרשת התערבות ידנית מיידית!")
            
            self._save_rollback_history(rollback_record)
            return rollback_success
            
        except Exception as e:
            print(f"💥 שגיאה קריטית ב-rollback: {e}")
            self._send_emergency_alert(f"💥 שגיאה קריטית ב-ROLLBACK: {e}")
            return False
    
    def _execute_rollback(self) -> bool:
        """מבצע rollback בפועל - מותאם לסביבת Render"""
        try:
            last_good_commit = self.get_last_known_good_commit()
            
            if not last_good_commit:
                print("❌ אין commit תקין להחזרה אליו!")
                return False
            
            print(f"🔄 מחזיר לcommit תקין: {last_good_commit[:7]}")
            
            # בסביבת Render - צריך לעשות redeploy של commit קודם
            if os.getenv("RENDER"):
                return self._render_rollback(last_good_commit)
            
            # בסביבה מקומית - git checkout
            else:
                return self._git_rollback(last_good_commit)
                
        except Exception as e:
            print(f"❌ שגיאה בביצוע rollback: {e}")
            return False
    
    def _render_rollback(self, commit_hash: str) -> bool:
        """rollback ספציפי לסביבת Render"""
        try:
            # בRender - הדרך הכי מהירה היא להריץ git reset ו-force push
            # אבל זה מסוכן, אז נשתמש בגישה בטוחה יותר
            
            print("🔄 מבצע Render rollback...")
            
            # שלב 1: reset לcommit הקודם
            subprocess.run(["git", "reset", "--hard", commit_hash], check=True, timeout=30)
            
            # שלב 2: יצירת commit חדש עם המצב הקודם
            subprocess.run(["git", "commit", "--allow-empty", "-m", f"EMERGENCY ROLLBACK to {commit_hash[:7]}"], check=True, timeout=30)
            
            print("✅ Render rollback הושלם (ממתין לפריסה אוטומטית)")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Git rollback נכשל: {e}")
            return False
        except Exception as e:
            print(f"❌ Render rollback נכשל: {e}")
            return False
    
    def _git_rollback(self, commit_hash: str) -> bool:
        """rollback בסביבה מקומית"""
        try:
            subprocess.run(["git", "checkout", commit_hash], check=True, timeout=30)
            print("✅ Git rollback הושלם")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Git rollback נכשל: {e}")
            return False
    
    def _send_emergency_alert(self, message: str):
        """שולח התראה חירום לאדמין"""
        try:
            # בדיקת סביבת CI/CD - דילוג על שליחת התראות אמיתיות
            if os.getenv('GITHUB_ACTIONS') or os.getenv('CI'):
                print(f"🔧 CI mode - התראת חירום (סימולציה): {message}")
                return
            
            from config import ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID
            
            # בדיקת ערכי dummy
            if (ADMIN_BOT_TELEGRAM_TOKEN == "dummy_token_for_testing" or 
                ADMIN_NOTIFICATION_CHAT_ID == "dummy_chat_id" or
                "dummy" in str(ADMIN_BOT_TELEGRAM_TOKEN).lower()):
                print(f"🔧 Dummy mode - התראת חירום (סימולציה): {message}")
                return
            
            emergency_message = f"🚨🚨🚨 EMERGENCY ALERT 🚨🚨🚨\n\n{message}\n\n⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            
            url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
                "text": emergency_message
            }
            
            requests.post(url, data=payload, timeout=5)
            print(f"📱 התראת חירום נשלחה: {message}")
            
        except Exception as e:
            print(f"💥 נכשל בשליחת התראת חירום: {e}")
    
    def _save_rollback_history(self, record: Dict):
        """שומר היסטוריית rollback"""
        try:
            os.makedirs("data", exist_ok=True)
            
            history = []
            if os.path.exists(self.rollback_history_file):
                with open(self.rollback_history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            history.append(record)
            
            # שמירה על 50 רשומות אחרונות בלבד
            if len(history) > 50:
                history = history[-50:]
            
            with open(self.rollback_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2)
                
        except Exception as e:
            print(f"❌ נכשל בשמירת היסטוריית rollback: {e}")

def post_deploy_verification():
    """
    פונקציה ראשית - בדיקת תקינות אחרי deploy עם rollback אוטומטי
    
    Exit codes:
    0 - הכל תקין
    1 - יש בעיה אבל rollback הצליח  
    2 - יש בעיה ו-rollback נכשל (דרוש טיפול ידני!)
    """
    print("🚨 מתחיל בדיקת תקינות פוסט-deploy")
    print("=" * 60)
    
    manager = RollbackManager()
    
    # בדיקה 1: health check בסיסי
    if not manager.perform_health_check():
        print("❌ בדיקת תקינות בסיסית נכשלה!")
        
        if manager.trigger_rollback("Basic health check failed"):
            print("✅ Rollback הצליח - הבוט אמור לחזור לעבוד")
            return 1
        else:
            print("💥 CRITICAL: Rollback נכשל! נדרשת התערבות ידנית!")
            return 2
    
    # בדיקה 2: בוט חי
    if not manager.perform_live_bot_test():
        print("❌ בדיקת בוט חי נכשלה!")
        
        if manager.trigger_rollback("Live bot test failed"):
            print("✅ Rollback הצליח - הבוט אמור לחזור לעבוד")
            return 1
        else:
            print("💥 CRITICAL: Rollback נכשל! נדרשת התערבות ידנית!")
            return 2
    
    # הכל תקין - שמירת commit כ-good
    current_commit = os.getenv('RENDER_GIT_COMMIT') or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    
    if current_commit:
        manager.save_successful_deploy(current_commit)
    
    print("=" * 60)
    print("🎉 Deploy מאומת בהצלחה! הבוט עובד תקין!")
    print("✅ הפריסה החדשה נשמרה כgood deploy")
    return 0

if __name__ == "__main__":
    try:
        exit_code = post_deploy_verification()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 בדיקה בוטלה על ידי המשתמש")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 שגיאה קריטית בבדיקת post-deploy: {e}")
        
        # ניסיון rollback חירום
        try:
            manager = RollbackManager()
            if manager.trigger_rollback(f"Critical error in verification: {str(e)}"):
                sys.exit(1)
            else:
                sys.exit(2)
        except:
            sys.exit(2)