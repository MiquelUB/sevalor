"use client";

import React, { useState } from "react";
import { CheckCircle2, Camera, Receipt } from "lucide-react";
import { localDB } from "@/lib/db";
import { getApiBaseUrl, getAuthToken } from "@/lib/api";
import { CAMERA_LIVE_INPUT_PROPS, compressImageToWebP } from "@/lib/media";

type CategoriaTiquet = "CARBURANT" | "FERRETERIA" | "PEATGES" | "DIETES" | "ALTRES";

const CATEGORIES: { id: CategoriaTiquet; label: string }[] = [
  { id: "CARBURANT", label: "Carburant" },
  { id: "FERRETERIA", label: "Ferreteria" },
  { id: "PEATGES", label: "Peatges" },
  { id: "DIETES", label: "Dietes" },
  { id: "ALTRES", label: "Altres" },
];

export default function TiquetScanner({ onSaved }: { onSaved?: () => void }) {
  const [categoria, setCategoria] = useState<CategoriaTiquet>("FERRETERIA");
  const [fotoTiquet, setFotoTiquet] = useState<Blob | null>(null);
  const [fotoOdometre, setFotoOdometre] = useState<Blob | null>(null);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const handleCapture = async (
    e: React.ChangeEvent<HTMLInputElement>,
    target: "TIQUET" | "ODOMETRE"
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const compressed = await compressImageToWebP(file);
    if (target === "TIQUET") setFotoTiquet(compressed);
    else setFotoOdometre(compressed);
    setStatusMsg(null);
  };

  const handleSave = async () => {
    if (!fotoTiquet) {
      setStatusMsg("Cal capturar la foto del tiquet primer.");
      return;
    }
    if (categoria === "CARBURANT" && !fotoOdometre) {
      setStatusMsg("Per a Carburant cal la segona foto de l'odòmetre.");
      return;
    }

    setSaving(true);
    setStatusMsg(null);
    const nomFitxer = `tiquet_tmp_${Math.floor(Date.now() / 1000)}.webp`;

    try {
      if (navigator.onLine) {
        const formData = new FormData();
        formData.append("categoria", categoria);
        formData.append("foto_tiquet", fotoTiquet, nomFitxer);
        if (fotoOdometre) {
          formData.append("foto_odometre", fotoOdometre, `odo_${nomFitxer}`);
        }
        const token = getAuthToken();
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch(`${getApiBaseUrl()}/operari/tiquets/captura-rapida`, {
          method: "POST",
          headers,
          credentials: "include",
          body: formData,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Error en enviar el tiquet.");
        }
        setStatusMsg(`Enviat (${nomFitxer}) a Gestió per processament OCR.`);
      } else {
        let empresaId = "default";
        try {
          const u = JSON.parse(localStorage.getItem("sevalor_user") || "{}");
          if (u?.empresa_id) empresaId = u.empresa_id;
        } catch {}
        const id = crypto.randomUUID();
        await localDB.tiquets.add({
          id,
          empresa_id: empresaId,
          categoria,
          import_total: null,
          nom_fitxer: nomFitxer,
          tiquet_foto_blob: fotoTiquet,
          odometre_foto_blob: fotoOdometre || undefined,
          data_despesa: new Date().toISOString(),
          custodia_confirmada: false,
          estat_sync: "PENDENT",
        });
        await localDB.sync_queue.add({
          id: crypto.randomUUID(),
          bloc_uuid: crypto.randomUUID(),
          acció: "CREAR_TIQUET",
          payload: { id, categoria, nom_fitxer: nomFitxer, data_captura: new Date().toISOString() },
          timestamp: Date.now(),
          intents: 0,
        });
        setStatusMsg(`Desat offline (${nomFitxer}). Pendent de sincronització.`);
      }

      setFotoTiquet(null);
      setFotoOdometre(null);
      onSaved?.();
    } catch (err: any) {
      setStatusMsg(err.message || "Error desant el tiquet.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-4 rounded-2xl border border-outline-variant/30 bg-surface-container-lowest dark:bg-slate-900 shadow-sm">
      <div className="flex items-center gap-2 text-primary dark:text-slate-100">
        <Receipt className="w-5 h-5 text-secondary-container" />
        <h2 className="text-sm font-extrabold uppercase tracking-wider">Captura Ràpida Zero-Tecleig</h2>
      </div>

      <div className="grid grid-cols-3 gap-1.5">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            type="button"
            onClick={() => {
              setCategoria(cat.id);
              setStatusMsg(null);
            }}
            className={`py-2 px-2 rounded-xl text-[11px] font-bold border transition-all ${
              categoria === cat.id
                ? "border-secondary-container bg-secondary-container text-white"
                : "border-outline-variant/30 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-slate-200"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      <label
        className={`w-full flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed cursor-pointer transition-colors ${
          fotoTiquet
            ? "border-secondary-container bg-secondary-container/10 text-secondary"
            : "border-outline-variant/40 bg-surface-container-low dark:bg-slate-800/50 text-on-surface-variant"
        }`}
      >
        {fotoTiquet ? <CheckCircle2 className="w-7 h-7 mb-1" /> : <Camera className="w-7 h-7 mb-1" />}
        <span className="text-xs font-bold">
          {fotoTiquet ? "Foto del Tiquet Capturada ✓" : "Capturar Foto del Tiquet (Càmera en viu)"}
        </span>
        <input {...CAMERA_LIVE_INPUT_PROPS} className="hidden" onChange={(e) => handleCapture(e, "TIQUET")} />
      </label>

      {categoria === "CARBURANT" && (
        <label
          className={`w-full flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed cursor-pointer transition-colors ${
            fotoOdometre
              ? "border-secondary-container bg-secondary-container/10 text-secondary"
              : "border-outline-variant/40 bg-surface-container-low dark:bg-slate-800/50 text-on-surface-variant"
          }`}
        >
          {fotoOdometre ? <CheckCircle2 className="w-7 h-7 mb-1" /> : <Camera className="w-7 h-7 mb-1" />}
          <span className="text-xs font-bold">
            {fotoOdometre ? "Foto de l'Odòmetre Capturada ✓" : "2a Foto Obligatòria: Odòmetre (Càmera en viu)"}
          </span>
          <input {...CAMERA_LIVE_INPUT_PROPS} className="hidden" onChange={(e) => handleCapture(e, "ODOMETRE")} />
        </label>
      )}

      {statusMsg && (
        <p className="text-xs font-semibold text-primary dark:text-slate-200 bg-surface-container-low dark:bg-slate-800 p-2.5 rounded-xl">
          {statusMsg}
        </p>
      )}

      <button
        type="button"
        disabled={saving || !fotoTiquet || (categoria === "CARBURANT" && !fotoOdometre)}
        onClick={handleSave}
        className="w-full py-3 rounded-xl bg-secondary-container text-white text-xs font-bold uppercase tracking-wider disabled:opacity-50"
      >
        {saving ? "Enviant sense OCR local..." : "Desar i Enviar a Gestió"}
      </button>
    </div>
  );
}
