"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { FileCheck2, Gauge, Square, X, AlertCircle, ShieldAlert, Camera, CheckCircle2 } from "lucide-react";
import { localDB } from "@/lib/db";
import { getAuthToken } from "@/lib/api";
import { CAMERA_LIVE_INPUT_PROPS, compressImageToWebP } from "@/lib/media";
import { JornadaActivaState } from "./ControlHorariBar";

interface EveningCheckoutModalProps {
  jornada: JornadaActivaState | null;
  isOpen: boolean;
  onClose: () => void;
  onFinished: () => void;
}

export default function EveningCheckoutModal({
  jornada,
  isOpen,
  onClose,
  onFinished,
}: EveningCheckoutModalProps) {
  const [fotoOdometreFinal, setFotoOdometreFinal] = useState<Blob | null>(null);
  const [orphanCount, setOrphanCount] = useState<number>(0);
  const [pendingTicketsCount, setPendingTicketsCount] = useState<number>(0);
  const [custodiaPaperConfirmada, setCustodiaPaperConfirmada] = useState(false);
  const [materialsRetornatsConfirmats, setMaterialsRetornatsConfirmats] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    const verificarBloquejos = async () => {
      try {
        const orphans = await localDB.camera_captures.filter((c) => !c.assignada).count();
        const pendTiquets = await localDB.tiquets
          .filter((t) => t.estat_sync === "PENDENT" || t.estat_sync === "ERROR")
          .count();
        const pendQueue = await localDB.sync_queue
          .filter((q) => q.acció === "CREAR_TIQUET")
          .count();
        if (active) {
          setOrphanCount(orphans);
          setPendingTicketsCount(pendTiquets + pendQueue);
        }
      } catch {
        // Ignorar errors puntuals d'IndexedDB
      }
    };
    verificarBloquejos();
    return () => {
      active = false;
    };
  }, [isOpen]);

  if (!isOpen || !jornada) return null;

  const obtenirGPS = (): Promise<{ latitud: number; longitud: number }> => {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("El dispositiu no disposa de geolocalització GPS."));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (p) => resolve({ latitud: p.coords.latitude, longitud: p.coords.longitude }),
        () => reject(new Error("Cal senyal GPS vàlid per finalitzar el torn.")),
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    });
  };

  const handleConfirmarTancament = async () => {
    const orphans = await localDB.camera_captures.filter((c) => !c.assignada).count();
    if (orphans > 0) {
      setOrphanCount(orphans);
      setError("Imatges sense assignar, assigna abans de tancar");
      return;
    }

    const pendTiquets = await localDB.tiquets
      .filter((t) => t.estat_sync === "PENDENT" || t.estat_sync === "ERROR")
      .count();
    const pendQueue = await localDB.sync_queue.filter((q) => q.acció === "CREAR_TIQUET").count();
    if (pendTiquets + pendQueue > 0) {
      setPendingTicketsCount(pendTiquets + pendQueue);
      setError("Sincronitzant tiquets amb el servidor... Espera la confirmació de pujada abans de tancar.");
      return;
    }

    if (!fotoOdometreFinal) {
      setError("És obligatori capturar en viu la fotografia de l'odòmetre final del vehicle.");
      return;
    }

    if (!custodiaPaperConfirmada) {
      setError("És obligatori confirmar la custòdia física dels tiquets en paper (FR-009).");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const coords = await obtenirGPS();
      const nowIso = new Date().toISOString();

      if (navigator.onLine) {
        const token = getAuthToken();
        const authHeaders: Record<string, string> = {};
        if (token) authHeaders["Authorization"] = `Bearer ${token}`;

        const formOdo = new FormData();
        formOdo.append("foto_odometre", fotoOdometreFinal, `odometre_fi_${Date.now()}.webp`);
        formOdo.append("moment", "FI");
        const odoRes = await fetch(`/api/v1/operari/jornada/${jornada.id}/odometre-foto`, {
          method: "POST",
          headers: authHeaders,
          credentials: "include",
          body: formOdo,
        });
        if (!odoRes.ok) {
          const errOdo = await odoRes.json().catch(() => ({}));
          throw new Error(errOdo.detail || "Error pujant la fotografia de l'odòmetre final.");
        }

        const headers: Record<string, string> = {
          "Content-Type": "application/json",
          ...authHeaders,
        };

        await fetch("/api/v1/operari/tiquets/checkout-custodia", {
          method: "POST",
          headers,
          credentials: "include",
          body: JSON.stringify({}),
        });

        const res = await fetch(`/api/v1/operari/jornada/${jornada.id}/fi`, {
          method: "POST",
          headers,
          credentials: "include",
          body: JSON.stringify({
            latitud: coords.latitud,
            longitud: coords.longitud,
            lat: coords.latitud,
            lon: coords.longitud,
          }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "Error en tancar la jornada al servidor.");
        }
      } else {
        await localDB.sync_queue.add({
          id: crypto.randomUUID(),
          bloc_uuid: crypto.randomUUID(),
          acció: "FITXAR_JORNADA",
          payload: {
            jornada_id: jornada.id,
            tipus: "FI",
            latitud: coords.latitud,
            longitud: coords.longitud,
            odometre_foto_final: true,
            custodia_paper_confirmada: true,
            materials_retornats: materialsRetornatsConfirmats,
            timestamp: nowIso,
          },
          timestamp: Date.now(),
          intents: 0,
        });
      }

      // Buidar safata diària de tiquets un cop confirmada la custòdia
      await localDB.tiquets.toCollection().modify({ custodia_confirmada: true }).catch(() => {});

      // Actualitzar el registre local
      await localDB.fichajes.update(jornada.id, {
        hora_fi: nowIso,
        latitud_fi: coords.latitud,
        longitud_fi: coords.longitud,
        estat: "COMPLERT",
      }).catch(() => {});

      localStorage.removeItem("sevalor_jornada_activa");
      window.dispatchEvent(new Event("sevalor-jornada-updated"));
      onFinished();
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error finalitzant el torn.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      data-testid="evening-checkout-modal"
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200"
    >
      <div className="bg-surface-container-lowest text-on-surface w-full max-w-md rounded-2xl shadow-2xl border border-outline-variant/30 overflow-hidden flex flex-col">
        {/* Capçalera d'alarma controlada */}
        <div className="bg-error text-on-error p-4 flex items-center justify-between shrink-0 shadow-sm">
          <div>
            <div className="flex items-center gap-1.5">
              <ShieldAlert className="w-4 h-4 text-on-error opacity-90" />
              <p className="text-[11px] font-bold uppercase tracking-wider opacity-90">
                Fi de Torn • Protocol US3 / FR-009
              </p>
            </div>
            <h2 className="text-lg font-black tracking-tight mt-0.5">Tancament de Jornada i Custòdia</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg bg-white/10 hover:bg-white/20 active:scale-95 transition-transform"
          >
            <X className="w-5 h-5 text-on-error" />
          </button>
        </div>

        <div className="p-5 space-y-4 overflow-y-auto">
          {error && (
            <div
              data-testid="checkout-error"
              className="p-3 rounded-xl bg-error-container text-on-error-container text-xs font-bold flex items-center gap-2 border border-error/20"
            >
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {orphanCount > 0 && (
            <div className="p-3 rounded-xl bg-amber-500/15 border border-amber-500/40 text-amber-800 dark:text-amber-300 text-xs font-bold flex items-center justify-between gap-2">
              <span>Imatges sense assignar ({orphanCount}), assigna abans de tancar</span>
              <Link
                href="/operari/camera"
                onClick={onClose}
                className="px-2.5 py-1 rounded-lg bg-amber-600 text-white text-[11px] font-bold shrink-0"
              >
                Assignar ara
              </Link>
            </div>
          )}

          {pendingTicketsCount > 0 && (
            <div className="p-3 rounded-xl bg-error-container text-on-error-container text-xs font-bold border border-error/30">
              Hi ha {pendingTicketsCount} tiquet(s) pendents de pujada al servidor. Espera la sincronització abans de tancar.
            </div>
          )}

          {/* Odòmetre final en viu (Spec 015/020 Zero-Tecleig) */}
          <div>
            <label className="text-xs font-bold uppercase text-on-surface flex items-center gap-1.5 mb-1.5">
              <Gauge className="w-4 h-4 text-primary" />
              Fotografia Odòmetre Final del Vehicle *
            </label>
            <label
              data-testid="input-checkout-odometre-foto"
              className={`w-full min-h-[54px] p-3 rounded-xl border-2 border-dashed flex items-center justify-center gap-2 cursor-pointer transition-colors ${
                fotoOdometreFinal
                  ? "border-secondary-container bg-secondary-container/10 text-secondary"
                  : "border-outline-variant bg-surface-container-low text-on-surface-variant"
              }`}
            >
              {fotoOdometreFinal ? (
                <CheckCircle2 className="w-5 h-5" />
              ) : (
                <Camera className="w-5 h-5" />
              )}
              <span className="text-xs font-bold">
                {fotoOdometreFinal
                  ? "Foto odòmetre final capturada ✓"
                  : "Capturar Odòmetre Final (Càmera en viu)"}
              </span>
              <input
                {...CAMERA_LIVE_INPUT_PROPS}
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  const blob = await compressImageToWebP(file);
                  setFotoOdometreFinal(blob);
                  setError(null);
                }}
              />
            </label>
          </div>

          {/* Confirmació de Retorn de Materials */}
          <label className="flex items-start gap-3 p-3.5 rounded-xl bg-surface-container-low border border-outline-variant/30 cursor-pointer select-none">
            <input
              type="checkbox"
              data-testid="checkbox-checkout-materials"
              checked={materialsRetornatsConfirmats}
              onChange={(e) => setMaterialsRetornatsConfirmats(e.target.checked)}
              className="mt-1 w-4 h-4 rounded text-secondary focus:ring-secondary"
            />
            <span className="text-xs text-on-surface leading-relaxed">
              <strong className="block text-on-surface font-bold">Pick-Out de Magatzem:</strong>
              He retornat les eines o registrat els materials sobrants a la furgoneta.
            </span>
          </label>

          {/* Confirmació Mandatòria de Custòdia de Tiquets en Paper (FR-009) */}
          <label className="flex items-start gap-3 p-3.5 rounded-xl bg-secondary-container/20 border-2 border-secondary cursor-pointer select-none">
            <input
              type="checkbox"
              data-testid="checkbox-custodia-paper"
              checked={custodiaPaperConfirmada}
              onChange={(e) => setCustodiaPaperConfirmada(e.target.checked)}
              className="mt-1 w-4 h-4 rounded text-secondary focus:ring-secondary"
            />
            <span className="text-xs text-on-surface leading-relaxed">
              <strong className="flex items-center gap-1 text-secondary font-black uppercase text-[11px] tracking-wide mb-0.5">
                <FileCheck2 className="w-4 h-4" /> Custòdia Física de Paper Obligatòria (FR-009)
              </strong>
              Confirmo que conservo físicament tots els tiquets de despesa i carburant en paper generats avui per lliurar-los al caixetí d&apos;administració.
            </span>
          </label>

          {/* Botó de finalització */}
          <button
            type="button"
            data-testid="btn-confirmar-checkout-jornada"
            disabled={
              loading ||
              !custodiaPaperConfirmada ||
              !fotoOdometreFinal ||
              orphanCount > 0 ||
              pendingTicketsCount > 0
            }
            onClick={handleConfirmarTancament}
            className="w-full min-h-[52px] bg-error text-on-error font-bold rounded-xl flex items-center justify-center gap-2 uppercase text-xs tracking-wider disabled:opacity-50 active:scale-95 transition-all shadow-md mt-2"
          >
            <Square className="w-4 h-4 fill-current" />
            <span>{loading ? "Tancant Torn amb GPS..." : "Confirmar Custòdia i Fitxar Sortida"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
