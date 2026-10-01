import subprocess
out = subprocess.run(["/media/akaun/Project_1/SEVALOR/backend/.venv/bin/pytest", "tests/test_047_ia_peritatge.py", "-v"], capture_output=True, text=True)
print(out.stdout)
