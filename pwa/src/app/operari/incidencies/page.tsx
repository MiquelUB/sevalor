"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  PhoneCall,
  ArrowLeft,
  Send,
  AlertCircle,
  CheckCircle2,
  Clock,
  RefreshCw,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import CameraInput from "@/components/CameraInput";
import VoiceRecorder from "@/components/operari/VoiceRecorder";
import { db } from "@/lib/offline/db";
import { addToSyncQueue } from "@/lib/offline/sync";

interface IncidenciaItem {
  id: string;
  ambit: string;
  estat: string;
  text_observacions?: string;
  created_at?: string;
}

export default function OperariIncidenciesPage() {
  const [descripcio, setDescripcio] = useState("");
  const [tipus, setTipus] = useState("VEHICLE");
  const [audioGravat, setAudioGravat] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [fotoPujada, setFotoPujada] = useState(false);
  const [enviant, setEnviant] = useState(false);
  const [enviatExit, setEnviatExit] = useState(false);
  const [errorValidacio, setErrorValidacio] = useState<string | null>(null);

  // Llista d'incidències prèvies de l'operari
  const [historial, setHistorial] = useState<IncidenciaItem[]>([]);
  const [pendingOffline, setPendingOffline] = useState<any[]>([]);
  const [loadingHistorial, setLoadingHistorial] = useState(false);

  const carregarHistorial = async () => {
    setLoadingHistorial(true);
    try {
      const data = await apiFetch<IncidenciaItem[]>("/operari/incidencies");
      setHistorial(data || []);
    } catch {
      setHistorial([]);
    } finally {
      setLoadingHistorial(false);
    }

    if (typeof window !== "undefined") {
      try {
        const queueItems = await db.sync_queue
          .where("action")
          .equals("REPORTAR_INCIDENCIA")
          .toArray();
        setPendingOffline(queueItems);
      } catch (err) {
        console.error("Error carregar offline sync queue:", err);
      }
    }
  };

  useEffect(() => {
    carregarHistorial();
  }, []);

  const handleRecordComplete = (blob: Blob) => {
    setAudioBlob(blob);
    setAudioGravat(true);
    setErrorValidacio(null);
  };

  const handleAudioClear = () => {
    setAudioBlob(null);
    setAudioGravat(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!descripcio.trim() && !audioGravat && !fotoPujada) {
      setErrorValidacio(
        "Aporta almenys una font d'informació: nota d'àudio, fotografia o descripció."
      );
      return;
    }

    setEnviant(true);
    setErrorValidacio(null);

    const isOnline = typeof navigator !== "undefined" && navigator.onLine;

    try {
      if (isOnline && audioBlob) {
        const formData = new FormData();
        formData.append("ambit", tipus);
        formData.append("estat", "VERMELL");
        if (descripcio.trim()) {
          formData.append("text_observacions", descripcio.trim());
        }
        formData.append("audio", audioBlob, "incidencia.webm");

        await apiFetch("/operari/incidencies", {
          method: "POST",
          body: formData,
        });
      } else {
        const payload = {
          ambit: tipus,
          estat: "VERMELL",
          text_observacions:
            descripcio.trim() ||
            (audioGravat
              ? "Nota de veu gravada en camp"
              : "Fotografia d'avaria aportada"),
          audio_path: audioGravat ? "/docs/audio/incidencia_live.webm" : null,
          foto_path: fotoPujada ? "/docs/fotos/incidencia_live.webp" : null,
        };
        await addToSyncQueue("REPORTAR_INCIDENCIA", payload);
      }

      setEnviatExit(true);
      await carregarHistorial();
    } catch (err: any) {
      setErrorValidacio(err.message || "Error al notificar la incidència");
    } finally {
      setEnviant(false);
    }
  };

  const ambitsConfig = [
    { id: "VEHICLE", label: "VEHICLE", icon: "local_shipping" },
    { id: "MATERIAL", label: "MATERIAL", icon: "inventory_2" },
    { id: "CLIENT", label: "CLIENT", icon: "water_damage" },
  ];

  return (
    <div className="flex-1 flex flex-col bg-surface dark:bg-slate-950 text-on-surface dark:text-slate-100 transition-colors">
      {/* Barra de Navegació Stitch Screen 481e9bc3205541b59a1226cd2f081f7f */}
      <header className="bg-surface-container-lowest dark:bg-slate-900 text-primary dark:text-white p-4 flex items-center justify-between border-b border-outline-variant/25 dark:border-slate-800">
        <Link
          href="/operari/feines"
          className="flex items-center gap-1.5 text-xs font-bold text-primary dark:text-slate-300 hover:opacity-80"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Tornar</span>
        </Link>
        <h1 className="text-sm font-extrabold uppercase tracking-wider text-primary dark:text-white">
          Incidència de Camp (Spec 016)
        </h1>
        <span className="material-symbols-outlined text-error text-xl">
          warning
        </span>
      </header>

      <div className="p-4 flex-1 flex flex-col gap-4 overflow-y-auto">
        {/* BOTÓ SOS 112 DIRECTE (Spec 016 RF-07) */}
        <a
          href="tel:112"
          className="w-full py-3.5 px-6 rounded-xl bg-error hover:opacity-95 active:scale-[0.98] text-white font-extrabold text-sm flex items-center justify-center gap-3 shadow-lg shadow-error/25 transition-all uppercase tracking-wider shrink-0"
        >
          <PhoneCall className="w-4 h-4 animate-pulse" />
          <span>SOS EMERGÈNCIA (112)</span>
        </a>

        {enviatExit ? (
          <div className="p-6 bg-surface-container-lowest dark:bg-slate-900 rounded-xl border border-secondary-container/40 text-center shadow-sm space-y-3">
            <div className="w-12 h-12 rounded-full bg-secondary-container/15 text-secondary flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h3 className="text-base font-extrabold text-primary dark:text-slate-100">
              Incidència Notificada amb Èxit
            </h3>
            <p className="text-xs text-on-surface-variant dark:text-slate-400 max-w-xs mx-auto">
              S&apos;ha registrat a la base de dades i notificat a la Torre de Control d&apos;Enginyers.
            </p>
            <button
              onClick={() => {
                setEnviatExit(false);
                setDescripcio("");
                setAudioGravat(false);
                setAudioBlob(null);
                setFotoPujada(false);
              }}
              className="mt-2 px-4 py-2.5 bg-primary text-white text-xs font-bold rounded-xl"
            >
              Registrar una altra incidència
            </button>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="bg-surface-container-lowest dark:bg-slate-900 p-5 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-4"
          >
            {/* Selector d'Àmbit Stitch Tactile Cards */}
            <div>
              <label className="block text-[11px] font-extrabold uppercase tracking-wider text-on-surface-variant dark:text-slate-400 mb-2">
                Àmbit de l&apos;Avaria
              </label>
              <div className="grid grid-cols-3 gap-2.5">
                {ambitsConfig.map((ambit) => {
                  const active = tipus === ambit.id;
                  return (
                    <button
                      key={ambit.id}
                      type="button"
                      onClick={() => setTipus(ambit.id)}
                      className={`py-3 px-2 rounded-xl border flex flex-col items-center justify-center gap-1.5 transition-all active:scale-95 ${
                        active
                          ? "bg-error-container/50 border-error text-on-error-container font-extrabold shadow-sm"
                          : "bg-surface-container-low dark:bg-slate-800 border-outline-variant/30 dark:border-slate-700 text-on-surface-variant dark:text-slate-300 font-bold"
                      }`}
                    >
                      <span
                        className={`material-symbols-outlined text-2xl ${
                          active ? "text-error" : "text-primary dark:text-slate-400"
                        }`}
                      >
                        {ambit.icon}
                      </span>
                      <span className="text-[11px] tracking-wider">
                        {ambit.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <CameraInput
                captured={fotoPujada}
                label="Càmera en Viu"
                onCapture={() => {
                  setFotoPujada(true);
                  setErrorValidacio(null);
                }}
              />
            </div>

            <div>
              <VoiceRecorder
                onRecordComplete={handleRecordComplete}
                onClear={handleAudioClear}
                maxSeconds={30}
              />
            </div>

            <div>
              <label className="block text-[11px] font-extrabold uppercase tracking-wider text-on-surface-variant dark:text-slate-400 mb-1.5">
                Descripció de la situació
              </label>
              <textarea
                value={descripcio}
                onChange={(e) => {
                  setDescripcio(e.target.value);
                  setErrorValidacio(null);
                }}
                rows={3}
                placeholder="Detalla breument què ha succeït o indica el suport necessari..."
                className="w-full p-3 rounded-xl border border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              />
            </div>

            {errorValidacio && (
              <div className="p-3 rounded-xl bg-error-container/60 border border-error/30 text-on-error-container text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-error" />
                <span>{errorValidacio}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={enviant}
              className="w-full py-3.5 rounded-xl bg-error hover:opacity-95 text-white text-xs font-extrabold uppercase tracking-wider flex items-center justify-center gap-2 shadow-md disabled:opacity-50 transition-all"
            >
              <Send className="w-4 h-4" />
              <span>
                {enviant
                  ? "Enviant incidència..."
                  : "Notificar Incidència al Centre"}
              </span>
            </button>
          </form>
        )}

        {/* Historial d'incidències prèvies de l'operari */}
        <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-primary dark:text-slate-300">
              Les Teves Incidències Recents
            </h3>
            <button
              onClick={carregarHistorial}
              className="p-1.5 rounded-lg bg-surface-container-low dark:bg-slate-800 text-on-surface-variant hover:text-primary"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${
                  loadingHistorial ? "animate-spin" : ""
                }`}
              />
            </button>
          </div>

          {loadingHistorial &&
          historial.length === 0 &&
          pendingOffline.length === 0 ? (
            <p className="text-xs text-on-surface-variant py-4 text-center">
              Carregant incidències...
            </p>
          ) : historial.length === 0 && pendingOffline.length === 0 ? (
            <div className="py-6 text-center text-on-surface-variant space-y-1">
              <CheckCircle2 className="w-8 h-8 mx-auto text-secondary-container/60 mb-2" />
              <p className="text-xs font-bold text-primary dark:text-slate-300">
                Sense incidències pendents
              </p>
              <p className="text-[11px] text-on-surface-variant">
                Tot el material i vehicles estan operatius.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {pendingOffline.map((item, idx) => (
                <div
                  key={`pending-${idx}`}
                  className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-center justify-between text-xs"
                >
                  <div className="space-y-0.5">
                    <span className="font-bold text-amber-600 dark:text-amber-400">
                      [Pendent de Sincronització Offline]
                    </span>
                    <p className="text-on-surface dark:text-slate-300 truncate max-w-[200px]">
                      {item.payload?.text_observacions ||
                        "Incidència enregistrada"}
                    </p>
                  </div>
                  <Clock className="w-4 h-4 text-amber-500 shrink-0" />
                </div>
              ))}

              {historial.map((inc) => (
                <div
                  key={inc.id}
                  className="p-3 bg-surface-container-low dark:bg-slate-800/60 rounded-xl border border-outline-variant/30 dark:border-slate-700/60 flex items-center justify-between text-xs"
                >
                  <div className="space-y-0.5">
                    <span className="font-bold text-primary dark:text-slate-200">
                      {inc.ambit} - {inc.estat}
                    </span>
                    <p className="text-on-surface-variant dark:text-slate-400 truncate max-w-[200px]">
                      {inc.text_observacions || "Sense comentari"}
                    </p>
                  </div>
                  <span className="text-[10px] font-mono text-on-surface-variant">
                    {inc.created_at
                      ? new Date(inc.created_at).toLocaleDateString()
                      : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
