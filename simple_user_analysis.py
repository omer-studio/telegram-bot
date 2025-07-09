#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
simple_user_analysis.py
========================
🎯 ניתוח פשוט ומקיף של 6 המשתמשים עם הנתונים הזמינים מקומית

👥 משתמשים: 1118251087, 179392777, 5676571979, 7957193610, 5526006524, 7186596694

🚀 הפעלה: python simple_user_analysis.py
"""

import os
import json
import re
from datetime import datetime
from utils import safe_str, get_logger

logger = get_logger(__name__)

# המשתמשים לניתוח - מוגדרים כמחרוזות בטוחות
TARGET_USERS = [
    safe_str("1118251087"), safe_str("179392777"), safe_str("5676571979"), 
    safe_str("7957193610"), safe_str("5526006524"), safe_str("7186596694")
]

class SimpleAnalyzer:
    """מנתח פשוט לחילוץ מידע מצ'אט"""
    
    def analyze_user_text(self, text):
        """ניתוח טקסט משתמש"""
        if not text:
            return {}
        
        findings = {}
        
        # חיפוש גיל
        age_patterns = [r'בן (\d+)', r'אני (\d+)', r'(\d+) שנים', r'גיל (\d+)']
        for pattern in age_patterns:
            match = re.search(pattern, text)
            if match:
                age = int(match.group(1))
                if 18 <= age <= 80:
                    findings['age'] = age
                    break
        
        # חיפוש מצב משפחתי
        if re.search(r'גרוש|התגרשתי', text):
            findings['relationship_type'] = 'גרוש'
        elif re.search(r'נשוי', text):
            findings['relationship_type'] = 'נשוי'
        elif re.search(r'רווק', text):
            findings['relationship_type'] = 'רווק'
        
        # חיפוש דתיות
        if re.search(r'חילוני', text):
            findings['religiosity'] = 'חילוני'
        elif re.search(r'דתי', text):
            findings['religiosity'] = 'דתי'
        elif re.search(r'מסורתי', text):
            findings['religiosity'] = 'מסורתי'
        
        # חיפוש מצב ארון
        if re.search(r'בארון|בסוד', text):
            findings['closet_status'] = 'בארון'
        elif re.search(r'יצאתי מהארון|פתוח', text):
            findings['closet_status'] = 'מחוץ לארון'
        
        # חיפוש משיכה
        if re.search(r'נמשך רק לגברים|אני הומו|רוצה גבר', text):
            findings['attraction'] = 'רק לגברים'
        elif re.search(r'גם לנשים וגם לגברים', text):
            findings['attraction'] = 'לשניהם'
        
        # חיפוש ילדים
        if re.search(r'יש לי ילדים|הילדים שלי|מהגרושה', text):
            findings['children'] = 'יש ילדים'
        elif re.search(r'אין לי ילדים', text):
            findings['children'] = 'אין ילדים'
        
        # חיפוש קונפליקטים
        conflicts = []
        conflict_words = ['מתמודד עם', 'קשה לי', 'מתקשה', 'הבעיה שלי']
        for word in conflict_words:
            if word in text:
                conflicts.append(word)
        if conflicts:
            findings['conflicts'] = ', '.join(conflicts[:3])
        
        # חיפוש פחדים
        fears = []
        fear_words = ['פחד', 'חושש', 'מפחיד אותי', 'דואג']
        for word in fear_words:
            if word in text:
                fears.append(word)
        if fears:
            findings['fears'] = ', '.join(fears[:3])
        
        return findings

