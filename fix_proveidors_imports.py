path = "backend/app/api/v1/gestio/proveidors.py"
with open(path, "r") as f:
    text = f.read()

text = "from fastapi import UploadFile, File\n" + text

with open(path, "w") as f:
    f.write(text)
print("Added imports to proveidors.py")
