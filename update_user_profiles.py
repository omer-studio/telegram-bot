#!/usr/bin/env python3
"""
update_user_profiles.py
======================
עדכון פרופילי משתמשים במסד הנתונים על בסיס הניתוח

🚀 איך להריץ:
1. הרץ קודם את comprehensive_user_analyzer.py
2. בדוק את התוצאות בקובץ JSON
3. הרץ את הסקריפט הזה עם אישור לכל עדכון
"""

import json
import psycopg2
from datetime import datetime
from config import config
from utils import safe_str, get_logger

logger = get_logger(__name__)

# יבוא של FIELDS_DICT
try:
    from fields_dict import FIELDS_DICT, get_user_profile_fields
    # 🗑️ עברנו למסד נתונים - אין צורך ב-Google Sheets!
    # from sheets_handler import update_user_profile, get_user_summary
    from profile_utils import update_user_profile_fast, get_user_summary_fast, get_user_profile
except ImportError:
    print("⚠️ לא ניתן לייבא חלק מהמודולים - חלק מהפונקציות לא יעבדו")

# הגדרת חיבור למסד הנתונים
DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

class UserProfileUpdater:
    def __init__(self, analysis_file='user_analysis_comprehensive.json'):
        """אתחול מעדכן הפרופילים"""
        self.analysis_file = analysis_file
        self.analysis_data = None
        self.updates_log = []
        
    def load_analysis_results(self):
        """טעינת תוצאות הניתוח"""
        try:
            with open(self.analysis_file, 'r', encoding='utf-8') as f:
                self.analysis_data = json.load(f)
            print(f"✅ נטענו תוצאות ניתוח מ-{self.analysis_file}")
            return True
        except FileNotFoundError:
            print(f"❌ לא נמצא קובץ ניתוח: {self.analysis_file}")
            print("   הרץ קודם: python comprehensive_user_analyzer.py")
            return False
        except Exception as e:
            print(f"❌ שגיאה בטעינת הניתוח: {e}")
            return False
    
    def connect_db(self):
        """חיבור למסד הנתונים"""
        try:
            return psycopg2.connect(DB_URL)
        except Exception as e:
            print(f"❌ שגיאה בחיבור למסד הנתונים: {e}")
            return None
    
    # 🗑️ הפונקציה הוסרה - משתמשים בייבוא מ-profile_utils
    
    def update_profile_field(self, chat_id, field_name, new_value, old_value=None):
        """עדכון שדה בפרופיל"""
        conn = self.connect_db()
        if not conn:
            return False
        
        try:
            cur = conn.cursor()
            
            # בדיקה אם הפרופיל קיים
            cur.execute("SELECT id FROM user_profiles WHERE chat_id = %s", (safe_str(chat_id),))
            profile_exists = cur.fetchone() is not None
            
            if profile_exists:
                # עדכון שדה קיים
                cur.execute(f"""
                    UPDATE user_profiles 
                    SET {field_name} = %s, updated_at = %s 
                    WHERE chat_id = %s
                """, (new_value, datetime.utcnow(), safe_str(chat_id)))
            else:
                # יצירת פרופיל חדש
                cur.execute(f"""
                    INSERT INTO user_profiles (chat_id, {field_name}, updated_at) 
                    VALUES (%s, %s, %s)
                """, (safe_str(chat_id), new_value, datetime.utcnow()))
            
            conn.commit()
            cur.close()
            conn.close()
            
            # רישום העדכון
            self.updates_log.append({
                'chat_id': chat_id,
                'field': field_name,
                'old_value': old_value,
                'new_value': new_value,
                'timestamp': datetime.now().isoformat(),
                'action': 'update' if profile_exists else 'create'
            })
            
            return True
        except Exception as e:
            print(f"❌ שגיאה בעדכון שדה {field_name} עבור {chat_id}: {e}")
            if conn:
                conn.close()
            return False
    
    def generate_user_summary(self, chat_id, profile_data, insights):
        """יצירת סיכום משתמש"""
        summary_parts = []
        
        # מידע בסיסי מהפרופיל
        if profile_data.get('filled_fields'):
            filled = profile_data['filled_fields']
            
            # שם וגיל
            if 'name' in filled:
                summary_parts.append(f"שמו {filled['name']}")
            if 'age' in filled:
                summary_parts.append(f"בן {filled['age']}")
            elif 'discovered_age' in insights:
                summary_parts.append(f"בן {insights['discovered_age']}")
            
            # מצב משפחתי
            if 'relationship_type' in filled:
                summary_parts.append(f"מצב משפחתי: {filled['relationship_type']}")
            elif 'discovered_relationship' in insights:
                summary_parts.append(f"מצב משפחתי: {insights['discovered_relationship']}")
            
            # דתיות
            if 'self_religiosity_level' in filled:
                summary_parts.append(f"רמת דתיות: {filled['self_religiosity_level']}")
            elif 'discovered_religiosity' in insights:
                summary_parts.append(f"רמת דתיות: {insights['discovered_religiosity']}")
            
            # מצב ארון
            if 'closet_status' in filled:
                summary_parts.append(f"מצב ארון: {filled['closet_status']}")
            elif 'discovered_closet_status' in insights:
                summary_parts.append(f"מצב ארון: {insights['discovered_closet_status']}")
            
            # קונפליקט עיקרי
            if 'primary_conflict' in filled:
                summary_parts.append(f"קונפליקט מרכזי: {filled['primary_conflict'][:100]}...")
            elif 'discovered_conflict' in insights:
                summary_parts.append(f"קונפליקט מרכזי: {insights['discovered_conflict'][:100]}...")
        
        # מידע מההיסטוריה
        summary_parts.append("משתמש פעיל בצ'אט")
        
        return ". ".join(summary_parts) if summary_parts else "משתמש ללא מידע מפורט"
    
    def process_recommendations_for_user(self, chat_id, interactive=True):
        """עיבוד המלצות למשתמש בודד"""
        if not self.analysis_data:
            print("❌ לא נטענו נתוני ניתוח")
            return False
        
        user_data = self.analysis_data.get('detailed_results', {}).get(chat_id)
        if not user_data:
            print(f"❌ לא נמצאו נתונים עבור משתמש {chat_id}")
            return False
        
        recommendations = user_data.get('recommendations', [])
        if not recommendations:
            print(f"✅ אין המלצות עבור משתמש {chat_id}")
            return True
        
        print(f"\n{'='*50}")
        print(f"👤 עיבוד המלצות עבור משתמש {chat_id}")
        print(f"{'='*50}")
        
        # הצגת סיכום המשתמש
        chat_history = user_data.get('chat_history', {})
        profile_data = user_data.get('profile_data', {})
        insights = user_data.get('discovered_insights', {})
        
        print(f"📊 סיכום משתמש:")
        print(f"  📈 הודעות: {chat_history.get('total_messages', 0)}")
        if chat_history.get('first_message_date'):
            print(f"  📅 תחילת שיחה: {chat_history['first_message_date'][:10]}")
        print(f"  👤 פרופיל קיים: {'✅' if profile_data.get('exists') else '❌'}")
        if profile_data.get('exists'):
            completion = user_data.get('completion_analysis', {}).get('completion_rate', 0)
            print(f"  📋 שלמות פרופיל: {completion}%")
        
        if insights:
            print(f"  🔍 מידע שהתגלה: {', '.join(insights.keys())}")
        
        # עיבוד כל המלצה
        updated_count = 0
        for i, rec in enumerate(recommendations, 1):
            print(f"\n💡 המלצה {i}/{len(recommendations)}:")
            print(f"   📝 {rec.get('description', 'לא ידוע')}")
            print(f"   ⚡ עדיפות: {rec.get('priority', 'לא ידוע')}")
            
            if rec.get('type') == 'add_field':
                field = rec.get('field')
                suggested_value = rec.get('suggested_value')
                
                print(f"   🎯 שדה: {field}")
                print(f"   💎 ערך מוצע: {suggested_value}")
                
                if interactive:
                    response = input(f"   ❓ לבצע עדכון? (y/n/s=דלג): ").lower()
                    if response == 'y':
                        if self.update_profile_field(chat_id, field, suggested_value):
                            print(f"   ✅ שדה {field} עודכן בהצלחה")
                            updated_count += 1
                        else:
                            print(f"   ❌ כשל בעדכון שדה {field}")
                    elif response == 's':
                        print(f"   ⏭️ דילוג על עדכון זה")
                    else:
                        print(f"   🚫 עדכון בוטל")
                else:
                    # מצב אוטומטי - עדכן רק שדות בעדיפות גבוהה
                    if rec.get('priority') == 'high':
                        if self.update_profile_field(chat_id, field, suggested_value):
                            print(f"   ✅ שדה {field} עודכן אוטומטית")
                            updated_count += 1
                        else:
                            print(f"   ❌ כשל בעדכון אוטומטי של שדה {field}")
                    else:
                        print(f"   ⏭️ דילוג (עדיפות נמוכה במצב אוטומטי)")
            
            elif rec.get('type') == 'check_discrepancy':
                field = rec.get('field')
                current = rec.get('current_value')
                suggested = rec.get('suggested_value')
                
                print(f"   ⚠️ סתירה בשדה: {field}")
                print(f"   📋 ערך נוכחי: {current}")
                print(f"   🔍 ערך שהתגלה: {suggested}")
                
                if interactive:
                    print(f"   🤔 אפשרויות:")
                    print(f"      1. השאר ערך נוכחי ({current})")
                    print(f"      2. עדכן לערך חדש ({suggested})")
                    print(f"      3. דלג על החלטה")
                    
                    choice = input(f"   ❓ בחר (1/2/3): ").strip()
                    if choice == '2':
                        if self.update_profile_field(chat_id, field, suggested, current):
                            print(f"   ✅ שדה {field} עודכן מ-'{current}' ל-'{suggested}'")
                            updated_count += 1
                        else:
                            print(f"   ❌ כשל בעדכון שדה {field}")
                    elif choice == '3':
                        print(f"   ⏭️ דילוג על החלטה")
                    else:
                        print(f"   📌 נשאר ערך נוכחי: {current}")
                else:
                    print(f"   ⏭️ דילוג על סתירה במצב אוטומטי")
            
            elif rec.get('type') == 'create_summary':
                print(f"   📝 יצירת סיכום נדרשת")
                
                if interactive:
                    response = input(f"   ❓ ליצור סיכום אוטומטי? (y/n): ").lower()
                    if response == 'y':
                        summary = self.generate_user_summary(chat_id, profile_data, insights)
                        print(f"   📄 סיכום שנוצר: {summary[:200]}...")
                        
                        confirm = input(f"   ❓ לשמור סיכום זה? (y/n): ").lower()
                        if confirm == 'y':
                            if self.update_profile_field(chat_id, 'summary', summary):
                                print(f"   ✅ סיכום נשמר בהצלחה")
                                updated_count += 1
                            else:
                                print(f"   ❌ כשל בשמירת הסיכום")
                        else:
                            print(f"   🚫 סיכום לא נשמר")
                    else:
                        print(f"   🚫 יצירת סיכום בוטלה")
                else:
                    # יצירת סיכום אוטומטית
                    summary = self.generate_user_summary(chat_id, profile_data, insights)
                    if self.update_profile_field(chat_id, 'summary', summary):
                        print(f"   ✅ סיכום נוצר ונשמר אוטומטית")
                        updated_count += 1
                    else:
                        print(f"   ❌ כשל ביצירת סיכום אוטומטי")
        
        print(f"\n📊 סיכום עדכונים עבור משתמש {chat_id}:")
        print(f"   ✅ עודכנו: {updated_count} שדות")
        print(f"   📋 מתוך: {len(recommendations)} המלצות")
        
        return updated_count > 0
    
    def process_all_users(self, interactive=True):
        """עיבוד כל המשתמשים"""
        if not self.analysis_data:
            if not self.load_analysis_results():
                return False
        
        detailed_results = self.analysis_data.get('detailed_results', {})
        
        print(f"🚀 מתחיל עיבוד עדכונים עבור {len(detailed_results)} משתמשים")
        print(f"🔧 מצב: {'אינטראקטיבי' if interactive else 'אוטומטי'}")
        
        total_updated_users = 0
        total_updates = 0
        
        for chat_id in detailed_results.keys():
            try:
                if self.process_recommendations_for_user(chat_id, interactive):
                    total_updated_users += 1
                
                updates_for_user = len([log for log in self.updates_log if log['chat_id'] == chat_id])
                total_updates += updates_for_user
                
                if interactive and chat_id != list(detailed_results.keys())[-1]:
                    input("\n⏯️ לחץ Enter להמשיך למשתמש הבא...")
                
            except KeyboardInterrupt:
                print(f"\n⏹️ העיבוד הופסק על ידי המשתמש")
                break
            except Exception as e:
                print(f"❌ שגיאה בעיבוד משתמש {chat_id}: {e}")
        
        print(f"\n{'='*60}")
        print(f"🎉 עיבוד הושלם!")
        print(f"📊 סיכום:")
        print(f"   👥 משתמשים שעודכנו: {total_updated_users}")
        print(f"   📝 סה״כ עדכונים: {total_updates}")
        
        return True
    
    def save_updates_log(self, filename=None):
        """שמירת לוג העדכונים"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'user_updates_log_{timestamp}.json'
        
        log_data = {
            'update_session': {
                'timestamp': datetime.now().isoformat(),
                'total_updates': len(self.updates_log),
                'updated_users': len(set(log['chat_id'] for log in self.updates_log))
            },
            'updates': self.updates_log
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        
        print(f"📄 לוג עדכונים נשמר ב-{filename}")
        return filename

def main():
    """פונקציה ראשית"""
    import sys
    
    print("🔧 מעדכן פרופילי משתמשים")
    print("="*40)
    
    # בדיקת ארגומנטים
    interactive = True
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        interactive = False
        print("🤖 מצב אוטומטי - יעדכן רק שדות בעדיפות גבוהה")
    else:
        print("👤 מצב אינטראקטיבי - תתבקש לאשר כל עדכון")
    
    # יצירת מעדכן
    updater = UserProfileUpdater()
    
    # טעינת נתוני הניתוח
    if not updater.load_analysis_results():
        return
    
    # עיבוד כל המשתמשים
    if updater.process_all_users(interactive):
        # שמירת לוג העדכונים
        updater.save_updates_log()
        
        print(f"\n✅ כל העדכונים הושלמו בהצלחה!")
        print(f"📋 עכשיו רצוי להריץ: python comprehensive_deploy_check.py")
    else:
        print(f"\n❌ היו בעיות בעיבוד העדכונים")

if __name__ == "__main__":
    main() 