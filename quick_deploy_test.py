#!/usr/bin/env python3
"""
🔥 Quick Deploy Test - בדיקה מהירה אחרי פריסה
===================================================

סקריפט לבדיקה מהירה שהמערכת החדשה עובדת אחרי פריסה לרנדר
"""

import json
from datetime import datetime, timedelta

try:
    from check_deployment_logs_live import DeploymentLogsMonitor
    
    def check_new_mirror_activity():
        """בדיקה שהמירור החדש עובד"""
        print("🔥 === בדיקת פעילות מירור חדש ===")
        print(f"🕐 {datetime.now().strftime('%H:%M:%S')}")
        
        monitor = DeploymentLogsMonitor()
        
        # בדיקת לוגים מהדקות האחרונות
        print("\n📊 סטטיסטיקות כלליות:")
        stats = monitor.get_table_stats()
        if stats:
            print(f"   📋 סה\"כ לוגים: {stats['total_logs']:,}")
            print(f"   🔥 10 דקות אחרונות: {stats['last_10min']:,}")
            
            if stats.get('last_update'):
                time_diff = datetime.now() - stats['last_update'].replace(tzinfo=None)
                print(f"   📝 עדכון אחרון: {time_diff.total_seconds():.0f} שניות")
        
        # חיפוש לוגים מהמירור החדש
        print("\n🔍 חיפוש לוגים מהמירור החדש:")
        mirror_activity = monitor.check_render_mirror_activity()
        
        if mirror_activity:
            api_logs = mirror_activity.get('mirror_logs_last_hour', 0)
            internal_logs = mirror_activity.get('internal_capture_logs_last_hour', 0)
            
            print(f"   🌐 לוגי Render API: {api_logs}")
            print(f"   💻 לוגי תפיסה פנימית: {internal_logs}")
            
            if mirror_activity.get('last_mirror_log'):
                last_log = mirror_activity['last_mirror_log']
                time_diff = datetime.now() - last_log['time'].replace(tzinfo=None)
                print(f"   📝 מירור אחרון: {time_diff.total_seconds():.0f} שניות")
                print(f"      הודעה: {last_log['message']}")
        else:
            print("   ❌ אין נתוני מירור זמינים")
        
        # בדיקת מקורות לוגים
        if stats and stats.get('sources_last_hour'):
            print(f"\n📈 מקורות לוגים (שעה אחרונה):")
            render_mirror_count = stats['sources_last_hour'].get('render_api_mirror', 0)
            deployment_logger_count = stats['sources_last_hour'].get('deployment_logger', 0)
            
            print(f"   🔥 render_api_mirror: {render_mirror_count}")
            print(f"   📝 deployment_logger: {deployment_logger_count}")
            
            if render_mirror_count > 0:
                print("   ✅ המירור החדש פעיל!")
            else:
                print("   ⚠️ המירור החדש עדיין לא פעיל")
        
        return stats

    def check_deployment_sync_indicators():
        """בדיקת סימנים לסנכרון פריסה"""
        print("\n🚀 בדיקת סימני סנכרון פריסה:")
        
        monitor = DeploymentLogsMonitor()
        
        # חיפוש לוגים האחרונים שקשורים לפריסה
        recent_logs = monitor.get_recent_logs(50)
        
        deploy_indicators = [
            "deployment sync",
            "Starting Render",
            "mirror thread started",
            "render_api_mirror",
            "sync_deployment"
        ]
        
        found_indicators = []
        for log in recent_logs:
            message = log['message'].lower()
            for indicator in deploy_indicators:
                if indicator.lower() in message:
                    found_indicators.append({
                        'time': log['created_at'],
                        'message': log['message'],
                        'source': log['source_module']
                    })
                    break
        
        if found_indicators:
            print(f"   ✅ נמצאו {len(found_indicators)} סימני פריסה:")
            for indicator in found_indicators[:5]:  # 5 אחרונים
                time_str = indicator['time'].strftime('%H:%M:%S')
                print(f"   [{time_str}] {indicator['message'][:60]}...")
        else:
            print("   ⚠️ לא נמצאו סימני פריסה אחרונים")
        
        return found_indicators

    def main():
        """פונקציה ראשית"""
        print("🔥 === Quick Deploy Test ===")
        
        # 1. בדיקת פעילות כללית
        stats = check_new_mirror_activity()
        
        # 2. בדיקת סימני פריסה
        indicators = check_deployment_sync_indicators()
        
        # 3. המלצות
        print(f"\n💡 המלצות:")
        
        if stats:
            last_10min = stats.get('last_10min', 0)
            if last_10min > 50:
                print("   ✅ פעילות תקינה - הרבה לוגים ב-10 דקות אחרונות")
            elif last_10min > 10:
                print("   🟡 פעילות בינונית - מעט לוגים ב-10 דקות אחרונות")
            else:
                print("   🔴 פעילות נמוכה - מעט מאוד לוגים")
        
        if indicators:
            print("   ✅ נמצאו סימני פריסה - המערכת החדשה הופעלה")
        else:
            print("   ⚠️ לא נמצאו סימני פריסה - ייתכן שהפריסה עדיין לא הושלמה")
        
        print(f"\n🎯 מה לעשות הלאה:")
        print(f"   1. אם אין סימני פריסה - חכה 2-3 דקות ותריץ שוב")
        print(f"   2. שלח הודעה לבוט בטלגרם")
        print(f"   3. תריץ: python {__file__} שוב אחרי ההודעה")
        print(f"   4. בדוק שיש יותר לוגים עם render_api_mirror")

    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"❌ שגיאה בייבוא: {e}")
    print("💡 תוודא שהקבצים הנדרשים קיימים") 