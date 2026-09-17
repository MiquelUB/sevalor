"use client";

import React, { useState, useEffect } from "react";
import {
  Bell,
  Search,
  Send,
  MessageSquare,
  AlertTriangle,
  CheckCircle2,
  Clock,
  User,
  Plus,
  RefreshCw,
  X,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch } from "@/lib/api";

interface Missatge {
  id: string;
  conversa_id: string;
  remitent: string;
  canal: string;
  contingut_text: string;
  tipus_esdeveniment?: string;
  created_at?: string;
}

interface Conversa {
  id: string;
  client_id: string;
  titol: string;
  estat: string;
  es_arxivada: boolean;
  ordre_treball_id?: string;
}

interface ClientOption {
  id: string;
  rao_social: string;
  codi: string;
}

export default function GestioNotificacionsPage() {
  const { rolActiu } = useGestio();
  const [converses, setConverses] = useState<Conversa[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conversaActiva, setConversaActiva] = useState<Conversa | null>(null);
  const [missatges, setMissatges] = useState<Missatge[]>([]);
  const [loadingMissatges, setLoadingMissatges] = useState(false);
  const [nouText, setNouText] = useState("");
  const [enviant, setEnviant] = useState(false);

  // Modal nova conversa
  const [modalNova, setModalNova] = useState(false);
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [selectedClientId, setSelectedClientId] = useState("");
  const [nouTitol, setNouTitol] = useState("");

  const carregarConverses = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Conversa[]>("/gestio/notificacions/converses");
      setConverses(data || []);
      if (data && data.length > 0) {
        const sel = data[0];
        setConversaActiva(sel);
        carregarMissatges(sel.id);
      } else {
        setConversaActiva(null);
        setMissatges([]);
      }
    } catch (err: any) {
      setError(err.message || "Error al carregar les converses");
      setConverses([]);
    } finally {
      setLoading(false);
    }
  };

  const carregarMissatges = async (conversaId: string) => {
    setLoadingMissatges(true);
    try {
      const data = await apiFetch<Missatge[]>(`/gestio/notificacions/converses/${conversaId}/missatges`);
      setMissatges(data || []);
    } catch {
      setMissatges([]);
    } finally {
      setLoadingMissatges(false);
    }
  };

  useEffect(() => {
    carregarConverses();
  }, []);

  const handleSeleccionarConversa = (conv: Conversa) => {
    setConversaActiva(conv);
    carregarMissatges(conv.id);
  };

  const handleEnviarMissatge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!conversaActiva || !nouText.trim()) return;
    setEnviant(true);
    try {
      await apiFetch<Missatge>(`/gestio/notificacions/converses/${conversaActiva.id}/missatges`, {
        method: "POST",
        body: JSON.stringify({
          remitent: "OFICINA",
          canal: "WEB_PWA",
          contingut_text: nouText.trim(),
        }),
      });
      setNouText("");
      await carregarMissatges(conversaActiva.id);
    } catch (err: any) {
      setError(err.message || "Error al enviar el missatge");
    } finally {
      setEnviant(false);
    }
  };

  const obrirModalNova = async () => {
    setModalNova(true);
    try {
      const cls = await apiFetch<ClientOption[]>("/gestio/clients");
      setClients(cls || []);
      if (cls && cls.length > 0) setSelectedClientId(cls[0].id);
    } catch {
      setClients([]);
    }
  };

  const handleCrearConversa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClientId || !nouTitol.trim()) return;
    try {
      const nova = await apiFetch<Conversa>("/gestio/notificacions/converses", {
        method: "POST",
        body: JSON.stringify({
          client_id: selectedClientId,
          titol: nouTitol.trim(),
        }),
      });
      setModalNova(false);
      setNouTitol("");
      await carregarConverses();
      if (nova) {
        setConversaActiva(nova);
        carregarMissatges(nova.id);
      }
    } catch (err: any) {
      setError(err.message || "Error al crear la conversa");
    }
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Barra superior de Notificacions */}
      <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-base font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <Bell className="w-5 h-5 text-emerald-600" />
            Notificacions & Xat de Clients (Spec 009)
          </h1>
          <p className="text-xs text-slate-500">
            Canal omnicanal Telegram / SMS / PWA amb notificacions automàtiques
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={carregarConverses}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-600 dark:text-slate-300 transition-colors"
            title="Refrescar dades"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>

          <button
            onClick={obrirModalNova}
            className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center gap-1 shadow transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Nova Conversa</span>
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

      {/* Cos principal: Llista de Converses + Finestra de Xat */}
      <div className="flex-1 flex overflow-hidden">
        {/* Llista lateral */}
        <div className="w-80 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-y-auto p-3 space-y-2">
          {loading && converses.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
              <RefreshCw className="w-5 h-5 animate-spin text-emerald-600" />
              <span>Carregant converses...</span>
            </div>
          ) : converses.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs space-y-3">
              <div className="w-10 h-10 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto text-slate-400">
                <MessageSquare className="w-5 h-5" />
              </div>
              <p className="font-bold text-slate-700 dark:text-slate-300">
                No hi ha converses obertes
              </p>
              <p className="text-[11px] text-slate-500">
                Estat Dia-0: Obre una conversa associada a un client per començar a comunicar-te.
              </p>
              <button
                onClick={obrirModalNova}
                className="mt-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold"
              >
                + Nova Conversa
              </button>
            </div>
          ) : (
            converses.map((c) => (
              <div
                key={c.id}
                onClick={() => handleSeleccionarConversa(c)}
                className={`p-3 rounded-2xl border transition-all cursor-pointer ${
                  conversaActiva?.id === c.id
                    ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-500 shadow-sm"
                    : "bg-slate-50 dark:bg-slate-850 border-slate-200 dark:border-slate-800 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    {c.estat || "OBERTA"}
                  </span>
                </div>
                <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100 mt-1 truncate">
                  {c.titol}
                </h4>
              </div>
            ))
          )}
        </div>

        {/* Finestra de Xat */}
        {conversaActiva ? (
          <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-950">
            {/* Capçalera conversa */}
            <div className="p-3.5 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div>
                <h2 className="text-xs font-bold text-slate-800 dark:text-slate-100">
                  {conversaActiva.titol}
                </h2>
                <p className="text-[10px] font-mono text-slate-500">
                  ID: {conversaActiva.id}
                </p>
              </div>
            </div>

            {/* Zona de missatges */}
            <div className="flex-1 p-4 overflow-y-auto space-y-3">
              {loadingMissatges ? (
                <div className="p-8 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
                  <span>Carregant missatges...</span>
                </div>
              ) : missatges.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-xs">
                  <p>Aquesta conversa encara no té missatges. Escriu el primer missatge a sota.</p>
                </div>
              ) : (
                missatges.map((m) => {
                  const isOficina = m.remitent === "OFICINA";
                  return (
                    <div
                      key={m.id}
                      className={`flex flex-col ${isOficina ? "items-end" : "items-start"}`}
                    >
                      <div
                        className={`max-w-md p-3 rounded-2xl text-xs ${
                          isOficina
                            ? "bg-emerald-600 text-white rounded-br-sm"
                            : "bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 border border-slate-200 dark:border-slate-700 rounded-bl-sm"
                        }`}
                      >
                        <p>{m.contingut_text}</p>
                      </div>
                      <span className="text-[9px] text-slate-400 mt-1 font-mono px-1">
                        {m.remitent} • {m.canal}
                      </span>
                    </div>
                  );
                })
              )}
            </div>

            {/* Input d'enviament */}
            <form onSubmit={handleEnviarMissatge} className="p-3 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex gap-2">
              <input
                type="text"
                value={nouText}
                onChange={(e) => setNouText(e.target.value)}
                placeholder="Escriu un missatge per al client..."
                className="flex-1 px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:outline-none focus:border-emerald-600"
              />
              <button
                type="submit"
                disabled={enviant || !nouText.trim()}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow disabled:opacity-50"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Enviar</span>
              </button>
            </form>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
            <MessageSquare className="w-12 h-12 stroke-[1.5] text-slate-300 dark:text-slate-700 mb-3" />
            <p className="font-medium text-sm text-slate-600 dark:text-slate-400">
              Selecciona una conversa de la safata
            </p>
          </div>
        )}
      </div>

      {/* Modal Nova Conversa */}
      {modalNova && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Plus className="w-4 h-4 text-emerald-600" />
                Nova Conversa amb Client
              </h3>
              <button
                onClick={() => setModalNova(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearConversa} className="p-5 space-y-4">
              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Client *
                </label>
                {clients.length === 0 ? (
                  <p className="text-xs text-amber-600">No hi ha clients disponibles. Cal crear primer un client.</p>
                ) : (
                  <select
                    value={selectedClientId}
                    onChange={(e) => setSelectedClientId(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-semibold"
                  >
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.codi} - {c.rao_social}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Títol o Assumpte *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Assessorament reg sector 3"
                  value={nouTitol}
                  onChange={(e) => setNouTitol(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                />
              </div>

              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNova(false)}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={!selectedClientId || !nouTitol.trim()}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow disabled:opacity-50"
                >
                  Crear Conversa
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
