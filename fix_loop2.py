"""Fix loop.py Unicode and syntax errors."""

with open('d:/Coding-New/crabclaw/crabclaw/agent/loop.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Find and fix the _strip_think method
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Check if this is the problematic _strip_think method
    if 'def _strip_think' in line and i + 5 < len(lines):
        # Skip the first implementation and its duplicate
        new_lines.append(line)  # def _strip_think
        i += 1
        new_lines.append(lines[i])  # docstring line 1
        i += 1
        new_lines.append(lines[i])  # if not text
        i += 1
        new_lines.append(lines[i])  # return None
        i += 1
        new_lines.append(lines[i])  # return re.sub
        i += 1
        
        # Skip the duplicate lines
        while i < len(lines) and ('blocks that some models' in lines[i] or 'return re.sub' in lines[i]):
            i += 1
        
        # Add the _tool_hint method
        if i < len(lines) and 'def _tool_hint' in lines[i]:
            new_lines.append('\n')
            new_lines.append(lines[i])
            i += 1
    else:
        new_lines.append(line)
        i += 1

with open('d:/Coding-New/crabclaw/crabclaw/agent/loop.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('File fixed successfully')
