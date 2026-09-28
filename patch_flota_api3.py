import re

path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/flota.py"
with open(path, "r") as f:
    text = f.read()

# Add polissa_asseguranca to VehicleCreate
target_create = """    companyia_asseguradora: Optional[str] = Field(None, max_length=100)"""
replace_create = """    companyia_asseguradora: Optional[str] = Field(None, max_length=100)
    polissa_asseguranca: Optional[str] = Field(None, max_length=100)"""
text = text.replace(target_create, replace_create)

# Add to alta
target_alta = """        companyia_asseguradora=vehicle.companyia_asseguradora,"""
replace_alta = """        companyia_asseguradora=vehicle.companyia_asseguradora,
        polissa_asseguranca=vehicle.polissa_asseguranca,"""
text = text.replace(target_alta, replace_alta)

# Add to put
target_put = """    v_db.companyia_asseguradora = vehicle.companyia_asseguradora"""
replace_put = """    v_db.companyia_asseguradora = vehicle.companyia_asseguradora
    v_db.polissa_asseguranca = vehicle.polissa_asseguranca"""
text = text.replace(target_put, replace_put)

with open(path, "w") as f:
    f.write(text)
print("Updated Vehicle schemas and endpoints")
