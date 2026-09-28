import re
path = "/media/akaun/Project_1/SEVALOR/backend/app/models/models.py"
with open(path, "r") as f:
    text = f.read()

target = """    companyia_asseguradora: Mapped[Optional[str]] = mapped_column(String(100))"""
replace = """    companyia_asseguradora: Mapped[Optional[str]] = mapped_column(String(100))
    polissa_asseguranca: Mapped[Optional[str]] = mapped_column(String(100))"""
if target in text:
    text = text.replace(target, replace)
    print("Added polissa")
else:
    print("Could not find companyia_asseguradora")

with open(path, "w") as f:
    f.write(text)
