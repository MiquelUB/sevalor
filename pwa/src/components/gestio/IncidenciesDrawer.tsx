"use client";

import React, { useState, useEffect } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  X,
  RefreshCw,
  User,
  FileText,
  Volume2,
  Image as ImageIcon,
  Check,
  ShieldCheck,
  ExternalLink,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

export interface IncidenciaDrawerItem {
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

interface IncidenciesDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onIncidenciaUpdated?: () => void;
}

export function IncidenciesDrawer({
  isOpen,
  onClose,
  onIncidenciaUpdated,
}: IncidenciesDrawerProps) {
  const [incidencies, setIncidencies] = useState<IncidenciaDrawerItem[]>([]);
  const [filtre, setFiltre] = useState<"OBERTA" | "RESOLTA" | "TOTES">("OBERTA");
  const [loading, setLoading] = useState(false);
  const [resolentId, setResolentId] = useState<string | null>(null);
  const [modalFotoUrl, setModalFotoUrl] = useState<string | null>(null);

  const carregarIncidencies = async () => {
    setLoading(true);
    try {
      const data = await apiFetch<IncidenciaDrawerItem[]>(
        "/gestio/dashboard/incidencies-drawer?totes=true"
      );
      setIncidencies(data || []);
    } catch {
      setIncidencies([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      carregarIncidencies();
    }
  }, [isOpen]);

  const handleResoldre = async (id: string) => {
    setResolentId(id);
    try {
      await apiFetch(`/gestio/dashboard/incidencies/${id}/resoldre`, {
        method: "PATCH",
      });
      setIncidencies((prev) =>
        prev.map((i) => (i.id === id ? { ...i, estat: "VERD" } : i))
      );
      if (onIncidenciaUpdated) onIncidenciaUpdated();
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
      if (onIncidenciaUpdated) onIncidenciaUpdated();
    } catch (err: any) {
      alert("Error en l'aprovació HITL: " + (err.message || err));
    } finally {
      setResolentId(null);
    }
  };

  if (!isOpen) return null;

  const obertesCount = incidencies.filter(
    (i) => !["VERD", "RESOLTA", "TANCADA"].includes(i.estat)
  ).length;

  const filtrades = incidencies.filter((item) => {
    const esResolta = ["VERD", "RESOLTA", "TANCADA"].includes(item.estat);
    if (filtre === "OBERTA") return !esResolta;
    if (filtre === "RESOLTA") return esResolta;
    return true;
  });

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Slide-over Drawer Panel */}
      <div className="relative w-full max-w-xl bg-surface-container-lowest dark:bg-slate-900 h-full shadow-2xl flex flex-col border-l border-outline-variant/30 z-10 transition-transform duration-300">
        {/* Header */}
        <div className="p-lg border-b border-outline-variant/20 flex items-center justify-between bg-surface-container-low/60 dark:bg-slate-800/50">
          <div className="flex items-center gap-md">
            <div className="w-10 h-10 rounded-xl bg-error-container/30 text-error flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-section-title text-base text-primary dark:text-white flex items-center gap-sm">
                <span>Calaix d&apos;Incidències de Camp</span>
                {obertesCount > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-extrabold bg-error text-white animate-pulse">
                    {obertesCount} obertes
                  </span>
                )}
              </h2>
              <p className="text-xs text-on-surface-variant dark:text-slate-400">
                Supervisió reactiva d&apos;imprevistos, auditories i bloquejos de quadrilla.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-xs">
            <button
              onClick={carregarIncidencies}
              disabled={loading}
              className="p-sm rounded-lg hover:bg-surface-container-high text-on-surface-variant transition-colors"
              title="Actualitzar incidències"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-sm rounded-lg hover:bg-surface-container-high text-on-surface-variant transition-colors"
              title="Tancar calaix"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="px-lg py-sm border-b border-outline-variant/15 flex items-center justify-between bg-surface-container-lowest dark:bg-slate-900">
          <div className="flex items-center gap-xs">
            <button
              type="button"
              onClick={() => setFiltre("OBERTA")}
              className={`px-md py-1.5 rounded-lg text-xs font-body-strong transition-all ${
                filtre === "OBERTA"
                  ? "bg-error text-white shadow-sm font-extrabold"
                  : "bg-surface-container-high text-on-surface-variant hover:text-on-surface"
              }`}
            >
              🔴 Obertes ({obertesCount})
            </button>
            <button
              type="button"
              onClick={() => setFiltre("RESOLTA")}
              className={`px-md py-1.5 rounded-lg text-xs font-body-strong transition-all ${
                filtre === "RESOLTA"
                  ? "bg-green-600 text-white shadow-sm font-extrabold"
                  : "bg-surface-container-high text-on-surface-variant hover:text-on-surface"
              }`}
            >
              🟢 Resoltes ({incidencies.length - obertesCount})
            </button>
            <button
              type="button"
              onClick={() => setFiltre("TOTES")}
              className={`px-md py-1.5 rounded-lg text-xs font-body-strong transition-all ${
                filtre === "TOTES"
                  ? "bg-primary text-white shadow-sm font-extrabold"
                  : "bg-surface-container-high text-on-surface-variant hover:text-on-surface"
              }`}
            >
              Totes ({incidencies.length})
            </button>
          </div>
          <span className="text-[11px] font-mono text-outline">
            {filtrades.length} resultats
          </span>
        </div>

        {/* Content List */}
        <div className="flex-1 overflow-y-auto p-lg space-y-md custom-scrollbar bg-surface/30 dark:bg-slate-950/40">
          {loading && incidencies.length === 0 ? (
            <div className="p-xl text-center">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto text-primary mb-sm" />
              <p className="text-xs text-on-surface-variant">Carregant incidències de camp...</p>
            </div>
          ) : filtrades.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-xl">
              <div className="w-14 h-14 rounded-2xl bg-green-50 dark:bg-green-950/30 text-green-600 dark:text-green-400 flex items-center justify-center mb-md">
                <ShieldCheck className="w-8 h-8" />
              </div>
              <h3 className="font-body-strong text-base text-on-surface dark:text-white">
                Cap incidència activa
              </h3>
              <p className="text-xs text-on-surface-variant dark:text-slate-400 mt-xs max-w-sm">
                Totes les quadrilles al terreny operen sense bloquejos tècnics ni aturades reportades.
              </p>
            </div>
          ) : (
            filtrades.map((inc) => {
              const esOberta = !["VERD", "RESOLTA", "TANCADA"].includes(inc.estat);
              const dataStr = inc.created_at
                ? new Date(inc.created_at).toLocaleString("ca-ES", {
                    day: "2-digit",
                    month: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "Recent";

              return (
                <div
                  key={inc.id}
                  className={`p-md rounded-xl border transition-all ${
                    esOberta
                      ? "bg-surface-container-lowest dark:bg-slate-900 border-error/30 shadow-sm"
                      : "bg-surface-container-low/50 dark:bg-slate-900/40 border-outline-variant/20 opacity-85"
                  }`}
                >
                  {/* Top Bar: Estat + Àmbit + Data */}
                  <div className="flex items-center justify-between gap-sm mb-xs">
                    <div className="flex items-center gap-xs">
                      {esOberta ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-error text-white tracking-wider flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                          VERMELL (BLOQUEJANT)
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 tracking-wider flex items-center gap-1">
                          <Check className="w-3 h-3" />
                          VERD (RESOLTA)
                        </span>
                      )}
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-surface-container-high text-on-surface-variant uppercase tracking-wider">
                        {inc.ambit || "TASCA"}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-outline flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {dataStr}
                    </span>
                  </div>

                  {/* Operari & Ordre Treball Info */}
                  <div className="flex flex-wrap items-center gap-x-md gap-y-xs text-xs mb-sm text-on-surface-variant dark:text-slate-300">
                    <span className="flex items-center gap-1 font-body-strong text-primary dark:text-slate-200">
                      <User className="w-3.5 h-3.5 text-primary" />
                      {inc.operari_nom || "Operari de camp"}
                    </span>
                    {inc.ordre_treball_codi && (
                      <span className="flex items-center gap-1 font-mono text-xs bg-surface-container px-2 py-0.5 rounded">
                        <FileText className="w-3.5 h-3.5 text-secondary" />
                        {inc.ordre_treball_codi}: {inc.ordre_treball_titol || ""}
                      </span>
                    )}
                    {inc.client_nom && (
                      <span className="text-[11px] text-outline font-medium">
                        Client: {inc.client_nom}
                      </span>
                    )}
                  </div>

                  {/* Descripció de l'Avaria */}
                  <div className="p-sm rounded-lg bg-surface-container-low dark:bg-slate-950/60 text-xs text-on-surface dark:text-slate-200 leading-relaxed mb-sm">
                    {inc.text_observacions || "Sense comentaris addicionals aportats."}
                  </div>

                  {/* Adjunts Multimèdia (Àudio & Foto) */}
                  <div className="space-y-xs mb-sm">
                    {inc.audio_path && (
                      <div className="p-xs rounded-lg bg-surface-container-high/60 flex items-center gap-sm">
                        <Volume2 className="w-4 h-4 text-primary shrink-0" />
                        <audio
                          controls
                          className="w-full h-7 text-xs"
                          src={
                            inc.audio_path.startsWith("http")
                              ? inc.audio_path
                              : `${inc.audio_path}`
                          }
                        />
                      </div>
                    )}

                    {inc.foto_path && (
                      <div className="flex items-center gap-sm">
                        <button
                          type="button"
                          onClick={() => setModalFotoUrl(inc.foto_path || null)}
                          className="flex items-center gap-xs px-2.5 py-1 rounded bg-surface-container-high hover:bg-surface-container-highest text-primary text-xs font-body-strong transition-colors"
                        >
                          <ImageIcon className="w-3.5 h-3.5" />
                          <span>Veure fotografia d&apos;avaria</span>
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Accions de Resolució (Enginyeria / HITL) */}
                  {esOberta && (
                    <div className="pt-xs border-t border-outline-variant/15 flex items-center justify-end gap-sm">
                      <button
                        type="button"
                        disabled={resolentId === inc.id}
                        onClick={() => handleAprovarHitl(inc.id)}
                        className="px-md py-1.5 rounded-lg bg-secondary-container hover:bg-secondary text-on-secondary-container hover:text-white text-xs font-body-strong flex items-center gap-1 transition-all"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Aprovar HITL</span>
                      </button>
                      <button
                        type="button"
                        disabled={resolentId === inc.id}
                        onClick={() => handleResoldre(inc.id)}
                        className="px-md py-1.5 rounded-lg bg-green-600 hover:bg-green-700 text-white text-xs font-body-strong flex items-center gap-1 shadow-sm transition-all"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Marcar Resolta (Verd)</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="p-md border-t border-outline-variant/20 bg-surface-container-lowest dark:bg-slate-900 flex items-center justify-between text-xs text-on-surface-variant">
          <span>Incidències sincronitzades amb PostgreSQL i memòria sobirana.</span>
          <button
            onClick={onClose}
            className="px-lg py-1.5 rounded-lg bg-surface-container-high text-on-surface font-body-strong hover:bg-surface-container-highest"
          >
            Tancar
          </button>
        </div>
      </div>

      {/* Modal Lightbox Foto */}
      {modalFotoUrl && (
        <div
          className="fixed inset-0 z-60 bg-black/80 flex items-center justify-center p-md"
          onClick={() => setModalFotoUrl(null)}
        >
          <div className="relative max-w-2xl max-h-[90vh] bg-slate-950 p-2 rounded-xl">
            <button
              onClick={() => setModalFotoUrl(null)}
              className="absolute top-4 right-4 p-1 bg-black/60 rounded-full text-white hover:bg-black"
            >
              <X className="w-6 h-6" />
            </button>
            <img
              src={modalFotoUrl}
              alt="Fotografia incidència"
              className="max-w-full max-h-[80vh] object-contain rounded-lg"
            />
          </div>
        </div>
      )}
    </div>
  );
}
