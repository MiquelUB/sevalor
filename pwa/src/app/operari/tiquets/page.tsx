"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Camera,
  CheckCircle2,
  AlertCircle,
  Receipt,
  Inbox,
  Plus,
  RefreshCw,
  X,
  Clock,
} from "lucide-react";
import { apiFetch, getApiBaseUrl, getAuthToken } from "@/lib/api";
import { localDB } from "@/lib/db";
import { CAMERA_LIVE_INPUT_PROPS, compressImageToWebP } from "@/lib/media";

type CategoriaTiquet = "CARBURANT" | "FERRETERIA" | "PEATGES" | "DIETES" | "ALTRES";

interface TiquetSafataItem {
  id: string;
  categoria: CategoriaTiquet;
  nom_fitxer_visible: string;
  estat_aprovacio: string;
  te_foto_odometre?: boolean;
  ordre_treball_id?: string | null;
  created_at?: string | null;
  isOfflinePending?: boolean;
}

interface OrdreSimple {
  id: string;
  codi?: string;
  titol: string;
}

const CATEGORIES_TAXTIL: { id: CategoriaTiquet; label: string }[] = [
  { id: "FERRETERIA", label: "Ferreteria" },
  { id: "CARBURANT", label: "Carburant" },
  { id: "PEATGES", label: "Peatges" },
  { id: "DIETES", label: "Dietes" },
  { id: "ALTRES", label: "Altres" },
];

