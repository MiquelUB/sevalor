"use client";

import React, { useState, useEffect } from "react";
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
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useGestio } from "@/lib/gestio-context";

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
interface Fitxa360Response {
  client: Client;
  finques: FincaFitxa360[];
  intervencions: IntervencioFitxa360[];
  peces_instalades: PecaInstaladaFitxa360[];
  incidencies: IncidenciaFitxa360[];
}

export default function GestioClientsPage() {
  const { rolActiu } = useGestio();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtreCerca, setFiltreCerca] = useState("");
  const [clientSeleccionat, setClientSeleccionat] = useState<Client | null>(null);
  const [modalNouClient, setModalNouClient] = useState(false);
  
  // Gestió de Tasques
  const [modalNovaTasca, setModalNovaTasca] = useState(false);
  const [guardantTasca, setGuardantTasca] = useState(false);
  const [operaris, setOperaris] = useState<any[]>([]);
  const [vehicles, setVehicles] = useState<any[]>([]);
  const [novaTasca, setNovaTasca] = useState({
    codi: `OT-${Math.floor(Math.random() * 10000)}`,
    titol: "",
    adreca: "",
    data_planificacio: new Date().toISOString().split('T')[0],
    descripcio: "",
    cap_de_colla_id: "",
    vehicle_id: "",
    finca_id: ""
  });
  const [guardant, setGuardant] = useState(false);
  const [fitxa360, setFitxa360] = useState<Fitxa360Response | null>(null);
  const [loadingFitxa, setLoadingFitxa] = useState(false);


  // Formulari nou client
  const [nouClient, setNouClient] = useState({
    codi: "",
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



  const handleObrirModalTasca = () => {
    setModalNovaTasca(true);
    setNovaTasca({
      ...novaTasca,
      codi: `OT-${Math.floor(Math.random() * 10000)}`
    });
    // Fetch operaris and vehicles if not loaded
    if (operaris.length === 0) {
      apiFetch("/gestio/operaris").then((data: any) => setOperaris(data)).catch(() => {});
    }
    if (vehicles.length === 0) {
      apiFetch("/gestio/flota").then((data: any) => setVehicles(data)).catch(() => {});
    }
  };

  const handleCrearTasca = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientSeleccionat || !novaTasca.cap_de_colla_id) return;
    setGuardantTasca(true);
    try {
      const payload = {
        ...novaTasca,
        client_id: clientSeleccionat.id,
        vehicle_id: novaTasca.vehicle_id || null,
        finca_id: novaTasca.finca_id || null
      };
      await apiFetch("/gestio/feines", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });
      setModalNovaTasca(false);
      // Reload Fitxa 360 to see the new tasca
      setLoadingFitxa(true);
      apiFetch<Fitxa360Response>('/gestio/clients/' + clientSeleccionat.id + '/fitxa360')
        .then(data => setFitxa360(data))
        .catch(err => console.error("Error carregant fitxa360:", err))
        .finally(() => setLoadingFitxa(false));
    } catch (err: any) {
      alert("Error al crear la tasca: " + (err.message || ""));
    } finally {
      setGuardantTasca(false);
    }
  };

  const handleCrearClient = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardant(true);
    setError(null);
    try {
      const creat = await apiFetch<Client>("/gestio/clients", {
        method: "POST",
        body: JSON.stringify(nouClient),
      });
      setModalNouClient(false);
      setNouClient({
        codi: "",
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

                {clientSeleccionat.iban && (
                  <div className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs flex items-center gap-2">
                    <Lock className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="font-mono text-slate-700 dark:text-slate-300">
                      {clientSeleccionat.iban}
                    </span>
                  </div>
                )}
                
                <button
                  onClick={handleObrirModalTasca}
                  className="mt-2 ml-4 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-sm flex items-center gap-2 transition-all cursor-pointer"
                >
                  <ClipboardList className="w-4 h-4" />
                  Assignar Tasca
                </button>
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
                  <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2 mb-4">
                    <MapPin className="w-4 h-4 text-emerald-600" />
                    Instal·lacions (Finques)
                  </h3>
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
                          <a key={ot.id} href={'/gestio/feines?c=' + ot.codi} className="block p-3 rounded-xl border border-slate-100 dark:border-slate-800 hover:border-emerald-200 dark:hover:border-emerald-800 hover:bg-emerald-50/50 dark:hover:bg-emerald-900/10 transition-colors">
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

              </div>
            ) : null}

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
                    Codi Client *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="CLI-0001"
                    value={nouClient.codi}
                    onChange={(e) => setNouClient({ ...nouClient, codi: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
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

      {/* Modal Crear Tasca */}
      {modalNovaTasca && clientSeleccionat && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <ClipboardList className="w-4 h-4 text-blue-600" />
                Assignar Tasca a {clientSeleccionat.rao_social}
              </h3>
              <button
                onClick={() => setModalNovaTasca(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearTasca} className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Codi Tasca *
                  </label>
                  <input
                    type="text"
                    required
                    value={novaTasca.codi}
                    onChange={(e) => setNovaTasca({ ...novaTasca, codi: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Data Planificació *
                  </label>
                  <input
                    type="date"
                    required
                    value={novaTasca.data_planificacio}
                    onChange={(e) => setNovaTasca({ ...novaTasca, data_planificacio: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Títol de la Feina *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Reparació fuita principal"
                  value={novaTasca.titol}
                  onChange={(e) => setNovaTasca({ ...novaTasca, titol: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Adreça de l'Obra *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Carrer de l'Obra, 123"
                  value={novaTasca.adreca}
                  onChange={(e) => setNovaTasca({ ...novaTasca, adreca: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                />
              </div>
              
              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Finca (Opcional)
                </label>
                <select
                  value={novaTasca.finca_id}
                  onChange={(e) => setNovaTasca({ ...novaTasca, finca_id: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                >
                  <option value="">-- Sense Finca Específica --</option>
                  {fitxa360?.finques.map(f => (
                    <option key={f.id} value={f.id}>{f.nom} ({f.adreca})</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Cap de Colla *
                  </label>
                  <select
                    required
                    value={novaTasca.cap_de_colla_id}
                    onChange={(e) => setNovaTasca({ ...novaTasca, cap_de_colla_id: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                  >
                    <option value="">-- Seleccionar --</option>
                    {operaris.map(op => (
                      <option key={op.id} value={op.id}>{op.nom} {op.cognoms}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Vehicle (Opcional)
                  </label>
                  <select
                    value={novaTasca.vehicle_id}
                    onChange={(e) => setNovaTasca({ ...novaTasca, vehicle_id: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                  >
                    <option value="">-- Seleccionar --</option>
                    {vehicles.map(v => (
                      <option key={v.id} value={v.id}>{v.matricula} ({v.marca})</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Descripció (Opcional)
                </label>
                <textarea
                  placeholder="Instruccions per a l'operari..."
                  value={novaTasca.descripcio}
                  onChange={(e) => setNovaTasca({ ...novaTasca, descripcio: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs min-h-[60px]"
                />
              </div>

              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNovaTasca(false)}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardantTasca}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow disabled:opacity-50 flex items-center gap-2"
                >
                  <ClipboardList className="w-4 h-4" />
                  {guardantTasca ? "Creant Tasca..." : "Crear i Assignar Tasca"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
