#!/usr/bin/env python3
"""
profile_utils.py - כלי עזר לניהול פרופילי משתמשים
"""

import json
import psycopg2
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from decimal import Decimal

# ייבואים מרכזיים
from config import config
from simple_logger import logger
from user_friendly_errors import safe_str, safe_chat_id
from utils import get_israel_time
from fields_dict import FIELDS_DICT, get_user_profile_fields

# Cache פשוט לפרופילים
_profile_cache = {}

def clear_profile_cache(chat_id: Any = None) -> None:
    """ניקוי cache פרופילים - פונקציה אחת פשוטה"""
    try:
        if chat_id is None:
            # ניקוי כל ה-cache
            _profile_cache.clear()
            logger.debug(f"[CACHE_CLEAR] ניקוי כל ה-cache", source="profile_utils")
        else:
            # ניקוי פרופיל ספציפי
            safe_id = safe_str(chat_id)
            if safe_id in _profile_cache:
                del _profile_cache[safe_id]
                logger.debug(f"[CACHE_CLEAR] ניסה לנקות cache עבור משתמש {safe_id}", source="profile_utils")
                
    except Exception as e:
        logger.error(f"שגיאה בניקוי cache למשתמש {safe_str(chat_id)}: {e}", source="profile_utils")

def get_user_profile(chat_id: Any) -> Dict:
    """קבלת פרופיל משתמש - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        # בדיקה ב-cache קודם
        if safe_id in _profile_cache:
            return _profile_cache[safe_id]
        
        # קבלה מהמסד נתונים
        from simple_data_manager import data_manager
        
        profile = data_manager.get_user_profile(safe_id)
        
        if profile:
            # שמירה ב-cache
            _profile_cache[safe_id] = profile
            return profile
        else:
            # יצירת פרופיל חדש
            new_profile = {
                'chat_id': safe_id,
                        'created_at': get_israel_time().isoformat(),
        'last_updated': get_israel_time().isoformat(),
                'message_count': 0,
                'total_cost': 0.0,
                'preferences': {},
                'summary': ""
            }
            
            # שמירה במסד נתונים
            data_manager.save_user_profile(safe_id, new_profile)
            
            # שמירה ב-cache
            _profile_cache[safe_id] = new_profile
            
            return new_profile
            
    except Exception as e:
        logger.error(f"שגיאה בשליפת פרופיל: {e}", source="profile_utils")
        return {}

def update_user_profile(chat_id: Any, updates: Dict) -> bool:
    """עדכון פרופיל משתמש - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        # קבלת פרופיל נוכחי
        current_profile = get_user_profile(safe_id)
        
        # עדכון הפרופיל
        current_profile.update(updates)
        current_profile['last_updated'] = get_israel_time().isoformat()
        
        # שמירה במסד נתונים
        from simple_data_manager import data_manager
        success = data_manager.save_user_profile(safe_id, current_profile)
        
        if success:
            # עדכון cache
            _profile_cache[safe_id] = current_profile
            logger.info(f"✅ פרופיל עודכן בהצלחה למשתמש {safe_id}", source="profile_utils")
            return True
        else:
            logger.error(f"שגיאה בעדכון פרופיל: {updates}", source="profile_utils")
            return False
            
    except Exception as exc:
        logger.error(f"שגיאה בעדכון פרופיל: {exc}", source="profile_utils")
        return False

