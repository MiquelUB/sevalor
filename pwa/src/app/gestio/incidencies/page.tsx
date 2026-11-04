"use client";

import React, { useState, useEffect } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Search,
  RefreshCw,
  User,
  FileText,
  Volume2,
  Image as ImageIcon,
  Check,
  ShieldCheck,
  X,
  Filter,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Incidencia {
  id: string;
  ambit: string;
  estat: string;
  grau?: string;
  text_observacions?: string | null;
  audio_path?: string | null;
  foto_path?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  operari_id?: string | null;
  operari_nom?: string;
  ordre_treball_id?: string | null;
  ordre_treball_codi?: string | null;
  ordre_treball_titol?: string | null;
  client_nom?: string | null;
}

export default function GestioIncidenciesPage() {
  const [incidencies, setIncidencies] = useState<Incidencia[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cerca, setCerca] = useState("");
  const [filtreAmbit, setFiltreAmbit] = useState<string>("TOTS");
  const [filtreEstat, setFiltreEstat] = useState<string>("TOTS");
  const [resolentId, setResolentId] = useState<string | null>(null);
  const [modalFotoUrl, setModalFotoUrl] = useState<string | null>(null);

  const carregarDades = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Incidencia[]>(
        "/gestio/dashboard/incidencies-drawer?totes=true"
      );
      setIncidencies(data || []);
    } catch (err: any) {
      setError(err.message || "Error en carregar les incidències");
      setIncidencies([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarDades();
  }, []);

  const handleResoldre = async (id: string) => {
    setResolentId(id);
    try {
      await apiFetch(`/gestio/dashboard/incidencies/${id}/resoldre`, {
        method: "PATCH",
      });
      setIncidencies((prev) =>
        prev.map((i) => (i.id === id ? { ...i, estat: "VERD" } : i))
      );
    } catch (err: any) {
      alert("Error al resoldre la incidència: " + (err.message || err));
    } finally {
      setResolentId(null);
    }
  };

  const handleAprovarHitl = async (id: string) => {
    setResolentId(id);
    try {
      await apiFetch(`/gestio/dashboard/incidencies/${id}/aprova-hitl`, {
        method: "PATCH",
      });
      setIncidencies((prev) =>
        prev.map((i) => (i.id === id ? { ...i, estat: "VERD" } : i))
      );
    } catch (err: any) {
      alert("Error en l'aprovació HITL: " + (err.message || err));
    } finally {
      setResolentId(null);
    }
  };

  const obertesCount = incidencies.filter(
    (i) => !["VERD", "RESOLTA", "TANCADA"].includes(i.estat)
  ).length;
  const resoltesCount = incidencies.length - obertesCount;
  const ambAudioCount = incidencies.filter((i) => Boolean(i.audio_path)).length;

  const incidenciesFiltrades = incidencies.filter((inc) => {
    const esResolta = ["VERD", "RESOLTA", "TANCADA"].includes(inc.estat);
    if (filtreEstat === "OBERTA" && esResolta) return false;
    if (filtreEstat === "RESOLTA" && !esResolta) return false;

    if (filtreAmbit !== "TOTS" && inc.ambit !== filtreAmbit) return false;

    if (cerca.trim()) {
      const q = cerca.toLowerCase();
      const textMatch = (inc.text_observacions || "").toLowerCase().includes(q);
      const opMatch = (inc.operari_nom || "").toLowerCase().includes(q);
      const otMatch = (inc.ordre_treball_codi || "").toLowerCase().includes(q);
      const titolMatch = (inc.ordre_treball_titol || "").toLowerCase().includes(q);
      const clientMatch = (inc.client_nom || "").toLowerCase().includes(q);
      return textMatch || opMatch || otMatch || titolMatch || clientMatch;
    }
    return true;
  });

  return (
    <div className="flex flex-col w-full gap-lg">
      {/* 1. Header */}
      <section className="flex flex-wrap items-end justify-between gap-md">
        <div>
          <h1 className="font-display-lg text-display-lg text-primary mb-xs">
            Incidències i Bloquejos de Camp
          </h1>
          <p className="font-body-base text-on-surface-variant max-w-2xl">
            Supervisió, resolució i peritatge tècnic en temps real de les incidències reportades pels operaris des de la PWA.
          </p>
        </div>
        <div className="flex items-center gap-sm">
          <button
            onClick={carregarDades}
            disabled={loading}
            className="px-lg py-sm rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-on-surface text-sm font-body-strong shadow-sm flex items-center gap-xs transition-all cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            <span>Actualitzar</span>
          </button>
        </div>
      </section>

      {/* 2. KPI Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-md">
        <div className="bg-surface-container-lowest p-md rounded-xl shadow-sm border border-outline-variant/20 flex flex-col justify-between">
          <span className="font-label-caps text-on-surface-variant uppercase text-xs">
            Total Reportades
          </span>
          <div className="font-display-lg text-2xl font-bold text-on-surface mt-xs font-mono">
            {incidencies.length}
          </div>
        </div>

        <div className="bg-surface-container-lowest p-md rounded-xl shadow-sm border-l-4 border-error border-outline-variant/20 flex flex-col justify-between">
          <span className="font-label-caps text-error uppercase text-xs font-bold">
            Obertes / Bloquejants
          </span>
          <div className="font-display-lg text-2xl font-bold text-error mt-xs font-mono flex items-center gap-2">
            <span>{obertesCount}</span>
            {obertesCount > 0 && (
              <span className="text-xs font-normal text-on-error-container bg-error-container/40 px-2 py-0.5 rounded-full">
                Requereixen atenció
              </span>
            )}
          </div>
        </div>

        <div className="bg-surface-container-lowest p-md rounded-xl shadow-sm border-l-4 border-green-500 border-outline-variant/20 flex flex-col justify-between">
          <span className="font-label-caps text-green-700 uppercase text-xs font-bold">
            Resoltes / Desbloquejades
          </span>
          <div className="font-display-lg text-2xl font-bold text-green-700 mt-xs font-mono">
            {resoltesCount}
          </div>
        </div>

        <div className="bg-surface-container-lowest p-md rounded-xl shadow-sm border border-outline-variant/20 flex flex-col justify-between">
          <span className="font-label-caps text-primary uppercase text-xs">
            Amb Nota de Veu (Àudio)
          </span>
          <div className="font-display-lg text-2xl font-bold text-primary mt-xs font-mono flex items-center gap-2">
            <Volume2 className="w-5 h-5 text-primary" />
            <span>{ambAudioCount}</span>
          </div>
        </div>
      </div>

      {/* 3. Filtres & Cerca */}
      <div className="bg-surface-container-lowest p-md rounded-xl shadow-sm border border-outline-variant/25 flex flex-wrap items-center justify-between gap-md">
        <div className="flex-1 min-w-[260px] relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
          <input
            type="text"
            value={cerca}
            onChange={(e) => setCerca(e.target.value)}
            placeholder="Cerca per descripció, operari, codi d'ordre de treball o client..."
            className="w-full pl-9 pr-4 py-2 bg-surface-container-low rounded-lg text-xs font-body border border-outline-variant/30 outline-none focus:border-primary"
          />
        </div>

        <div className="flex flex-wrap items-center gap-sm">
          <div className="flex items-center gap-xs text-xs font-body-strong">
            <span className="text-on-surface-variant font-label-caps uppercase text-[10px]">
              Àmbit:
            </span>
            <select
              value={filtreAmbit}
              onChange={(e) => setFiltreAmbit(e.target.value)}
              className="bg-surface-container-low px-2 py-1.5 rounded-lg border border-outline-variant/30 text-xs font-bold outline-none cursor-pointer"
            >
              <option value="TOTS">Tots els àmbits</option>
              <option value="TASCA">Tasca / Obra</option>
              <option value="VEHICLE">Vehicle / Flota</option>
              <option value="MATERIAL">Material / Estoc</option>
              <option value="CLIENT">Client / Accés</option>
            </select>
          </div>

          <div className="flex items-center gap-xs text-xs font-body-strong">
            <span className="text-on-surface-variant font-label-caps uppercase text-[10px]">
              Estat:
            </span>
            <select
              value={filtreEstat}
              onChange={(e) => setFiltreEstat(e.target.value)}
              className="bg-surface-container-low px-2 py-1.5 rounded-lg border border-outline-variant/30 text-xs font-bold outline-none cursor-pointer"
            >
              <option value="TOTS">Tots els estats</option>
              <option value="OBERTA">🔴 Obertes (Bloquejant)</option>
              <option value="RESOLTA">🟢 Resoltes (Verd)</option>
            </select>
          </div>
        </div>
      </div>

      {/* 4. Llistat d'Incidències */}
      <section className="bg-surface-container-lowest rounded-xl shadow-xl overflow-hidden border border-outline-variant/20">
        {loading && incidencies.length === 0 ? (
          <div className="p-16 text-center">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto text-primary mb-3" />
            <p className="font-body-strong text-sm text-on-surface">
              Carregant incidències del sistema...
            </p>
          </div>
        ) : incidenciesFiltrades.length === 0 ? (
          <div className="p-16 text-center">
            <ShieldCheck className="w-12 h-12 text-outline mx-auto mb-3" />
            <h3 className="font-body-strong text-base text-on-surface">
              No hi ha incidències coincidents
            </h3>
            <p className="text-xs text-on-surface-variant mt-1">
              {incidencies.length === 0
                ? "No hi ha cap incidència registrada per les quadrilles a camp. La plataforma opera amb normalitat."
                : "Modifica els filtres o el text de cerca per trobar registres."}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-outline-variant/15">
            {incidenciesFiltrades.map((inc) => {
              const esOberta = !["VERD", "RESOLTA", "TANCADA"].includes(inc.estat);
              const dataStr = inc.created_at
                ? new Date(inc.created_at).toLocaleString("ca-ES", {
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "Recent";

              return (
                <div
                  key={inc.id}
                  className={`p-lg hover:bg-surface-container-low/40 transition-colors flex flex-col lg:flex-row lg:items-center justify-between gap-md ${
                    esOberta ? "border-l-4 border-error" : "border-l-4 border-green-500"
                  }`}
                >
                  <div className="flex-1 space-y-sm">
                    {/* Header badges */}
                    <div className="flex flex-wrap items-center gap-xs">
                      {esOberta ? (
                        <span className="px-2.5 py-1 rounded-full text-[11px] font-extrabold bg-error text-white tracking-wider inline-flex items-center gap-1.5 shadow-sm">
                          <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                          VERMELL (BLOQUEJANT)
                        </span>
                      ) : (
                        <span className="px-2.5 py-1 rounded-full text-[11px] font-extrabold bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 tracking-wider inline-flex items-center gap-1">
                          <Check className="w-3.5 h-3.5" />
                          VERD (RESOLTA)
                        </span>
                      )}
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-surface-container-high text-on-surface-variant uppercase tracking-wider">
                        {inc.ambit || "TASCA"}
                      </span>
                      <span className="text-xs font-mono text-outline flex items-center gap-1 ml-2">
                        <Clock className="w-3.5 h-3.5" />
                        {dataStr}
                      </span>
                    </div>

                    {/* Metadata: Operari i OT */}
                    <div className="flex flex-wrap items-center gap-x-lg gap-y-xs text-xs text-on-surface-variant">
                      <span className="font-body-strong text-primary flex items-center gap-1 text-sm">
                        <User className="w-4 h-4" />
                        {inc.operari_nom || "Operari de camp"}
                      </span>
                      {inc.ordre_treball_codi && (
                        <span className="font-mono bg-surface-container-high px-2 py-0.5 rounded text-xs text-on-surface flex items-center gap-1">
                          <FileText className="w-3.5 h-3.5 text-secondary" />
                          {inc.ordre_treball_codi}: {inc.ordre_treball_titol || ""}
                        </span>
                      )}
                      {inc.client_nom && (
                        <span className="text-xs text-outline font-medium">
                          Client: {inc.client_nom}
                        </span>
                      )}
                    </div>

                    {/* Observacions */}
                    <div className="p-md rounded-xl bg-surface-container-low text-xs text-on-surface leading-relaxed max-w-4xl border border-outline-variant/15">
                      {inc.text_observacions || "Sense comentaris addicionals aportats per l'operari."}
                    </div>

                    {/* Multimèdia */}
                    <div className="flex flex-wrap items-center gap-md pt-xs">
                      {inc.audio_path && (
                        <div className="p-xs rounded-lg bg-surface-container-high/70 flex items-center gap-sm max-w-sm">
                          <Volume2 className="w-4 h-4 text-primary shrink-0" />
                          <audio
                            controls
                            className="w-full h-8 text-xs"
                            src={inc.audio_path}
                          />
                        </div>
                      )}
                      {inc.foto_path && (
                        <button
                          type="button"
                          onClick={() => setModalFotoUrl(inc.foto_path || null)}
                          className="px-3 py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-primary font-body-strong text-xs flex items-center gap-1.5 transition-colors"
                        >
                          <ImageIcon className="w-4 h-4" />
                          <span>Veure fotografia d&apos;obra</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Accions dreta */}
                  {esOberta && (
                    <div className="flex flex-row lg:flex-col items-end gap-sm shrink-0 pt-sm lg:pt-0">
                      <button
                        type="button"
                        disabled={resolentId === inc.id}
                        onClick={() => handleAprovarHitl(inc.id)}
                        className="px-lg py-2 rounded-lg bg-secondary-container hover:bg-secondary text-on-secondary-container hover:text-white text-xs font-body-strong flex items-center gap-1.5 transition-all shadow-sm cursor-pointer"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        <span>Aprovar HITL</span>
                      </button>
                      <button
                        type="button"
                        disabled={resolentId === inc.id}
                        onClick={() => handleResoldre(inc.id)}
                        className="px-lg py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-xs font-body-strong flex items-center gap-1.5 shadow-md transition-all cursor-pointer"
                      >
                        <Check className="w-4 h-4" />
                        <span>Marcar Resolta (Verd)</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Lightbox Modal Foto */}
      {modalFotoUrl && (
        <div
          className="fixed inset-0 z-60 bg-black/85 flex items-center justify-center p-md"
          onClick={() => setModalFotoUrl(null)}
        >
          <div className="relative max-w-3xl max-h-[90vh] bg-slate-950 p-2 rounded-xl">
            <button
              onClick={() => setModalFotoUrl(null)}
              className="absolute top-4 right-4 p-1.5 bg-black/70 rounded-full text-white hover:bg-black"
            >
              <X className="w-6 h-6" />
            </button>
            <img
              src={modalFotoUrl}
              alt="Fotografia de la incidència"
              className="max-w-full max-h-[82vh] object-contain rounded-lg"
            />
          </div>
        </div>
      )}
    </div>
  );
}
