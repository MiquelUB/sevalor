import re

with open("pwa/src/app/gestio/clients/page.tsx", "r") as f:
    content = f.read()

# Add Fitxa360 interfaces
interfaces = """
interface FincaFitxa360 { id: string; nom: string; adreca?: string; superficie_ha?: number; }
interface IntervencioFitxa360 { id: string; codi: string; titol: string; estat: string; data_planificacio?: string; }
interface PecaInstaladaFitxa360 { article_id: string; nom_article: string; quantitat_instalada: number; unitat_mesura: string; data_instalacio: string; ordre_treball_codi: string; }
interface IncidenciaFitxa360 { id: string; ambit: string; estat: string; text_observacions?: string; ordre_treball_codi?: string; created_at: string; }
interface Fitxa360Response {
  client: Client;
  finques: FincaFitxa360[];
  intervencions: IntervencioFitxa360[];
  peces_instalades: PecaInstaladaFitxa360[];
  incidencies: IncidenciaFitxa360[];
}
"""
content = content.replace("export default function GestioClientsPage() {", interfaces + "\nexport default function GestioClientsPage() {")

# Add state
states = """
  const [fitxa360, setFitxa360] = useState<Fitxa360Response | null>(null);
  const [loadingFitxa, setLoadingFitxa] = useState(false);
"""
content = content.replace("const [guardant, setGuardant] = useState(false);", "const [guardant, setGuardant] = useState(false);" + states)

# Add fetch effect
effect = """
  useEffect(() => {
    if (clientSeleccionat) {
      setLoadingFitxa(true);
      apiFetch<Fitxa360Response>(`/gestio/clients/${clientSeleccionat.id}/fitxa360`)
        .then(data => setFitxa360(data))
        .catch(err => console.error("Error carregant fitxa360:", err))
        .finally(() => setLoadingFitxa(false));
    } else {
      setFitxa360(null);
    }
  }, [clientSeleccionat]);
"""
content = content.replace("useEffect(() => {\n    carregarClients();\n  }, []);", "useEffect(() => {\n    carregarClients();\n  }, []);\n" + effect)

with open("pwa/src/app/gestio/clients/page.tsx", "w") as f:
    f.write(content)