def load_available_data():
    """טעינת כל הנתונים הזמינים"""
    logger.info("טוען נתונים זמינים")
    print("📂 טוען נתונים זמינים...")
    
    data = {}
    
    # 1. קובץ היסטוריה עיקרי
    chat_file = "data/chat_history.json"
    if os.path.exists(chat_file):
        with open(chat_file, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        
        for user_id in TARGET_USERS:
            if user_id in chat_data:
                user_texts = []
                chat_info = chat_data[user_id]
                if isinstance(chat_info, dict) and 'history' in chat_info:
                    for entry in chat_info['history']:
                        if 'user' in entry and entry['user']:
                            user_texts.append(entry['user'])
                
                if user_texts:
                    data[user_id] = {
                        'source': 'chat_history.json',
                        'text': ' '.join(user_texts),
                        'message_count': len(user_texts)
                    }
                    print(f"✅ {user_id}: {len(user_texts)} הודעות")
    
    # 2. קובץ טקסט ספציפי
    specific_file = "chat_history_5676571979.txt"
    if os.path.exists(specific_file):
        with open(specific_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # חילוץ הודעות משתמש
        user_messages = re.findall(r'USER: ([^\n]+)', content)
        if user_messages:
            user_text = ' '.join(user_messages)
            if '5676571979' in data:
                data['5676571979']['text'] += ' ' + user_text
                data['5676571979']['source'] += ' + txt_file'
            else:
                data['5676571979'] = {
                    'source': 'txt_file',
                    'text': user_text,
                    'message_count': len(user_messages)
                }
            print(f"✅ 5676571979: +{len(user_messages)} הודעות מקובץ טקסט")
    
    # 3. קובץ הודעות מחולצות
    extracted_file = "temp_files/extracted_all_messages.json"
    if os.path.exists(extracted_file):
        try:
            with open(extracted_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)
            
            for msg in messages:
                user_id = str(msg.get('user_id', ''))
                if user_id in TARGET_USERS and msg.get('user_message'):
                    if user_id not in data:
                        data[user_id] = {
                            'source': 'extracted_messages',
                            'text': '',
                            'message_count': 0
                        }
                    data[user_id]['text'] += ' ' + msg['user_message']
                    data[user_id]['message_count'] += 1
            
            print(f"✅ נטענו הודעות נוספות מ-extracted_messages")
        except:
            print("⚠️ בעיה בטעינת extracted_messages")
    
    print(f"📊 סיכום: נתונים עבור {len(data)} משתמשים")
    return data

def main():
    """ניתוח ראשי"""
    logger.info("מתחיל ניתוח פשוט ומקיף של 6 המשתמשים")
    print("🎯 ניתוח פשוט ומקיף של 6 המשתמשים")
    print("=" * 60)
    
    # טעינת נתונים
    user_data = load_available_data()
    
    if not user_data:
        logger.warning("לא נמצאו נתונים")
        print("❌ לא נמצאו נתונים!")
        return
    
    # אתחול מנתח
    analyzer = SimpleAnalyzer()
    
    print(f"\n🔍 מנתח {len(user_data)} משתמשים...")
    print("=" * 60)
    
    all_results = {}
    
    for user_id in TARGET_USERS:
        safe_user_id = safe_str(user_id)
        logger.info(f"מנתח משתמש {safe_user_id}")
        print(f"\n👤 משתמש {safe_user_id}:")
        print("-" * 40)
        
        if user_id not in user_data:
            logger.warning(f"אין נתונים זמינים למשתמש {safe_user_id}")
            print("❌ אין נתונים זמינים")
            all_results[user_id] = {'status': 'no_data'}
            continue
        
        user_info = user_data[user_id]
        text = user_info['text']
        
        print(f"📊 מקור: {user_info['source']}")
        print(f"📊 הודעות: {user_info['message_count']}")
        print(f"📊 אורך טקסט: {len(text)} תווים")
        
        # ניתוח
        findings = analyzer.analyze_user_text(text)
        
        print(f"\n🔍 ממצאים ({len(findings)} שדות):")
        if findings:
            for field, value in findings.items():
                print(f"   • {field}: {value}")
        else:
            print("   ❌ לא נמצאו ממצאים ברורים")
        
        # מציג קטעי טקסט מעניינים
        interesting_snippets = []
        for keyword in ['בן', 'גיל', 'נשוי', 'גרוש', 'חילוני', 'דתי', 'ארון', 'הומו', 'נמשך']:
            if keyword in text.lower():
                start = text.lower().find(keyword)
                if start != -1:
                    snippet = text[start:start+80].strip()
                    interesting_snippets.append(snippet)
        
        if interesting_snippets:
            print(f"\n📝 קטעים מעניינים:")
            for i, snippet in enumerate(interesting_snippets[:3], 1):
                clean_snippet = re.sub(r'\s+', ' ', snippet)
                print(f"   {i}. {clean_snippet}...")
        
        all_results[user_id] = {
            'status': 'analyzed',
            'findings': findings,
            'text_length': len(text),
            'message_count': user_info['message_count'],
            'source': user_info['source']
        }
    
    # סיכום כללי
    print("\n" + "=" * 60)
    print("📊 סיכום כללי")
    print("=" * 60)
    
    analyzed_count = sum(1 for r in all_results.values() if r['status'] == 'analyzed')
    total_findings = sum(len(r.get('findings', {})) for r in all_results.values())
    
    print(f"👥 משתמשים שנותחו: {analyzed_count}/{len(TARGET_USERS)}")
    print(f"🔍 סה\"כ ממצאים: {total_findings}")
    
    # פירוט לכל משתמש
    for user_id, result in all_results.items():
        if result['status'] == 'analyzed':
            findings_count = len(result.get('findings', {}))
            status_icon = "✅" if findings_count > 0 else "⚠️"
            print(f"\n{status_icon} {user_id}: {findings_count} ממצאים")
            
            # הצגת התובנות החשובות ביותר
            findings = result.get('findings', {})
            important_fields = ['age', 'relationship_type', 'religiosity', 'attraction', 'closet_status']
            for field in important_fields:
                if field in findings:
                    print(f"   • {field}: {findings[field]}")
    
    # שמירת תוצאות
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'user_analysis_results_{timestamp}.json'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 תוצאות נשמרו ב-{output_file}")
    print(f"🎉 הניתוח הושלם!")

if __name__ == "__main__":
    main() 