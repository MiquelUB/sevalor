"use client";

import React, { useState, useEffect } from "react";
import {
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

export default function GestioClientsPage() {
  const { rolActiu } = useGestio();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtreCerca, setFiltreCerca] = useState("");
  const [clientSeleccionat, setClientSeleccionat] = useState<Client | null>(null);
  const [modalNouClient, setModalNouClient] = useState(false);
  const [guardant, setGuardant] = useState(false);

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
              </div>

              {clientSeleccionat.adreca_fiscal && (
                <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
                  <MapPin className="w-4 h-4 text-slate-400 shrink-0" />
                  <span>{clientSeleccionat.adreca_fiscal}</span>
                </div>
              )}
            </div>
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
    </div>
  );
}