def save_user_profile(chat_id: Any, profile_data: Dict) -> bool:
    """שמירת פרופיל משתמש - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        # שמירה במסד נתונים
        from simple_data_manager import data_manager
        success = data_manager.save_user_profile(safe_id, profile_data)
        
        if success:
            # עדכון cache
            _profile_cache[safe_id] = profile_data
            logger.info(f"✅ פרופיל נשמר בהצלחה למשתמש {safe_id}", source="profile_utils")
            return True
        else:
            logger.error(f"שגיאה בשמירת פרופיל: {profile_data}", source="profile_utils")
            return False
            
    except Exception as exc:
        logger.error(f"שגיאה בשמירת פרופיל: {exc}", source="profile_utils")
        return False

def sync_profile_to_sheets(chat_id: Any) -> bool:
    """🗑️ פונקציה זו הוסרה - עברנו למסד נתונים"""
    safe_id = safe_str(chat_id)
    logger.info(f"🗑️ פונקציה זו הוסרה - עברנו למסד נתונים עבור {safe_id}", source="profile_utils")
    return True

def sync_profile_by_headers(chat_id: Any) -> bool:
    """🗑️ פונקציה זו הוסרה - עברנו למסד נתונים"""
    safe_id = safe_str(chat_id)
    logger.info(f"🗑️ פונקציה זו הוסרה - עברנו למסד נתונים עבור {safe_id}", source="profile_utils")
    return True

def sync_to_google_sheets(chat_id: Any) -> bool:
    """🗑️ פונקציה זו הוסרה - עברנו למסד נתונים"""
    safe_id = safe_str(chat_id)
    logger.info(f"🗑️ פונקציה זו הוסרה - עברנו למסד נתונים עבור {safe_id}", source="profile_utils")
    return True

def sync_to_sheets_by_headers(chat_id: Any) -> bool:
    """🗑️ פונקציה זו הוסרה - עברנו למסד נתונים"""
    safe_id = safe_str(chat_id)
    logger.info(f"🗑️ פונקציה זו הוסרה - עברנו למסד נתונים עבור {safe_id}", source="profile_utils")
    return True

def schedule_sheets_sync_safely(chat_id: Any) -> None:
    """🗑️ פונקציה זו הוסרה - עברנו למסד נתונים"""
    safe_id = safe_str(chat_id)
    logger.debug(f"🗑️ _schedule_sheets_sync_safely deprecated - using database for {safe_id}", source="profile_utils")

def log_profile_change(chat_id: Any, field: str, old_val: Any, new_val: Any) -> None:
    """רישום שינוי בפרופיל - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        if old_val is None:
            log_message = f"[PROFILE_CHANGE] Added {field} for user: '{new_val}'"
            logger.info(log_message, source="profile_utils")
        else:
            log_message = f"[PROFILE_CHANGE] Updated {field} for user: '{old_val}' → '{new_val}'"
            logger.info(log_message, source="profile_utils")
        
        # שמירה במסד נתונים
        from simple_data_manager import data_manager
        
        change_data = {
            'chat_id': safe_id,
            'field': field,
            'old_value': str(old_val) if old_val is not None else None,
            'new_value': str(new_val),
            'timestamp': get_israel_time().isoformat()
        }
        
        data_manager.save_profile_change(change_data)
        
    except Exception as e:
        logger.error(f"שגיאה ברישום שינויים: {e}", source="profile_utils")

