"use client";

import React, { useState } from "react";
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
} from "lucide-react";
import { CAMERA_LIVE_INPUT_PROPS, compressImageToWebP } from "@/lib/media";

export default function OperariIncidenciesPage() {
  const [descripcio, setDescripcio] = useState("");
  const [tipus, setTipus] = useState("AVARIA_VEHICLE");
  const [audioGravat, setAudioGravat] = useState(false);
  const [fotoPujada, setFotoPujada] = useState(false);
  const [enviant, setEnviant] = useState(false);
  const [enviatExit, setEnviatExit] = useState(false);
  const [errorValidacio, setErrorValidacio] = useState<string | null>(null);

  const handleFotoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      try {
        const compressed = await compressImageToWebP(e.target.files[0]);
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

  // Spec 016 RF-15: Vàlida si s'aporta almenys un sol canal (text, àudio o foto)
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!descripcio.trim() && !audioGravat && !fotoPujada) {
      setErrorValidacio(
        "Aporta almenys una font d'informació: nota d'àudio, fotografia o descripció."
      );
      return;
    }

    setEnviant(true);
    setTimeout(() => {
      setEnviant(false);
      setEnviatExit(true);
    }, 600);
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

      <div className="p-4 flex-1 flex flex-col gap-4">
        {/* BOTÓ SOS 112 DIRECTE (Spec 016 RF-07, Tasca 3.7) */}
        <a
          href="tel:112"
          className="w-full py-3.5 px-6 rounded-2xl bg-rose-600 hover:bg-rose-700 active:scale-98 text-white font-extrabold text-base flex items-center justify-center gap-3 shadow-lg shadow-rose-600/30 transition-all uppercase tracking-wider"
        >
          <PhoneCall className="w-5 h-5 animate-pulse" />
          <span>SOS EMERGÈNCIA (112)</span>
        </a>

        {enviatExit ? (
          <div className="p-6 bg-white dark:bg-slate-900 rounded-2xl border border-emerald-300 dark:border-emerald-800 text-center my-auto shadow-sm space-y-3">
            <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
              Incidència Notificada
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-xs mx-auto">
              S'ha derivat a la Torre de Control d'Enginyers i desat en memòria
              local per a sincronització asíncrona Hetzner.
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
              Registrar una altra
            </button>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="flex-1 flex flex-col justify-between bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm"
          >
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
                  Tipus de Contingència
                </label>
                <select
                  value={tipus}
                  onChange={(e) => setTipus(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-800 dark:text-slate-200 bg-white dark:bg-slate-800"
                >
                  <option value="AVARIA_VEHICLE">Avaria mecànica de vehicle / furgó</option>
                  <option value="MATERIAL_DEFECTUOS">Material defectuós o trencament d'eina</option>
                  <option value="ZONA_PERILLOSA">Obstacle / accés impedit a la finca</option>
                  <option value="EMERGENCIA">Altra incidència tècnica</option>
                </select>
              </div>

              {/* Botons Multimodals: Àudio i Foto en Viu Antifraude */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                  Entrada Multimodal (Àudio, Foto o Text)
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={handleSimularAudio}
                    className={`py-3 px-3 rounded-xl border flex flex-col items-center justify-center gap-1.5 transition-colors ${
                      audioGravat
                        ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 font-bold"
                        : "border-slate-300 dark:border-slate-700 hover:border-slate-400 text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    <Mic className="w-5 h-5" />
                    <span className="text-[11px]">
                      {audioGravat ? "Àudio Gravat (OK)" : "Gravar Nota de Veu"}
                    </span>
                  </button>

                  <label
                    className={`py-3 px-3 rounded-xl border flex flex-col items-center justify-center gap-1.5 transition-colors cursor-pointer ${
                      fotoPujada
                        ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 font-bold"
                        : "border-slate-300 dark:border-slate-700 hover:border-slate-400 text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    <Camera className="w-5 h-5" />
                    <span className="text-[11px]">
                      {fotoPujada ? "Foto Capturada (OK)" : "Foto en Viu"}
                    </span>
                    {/* CÀMERA DIRECTA AMB ATRIBUTS ANTIFRAUDE (Spec 020 RF-17) */}
                    <input
                      {...CAMERA_LIVE_INPUT_PROPS}
                      onChange={handleFotoChange}
                      className="hidden"
                    />
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
                  Observacions Ràpides (Opcional si hi ha àudio/foto)
                </label>
                <textarea
                  rows={3}
                  value={descripcio}
                  onChange={(e) => {
                    setDescripcio(e.target.value);
                    setErrorValidacio(null);
                  }}
                  placeholder="Detalls curts de la incidència..."
                  className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-800 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:border-slate-800"
                />
              </div>

              {errorValidacio && (
                <div className="flex items-center gap-1.5 text-xs text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40 p-2.5 rounded-xl border border-rose-200 dark:border-rose-900">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{errorValidacio}</span>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={enviant}
              className="w-full mt-4 py-3 rounded-xl bg-slate-900 dark:bg-slate-100 dark:text-slate-900 hover:bg-slate-800 active:scale-98 text-white text-xs font-bold flex items-center justify-center gap-2 shadow"
            >
              <Send className="w-4 h-4" />
              <span>{enviant ? "Notificant..." : "Transmetre Incidència"}</span>
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
