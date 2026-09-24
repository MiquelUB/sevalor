import re

files_to_patch = [
    "backend/app/api/v1/gestio/magatzem.py",
    "backend/app/api/v1/gestio/proveidors.py"
]

for filepath in files_to_patch:
    with open(filepath, "r") as f:
        content = f.read()

    # Case 1: single condition in .where() -> .where(Model.empresa_id == empresa_id) -> remove the .where() entirely
    content = re.sub(r'\.where\(\w+\.empresa_id == (?:uuid\.UUID\()?empresa_id(?:\))?\)', '', content)

    # Case 2: first condition in .where(..., ...) -> remove it and the following comma
    content = re.sub(r'\(\w+\.empresa_id == (?:uuid\.UUID\()?empresa_id(?:\))?,\s*', '(', content)

    # Case 3: trailing condition in .where(..., ...) -> remove the preceding comma and it
    content = re.sub(r',\s*\w+\.empresa_id == (?:uuid\.UUID\()?empresa_id(?:\))?', '', content)

    with open(filepath, "w") as f:
        f.write(content)
