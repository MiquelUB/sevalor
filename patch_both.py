import re

# 1. PWA
path_pwa = "pwa/src/app/gestio/flota/page.tsx"
with open(path_pwa, "r") as f:
    text_pwa = f.read()

target_opt = """          anomalia_descartada: false,
        };"""
replace_opt = """          anomalia_descartada: false,
          estat_itv: nouEstatItv,
          data_caducitat_asseguranca: novaDataAsseguranca || null,
          companyia_asseguradora: novaCompanyiaAsseguranca || null,
          carnet_necessari: nouCarnet,
          historial_reparacions: null
        };"""
text_pwa = text_pwa.replace(target_opt, replace_opt)

with open(path_pwa, "w") as f:
    f.write(text_pwa)

# 2. Backend
path_back = "backend/app/api/v1/gestio/copilot.py"
with open(path_back, "r") as f:
    text_back = f.read()

target_back = """    return {
        "trobat": True,
        "vehicle_id": str(v.id),
        "matricula": v.matricula,
        "marca": v.marca,
        "model": v.model,
        "tipus": v.tipus,
        "estat": v.estat,
        "data_proxima_itv": v.data_proxima_itv.isoformat() if v.data_proxima_itv else None,
        "odometre_acumulat": v.odometre_acumulat
    }"""
replace_back = """    return {
        "trobat": True,
        "vehicle_id": str(v.id),
        "matricula": v.matricula,
        "marca": v.marca,
        "model": v.model,
        "tipus": v.tipus,
        "estat": v.estat,
        "data_proxima_itv": v.data_proxima_itv.isoformat() if v.data_proxima_itv else None,
        "odometre_acumulat": v.odometre_acumulat,
        "estat_itv": v.estat_itv,
        "data_caducitat_asseguranca": v.data_caducitat_asseguranca.isoformat() if v.data_caducitat_asseguranca else None,
        "companyia_asseguradora": v.companyia_asseguradora,
        "carnet_necessari": v.carnet_necessari,
        "historial_reparacions": v.historial_reparacions
    }"""

if target_back in text_back:
    text_back = text_back.replace(target_back, replace_back)
    print("Patched backend")
else:
    print("Could not find backend target")

with open(path_back, "w") as f:
    f.write(text_back)

print("Done")
