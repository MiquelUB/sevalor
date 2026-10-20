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
import { addToSyncQueue } from "@/lib/offline/sync";

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
  const [zoom, setZoom] = useState<number>(1);

  const [capaActivaId, setCapaActivaId] = useState<string>("");
  const [mostrarDialegCapaTancada, setMostrarDialegCapaTancada] =
    useState<boolean>(false);
  const [pendentClickCoords, setPendentClickCoords] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const [errorConnexio, setErrorConnexio] = useState<{
    code?: string;
    message: string;
  } | null>(null);
  const [refArxiuExtern, setRefArxiuExtern] = useState<string>("");
  const [consultantArxiu, setConsultantArxiu] = useState<boolean>(false);

  // Carregar capes reals des del backend (buffer diari de feines d'avui)
  const carregarPlanol = async () => {
    setLoading(true);
    setErrorConnexio(null);
    try {
      const data = await apiFetch("/operari/planols");
      const capesData = Array.isArray(data) ? data : [];
      const capesNormalitzades = capesData.map((c: any) => ({
        ...c,
        visible: c.visible ?? true,
        pins: c.pins ?? [],
      }));
      setCapes(capesNormalitzades);
      if (capesNormalitzades.length > 0 && !capaActivaId) {
        setCapaActivaId(capesNormalitzades[0].id);
      }
    } catch (err: any) {
      setCapes([]);
      if (
        err?.code === "SENSE_COBERTURA_MOBIL" ||
        err?.code === "NODE_EMPRESA_OFFLINE" ||
        err?.code === "DB_UNAVAILABLE"
      ) {
        setErrorConnexio({
          code: err.code,
          message: err.message,
        });
      }
    } finally {
      setLoading(false);
    }
  };

  // Consultar documentació extra (ex. plànol de caldera no inclòs a l'OT d'avui) al disc de l'empresa
  const handleConsultarArxiuExtern = async () => {
    if (!refArxiuExtern.trim()) return;
    setConsultantArxiu(true);
    setErrorConnexio(null);
    try {
      await apiFetch(
        `/operari/planols/arxiu-extern?referencia=${encodeURIComponent(
          refArxiuExtern.trim()
        )}`
      );
    } catch (err: any) {
      setErrorConnexio({
        code: err?.code || "NODE_EMPRESA_OFFLINE",
        message:
          err?.message ||
          "🖥️ Ordinador central de l'empresa apagat: Aquest plànol extra viu al disc dur de l'oficina i ara mateix està apagat o sense internet.",
      });
    } finally {
      setConsultantArxiu(false);
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

    afegirPinACapa(capaActivaId, x, y);
  };

  const afegirPinACapa = (capaId: string, x: number, y: number) => {
    setCapes((prev) =>
      prev.map((c) => {
        if (c.id === capaId) {
          return {
            ...c,
            pins: [
              ...c.pins,
              { x, y, etiqueta: `Anotació #${c.pins.length + 1}` },
            ],
          };
        }
        return c;
      })
    );
    const planolId =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("planol")
        : null;

    if (planolId) {
      addToSyncQueue("POST_PLANOL_PIN", {
        planol_id: planolId,
        capa_id: capaId,
        pin: {
          x,
          y,
          etiqueta: `Anotació #${
            (capes.find((c) => c.id === capaId)?.pins.length || 0) + 1
          }`,
        },
      }).catch(console.error);
    }
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

    const planolId =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("planol")
        : null;
    if (!planolId) {
      alert(
        "No s'ha pogut desar la capa: obre el visor des d'un plànol concret (falta ?planol=<id>)."
      );
      return;
    }
    try {
      await addToSyncQueue("POST_PLANOL_CAPA", {
        planol_id: planolId,
        capa: novaCapa,
      });
    } catch (e: any) {
      alert(e?.message || "Error desant la capa al servidor");
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-surface dark:bg-slate-950 text-on-surface dark:text-slate-100 transition-colors">
      {/* Barra de Navegació Stitch Screen 75a27334535b491fa5ffc622182171cf */}
      <header className="bg-surface-container-lowest dark:bg-slate-900 text-primary dark:text-white p-4 flex items-center justify-between border-b border-outline-variant/25 dark:border-slate-800">
        <Link
          href="/operari/feines"
          className="flex items-center gap-1.5 text-xs font-bold text-primary dark:text-slate-300 hover:opacity-80"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Tornar</span>
        </Link>
        <h1 className="text-sm font-extrabold uppercase tracking-wider text-primary dark:text-white">
          Visor As-Built (Spec 017)
        </h1>
        <button
          onClick={carregarPlanol}
          disabled={loading}
          className="w-8 h-8 rounded-lg bg-surface-container-low dark:bg-slate-800 flex items-center justify-center text-primary dark:text-slate-300 hover:bg-surface-container disabled:opacity-50"
          title="Recarregar plànols des del backend"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      {/* AVÍS CLAR DIFERENCIAT: COBERTURA MÒBIL vs. ORDINADOR D'EMPRESA APAGAT vs. BD */}
      {errorConnexio && (
        <div
          className={`mx-4 mt-3 p-3.5 rounded-xl border text-xs font-medium space-y-1 shadow-sm ${
            errorConnexio.code === "SENSE_COBERTURA_MOBIL"
              ? "bg-amber-50 dark:bg-amber-950/70 border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-200"
              : errorConnexio.code === "NODE_EMPRESA_OFFLINE"
              ? "bg-rose-50 dark:bg-rose-950/70 border-rose-300 dark:border-rose-800 text-rose-900 dark:text-rose-200"
              : "bg-blue-50 dark:bg-blue-950/70 border-blue-300 dark:border-blue-800 text-blue-900 dark:text-blue-200"
          }`}
        >
          <div className="font-extrabold uppercase tracking-wider text-[11px]">
            {errorConnexio.code === "SENSE_COBERTURA_MOBIL"
              ? "📶 Sense Cobertura Mòbil al Telèfon"
              : errorConnexio.code === "NODE_EMPRESA_OFFLINE"
              ? "🖥️ Ordinador Central de l'Empresa Apagat"
              : "⚠️ Base de Dades Temporalment No Disponible"}
          </div>
          <p className="leading-relaxed">{errorConnexio.message}</p>
        </div>
      )}

      {/* CERCA DE DOCUMENTACIÓ EXTRA AL DISC DE L'EMPRESA (ARXIU MESTRE) */}
      <div className="mx-4 mt-3 p-3 rounded-xl bg-surface-container-low dark:bg-slate-900 border border-outline-variant/30 dark:border-slate-800 flex flex-col sm:flex-row items-stretch sm:items-center gap-2 text-xs">
        <input
          type="text"
          value={refArxiuExtern}
          onChange={(e) => setRefArxiuExtern(e.target.value)}
          placeholder="Plànol extra fora de l'OT d'avui (ex: caldera-model-x)..."
          className="flex-1 px-3 py-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs"
        />
        <button
          type="button"
          onClick={handleConsultarArxiuExtern}
          disabled={consultantArxiu || !refArxiuExtern.trim()}
          className="px-3.5 py-2 rounded-lg bg-primary text-white font-bold text-xs disabled:opacity-50 shrink-0"
        >
          {consultantArxiu ? "Connectant a l'oficina..." : "Consultar Disc Empresa"}
        </button>
      </div>

      {/* ESTAT BUIT REAL ZERO-MOCK (Spec 017 Context & RF-03) */}
      {!loading && capes.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-surface-container-lowest dark:bg-slate-900 rounded-2xl border-2 border-dashed border-outline-variant/40 dark:border-slate-800 m-4 shadow-sm">
          <div className="w-16 h-16 rounded-2xl bg-secondary-container/10 text-secondary flex items-center justify-center mb-3">
            <Compass className="w-8 h-8" />
          </div>
          {/* TEXT EXACTE EXIGIT PER LA SPEC 017 */}
          <h3 className="text-base font-extrabold text-primary dark:text-slate-100">
            No tens cap plànol o xarxa tècnica assignada avui
          </h3>
          <p className="text-xs text-on-surface-variant dark:text-slate-400 mt-1 max-w-xs">
            Només es descarreguen els plànols vinculats a les tasques que tens assignades per a la jornada.
          </p>
          <button
            onClick={carregarPlanol}
            disabled={loading}
            className="mt-5 px-5 py-2.5 rounded-xl bg-secondary-container hover:brightness-110 text-white text-xs font-bold shadow-md transition-all disabled:opacity-50 flex items-center gap-1.5"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            <span>Carregar dades reals</span>
          </button>
        </div>
      ) : loading && capes.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-on-surface-variant text-xs font-bold uppercase tracking-wider">
          Carregant plànols...
        </div>
      ) : (
        <div className="flex-1 flex flex-col">
          {/* Selector de Capes Dinàmic (Spec 017 RF-11) */}
          <div className="p-3 bg-surface-container-lowest dark:bg-slate-900 border-b border-outline-variant/25 dark:border-slate-800 flex items-center gap-2 overflow-x-auto text-xs">
            <Layers className="w-4 h-4 text-secondary shrink-0" />
            {capes.map((capa) => (
              <div
                key={capa.id}
                onClick={() => setCapaActivaId(capa.id)}
                className={`px-3 py-1.5 rounded-xl flex items-center gap-2 cursor-pointer transition-colors shrink-0 ${
                  capaActivaId === capa.id
                    ? "bg-secondary-container text-white font-bold shadow-sm"
                    : "bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-slate-300 hover:bg-surface-container"
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

          {/* Àrea del Plànol Cartogràfic Stitch Interactive Canvas */}
          <div className="flex-1 relative p-4 flex items-center justify-center overflow-hidden bg-slate-900">
            {/* Floating GPS Badge */}
            <div className="absolute top-6 left-6 z-20 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-950/80 backdrop-blur-md border border-white/15 text-[10px] font-mono text-white">
              <span className="w-2 h-2 rounded-full bg-secondary-container animate-ping" />
              <span>GIS AS-BUILT ACTIU</span>
            </div>

            {/* Floating Zoom Controls */}
            <div className="absolute right-6 top-6 z-20 flex flex-col gap-1.5">
              <button
                type="button"
                onClick={() => setZoom((z) => Math.min(2, +(z + 0.2).toFixed(1)))}
                className="w-9 h-9 rounded-lg bg-slate-950/80 backdrop-blur-md border border-white/15 text-white flex items-center justify-center font-bold hover:bg-slate-800"
              >
                +
              </button>
              <button
                type="button"
                onClick={() => setZoom((z) => Math.max(0.8, +(z - 0.2).toFixed(1)))}
                className="w-9 h-9 rounded-lg bg-slate-950/80 backdrop-blur-md border border-white/15 text-white flex items-center justify-center font-bold hover:bg-slate-800"
              >
                -
              </button>
            </div>

            <div
              onClick={handlePlanolClick}
              style={{ transform: `scale(${zoom})` }}
              className="relative w-full max-w-sm aspect-[4/5] bg-slate-800 rounded-2xl border-2 border-white/20 shadow-2xl overflow-hidden cursor-crosshair transition-transform"
            >
              {/* Grid Tècnic Vectorial */}
              <div
                className="absolute inset-0 opacity-20 pointer-events-none"
                style={{
                  backgroundImage:
                    "linear-gradient(to right, #94a3b8 1px, transparent 1px), linear-gradient(to bottom, #94a3b8 1px, transparent 1px)",
                  backgroundSize: "24px 24px",
                }}
              />
              <div className="absolute inset-4 border border-dashed border-slate-500/60 rounded-xl pointer-events-none flex items-center justify-center">
                <span className="text-xs font-mono text-slate-300 bg-slate-900/70 px-2.5 py-1 rounded">
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
                        c.es_tancada
                          ? "text-amber-400"
                          : "text-secondary-container"
                      }`}
                    >
                      <MapPin className="w-6 h-6 drop-shadow-md fill-current" />
                      <span className="text-[9px] font-mono font-bold bg-slate-950/90 px-1.5 py-0.5 rounded text-white border border-slate-700 shadow">
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
              <div className="bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/30 dark:border-slate-800 p-5 rounded-2xl max-w-xs w-full text-center shadow-2xl space-y-4">
                <div className="w-12 h-12 rounded-full bg-amber-500/20 text-amber-500 flex items-center justify-center mx-auto border border-amber-500/30">
                  <Lock className="w-6 h-6" />
                </div>
                {/* TEXT EXACTE EXIGIT PER LA SPEC 017 */}
                <h3 className="text-sm font-extrabold text-primary dark:text-slate-100">
                  Capa tancada, vols crear una capa nova?
                </h3>
                <p className="text-xs text-on-surface-variant dark:text-slate-400">
                  Aquesta ordre de treball està tancada i facturada. Per a respectar la inalterabilitat del SIF, cal crear una capa d&apos;addenda activa.
                </p>
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={handleCrearNovaCapa}
                    className="flex-1 py-2.5 bg-secondary-container hover:brightness-110 text-white text-xs font-bold rounded-xl flex items-center justify-center gap-1 shadow-md"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Crear Capa Nova</span>
                  </button>
                  <button
                    onClick={() => {
                      setMostrarDialegCapaTancada(false);
                      setPendentClickCoords(null);
                    }}
                    className="px-3 py-2.5 bg-surface-container-low dark:bg-slate-800 hover:bg-surface-container text-on-surface dark:text-slate-300 text-xs font-semibold rounded-xl"
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