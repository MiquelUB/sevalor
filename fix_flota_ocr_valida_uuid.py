path = "backend/app/api/v1/gestio/flota.py"
with open(path, "r") as f:
    text = f.read()

target = """@router.post("/ocr-draft")
async def ocr_vehicle_draft(
    request: Request,
    file: UploadFile = File(...),
    tenant: dict = Depends(valida_uuid)
):"""

replace = """@router.post("/ocr-draft")
async def ocr_vehicle_draft(
    request: Request,
    file: UploadFile = File(...)
):"""

if target in text:
    text = text.replace(target, replace)
    print("Fixed valida_uuid NameError in flota.py")
else:
    print("Target not found. Let's try a regex.")
    import re
    text = re.sub(r'tenant:\s*dict\s*=\s*Depends\(valida_uuid\)', '', text)
    # clean up any trailing commas
    text = re.sub(r',\s*\)', ')', text)

with open(path, "w") as f:
    f.write(text)
