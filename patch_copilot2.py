import re

path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/copilot.py"
with open(path, "r") as f:
    text = f.read()

target1 = """        "companyia_asseguradora": v.companyia_asseguradora,
        "carnet_necessari": v.carnet_necessari,
        "historial_reparacions": v.historial_reparacions
    }"""
replace1 = """        "companyia_asseguradora": v.companyia_asseguradora,
        "carnet_necessari": v.carnet_necessari,
        "historial_reparacions": v.historial_reparacions,
        "regim_adquisicio": v.regim_adquisicio,
        "renting_limit_km": v.renting_limit_km,
        "consum_l_100km": v.consum_l_100km
    }"""
text = text.replace(target1, replace1)

target2 = """                    f"Carnet Requerit: {tool_res.get('carnet_necessari')}. "
                    f"Odòmetre: {tool_res['odometre_acumulat']} km."
                )"""
replace2 = """                    f"Carnet Requerit: {tool_res.get('carnet_necessari')}. "
                    f"Règim: {tool_res.get('regim_adquisicio')} (Límit: {tool_res.get('renting_limit_km') or 'N/A'} km). "
                    f"Consum: {tool_res.get('consum_l_100km') or 'N/A'} L/100km. "
                    f"Odòmetre: {tool_res['odometre_acumulat']} km."
                )"""
text = text.replace(target2, replace2)

with open(path, "w") as f:
    f.write(text)
print("Copilot updated")
