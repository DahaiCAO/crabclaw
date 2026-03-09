"""Fix loop.py by removing corrupted Unicode characters."""

with open('d:/Coding-New/crabclaw/crabclaw/agent/loop.py', 'rb') as f:
    content = f.read()

# Remove all corrupted Unicode sequences (0xEF 0xBF 0xBD is the replacement character)
# and fix other encoding issues
content = content.replace(b'\xef\xbf\xbd', b'')  # Remove replacement character
content = content.replace(b'\r\n', b'\n')  # Normalize line endings

# Write back
with open('d:/Coding-New/crabclaw/crabclaw/agent/loop.py', 'wb') as f:
    f.write(content)

print('File cleaned')
