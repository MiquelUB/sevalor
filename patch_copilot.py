path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/copilot.py"
with open(path, "r") as f:
    text = f.read()

target = """    return {
        "trobat": True,
        "vehicle_id": str(v.id),
        "matricula": v.matricula,
        "marca": v.marca,
        "model": v.model,
        "tipus": v.tipus,
        "estat": v.estat,
        "odometre_acumulat": v.odometre_acumulat,
        "data_proxima_itv": v.data_proxima_itv.isoformat() if v.data_proxima_itv else None
    }"""
replacement = """    return {
        "trobat": True,
        "vehicle_id": str(v.id),
        "matricula": v.matricula,
        "marca": v.marca,
        "model": v.model,
        "tipus": v.tipus,
        "estat": v.estat,
        "odometre_acumulat": v.odometre_acumulat,
        "data_proxima_itv": v.data_proxima_itv.isoformat() if v.data_proxima_itv else None,
        "estat_itv": v.estat_itv,
        "data_caducitat_asseguranca": v.data_caducitat_asseguranca.isoformat() if v.data_caducitat_asseguranca else None,
        "companyia_asseguradora": v.companyia_asseguradora,
        "carnet_necessari": v.carnet_necessari,
        "historial_reparacions": v.historial_reparacions
    }"""

if target in text:
    text = text.replace(target, replacement)
    print("Patched execute_tool_get_vehicle_info")
else:
    print("Could not find execute_tool_get_vehicle_info")

target_resposta = """                resposta = (
                    f"Vehicle {tool_res['matricula']} ({tool_res['marca']} {tool_res['model']}): "
                    f"Estat: {tool_res['estat']}. Data propera ITV: {tool_res.get('data_proxima_itv') or 'Pendent'}. "
                    f"Odòmetre: {tool_res['odometre_acumulat']} km."
                )"""

replacement_resposta = """                resposta = (
                    f"Vehicle {tool_res['matricula']} ({tool_res['marca']} {tool_res['model']}): "
                    f"Estat: {tool_res['estat']}. "
                    f"ITV: {tool_res.get('estat_itv')} (Propera: {tool_res.get('data_proxima_itv') or 'Pendent'}). "
                    f"Assegurança: {tool_res.get('companyia_asseguradora') or 'No consta'} (Caduca: {tool_res.get('data_caducitat_asseguranca') or 'No consta'}). "
                    f"Carnet Requerit: {tool_res.get('carnet_necessari')}. "
                    f"Odòmetre: {tool_res['odometre_acumulat']} km."
                )"""

if target_resposta in text:
    text = text.replace(target_resposta, replacement_resposta)
    print("Patched copilot target_resposta")
else:
    print("Could not find target_resposta")

with open(path, "w") as f:
    f.write(text)