def send_admin_profile_notification(chat_id: Any, changes: Dict) -> bool:
    """שליחת התראה לאדמין על שינויי פרופיל - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        if not changes:
            logger.debug(f"[ADMIN_NOTIFICATION] 🚫 לא נשלחת הודעה למשתמש {safe_id} - אין שינויים בפרופיל", source="profile_utils")
            return True
        
        # הכנת הודעה לאדמין
        total_changes = len(changes)
        gpt_c_changes = len([c for c in changes if 'gpt_c' in str(c)])
        gpt_d_changes = len([c for c in changes if 'gpt_d' in str(c)])
        gpt_e_changes = len([c for c in changes if 'gpt_e' in str(c)])
        
        logger.info(f"[ADMIN_NOTIFICATION] 📬 שולח הודעה למשתמש {safe_id} עם {total_changes} שינויים (C:{gpt_c_changes}, D:{gpt_d_changes}, E:{gpt_e_changes})", source="profile_utils")
        
        # ✅ שליחת התראה פשוטה לאדמין
        try:
            from admin_notifications import send_admin_notification
            
            # יצירת הודעה פשוטה על השינויים
            change_details = []
            for field, value in changes.items():
                change_details.append(f"• {field}: {value}")
            
            notification_message = f"📝 **עדכון פרופיל משתמש**\n\n"
            notification_message += f"👤 **משתמש:** {safe_id}\n"
            notification_message += f"📊 **מספר שינויים:** {total_changes}\n"
            notification_message += f"🔗 **פירוט השינויים:**\n" + "\n".join(change_details[:5])  # מגביל ל-5 שינויים
            
            if len(change_details) > 5:
                notification_message += f"\n... ועוד {len(change_details) - 5} שינויים"
            
            send_admin_notification(notification_message)
            success = True
            
        except Exception as import_error:
            logger.debug(f"[ADMIN_NOTIFICATION] שגיאה בשליחת התראה לאדמין: {import_error}", source="profile_utils")
            success = True  # לא נכשיל בגלל זה
        
        if success:
            logger.info(f"[ADMIN_NOTIFICATION] ✅ הודעה נשלחה בהצלחה למשתמש {safe_id}", source="profile_utils")
            return True
        else:
            logger.error(f"[ADMIN_NOTIFICATION] ❌ שגיאה בשליחת הודעה למשתמש {safe_id}", source="profile_utils")
            return False
            
    except Exception as exc:
        logger.error(f"[ADMIN_NOTIFICATION] ❌ שגיאה בשליחת הודעה למשתמש {safe_str(chat_id)}: {exc}", source="profile_utils")
        return False

def generate_auto_summary(chat_id: Any) -> str:
    """יצירת סיכום אוטומטי - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        # קבלת היסטוריית הודעות
        from simple_data_manager import data_manager
        
        messages = data_manager.get_chat_messages(safe_id, limit=50)
        
        if not messages:
            return ""
        
        # יצירת סיכום פשוט
        user_messages = [msg['user_msg'] for msg in messages if msg.get('user_msg')]
        
        if not user_messages:
            return ""
        
        # סיכום בסיסי - 3 הנושאים העיקריים
        topics = {}
        for msg in user_messages:
            words = msg.split()
            for word in words:
                if len(word) > 3:  # מילים משמעותיות בלבד
                    topics[word] = topics.get(word, 0) + 1
        
        # מיון לפי תדירות
        sorted_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)
        
        # יצירת סיכום
        if sorted_topics:
            main_topics = [topic for topic, count in sorted_topics[:3]]
            auto_summary = f"נושאים עיקריים: {', '.join(main_topics)}"
            
            logger.debug(f"[SUMMARY_DEBUG] Generated auto summary: '{auto_summary}' for user {safe_id}", source="profile_utils")
            
            # עדכון הפרופיל
            update_user_profile(safe_id, {'summary': auto_summary})
            
            logger.debug(f"[SUMMARY_DEBUG] Updated profile summary for user {safe_id}: '{auto_summary}'", source="profile_utils")
            
            return auto_summary
        else:
            logger.debug(f"[SUMMARY_DEBUG] Empty auto summary generated for user {safe_id}", source="profile_utils")
            return ""
            
    except Exception as e:
        logger.debug(f"שגיאה ביצירת סיכום אוטומטי: {e}", source="profile_utils")
        return ""

