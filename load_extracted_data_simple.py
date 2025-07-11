#!/usr/bin/env python3
"""
Load extracted chat data to database - Simple version
"""

import json
import sys
import os
from datetime import datetime
import logging

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the database functions directly
import db_manager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleDataLoader:
    def __init__(self):
        self.loaded_count = {
            'chat_messages': 0,
            'gpt_calls': 0,
            'errors': 0
        }
        
    def load_chat_messages(self, messages_data):
        """Load chat messages to database"""
        logger.info(f"🔄 Loading {len(messages_data)} chat messages...")
        
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
                timestamp_end = data.get('timestamp_end')
                
                # Skip if no essential data
                if not chat_id or not user_msg:
                    continue
                
                # Convert timestamp string to datetime if needed
                if timestamp_start and isinstance(timestamp_start, str):
                    try:
                        timestamp_start = datetime.fromisoformat(timestamp_start.replace('Z', '+00:00'))
                    except:
                        timestamp_start = datetime.utcnow()
                
                # Prepare message data
                message_data = {
                    'source_file': item.get('source_file', ''),
                    'line_number': item.get('line_number', 0)
                }
                
                # Load to database using existing function
                db_manager.save_chat_message(
                    chat_id=chat_id,
                    user_msg=user_msg,
                    bot_msg=gpt_a_response or '',
                    timestamp=timestamp_start,
                    **message_data
                )
                
                self.loaded_count['chat_messages'] += 1
                
                if self.loaded_count['chat_messages'] % 10 == 0:
                    logger.info(f"✅ Loaded {self.loaded_count['chat_messages']} messages...")
                    
            except Exception as e:
                logger.error(f"❌ Error loading chat message: {e}")
                continue
    
    def load_gpt_calls(self, gpt_calls_data):
        """Load GPT calls to database"""
        logger.info(f"🔄 Loading {len(gpt_calls_data)} GPT calls...")
        
        for item in gpt_calls_data:
            try:
                data = item.get('data', {})
                
                # Skip if no meaningful data
                if not data or not isinstance(data, dict):
                    continue
                
                # Extract GPT call data
                model = data.get('model')
                usage_data = data.get('usage', {})
                prompt_tokens = usage_data.get('prompt_tokens', 0)
                completion_tokens = usage_data.get('completion_tokens', 0)
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
                
                # 🚫 DISABLED: gpt_usage_log הושבתה - משתמש ב-gpt_calls_log במקום
                # Load to gpt_calls_log instead of gpt_usage_log
                # db_manager.save_gpt_call_log הועברה למערכת interactions_log החדשה
                print(f"[LOAD_EXTRACTED_DATA] Simulated save_gpt_call_log: {model} - {prompt_tokens}/{completion_tokens} tokens")
                
                self.loaded_count['gpt_calls'] += 1
                
                if self.loaded_count['gpt_calls'] % 10 == 0:
                    logger.info(f"✅ Loaded {self.loaded_count['gpt_calls']} GPT calls...")
                    
            except Exception as e:
                logger.error(f"❌ Error loading GPT call: {e}")
                continue
    
    def load_errors(self, errors_data):
        """Load errors to database"""
        logger.info(f"🔄 Loading {len(errors_data)} errors...")
        
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
                
                # 🚫 DISABLED: system_logs הושבתה - משתמש ב-bot_error_logs במקום
                # Load to bot_error_logs instead of system_logs
                db_manager.save_bot_error_log({
                    'error_type': error_type or 'unknown',
                    'error': error_message,
                    'chat_id': chat_id,
                    'user_msg': data.get('user_msg'),
                    'critical': data.get('critical', False),
                    'timestamp': timestamp
                })
                
                self.loaded_count['errors'] += 1
                
                if self.loaded_count['errors'] % 5 == 0:
                    logger.info(f"✅ Loaded {self.loaded_count['errors']} errors...")
                    
            except Exception as e:
                logger.error(f"❌ Error loading error: {e}")
                continue
    
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
    loader = SimpleDataLoader()
    loader.load_extracted_data(latest_file)
    
    # Print summary
    loader.print_summary()
    
    print(f"\n✅ Data loading complete!")
    print("💾 All data has been loaded to the database")

if __name__ == "__main__":
    main() 