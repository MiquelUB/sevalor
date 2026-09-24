import re
import os

files_to_patch = [
    "backend/app/api/v1/gestio/magatzem.py",
    "backend/app/api/v1/gestio/proveidors.py"
]

for filepath in files_to_patch:
    with open(filepath, "r") as f:
        content = f.read()

    # Pattern 1: .where(Model.empresa_id == empresa_id) or UUID wrap
    content = re.sub(r'\.where\([A-Za-z0-9_]+\.empresa_id == (?:uuid\.UUID\()?empresa_id(?:\))?\)', '', content)
    
    # Pattern 2: Model.empresa_id == empresa_id, (at the beginning of where)
    content = re.sub(r'\([A-Za-z0-9_]+\.empresa_id == (?:uuid\.UUID\()?empresa_id(?:\))?,\s*', '(', content)
    
    # Pattern 3: , Model.empresa_id == empresa_id (at the end of where)
    content = re.sub(r',\s*[A-Za-z0-9_]+\.empresa_id == (?:uuid\.UUID\()?empresa_id(?:\))?', '', content)

    with open(filepath, "w") as f:
        f.write(content)
