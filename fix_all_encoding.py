"""Fix encoding issues in all Python files."""

import os
from pathlib import Path

def fix_file(filepath):
    """Fix encoding issues in a single file."""
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        
        original = content
        
        # Fix common corrupted Unicode sequences
        # e2 80 xx sequences (em-dash, en-dash, etc.)
        content = content.replace(b'\xe2\x80\x3f', b'-')  # corrupted em-dash
        content = content.replace(b'\xe2\x80\x99', b"'")  # right single quote
        content = content.replace(b'\xe2\x80\x98', b"'")  # left single quote
        content = content.replace(b'\xe2\x80\x9c', b'"')  # left double quote
        content = content.replace(b'\xe2\x80\x9d', b'"')  # right double quote
        content = content.replace(b'\xe2\x80\xa6', b'...')  # ellipsis
        content = content.replace(b'\xe2\x80\x93', b'-')  # en-dash
        content = content.replace(b'\xe2\x80\x94', b'--')  # em-dash
        
        # Fix other common issues
        content = content.replace(b'\xef\xbf\xbd', b'')  # replacement character
        content = content.replace(b'\xc2\xa0', b' ')  # non-breaking space
        
        # Normalize line endings
        content = content.replace(b'\r\n', b'\n')
        
        if content != original:
            with open(filepath, 'wb') as f:
                f.write(content)
            print(f'Fixed: {filepath}')
            return True
        return False
    except Exception as e:
        print(f'Error fixing {filepath}: {e}')
        return False

def main():
    base_path = Path('d:/Coding-New/crabclaw/crabclaw')
    fixed_count = 0
    
    for py_file in base_path.rglob('*.py'):
        if fix_file(py_file):
            fixed_count += 1
    
    print(f'\nFixed {fixed_count} files')

if __name__ == '__main__':
    main()
