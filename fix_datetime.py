import os
import re

files_to_check = []
for root, dirs, files in os.walk('backend'):
    for f in files:
        if f.endswith('.py'):
            files_to_check.append(os.path.join(root, f))
for root, dirs, files in os.walk('bot'):
    for f in files:
        if f.endswith('.py'):
            files_to_check.append(os.path.join(root, f))

for filepath in files_to_check:
    with open(filepath, 'r') as f:
        content = f.read()
    
    if 'datetime.utcnow' in content:
        # replace datetime.utcnow() with datetime.now(timezone.utc)
        content = content.replace('datetime.utcnow', 'datetime.now(timezone.utc)')
        
        # ensure timezone is imported
        if 'from datetime import' in content and 'timezone' not in content:
            content = re.sub(r'from datetime import (.*?)\n', r'from datetime import \1, timezone\n', content, count=1)
        
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Fixed {filepath}")
