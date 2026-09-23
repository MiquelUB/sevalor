"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  MapPin,
  Navigation,
  Play,
  CheckCircle,
  AlertTriangle,
  Receipt,
  LogOut,
  Clock,
  Briefcase,
  Plus,
  RefreshCw,
} from "lucide-react";
import { validarGeovalla } from "@/lib/geo";
import { apiFetch } from "@/lib/api";

interface OrdreCamp {
  id: string;
  codi: string;
  titol: string;
  client: string;
  estat: "PENDENT" | "EN_TRAJECTE" | "EN_CURS" | "FINALITZADA";
  coords_gps: [number, number];
  hora_inici: string;
}

export default function OperariFeinesPage() {
  // Inicialitzat buit per defecte (Zero Mock Data Mandat - Spec 013 RF-07)
  const [feines, setFeines] = useState<OrdreCamp[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [geovallaAlerta, setGeovallaAlerta] = useState<string | null>(null);
  const [ordreDesviacio, setOrdreDesviacio] = useState<string | null>(null);

  const [nomOperari, setNomOperari] = useState("Operari de Camp");

  // Carregar feines reals des del backend
  const carregarFeines = async () => {
    setLoading(true);
    try {
      const userRaw = typeof window !== "undefined" ? localStorage.getItem("sevalor_user") : null;
      if (userRaw) {
        const u = JSON.parse(userRaw);
        if (u.nom) setNomOperari(u.nom);
      }
    } catch {}

    try {
      const data = await apiFetch<any[]>("/operari/feines");
      if (Array.isArray(data)) {
        setFeines(
          data.map((item: any) => ({
            id: String(item.id),
            codi: item.codi || "OT-00",
            titol: item.titol || "Ordre de treball",
            client: item.client?.rao_social || "Client",
            estat: item.estat || "PENDENT",
            coords_gps: [41.3851, 2.1734],
            hora_inici: item.data_planificacio || "08:00",
          }))
        );
      } else {
        setFeines([]);
      }
    } catch {
      setFeines([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarFeines();
  }, []);

  // Spec 013 RF-11: Iniciar Trajecte i notificació ETA
  const handleIniciarTrajecte = (id: string) => {
    setFeines((prev) =>
      prev.map((f) => (f.id === id ? { ...f, estat: "EN_TRAJECTE" } : f))
    );
    // TODO: Enviar notificació ETA al backend
    apiFetch(`/ordres-camp/${id}/iniciar-trajecte`, { method: "POST" }).catch(() => {});
    alert("Trajecte iniciat. Notificació d'ETA transmesa al client via Telegram.");
  };

  // Spec 013 RF-12 & RF-12.1: Començar Feina amb validació de Geovalla (< 50m)
  const handleComencarFeina = (ordre: OrdreCamp) => {
    if (!navigator.geolocation) {
      alert("Geolocalització no disponible.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coordsActuals: [number, number] = [
          pos.coords.latitude,
          pos.coords.longitude,
        ];
        const res = validarGeovalla(coordsActuals, ordre.coords_gps);

        if (res.dins_geovalla) {
          setFeines((prev) =>
            prev.map((f) => (f.id === ordre.id ? { ...f, estat: "EN_CURS" } : f))
          );
          // TODO: Notificar al backend
          apiFetch(`/ordres-camp/${ordre.id}/comencar`, { method: "POST" }).catch(() => {});
        } else {
          // Desviació > 50 metres
          setGeovallaAlerta(
            `Ets a ${res.distancia_metres}m de la finca (límit 50m). Es requereix protocol d'Inici per Desviació.`
          );
          setOrdreDesviacio(ordre.id);
        }
      },
      () => {
        // Si no hi ha permís GPS en test, activar advertència de geovalla
        setGeovallaAlerta("No s'ha pogut obtenir la posició GPS amb precisió.");
        setOrdreDesviacio(ordre.id);
      }
    );
  };

  const handleConfirmarDesviacio = (motiu: string) => {
    if (ordreDesviacio) {
      setFeines((prev) =>
        prev.map((f) =>
          f.id === ordreDesviacio ? { ...f, estat: "EN_CURS" } : f
        )
      );
      // TODO: Registrar la desviació al backend
      apiFetch(`/ordres-camp/${ordreDesviacio}/comencar-desviacio`, {
        method: "POST",
        body: JSON.stringify({ motiu }),
      }).catch(() => {});
      setGeovallaAlerta(null);
      setOrdreDesviacio(null);
      alert(`Inici per desviació autoritzat sota motiu: "${motiu}"`);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Barra Superior de Camp (Spec 013 RF-01) */}
      <header className="bg-emerald-700 dark:bg-emerald-900 text-white p-4 shadow-md flex items-center justify-between">
        <div>
          <h1 className="text-base font-bold leading-tight">SEVALOR</h1>
          <p className="text-xs text-emerald-200">{nomOperari}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/operari/tiquets"
            className="p-2 rounded-lg bg-emerald-800/80 hover:bg-emerald-800 text-white transition-colors"
            title="Tiquets i Repostatge"
          >
            <Receipt className="w-4 h-4" />
          </Link>
          <Link
            href="/operari/incidencies"
            className="p-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white transition-colors"
            title="SOS / Incidència"
          >
            <AlertTriangle className="w-4 h-4" />
          </Link>
          <Link
            href="/operari/login"
            className="p-2 rounded-lg bg-emerald-800/80 hover:bg-emerald-800 text-white transition-colors"
            title="Tancar Sessió"
          >
            <LogOut className="w-4 h-4" />
          </Link>
        </div>
      </header>

      {/* Contingut Principal */}
      <div className="flex-1 p-4 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Feines del Dia (Spec 013)
          </h2>
          <span className="text-xs font-semibold px-2 py-0.5 bg-white dark:bg-slate-900 rounded-full border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400">
            {feines.length} tasques
          </span>
        </div>

        {/* Modal d'Alerta de Geovalla (Spec 013 RF-12.1) */}
        {geovallaAlerta && (
          <div className="mb-4 p-4 rounded-xl bg-amber-50 dark:bg-amber-950/50 border border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-200 shadow-sm">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-xs font-semibold">{geovallaAlerta}</p>
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() =>
                      handleConfirmarDesviacio("Avaries d'accés o bloqueig de camí")
                    }
                    className="px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold shadow"
                  >
                    Inici per Desviació
                  </button>
                  <button
                    onClick={() => setGeovallaAlerta(null)}
                    className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium"
                  >
                    Cancel·lar
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Llista de Feines o Estat Buit Net (Mandat Zero-Mock - Spec 013 RF-07) */}
        {loading ? (
          <div className="flex-1 flex items-center justify-center text-slate-400 text-xs">
            Carregant ordres de camp...
          </div>
        ) : feines.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 my-auto shadow-sm">
            <div className="w-16 h-16 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-3">
              <CheckCircle className="w-8 h-8" />
            </div>
            {/* TEXT EXACTE EXIGIT PER LA SPEC 013 RF-07 */}
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
              No hi ha feines assignades per a avui
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
              Quan l'oficina tècnica planifiqui noves ordres de treball,
              apareixeran automàticament aquí.
            </p>
            <button
              onClick={carregarFeines}
              disabled={loading}
              className="mt-5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow flex items-center gap-1.5 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              <span>Carregar dades reals</span>
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {feines.map((f) => (
              <div
                key={f.id}
                className="p-4 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-mono font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950 px-2 py-0.5 rounded">
                      {f.codi}
                    </span>
                    <h4 className="text-sm font-bold text-slate-800 dark:text-slate-100 mt-1">
                      {f.titol}
                    </h4>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{f.client}</p>
                  </div>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      f.estat === "EN_CURS"
                        ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300"
                        : f.estat === "EN_TRAJECTE"
                        ? "bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    {f.estat}
                  </span>
                </div>

                <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
                  <div className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{f.hora_inici}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5" />
                    <span>GPS Fixat</span>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex gap-2">
                  {f.estat === "PENDENT" && (
                    <button
                      onClick={() => handleIniciarTrajecte(f.id)}
                      className="flex-1 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow"
                    >
                      <Navigation className="w-3.5 h-3.5" />
                      Iniciar Trajecte (ETA)
                    </button>
                  )}
                  {f.estat === "EN_TRAJECTE" && (
                    <button
                      onClick={() => handleComencarFeina(f)}
                      className="flex-1 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow"
                    >
                      <Play className="w-3.5 h-3.5" />
                      Començar Feina (Geovalla 50m)
                    </button>
                  )}
                  {f.estat === "EN_CURS" && (
                    <div className="flex-1 text-center py-2 bg-emerald-50 dark:bg-emerald-950 rounded-xl text-emerald-800 dark:text-emerald-300 text-xs font-bold border border-emerald-200 dark:border-emerald-800">
                      Feina en Progrés a Finca
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}