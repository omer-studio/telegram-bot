#!/usr/bin/env python3
"""
🪣 גיבוי ל-AWS S3 (אפשרות נוספת)
"""

import os
import json
import boto3
from datetime import datetime
from simple_logger import logger

# הגדרת AWS (דרוש API Key)
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY") 
AWS_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "telegram-bot-backups")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def upload_to_s3(file_path, s3_key):
    """מעלה קובץ ל-S3"""
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
        
        s3_client.upload_file(file_path, AWS_BUCKET_NAME, s3_key)
        logger.info(f"☁️ הועלה ל-S3: {s3_key}")
        return True
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהעלאה ל-S3: {e}")
        return False

def backup_to_s3():
    """מגבה את כל קבצי הגיבוי ל-S3"""
    try:
        backup_date = datetime.now().strftime("%Y%m%d")
        backup_dir = "backups/daily_db_backups"
        
        if not os.path.exists(backup_dir):
            logger.error("❌ תיקיית גיבויים לא קיימת")
            return False
        
        uploaded_files = 0
        for filename in os.listdir(backup_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(backup_dir, filename)
                s3_key = f"daily_backups/{backup_date}/{filename}"
                
                if upload_to_s3(file_path, s3_key):
                    uploaded_files += 1
        
        logger.info(f"☁️ גיבוי S3 הושלם: {uploaded_files} קבצים")
        return uploaded_files > 0
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי S3: {e}")
        return False

if __name__ == "__main__":
    if AWS_ACCESS_KEY and AWS_SECRET_KEY:
        backup_to_s3()
    else:
        print("⚠️ AWS credentials לא מוגדרים") 