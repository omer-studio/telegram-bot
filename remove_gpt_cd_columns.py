"""
remove_gpt_cd_columns.py
-----------------------
סקריפט להסרת עמודות gpt_c ו-gpt_d מהגיליון Google Sheets.
"""
from config import setup_google_sheets

def remove_gpt_cd_columns():
    """
    מסיר את כל העמודות של gpt_c ו-gpt_d מהגיליון.
    """
    try:
        sheet_users, sheet_log, sheet_states = setup_google_sheets()
        
        # רשימת העמודות להסרה
        columns_to_remove = [
            "usage_prompt_tokens_gpt_c",
            "usage_completion_tokens_gpt_c", 
            "usage_total_tokens_gpt_c",
            "cached_tokens_gpt_c",
            "cost_gpt_c",
            "model_gpt_c",
            "usage_prompt_tokens_gpt_d",
            "usage_completion_tokens_gpt_d",
            "usage_total_tokens_gpt_d", 
            "cached_tokens_gpt_d",
            "cost_gpt_d",
            "model_gpt_d",
            "fields_updated_by_gpt_d"
        ]
        
        print("🔍 בודק עמודות בגיליון הלוגים...")
        header = sheet_log.row_values(1)
        print(f"כותרות קיימות: {header}")
        
        # מצא עמודות להסרה
        columns_to_delete = []
        for col_name in columns_to_remove:
            if col_name in header:
                col_index = header.index(col_name) + 1  # +1 כי Google Sheets מתחיל מ-1
                columns_to_delete.append((col_index, col_name))
                print(f"✅ נמצאה עמודה להסרה: {col_name} (עמודה {col_index})")
            else:
                print(f"ℹ️ עמודה לא קיימת: {col_name}")
        
        if not columns_to_delete:
            print("✅ אין עמודות gpt_c/D להסרה!")
            return
        
        # הסר עמודות (מהסוף להתחלה כדי לא לשנות אינדקסים)
        columns_to_delete.sort(reverse=True)  # מהסוף להתחלה
        
        for col_index, col_name in columns_to_delete:
            print(f"🗑️ מסיר עמודה: {col_name} (עמודה {col_index})")
            sheet_log.delete_columns(col_index)
        
        print("✅ הסרת עמודות הושלמה!")
        
        # בדוק את הכותרות החדשות
        new_header = sheet_log.row_values(1)
        print(f"כותרות חדשות: {new_header}")
        
    except Exception as e:
        print(f"❌ שגיאה בהסרת עמודות: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    remove_gpt_cd_columns() 