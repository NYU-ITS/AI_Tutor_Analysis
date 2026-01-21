import json
import re

def load_questions(file_path: str) -> dict:
    """
    Parse the questions markdown file into a dictionary {q_num: q_text}.
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    questions = {}
    # Regex to find questions starting with "**N.**" or "**N**." where N is a number
    # Adjust regex based on the specific format of hw4_question.md
    # Looking at the file, questions are like "**1.** For what values..." or "**8.** Use the limit..."
    
    # Split by "**N.**" pattern
    # This is a simple heuristic, might need refinement based on exact file structure
    
    # Let's try to find blocks that start with **N.**
    pattern = r'\*\*(\d+)\.\*\*\s+(.*?)(?=\n\n\*\*|\n\n---|\Z)'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        q_num = int(match.group(1))
        q_text = match.group(2).strip()
        questions[q_num] = q_text
        
    return questions

def load_solutions(file_path: str) -> dict:
    """
    Parse the solutions markdown file into a dictionary {q_num: sol_text}.
    """
    with open(file_path, 'r') as f:
        content = f.read()
        
    solutions = {}
    # Solutions seem to be under "### Problem N" headers
    
    pattern = r'### Problem (\d+)\n(.*?)(?=\n### Problem|\n## |\Z)'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        q_num = int(match.group(1))
        sol_text = match.group(2).strip()
        solutions[q_num] = sol_text
        
    return solutions

def load_chat_history(file_path: str) -> str:
    """
    Parse the chat JSON file and reconstruct the conversation as a linear text.
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
        
    # The JSON structure is a list of conversations. We usually care about the first one or iterate all.
    # Based on the file view, it's a list containing one object with "chat" -> "history" -> "messages"
    
    if not data:
        return ""
        
    # Assuming we process the first conversation in the list
    conversation_data = data[0]
    messages_map = conversation_data.get("chat", {}).get("history", {}).get("messages", {})
    
    if not messages_map:
        return ""
        
    # Reconstruct order using parentId/childrenIds
    # Find the root message (parentId is null)
    root_id = None
    for msg_id, msg in messages_map.items():
        if msg.get("parentId") is None:
            root_id = msg_id
            break
            
    if not root_id:
        return ""
        
    ordered_messages = []
    current_id = root_id
    
    while current_id:
        msg = messages_map.get(current_id)
        if not msg:
            break
            
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        ordered_messages.append(f"{role.upper()}: {content}")
        
        # Move to next child
        children = msg.get("childrenIds", [])
        if children:
            current_id = children[0] # Assume linear conversation for now
        else:
            current_id = None
            
    return "\n\n".join(ordered_messages)
