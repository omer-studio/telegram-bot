#!/usr/bin/env python3
"""
Load extracted chat data to database - Minimal version
"""

import json
import sys
import os
from datetime import datetime
import logging
import psycopg2

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load config from JSON file
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "etc", "secrets", "config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config()
DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

class MinimalDataLoader:
    def __init__(self):
        self.loaded_count = {
            'chat_messages': 0,
            'gpt_calls': 0,
            'errors': 0
        }
        
    def get_db_connection(self):
        """Get database connection"""
        try:
            return psycopg2.connect(DB_URL)
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return None
    
    def load_chat_messages(self, messages_data):
        """Load chat messages to database"""
        logger.info(f"🔄 Loading {len(messages_data)} chat messages...")
        
        conn = self.get_db_connection()
        if not conn:
            return
        
        try:
            cur = conn.cursor()
            
            for item in messages_data:
                try:
                    data = item.get('data', {})
                    
                    # Skip if no meaningful data
                    if not data or not isinstance(data, dict):
                        continue
                    
                    # Extract chat message data
                    chat_id = data.get('chat_id')
                    user_msg = data.get('user_msg')
                    gpt_a_response = data.get('gpt_a_response')
                    timestamp_start = data.get('timestamp_start')
                    
                    # Skip if no essential data
                    if not chat_id or not user_msg:
                        continue
                    
                    # Convert chat_id to string
                    chat_id = str(chat_id)
                    
                    # Convert timestamp string to datetime if needed
                    if timestamp_start and isinstance(timestamp_start, str):
                        try:
                            timestamp_start = datetime.fromisoformat(timestamp_start.replace('Z', '+00:00'))
                        except:
                            timestamp_start = datetime.utcnow()
                    else:
                        timestamp_start = datetime.utcnow()
                    
                    # Check if message already exists
                    cur.execute(
                        "SELECT id FROM chat_messages WHERE chat_id = %s AND user_msg = %s AND timestamp = %s",
                        (chat_id, user_msg, timestamp_start)
                    )
                    if cur.fetchone():
                        continue
                    
                    # Insert message
                    cur.execute(
                        "INSERT INTO chat_messages (chat_id, user_msg, bot_msg, timestamp) VALUES (%s, %s, %s, %s)",
                        (chat_id, user_msg, gpt_a_response or '', timestamp_start)
                    )
                    
                    self.loaded_count['chat_messages'] += 1
                    
                    if self.loaded_count['chat_messages'] % 10 == 0:
                        logger.info(f"✅ Loaded {self.loaded_count['chat_messages']} messages...")
                        
                except Exception as e:
                    logger.error(f"❌ Error loading chat message: {e}")
                    continue
            
            conn.commit()
            cur.close()
            
        except Exception as e:
            logger.error(f"❌ Error in chat messages loading: {e}")
        finally:
            conn.close()
    
    def load_gpt_calls(self, gpt_calls_data):
        """Load GPT calls to database"""
        logger.info(f"🔄 Loading {len(gpt_calls_data)} GPT calls...")
        
        conn = self.get_db_connection()
        if not conn:
            return
        
        try:
            cur = conn.cursor()
            
            for item in gpt_calls_data:
                try:
                    data = item.get('data', {})
                    
                    # Skip if no meaningful data
                    if not data or not isinstance(data, dict):
                        continue
                    
                    # Extract GPT call data
                    model = data.get('model')
                    usage_data = data.get('usage', {})
                    total_tokens = usage_data.get('total_tokens', 0)
                    timestamp = data.get('timestamp')
                    
                    # Skip if no essential data
                    if not model or not timestamp:
                        continue
                    
                    # Convert timestamp string to datetime if needed
                    if timestamp and isinstance(timestamp, str):
                        try:
                            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except:
                            timestamp = datetime.utcnow()
                    else:
                        timestamp = datetime.utcnow()
                    
                    # 🚫 DISABLED: gpt_usage_log הושבתה - משתמש ב-gpt_calls_log במקום
                    # Check if call already exists in gpt_calls_log instead
                    cur.execute(
                        "SELECT id FROM gpt_calls_log WHERE call_type = %s AND timestamp = %s AND tokens_input + tokens_output = %s",
                        ('extracted_data', timestamp, total_tokens)
                    )
                    if cur.fetchone():
                        continue
                    
                    # Insert GPT call to gpt_calls_log instead of gpt_usage_log
                    cur.execute(
                        "INSERT INTO gpt_calls_log (chat_id, call_type, request_data, response_data, tokens_input, tokens_output, cost_usd, processing_time_seconds, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            data.get('chat_id'),
                            'extracted_data',
                            json.dumps({'model': model, 'type': data.get('type', 'unknown')}),
                            json.dumps(usage_data),
                            usage_data.get('prompt_tokens', 0),
                            usage_data.get('completion_tokens', 0),
                            data.get('cost_total', 0),
                            0,  # processing_time not available
                            timestamp
                        )
                    )
                    
                    self.loaded_count['gpt_calls'] += 1
                    
                    if self.loaded_count['gpt_calls'] % 10 == 0:
                        logger.info(f"✅ Loaded {self.loaded_count['gpt_calls']} GPT calls...")
                        
                except Exception as e:
                    logger.error(f"❌ Error loading GPT call: {e}")
                    continue
            
            conn.commit()
            cur.close()
            
        except Exception as e:
            logger.error(f"❌ Error in GPT calls loading: {e}")
        finally:
            conn.close()
    
    def load_errors(self, errors_data):
        """Load errors to database"""
        logger.info(f"🔄 Loading {len(errors_data)} errors...")
        
        conn = self.get_db_connection()
        if not conn:
            return
        
        try:
            cur = conn.cursor()
            
            for item in errors_data:
                try:
                    data = item.get('data', {})
                    
                    # Skip if no meaningful data
                    if not data or not isinstance(data, dict):
                        continue
                    
                    # Extract error data
                    error_type = data.get('error_type')
                    error_message = data.get('error')
                    chat_id = data.get('chat_id')
                    timestamp = data.get('timestamp')
                    
                    # Skip if no essential data
                    if not error_message or not timestamp:
                        continue
                    
                    # Convert timestamp string to datetime if needed
                    if timestamp and isinstance(timestamp, str):
                        try:
                            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except:
                            timestamp = datetime.utcnow()
                    else:
                        timestamp = datetime.utcnow()
                    
                    # 🚫 DISABLED: system_logs הושבתה - משתמש ב-bot_error_logs במקום
                    # Check if error already exists in bot_error_logs instead
                    cur.execute(
                        "SELECT id FROM bot_error_logs WHERE error_message = %s AND timestamp = %s",
                        (error_message, timestamp)
                    )
                    if cur.fetchone():
                        continue
                    
                    # Insert error to bot_error_logs instead of system_logs
                    cur.execute(
                        "INSERT INTO bot_error_logs (error_type, error_message, chat_id, user_message, timestamp, error_data) VALUES (%s, %s, %s, %s, %s, %s)",
                        (
                            error_type or 'unknown',
                            error_message,
                            chat_id,
                            data.get('user_msg'),
                            timestamp,
                            json.dumps(data)
                        )
                    )
                    
                    self.loaded_count['errors'] += 1
                    
                    if self.loaded_count['errors'] % 5 == 0:
                        logger.info(f"✅ Loaded {self.loaded_count['errors']} errors...")
                        
                except Exception as e:
                    logger.error(f"❌ Error loading error: {e}")
                    continue
            
            conn.commit()
            cur.close()
            
        except Exception as e:
            logger.error(f"❌ Error in errors loading: {e}")
        finally:
            conn.close()
    
    def load_extracted_data(self, extracted_file):
        """Load all extracted data to database"""
        try:
            logger.info(f"📂 Loading data from: {extracted_file}")
            
            with open(extracted_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load chat messages
            if 'chat_messages' in data:
                self.load_chat_messages(data['chat_messages'])
            
            # Load GPT calls
            if 'gpt_calls' in data:
                self.load_gpt_calls(data['gpt_calls'])
            
            # Load errors
            if 'errors' in data:
                self.load_errors(data['errors'])
            
            logger.info("✅ Data loading completed!")
            
        except Exception as e:
            logger.error(f"❌ Error loading extracted data: {e}")
    
    def print_summary(self):
        """Print loading summary"""
        print("\n" + "="*60)
        print("📊 LOADING SUMMARY")
        print("="*60)
        
        print(f"💬 Chat messages loaded: {self.loaded_count['chat_messages']}")
        print(f"🤖 GPT calls loaded: {self.loaded_count['gpt_calls']}")
        print(f"❌ Errors loaded: {self.loaded_count['errors']}")
        
        total_loaded = sum(self.loaded_count.values())
        print(f"📈 Total items loaded: {total_loaded}")
        
        print("\n" + "="*60)

def main():
    """Main loading function"""
    print("🚀 Starting data loading to database...")
    
    if not DB_URL:
        print("❌ No database URL found in config!")
        return
    
    print(f"🔗 Database URL: {DB_URL[:50]}...")
    
    # Find the most recent extracted data file
    extracted_files = [f for f in os.listdir('.') if f.startswith('extracted_chat_data_') and f.endswith('.json')]
    
    if not extracted_files:
        print("❌ No extracted data files found!")
        return
    
    # Sort by timestamp and get the most recent
    extracted_files.sort(reverse=True)
    latest_file = extracted_files[0]
    
    print(f"📁 Using file: {latest_file}")
    
    # Load data
    loader = MinimalDataLoader()
    loader.load_extracted_data(latest_file)
    
    # Print summary
    loader.print_summary()
    
    print(f"\n✅ Data loading complete!")
    print("💾 All data has been loaded to the database")

if __name__ == "__main__":
    main() 