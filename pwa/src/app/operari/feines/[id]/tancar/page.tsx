"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import SignaturePad from "@/components/operari/SignaturePad";
import TiquetScanner from "@/components/operari/TiquetScanner";
import { apiFetch } from "@/lib/api";
import { db } from "@/lib/offline/db";

interface OrdreResum {
  codi?: string;
  titol?: string;
  hores_imputades_facturables?: number | null;
}

export default function TancarFeinaPage() {
  const params = useParams();
  const router = useRouter();
  const [signatureSaved, setSignatureSaved] = useState(false);
  const [savingSignature, setSavingSignature] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [nomSignant, setNomSignant] = useState("");
  const [dniSignant, setDniSignant] = useState("");
  const [observacions, setObservacions] = useState("");
  const [ordre, setOrdre] = useState<OrdreResum | null>(null);

  const feinaId = params.id as string;

  useEffect(() => {
    const carregarOrdre = async () => {
      try {
        if (typeof navigator !== "undefined" && navigator.onLine) {
          const data = await apiFetch<any>(`/operari/feines/${feinaId}`);
          if (data) {
            setOrdre({
              codi: data.codi,
              titol: data.titol,
              hores_imputades_facturables: data.hores_imputades_facturables,
            });
          }
        }
      } catch {
        // Mode offline silenciós
      }
    };
    carregarOrdre();
  }, [feinaId]);

  const handleSaveSignature = async (base64Signature: string) => {
    setSavingSignature(true);
    setErrorMsg(null);
    try {
      const horesAImputar =
        ordre?.hores_imputades_facturables != null && ordre.hores_imputades_facturables > 0
          ? ordre.hores_imputades_facturables
          : undefined;
      const nomClean = nomSignant.trim() || undefined;
      const dniClean = dniSignant.trim().toUpperCase() || undefined;
      const obsClean = observacions.trim() || undefined;

      if (typeof navigator !== "undefined" && navigator.onLine) {
        await apiFetch(`/operari/feines/${feinaId}/finalitzar`, {
          method: "PUT",
          body: JSON.stringify({
            signatura_base64: base64Signature,
            nom_receptor: nomClean,
            dni_receptor: dniClean,
            observacions: obsClean,
            hores: horesAImputar,
          }),
        });
      } else {
        await db.sync_queue.add({
          action: "TANCAR_ORDRE",
          payload: {
            ordre_id: feinaId,
            signatura_base64: base64Signature,
            nom_receptor: nomClean,
            dni_receptor: dniClean,
            nom_signant: nomClean,
            dni_signant: dniClean,
            observacions: obsClean,
            hores: horesAImputar,
            data_tancament: new Date().toISOString(),
          },
          status: "pending",
          createdAt: Date.now(),
        });
      }

      setSignatureSaved(true);
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Error en desar la signatura i tancar la feina.");
    } finally {
      setSavingSignature(false);
    }
  };

  const handleFinalize = () => {
    router.push("/operari/feines");
  };

  const hores = Number(ordre?.hores_imputades_facturables || 0);

  return (
    <div className="p-4 max-w-md mx-auto flex flex-col gap-5 bg-surface dark:bg-slate-950 min-h-screen">
      {/* Header Stitch Screen 7b207f2eb5474f77b6138461df461858 */}
      <header className="flex items-center justify-between bg-surface-container-lowest dark:bg-slate-900 p-3.5 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => router.back()}
            className="w-9 h-9 rounded-lg bg-surface-container-low dark:bg-slate-800 flex items-center justify-center text-primary dark:text-white"
          >
            <span className="material-symbols-outlined text-lg">
              arrow_back
            </span>
          </button>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant block">
              Ordre #{ordre?.codi || feinaId}
            </span>
            <h1 className="text-base font-extrabold text-primary dark:text-white leading-tight">
              Tancament de Jornada / Feina
            </h1>
          </div>
        </div>
        <span className="material-symbols-outlined text-secondary-container text-2xl">
          fact_check
        </span>
      </header>

      {/* Targeta Resum Temps Treballat */}
      <div className="bg-secondary-container/15 border border-secondary-container/30 rounded-xl p-3.5 flex items-center justify-between shadow-sm">
        <div>
          <span className="text-[10px] font-extrabold uppercase tracking-wider text-secondary block">
            Temps treballat registrat
          </span>
          <span className="text-xs text-on-surface-variant dark:text-slate-400">
            Còmput real en camp amb GPS
          </span>
        </div>
        <div className="text-right">
          <span className="text-lg font-mono font-black text-primary dark:text-slate-100 block">
            {hores > 0 ? `${hores.toFixed(2)} h` : "Segons GPS"}
          </span>
        </div>
      </div>

      <p className="text-xs text-on-surface-variant dark:text-slate-400 leading-relaxed px-1">
        Per favor, escaneja els tiquets de combustible o despeses necessaris i recull la conformitat del client o operari abans de tancar l&apos;ordre.
      </p>

      {/* Escàner OCR de Tiquets vinculat a aquesta OT */}
      <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm">
        <TiquetScanner ordreTreballId={feinaId} />
      </div>

      {/* Dades del receptor, observacions tècniques i Signatura Digital */}
      <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-4">
        {!signatureSaved ? (
          <>
            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider text-on-surface-variant mb-1">
                  Nom del Receptor
                </label>
                <input
                  type="text"
                  data-testid="input-nom-receptor"
                  value={nomSignant}
                  onChange={(e) => setNomSignant(e.target.value)}
                  placeholder="Nom i cognoms"
                  maxLength={150}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-white"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider text-on-surface-variant mb-1">
                  DNI / NIF Receptor
                </label>
                <input
                  type="text"
                  data-testid="input-dni-receptor"
                  value={dniSignant}
                  onChange={(e) => setDniSignant(e.target.value.toUpperCase())}
                  placeholder="12345678A"
                  maxLength={30}
                  className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-white"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-on-surface-variant mb-1">
                Observacions Tècniques de Tancament
              </label>
              <textarea
                data-testid="input-observacions-tancament"
                value={observacions}
                onChange={(e) => setObservacions(e.target.value)}
                placeholder="Notes d'obra, recomanacions al client o incidències resoltes..."
                rows={3}
                maxLength={2000}
                className="w-full px-3 py-2 text-xs rounded-lg border border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-white resize-none"
              />
            </div>

            {errorMsg && (
              <div className="p-3 rounded-lg bg-error-container/25 border border-error text-xs font-semibold text-error">
                {errorMsg}
              </div>
            )}

            <SignaturePad onSave={handleSaveSignature} disabled={savingSignature} />
          </>
        ) : (
          <div className="text-center p-6 text-secondary bg-secondary-container/10 rounded-xl border border-secondary-container/30">
            <span className="material-symbols-outlined text-4xl text-secondary-container mb-2 block">
              task_alt
            </span>
            <h3 className="font-extrabold text-base text-primary dark:text-white">
              Signatura desada correctament
            </h3>
            <p className="text-xs text-on-surface-variant mt-1">
              La feina s&apos;ha tancat i sincronitzat (o s&apos;ha posat a la cua offline).
            </p>
          </div>
        )}
      </div>

      {signatureSaved && (
        <button
          onClick={handleFinalize}
          className="w-full py-3.5 bg-primary text-white font-bold text-xs uppercase tracking-wider rounded-xl shadow-md hover:bg-primary-container transition-all flex items-center justify-center gap-2"
        >
          <span className="material-symbols-outlined text-base">
            assignment_return
          </span>
          Tornar a Feines
        </button>
      )}
    </div>
  );
}
