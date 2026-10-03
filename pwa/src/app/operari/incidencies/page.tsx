"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  PhoneCall,
  Mic,
  Camera,
  ArrowLeft,
  Send,
  AlertCircle,
  CheckCircle2,
  ShieldAlert,
  Clock,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { compressImageToWebP } from "@/lib/media";
import CameraInput from "@/components/CameraInput";

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
    
    // Offline queries
    if (typeof window !== "undefined") {
      try {
        const queue = await db.sync_queue.filter(i => i.action === 'REPORTAR_INCIDENCIA').toArray();
        setPendingOffline(queue);
      } catch (e) {
        console.error("Error reading offline queue:", e);
      }
    }
  };

  useEffect(() => {
    carregarHistorial();
  }, []);

  const handleFotoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      try {
        await compressImageToWebP(e.target.files[0]);
        setFotoPujada(true);
        setErrorValidacio(null);
      } catch {
        setErrorValidacio("Error en processar la imatge en viu.");
      }
    }
  };

  const handleSimularAudio = () => {
    setAudioGravat(!audioGravat);
    setErrorValidacio(null);
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

    const payload = {
      ambit: tipus,
      estat: "VERMELL",
      text_observacions: descripcio.trim() || (audioGravat ? "Nota de veu gravada en camp" : "Fotografia d'avaria aportada"),
      audio_path: audioGravat ? "/docs/audio/incidencia_live.webm" : null,
      foto_path: fotoPujada ? "/docs/fotos/incidencia_live.webp" : null,
    };

    try {
      await addToSyncQueue("REPORTAR_INCIDENCIA", payload);
      setEnviatExit(true);
      await carregarHistorial();
    } catch (err: any) {
      setErrorValidacio(err.message || "Error al notificar la incidència");
    } finally {
      setEnviant(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Barra de Navegació */}
      <header className="bg-slate-900 dark:bg-slate-950 text-white p-4 flex items-center justify-between border-b border-slate-800">
        <Link
          href="/operari/feines"
          className="flex items-center gap-1 text-xs text-slate-300 hover:text-white"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Tornar</span>
        </Link>
        <h1 className="text-sm font-bold uppercase tracking-wider text-white">
          Incidència de Camp (Spec 016)
        </h1>
        <div className="w-12"></div>
      </header>

      <div className="p-4 flex-1 flex flex-col gap-4 overflow-y-auto">
        {/* BOTÓ SOS 112 DIRECTE (Spec 016 RF-07) */}
        <a
          href="tel:112"
          className="w-full py-3 px-6 rounded-2xl bg-rose-600 hover:bg-rose-700 active:scale-98 text-white font-extrabold text-sm flex items-center justify-center gap-3 shadow-lg shadow-rose-600/30 transition-all uppercase tracking-wider shrink-0"
        >
          <PhoneCall className="w-4 h-4 animate-pulse" />
          <span>SOS EMERGÈNCIA (112)</span>
        </a>

        {enviatExit ? (
          <div className="p-6 bg-white dark:bg-slate-900 rounded-2xl border border-emerald-300 dark:border-emerald-800 text-center shadow-sm space-y-3">
            <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
              Incidència Notificada amb Èxit
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-xs mx-auto">
              S'ha registrat a la base de dades i notificat a la Torre de Control d'Enginyers.
            </p>
            <button
              onClick={() => {
                setEnviatExit(false);
                setDescripcio("");
                setAudioGravat(false);
                setFotoPujada(false);
              }}
              className="mt-2 px-4 py-2 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-xs font-bold rounded-xl"
            >
              Registrar una altra incidència
            </button>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4"
          >
            <div>
              <CameraInput captured={fotoPujada} label="Càmera en Viu" onCapture={(blob) => { setFotoPujada(true); setErrorValidacio(null); }} />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
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
                className="w-full p-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:outline-none focus:border-emerald-600 resize-none"
              />
            </div>

            {errorValidacio && (
              <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorValidacio}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={enviant}
              className="w-full py-3 rounded-xl bg-slate-900 dark:bg-slate-100 hover:bg-slate-800 dark:hover:bg-white text-white dark:text-slate-900 text-xs font-bold flex items-center justify-center gap-2 shadow disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
              <span>{enviant ? "Enviant incidència..." : "Notificar Incidència al Centre"}</span>
            </button>
          </form>
        )}

        {/* Historial d'incidències prèvies de l'operari */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
              Les Teves Incidències Recents
            </h3>
            <button
              onClick={carregarHistorial}
              className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingHistorial ? "animate-spin" : ""}`} />
            </button>
          </div>

          {loadingHistorial && historial.length === 0 && pendingOffline.length === 0 ? (
            <p className="text-xs text-slate-400 py-4 text-center">Carregant incidències...</p>
          ) : historial.length === 0 && pendingOffline.length === 0 ? (
            <div className="text-center py-6 text-slate-400">
              <CheckCircle2 className="w-8 h-8 mx-auto text-emerald-500/50 mb-1" />
              <p className="text-xs font-bold text-slate-600 dark:text-slate-400">Cap incidència activa</p>
              <p className="text-[10px] text-slate-400 mt-0.5">Estat Dia-0: Totes les feines estan operatives.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {pendingOffline.map((item) => (
                <div
                  key={`offline-${item.id}`}
                  className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 flex items-start justify-between"
                >
                  <div>
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300">
                      {item.payload.ambit}
                    </span>
                    <p className="text-xs font-medium text-slate-800 dark:text-slate-200 mt-1">
                      {item.payload.text_observacions}
                    </p>
                  </div>
                  <span className="text-[9px] font-mono text-amber-600 dark:text-amber-400">
                    PENDENT DE SYNC
                  </span>
                </div>
              ))}
              {historial.map((item) => (
                <div
                  key={item.id}
                  className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-start justify-between"
                >
                  <div>
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300">
                      {item.ambit}
                    </span>
                    <p className="text-xs font-medium text-slate-800 dark:text-slate-200 mt-1">
                      {item.text_observacions}
                    </p>
                  </div>
                  <span className="text-[9px] font-mono text-slate-400">
                    {item.estat}
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
