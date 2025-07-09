#!/usr/bin/env python3
"""
🔍 בדיקת נפח אחסון גיבויים
בודק גודל גיבויים במסד נתונים ובקבצים מקומיים
"""

import os
import json
import psycopg2
from datetime import datetime
from config import config
from simple_logger import logger

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

def format_size(size_bytes):
    """מפרמט גודל לקריאה נעימה"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.1f}MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.1f}GB"

def check_database_storage():
    """בודק נפח אחסון במסד הנתונים"""
    try:
        print("🏠 בדיקת גיבויים פנימיים במסד הנתונים:")
        print("=" * 60)
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקת גודל מסד הנתונים הכולל
        cur.execute("""
            SELECT pg_size_pretty(pg_database_size(current_database())) as db_size,
                   pg_database_size(current_database()) as db_size_bytes
        """)
        db_size_pretty, db_size_bytes = cur.fetchone()
        
        print(f"📊 **גודל מסד הנתונים הכולל:** {db_size_pretty}")
        
        # בדיקת schemas של גיבוי
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata 
            WHERE schema_name LIKE 'backup_%'
            ORDER BY schema_name DESC
        """)
        backup_schemas = [row[0] for row in cur.fetchall()]
        
        if not backup_schemas:
            print("📭 אין schemas גיבוי פנימיים")
            return
        
        print(f"\n🔍 נמצאו {len(backup_schemas)} schemas גיבוי:")
        
        total_backup_size = 0
        for schema in backup_schemas:
            try:
                # בדיקת גודל schema
                cur.execute(f"""
                    SELECT 
                        SUM(pg_total_relation_size(schemaname||'.'||tablename)) as schema_size
                    FROM pg_tables 
                    WHERE schemaname = '{schema}'
                """)
                
                result = cur.fetchone()
                schema_size = result[0] if result[0] else 0
                total_backup_size += schema_size
                
                # בדיקת מספר טבלאות ורשומות
                cur.execute(f"""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = '{schema}'
                    AND table_name != 'backup_metadata'
                """)
                tables = [row[0] for row in cur.fetchall()]
                
                total_records = 0
                for table in tables:
                    cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
                    count = cur.fetchone()[0]
                    total_records += count
                
                # פירמוט תאריך
                try:
                    date_part = schema.replace("backup_", "")
                    date_obj = datetime.strptime(date_part, "%Y%m%d")
                    formatted_date = date_obj.strftime("%d/%m/%Y")
                except:
                    formatted_date = date_part
                
                print(f"   📅 {formatted_date} ({schema})")
                print(f"      📊 {total_records:,} רשומות | 💾 {format_size(schema_size)}")
                
            except Exception as e:
                print(f"   ❌ שגיאה בבדיקת {schema}: {e}")
        
        print(f"\n📊 **סה\"כ גיבויים פנימיים:** {format_size(total_backup_size)}")
        
        # אחוז מהמסד הכולל
        if db_size_bytes > 0:
            backup_percentage = (total_backup_size / db_size_bytes) * 100
            print(f"📈 **אחוז מהמסד הכולל:** {backup_percentage:.1f}%")
        
        # בדיקת מגבלות (אם ידועות)
        print(f"\n🔍 **מגבלות מסד נתונים:**")
        try:
            # נסיון לזהות ספק מסד הנתונים
            if "render" in DB_URL.lower():
                print("   🌐 **Render PostgreSQL**")
                print("   📦 **מגבלת נפח:** 1GB (תכנית חינם) / 10GB+ (תכנית בתשלום)")
            elif "railway" in DB_URL.lower():
                print("   🚂 **Railway PostgreSQL**")
                print("   📦 **מגבלת נפח:** 500MB (תכנית חינם) / 8GB+ (תכנית בתשלום)")
            elif "heroku" in DB_URL.lower():
                print("   🟣 **Heroku PostgreSQL**")
                print("   📦 **מגבלת נפח:** 1GB (תכנית חינם) / 10TB+ (תכנית בתשלום)")
            else:
                print("   ❓ **ספק לא מזוהה** - בדוק במנהל מסד הנתונים שלך")
            
            # אזהרות
            if db_size_bytes > 500 * 1024 * 1024:  # 500MB
                print("   ⚠️  **אזהרה:** המסד מעל 500MB - בדוק מגבלות!")
            elif db_size_bytes > 1024 * 1024 * 1024:  # 1GB
                print("   🚨 **דחוף:** המסד מעל 1GB - עלול להגיע למגבלה!")
        
        except Exception as e:
            print(f"   ❌ שגיאה בבדיקת מגבלות: {e}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת מסד הנתונים: {e}")

def check_render_environment():
    """בודק את סביבת הרנדר"""
    print("\n🌐 בדיקת סביבת רנדר:")
    print("=" * 60)
    
    # בדיקה אם רצים ברנדר
    is_render = os.getenv('RENDER') is not None
    print(f"📍 **סביבה:** {'Render' if is_render else 'מקומי/אחר'}")
    
    if is_render:
        print("💡 **הערה:** ברנדר אין דיסק קבוע - כל הגיבויים צריכים להיות במסד הנתונים")
    
    # בדיקת משתני סביבה רלוונטיים
    env_vars = ['RENDER_SERVICE_NAME', 'RENDER_SERVICE_TYPE', 'RENDER_REGION']
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"🔧 **{var}:** {value}")
    
    return is_render

def check_backup_recommendations():
    """המלצות לגיבוי"""
    print("\n💡 **המלצות אחסון גיבויים:**")
    print("=" * 60)
    
    print("🏠 **גיבוי פנימי (במסד הנתונים):**")
    print("   ✅ **יתרונות:** מהיר, בטוח, בתוך אותו מסד")
    print("   ❌ **חסרונות:** תופס מקום במסד, כפוף למגבלות הספק")
    print("   🎯 **מתאים ל:** גיבויים קצרי טווח (7-14 ימים)")
    
    print("\n🌐 **ברנדר:**")
    print("   ✅ **יתרונות:** אין דיסק קבוע, הכל במסד הנתונים")
    print("   ❌ **חסרונות:** מגבלת נפח מסד הנתונים")
    print("   🎯 **מתאים ל:** גיבוי פנימי בלבד - 7 ימים")
    
    print("\n🔧 **אפשרויות:**")
    print("   1️⃣ **גיבוי פנימי בלבד:** פשטות מקסימלית (מומלץ לרנדר)")
    print("   2️⃣ **גיבוי חיצוני:** אם נדרש גיבוי ארוך טווח")

def main():
    """בדיקה מקיפה של אחסון גיבויים"""
    print("🔍 **בדיקת נפח אחסון גיבויים**")
    print("=" * 80)
    
    # בדיקת גיבויים במסד
    check_database_storage()
    
    # בדיקת סביבת רנדר
    check_render_environment()
    
    # המלצות
    check_backup_recommendations()
    
    print("\n" + "=" * 80)
    print("✅ **בדיקת אחסון הושלמה**")

if __name__ == "__main__":
    main() 