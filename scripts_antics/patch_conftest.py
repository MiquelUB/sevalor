with open("backend/tests/conftest.py", "r") as f:
    content = f.read()

content = content.replace("redis://:sevalor_dev_redis@127.0.0.1:6380/0", "redis://:sevalor_redis_pass@127.0.0.1:6380/0")

with open("backend/tests/conftest.py", "w") as f:
    f.write(content)
