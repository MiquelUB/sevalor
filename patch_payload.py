path = "pwa/src/app/gestio/flota/page.tsx"
with open(path, "r") as f:
    text = f.read()

target = """          odometre_acumulat: nouOdometre,
          regim_adquisicio: nouRegim,
          renting_limit_km: nouLimitKm,
        }),"""

replacement = """          odometre_acumulat: nouOdometre,
          regim_adquisicio: nouRegim,
          renting_limit_km: nouLimitKm,
          estat_itv: nouEstatItv,
          data_proxima_itv: novaDataItv || null,
          data_caducitat_asseguranca: novaDataAsseguranca || null,
          companyia_asseguradora: novaCompanyiaAsseguranca || null,
          carnet_necessari: nouCarnet
        }),"""

if target in text:
    text = text.replace(target, replacement)
    print("Patched payload")
else:
    print("Target not found")

with open(path, "w") as f:
    f.write(text)
