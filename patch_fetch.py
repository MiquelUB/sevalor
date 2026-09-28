path = "pwa/src/app/gestio/flota/page.tsx"
with open(path, "r") as f:
    text = f.read()

target = """    try {
      const res = await apiFetch("/gestio/flota/vehicles");
      if (res.ok) {
        const data = await res.json();
        setVehicles(data);
      }
    } catch (err) {
      console.error(err);
    }
  };"""

replace = """    try {
      const res = await apiFetch("/gestio/flota");
      if (res.ok) {
        const data = await res.json();
        const mapped = data.map((v: any) => {
          let diesItv = null;
          let alertaItv = "OK";
          if (v.data_proxima_itv) {
             const diff = (new Date(v.data_proxima_itv).getTime() - new Date().getTime()) / (1000 * 3600 * 24);
             diesItv = Math.floor(diff);
             if (diesItv < 0) alertaItv = "CADUCADA";
             else if (diesItv <= 5) alertaItv = "CRITIC";
             else if (diesItv <= 15) alertaItv = "AVIS";
          }
          
          let pct = 0;
          let rAlerta = false;
          let rNiv = "NOMINAL";
          if (v.regim_adquisicio === "RENTING" && v.renting_limit_km > 0) {
             pct = Math.round((v.odometre_acumulat / v.renting_limit_km) * 100);
             if (pct >= 100) { rAlerta = true; rNiv = "EXCEDIT"; }
             else if (pct >= 95) { rAlerta = true; rNiv = "95%"; }
             else if (pct >= 90) { rAlerta = true; rNiv = "90%"; }
          }
          
          return {
             ...v,
             dies_propera_itv: diesItv,
             alerta_itv_cadena: alertaItv,
             renting_ocupacio_percent: pct,
             renting_alerta: rAlerta,
             renting_nivell_alerta: rNiv,
             consum_format: v.tipus === "REMOLC" ? "N/A" : (v.consum_l_100km ? `${v.consum_l_100km} L/100km` : "Pendent dades"),
             anomalia_consum: v.consum_l_100km && v.consum_mitjana_historica && (v.consum_l_100km > v.consum_mitjana_historica * 1.1),
             anomalia_descartada: false, // Temporal frontend state
             conductor_nom: v.conductor_habitual_id ? "Assignat" : "Cap", // TODO
          };
        });
        setVehicles(mapped);
      }
    } catch (err) {
      console.error(err);
    }
  };"""
text = text.replace(target, replace)

# 2. Fix apiFetch POST
target_post = """      const res = await apiFetch("/gestio/flota/vehicles", {"""
replace_post = """      const res = await apiFetch("/gestio/flota", {"""
text = text.replace(target_post, replace_post)

with open(path, "w") as f:
    f.write(text)
print("fetchVehicles patched")
