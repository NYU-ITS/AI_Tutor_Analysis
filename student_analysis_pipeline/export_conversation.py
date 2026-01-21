#!/usr/bin/env python3
"""
Convert student chat JSON to clean, readable markdown format.
Only keeps essential information - no redundant metadata.
"""

import json
import sys
from pathlib import Path


def extract_conversation_to_markdown(json_path: str, output_path: str):
    """
    Extract conversation data from JSON and save as clean markdown.
    
    Args:
        json_path: Path to the student chat JSON file
        output_path: Path where markdown file will be saved
    """
    
    # Load JSON
    print(f"Loading {json_path}...")
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    if not data or len(data) == 0:
        print("ERROR: No data in JSON file")
        return
    
    print(f"Found {len(data)} conversation(s) in JSON")
    
    # Extract metadata from first conversation
    first_conv = data[0]
    user_id = first_conv.get('user_id', 'unknown')
    title = first_conv.get('title', 'Untitled')
    
    # Merge messages from ALL conversations
    messages = {}
    for i, conversation in enumerate(data):
        conv_messages = conversation.get('chat', {}).get('history', {}).get('messages', {})
        print(f"  Conversation {i+1}: {len(conv_messages)} messages")
        messages.update(conv_messages)
    
    # Get model name from first assistant message
    model_name = None
    for msg in messages.values():
        if msg.get('role') == 'assistant' and msg.get('modelName'):
            model_name = msg.get('modelName')
            break
    
    if not messages:
        print("ERROR: No messages found in JSON")
        return
    
    print(f"Total merged messages: {len(messages)}")
    
    # Convert to list and sort by timestamp
    message_list = []
    for msg_id, msg in messages.items():
        message_list.append({
            'role': msg.get('role', 'unknown'),
            'content': msg.get('content', ''),
            'timestamp': msg.get('timestamp', 0)
        })
    
    # Sort by timestamp
    message_list.sort(key=lambda x: x['timestamp'])
    
    # Count messages by role
    user_count = sum(1 for m in message_list if m['role'] == 'user')
    assistant_count = sum(1 for m in message_list if m['role'] == 'assistant')
    
    print(f"User messages: {user_count}")
    print(f"Assistant messages: {assistant_count}")
    
    # Write to markdown
    print(f"Writing to {output_path}...")
    with open(output_path, 'w') as f:
        # Header
        f.write('# Student Conversation\n\n')
        
        # Metadata
        f.write(f'**Student ID:** {user_id}\n')
        f.write(f'**Title:** {title}\n')
        if model_name:
            f.write(f'**Model:** {model_name}\n')
        f.write(f'**Total Messages:** {len(message_list)} ({user_count} student, {assistant_count} assistant)\n\n')
        f.write('---\n\n')
        
        # Messages - clean format
        for msg in message_list:
            role = msg['role'].upper()
            content = msg['content']
            
            f.write(f'**{role}:** {content}\n\n')
    
    print(f' Successfully created {output_path}')
    print(f' Clean format: {len(message_list)} messages')


if __name__ == '__main__':
    # Default paths
    base_dir = Path(__file__).parent
    json_file = base_dir / '../hw4/student_conversations/ab12167_hw4_chats.json'
    output_file = base_dir / 'ab12167_hw4_conversation.md'
    
    # Allow command line arguments
    if len(sys.argv) > 1:
        json_file = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_file = Path(sys.argv[2])
    
    # Run conversion
    extract_conversation_to_markdown(str(json_file), str(output_file))
