#!/usr/bin/env python3
"""
🔧 Setup MCP Database Connection
מגדיר חיבור MCP למסד הנתונים בהתאם לקונפיגורציה הקיימת
"""

import json
import os
from pathlib import Path

def load_project_config():
    """טעינת קונפיגורציה של הפרויקט"""
    try:
        from config import get_config
        return get_config()
    except Exception as e:
        print(f"❌ שגיאה בטעינת קונפיגורציה: {e}")
        return None

def update_mcp_config():
    """עדכון קונפיגורציית MCP עם פרטי חיבור נכונים"""
    print("🔧 מגדיר MCP לפרויקט...")
    
    # טעינת קונפיגורציה
    config = load_project_config()
    if not config:
        return False
    
    # קבלת URL מסד הנתונים
    db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
    if not db_url:
        print("❌ לא נמצא URL למסד הנתונים בקונפיגורציה!")
        return False
    
    print(f"✅ נמצא חיבור למסד נתונים: {db_url[:30]}...")
    
    # יצירת קונפיגורציית MCP
    mcp_config = {
        "mcpServers": {
            "telegram-bot-postgres": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-postgres"],
                "env": {
                    "POSTGRES_CONNECTION_STRING": db_url
                }
            },
            "database-inspector": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-everything"],
                "env": {
                    "CONNECTION_STRING": db_url
                }
            }
        }
    }
    
    # יצירת תיקיית .cursor אם לא קיימת
    cursor_dir = Path(".cursor")
    cursor_dir.mkdir(exist_ok=True)
    
    # שמירת קונפיגורציה
    mcp_file = cursor_dir / "mcp.json"
    with open(mcp_file, 'w', encoding='utf-8') as f:
        json.dump(mcp_config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ קובץ MCP נוצר: {mcp_file}")
    print("🎯 שרתי MCP זמינים:")
    print("   • telegram-bot-postgres - חיבור ישיר למסד הנתונים")
    print("   • database-inspector - בדיקת מבני נתונים")
    
    return True

def test_database_connection():
    """בדיקת חיבור למסד הנתונים"""
    try:
        import psycopg2
        from config import config
        
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        print("🔍 בודק חיבור למסד הנתונים...")
        conn = psycopg2.connect(db_url)
        
        # בדיקת טבלאות קיימות
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = [row[0] for row in cur.fetchall()]
        
        print(f"✅ חיבור תקין! נמצאו {len(tables)} טבלאות:")
        for table in tables[:10]:  # הצגת 10 הראשונות
            print(f"   • {table}")
        
        if len(tables) > 10:
            print(f"   ... ועוד {len(tables) - 10} טבלאות")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ שגיאה בחיבור למסד הנתונים: {e}")
        return False

def main():
    """פונקציה ראשית"""
    print("🚀 הגדרת MCP למסד הנתונים של הטלגרם בוט")
    print("=" * 50)
    
    # בדיקת חיבור
    if not test_database_connection():
        print("❌ החיבור למסד הנתונים נכשל - בדוק את הקונפיגורציה")
        return
    
    # עדכון MCP
    if update_mcp_config():
        print("\n✅ הגדרת MCP הושלמה בהצלחה!")
        print("\n📋 שלבים הבאים:")
        print("1. פתח מחדש את Cursor (או Ctrl+Shift+P → 'Developer: Reload Window')")
        print("2. עבור להגדרות MCP: Ctrl+Shift+J → Features → Model Context Protocol")
        print("3. וודא שהשרתים מופיעים ברשימה")
        print("4. בצ'אט נסה: @test_connection() או @run_query(\"SELECT NOW()\")")
    else:
        print("❌ הגדרת MCP נכשלה")

if __name__ == "__main__":
    main() 