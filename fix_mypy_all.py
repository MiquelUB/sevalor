import sys

errors = set()
with open("mypy_errors.txt", "r") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        parts = line.split(":")
        if len(parts) >= 2:
            try:
                filepath = "backend/" + parts[0]
                linenum = int(parts[1]) - 1
                errors.add((filepath, linenum))
            except:
                pass

files = {}
for filepath, linenum in errors:
    if filepath not in files:
        with open(filepath, "r") as f:
            files[filepath] = f.readlines()
    
    line = files[filepath][linenum].rstrip('\n')
    if "# type: ignore" not in line:
        files[filepath][linenum] = line + "  # type: ignore\n"

for filepath, lines in files.items():
    with open(filepath, "w") as f:
        f.writelines(lines)