export default function OperariTiquetsPage() {
  const [safataAvui, setSafataAvui] = useState<TiquetSafataItem[]>([]);
  const [ordres, setOrdres] = useState<OrdreSimple[]>([]);
  const [loading, setLoading] = useState(true);
  const [mostrarFormulari, setMostrarFormulari] = useState<boolean>(false);

  const [categoria, setCategoria] = useState<CategoriaTiquet>("FERRETERIA");
  const [ordreTreballId, setOrdreTreballId] = useState<string>("");
  const [fotoTiquet, setFotoTiquet] = useState<Blob | null>(null);
  const [fotoOdometre, setFotoOdometre] = useState<Blob | null>(null);
  const [guardant, setGuardant] = useState(false);
  const [errorValidacio, setErrorValidacio] = useState<string | null>(null);

  const carregarDades = useCallback(async () => {
    setLoading(true);
    try {
      const offlineItems = await localDB.tiquets
        .filter((t) => !t.custodia_confirmada && t.estat_sync !== "SINCRONITZAT")
        .toArray();
      const mappedOffline: TiquetSafataItem[] = offlineItems.map((t) => ({
        id: t.id,
        categoria: (t.categoria === "MATERIAL" ? "FERRETERIA" : t.categoria) as CategoriaTiquet,
        nom_fitxer_visible: t.nom_fitxer || `tiquet_tmp_${Date.now()}.webp`,
        estat_aprovacio: t.estat_sync === "PENDENT" ? "PENDENT_SYNC_OFFLINE" : t.estat_sync,
        te_foto_odometre: Boolean(t.odometre_foto_blob),
        ordre_treball_id: t.ordre_treball_id || null,
        created_at: t.data_despesa,
        isOfflinePending: true,
      }));

      let remoteItems: TiquetSafataItem[] = [];
      if (navigator.onLine) {
        try {
          remoteItems = (await apiFetch<TiquetSafataItem[]>("/operari/tiquets/avui")) || [];
        } catch {
          remoteItems = [];
        }
        try {
          const ordresData = (await apiFetch<OrdreSimple[]>("/operari/feines")) || [];
          setOrdres(ordresData);
        } catch {
          const locals = await localDB.ordres.toArray();
          setOrdres(locals.map((o) => ({ id: o.id, codi: o.codi, titol: o.titol })));
        }
      } else {
        const locals = await localDB.ordres.toArray();
        setOrdres(locals.map((o) => ({ id: o.id, codi: o.codi, titol: o.titol })));
      }

      setSafataAvui([...mappedOffline, ...remoteItems]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    carregarDades();
  }, [carregarDades]);

  const handleFotoTiquet = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const blob = await compressImageToWebP(file);
    setFotoTiquet(blob);
    setErrorValidacio(null);
  };

  const handleFotoOdometre = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const blob = await compressImageToWebP(file);
    setFotoOdometre(blob);
    setErrorValidacio(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fotoTiquet) {
      setErrorValidacio("La fotografia del tiquet és obligatòria.");
      return;
    }
    if (categoria === "CARBURANT" && !fotoOdometre) {
      setErrorValidacio("Per a CARBURANT és obligatori capturar la segona foto de l'odòmetre.");
      return;
    }

    setGuardant(true);
    setErrorValidacio(null);
    const nomFitxer = `tiquet_tmp_${Math.floor(Date.now() / 1000)}.webp`;

    try {
      if (navigator.onLine) {
        const formData = new FormData();
        formData.append("categoria", categoria);
        formData.append("foto_tiquet", fotoTiquet, nomFitxer);
        if (fotoOdometre) {
          formData.append("foto_odometre", fotoOdometre, `odo_${nomFitxer}`);
        }
        if (ordreTreballId) {
          formData.append("ordre_treball_id", ordreTreballId);
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
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "No s'ha pogut enviar el tiquet.");
        }
      } else {
        let empresaId = "default";
        try {
          const u = JSON.parse(localStorage.getItem("sevalor_user") || "{}");
          if (u?.empresa_id) empresaId = u.empresa_id;
        } catch {}

        const localId = crypto.randomUUID();
        await localDB.tiquets.add({
          id: localId,
          empresa_id: empresaId,
          categoria,
          import_total: null,
          nom_fitxer: nomFitxer,
          ordre_treball_id: ordreTreballId || null,
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
          payload: {
            id: localId,
            categoria,
            nom_fitxer: nomFitxer,
            ordre_treball_id: ordreTreballId || null,
            timestamp: Date.now(),
          },
          timestamp: Date.now(),
          intents: 0,
        });
      }

      setFotoTiquet(null);
      setFotoOdometre(null);
      setOrdreTreballId("");
      setMostrarFormulari(false);
      await carregarDades();
    } catch (err: any) {
      setErrorValidacio(err.message || "Error desant la captura del tiquet.");
    } finally {
      setGuardant(false);
    }
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
              Tiquets i Despeses
            </h1>
            <p className="text-[11px] font-mono text-on-surface-variant dark:text-slate-400">
              Captura Zero-Tecleig • Sense OCR al terminal
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={carregarDades}
          className="p-2 rounded-lg bg-surface-container-low dark:bg-slate-800 text-on-surface-variant"
          title="Actualitzar safata"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      <div className="flex-1 p-4 space-y-4 overflow-y-auto">
        {mostrarFormulari ? (
          <form
            onSubmit={handleSubmit}
            className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-2xl border border-outline-variant/30 dark:border-slate-800 shadow-sm space-y-4"
          >
            <div className="flex items-center justify-between border-b border-outline-variant/20 pb-2">
              <h2 className="text-sm font-extrabold text-primary dark:text-white">
                Nova Captura de Tiquet
              </h2>
              <button
                type="button"
                onClick={() => {
                  setMostrarFormulari(false);
                  setErrorValidacio(null);
                }}
                className="p-1 text-on-surface-variant hover:text-error"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {errorValidacio && (
              <div className="p-3 rounded-xl bg-error-container text-on-error-container text-xs font-semibold flex items-center gap-2 border border-error/20">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorValidacio}</span>
              </div>
            )}

            <div>
              <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-2">
                1. Categoria de Despesa
              </label>
              <div className="grid grid-cols-3 gap-2">
                {CATEGORIES_TAXTIL.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => {
                      setCategoria(cat.id);
                      setErrorValidacio(null);
                    }}
                    className={`py-2.5 px-2 rounded-xl text-xs font-extrabold border transition-all ${
                      categoria === cat.id
                        ? "border-secondary-container bg-secondary-container text-white shadow-sm"
                        : "border-outline-variant/30 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-slate-300"
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1.5">
                2. Vincular a Ordre de Treball (Opcional)
              </label>
              <select
                value={ordreTreballId}
                onChange={(e) => setOrdreTreballId(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-outline-variant/40 bg-surface-container-low dark:bg-slate-800 text-xs font-medium"
              >
                <option value="">Sense OT específica (Despesa general)</option>
                {ordres.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.codi ? `${o.codi} — ` : ""}
                    {o.titol}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-3">
              <div>
                <p className="text-[11px] font-bold uppercase text-on-surface-variant mb-1">
                  3. Fotografia en Viu del Tiquet *
                </p>
                <label
                  className={`flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed cursor-pointer transition-colors ${
                    fotoTiquet
                      ? "border-secondary-container bg-secondary-container/10 text-secondary"
                      : "border-outline-variant/40 bg-surface-container-low dark:bg-slate-800 text-on-surface-variant"
                  }`}
                >
                  {fotoTiquet ? (
                    <CheckCircle2 className="w-6 h-6 mb-1" />
                  ) : (
                    <Camera className="w-6 h-6 mb-1" />
                  )}
                  <span className="text-xs font-bold">
                    {fotoTiquet ? "Tiquet Capturat ✓" : "Obrir Càmera del Tiquet"}
                  </span>
                  <input {...CAMERA_LIVE_INPUT_PROPS} className="hidden" onChange={handleFotoTiquet} />
                </label>
              </div>

              {categoria === "CARBURANT" && (
                <div>
                  <p className="text-[11px] font-bold uppercase text-error mb-1">
                    4. Segona Foto Obligatòria: Odòmetre del Vehicle *
                  </p>
                  <label
                    className={`flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed cursor-pointer transition-colors ${
                      fotoOdometre
                        ? "border-secondary-container bg-secondary-container/10 text-secondary"
                        : "border-error/40 bg-error-container/20 text-error"
                    }`}
                  >
                    {fotoOdometre ? (
                      <CheckCircle2 className="w-6 h-6 mb-1" />
                    ) : (
                      <Camera className="w-6 h-6 mb-1" />
                    )}
                    <span className="text-xs font-bold">
                      {fotoOdometre ? "Odòmetre Capturat ✓" : "Capturar Odòmetre en Viu"}
                    </span>
                    <input
                      {...CAMERA_LIVE_INPUT_PROPS}
                      className="hidden"
                      onChange={handleFotoOdometre}
                    />
                  </label>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={guardant}
              className="w-full py-3.5 rounded-xl bg-secondary-container hover:brightness-110 text-white text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow disabled:opacity-50"
            >
              <Receipt className="w-4 h-4" />
              <span>{guardant ? "Transmetent..." : "Enviar Captura a Gestió"}</span>
            </button>
          </form>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                Safata d&apos;Avui (Sense Miniatures)
              </h2>
              <button
                type="button"
                onClick={() => setMostrarFormulari(true)}
                className="px-3.5 py-2 rounded-xl bg-secondary-container text-white text-xs font-bold flex items-center gap-1.5 shadow"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Capturar Tiquet</span>
              </button>
            </div>

            {loading && safataAvui.length === 0 ? (
              <div className="p-8 text-center text-on-surface-variant text-xs">
                <RefreshCw className="w-5 h-5 animate-spin text-secondary-container mx-auto mb-2" />
                <span>Carregant safata diària...</span>
              </div>
            ) : safataAvui.length === 0 ? (
              <div className="p-8 text-center bg-surface-container-lowest dark:bg-slate-900 rounded-2xl border border-dashed border-outline-variant/40 dark:border-slate-800 space-y-2">
                <Inbox className="w-10 h-10 mx-auto text-outline" />
                <h3 className="text-sm font-bold text-primary dark:text-slate-200">
                  Safata diària buida
                </h3>
                <p className="text-xs text-on-surface-variant max-w-xs mx-auto">
                  Captura els tiquets en paper amb un sol toc; Gestió processarà els imports i l&apos;IVA automàticament.
                </p>
                <button
                  type="button"
                  onClick={() => setMostrarFormulari(true)}
                  className="mt-2 px-4 py-2 bg-secondary-container text-white rounded-xl text-xs font-bold"
                >
                  + Capturar Primer Tiquet
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {safataAvui.map((tiq) => (
                  <div
                    key={tiq.id}
                    className="p-3.5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/25 dark:border-slate-800 shadow-sm flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-secondary-container/15 text-secondary flex items-center justify-center">
                        <Receipt className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="text-xs font-extrabold text-primary dark:text-white font-mono">
                          {tiq.nom_fitxer_visible}
                        </p>
                        <p className="text-[10px] text-on-surface-variant font-semibold uppercase">
                          {tiq.categoria} {tiq.te_foto_odometre ? "• +Odòmetre" : ""}
                        </p>
                      </div>
                    </div>
                    <span
                      className={`text-[10px] font-bold uppercase px-2 py-1 rounded-full flex items-center gap-1 ${
                        tiq.isOfflinePending
                          ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                          : "bg-secondary-container/15 text-secondary"
                      }`}
                    >
                      <Clock className="w-3 h-3" />
                      {tiq.estat_aprovacio}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