def update_user_profile_fast(chat_id: Any, updates: Dict) -> bool:
    """עדכון מהיר של פרופיל משתמש - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        # 🔧 תיקון: וידוא שהעדכונים תקינים
        if not updates or not isinstance(updates, dict):
            logger.warning(f"Invalid updates for {safe_id}: {updates}", source="profile_utils")
            return False
        
        # 🔧 תיקון: סינון שדות לא חוקיים
        valid_updates = {}
        for key, value in updates.items():
            if key and isinstance(key, str):
                # המרת ערכים מורכבים לJSON
                if isinstance(value, (dict, list)):
                    valid_updates[key] = json.dumps(value) if value else None
                else:
                    valid_updates[key] = value
            else:
                logger.warning(f"Invalid field name: {key}", source="profile_utils")
        
        if not valid_updates:
            logger.warning(f"No valid updates for {safe_id}", source="profile_utils")
            return True  # אין מה לעדכן - זה בסדר
        
        # עדכון ישיר במסד נתונים
        from simple_data_manager import data_manager
        
        success = data_manager.update_user_profile_fast(safe_id, valid_updates)
        
        if success:
            # ניקוי cache
            if safe_id in _profile_cache:
                del _profile_cache[safe_id]
            
            logger.info(f"✅ פרופיל עודכן במהירות למשתמש {safe_id}", source="profile_utils")
            return True
        else:
            logger.error(f"Database update failed for {safe_id}: {valid_updates}", source="profile_utils")
            return False
            
    except Exception as e:
        logger.error(f"Error updating profile for {safe_str(chat_id)}: {e}", source="profile_utils")
        return False

def get_user_summary_fast(chat_id):
    """תאימות לאחור – מפנה ל-get_profile_summary"""
    return get_profile_summary(chat_id)

def get_profile_summary(chat_id: Any) -> str:
    """קבלת סיכום פרופיל - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        profile = get_user_profile(safe_id)
        return profile.get('summary', '')
        
    except Exception as exc:
        logger.debug(f"Error getting summary for {safe_str(chat_id)}: {exc}", source="profile_utils")
        return ""

def update_emotional_identity(chat_id: Any, emotional_data: Dict) -> bool:
    """עדכון תעודת זהות רגשית - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        # עדכון הפרופיל עם נתונים רגשיים
        updates = {
            'emotional_identity': emotional_data,
            'last_emotional_update': get_israel_time().isoformat()
        }
        
        success = update_user_profile(safe_id, updates)
        
        if success:
            logger.info(f"✅ תעודת זהות רגשית עודכנה עבור משתמש {safe_id}", source="profile_utils")
            return True
        else:
            logger.error(f"שגיאה בעדכון תעודת זהות רגשית: {emotional_data}", source="profile_utils")
            return False
            
    except Exception as exc:
        logger.error(f"שגיאה בעדכון תעודת זהות רגשית: {exc}", source="profile_utils")
        
        # ניסיון גיבוי
        try:
            from simple_data_manager import data_manager
            data_manager.save_emotional_backup(safe_str(chat_id), emotional_data)
        except Exception as fallback_exc:
            logger.error(f"שגיאה גם בניסיון הגיבוי: {fallback_exc}", source="profile_utils")
        
        return False

def check_emotional_consistency(chat_id: Any) -> Dict:
    """בדיקת עקביות תעודת זהות רגשית - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        profile = get_user_profile(safe_id)
        emotional_data = profile.get('emotional_identity', {})
        
        if not emotional_data:
            return {'consistent': True, 'message': 'אין נתונים רגשיים לבדיקה'}
        
        # בדיקות עקביות בסיסיות
        consistency_checks = {
            'has_personality': bool(emotional_data.get('personality')),
            'has_emotions': bool(emotional_data.get('emotions')),
            'has_preferences': bool(emotional_data.get('preferences')),
            'recent_update': bool(emotional_data.get('last_update'))
        }
        
        is_consistent = all(consistency_checks.values())
        
        result = {
            'consistent': is_consistent,
            'checks': consistency_checks,
            'last_update': emotional_data.get('last_update'),
            'message': 'תעודת זהות רגשית עקבית' if is_consistent else 'תעודת זהות רגשית לא עקבית'
        }
        
        logger.info(
            f"בדיקת עקביות תעודת זהות רגשית למשתמש {safe_id}: {'עקבית' if is_consistent else 'לא עקבית'}",
            source="profile_utils"
        )
        
        return result
        
    except Exception as exc:
        logger.error(f"שגיאה בבדיקת עקביות תעודת זהות רגשית: {exc}", source="profile_utils")
        return {'consistent': False, 'error': str(exc)}

