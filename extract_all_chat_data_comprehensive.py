#!/usr/bin/env python3
"""
Comprehensive Chat Data Extraction Script
Extracts all possible chat data from various sources and loads to database
"""

import json
import csv
import re
import sqlite3
import os
import sys
from datetime import datetime
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChatDataExtractor:
    def __init__(self):
        self.extracted_data = {
            'chat_messages': [],
            'user_profiles': [],
            'gpt_calls': [],
            'errors': []
        }
        self.processed_files = []
        
    def extract_from_json(self, file_path):
        """Extract data from JSON files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                # Check if it's chat history
                if 'messages' in data or 'chat_history' in data:
                    messages = data.get('messages', data.get('chat_history', []))
                    for msg in messages:
                        if isinstance(msg, dict):
                            self.extracted_data['chat_messages'].append({
                                'source_file': str(file_path),
                                'data': msg
                            })
                
                # Check if it's user profiles
                if 'users' in data or 'profiles' in data:
                    users = data.get('users', data.get('profiles', []))
                    for user in users:
                        if isinstance(user, dict):
                            self.extracted_data['user_profiles'].append({
                                'source_file': str(file_path),
                                'data': user
                            })
                
                # Check for other data types
                if 'errors' in data:
                    self.extracted_data['errors'].append({
                        'source_file': str(file_path),
                        'data': data
                    })
            
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        # Check if it's a message
                        if 'message' in item or 'text' in item or 'chat_id' in item:
                            self.extracted_data['chat_messages'].append({
                                'source_file': str(file_path),
                                'data': item
                            })
                        # Check if it's a user profile
                        elif 'user_id' in item and ('name' in item or 'username' in item):
                            self.extracted_data['user_profiles'].append({
                                'source_file': str(file_path),
                                'data': item
                            })
                        # Check if it's a GPT call
                        elif 'model' in item or 'prompt' in item or 'response' in item:
                            self.extracted_data['gpt_calls'].append({
                                'source_file': str(file_path),
                                'data': item
                            })
            
            self.processed_files.append(str(file_path))
            logger.info(f"✅ Processed JSON file: {file_path}")
            
        except Exception as e:
            logger.error(f"❌ Error processing JSON file {file_path}: {e}")
    
    def extract_from_jsonl(self, file_path):
        """Extract data from JSONL files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        if line.strip():
                            data = json.loads(line.strip())
                            if isinstance(data, dict):
                                # Check if it's a message
                                if 'message' in data or 'text' in data or 'chat_id' in data:
                                    self.extracted_data['chat_messages'].append({
                                        'source_file': str(file_path),
                                        'line_number': line_num,
                                        'data': data
                                    })
                                # Check if it's a GPT call
                                elif 'model' in data or 'prompt' in data or 'response' in data:
                                    self.extracted_data['gpt_calls'].append({
                                        'source_file': str(file_path),
                                        'line_number': line_num,
                                        'data': data
                                    })
                                # Check if it's an error
                                elif 'error' in data or 'exception' in data:
                                    self.extracted_data['errors'].append({
                                        'source_file': str(file_path),
                                        'line_number': line_num,
                                        'data': data
                                    })
                    except json.JSONDecodeError:
                        continue
            
            self.processed_files.append(str(file_path))
            logger.info(f"✅ Processed JSONL file: {file_path}")
            
        except Exception as e:
            logger.error(f"❌ Error processing JSONL file {file_path}: {e}")
    
    def extract_from_csv(self, file_path):
        """Extract data from CSV files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, 1):
                    # Check if it contains chat-related data
                    if any(key in row for key in ['chat_id', 'user_id', 'message', 'text', 'timestamp']):
                        self.extracted_data['chat_messages'].append({
                            'source_file': str(file_path),
                            'line_number': row_num,
                            'data': row
                        })
            
            self.processed_files.append(str(file_path))
            logger.info(f"✅ Processed CSV file: {file_path}")
            
        except Exception as e:
            logger.error(f"❌ Error processing CSV file {file_path}: {e}")
    
    def extract_from_log(self, file_path):
        """Extract data from log files"""
        try:
            chat_patterns = [
                r'chat_id[:\s]*(\d+)',
                r'user_id[:\s]*(\d+)',
                r'message[:\s]*"([^"]*)"',
                r'text[:\s]*"([^"]*)"',
                r'Chat ID: (\d+)',
                r'User ID: (\d+)',
                r'Message: ([^\n]*)',
                r'Text: ([^\n]*)'
            ]
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # Look for chat-related patterns
                    for pattern in chat_patterns:
                        matches = re.findall(pattern, line, re.IGNORECASE)
                        if matches:
                            self.extracted_data['chat_messages'].append({
                                'source_file': str(file_path),
                                'line_number': line_num,
                                'raw_line': line.strip(),
                                'matches': matches
                            })
                            break
            
            self.processed_files.append(str(file_path))
            logger.info(f"✅ Processed log file: {file_path}")
            
        except Exception as e:
            logger.error(f"❌ Error processing log file {file_path}: {e}")
    
    def extract_from_html(self, file_path):
        """Extract data from HTML files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for JSON data in HTML
            json_patterns = [
                r'<script[^>]*>([^<]*)</script>',
                r'data-json="([^"]*)"',
                r'window\.chatData\s*=\s*(\{.*?\});',
                r'window\.userData\s*=\s*(\{.*?\});'
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    try:
                        data = json.loads(match)
                        if isinstance(data, dict):
                            if 'messages' in data or 'chat_history' in data:
                                messages = data.get('messages', data.get('chat_history', []))
                                for msg in messages:
                                    self.extracted_data['chat_messages'].append({
                                        'source_file': str(file_path),
                                        'data': msg
                                    })
                    except json.JSONDecodeError:
                        continue
            
            self.processed_files.append(str(file_path))
            logger.info(f"✅ Processed HTML file: {file_path}")
            
        except Exception as e:
            logger.error(f"❌ Error processing HTML file {file_path}: {e}")
    
    def process_directory(self, directory_path):
        """Process all files in a directory"""
        directory = Path(directory_path)
        if not directory.exists():
            logger.warning(f"⚠️ Directory not found: {directory_path}")
            return
        
        logger.info(f"🔍 Scanning directory: {directory_path}")
        
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                try:
                    if file_path.suffix.lower() == '.json':
                        self.extract_from_json(file_path)
                    elif file_path.suffix.lower() == '.jsonl':
                        self.extract_from_jsonl(file_path)
                    elif file_path.suffix.lower() == '.csv':
                        self.extract_from_csv(file_path)
                    elif file_path.suffix.lower() == '.log':
                        self.extract_from_log(file_path)
                    elif file_path.suffix.lower() == '.html':
                        self.extract_from_html(file_path)
                except Exception as e:
                    logger.error(f"❌ Error processing file {file_path}: {e}")
    
    def save_extracted_data(self, output_file):
        """Save extracted data to JSON file"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.extracted_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Saved extracted data to: {output_file}")
            
        except Exception as e:
            logger.error(f"❌ Error saving extracted data: {e}")
    
    def print_summary(self):
        """Print summary of extracted data"""
        print("\n" + "="*60)
        print("📊 EXTRACTION SUMMARY")
        print("="*60)
        
        print(f"📁 Processed files: {len(self.processed_files)}")
        print(f"💬 Chat messages found: {len(self.extracted_data['chat_messages'])}")
        print(f"👤 User profiles found: {len(self.extracted_data['user_profiles'])}")
        print(f"🤖 GPT calls found: {len(self.extracted_data['gpt_calls'])}")
        print(f"❌ Errors found: {len(self.extracted_data['errors'])}")
        
        print("\n📁 Processed files:")
        for file_path in self.processed_files:
            print(f"  - {file_path}")
        
        print("\n" + "="*60)

def main():
    """Main extraction function"""
    print("🚀 Starting comprehensive chat data extraction...")
    
    extractor = ChatDataExtractor()
    
    # Process all relevant directories
    directories_to_process = [
        'data',
        'backups',
        'server_data',
        'logs'
    ]
    
    for directory in directories_to_process:
        extractor.process_directory(directory)
    
    # Save extracted data
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"extracted_chat_data_{timestamp}.json"
    extractor.save_extracted_data(output_file)
    
    # Print summary
    extractor.print_summary()
    
    print(f"\n✅ Extraction complete! Data saved to: {output_file}")
    print("🔍 Check the output file for all extracted data")

if __name__ == "__main__":
    main() 