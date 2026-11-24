"use client";

import React, { useState, useEffect } from "react";
import { CsvImportModal } from '@/components/ui/CsvImportModal';

import { ClipboardList, Package, Factory,
  Users,
  Search,
  Plus,
  MapPin,
  Lock,
  Send,
  Building,
  CheckCircle2,
  AlertTriangle,
  X,
  Phone,
  Mail,
  RefreshCw,
  Receipt,
} from "lucide-react";
import { apiFetch, getApiBaseUrl, getAuthToken, extractTenantId } from "@/lib/api";
import { geocodificarAdreca } from "@/lib/geocoding";
import { useGestio } from "@/lib/gestio-context";
import { CrearOTModal } from "@/components/gestio/CrearOTModal";
import { FacturaComercialModal } from "@/components/gestio/FacturaComercialModal";

interface Client {
  id: string;
  codi: string;
  rao_social: string;
  nif: string;
  telefon?: string;
  email?: string;
  adreca_fiscal?: string;
  iban?: string;
  estat_canal_telegram?: string;
  actiu?: boolean;
}


interface FincaFitxa360 { id: string; nom: string; adreca?: string; superficie_ha?: number; }
interface IntervencioFitxa360 { id: string; codi: string; titol: string; estat: string; data_planificacio?: string; }
interface PecaInstaladaFitxa360 { article_id: string; nom_article: string; quantitat_instalada: number; unitat_mesura: string; data_instalacio: string; ordre_treball_codi: string; }
interface IncidenciaFitxa360 { id: string; ambit: string; estat: string; text_observacions?: string; ordre_treball_codi?: string; created_at: string; }
interface PressupostFitxa360 { id: string; numero: string; estat: string; total?: number | null; created_at: string; }
interface FacturaClientFitxa360 {
  id: string;
  serie: string;
  numero_factura: number;
  estat_document: string;
  estat_cobrament: string;
  data_emissio?: string | null;
  data_venciment?: string | null;
  base_imposable: number;
  quota_iva: number;
  liquid_exigible: number;
  ordres_treball_codis: string[];
}
interface Fitxa360Response {
  client: Client;
  finques: FincaFitxa360[];
  intervencions: IntervencioFitxa360[];
  peces_instalades: PecaInstaladaFitxa360[];
  incidencies: IncidenciaFitxa360[];
  pressupostos?: PressupostFitxa360[];
  factures?: FacturaClientFitxa360[];
}

