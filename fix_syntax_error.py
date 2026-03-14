#!/usr/bin/env python3
"""Fix the syntax error in commands.py"""

import re

file_path = r"d:\Coding-New\crabclaw\crabclaw\cli\commands.py"

# Read the file
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the syntax error
content = content.replace("s.bind(('127.0.0.1', port))", "s.bind(('127.0.0.1', port))")

# Write the file back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed the syntax error in commands.py")
