import glob

for filepath in glob.glob('/media/akaun/Project_1/SEVALOR/backend/tests/*.py'):
    with open(filepath, 'r') as f:
        content = f.read()
    
    if '@pytest_asyncio.fixture' in content and 'import pytest_asyncio' not in content:
        content = 'import pytest_asyncio\n' + content
        with open(filepath, 'w') as f:
            f.write(content)
