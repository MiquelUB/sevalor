"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Play, Square, MapPin, Clock, Truck, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";
import { localDB } from "@/lib/db";
import { getAuthToken } from "@/lib/api";
import MorningBriefing from "./MorningBriefing";
import EveningCheckoutModal from "./EveningCheckoutModal";

export interface JornadaActivaState {
  id: string;
  data_inici: string;
  lat_inici: number;
  lon_inici: number;
  vehicle_id?: string | null;
  km_inicials?: number | null;
}

const STORAGE_KEY = "sevalor_jornada_activa";

export default function ControlHorariBar() {
  const [jornada, setJornada] = useState<JornadaActivaState | null>(null);
  const [elapsed, setElapsed] = useState<string>("00:00:00");
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(true);

  // Modals de Torn
  const [isMorningOpen, setIsMorningOpen] = useState(false);
  const [isEveningOpen, setIsEveningOpen] = useState(false);

  const loadJornadaState = useCallback(async () => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        setJornada(JSON.parse(raw));
        return;
      }
      // Si no hi ha a localStorage, comprovar al servidor si hi ha torn obert
      if (navigator.onLine) {
        const token = getAuthToken();
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch("/api/v1/operari/jornada/activa", {
          headers,
          credentials: "include",
        });
        if (res.ok) {
          const act = await res.json();
          if (act?.id && act.estat === "EN_CURS") {
            let lat = 0.0;
            let lon = 0.0;
            if (act.geolocalitzacio_inici && act.geolocalitzacio_inici.includes(",")) {
              const parts = act.geolocalitzacio_inici.split(",");
              lat = parseFloat(parts[0]) || 0.0;
              lon = parseFloat(parts[1]) || 0.0;
            }
            const jState: JornadaActivaState = {
              id: act.id,
              data_inici: act.hora_inici || new Date().toISOString(),
              lat_inici: lat,
              lon_inici: lon,
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(jState));
            setJornada(jState);
            return;
          }
        }
      }
      setJornada(null);
    } catch {
      setJornada(null);
    }
  }, []);

  useEffect(() => {
    loadJornadaState();
    const handleStorageChange = () => loadJornadaState();
    window.addEventListener("sevalor-jornada-updated", handleStorageChange);
    return () => window.removeEventListener("sevalor-jornada-updated", handleStorageChange);
  }, [loadJornadaState]);

  // Cronòmetre en viu
  useEffect(() => {
    if (!jornada?.data_inici) {
      setElapsed("00:00:00");
      return;
    }
    const updateTimer = () => {
      const startMs = new Date(jornada.data_inici).getTime();
      const diffSec = Math.max(0, Math.floor((Date.now() - startMs) / 1000));
      const hrs = String(Math.floor(diffSec / 3600)).padStart(2, "0");
      const mins = String(Math.floor((diffSec % 3600) / 60)).padStart(2, "0");
      const secs = String(diffSec % 60).padStart(2, "0");
      setElapsed(`${hrs}:${mins}:${secs}`);
    };
    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [jornada]);

  const obtenirPosicioGPS = (): Promise<{ latitud: number; longitud: number }> => {
    return new Promise((resolve, reject) => {
      if (typeof navigator === "undefined" || !navigator.geolocation) {
        reject(new Error("El dispositiu no suporta geolocalització GPS."));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ latitud: pos.coords.latitude, longitud: pos.coords.longitude }),
        () => reject(new Error("Permís GPS denegat o senyal insuficient.")),
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    });
  };

  const handleIniciarJornada = () => {
    setIsMorningOpen(true);
  };

  const handleFinalitzarJornada = () => {
    setIsEveningOpen(true);
  };

  return (
    <>
      <div className={`bg-surface-container-low dark:bg-slate-900 border-b border-outline-variant/25 dark:border-slate-800 px-4 ${jornada && isCollapsed ? "py-1.5" : "py-2.5"} text-on-surface dark:text-slate-100 transition-all duration-200`}>
        <div className="flex items-center justify-between gap-2 max-w-md mx-auto">
          {jornada ? (
            isCollapsed ? (
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-secondary animate-pulse shrink-0" />
                  <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-on-surface dark:text-slate-100">
                    <Clock className="w-3.5 h-3.5 text-secondary shrink-0" />
                    <span data-testid="jornada-timer">{elapsed}</span>
                  </div>
                  {jornada.vehicle_id && (
                    <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-secondary-container text-on-secondary-container">
                      Flota OK
                    </span>
                  )}
                  <span className="text-[10px] text-on-surface-variant dark:text-slate-400 font-medium hidden sm:inline">
                    Torn en curs
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    data-testid="btn-finalitzar-jornada"
                    disabled={loading}
                    onClick={handleFinalitzarJornada}
                    className="min-h-[32px] px-2.5 py-1 rounded-md bg-error text-on-error font-bold text-[10px] uppercase tracking-wider flex items-center gap-1 active:scale-95 transition-transform disabled:opacity-50 shadow-sm"
                  >
                    <Square className="w-2.5 h-2.5 fill-current" />
                    <span>Tancar Torn</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsCollapsed(false)}
                    title="Mostrar detalls del torn"
                    className="p-1 rounded text-on-surface-variant hover:text-on-surface"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="w-2.5 h-2.5 rounded-full bg-secondary animate-pulse shrink-0" />
                  <div className="truncate">
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-secondary shrink-0" />
                      <span
                        data-testid="jornada-timer"
                        className="font-mono font-bold text-sm tracking-tight text-on-surface dark:text-slate-100"
                      >
                        {elapsed}
                      </span>
                      {jornada.vehicle_id && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-secondary-container text-on-secondary-container">
                          <Truck className="w-3 h-3" /> Flota OK
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-on-surface-variant dark:text-slate-400 flex items-center gap-1 truncate">
                      <MapPin className="w-3 h-3 text-primary shrink-0" />
                      Torn actiu ({jornada.lat_inici.toFixed(4)}, {jornada.lon_inici.toFixed(4)})
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    data-testid="btn-finalitzar-jornada"
                    disabled={loading}
                    onClick={handleFinalitzarJornada}
                    className="min-h-[38px] px-3 py-1.5 rounded-lg bg-error text-on-error font-bold text-xs uppercase tracking-wider flex items-center gap-1.5 active:scale-95 transition-transform disabled:opacity-50 shrink-0 shadow-sm"
                  >
                    <Square className="w-3.5 h-3.5 fill-current" />
                    {loading ? "GPS..." : "Tancar Torn"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsCollapsed(true)}
                    title="Amagar per no ocupar espai a la pantalla"
                    className="p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface flex items-center gap-0.5 text-[10px] font-bold"
                  >
                    <ChevronUp className="w-3.5 h-3.5" />
                    <span>Amagar</span>
                  </button>
                </div>
              </>
            )
          ) : (
            <>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-outline shrink-0" />
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-on-surface dark:text-slate-100">
                    Torn Sense Iniciar
                  </p>
                  <p className="text-[11px] text-on-surface-variant dark:text-slate-400">
                    Fitxatge GPS obligatori (FR-004)
                  </p>
                </div>
              </div>

              <button
                type="button"
                data-testid="btn-iniciar-jornada"
                disabled={loading}
                onClick={handleIniciarJornada}
                className="min-h-[42px] px-4 py-2 rounded-lg bg-primary text-on-primary font-bold text-xs uppercase tracking-wider flex items-center gap-1.5 active:scale-95 transition-transform disabled:opacity-50 shrink-0 shadow-sm"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                {loading ? "Capturant GPS..." : "Iniciar Jornada"}
              </button>
            </>
          )}
        </div>

        {errorMsg && (
          <div
            data-testid="jornada-error"
            className="mt-2 max-w-md mx-auto flex items-center gap-1.5 text-xs font-semibold text-error bg-error-container/30 px-2.5 py-1.5 rounded"
          >
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}
      </div>

      {/* Assistent Matinal (US1) */}
      <MorningBriefing
        isOpen={isMorningOpen}
        onClose={() => setIsMorningOpen(false)}
        onCompleted={() => {
          loadJornadaState();
          setIsMorningOpen(false);
        }}
      />

      {/* Assistent de Tancament de Torn (US3 / FR-009) */}
      <EveningCheckoutModal
        jornada={jornada}
        isOpen={isEveningOpen}
        onClose={() => setIsEveningOpen(false)}
        onFinished={() => {
          loadJornadaState();
          setIsEveningOpen(false);
        }}
      />
    </>
  );
}