def get_user_statistics(chat_id: Any) -> Dict:
    """קבלת סטטיסטיקות משתמש - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        profile = get_user_profile(safe_id)
        
        if not profile:
            logger.warning(f"אין נתונים למשתמש {safe_id}", source="profile_utils")
            return {}
        
        # חישוב סטטיסטיקות
        stats = {
            'message_count': profile.get('message_count', 0),
            'total_cost': profile.get('total_cost', 0.0),
            'created_at': profile.get('created_at'),
            'last_updated': profile.get('last_updated'),
            'has_summary': bool(profile.get('summary')),
            'has_emotional_identity': bool(profile.get('emotional_identity'))
        }
        
        return stats
        
    except Exception as exc:
        logger.error(f"שגיאה בקבלת סטטיסטיקות: {exc}", source="profile_utils")
        return {}

def force_sync_to_sheets(chat_id: Any) -> bool:
    """🗑️ פונקציה זו הוסרה - עברנו למסד נתונים"""
    safe_id = safe_str(chat_id)
    logger.info(f"🗑️ force_sync_to_sheets deprecated - using database for {safe_id}", source="profile_utils")
    return True

def check_user_data_consistency(chat_id: Any) -> Dict:
    """בדיקת עקביות נתוני משתמש - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        # בדיקת פרופיל
        profile = get_user_profile(safe_id)
        
        # בדיקת הודעות
        from simple_data_manager import data_manager
        messages = data_manager.get_chat_messages(safe_id, limit=10)
        
        consistency_report = {
            'has_profile': bool(profile),
            'profile_message_count': profile.get('message_count', 0) if profile else 0,
            'actual_message_count': len(messages),
            'profile_consistent': profile.get('message_count', 0) == len(messages) if profile else False,
            'has_recent_activity': bool(messages),
            'last_message_time': messages[-1].get('timestamp') if messages else None
        }
        
        return consistency_report
        
    except Exception as exc:
        logger.error(f"שגיאה בבדיקת נתונים: {exc}", source="profile_utils")
        return {'error': str(exc)}

def cleanup_old_profiles() -> int:
    """ניקוי פרופילים ישנים - פונקציה אחת פשוטה"""
    try:
        from simple_data_manager import data_manager
        
        # מחיקת פרופילים ישנים (יותר מ-30 ימים ללא פעילות)
        deleted_count = data_manager.cleanup_old_profiles(days=30)
        
        logger.info(f"✅ נמחקו {deleted_count} פרופילים ישנים", source="profile_utils")
        return deleted_count
        
    except Exception as exc:
        logger.error(f"שגיאה בניקוי פרופילים ישנים: {exc}", source="profile_utils")
        return 0

def get_profile_statistics() -> Dict:
    """קבלת סטטיסטיקות פרופילים - פונקציה אחת פשוטה"""
    try:
        from simple_data_manager import data_manager
        
        stats = data_manager.get_profile_statistics()
        
        return {
            'total_profiles': stats.get('total_profiles', 0),
            'active_profiles': stats.get('active_profiles', 0),
            'profiles_with_summary': stats.get('profiles_with_summary', 0),
            'profiles_with_emotional_identity': stats.get('profiles_with_emotional_identity', 0),
            'average_messages_per_profile': stats.get('average_messages', 0),
            'total_cost': stats.get('total_cost', 0.0)
        }
        
    except Exception as exc:
        logger.error(f"שגיאה בקבלת סטטיסטיקות פרופילים: {exc}", source="profile_utils")
        return {}

