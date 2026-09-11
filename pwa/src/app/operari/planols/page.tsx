"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Layers,
  Plus,
  Lock,
  Eye,
  EyeOff,
  MapPin,
  Compass,
  RefreshCw,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface CapaAnotacio {
  id: string;
  nom: string;
  es_tancada: boolean;
  visible: boolean;
  pins: Array<{ x: number; y: number; etiqueta: string }>;
}

export default function OperariPlanolsPage() {
  // Inicialitzat segons mandat Zero Mock Data (Spec 017 RF-03 / DoD)
  const [capes, setCapes] = useState<CapaAnotacio[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const [capaActivaId, setCapaActivaId] = useState<string>("");
  const [mostrarDialegCapaTancada, setMostrarDialegCapaTancada] = useState<boolean>(false);
  const [pendentClickCoords, setPendentClickCoords] = useState<{ x: number; y: number } | null>(null);

  // Carregar capes reals des del backend
  const carregarPlanol = async () => {
    setLoading(true);
    try {
      const data = await apiFetch("/planols/operari");
      const capesData = Array.isArray(data) ? data : [];
      // Assegurar visibilitat per defecte
      const capesNormalitzades = capesData.map((c: any) => ({
        ...c,
        visible: c.visible ?? true,
        pins: c.pins ?? [],
      }));
      setCapes(capesNormalitzades);
      if (capesNormalitzades.length > 0 && !capaActivaId) {
        setCapaActivaId(capesNormalitzades[0].id);
      }
    } catch {
      setCapes([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarPlanol();
  }, []);

  // Commutar visibilitat de la capa (Spec 017 RF-11)
  const toggleVisibilitat = (id: string) => {
    setCapes((prev) =>
      prev.map((c) => (c.id === id ? { ...c, visible: !c.visible } : c))
    );
  };

  // Clic sobre el plànol base
  const handlePlanolClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 100);
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 100);

    const capaActual = capes.find((c) => c.id === capaActivaId);

    // Spec 017 RF-13.1: Si la capa és tancada, bloquejar i obrir el diàleg
    if (capaActual?.es_tancada) {
      setPendentClickCoords({ x, y });
      setMostrarDialegCapaTancada(true);
      return;
    }

    // Afegir pin a la capa activa de forma no destructiva
    afegirPinACapa(capaActivaId, x, y);
  };

  const afegirPinACapa = (capaId: string, x: number, y: number) => {
    setCapes((prev) =>
      prev.map((c) => {
        if (c.id === capaId) {
          return {
            ...c,
            pins: [...c.pins, { x, y, etiqueta: `Anotació #${c.pins.length + 1}` }],
          };
        }
        return c;
      })
    );
    // TODO: Sincronitzar amb backend
  };

  // Creació de nova capa davant d'obra tancada (Spec 017 RF-13.1)
  const handleCrearNovaCapa = async () => {
    const novaCapa: CapaAnotacio = {
      id: `capa-${Date.now()}`,
      nom: `Addenda As-Built (${new Date().toLocaleDateString("ca-ES")})`,
      es_tancada: false,
      visible: true,
      pins: pendentClickCoords
        ? [{ ...pendentClickCoords, etiqueta: "Nova Anotació" }]
        : [],
    };

    setCapes((prev) => [...prev, novaCapa]);
    setCapaActivaId(novaCapa.id);
    setMostrarDialegCapaTancada(false);
    setPendentClickCoords(null);

    // TODO: Persistir al backend
    try {
      await apiFetch("/planols/capes", {
        method: "POST",
        body: JSON.stringify(novaCapa),
      });
    } catch {}
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
          Visor As-Built (Spec 017)
        </h1>
        <button
          onClick={carregarPlanol}
          disabled={loading}
          className="text-[10px] font-mono font-semibold text-slate-400 hover:text-white disabled:opacity-50"
          title="Recarregar plànols des del backend"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      {/* ESTAT BUIT REAL ZERO-MOCK (Spec 017 Context & RF-03) */}
      {!loading && capes.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 m-4 shadow-sm">
          <div className="w-16 h-16 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-3">
            <Compass className="w-8 h-8" />
          </div>
          {/* TEXT EXACTE EXIGIT PER LA SPEC 017 */}
          <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
            No tens cap plànol o xarxa tècnica assignada avui
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
            Només es descarreguen els plànols vinculats a les tasques que tens assignades per a la jornada.
          </p>
          <button
            onClick={carregarPlanol}
            disabled={loading}
            className="mt-5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow transition-all disabled:opacity-50 flex items-center gap-1.5"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            <span>Carregar dades reals</span>
          </button>
        </div>
      ) : loading && capes.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-slate-400 text-xs">
          Carregant plànols...
        </div>
      ) : (
        <div className="flex-1 flex flex-col">
          {/* Selector de Capes Dinàmic (Spec 017 RF-11) */}
          <div className="p-3 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2 overflow-x-auto text-xs">
            <Layers className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            {capes.map((capa) => (
              <div
                key={capa.id}
                onClick={() => setCapaActivaId(capa.id)}
                className={`px-3 py-1.5 rounded-xl flex items-center gap-2 cursor-pointer transition-colors shrink-0 ${
                  capaActivaId === capa.id
                    ? "bg-emerald-600 text-white font-bold shadow"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
                }`}
              >
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleVisibilitat(capa.id);
                  }}
                  className="hover:opacity-80"
                >
                  {capa.visible ? (
                    <Eye className="w-3.5 h-3.5" />
                  ) : (
                    <EyeOff className="w-3.5 h-3.5 opacity-40" />
                  )}
                </button>
                <span>{capa.nom}</span>
                {capa.es_tancada && <Lock className="w-3 h-3 text-amber-300" />}
              </div>
            ))}
          </div>

          {/* Àrea del Plànol Cartogràfic */}
          <div className="flex-1 relative p-4 flex items-center justify-center overflow-hidden">
            <div
              onClick={handlePlanolClick}
              className="relative w-full max-w-sm aspect-[4/5] bg-slate-100 dark:bg-slate-800 rounded-2xl border-2 border-slate-300 dark:border-slate-700 shadow-inner overflow-hidden cursor-crosshair"
            >
              {/* Fons del Plànol Mestre Simulat */}
              <div className="absolute inset-0 bg-grid-pattern opacity-10 pointer-events-none"></div>
              <div className="absolute inset-4 border border-dashed border-slate-400 dark:border-slate-600 rounded-xl pointer-events-none flex items-center justify-center">
                <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                  Plànol Mestre de Finca (Inalterable)
                </span>
              </div>

              {/* Renderització de Capes Vectorials Independents */}
              {capes
                .filter((c) => c.visible)
                .map((c) =>
                  c.pins.map((pin, idx) => (
                    <div
                      key={`${c.id}-${idx}`}
                      style={{ left: `${pin.x}%`, top: `${pin.y}%` }}
                      className={`absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center pointer-events-none ${
                        c.es_tancada ? "text-amber-500" : "text-emerald-600 dark:text-emerald-400"
                      }`}
                    >
                      <MapPin className="w-6 h-6 drop-shadow-md fill-current" />
                      <span className="text-[9px] font-mono font-bold bg-slate-900/90 px-1.5 py-0.5 rounded text-white border border-slate-700 shadow">
                        {pin.etiqueta}
                      </span>
                    </div>
                  ))
                )}
            </div>
          </div>

          {/* POP-UP DIÀLEG D'ESMENA SOBRE OBRES TANCADES (Spec 017 RF-13.1) */}
          {mostrarDialegCapaTancada && (
            <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50 animate-fade-in">
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl max-w-xs w-full text-center shadow-2xl space-y-4">
                <div className="w-12 h-12 rounded-full bg-amber-500/20 text-amber-500 flex items-center justify-center mx-auto border border-amber-500/30">
                  <Lock className="w-6 h-6" />
                </div>
                {/* TEXT EXACTE EXIGIT PER LA SPEC 017 */}
                <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                  Capa tancada, vols crear una capa nova?
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Aquesta ordre de treball està tancada i facturada. Per a respectar
                  la inalterabilitat del SIF, cal crear una capa d'addenda activa.
                </p>
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={handleCrearNovaCapa}
                    className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl flex items-center justify-center gap-1 shadow"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Crear Capa Nova</span>
                  </button>
                  <button
                    onClick={() => {
                      setMostrarDialegCapaTancada(false);
                      setPendentClickCoords(null);
                    }}
                    className="px-3 py-2.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold rounded-xl"
                  >
                    Cancel·lar
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}