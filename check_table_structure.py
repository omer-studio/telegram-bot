#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🔍 בדיקת מבנה טבלת user_profiles במסד הנתונים
"""

import json
import psycopg2

def load_config():
    """טעינת קונפיגורציה"""
    try:
        from config import get_config
            return get_config()
    except Exception as e:
        print(f"❌ שגיאה בטעינת קונפיגורציה: {e}")
        return {}

def check_table_structure():
    """
    בדיקת מבנה הטבלה במסד הנתונים
    """
    try:
        config = load_config()
        if not config:
            return
            
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        if not db_url:
            print("❌ לא נמצא URL למסד הנתונים")
            return
            
        print("🔍 בדיקת מבנה טבלת user_profiles")
        print("=" * 50)
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # בדיקת קיום הטבלה
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'user_profiles'
            );
        """)
        
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("❌ טבלת user_profiles לא קיימת!")
            
            # בדיקת כל הטבלאות הקיימות
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            
            tables = cur.fetchall()
            print(f"\n📋 טבלאות קיימות במסד:")
            for table in tables:
                print(f"   - {table[0]}")
                
        else:
            print("✅ טבלת user_profiles קיימת!")
            
            # בדיקת מבנה הטבלה
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'user_profiles'
                ORDER BY ordinal_position;
            """)
            
            columns = cur.fetchall()
            print(f"\n📋 מבנה טבלת user_profiles ({len(columns)} עמודות):")
            for column_name, data_type, is_nullable, default_value in columns:
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                default = f" DEFAULT {default_value}" if default_value else ""
                print(f"   - {column_name}: {data_type} {nullable}{default}")
            
            # חיפוש עמודות שקשורות לקוד אישור
            approval_related_columns = []
            for column_name, _, _, _ in columns:
                if any(keyword in column_name.lower() for keyword in ['code', 'approve', 'auth', 'access']):
                    approval_related_columns.append(column_name)
            
            if approval_related_columns:
                print(f"\n🔍 עמודות הקשורות לאישור:")
                for col in approval_related_columns:
                    print(f"   - {col}")
            
            # בדיקת הנתונים בטבלה
            cur.execute("SELECT COUNT(*) FROM user_profiles;")
            total_rows = cur.fetchone()[0]
            print(f"\n📊 סה״כ שורות בטבלה: {total_rows}")
            
            if total_rows > 0:
                # הצגת דוגמאות של שורות
                cur.execute("SELECT * FROM user_profiles LIMIT 3;")
                sample_rows = cur.fetchall()
                
                print(f"\n📋 דוגמאות נתונים (3 שורות ראשונות):")
                column_names = [desc[0] for desc in cur.description]
                
                if sample_rows:
                    for i, row in enumerate(sample_rows or [], 1):
                        if row:
                            print(f"\n   שורה #{i}:")
                            for j, value in enumerate(row):
                                if value is not None:
                                    print(f"     {column_names[j]}: {value}")
                else:
                    print("   אין נתונים להצגה")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_table_structure() 