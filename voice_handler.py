"""
voice_handler.py
----------------
קובץ זה מטפל בהודעות קוליות מהמשתמשים באמצעות Whisper.

תכונות:
- תמלול הודעות קוליות לעברית
- שימוש ב-whisper לביצועים מהירים
- טיפול בשגיאות וניקוי קבצים זמניים
- לוגים מפורטים למעקב
- הודעות סטטוס מדורגות למשתמש

עלויות:
- חינמי לחלוטין (הרצה מקומית)
- אין עלויות API נוספות
- צריכת זיכרון נמוכה יחסית

שימוש:
1. המודל נטען אוטומטית בפעם הראשונה שמתקבלת הודעה קולית
2. כל הודעה קולית מתמללת לעברית
3. אם התמלול נכשל, נשלחת הודעה מתאימה למשתמש
4. הודעות סטטוס: 3s -> 7s -> 10s -> שגיאה
"""

import logging
import os
import tempfile
import subprocess  # נוסף: נדרש לבדיקת FFmpeg
from typing import Optional
import whisper
import asyncio
from telegram import Update
from telegram.ext import ContextTypes

# הגדרת לוגר
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoiceHandler:
    """מטפל בהודעות קול - מתמלל באמצעות Whisper"""
    
    def __init__(self):
        self.model = None
        self.model_loaded = False
        
        # תיקון FFmpeg PATH מיידי - חייב לפני כל שימוש בFFmpeg
        self._fix_ffmpeg_path_now()
        
        self._ensure_ffmpeg_available()
    
    def _is_ffmpeg_available(self):
        """בדיקה פשוטה אם FFmpeg זמין"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=3)
            return True
        except:
            return False
    
    def _fix_ffmpeg_path_now(self):
        """תיקון מיידי של FFmpeg PATH בWindows"""
        if os.name != 'nt':  # רק ב-Windows
            return True
            
        # בדיקה אם FFmpeg כבר זמין
        if self._is_ffmpeg_available():
            logging.info("[DEBUG] FFmpeg כבר זמין")
            return True
        
        try:
            # הנתיב הסטנדרטי של FFmpeg מ-winget
            username = os.environ.get('USERNAME', 'user')
            ffmpeg_path = f"C:\\Users\\{username}\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-7.1.1-full_build\\bin"
            
            if os.path.exists(ffmpeg_path):
                # הוסף ל-PATH של התהליך הנוכחי
                current_path = os.environ.get('PATH', '')
                if ffmpeg_path not in current_path:
                    os.environ['PATH'] = current_path + ';' + ffmpeg_path
                    logging.info(f"[DEBUG] הוספתי FFmpeg ל-PATH: {ffmpeg_path}")
                
                # בדק שוב
                if self._is_ffmpeg_available():
                    logging.info("[DEBUG] FFmpeg זמין עכשיו!")
                    return True
                else:
                    logging.warning("[WARNING] FFmpeg עדיין לא זמין אחרי הוספה ל-PATH")
                    return False
            else:
                logging.warning(f"[WARNING] FFmpeg לא נמצא ב: {ffmpeg_path}")
                return False
                
        except Exception as e:
            logging.error(f"[ERROR] שגיאה בתיקון FFmpeg PATH: {e}")
            return False
        
    def _ensure_ffmpeg_available(self):
        """
        בדיקה שFFmpeg זמין, ואם לא - ניסיון התקנה
        """
        import shutil
        import subprocess
        import sys
        
        # בדיקה ישירה אם FFmpeg זמין
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
            logging.info("[DEBUG] FFmpeg זמין במערכת")
            return True
        except:
            pass
        
        # נסה להוסיף FFmpeg לPATH בWindows אם הוא מותקן
        if os.name == 'nt':
            try:
                username = os.environ.get('USERNAME', 'user')
                ffmpeg_path = f"C:\\Users\\{username}\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-7.1.1-full_build\\bin"
                
                if os.path.exists(ffmpeg_path):
                    # הוסף ל-PATH של התהליך הנוכחי
                    current_path = os.environ.get('PATH', '')
                    if ffmpeg_path not in current_path:
                        os.environ['PATH'] = current_path + ';' + ffmpeg_path
                        logging.info(f"[DEBUG] הוספתי FFmpeg ל-PATH: {ffmpeg_path}")
                    
                    # בדק שוב
                    try:
                        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
                        logging.info("[DEBUG] FFmpeg זמין אחרי הוספה ל-PATH")
                        return True
                    except:
                        pass
                        
            except Exception as e:
                logging.warning(f"[WARNING] נכשל בהוספת FFmpeg ל-PATH: {e}")
        
        # אם shutil.which עדיין לא מוצא, אבל הוא כן עובד ישירות
        if shutil.which("ffmpeg"):
            logging.info("[DEBUG] FFmpeg זמין במערכת (shutil.which)")
            return True
        
        logging.warning("[WARNING] FFmpeg לא נמצא במערכת")
        logging.warning("[WARNING] FFmpeg לא נמצא ב-PATH")
        
        # התקנה עבור Windows
        try:
            if os.name == 'nt':  # Windows
                logging.info("[DEBUG] מזהה מערכת Windows - מנסה להתקין FFmpeg...")
                
                # ניסיון התקנה דרך winget (Windows Package Manager)
                try:
                    result = subprocess.run(['winget', 'install', 'FFmpeg'], 
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        logging.info("[DEBUG] FFmpeg הותקן בהצלחה דרך winget")
                        return True
                except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError) as e:
                    logging.warning(f"[WARNING] התקנה דרך winget נכשלה: {e}")
                
                # ניסיון התקנה דרך choco
                try:
                    result = subprocess.run(['choco', 'install', 'ffmpeg', '-y'], 
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        logging.info("[DEBUG] FFmpeg הותקן בהצלחה דרך chocolatey")
                        return True
                except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError) as e:
                    logging.warning(f"[WARNING] התקנה דרך chocolatey נכשלה: {e}")
                    
        except Exception as e:
            logging.error(f"[ERROR] שגיאה כללית בהתקנת FFmpeg ב-Windows: {e}")
        
        # ניסיון התקנה ב-Linux/Unix (סביבות פרודקשן)
        try:
            if os.name == 'posix':  # Linux/Unix
                logging.info("[DEBUG] מנסה להתקין FFmpeg ב-Linux...")
                subprocess.run(['apt-get', 'update'], check=True, capture_output=True, timeout=30)
                subprocess.run(['apt-get', 'install', '-y', 'ffmpeg'], check=True, capture_output=True, timeout=60)
                logging.info("[DEBUG] FFmpeg הותקן בהצלחה ב-Linux")
                return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logging.error(f"[ERROR] נכשל בהתקנת FFmpeg ב-Linux: {e}")
        except FileNotFoundError:
            logging.warning("[WARNING] apt-get לא זמין")
        
        # ניסיון התקנה דרך ffmpeg-python
        try:
            logging.info("[DEBUG] מנסה להתקין ffmpeg-python...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'ffmpeg-python'], timeout=60)
            
            # ניסיון נוסף להורדת FFmpeg binary
            import ffmpeg
            logging.info("[DEBUG] ffmpeg-python הותקן בהצלחה")
            
        except Exception as e:
            logging.error(f"[ERROR] נכשל בהתקנת ffmpeg-python: {e}")
        
        # בדיקה סופית
        if shutil.which("ffmpeg"):
            logging.info("[DEBUG] FFmpeg זמין אחרי התקנה")
            return True
        else:
            logging.error("[ERROR] FFmpeg עדיין לא זמין אחרי כל הניסיונות")
            return False
    
    async def load_model(self):
        """טוען את מודל Whisper"""
        try:
            logger.info("🔄 טוען מודל Whisper...")
            
            # שימוש במודל Whisper קטן יותר להורדה מהירה
            model_name = "tiny"  # מודל קטן יותר
            logger.info(f"📥 מוריד מודל: {model_name}")
            
            # טעינת המודל
            self.model = whisper.load_model(model_name)
            
            self.model_loaded = True
            logger.info("✅ מודל Whisper נטען בהצלחה!")
            
        except Exception as e:
            logger.error(f"❌ שגיאה בטעינת מודל Whisper: {e}")
            logger.error(f"❌ פרטי השגיאה: {type(e).__name__}: {str(e)}")
            self.model_loaded = False
    
    async def transcribe_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
        """
        מתמלל הודעה קולית לעברית עם הודעות סטטוס מדורגות
        
        Timeline:
        - 0s: "מעבד את ההודעה הקולית שלך"
        - 3s: עדכון לאותה הודעה
        - 7s: "רגע... זה לוקח לי קצת יותר זמן משחשבתי אני על זה.."
        - 10s: "🔧 לא הצלחתי לתמלל את ההודעה הקולית..."
        
        Args:
            update: אובייקט Update מ-Telegram
            context: Context מ-Telegram
            
        Returns:
            str: הטקסט המתומלל או None אם יש שגיאה
        """
        processing_msg = None
        status_tasks = []
        local_filename = None
        
        try:
            logging.info("[DEBUG] נכנס לפונקציית transcribe_voice_message")
            # בדיקה אם יש הודעה קולית
            if not update.message.voice:
                logging.info("[DEBUG] אין הודעה קולית ב-update.message.voice")
                return None
                
            # שליחת הודעת סטטוס ראשונה
            processing_msg = await update.message.reply_text("🎤 מעבד את ההודעה הקולית שלך...")
            logging.info("[DEBUG] שלחתי הודעת סטטוס ראשונה")
            
            # יצירת tasks לעדכוני סטטוס מדורגים
            async def update_status_after_3s():
                try:
                    await asyncio.sleep(3)
                    if processing_msg:
                        await processing_msg.edit_text("🎤 מעבד את ההודעה הקולית שלך...")
                        logging.info("[DEBUG] עדכון סטטוס אחרי 3 שניות")
                except asyncio.CancelledError:
                    logging.info("[DEBUG] Task של 3 שניות בוטל")
                except Exception as e:
                    logging.error(f"[ERROR] שגיאה בעדכון סטטוס 3s: {e}")
            
            async def update_status_after_7s():
                try:
                    await asyncio.sleep(7)
                    if processing_msg:
                        await processing_msg.edit_text("⏳ רגע... זה לוקח לי קצת יותר זמן משחשבתי אני על זה..")
                        logging.info("[DEBUG] עדכון סטטוס אחרי 7 שניות")
                except asyncio.CancelledError:
                    logging.info("[DEBUG] Task של 7 שניות בוטל")
                except Exception as e:
                    logging.error(f"[ERROR] שגיאה בעדכון סטטוס 7s: {e}")
            
            async def final_timeout_after_10s():
                try:
                    await asyncio.sleep(10)
                    if processing_msg:
                        await processing_msg.edit_text("🔧 לא הצלחתי לתמלל את ההודעה הקולית. אשמח אם תוכל לכתוב לי את זה בטקסט 😊")
                        logging.info("[DEBUG] timeout סופי אחרי 10 שניות")
                        
                        # שליחת הודעה לאדמין
                        try:
                            from notifications import send_error_notification
                            send_error_notification(
                                error_message=f"תמלול הודעה קולית נכשל - timeout 10s",
                                chat_id=update.message.chat_id,
                                user_msg="הודעה קולית"
                            )
                        except Exception as notify_err:
                            logging.error(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}")
                except asyncio.CancelledError:
                    logging.info("[DEBUG] Task של 10 שניות בוטל")
                except Exception as e:
                    logging.error(f"[ERROR] שגיאה בעדכון סטטוס 10s: {e}")
            
            # הפעלת כל ה-tasks
            status_tasks = [
                asyncio.create_task(update_status_after_3s()),
                asyncio.create_task(update_status_after_7s()),
                asyncio.create_task(final_timeout_after_10s())
            ]
            logging.info("[DEBUG] יצרתי כל tasks הסטטוס")
            
            # קבלת אובייקט הבוט
            bot = getattr(context, 'bot', None) or getattr(update, 'bot', None)
            logging.info(f"[DEBUG] bot instance: {str(bot)}")
            
            # בדיקה אם המודל נטען
            if not self.model_loaded:
                logging.info("[DEBUG] מודל לא נטען - מנסה לטעון כעת")
                await self.load_model()
                
            if not self.model_loaded:
                logging.error("[ERROR] לא הצלחתי לטעון את מודל Whisper")
                
                # ביטול כל tasks הסטטוס
                for task in status_tasks:
                    if not task.done():
                        task.cancel()
                logging.info("[DEBUG] ביטלתי כל tasks הסטטוס (מודל לא נטען)")
                
                # שליחת הודעה לאדמין
                try:
                    from notifications import send_error_notification
                    send_error_notification(
                        error_message="שגיאה בטעינת מודל Whisper - המודל לא נטען",
                        chat_id=update.message.chat_id,
                        user_msg="הודעה קולית"
                    )
                except Exception as notify_err:
                    logging.error(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}")
                
                # הודעה למשתמש
                await processing_msg.edit_text("🔧 יש בעיה טכנית עם מערכת התמלול. אשמח אם תוכל לכתוב לי את זה בטקסט 😊")
                return None
                
            # הורדת קובץ ה־voice
            file_id = update.message.voice.file_id
            logging.info(f"[DEBUG] file_id: {file_id}")
            file = await bot.get_file(file_id)
            file_path = file.file_path
            logging.info(f"[DEBUG] file_path: {file_path}")
            
            # שימוש בנתיב מלא לקובץ
            current_dir = os.getcwd()
            local_filename = os.path.join(current_dir, f"voice_{update.message.message_id}.ogg")
            logging.info(f"[DEBUG] נתיב מלא לקובץ: {local_filename}")
            
            # וידוא שתיקיית הבסיס קיימת
            os.makedirs(os.path.dirname(local_filename), exist_ok=True)
            
            # הורדת הקובץ עם try-catch מפורט
            try:
                logging.info(f"[DEBUG] מתחיל הורדת קובץ...")
                await file.download_to_drive(local_filename)
                logging.info(f"[DEBUG] הורדתי קובץ קול ל־{local_filename}")
            except Exception as download_error:
                logging.error(f"[ERROR] שגיאה בהורדת קובץ: {download_error}")
                # ניסיון חלופי עם שם קובץ פשוט יותר
                simple_filename = f"voice_{update.message.message_id}.ogg"
                logging.info(f"[DEBUG] מנסה שם קובץ פשוט: {simple_filename}")
                await file.download_to_drive(simple_filename)
                local_filename = os.path.join(current_dir, simple_filename)
                logging.info(f"[DEBUG] הורדתי קובץ קול ל־{local_filename} (ניסיון שני)")
            
            # בדיקה מפורטת שהקובץ קיים
            logging.info(f"[DEBUG] בודק אם קובץ קיים: {local_filename}")
            logging.info(f"[DEBUG] תיקיית עבודה נוכחית: {os.getcwd()}")
            logging.info(f"[DEBUG] תוכן תיקייה: {os.listdir('.')}")
            
            if not os.path.exists(local_filename):
                logging.error(f"[ERROR] הקובץ לא קיים אחרי ההורדה: {local_filename}")
                # חיפוש קבצי קול בתיקייה
                voice_files = [f for f in os.listdir('.') if f.startswith('voice_')]
                logging.info(f"[DEBUG] קבצי קול שנמצאו: {voice_files}")
                raise FileNotFoundError(f"הקובץ לא קיים: {local_filename}")
            
            file_size = os.path.getsize(local_filename)
            logging.info(f"[DEBUG] גודל הקובץ: {file_size} bytes")
            
            if file_size == 0:
                logging.error(f"[ERROR] הקובץ ריק: {local_filename}")
                raise ValueError("הקובץ הקולי ריק")
            
            # בדיקה חובה של FFmpeg לפני תמלול - פשוט ויעיל
            logging.info("[DEBUG] בודק זמינות FFmpeg לפני תמלול...")
            
            # אם FFmpeg לא זמין - תקן מיד
            if not self._is_ffmpeg_available():
                logging.warning("[WARNING] FFmpeg לא זמין - מתקן...")
                self._fix_ffmpeg_path_now()
                
                # בדיקה סופית
                if not self._is_ffmpeg_available():
                    logging.error("[ERROR] FFmpeg עדיין לא זמין אחרי התיקון")
                    raise RuntimeError("FFmpeg לא זמין - לא ניתן לתמלל הודעות קול")
                    
            logging.info("[DEBUG] FFmpeg זמין - מתקדם לתמלול")
            
            # ביטול כל tasks הסטטוס כי התמלול מתחיל
            for task in status_tasks:
                if not task.done():
                    task.cancel()
            logging.info("[DEBUG] ביטלתי כל tasks הסטטוס (התמלול מתחיל)")
            
            # התחלת תמלול
            logging.info(f"[DEBUG] מתחיל תמלול קובץ: {local_filename}")
            logging.info(f"[DEBUG] נתיב מוחלט לקובץ: {os.path.abspath(local_filename)}")
            
            # ניסיון עם נתיב מוחלט
            absolute_path = os.path.abspath(local_filename)
            logging.info(f"[DEBUG] בדיקה אחרונה שהקובץ קיים ברגע התמלול: {os.path.exists(absolute_path)}")
            
            # עדכון סטטוס שהתמלול התחיל
            try:
                await processing_msg.edit_text("🔄 מתמלל כעת...")
                logging.info("[DEBUG] עדכנתי סטטוס לתמלול")
            except Exception as e:
                logging.warning(f"[WARNING] לא הצלחתי לעדכן סטטוס תמלול: {e}")
            
            # תמלול עם try-catch מפורט
            try:
                logging.info(f"[DEBUG] קורא ל-model.transcribe עם: {absolute_path}")
                result = self.model.transcribe(absolute_path, language="he")
                logging.info(f"[DEBUG] תמלול הסתיים בהצלחה")
                text = result["text"].strip()
                logging.info(f"[DEBUG] תמלול: {text}")
            except Exception as transcribe_error:
                logging.error(f"[ERROR] שגיאה בתמלול ישירות: {transcribe_error}")
                logging.error(f"[ERROR] סוג שגיאת תמלול: {type(transcribe_error).__name__}")
                raise transcribe_error
            
            # בדיקה שהתמלול לא ריק
            if not text:
                logging.warning("[WARNING] התמלול ריק")
                raise ValueError("התמלול החזיר תוצאה ריקה")
            
            # מחיקת הודעת הסטטוס והצגת התמלול
            try:
                await processing_msg.delete()
                logging.info("[DEBUG] מחקתי הודעת processing")
            except Exception as e:
                logging.warning(f"[WARNING] לא הצלחתי למחוק הודעת processing: {e}")
            
            await update.message.reply_text(f"📝 התמלול: {text}")
            logging.info("[DEBUG] שלחתי את התמלול למשתמש")
            
            # ניקוי קובץ זמני
            try:
                if os.path.exists(local_filename):
                    os.remove(local_filename)
                    logging.info(f"[DEBUG] קובץ זמני נמחק: {local_filename}")
            except Exception as e:
                logging.warning(f"[WARNING] לא הצלחתי למחוק קובץ זמני: {e}")
            
            return text
            
        except Exception as e:
            logging.error(f"[ERROR] חריגה בתמלול: {e}")
            logging.error(f"[ERROR] סוג השגיאה: {type(e).__name__}")
            
            # ביטול כל tasks הסטטוס במקרה של שגיאה
            for task in status_tasks:
                if not task.done():
                    try:
                        task.cancel()
                    except Exception:
                        pass
            logging.info("[DEBUG] ביטלתי כל tasks הסטטוס (שגיאה)")
            
            # ניקוי קובץ זמני במקרה של שגיאה
            try:
                if local_filename and os.path.exists(local_filename):
                    os.remove(local_filename)
                    logging.info(f"[DEBUG] קובץ זמני נמחק אחרי שגיאה: {local_filename}")
            except Exception as cleanup_err:
                logging.warning(f"[WARNING] לא הצלחתי למחוק קובץ זמני אחרי שגיאה: {cleanup_err}")
            
            # הודעה למשתמש במקרה של שגיאה
            try:
                if processing_msg:
                    await processing_msg.edit_text("🔧 לא הצלחתי לתמלל את ההודעה הקולית. אשמח אם תוכל לכתוב לי את זה בטקסט 😊")
                    logging.info("[DEBUG] שלחתי הודעת שגיאה למשתמש")
                else:
                    await update.message.reply_text("🔧 לא הצלחתי לתמלל את ההודעה הקולית. אשמח אם תוכל לכתוב לי את זה בטקסט 😊")
                    logging.info("[DEBUG] שלחתי הודעת שגיאה למשתמש (fallback)")
            except Exception as msg_err:
                logging.error(f"[ERROR] לא הצלחתי לשלוח הודעת שגיאה למשתמש: {msg_err}")
            
            # שליחת הודעה לאדמין על השגיאה
            try:
                from notifications import send_error_notification
                send_error_notification(
                    error_message=f"שגיאה בתמלול הודעה קולית: {type(e).__name__}: {str(e)}",
                    chat_id=update.message.chat_id,
                    user_msg="הודעה קולית"
                )
            except Exception as notify_err:
                logging.error(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}")
            
            return None

# יצירת instance גלובלי
voice_handler = VoiceHandler() 