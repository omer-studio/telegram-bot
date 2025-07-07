#!/usr/bin/env python3
"""
comprehensive_user_analyzer.py
=============================
ניתוח מקיף של משתמשים - להרצה על השרת עם גישה למסד הנתונים

🚀 איך להריץ:
1. העלה את הקובץ לשרת רנדר
2. הרץ: python comprehensive_user_analyzer.py
3. הקובץ יקרא את כל הנתונים ויצור דוח JSON מפורט
"""

import json
import psycopg2
from datetime import datetime
import re
from config import config

# יבוא של FIELDS_DICT
try:
    from fields_dict import FIELDS_DICT, get_user_profile_fields
except ImportError:
    # נגדיר באופן בסיסי אם אין גישה לקובץ
    FIELDS_DICT = {}
    def get_user_profile_fields():
        return ['name', 'age', 'relationship_type', 'closet_status', 'primary_conflict', 'summary']

# הגדרת חיבור למסד הנתונים
DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

class UserAnalyzer:
    def __init__(self):
        """אתחול המנתח"""
        self.users_to_analyze = [
            "1118251087",
            "179392777", 
            "5676571979",
            "7957193610",
            "5526006524",
            "7186596694"
        ]
        self.results = {}
        
    def connect_db(self):
        """חיבור למסד הנתונים"""
        try:
            return psycopg2.connect(DB_URL)
        except Exception as e:
            print(f"❌ שגיאה בחיבור למסד הנתונים: {e}")
            return None
    
    def get_user_chat_history(self, chat_id, limit=200):
        """קבלת היסטוריית צ'אט של משתמש"""
        conn = self.connect_db()
        if not conn:
            return []
        
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT user_msg, bot_msg, timestamp 
                FROM chat_messages 
                WHERE chat_id = %s 
                ORDER BY timestamp ASC
                LIMIT %s
            """, (str(chat_id), limit))
            
            history = cur.fetchall()
            cur.close()
            conn.close()
            return history
        except Exception as e:
            print(f"❌ שגיאה בקבלת היסטוריה עבור {chat_id}: {e}")
            if conn:
                conn.close()
            return []
    
    def get_user_profile(self, chat_id):
        """קבלת פרופיל משתמש"""
        conn = self.connect_db()
        if not conn:
            return None
        
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM user_profiles 
                WHERE chat_id = %s
            """, (str(chat_id),))
            
            profile_row = cur.fetchone()
            
            if profile_row and cur.description:
                # קבלת שמות העמודות
                column_names = [desc[0] for desc in cur.description]
                profile = dict(zip(column_names, profile_row))
                cur.close()
                conn.close()
                return profile
            else:
                cur.close()
                conn.close()
                return None
        except Exception as e:
            print(f"❌ שגיאה בקבלת פרופיל עבור {chat_id}: {e}")
            if conn:
                conn.close()
            return None
    
    def extract_insights_from_text(self, text):
        """חילוץ תובנות מטקסט הודעות המשתמש"""
        if not text:
            return {}
        
        text_lower = text.lower()
        insights = {}
        
        # חיפוש גיל
        age_patterns = [
            r'בן (\d+)', r'בת (\d+)', r'אני (\d+)', r'גיל (\d+)', 
            r'(\d+) שנים', r'(\d+) שנה', r'אני בן (\d+)', r'אני בת (\d+)',
            r'הגיל שלי (\d+)', r'בגיל (\d+)'
        ]
        
        for pattern in age_patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    age = int(matches[0])
                    if 18 <= age <= 99:
                        insights['discovered_age'] = age
                        break
                except ValueError:
                    continue
        
        # חיפוש שם
        name_patterns = [
            r'קוראים לי ([א-ת]+)', r'השם שלי ([א-ת]+)', r'אני ([א-ת]+)',
            r'השם ([א-ת]+)', r'שמי ([א-ת]+)', r'אני ([א-ת]+) ו'
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text)
            if matches:
                name = matches[0]
                if len(name) > 2 and name not in ['אני', 'זה', 'כמו', 'עם']:
                    insights['discovered_name'] = name
                    break
        
        # חיפוש מצב משפחתי
        relationship_keywords = {
            'רווק': ['רווק', 'לא נשוי', 'לא נשואה', 'יחיד'],
            'נשוי': ['נשוי', 'נשואה', 'אישה שלי', 'הבעל שלי', 'הבעל', 'האישה'],
            'גרוש': ['גרוש', 'גרושה', 'התגרשתי', 'התגרשנו'],
            'בזוגיות': ['בזוגיות', 'חבר שלי', 'חברה שלי', 'בן זוג', 'בת זוג', 'במערכת יחסים']
        }
        
        for status, keywords in relationship_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                insights['discovered_relationship'] = status
                break
        
        # חיפוש מידע דתי
        religious_keywords = {
            'חילוני': ['חילוני', 'חילונית', 'לא דתי', 'לא דתית', 'אתאיסט'],
            'דתי': ['דתי', 'דתית', 'מאמין', 'מאמינה', 'שומר מצוות'],
            'מסורתי': ['מסורתי', 'מסורתית', 'קצת דתי'],
            'חרדי': ['חרדי', 'חרדית', 'אורתודוכסי']
        }
        
        for level, keywords in religious_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                insights['discovered_religiosity'] = level
                break
        
        # חיפוש מידע על ארון
        closet_keywords = {
            'בארון': ['בארון', 'לא יודעים עליי', 'סודי', 'מסתיר', 'נשמר בסוד', 'אף אחד לא יודע'],
            'יצא_מהארון': ['יצאתי מהארון', 'כולם יודעים', 'פתוח', 'לא מסתיר', 'יודעים עליי'],
            'חלקית': ['חלק יודעים', 'לא כולם יודעים', 'בחלקיות', 'רק חלק מהאנשים']
        }
        
        for status, keywords in closet_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                insights['discovered_closet_status'] = status
                break
        
        # חיפוש מידע על עיסוק
        occupation_patterns = [
            r'אני עובד ([^\.]+)', r'אני עובדת ([^\.]+)', r'אני סטודנט ([^\.]+)',
            r'המקצוע שלי ([^\.]+)', r'אני ([^\.]*(?:רופא|מהנדס|עורך דין|מורה|מנהל))',
            r'עובד ב([^\.]+)', r'לומד ([^\.]+)'
        ]
        
        for pattern in occupation_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                insights['discovered_occupation'] = matches[0].strip()
                break
        
        # חיפוש קונפליקטים עיקריים
        conflict_keywords = [
            'הבעיה הכי גדולה', 'מה שמטריד אותי', 'הדבר הכי קשה',
            'נאבק עם', 'מתמודד עם', 'הקושי שלי', 'הפחד שלי'
        ]
        
        for keyword in conflict_keywords:
            if keyword in text_lower:
                # נסה למצוא המשך המשפט
                start_idx = text_lower.find(keyword)
                if start_idx != -1:
                    end_idx = text_lower.find('.', start_idx)
                    if end_idx == -1:
                        end_idx = start_idx + 100
                    conflict_text = text[start_idx:end_idx]
                    insights['discovered_conflict'] = conflict_text.strip()
                    break
        
        return insights
    
    def analyze_single_user(self, chat_id):
        """ניתוח משתמש בודד"""
        print(f"\n🔍 מנתח משתמש {chat_id}")
        
        result = {
            'chat_id': chat_id,
            'analysis_timestamp': datetime.now().isoformat(),
            'chat_history': {},
            'profile_data': {},
            'discovered_insights': {},
            'recommendations': [],
            'completion_analysis': {}
        }
        
        # שלב 1: קבלת היסטוריית צ'אט
        print(f"  📊 קורא היסטוריית צ'אט...")
        history = self.get_user_chat_history(chat_id)
        
        if history:
            result['chat_history'] = {
                'total_messages': len(history),
                'first_message_date': history[0][2].isoformat() if history[0][2] else None,
                'last_message_date': history[-1][2].isoformat() if history[-1][2] else None,
                'sample_messages': []
            }
            
            # חילוץ הודעות המשתמש
            user_messages = []
            sample_count = 0
            for user_msg, bot_msg, timestamp in history:
                if user_msg:
                    user_messages.append(user_msg)
                    if sample_count < 5:  # שמירת 5 דוגמאות
                        result['chat_history']['sample_messages'].append({
                            'message': user_msg[:200] + "..." if len(user_msg) > 200 else user_msg,
                            'timestamp': timestamp.isoformat() if timestamp else None
                        })
                        sample_count += 1
            
            # ניתוח תוכן ההודעות
            all_user_text = " ".join(user_messages)
            result['discovered_insights'] = self.extract_insights_from_text(all_user_text)
            
            print(f"    ✅ נמצאו {len(history)} הודעות")
            if result['discovered_insights']:
                print(f"    🔍 מידע שהתגלה: {list(result['discovered_insights'].keys())}")
        else:
            print(f"    ❌ לא נמצאה היסטוריה")
        
        # שלב 2: קבלת פרופיל קיים
        print(f"  👤 קורא פרופיל קיים...")
        profile = self.get_user_profile(chat_id)
        
        if profile:
            result['profile_data'] = {
                'exists': True,
                'filled_fields': {},
                'empty_fields': [],
                'summary_exists': bool(profile.get('summary', '').strip())
            }
            
            # ניתוח שדות הפרופיל
            profile_fields = get_user_profile_fields()
            for field in profile_fields:
                if field in profile and profile[field] and str(profile[field]).strip():
                    result['profile_data']['filled_fields'][field] = str(profile[field])
                else:
                    result['profile_data']['empty_fields'].append(field)
            
            completion_rate = len(result['profile_data']['filled_fields']) / len(profile_fields) * 100
            result['completion_analysis'] = {
                'completion_rate': round(completion_rate, 1),
                'filled_count': len(result['profile_data']['filled_fields']),
                'total_count': len(profile_fields)
            }
            
            print(f"    ✅ פרופיל קיים - שלמות: {completion_rate:.1f}%")
        else:
            result['profile_data'] = {'exists': False}
            result['completion_analysis'] = {'completion_rate': 0, 'filled_count': 0, 'total_count': len(get_user_profile_fields())}
            print(f"    ❌ אין פרופיל קיים")
        
        # שלב 3: השוואה והמלצות
        print(f"  🔄 מכין המלצות...")
        recommendations = self.generate_recommendations(result['discovered_insights'], result['profile_data'])
        result['recommendations'] = recommendations
        
        if recommendations:
            print(f"    💡 {len(recommendations)} המלצות נוצרו")
        else:
            print(f"    ✅ אין המלצות - הפרופיל מעודכן")
        
        return result
    
    def generate_recommendations(self, insights, profile_data):
        """יצירת המלצות על בסיס ההשוואה"""
        recommendations = []
        
        if not profile_data.get('exists'):
            recommendations.append({
                'type': 'create_profile',
                'priority': 'high',
                'description': 'יש ליצור פרופיל למשתמש זה',
                'suggested_data': insights
            })
            return recommendations
        
        filled_fields = profile_data.get('filled_fields', {})
        
        # בדיקת כל insight מול הפרופיל הקיים
        field_mapping = {
            'discovered_age': 'age',
            'discovered_name': 'name',
            'discovered_relationship': 'relationship_type',
            'discovered_religiosity': 'self_religiosity_level',
            'discovered_closet_status': 'closet_status',
            'discovered_occupation': 'occupation_or_role',
            'discovered_conflict': 'primary_conflict'
        }
        
        for insight_key, field_name in field_mapping.items():
            if insight_key in insights:
                discovered_value = insights[insight_key]
                current_value = filled_fields.get(field_name)
                
                if not current_value:
                    # שדה ריק - צריך להוסיף
                    recommendations.append({
                        'type': 'add_field',
                        'priority': 'medium',
                        'field': field_name,
                        'current_value': None,
                        'suggested_value': discovered_value,
                        'description': f'להוסיף {field_name}: {discovered_value}'
                    })
                elif str(discovered_value).lower() not in str(current_value).lower():
                    # יש סתירה - צריך לבדוק
                    recommendations.append({
                        'type': 'check_discrepancy',
                        'priority': 'high',
                        'field': field_name,
                        'current_value': current_value,
                        'suggested_value': discovered_value,
                        'description': f'סתירה ב{field_name}: פרופיל "{current_value}" vs היסטוריה "{discovered_value}"'
                    })
        
        # בדיקת סיכום
        if not profile_data.get('summary_exists'):
            recommendations.append({
                'type': 'create_summary',
                'priority': 'medium',
                'description': 'חסר סיכום למשתמש - יש ליצור',
                'suggested_summary_base': insights
            })
        
        return recommendations
    
    def analyze_all_users(self):
        """ניתוח כל המשתמשים"""
        print("🚀 מתחיל ניתוח מקיף של משתמשים")
        print(f"👥 {len(self.users_to_analyze)} משתמשים לניתוח")
        print("="*60)
        
        for chat_id in self.users_to_analyze:
            try:
                result = self.analyze_single_user(chat_id)
                self.results[chat_id] = result
            except Exception as e:
                print(f"❌ שגיאה בניתוח משתמש {chat_id}: {e}")
                self.results[chat_id] = {
                    'chat_id': chat_id,
                    'error': str(e),
                    'analysis_timestamp': datetime.now().isoformat()
                }
        
        return self.results
    
    def generate_summary_report(self):
        """יצירת דוח מסכם"""
        print("\n" + "="*60)
        print("📊 דוח מסכם")
        print("="*60)
        
        total_users = len(self.results)
        users_with_data = sum(1 for r in self.results.values() if 'chat_history' in r and r['chat_history'])
        users_with_profiles = sum(1 for r in self.results.values() if r.get('profile_data', {}).get('exists'))
        total_recommendations = sum(len(r.get('recommendations', [])) for r in self.results.values())
        
        print(f"👥 סה״כ משתמשים: {total_users}")
        print(f"📊 עם היסטוריה: {users_with_data}")
        print(f"👤 עם פרופיל: {users_with_profiles}")
        print(f"💡 סה״כ המלצות: {total_recommendations}")
        
        # פירוט לפי משתמש
        for chat_id, result in self.results.items():
            if 'error' in result:
                print(f"\n❌ {chat_id}: שגיאה - {result['error']}")
                continue
            
            completion = result.get('completion_analysis', {}).get('completion_rate', 0)
            recommendations_count = len(result.get('recommendations', []))
            messages_count = result.get('chat_history', {}).get('total_messages', 0)
            
            status = "🟢" if recommendations_count == 0 else "🟡" if recommendations_count <= 3 else "🔴"
            print(f"\n{status} {chat_id}:")
            print(f"  📈 הודעות: {messages_count}")
            print(f"  📋 שלמות פרופיל: {completion}%")
            print(f"  💡 המלצות: {recommendations_count}")
            
            if recommendations_count > 0:
                print("  🔍 עיקר ההמלצות:")
                for rec in result['recommendations'][:3]:  # רק 3 הראשונות
                    print(f"    • {rec.get('description', 'לא ידוע')}")
        
        return {
            'summary': {
                'total_users': total_users,
                'users_with_data': users_with_data,
                'users_with_profiles': users_with_profiles,
                'total_recommendations': total_recommendations,
                'analysis_date': datetime.now().isoformat()
            },
            'detailed_results': self.results
        }
    
    def save_results(self, filename='user_analysis_comprehensive.json'):
        """שמירת תוצאות לקובץ"""
        summary_report = self.generate_summary_report()
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(summary_report, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 תוצאות נשמרו ב-{filename}")
        return filename

def main():
    """פונקציה ראשית"""
    analyzer = UserAnalyzer()
    
    # ביצוע הניתוח
    results = analyzer.analyze_all_users()
    
    # שמירת התוצאות
    filename = analyzer.save_results()
    
    print(f"\n🎉 ניתוח הושלם!")
    print(f"📄 קובץ התוצאות: {filename}")
    print("\n📋 איך להמשיך:")
    print("1. בדוק את הקובץ JSON עם כל התוצאות")
    print("2. עבור על ההמלצות לכל משתמש")
    print("3. החלט אלו עדכונים לבצע")
    print("4. השתמש בפונקציות העדכון למסד הנתונים")

if __name__ == "__main__":
    main() 