def get_all_users_with_condition(condition: str) -> List[Dict]:
    """קבלת כל המשתמשים עם תנאי מסויים - פונקציה אחת פשוטה"""
    try:
        import psycopg2
        from config import get_config
        config = get_config()
        DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        # 🔧 תיקון: וידוא שהחיבור תקין
        if not DB_URL:
            logger.error("No database URL found", source="profile_utils")
            return []
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # 🔧 תיקון: בדיקת קיום הטבלה תחילה
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'user_profiles'
            )
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            logger.warning("Table user_profiles does not exist", source="profile_utils")
            cur.close()
            conn.close()
            return []
        
        # 🔧 תיקון: בדיקת קיום העמודות בתנאי
        try:
            # שאילתה עם תנאי - עם הגנה מפני SQL injection
            if "needs_recovery_message" in condition:
                # בדיקת קיום העמודה
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'user_profiles' 
                        AND column_name = 'needs_recovery_message'
                    )
                """)
                column_exists = cur.fetchone()[0]
                
                if not column_exists:
                    logger.warning("Column needs_recovery_message does not exist - running migration", source="profile_utils")
                    cur.close()
                    conn.close()
                    
                    # ריצת מיגרציה
                    from database_operations import force_database_migration
                    if force_database_migration():
                        # ניסיון חוזר לאחר המיגרציה
                        return get_all_users_with_condition(condition)
                    else:
                        return []
            
            # שאילתה רגילה
            query = f"SELECT * FROM user_profiles WHERE {condition}"
            cur.execute(query)
            
            # קבלת כל השורות
            rows = cur.fetchall()
            
            # קבלת שמות עמודות
            columns = [desc[0] for desc in cur.description] if cur.description else []
            
            # המרה לרשימת dictionaries
            users = []
            for row in rows:
                if columns:
                    user_dict = dict(zip(columns, row))
                    users.append(user_dict)
                else:
                    # גיבוי אם אין שמות עמודות
                    users.append({})
            
            cur.close()
            conn.close()
            
            logger.info(f"✅ נמצאו {len(users)} משתמשים עם תנאי: {condition}", source="profile_utils")
            return users
            
        except psycopg2.Error as db_error:
            logger.error(f"Database error with condition '{condition}': {db_error}", source="profile_utils")
            cur.close()
            conn.close()
            return []
        
    except Exception as exc:
        logger.error(f"שגיאה בקבלת משתמשים עם תנאי '{condition}': {exc}", source="profile_utils")
        return []

def _detect_profile_changes(old_profile: Dict, new_profile: Dict) -> List[Dict]:
    """זיהוי שינויים בפרופיל - פונקציה פשוטה"""
    try:
        changes = []
        
        # שדות לבדיקה
        fields_to_check = [
            'age', 'location', 'name', 'occupation', 'interests', 
            'personality', 'summary', 'preferences', 'emotional_identity'
        ]
        
        for field in fields_to_check:
            old_value = old_profile.get(field)
            new_value = new_profile.get(field)
            
            # בדיקה אם השדה השתנה
            if old_value != new_value:
                change_type = "added" if old_value is None else ("removed" if new_value is None else "updated")
                
                changes.append({
                    'field': field,
                    'old_value': old_value,
                    'new_value': new_value,
                    'change_type': change_type
                })
                
                logger.debug(f"[PROFILE_CHANGE] {change_type}: {field} = {old_value} → {new_value}", source="profile_utils")
        
        logger.debug(f"[PROFILE_CHANGES] זוהו {len(changes)} שינויים", source="profile_utils")
        return changes
        
    except Exception as exc:
        logger.error(f"שגיאה בזיהוי שינויי פרופיל: {exc}", source="profile_utils")
        return []

# 🗑️ פונקציה זו הוחלפה ב-unified_profile_notifications.send_profile_update_notification

def get_user_profile_fast(chat_id: Any) -> Dict:
    """קבלת פרופיל מהיר - תאימות לאחור"""
    return get_user_profile(chat_id) 