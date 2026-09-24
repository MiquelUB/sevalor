import sys

with open("pwa/src/app/gestio/proveidors/page.tsx", "r") as f:
    content = f.read()

# Fix handleCrearProveidor
old_crear = """      const res = await apiFetch("/gestio/proveidors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rao_social: novaRaoSocial,
          nif: nouNif,
          telefon: nouTelefon,
          email: nouEmail,
          especialitat: novaEspecialitat,
          es_recc: nouEsRecc,
          aplica_isp_defecte: nouAplicaIsp,
          iban: nouIban || "ES82 0049 1823 44 2819481920",
        }),
      });

      if (res.ok) {
        setModalAltaObert(false);
        fetchProveidors();
      } else {"""

new_crear = """      await apiFetch("/gestio/proveidors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          codi: `PRV-${Date.now().toString().slice(-4)}`,
          rao_social: novaRaoSocial,
          nif: nouNif,
          telefon: nouTelefon || null,
          email: nouEmail || null,
          especialitat: novaEspecialitat,
          iban: nouIban || "ES8200491823442819481920",
        }),
      });
      setModalAltaObert(false);
      fetchProveidors();
      if (false) {"""

content = content.replace(old_crear, new_crear)


old_canvi = """      const res = await apiFetch("/gestio/proveidors/autoritzar-canvi-iban", {
        method: "POST",
        body: JSON.stringify({ proveidor_id: provSeleccionatBec.id, nou_iban: nouIbanInput })
      });
      if (res.ok) {
        setModalBecObert(false);
        fetchProveidors();
      }"""
new_canvi = """      await apiFetch(`/gestio/proveidors/${provSeleccionatBec.id}/iban`, {
        method: "PUT",
        body: JSON.stringify({ nou_iban: nouIbanInput })
      });
      setModalBecObert(false);
      fetchProveidors();"""
content = content.replace(old_canvi, new_canvi)

old_alt = """      const res = await apiFetch("/gestio/proveidors/subcontractes-alternatives");
      if (res.ok) {
        const data = await res.json();
        setAlternativesSubcontractes(data);
      }"""
new_alt = """      const data = await apiFetch<any[]>("/gestio/proveidors");
      setAlternativesSubcontractes(data || []);"""
content = content.replace(old_alt, new_alt)

with open("pwa/src/app/gestio/proveidors/page.tsx", "w") as f:
    f.write(content)
