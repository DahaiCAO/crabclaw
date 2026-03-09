"""Fix loop.py syntax errors."""

import re

with open('d:/Coding-New/crabclaw/crabclaw/agent/loop.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Fix the method definition - remove duplicate docstring
content = re.sub(
    r'def _register_default_tools\(self\) -> None:\s+"""Register the default set of tools."""\s+"""Register the default set of tools."""',
    'def _register_default_tools(self) -> None:\n        """Register the default set of tools."""',
    content
)

# Fix the _strip_think method - remove duplicate lines
content = re.sub(
    r'def _strip_think\(text: str \| None\) -> str \| None:\s+""".*?"""[\s\S]*?return re\.sub\(r".*?", "", text\)\.strip\(\) or None\s+""".*?"""[\s\S]*?return re\.sub\(r".*?", "", text\)\.strip\(\) or None',
    'def _strip_think(text: str | None) -> str | None:\n        """Remove  blocks that some models embed in content."""\n        if not text:\n            return None\n        return re.sub(r"[\s\S]*?", "", text).strip() or None',
    content,
    flags=re.DOTALL
)

with open('d:/Coding-New/crabclaw/crabclaw/agent/loop.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('File fixed successfully')
