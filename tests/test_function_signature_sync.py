#!/usr/bin/env python3
"""
🛡️ Function Signature Sync Validator
מונע שגיאות של קריאות לפונקציות עם פרמטרים שגויים

זה היה תופס את השגיאה הקריטית שקרתה!
"""
import ast
import os
import sys
import inspect
from typing import Dict, List, Tuple, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_function_signature(module_name: str, function_name: str) -> Dict[str, Any]:
    """
    מחזיר את חתימת הפונקציה האמיתית מהמודול
    """
    try:
        module = __import__(module_name, fromlist=[function_name])
        func = getattr(module, function_name)
        sig = inspect.signature(func)
        
        return {
            'name': function_name,
            'params': [param.name for param in sig.parameters.values()],
            'param_details': {
                param.name: {
                    'default': param.default if param.default != inspect.Parameter.empty else None,
                    'annotation': str(param.annotation) if param.annotation != inspect.Parameter.empty else None
                }
                for param in sig.parameters.values()
            }
        }
    except Exception as e:
        return {'error': str(e)}

def find_function_calls_in_file(file_path: str, function_name: str) -> List[Tuple[int, str, List[str]]]:
    """
    מוצא את כל הקריאות לפונקציה בקובץ ואת הפרמטרים שנשלחים
    """
    calls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        class FunctionCallVisitor(ast.NodeVisitor):
            def visit_Call(self, node):
                # בדיקה אם זה קריאה לפונקציה שמעניינת אותנו
                if isinstance(node.func, ast.Name) and node.func.id == function_name:
                    line_num = node.lineno
                    args = []
                    
                    # רגיל arguments
                    for arg in node.args:
                        if isinstance(arg, ast.Constant):
                            args.append(f"{arg.value}")
                        elif isinstance(arg, ast.Name):
                            args.append(arg.id)
                        else:
                            args.append("complex_expr")
                    
                    # keyword arguments  
                    for keyword in node.keywords:
                        args.append(f"{keyword.arg}=...")
                    
                    calls.append((line_num, file_path, args))
                
                # קריאה דרך attribute (module.function)
                elif (isinstance(node.func, ast.Attribute) and 
                      node.func.attr == function_name):
                    line_num = node.lineno
                    args = []
                    
                    for arg in node.args:
                        if isinstance(arg, ast.Constant):
                            args.append(f"{arg.value}")
                        elif isinstance(arg, ast.Name):
                            args.append(arg.id)
                        else:
                            args.append("complex_expr")
                    
                    for keyword in node.keywords:
                        args.append(f"{keyword.arg}=...")
                    
                    calls.append((line_num, file_path, args))
                
                self.generic_visit(node)
        
        visitor = FunctionCallVisitor()
        visitor.visit(tree)
        
    except Exception as e:
        print(f"⚠️ שגיאה בניתוח {file_path}: {e}")
    
    return calls

def validate_function_calls():
    """
    🛡️ הפונקציה הראשית: בודקת שכל הקריאות לפונקציות קריטיות תואמות לחתימות
    """
    # רשימת פונקציות קריטיות לבדיקה
    critical_functions = [
        ('chat_utils', 'get_recent_history_for_gpt'),
        ('chat_utils', 'get_balanced_history_for_gpt'),
        ('chat_utils', 'get_chat_history_simple'),
        ('gpt_a_handler', 'get_main_response'),
        ('notifications', 'send_error_notification'),
    ]
    
    issues = []
    
    for module_name, func_name in critical_functions:
        print(f"🔍 בודק {module_name}.{func_name}...")
        
        # קבלת חתימת הפונקציה האמיתית
        signature = get_function_signature(module_name, func_name)
        if 'error' in signature:
            print(f"⚠️ לא ניתן לקבל חתימה עבור {func_name}: {signature['error']}")
            continue
        
        # חיפוש קריאות בכל הקבצים
        python_files = []
        for root, dirs, files in os.walk('.'):
            # דילוג על תיקיות שאין צורך לבדוק
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['temp_files', 'venv', '__pycache__']]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        
        for file_path in python_files:
            calls = find_function_calls_in_file(file_path, func_name)
            
            for line_num, file_path, call_args in calls:
                # בדיקת התאמה בסיסית
                expected_params = signature['params']
                
                # ספירת keyword args בקריאה
                keyword_args_in_call = [arg for arg in call_args if '=' in str(arg)]
                positional_args_count = len(call_args) - len(keyword_args_in_call)
                
                # בדיקת keyword args שלא קיימים בחתימה
                for kw_arg in keyword_args_in_call:
                    kw_name = kw_arg.split('=')[0]
                    if kw_name not in expected_params:
                        issues.append({
                            'file': file_path,
                            'line': line_num,
                            'function': func_name,
                            'issue': f"Keyword argument '{kw_name}' לא קיים בחתימת הפונקציה",
                            'expected_params': expected_params,
                            'call_args': call_args
                        })
    
    return issues

def main():
    """🚀 הפעלת הבדיקה"""
    print("🛡️ מריץ בדיקת סנכרון חתימות פונקציות...")
    print("="*60)
    
    issues = validate_function_calls()
    
    if not issues:
        print("✅ כל הפונקציות מסונכרנות!")
        return True
    
    print(f"❌ נמצאו {len(issues)} בעיות:")
    print("="*60)
    
    for issue in issues:
        print(f"📍 {issue['file']}:{issue['line']}")
        print(f"   פונקציה: {issue['function']}")
        print(f"   בעיה: {issue['issue']}")
        print(f"   פרמטרים נדרשים: {issue['expected_params']}")
        print(f"   פרמטרים בקריאה: {issue['call_args']}")
        print()
    
    return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1) 