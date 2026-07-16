import re
import hashlib
import uuid

def calculate_hash(heading: str, body_text: str) -> str:
    content = f"{heading.strip()}|{body_text.strip()}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def parse_document(raw_text: str) -> list[dict]:
    lines = raw_text.splitlines()
    nodes_data = []
    current_node = None
    
    # Matches structure sections like "1. Device Overview" or "2.1.1.1 Battery Life"
    heading_re = re.compile(r'^(\d+(?:\.\d+)*)\.?\s+(.*)$')
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        match = heading_re.match(line_str)
        if match:
            sec_num = match.group(1)
            title = match.group(2)
            
            # Heuristic to filter nested body lists like "1. Normal: systolic < 120"
            is_list_item = False
            if "." not in sec_num:
                num_val = int(sec_num)
                if current_node:
                    current_top = int(current_node['section_number'].split('.')[0])
                    if num_val != current_top + 1:
                        is_list_item = True
            
            if not is_list_item:
                if current_node:
                    nodes_data.append(current_node)
                
                level = len(sec_num.split('.'))
                current_node = {
                    "section_number": sec_num,
                    "heading": title,
                    "level": level,
                    "body_lines": [],
                }
                continue
        
        if current_node:
            current_node["body_lines"].append(line)
            
    if current_node:
        nodes_data.append(current_node)
        
    for node in nodes_data:
        node["body_text"] = "\n".join(node["body_lines"]).strip()
        del node["body_lines"]
        node["content_hash"] = calculate_hash(node["heading"], node["body_text"])
        
    # Resolve hierarchical parent-child associations
    for i, node in enumerate(nodes_data):
        sec_parts = node["section_number"].split('.')
        parent_node = None
        for length in range(len(sec_parts) - 1, 0, -1):
            parent_prefix = ".".join(sec_parts[:length])
            for prev_node in reversed(nodes_data[:i]):
                if prev_node["section_number"] == parent_prefix:
                    parent_node = prev_node
                    break
            if parent_node:
                break
        
        # Build node paths (e.g. "2/2.1/2.1.1.1")
        if parent_node:
            node["parent_section"] = parent_node["section_number"]
            node["path"] = f"{parent_node['path']}/{node['section_number']}"
        else:
            node["parent_section"] = None
            node["path"] = node["section_number"]
            
    return nodes_data
