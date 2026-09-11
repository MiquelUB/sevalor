import os
import glob

for filepath in glob.glob('/media/akaun/Project_1/SEVALOR/backend/tests/*.py'):
    with open(filepath, 'r') as f:
        content = f.read()
    
    content = content.replace('@pytest.fixture\nasync def', '@pytest_asyncio.fixture\nasync def')
    
    with open(filepath, 'w') as f:
        f.write(content)