export default function GestioClientsPage() {
  const { rolActiu } = useGestio();
  const esEnginyer = (rolActiu || "").toUpperCase() === "ENGINYER";
  const [facturaModalId, setFacturaModalId] = useState<string | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtreCerca, setFiltreCerca] = useState("");
  const [clientSeleccionat, setClientSeleccionat] = useState<Client | null>(null);
  const [modalNouClient, setModalNouClient] = useState(false);
  const [modalEditarClient, setModalEditarClient] = useState(false);
  const [clientEditant, setClientEditant] = useState<Client | null>(null);
  const [modalNovaFinca, setModalNovaFinca] = useState(false);
  const [novaFinca, setNovaFinca] = useState({
    nom: "",
    adreca: "",
    latitud: "",
    longitud: "",
    ref_cadastral: "",
    superficie_ha: "",
  });
  const [guardantFinca, setGuardantFinca] = useState(false);
  const [exportantCsv, setExportantCsv] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  
  // Gestió de Tasques (reutilitzant CrearOTModal unificat)
  const [modalNovaTasca, setModalNovaTasca] = useState(false);
  const [guardant, setGuardant] = useState(false);
  const [fitxa360, setFitxa360] = useState<Fitxa360Response | null>(null);
  const [loadingFitxa, setLoadingFitxa] = useState(false);


  // Formulari nou client (codi generat automàticament al backend: CLI-XXXX)
  const [nouClient, setNouClient] = useState({
    rao_social: "",
    nif: "",
    telefon: "",
    email: "",
    adreca_fiscal: "",
    iban: "",
  });

  const carregarClients = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Client[]>("/gestio/clients");
      setClients(data || []);
      if (data && data.length > 0) {
        setClientSeleccionat((prev) => (prev ? data.find((c) => c.id === prev.id) || data[0] : data[0]));
      } else {
        setClientSeleccionat(null);
      }
    } catch (err: any) {
      setError(err.message || "Error al carregar la llista de clients");
      setClients([]);
      setClientSeleccionat(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarClients();
  }, []);

  useEffect(() => {
    if (clientSeleccionat) {
      setLoadingFitxa(true);
      apiFetch<Fitxa360Response>('/gestio/clients/' + clientSeleccionat.id + '/fitxa360')
        .then(data => setFitxa360(data))
        .catch(err => console.error("Error carregant fitxa360:", err))
        .finally(() => setLoadingFitxa(false));
    } else {
      setFitxa360(null);
    }
  }, [clientSeleccionat]);



  const recarregarFitxa360 = async (clientId: string) => {
    setLoadingFitxa(true);
    try {
      const data = await apiFetch<Fitxa360Response>(`/gestio/clients/${clientId}/fitxa360`);
      setFitxa360(data);
    } catch (err) {
      console.error("Error carregant fitxa360:", err);
    } finally {
      setLoadingFitxa(false);
    }
  };

  const handleExportarCsv = async () => {
    setExportantCsv(true);
    setError(null);
    try {
      const token = getAuthToken();
      const tenantId = extractTenantId();
      const hdrs: Record<string, string> = {};
      if (token) hdrs["Authorization"] = `Bearer ${token}`;
      if (tenantId) hdrs["X-Empresa-ID"] = tenantId;

      const resp = await fetch(`${getApiBaseUrl()}/gestio/clients/export`, {
        credentials: "include",
        headers: hdrs,
      });
      if (!resp.ok) {
        throw new Error(`Error exportant CSV (${resp.status})`);
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "clients_export.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || "Error exportant clients a CSV");
    } finally {
      setExportantCsv(false);
    }
  };

  const handleDesarEdicioClient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientEditant) return;
    setGuardant(true);
    setError(null);
    try {
      const updated = await apiFetch<Client>(`/gestio/clients/${clientEditant.id}`, {
        method: "PUT",
        body: JSON.stringify({
          rao_social: clientEditant.rao_social,
          nif: clientEditant.nif,
          telefon: clientEditant.telefon || null,
          email: clientEditant.email || null,
          adreca_fiscal: clientEditant.adreca_fiscal || null,
          iban: esEnginyer ? null : (clientEditant.iban || null),
        }),
      });
      setModalEditarClient(false);
      setClientEditant(null);
      await carregarClients();
      if (updated) {
        setClientSeleccionat(updated);
        recarregarFitxa360(updated.id);
      }
    } catch (err: any) {
      setError(err.message || "Error en modificar la fitxa del client");
    } finally {
      setGuardant(false);
    }
  };

  const handleCrearFinca = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientSeleccionat) return;
    setGuardantFinca(true);
    setError(null);
    try {
      let lat = parseFloat(novaFinca.latitud);
      let lng = parseFloat(novaFinca.longitud);
      if ((Number.isNaN(lat) || Number.isNaN(lng)) && novaFinca.adreca.trim()) {
        const geo = await geocodificarAdreca(novaFinca.adreca.trim());
        if (geo) {
          lat = geo.lat;
          lng = geo.lng;
        }
      }
      if (Number.isNaN(lat) || Number.isNaN(lng)) {
        setError("Cal indicar latitud i longitud vàlides (o una adreça geocodificable).");
        setGuardantFinca(false);
        return;
      }
      await apiFetch(`/gestio/clients/${clientSeleccionat.id}/finques`, {
        method: "POST",
        body: JSON.stringify({
          nom: novaFinca.nom,
          adreca: novaFinca.adreca || null,
          latitud: lat,
          longitud: lng,
          ref_cadastral: novaFinca.ref_cadastral || null,
          superficie_ha: novaFinca.superficie_ha ? parseFloat(novaFinca.superficie_ha) : null,
        }),
      });
      setModalNovaFinca(false);
      setNovaFinca({
        nom: "",
        adreca: "",
        latitud: "",
        longitud: "",
        ref_cadastral: "",
        superficie_ha: "",
      });
      await recarregarFitxa360(clientSeleccionat.id);
    } catch (err: any) {
      setError(err.message || "Error donant d'alta la finca");
    } finally {
      setGuardantFinca(false);
    }
  };

  const handleCrearClient = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardant(true);
    setError(null);
    try {
      const creat = await apiFetch<Client>("/gestio/clients", {
        method: "POST",
        body: JSON.stringify({
          ...nouClient,
          iban: esEnginyer ? null : (nouClient.iban || null),
        }),
      });
      setModalNouClient(false);
      setNouClient({
        rao_social: "",
        nif: "",
        telefon: "",
        email: "",
        adreca_fiscal: "",
        iban: "",
      });
      await carregarClients();
      if (creat) setClientSeleccionat(creat);
    } catch (err: any) {
      setError(err.message || "Error al crear el client");
    } finally {
      setGuardant(false);
    }
  };

  const clientsFiltrats = clients.filter(
    (c) =>
      c.rao_social.toLowerCase().includes(filtreCerca.toLowerCase()) ||
      c.codi.toLowerCase().includes(filtreCerca.toLowerCase()) ||
      c.nif.toLowerCase().includes(filtreCerca.toLowerCase())
  );

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Barra superior del directori */}
      <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-base font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <Users className="w-5 h-5 text-emerald-600" />
            Directori de Clients (Spec 002)
          </h1>
          <p className="text-xs text-slate-500">
            Dades fiscals, codis d'expedient i canals de comunicació en temps real
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={filtreCerca}
              onChange={(e) => setFiltreCerca(e.target.value)}
              placeholder="Cercar per raó social, CLI o NIF..."
              className="pl-9 pr-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium focus:outline-none focus:border-emerald-600 w-64"
            />
          </div>

          <button
            onClick={carregarClients}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-600 dark:text-slate-300 transition-colors"
            title="Refrescar llista"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>

          
          <button
            onClick={handleExportarCsv}
            disabled={exportantCsv}
            className="px-3 py-1.5 rounded-xl bg-blue-50 text-blue-600 hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400 dark:hover:bg-blue-900/50 text-xs font-bold flex items-center gap-1 shadow-sm transition-all disabled:opacity-50"
            title="Exportar a CSV"
          >
            <span>{exportantCsv ? "Exportant..." : "Exportar CSV"}</span>
          </button>
          
          <button
            onClick={() => setIsImportModalOpen(true)}
            className="px-3 py-1.5 rounded-xl bg-orange-50 text-orange-600 hover:bg-orange-100 dark:bg-orange-900/30 dark:text-orange-400 dark:hover:bg-orange-900/50 text-xs font-bold flex items-center gap-1 shadow-sm transition-all"
            title="Importar des de CSV"
          >
            <span>Importar CSV</span>
          </button>

          <button
            onClick={() => setModalNouClient(true)}
            className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center gap-1 shadow transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Nou Client</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-4 mt-3 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="p-1 hover:text-rose-900">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Cos principal: Columna de Llista + Panell 360º */}
      <div className="flex-1 flex overflow-hidden">
        {/* Llista lateral */}
        <div className="w-80 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-y-auto p-3 space-y-2">
          {loading && clients.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
              <RefreshCw className="w-5 h-5 animate-spin text-emerald-600" />
              <span>Carregant directori de clients...</span>
            </div>
          ) : clients.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs space-y-3">
              <div className="w-10 h-10 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto text-slate-400">
                <Users className="w-5 h-5" />
              </div>
              <p className="font-bold text-slate-700 dark:text-slate-300">
                No hi ha clients registrats
              </p>
              <p className="text-[11px] text-slate-500">
                Estat Dia-0: Registra el primer client fiscal per començar a emetre feines i factures.
              </p>
              <button
                onClick={() => setModalNouClient(true)}
                className="mt-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold"
              >
                + Afegir Client
              </button>
            </div>
          ) : (
            clientsFiltrats.map((c) => (
              <div
                key={c.id}
                onClick={() => setClientSeleccionat(c)}
                className={`p-3 rounded-2xl border transition-all cursor-pointer ${
                  clientSeleccionat?.id === c.id
                    ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-500 shadow-sm"
                    : "bg-slate-50 dark:bg-slate-850 border-slate-200 dark:border-slate-800 hover:border-slate-300"
                }`}
              >
                <div className="flex items-start justify-between">
                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    {c.codi}
                  </span>
                  <span
                    className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${
                      c.estat_canal_telegram === "VINCULAT"
                        ? "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300"
                        : "bg-slate-200 dark:bg-slate-800 text-slate-500"
                    }`}
                  >
                    {c.estat_canal_telegram === "VINCULAT" ? "Telegram OK" : "Sense Bot"}
                  </span>
                </div>
                <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100 mt-1 truncate">
                  {c.rao_social}
                </h4>
                <p className="text-[11px] text-slate-500 mt-0.5 font-mono">NIF: {c.nif}</p>
              </div>
            ))
          )}
        </div>

        {/* Panell 360º de Detalls */}
        {clientSeleccionat ? (
          <div className="flex-1 p-6 overflow-y-auto space-y-6">
            <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300">
                      {clientSeleccionat.codi}
                    </span>
                    <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">
                      {clientSeleccionat.rao_social}
                    </h2>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-slate-500 mt-2">
                    <span className="flex items-center gap-1">
                      <Building className="w-3.5 h-3.5" />
                      NIF: <strong className="font-mono text-slate-700 dark:text-slate-300">{clientSeleccionat.nif}</strong>
                    </span>
                    {clientSeleccionat.email && (
                      <span className="flex items-center gap-1">
                        <Mail className="w-3.5 h-3.5" />
                        {clientSeleccionat.email}
                      </span>
                    )}
                    {clientSeleccionat.telefon && (
                      <span className="flex items-center gap-1">
                        <Phone className="w-3.5 h-3.5" />
                        {clientSeleccionat.telefon}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {!esEnginyer && clientSeleccionat.iban && (
                    <div className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs flex items-center gap-2">
                      <Lock className="w-3.5 h-3.5 text-emerald-600" />
                      <span className="font-mono text-slate-700 dark:text-slate-300">
                        {clientSeleccionat.iban}
                      </span>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => {
                      setClientEditant({ ...clientSeleccionat });
                      setModalEditarClient(true);
                    }}
                    className="px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-50 text-xs font-bold transition-all cursor-pointer"
                  >
                    Editar Fitxa
                  </button>

                  <button
                    type="button"
                    onClick={() => setModalNovaTasca(true)}
                    className="px-4 py-2 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold shadow-sm flex items-center gap-2 transition-all cursor-pointer"
                  >
                    <ClipboardList className="w-4 h-4" />
                    Nova OT / Pressupost
                  </button>
                </div>
              </div>

              {clientSeleccionat.adreca_fiscal && (
                <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
                  <MapPin className="w-4 h-4 text-slate-400 shrink-0" />
                  <span>{clientSeleccionat.adreca_fiscal}</span>
                </div>
              )}
            </div>

            {/* SEVALOR DIGITAL TWIN UI (Fitxa 360) */}
            {loadingFitxa ? (
              <div className="flex justify-center p-8">
                <RefreshCw className="w-6 h-6 text-emerald-500 animate-spin" />
              </div>
            ) : fitxa360 ? (
              <div className="space-y-6">
                
                {/* 1. INSTAL·LACIONS / FINQUES */}
                <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                      <MapPin className="w-4 h-4 text-primary" />
                      Instal·lacions (Finques)
                    </h3>
                    <button
                      type="button"
                      onClick={() => setModalNovaFinca(true)}
                      className="px-3 py-1.5 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary text-xs font-bold flex items-center gap-1 transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Nova Finca</span>
                    </button>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                    {fitxa360.finques.length === 0 ? (
                      <p className="text-xs text-slate-400">Cap instal·lació registrada.</p>
                    ) : (
                      fitxa360.finques.map(f => (
                        <div key={f.id} className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
                          <p className="text-xs font-bold text-slate-700 dark:text-slate-200">{f.nom}</p>
                          {f.adreca && <p className="text-[11px] text-slate-500 mt-1">{f.adreca}</p>}
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* 2. ACTIUS I PECES INSTAL·LADES (Historico Materiales) */}
                <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                  <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2 mb-4">
                    <Package className="w-4 h-4 text-emerald-600" />
                    Actius & Peces Instal·lades (Últims 365 dies)
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 dark:bg-slate-800 text-slate-500">
                        <tr>
                          <th className="px-3 py-2 rounded-l-lg font-medium">Actiu / Material</th>
                          <th className="px-3 py-2 font-medium">Quantitat</th>
                          <th className="px-3 py-2 font-medium">OT Associada</th>
                          <th className="px-3 py-2 rounded-r-lg font-medium">Data Instal·lació</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {fitxa360.peces_instalades.length === 0 ? (
                          <tr><td colSpan={4} className="px-3 py-4 text-center text-slate-400">Sense històric d'actius instal·lats</td></tr>
                        ) : (
                          fitxa360.peces_instalades.map((p, i) => (
                            <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                              <td className="px-3 py-2 font-medium text-slate-700 dark:text-slate-300">{p.nom_article}</td>
                              <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{p.quantitat_instalada} {p.unitat_mesura}</td>
                              <td className="px-3 py-2"><span className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 rounded font-mono text-[10px] text-slate-600 dark:text-slate-400">{p.ordre_treball_codi}</span></td>
                              <td className="px-3 py-2 text-slate-500">{new Date(p.data_instalacio).toLocaleDateString()}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* 3. HISTÒRIC D'INTERVENCIONS I INCIDÈNCIES */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Treballs */}
                  <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2 mb-4">
                      <Factory className="w-4 h-4 text-emerald-600" />
                      Històric Intervencions (OTs)
                    </h3>
                    <div className="space-y-2">
                      {fitxa360.intervencions.length === 0 ? (
                        <p className="text-xs text-slate-400">Sense intervencions recents.</p>
                      ) : (
                        fitxa360.intervencions.slice(0,5).map(ot => (
                          <a key={ot.id} href={`/gestio/feines?id=${ot.id}`} className="block p-3 rounded-xl border border-slate-100 dark:border-slate-800 hover:border-emerald-200 dark:hover:border-emerald-800 hover:bg-emerald-50/50 dark:hover:bg-emerald-900/10 transition-colors">
                            <div className="flex justify-between items-start mb-1">
                              <span className="font-mono text-[10px] font-bold text-slate-500">{ot.codi}</span>
                              <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 rounded">{ot.estat}</span>
                            </div>
                            <p className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">{ot.titol}</p>
                            {ot.data_planificacio && <p className="text-[10px] text-slate-500 mt-1">Planificat: {new Date(ot.data_planificacio).toLocaleDateString()}</p>}
                          </a>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Incidencies */}
                  <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2 mb-4">
                      <AlertTriangle className="w-4 h-4 text-amber-500" />
                      Incidències i Avaries
                    </h3>
                    <div className="space-y-2">
                      {fitxa360.incidencies.length === 0 ? (
                        <p className="text-xs text-slate-400">El client no té incidències.</p>
                      ) : (
                        fitxa360.incidencies.slice(0,5).map(inc => (
                          <div key={inc.id} className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
                            <div className="flex justify-between items-start mb-1">
                              <span className="font-mono text-[10px] font-bold text-amber-600 dark:text-amber-400">{inc.ambit}</span>
                              <span className="text-[10px] px-1.5 py-0.5 bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700">{inc.estat}</span>
                            </div>
                            <p className="text-xs text-slate-700 dark:text-slate-300 mt-1 line-clamp-2">{inc.text_observacions || "Sense observacions"}</p>
                            {inc.ordre_treball_codi && <p className="text-[10px] text-slate-500 mt-2">OT: {inc.ordre_treball_codi}</p>}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>

                {/* 4. PRESSUPOSTOS DEL CLIENT */}
                <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                      <Send className="w-4 h-4 text-primary" />
                      Pressupostos del Client
                    </h3>
                    <a
                      href={`/gestio/pressupostos?client_id=${clientSeleccionat.id}`}
                      className="px-3 py-1.5 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary text-xs font-bold transition-colors"
                    >
                      Gestionar / Enviar Pressupostos
                    </a>
                  </div>
                  {!fitxa360.pressupostos || fitxa360.pressupostos.length === 0 ? (
                    <p className="text-xs text-slate-400">Cap pressupost registrat per a aquest client.</p>
                  ) : (
                    <div className="space-y-2">
                      {fitxa360.pressupostos.map((p) => (
                        <div
                          key={p.id}
                          className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex items-center justify-between gap-3"
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold text-primary">
                                {p.numero}
                              </span>
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 font-semibold">
                                {p.estat}
                              </span>
                            </div>
                            <p className="text-[10px] text-slate-500 mt-0.5">
                              {new Date(p.created_at).toLocaleDateString()}
                            </p>
                          </div>
                          <div className="flex items-center gap-3">
                            {p.total != null && (
                              <span className="font-mono text-xs font-bold text-slate-800 dark:text-slate-200">
                                {Number(p.total).toFixed(2)} €
                              </span>
                            )}
                            <a
                              href={`/gestio/pressupostos?id=${p.id}&enviar=1`}
                              className="px-2.5 py-1 rounded-lg bg-primary text-white text-[11px] font-bold hover:opacity-90"
                            >
                              Enviar / Veure
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* 5. PRE-FACTURES I FACTURES DE TASQUES DEL CLIENT (Tots 3 rols per reclamacions) */}
                <div
                  data-testid="fitxa360-factures-client"
                  className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm"
                >
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                      <Receipt className="w-4 h-4 text-primary" />
                      Pre-factures i Factures de Tasques del Client
                    </h3>
                    <span className="text-[11px] font-mono text-slate-500">
                      {fitxa360.factures?.length || 0} documents
                    </span>
                  </div>
                  {!fitxa360.factures || fitxa360.factures.length === 0 ? (
                    <p className="text-xs text-slate-400">
                      Cap pre-factura ni factura associada a les tasques d&apos;aquest client.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {fitxa360.factures.map((fac) => {
                        const esPref = fac.estat_document === "ESBORRANY_PREFACTURA";
                        return (
                          <div
                            key={fac.id}
                            className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex flex-wrap items-center justify-between gap-3"
                          >
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-mono text-xs font-bold text-primary">
                                  {fac.serie}-{String(fac.numero_factura).padStart(4, "0")}
                                </span>
                                <span
                                  className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                                    esPref
                                      ? "bg-amber-50 text-amber-900 border-amber-300"
                                      : "bg-emerald-50 text-emerald-800 border-emerald-300"
                                  }`}
                                >
                                  {esPref ? "PRE-FACTURA" : fac.estat_document}
                                </span>
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300">
                                  {fac.estat_cobrament}
                                </span>
                              </div>
                              <p className="text-[10px] text-slate-500 mt-1 font-mono">
                                {fac.data_emissio
                                  ? new Date(fac.data_emissio).toLocaleDateString("ca-ES")
                                  : "—"}
                                {fac.ordres_treball_codis?.length > 0
                                  ? ` · OTs: ${fac.ordres_treball_codis.join(", ")}`
                                  : ""}
                              </p>
                            </div>
                            <div className="flex items-center gap-3">
                              <div className="text-right">
                                <span className="font-mono text-xs font-extrabold text-slate-900 dark:text-white block">
                                  {Number(fac.liquid_exigible || 0).toFixed(2)} €
                                </span>
                                <span className="text-[10px] font-mono text-slate-500">
                                  Base {Number(fac.base_imposable || 0).toFixed(2)} € + IVA{" "}
                                  {Number(fac.quota_iva || 0).toFixed(2)} €
                                </span>
                              </div>
                              <button
                                type="button"
                                onClick={() => setFacturaModalId(fac.id)}
                                className="px-2.5 py-1.5 rounded-lg bg-primary text-white text-[11px] font-bold hover:opacity-90 cursor-pointer"
                              >
                                Veure Detall / PDF
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

              </div>
            ) : (
              <div className="p-8 text-center text-slate-400 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
                <Package className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                <p className="text-xs font-bold text-slate-600 dark:text-slate-400">Sense dades de la Fitxa 360°</p>
                <p className="text-[11px] text-slate-400 mt-1">No s'han trobat finques o intervencions recents per a aquest client.</p>
              </div>
            )}

          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
            <Users className="w-12 h-12 stroke-[1.5] text-slate-300 dark:text-slate-700 mb-3" />
            <p className="font-medium text-sm text-slate-600 dark:text-slate-400">
              Selecciona un client de la llista lateral
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Visualitza dades fiscals, finques i estat de comunicacions en temps real
            </p>
          </div>
        )}
      </div>

      
      <FacturaComercialModal
        facturaId={facturaModalId}
        onClose={() => setFacturaModalId(null)}
      />

      <CsvImportModal 
        isOpen={isImportModalOpen} 
        onClose={() => setIsImportModalOpen(false)} 
        resourceName="Clients"
        endpoint="/gestio/clients/import"
        onSuccess={() => {
          carregarClients();
        }}
      />

      {/* Modal Alta Nou Client */}
      {modalNouClient && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Plus className="w-4 h-4 text-emerald-600" />
                Alta de Client Fiscal (Spec 002)
              </h3>
              <button
                onClick={() => setModalNouClient(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearClient} className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Codi Client
                  </label>
                  <div className="w-full px-3 py-2 rounded-xl border border-dashed border-emerald-300 dark:border-emerald-800 bg-emerald-50/70 dark:bg-emerald-950/30 text-xs font-mono text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
                    <Lock className="w-3.5 h-3.5 shrink-0" />
                    <span>Automàtic (CLI-XXXX)</span>
                  </div>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    NIF / CIF *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="B12345678"
                    value={nouClient.nif}
                    onChange={(e) => setNouClient({ ...nouClient, nif: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Raó Social *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Aigües del Territori S.L."
                  value={nouClient.rao_social}
                  onChange={(e) => setNouClient({ ...nouClient, rao_social: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Telèfon
                  </label>
                  <input
                    type="tel"
                    placeholder="+34 600 000 000"
                    value={nouClient.telefon}
                    onChange={(e) => setNouClient({ ...nouClient, telefon: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Correu Electrònic
                  </label>
                  <input
                    type="email"
                    placeholder="facturacio@empresa.com"
                    value={nouClient.email}
                    onChange={(e) => setNouClient({ ...nouClient, email: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Adreça Fiscal
                </label>
                <input
                  type="text"
                  placeholder="Carrer Major, 12, 08001 Barcelona"
                  value={nouClient.adreca_fiscal}
                  onChange={(e) => setNouClient({ ...nouClient, adreca_fiscal: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                />
              </div>

              {!esEnginyer && (
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    IBAN Bancari (opcional, xifrat al backend)
                  </label>
                  <input
                    type="text"
                    placeholder="ES00 0000 0000 0000 0000 0000"
                    value={nouClient.iban}
                    onChange={(e) => setNouClient({ ...nouClient, iban: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
              )}

              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNouClient(false)}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardant}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow disabled:opacity-50"
                >
                  {guardant ? "Desant..." : "Desar Client"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Unificat Nova OT (CrearOTModal preomplert amb client_id) */}
      {modalNovaTasca && clientSeleccionat && (
        <CrearOTModal
          initialClientId={clientSeleccionat.id}
          onClose={() => setModalNovaTasca(false)}
          onSuccess={() => {
            setModalNovaTasca(false);
            recarregarFitxa360(clientSeleccionat.id);
          }}
        />
      )}

      {/* Modal Editar Client */}
      {modalEditarClient && clientEditant && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100">
                Editar Fitxa Client: {clientEditant.rao_social}
              </h3>
              <button
                type="button"
                onClick={() => {
                  setModalEditarClient(false);
                  setClientEditant(null);
                }}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleDesarEdicioClient} className="p-5 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Codi (Automàtic)
                  </label>
                  <input
                    type="text"
                    readOnly
                    value={clientEditant.codi}
                    title="Numeració automàtica assignada pel sistema"
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 text-xs font-mono cursor-not-allowed"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">NIF / CIF *</label>
                  <input
                    type="text"
                    required
                    value={clientEditant.nif}
                    onChange={(e) => setClientEditant({ ...clientEditant, nif: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Raó Social *</label>
                <input
                  type="text"
                  required
                  value={clientEditant.rao_social}
                  onChange={(e) => setClientEditant({ ...clientEditant, rao_social: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Telèfon</label>
                  <input
                    type="tel"
                    value={clientEditant.telefon || ""}
                    onChange={(e) => setClientEditant({ ...clientEditant, telefon: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Correu</label>
                  <input
                    type="email"
                    value={clientEditant.email || ""}
                    onChange={(e) => setClientEditant({ ...clientEditant, email: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                  />
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Adreça Fiscal</label>
                <input
                  type="text"
                  value={clientEditant.adreca_fiscal || ""}
                  onChange={(e) => setClientEditant({ ...clientEditant, adreca_fiscal: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                />
              </div>
              {!esEnginyer && (
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">IBAN Bancari</label>
                  <input
                    type="text"
                    value={clientEditant.iban || ""}
                    onChange={(e) => setClientEditant({ ...clientEditant, iban: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
              )}
              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setModalEditarClient(false);
                    setClientEditant(null);
                  }}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardant}
                  className="px-4 py-2 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold disabled:opacity-50"
                >
                  {guardant ? "Desant..." : "Desar Canvis"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Alta Nova Finca */}
      {modalNovaFinca && clientSeleccionat && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-primary" />
                Nova Finca per a {clientSeleccionat.rao_social}
              </h3>
              <button
                type="button"
                onClick={() => setModalNovaFinca(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCrearFinca} className="p-5 space-y-3">
              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Nom de la Finca *</label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Finca Les Garrigues Nord"
                  value={novaFinca.nom}
                  onChange={(e) => setNovaFinca({ ...novaFinca, nom: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Adreça / Partida (per geocodificar)</label>
                <input
                  type="text"
                  placeholder="Camí Rural s/n, Municipi"
                  value={novaFinca.adreca}
                  onChange={(e) => setNovaFinca({ ...novaFinca, adreca: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Latitud</label>
                  <input
                    type="number"
                    step="any"
                    placeholder="Auto via adreça"
                    value={novaFinca.latitud}
                    onChange={(e) => setNovaFinca({ ...novaFinca, latitud: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Longitud</label>
                  <input
                    type="number"
                    step="any"
                    placeholder="Auto via adreça"
                    value={novaFinca.longitud}
                    onChange={(e) => setNovaFinca({ ...novaFinca, longitud: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Ref. Cadastral</label>
                  <input
                    type="text"
                    value={novaFinca.ref_cadastral}
                    onChange={(e) => setNovaFinca({ ...novaFinca, ref_cadastral: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Superfície (ha)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={novaFinca.superficie_ha}
                    onChange={(e) => setNovaFinca({ ...novaFinca, superficie_ha: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
              </div>
              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNovaFinca(false)}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardantFinca}
                  className="px-4 py-2 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold disabled:opacity-50"
                >
                  {guardantFinca ? "Desant..." : "Registrar Finca"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
