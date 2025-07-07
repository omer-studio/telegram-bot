#!/usr/bin/env python3
"""
🧠 כלי ניתוח חכם למשתמשים
================================

כלי יחיד ומתקדם לניתוח משתמשים:
- מנתח את התוכן בצורה חכמה 
- מחלץ מידע לפי FIELDS_DICT
- מציג תוצאות מפורטות
- מציע עדכון פרופיל

שימוש:
python smart_user_analyzer.py <chat_id>
python smart_user_analyzer.py --list
"""

import sys
import os
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

# הוספת נתיב לפרויקט
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fields_dict import FIELDS_DICT, get_user_profile_fields, get_summary_fields
from db_manager import get_user_profile, get_user_message_count, update_user_profile_field
from chat_utils import get_chat_history_messages

class SmartUserAnalyzer:
    """כלי ניתוח חכם למשתמשים"""
    
    def __init__(self):
        self.user_profile_fields = get_user_profile_fields()
        self.summary_fields = get_summary_fields()
        
    def analyze_user(self, chat_id: str) -> Dict[str, Any]:
        """מנתח משתמש באופן מקיף"""
        print(f"🧠 מנתח משתמש {chat_id}...")
        
        # שלב 1: איסוף נתונים
        data = self._collect_user_data(chat_id)
        
        # שלב 2: ניתוח תוכן
        analysis = self._analyze_content(data)
        
        # שלב 3: מיפוי לפי FIELDS_DICT
        field_mapping = self._map_to_fields(analysis)
        
        # שלב 4: יצירת סיכום
        summary = self._generate_summary(field_mapping)
        
        return {
            'chat_id': chat_id,
            'data_sources': data,
            'analysis': analysis,
            'field_mapping': field_mapping,
            'summary': summary,
            'confidence_score': self._calculate_confidence(field_mapping)
        }
    
    def _collect_user_data(self, chat_id: str) -> Dict[str, Any]:
        """אוסף נתונים על המשתמש מכל המקורות"""
        data = {
            'chat_id': chat_id,
            'profile': {},
            'messages': [],
            'message_count': 0,
            'data_sources': []
        }
        
        # נתונים מהמסד נתונים
        try:
            profile = get_user_profile(chat_id)
            if profile:
                data['profile'] = profile
                data['data_sources'].append('database_profile')
                print(f"  📊 פרופיל מוצא: {len(profile)} שדות")
        except Exception as e:
            print(f"  ⚠️ שגיאה בקריאת פרופיל: {e}")
        
        # מספר הודעות
        try:
            message_count = get_user_message_count(chat_id)
            data['message_count'] = message_count
            print(f"  📧 מספר הודעות: {message_count}")
        except Exception as e:
            print(f"  ⚠️ שגיאה בקריאת מספר הודעות: {e}")
        
        # היסטוריית הודעות
        try:
            messages = get_chat_history_messages(chat_id)
            if messages:
                data['messages'] = messages
                data['data_sources'].append('chat_history')
                print(f"  💬 היסטוריית הודעות: {len(messages)} הודעות")
        except Exception as e:
            print(f"  ⚠️ שגיאה בקריאת היסטוריית הודעות: {e}")
        
        # קבצי נתונים מקומיים
        local_files = [
            f"temp_files/chat_history_{chat_id}.txt",
            f"temp_files/chat_data_{chat_id}.json", 
            f"data/chat_history_{chat_id}.json"
        ]
        
        for file_path in local_files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        if file_path.endswith('.txt'):
                            content = f.read()
                            data['text_content'] = content
                            data['data_sources'].append(f'local_file_{os.path.basename(file_path)}')
                            print(f"  📄 קובץ טקסט: {len(content)} תווים")
                        elif file_path.endswith('.json'):
                            content = json.load(f)
                            data['json_content'] = content
                            data['data_sources'].append(f'local_file_{os.path.basename(file_path)}')
                            print(f"  📄 קובץ JSON: {len(str(content))} תווים")
                except Exception as e:
                    print(f"  ⚠️ שגיאה בקריאת {file_path}: {e}")
        
        return data
    
    def _analyze_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """מנתח את התוכן בצורה חכמה"""
        analysis = {
            'personal_info': {},
            'relationships': {},
            'conflicts': {},
            'goals': {},
            'background': {},
            'emotions': {},
            'timeline': {},
            'patterns': []
        }
        
        # איחוד כל הטקסט לניתוח
        all_text = ""
        
        # הודעות מההיסטוריה
        if 'messages' in data:
            for msg in data['messages']:
                if isinstance(msg, dict):
                    all_text += f"{msg.get('user', '')} {msg.get('bot', '')} "
                else:
                    all_text += f"{msg} "
        
        # תוכן טקסט
        if 'text_content' in data:
            all_text += data['text_content']
        
        # תוכן JSON
        if 'json_content' in data:
            all_text += json.dumps(data['json_content'], ensure_ascii=False)
        
        print(f"  🔍 מנתח {len(all_text)} תווים...")
        
        # ניתוח חכם של הטקסט
        analysis['personal_info'] = self._extract_personal_info(all_text)
        analysis['relationships'] = self._extract_relationships(all_text)
        analysis['conflicts'] = self._extract_conflicts(all_text)
        analysis['goals'] = self._extract_goals(all_text)
        analysis['background'] = self._extract_background(all_text)
        analysis['emotions'] = self._extract_emotions(all_text)
        analysis['timeline'] = self._extract_timeline(all_text)
        analysis['patterns'] = self._extract_patterns(all_text)
        
        return analysis
    
    def _extract_personal_info(self, text: str) -> Dict[str, str]:
        """חילוץ מידע אישי"""
        info = {}
        
        # גיל
        age_patterns = [
            r'בן (\d+)', r'בת (\d+)', r'אני (\d+)', r'גיל (\d+)',
            r'(\d+) שנים', r'(\d+) שנה', r'בתור מישהו בן (\d+)'
        ]
        for pattern in age_patterns:
            match = re.search(pattern, text)
            if match:
                age = int(match.group(1))
                if 18 <= age <= 99:
                    info['age'] = str(age)
                    break
        
        # שם
        name_patterns = [
            r'קוראים לי ([א-ת]+)', r'השם שלי ([א-ת]+)', r'אני ([א-ת]+)',
            r'שלום,? אני ([א-ת]+)', r'היי,? אני ([א-ת]+)'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                info['name'] = match.group(1)
                break
        
        # עיסוק
        occupation_patterns = [
            r'אני עובד ב?([א-ת\s]+)', r'אני ([א-ת\s]+) במקצוע',
            r'המקצוע שלי ([א-ת\s]+)', r'אני סטודנט ל?([א-ת\s]+)',
            r'אני מורה ל?([א-ת\s]+)', r'אני עורך דין', r'אני רופא',
            r'אני מהנדס', r'אני מתכנת', r'אני עובד בהייטק'
        ]
        for pattern in occupation_patterns:
            match = re.search(pattern, text)
            if match:
                info['occupation'] = match.group(1) if match.group(1) else match.group(0)
                break
        
        return info
    
    def _extract_relationships(self, text: str) -> Dict[str, str]:
        """חילוץ מידע על מערכות יחסים"""
        relationships = {}
        
        # מצב זוגי
        relationship_patterns = [
            r'אני רווק', r'אני נשוי', r'אני גרוש', r'אני מתגרש',
            r'יש לי בן זוג', r'יש לי חבר', r'יש לי בחורה',
            r'אני בזוגיות', r'אני לבד', r'אני בנישואין'
        ]
        for pattern in relationship_patterns:
            if re.search(pattern, text):
                relationships['relationship_status'] = pattern.replace('אני ', '')
                break
        
        # ילדים
        children_patterns = [
            r'יש לי (\d+) ילדים', r'יש לי ילד', r'יש לי ילדה',
            r'יש לי (\d+) ילדות', r'יש לי בן', r'יש לי בת',
            r'אין לי ילדים', r'בלי ילדים'
        ]
        for pattern in children_patterns:
            match = re.search(pattern, text)
            if match:
                relationships['children'] = match.group(0)
                break
        
        # נטייה מינית
        attraction_patterns = [
            r'אני גיי', r'אני הומו', r'אני נמשך לגברים',
            r'אני ביסקסואל', r'אני נמשך גם לנשים',
            r'אני בא רק על גברים', r'אני לא נמשך לנשים'
        ]
        for pattern in attraction_patterns:
            if re.search(pattern, text):
                relationships['attraction'] = pattern.replace('אני ', '')
                break
        
        return relationships
    
    def _extract_conflicts(self, text: str) -> Dict[str, str]:
        """חילוץ קונפליקטים ובעיות"""
        conflicts = {}
        
        # בעיות מרכזיות
        conflict_patterns = [
            r'הבעיה שלי', r'המתח שלי', r'הקושי שלי',
            r'אני מתמודד עם', r'אני נלחם נגד',
            r'מה שמעסיק אותי', r'מה שמטריד אותי'
        ]
        
        for pattern in conflict_patterns:
            matches = re.findall(f'{pattern}[^.!?]*[.!?]', text)
            if matches:
                conflicts['main_conflict'] = ' '.join(matches)
                break
        
        # פחדים
        fear_patterns = [
            r'אני מפחד', r'אני חושש', r'הפחד שלי',
            r'אני מתפחד', r'אני דואג'
        ]
        
        for pattern in fear_patterns:
            matches = re.findall(f'{pattern}[^.!?]*[.!?]', text)
            if matches:
                conflicts['fears'] = ' '.join(matches)
                break
        
        return conflicts
    
    def _extract_goals(self, text: str) -> Dict[str, str]:
        """חילוץ מטרות וחזונות"""
        goals = {}
        
        # מטרות
        goal_patterns = [
            r'אני רוצה', r'המטרה שלי', r'אני מחפש',
            r'אני מקווה', r'אני שואף', r'החלום שלי'
        ]
        
        for pattern in goal_patterns:
            matches = re.findall(f'{pattern}[^.!?]*[.!?]', text)
            if matches:
                goals['main_goals'] = ' '.join(matches)
                break
        
        # חזון עתיד
        future_patterns = [
            r'בעתיד אני', r'עד כמה שנים', r'בעוד',
            r'איך אני רואה', r'איך אני מתכנן'
        ]
        
        for pattern in future_patterns:
            matches = re.findall(f'{pattern}[^.!?]*[.!?]', text)
            if matches:
                goals['future_vision'] = ' '.join(matches)
                break
        
        return goals
    
    def _extract_background(self, text: str) -> Dict[str, str]:
        """חילוץ רקע דתי ומשפחתי"""
        background = {}
        
        # רקע דתי
        religion_patterns = [
            r'אני חילוני', r'אני דתי', r'אני חרדי',
            r'אני מסורתי', r'המשפחה שלי דתית',
            r'גדלתי בבית דתי', r'גדלתי בבית חילוני'
        ]
        
        for pattern in religion_patterns:
            if re.search(pattern, text):
                background['religiosity'] = pattern.replace('אני ', '')
                break
        
        # ארון
        closet_patterns = [
            r'אני בארון', r'אני לא בארון', r'יצאתי מהארון',
            r'רק החברים יודעים', r'כולם יודעים',
            r'המשפחה לא יודעת', r'המשפחה יודעת'
        ]
        
        for pattern in closet_patterns:
            if re.search(pattern, text):
                background['closet_status'] = pattern
                break
        
        return background
    
    def _extract_emotions(self, text: str) -> Dict[str, str]:
        """חילוץ רגשות ותחושות"""
        emotions = {}
        
        # רגשות חיוביים
        positive_patterns = [
            r'אני מרגיש טוב', r'אני שמח', r'אני בטוח',
            r'אני חזק', r'אני גאה', r'אני שלם'
        ]
        
        positive_emotions = []
        for pattern in positive_patterns:
            if re.search(pattern, text):
                positive_emotions.append(pattern)
        
        if positive_emotions:
            emotions['positive'] = ', '.join(positive_emotions)
        
        # רגשות שליליים
        negative_patterns = [
            r'אני מרגיש רע', r'אני עצוב', r'אני מבולבל',
            r'אני לבד', r'אני אבוד', r'אני מתבייש'
        ]
        
        negative_emotions = []
        for pattern in negative_patterns:
            if re.search(pattern, text):
                negative_emotions.append(pattern)
        
        if negative_emotions:
            emotions['negative'] = ', '.join(negative_emotions)
        
        return emotions
    
    def _extract_timeline(self, text: str) -> Dict[str, str]:
        """חילוץ אירועים בזמן"""
        timeline = {}
        
        # אירועים חשובים
        event_patterns = [
            r'לפני (\d+) שנים', r'בגיל (\d+)',
            r'כשהייתי (\d+)', r'בתקופה האחרונה',
            r'לאחרונה', r'בשנים האחרונות'
        ]
        
        events = []
        for pattern in event_patterns:
            matches = re.findall(f'[^.!?]*{pattern}[^.!?]*[.!?]', text)
            events.extend(matches)
        
        if events:
            timeline['major_events'] = ' '.join(events)
        
        return timeline
    
    def _extract_patterns(self, text: str) -> List[str]:
        """חילוץ תבניות והתנהגויות"""
        patterns = []
        
        # תבניות התנהגות
        behavior_patterns = [
            r'אני נוהג', r'אני עושה', r'אני מתנהג',
            r'הרגל שלי', r'איך שאני', r'הדרך שלי'
        ]
        
        for pattern in behavior_patterns:
            matches = re.findall(f'{pattern}[^.!?]*[.!?]', text)
            patterns.extend(matches)
        
        return patterns
    
    def _map_to_fields(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """ממפה את הניתוח לשדות של FIELDS_DICT"""
        field_mapping = {}
        
        # מיפוי מידע אישי
        personal_info = analysis.get('personal_info', {})
        if 'age' in personal_info:
            field_mapping['age'] = personal_info['age']
        if 'name' in personal_info:
            field_mapping['name'] = personal_info['name']
        if 'occupation' in personal_info:
            field_mapping['occupation_or_role'] = personal_info['occupation']
        
        # מיפוי מערכות יחסים
        relationships = analysis.get('relationships', {})
        if 'relationship_status' in relationships:
            field_mapping['relationship_type'] = relationships['relationship_status']
        if 'children' in relationships:
            field_mapping['parental_status'] = relationships['children']
        if 'attraction' in relationships:
            field_mapping['attracted_to'] = relationships['attraction']
        
        # מיפוי קונפליקטים
        conflicts = analysis.get('conflicts', {})
        if 'main_conflict' in conflicts:
            field_mapping['primary_conflict'] = conflicts['main_conflict']
        if 'fears' in conflicts:
            field_mapping['fears_concerns'] = conflicts['fears']
        
        # מיפוי מטרות
        goals = analysis.get('goals', {})
        if 'main_goals' in goals:
            field_mapping['goal_in_course'] = goals['main_goals']
        if 'future_vision' in goals:
            field_mapping['future_vision'] = goals['future_vision']
        
        # מיפוי רקע
        background = analysis.get('background', {})
        if 'religiosity' in background:
            field_mapping['self_religiosity_level'] = background['religiosity']
        if 'closet_status' in background:
            field_mapping['closet_status'] = background['closet_status']
        
        # מיפוי רגשות
        emotions = analysis.get('emotions', {})
        if 'positive' in emotions or 'negative' in emotions:
            emotion_text = f"רגשות חיוביים: {emotions.get('positive', 'לא זוהו')}. רגשות שליליים: {emotions.get('negative', 'לא זוהו')}."
            field_mapping['other_insights'] = emotion_text
        
        # מיפוי תבניות
        patterns = analysis.get('patterns', [])
        if patterns:
            field_mapping['coping_strategies'] = ' '.join(patterns[:3])  # רק 3 הראשונות
        
        # מיפוי אירועים
        timeline = analysis.get('timeline', {})
        if 'major_events' in timeline:
            if 'other_insights' in field_mapping:
                field_mapping['other_insights'] += f" אירועים חשובים: {timeline['major_events']}"
            else:
                field_mapping['other_insights'] = f"אירועים חשובים: {timeline['major_events']}"
        
        return field_mapping
    
    def _generate_summary(self, field_mapping: Dict[str, str]) -> str:
        """יוצר סיכום רגשי מקיף"""
        summary_parts = []
        
        # מידע בסיסי
        basic_info = []
        if 'age' in field_mapping:
            basic_info.append(f"בן {field_mapping['age']}")
        if 'name' in field_mapping:
            basic_info.append(f"שמו {field_mapping['name']}")
        if 'occupation_or_role' in field_mapping:
            basic_info.append(f"עובד כ{field_mapping['occupation_or_role']}")
        
        if basic_info:
            summary_parts.append(', '.join(basic_info))
        
        # מצב אישי
        personal_status = []
        if 'relationship_type' in field_mapping:
            personal_status.append(field_mapping['relationship_type'])
        if 'parental_status' in field_mapping:
            personal_status.append(field_mapping['parental_status'])
        if 'attracted_to' in field_mapping:
            personal_status.append(field_mapping['attracted_to'])
        
        if personal_status:
            summary_parts.append(f"מצב אישי: {', '.join(personal_status)}")
        
        # קונפליקט מרכזי
        if 'primary_conflict' in field_mapping:
            summary_parts.append(f"קונפליקט מרכזי: {field_mapping['primary_conflict'][:100]}...")
        
        # מטרות
        if 'goal_in_course' in field_mapping:
            summary_parts.append(f"מטרות: {field_mapping['goal_in_course'][:100]}...")
        
        # רקע
        if 'closet_status' in field_mapping:
            summary_parts.append(f"מצב ארון: {field_mapping['closet_status']}")
        
        return '. '.join(summary_parts) + '.'
    
    def _calculate_confidence(self, field_mapping: Dict[str, str]) -> float:
        """מחשב ציון אמינות לניתוח"""
        total_fields = len(self.user_profile_fields)
        filled_fields = len(field_mapping)
        
        # ציון בסיסי לפי כמות שדות
        base_score = (filled_fields / total_fields) * 100
        
        # בונוס לשדות חשובים
        important_fields = ['age', 'primary_conflict', 'goal_in_course', 'closet_status']
        important_filled = sum(1 for field in important_fields if field in field_mapping)
        bonus = (important_filled / len(important_fields)) * 20
        
        return min(base_score + bonus, 100)
    
    def display_analysis(self, result: Dict[str, Any]) -> None:
        """מציג את תוצאות הניתוח"""
        print(f"\n{'='*60}")
        print(f"🧠 תוצאות ניתוח חכם למשתמש {result['chat_id']}")
        print(f"{'='*60}")
        
        # מקורות נתונים
        print(f"\n📊 מקורות נתונים:")
        for source in result['data_sources']['data_sources']:
            print(f"   ✅ {source}")
        
        # ציון אמינות
        print(f"\n🎯 ציון אמינות: {result['confidence_score']:.1f}%")
        
        # מיפוי שדות
        print(f"\n📋 שדות שזוהו ({len(result['field_mapping'])} מתוך {len(self.user_profile_fields)}):")
        for field, value in result['field_mapping'].items():
            field_info = FIELDS_DICT.get(field, {})
            label = field_info.get('label', field)
            print(f"   🔹 {label}: {value}")
        
        # סיכום
        print(f"\n📝 סיכום רגשי:")
        print(f"   {result['summary']}")
        
        # המלצות
        print(f"\n💡 המלצות:")
        empty_fields = [f for f in self.user_profile_fields if f not in result['field_mapping']]
        if empty_fields:
            print(f"   ⚠️  שדות חסרים: {len(empty_fields)}")
            for field in empty_fields[:5]:  # רק 5 הראשונים
                field_info = FIELDS_DICT.get(field, {})
                label = field_info.get('label', field)
                print(f"      • {label}")
            if len(empty_fields) > 5:
                print(f"      ... ועוד {len(empty_fields) - 5} שדות")
        
        # אפשרויות פעולה
        print(f"\n🔧 אפשרויות פעולה:")
        print(f"   1. עדכון הפרופיל במסד הנתונים")
        print(f"   2. שמירת הניתוח לקובץ")
        print(f"   3. יצירת דוח מפורט")
    
    def save_analysis(self, result: Dict[str, Any], filename: str = None) -> str:
        """שומר את הניתוח לקובץ"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_{result['chat_id']}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        return filename
    
    def update_profile(self, result: Dict[str, Any]) -> bool:
        """מעדכן את הפרופיל במסד הנתונים"""
        try:
            chat_id = result['chat_id']
            field_mapping = result['field_mapping']
            
            # עדכון שדה אחד בכל פעם
            updated_count = 0
            for field, value in field_mapping.items():
                if field in self.user_profile_fields:
                    success = update_user_profile_field(chat_id, field, value)
                    if success:
                        updated_count += 1
            
            # עדכון הסיכום
            summary = result['summary']
            if summary:
                update_user_profile_field(chat_id, 'summary', summary)
                updated_count += 1
            
            print(f"✅ עודכנו {updated_count} שדות בפרופיל")
            return True
            
        except Exception as e:
            print(f"❌ שגיאה בעדכון פרופיל: {e}")
            return False
    
    def list_available_users(self) -> List[str]:
        """מציג רשימה של משתמשים זמינים"""
        users = []
        
        # חיפוש בקבצים מקומיים
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.startswith('chat_history_') and file.endswith('.txt'):
                    chat_id = file.replace('chat_history_', '').replace('.txt', '')
                    users.append(chat_id)
        
        return sorted(list(set(users)))

def main():
    """פונקציה ראשית"""
    analyzer = SmartUserAnalyzer()
    
    # בדיקת ארגומנטים
    if len(sys.argv) < 2:
        print("🧠 כלי ניתוח חכם למשתמשים")
        print("=" * 40)
        print("שימוש:")
        print("  python smart_user_analyzer.py <chat_id>")
        print("  python smart_user_analyzer.py --list")
        print()
        print("דוגמאות:")
        print("  python smart_user_analyzer.py 5676571979")
        print("  python smart_user_analyzer.py --list")
        return
    
    arg = sys.argv[1]
    
    # הצגת רשימת משתמשים
    if arg == '--list':
        print("👥 משתמשים זמינים:")
        users = analyzer.list_available_users()
        if users:
            for user in users:
                print(f"   📧 {user}")
        else:
            print("   ❌ לא נמצאו משתמשים")
        return
    
    # ניתוח משתמש
    chat_id = arg
    print(f"🚀 מתחיל ניתוח חכם למשתמש {chat_id}")
    
    try:
        # ביצוע הניתוח
        result = analyzer.analyze_user(chat_id)
        
        # הצגת התוצאות
        analyzer.display_analysis(result)
        
        # שאלה אם לעדכן את הפרופיל
        while True:
            choice = input("\n🔧 מה תרצה לעשות? (u=עדכן פרופיל, s=שמור לקובץ, q=יציאה): ").strip().lower()
            
            if choice == 'u':
                if analyzer.update_profile(result):
                    print("✅ הפרופיל עודכן בהצלחה!")
                else:
                    print("❌ העדכון נכשל")
            elif choice == 's':
                filename = analyzer.save_analysis(result)
                print(f"✅ הניתוח נשמר לקובץ: {filename}")
            elif choice == 'q':
                print("👋 להתראות!")
                break
            else:
                print("❌ בחירה לא חוקית")
        
    except Exception as e:
        print(f"❌ שגיאה בניתוח: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 