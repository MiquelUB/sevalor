with open("backend/tests/conftest.py", "r") as f:
    content = f.read()

if "os.environ['REDIS_URL']" not in content:
    content = "import os\nos.environ['REDIS_URL'] = 'redis://:@127.0.0.1:6380/0'\n" + content

with open("backend/tests/conftest.py", "w") as f:
    f.write(content)
