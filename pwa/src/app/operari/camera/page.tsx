"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Camera,
  CheckCircle2,
  Trash2,
  FolderCheck,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { apiFetch, getApiBaseUrl, getAuthToken } from "@/lib/api";
import { localDB, LocalCameraCapture } from "@/lib/db";
import { CAMERA_LIVE_INPUT_PROPS, compressImageToWebP } from "@/lib/media";

interface OrdreSimple {
  id: string;
  codi?: string;
  titol: string;
}

type FaseFoto = "INICIAL" | "INTERMEDIA" | "FINAL";

export default function OperariCameraPage() {
  const [captures, setCaptures] = useState<LocalCameraCapture[]>([]);
  const [ordres, setOrdres] = useState<OrdreSimple[]>([]);
  const [selectedOrdre, setSelectedOrdre] = useState<Record<string, string>>({});
  const [selectedFase, setSelectedFase] = useState<Record<string, FaseFoto>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const carregarEstat = useCallback(async () => {
    setLoading(true);
    try {
      const orfanes = await localDB.camera_captures
        .filter((c) => !c.assignada)
        .toArray();
      setCaptures(orfanes);

      if (navigator.onLine) {
        try {
          const data = (await apiFetch<OrdreSimple[]>("/operari/feines")) || [];
          setOrdres(data);
        } catch {
          const locals = await localDB.ordres.toArray();
          setOrdres(locals.map((o) => ({ id: o.id, codi: o.codi, titol: o.titol })));
        }
      } else {
        const locals = await localDB.ordres.toArray();
        setOrdres(locals.map((o) => ({ id: o.id, codi: o.codi, titol: o.titol })));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    carregarEstat();
  }, [carregarEstat]);

  const handleNovaCaptura = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    const compressed = await compressImageToWebP(file);
    let empresaId = "default";
    try {
      const u = JSON.parse(localStorage.getItem("sevalor_user") || "{}");
      if (u?.empresa_id) empresaId = u.empresa_id;
    } catch {}

    const id = crypto.randomUUID();
    await localDB.camera_captures.add({
      id,
      empresa_id: empresaId,
      blob: compressed,
      nom_fitxer: `cam_${Math.floor(Date.now() / 1000)}.webp`,
      assignada: false,
      created_at: new Date().toISOString(),
    });
    await carregarEstat();
  };

  const handleAssignarAOrdre = async (capture: LocalCameraCapture) => {
    const ordreId = selectedOrdre[capture.id];
    const fase: FaseFoto = selectedFase[capture.id] || "INTERMEDIA";
    if (!ordreId) {
      setError("Selecciona una Ordre de Treball abans d'assignar la captura.");
      return;
    }

    setProcessingId(capture.id);
    setError(null);
    try {
      if (navigator.onLine) {
        const formData = new FormData();
        formData.append("tipus", fase);
        formData.append("foto", capture.blob, capture.nom_fitxer);

        const token = getAuthToken();
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch(`${getApiBaseUrl()}/operari/feines/${ordreId}/fotos`, {
          method: "POST",
          headers,
          credentials: "include",
          body: formData,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Error assignant la fotografia a l'ordre.");
        }
      }

      await localDB.camera_captures.update(capture.id, {
        assignada: true,
        ordre_treball_id: ordreId,
        fase_foto: fase,
      });
      await carregarEstat();
    } catch (err: any) {
      setError(err.message || "No s'ha pogut assignar la imatge.");
    } finally {
      setProcessingId(null);
    }
  };

  const handleDescartar = async (captureId: string) => {
    await localDB.camera_captures.delete(captureId);
    await carregarEstat();
  };

  return (
    <div className="flex-1 flex flex-col bg-surface dark:bg-slate-950 text-on-surface dark:text-slate-100">
      <header className="bg-surface-container-lowest dark:bg-slate-900 border-b border-outline-variant/25 dark:border-slate-800 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/operari/feines"
            className="w-9 h-9 rounded-lg bg-surface-container-low dark:bg-slate-800 flex items-center justify-center text-primary dark:text-slate-200"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-base font-extrabold text-primary dark:text-white leading-tight">
              Càmera d&apos;Obra i Evidències
            </h1>
            <p className="text-[11px] font-mono text-on-surface-variant dark:text-slate-400">
              {captures.length} imatge(s) òrfena(es) pendent(s) d&apos;assignar
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={carregarEstat}
          className="p-2 rounded-lg bg-surface-container-low dark:bg-slate-800 text-on-surface-variant"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      <div className="flex-1 p-4 space-y-4 overflow-y-auto">
        {error && (
          <div className="p-3 rounded-xl bg-error-container text-on-error-container text-xs font-semibold flex items-center gap-2 border border-error/20">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <label className="w-full p-5 rounded-2xl border-2 border-dashed border-secondary-container/60 bg-secondary-container/10 text-secondary flex flex-col items-center justify-center gap-2 cursor-pointer active:scale-[0.99] transition-transform">
          <Camera className="w-8 h-8" />
          <span className="text-xs font-extrabold uppercase tracking-wider">
            Capturar Fotografia en Viu
          </span>
          <span className="text-[11px] text-on-surface-variant text-center">
            Cada foto s&apos;ha d&apos;assignar a una OT o descartar abans de tancar el torn.
          </span>
          <input {...CAMERA_LIVE_INPUT_PROPS} className="hidden" onChange={handleNovaCaptura} />
        </label>

        {captures.length === 0 ? (
          <div className="p-8 text-center bg-surface-container-lowest dark:bg-slate-900 rounded-2xl border border-dashed border-outline-variant/40 dark:border-slate-800 space-y-2">
            <CheckCircle2 className="w-10 h-10 mx-auto text-secondary" />
            <h2 className="text-sm font-bold text-primary dark:text-white">
              Cap imatge sense assignar
            </h2>
            <p className="text-xs text-on-surface-variant">
              El repositori de càmera està net. Pots tancar la jornada quan finalitzis les feines.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <h2 className="text-xs font-bold uppercase tracking-wider text-error">
              Captures Pendents d&apos;Assignar ({captures.length})
            </h2>
            {captures.map((cap) => (
              <div
                key={cap.id}
                className="p-4 rounded-2xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/30 dark:border-slate-800 shadow-sm space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-primary dark:text-white">
                    {cap.nom_fitxer}
                  </span>
                  <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400">
                    Sense OT
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-2">
                  <select
                    value={selectedOrdre[cap.id] || ""}
                    onChange={(e) =>
                      setSelectedOrdre((prev) => ({ ...prev, [cap.id]: e.target.value }))
                    }
                    className="w-full p-2.5 rounded-xl border border-outline-variant/40 bg-surface-container-low dark:bg-slate-800 text-xs font-medium"
                  >
                    <option value="">Selecciona Ordre de Treball...</option>
                    {ordres.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.codi ? `${o.codi} — ` : ""}
                        {o.titol}
                      </option>
                    ))}
                  </select>

                  <select
                    value={selectedFase[cap.id] || "INTERMEDIA"}
                    onChange={(e) =>
                      setSelectedFase((prev) => ({
                        ...prev,
                        [cap.id]: e.target.value as FaseFoto,
                      }))
                    }
                    className="w-full p-2.5 rounded-xl border border-outline-variant/40 bg-surface-container-low dark:bg-slate-800 text-xs font-medium"
                  >
                    <option value="INICIAL">Fase Inicial (Abans)</option>
                    <option value="INTERMEDIA">Fase Intermèdia (Progrés)</option>
                    <option value="FINAL">Fase Final (Acabat)</option>
                  </select>
                </div>

                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={processingId === cap.id}
                    onClick={() => handleAssignarAOrdre(cap)}
                    className="flex-1 py-2.5 rounded-xl bg-secondary-container text-white text-xs font-bold flex items-center justify-center gap-1.5 disabled:opacity-50"
                  >
                    <FolderCheck className="w-4 h-4" />
                    <span>{processingId === cap.id ? "Assignant..." : "Assignar a OT"}</span>
                  </button>
                  <button
                    type="button"
                    disabled={processingId === cap.id}
                    onClick={() => handleDescartar(cap.id)}
                    className="px-3.5 py-2.5 rounded-xl bg-error-container text-on-error-container text-xs font-bold flex items-center gap-1"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span>Descartar</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
