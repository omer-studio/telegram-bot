#!/usr/bin/env python3
"""
🔧 Simple Database Interface for MCP
פתרון Python שעובד בלי Node.js
"""

import json
import sys
from config import config
import psycopg2
from psycopg2.extras import RealDictCursor

class SimpleDatabaseMCP:
    def __init__(self):
        self.db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
    
    def test_connection(self):
        """בדיקת חיבור למסד הנתונים"""
        try:
            conn = psycopg2.connect(self.db_url)
            conn.close()
            return {"status": "success", "message": "חיבור תקין למסד הנתונים"}
        except Exception as e:
            return {"status": "error", "message": f"שגיאה בחיבור: {e}"}
    
    def run_query(self, query, limit=50):
        """הרצת שאילתה במסד הנתונים"""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # הגבלת תוצאות לביטחון
            if "LIMIT" not in query.upper() and "SELECT" in query.upper():
                query += f" LIMIT {limit}"
            
            cur.execute(query)
            
            if query.strip().upper().startswith('SELECT'):
                results = cur.fetchall()
                # המרה לרשימת dictionaries
                return {
                    "status": "success", 
                    "data": [dict(row) for row in results],
                    "count": len(results)
                }
            else:
                conn.commit()
                return {"status": "success", "message": "שאילתה בוצעה בהצלחה"}
                
        except Exception as e:
            return {"status": "error", "message": f"שגיאה בשאילתה: {e}"}
        finally:
            if 'conn' in locals():
                conn.close()
    
    def query_table_info(self, table_name):
        """קבלת מידע על מבנה טבלה"""
        query = f"""
        SELECT 
            column_name, 
            data_type, 
            is_nullable,
            column_default
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
        """
        return self.run_query(query)
    
    def list_tables(self):
        """רשימת כל הטבלאות"""
        query = """
        SELECT 
            table_name,
            (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
        FROM information_schema.tables t
        WHERE table_schema = 'public'
        ORDER BY table_name
        """
        return self.run_query(query)

def main():
    if len(sys.argv) < 2:
        print("שימוש:")
        print("  python simple_mcp_db.py test_connection")
        print("  python simple_mcp_db.py run_query \"SELECT * FROM chat_messages LIMIT 5\"")
        print("  python simple_mcp_db.py query_table_info chat_messages")
        print("  python simple_mcp_db.py list_tables")
        return
    
    mcp = SimpleDatabaseMCP()
    command = sys.argv[1]
    
    if command == "test_connection":
        result = mcp.test_connection()
    elif command == "run_query" and len(sys.argv) > 2:
        result = mcp.run_query(sys.argv[2])
    elif command == "query_table_info" and len(sys.argv) > 2:
        result = mcp.query_table_info(sys.argv[2])
    elif command == "list_tables":
        result = mcp.list_tables()
    else:
        result = {"status": "error", "message": "פקודה לא זוהתה"}
    
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

if __name__ == "__main__":
    main() 