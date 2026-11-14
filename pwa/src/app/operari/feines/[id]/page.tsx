"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Settings,
  Cpu,
  HardDrive,
  Server,
  Smartphone,
  Wrench,
  FileText,
  Bot,
  Truck,
  Package,
  Navigation,
  CheckCircle2,
  MapPin,
  Layers,
  ExternalLink,
  Camera,
  ShieldCheck,
  Lock,
  AlertTriangle,
} from "lucide-react";
import CameraCapture from "@/components/CameraCapture";
import { apiFetch } from "@/lib/api";
import { db } from "@/lib/offline/db";
import { encryptWithPin, decryptWithPin } from "@/lib/crypto";

type TipusFotoQA = "INICIAL" | "INTERMEDIA" | "FINAL";

interface EstatFotosQA {
  fotos_pujades: TipusFotoQA[];
  protocol_complet: boolean;
  falten: TipusFotoQA[];
}

interface Asset {
  id: string;
  nom: string;
  model: string;
  tipus: string;
  num_serie: string;
  estat: string;
}

interface LiniaPicking {
  id: string;
  article_id: string;
  article_nom: string;
  quantitat_prevista: number;
  quantitat_carregada_pick_in: number;
}

interface EinaCustodia {
  id: string;
  nom: string;
  model?: string;
  numero_serie: string;
  estat: string;
}

interface OrdreDetall {
  id: string;
  codi: string;
  titol: string;
  descripcio?: string;
  client: string;
  estat: string;
  adreca?: string;
  vehicle?: { matricula: string; model: string };
  linies_picking?: LiniaPicking[];
  eines_assignades?: EinaCustodia[];
  assets: Asset[];
  planol_id?: string | null;
  planol_titol?: string | null;
  planol_codi?: string | null;
  planol_tipus_fitxer?: string | null;
  hora_inici_real?: string | null;
  hora_fi_real?: string | null;
  gps_inici_lat?: number | null;
  gps_inici_lng?: number | null;
  gps_fi_lat?: number | null;
  gps_fi_lng?: number | null;
  hores_imputades_facturables?: number | null;
  desviacio_geovalla?: boolean;
  justificacio_geovalla?: string | null;
}

export default function LlistaMaquinesPage() {
  const { id } = useParams() as { id: string };
  const router = useRouter();

  const [ordre, setOrdre] = useState<OrdreDetall | null>(null);
  const [hasCopilotIa, setHasCopilotIa] = useState<boolean>(true);
  const [loading, setLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(false);
  const [showPinModal, setShowPinModal] = useState(false);
  const [offlinePin, setOfflinePin] = useState("");
  const [offlineError, setOfflineError] = useState<string | null>(null);

  // Geovalla i inici/final en temps de feina (FR-005)
  const [iniciantFeina, setIniciantFeina] = useState(false);
  const [requereixJustificacioGPS, setRequereixJustificacioGPS] = useState(false);
  const [accioPendentGps, setAccioPendentGps] = useState<"inici" | "final">("inici");
  const [justificacioGps, setJustificacioGps] = useState("");
  const [gpsFeedback, setGpsFeedback] = useState<string | null>(null);
  const [gpsError, setGpsError] = useState<string | null>(null);

  // Semàfor 3 Fotos QA (FR-007)
  const [estatFotos, setEstatFotos] = useState<EstatFotosQA>({
    fotos_pujades: [],
    protocol_complet: false,
    falten: ["INICIAL", "INTERMEDIA", "FINAL"],
  });
  const [tipusFotoActiva, setTipusFotoActiva] = useState<TipusFotoQA | null>(null);
  const [uploadingFoto, setUploadingFoto] = useState(false);

  const carregarEstatFotos = async () => {
    if (typeof navigator !== "undefined" && !navigator.onLine) return;
    try {
      const res = await fetch(`/api/v1/operari/feines/${id}/fotos`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        const fotosDict = data.fotos || {};
        const pujades: TipusFotoQA[] = [];
        if (fotosDict.inicial) pujades.push("INICIAL");
        if (fotosDict.intermedia) pujades.push("INTERMEDIA");
        if (fotosDict.final) pujades.push("FINAL");

        const tot: TipusFotoQA[] = ["INICIAL", "INTERMEDIA", "FINAL"];
        const falten = tot.filter((t) => !pujades.includes(t));
        setEstatFotos({
          fotos_pujades: pujades,
          protocol_complet: Boolean(data.protocol_complet || pujades.length === 3),
          falten,
        });
      }
    } catch {
      // mode offline
    }
  };

  const obtenirGPS = (): Promise<{ latitud: number; longitud: number }> =>
    new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Geolocalització no disponible"));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ latitud: pos.coords.latitude, longitud: pos.coords.longitude }),
        () => reject(new Error("No s'ha pogut obtenir el senyal GPS")),
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });

  const handleMarcarTempsGps = async (accio: "inici" | "final") => {
    setIniciantFeina(true);
    setAccioPendentGps(accio);
    setGpsError(null);
    setGpsFeedback(null);
    try {
      const coords = await obtenirGPS();
      const endpoint =
        accio === "inici"
          ? `/api/v1/operari/feines/${id}/comencar`
          : `/api/v1/operari/feines/${id}/finalitzar-temps`;
      const res = await fetch(endpoint, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          lat: coords.latitud,
          lng: coords.longitud,
          lon: coords.longitud,
          desviacio_justificada: Boolean(justificacioGps.trim()),
          justificacio_gps: justificacioGps.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail =
          err.detail ||
          (accio === "inici" ? "Error en iniciar la feina" : "Error en marcar el final de la feina");
        if (
          detail.includes("50m") ||
          detail.toLowerCase().includes("geovalla") ||
          detail.toLowerCase().includes("desviaci")
        ) {
          setRequereixJustificacioGPS(true);
        }
        throw new Error(detail);
      }

      const data = await res.json().catch(() => ({}));
      setOrdre((prev) =>
        prev
          ? {
              ...prev,
              estat: data.estat || (accio === "inici" ? "EN_CURS" : prev.estat),
              hora_inici_real: data.hora_inici_real ?? prev.hora_inici_real,
              hora_fi_real: data.hora_fi_real ?? prev.hora_fi_real,
              gps_inici_lat: data.gps_inici_lat ?? prev.gps_inici_lat,
              gps_inici_lng: data.gps_inici_lng ?? prev.gps_inici_lng,
              gps_fi_lat: data.gps_fi_lat ?? prev.gps_fi_lat,
              gps_fi_lng: data.gps_fi_lng ?? prev.gps_fi_lng,
              hores_imputades_facturables:
                data.hores_imputades_facturables ?? prev.hores_imputades_facturables,
              desviacio_geovalla: data.desviacio_geovalla ?? prev.desviacio_geovalla,
              justificacio_geovalla: data.justificacio_geovalla ?? prev.justificacio_geovalla,
            }
          : null
      );
      setRequereixJustificacioGPS(false);
      setJustificacioGps("");
      setGpsFeedback(
        accio === "inici"
          ? "Inici de feina i posició GPS registrats. Feina en curs!"
          : "Final de feina i posició GPS registrats correctament!"
      );
    } catch (e: unknown) {
      setGpsError(e instanceof Error ? e.message : "Error GPS");
    } finally {
      setIniciantFeina(false);
    }
  };

  const handleCaptureFotoQA = async (blob: Blob) => {
    if (!tipusFotoActiva) return;
    const tipus = tipusFotoActiva;
    setTipusFotoActiva(null);
    setUploadingFoto(true);
    setGpsError(null);

    try {
      const formData = new FormData();
      formData.append("tipus", tipus);
      formData.append("foto", blob, `ot_${id}_foto_${tipus.toLowerCase()}.webp`);
      formData.append("fitxer", blob, `ot_${id}_foto_${tipus.toLowerCase()}.webp`);

      const res = await fetch(`/api/v1/operari/feines/${id}/fotos`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Error pujant la fotografia QA.");
      }

      await carregarEstatFotos();
    } catch (e: unknown) {
      setGpsError(e instanceof Error ? e.message : "Error pujant la fotografia");
    } finally {
      setUploadingFoto(false);
    }
  };

  const loadFeina = async (pin?: string) => {
    setLoading(true);
    setOfflineError(null);
    const checkOffline = typeof navigator !== "undefined" && !navigator.onLine;
    setIsOffline(checkOffline);

    try {
      if (checkOffline) {
        const storedPin = pin || sessionStorage.getItem("sevalor_session_pin");
        if (!storedPin) {
          setShowPinModal(true);
          setLoading(false);
          return;
        }

        const record = await db.ordres.get(id);
        if (!record) {
          throw new Error("Dades no trobades a la memòria cau offline.");
        }

        const saltStr = localStorage.getItem("sevalor_sentinel_salt");
        if (!saltStr)
          throw new Error("No s'ha trobat la sal criptogràfica del dispositiu.");
        const saltBytes = new Uint8Array(saltStr.split(",").map(Number));

        try {
          const decryptedStr = await decryptWithPin(
            record.ciphertext,
            record.iv,
            storedPin,
            saltBytes
          );
          const data = JSON.parse(decryptedStr);

          sessionStorage.setItem("sevalor_session_pin", storedPin);
          setShowPinModal(false);

          setOrdre({
            id: String(data.id),
            codi: data.codi || "OT-00",
            titol: data.titol || "Detall de l'Ordre",
            descripcio: data.descripcio,
            client: data.client?.rao_social || "Client",
            estat: data.estat || "PENDENT",
            adreca: data.adreca || "",
            vehicle: data.vehicle,
            linies_picking: data.linies_picking || [],
            eines_assignades: data.eines_assignades || [],
            assets: data.assets || [],
            planol_id: data.planol_id || null,
            planol_titol: data.planol_titol || null,
            planol_codi: data.planol_codi || null,
            planol_tipus_fitxer: data.planol_tipus_fitxer || null,
            hora_inici_real: data.hora_inici_real || null,
            hora_fi_real: data.hora_fi_real || null,
            gps_inici_lat: data.gps_inici_lat ?? null,
            gps_inici_lng: data.gps_inici_lng ?? null,
            gps_fi_lat: data.gps_fi_lat ?? null,
            gps_fi_lng: data.gps_fi_lng ?? null,
            hores_imputades_facturables: data.hores_imputades_facturables ?? null,
            desviacio_geovalla: Boolean(data.desviacio_geovalla),
            justificacio_geovalla: data.justificacio_geovalla || null,
          });
        } catch {
          throw new Error("PIN incorrecte o error de desxifratge.");
        }
      } else {
        const data = await apiFetch<any>(`/operari/feines/${id}`);
        if (data) {
          const mapped: OrdreDetall = {
            id: String(data.id),
            codi: data.codi || "OT-00",
            titol: data.titol || "Detall de l'Ordre",
            descripcio: data.descripcio,
            client: data.client?.rao_social || "Client",
            estat: data.estat || "PENDENT",
            adreca: data.adreca || "",
            vehicle: data.vehicle,
            linies_picking: data.linies_picking || [],
            eines_assignades: data.eines_assignades || [],
            assets: data.assets || [],
            planol_id: data.planol_id || null,
            planol_titol: data.planol_titol || null,
            planol_codi: data.planol_codi || null,
            planol_tipus_fitxer: data.planol_tipus_fitxer || null,
            hora_inici_real: data.hora_inici_real || null,
            hora_fi_real: data.hora_fi_real || null,
            gps_inici_lat: data.gps_inici_lat ?? null,
            gps_inici_lng: data.gps_inici_lng ?? null,
            gps_fi_lat: data.gps_fi_lat ?? null,
            gps_fi_lng: data.gps_fi_lng ?? null,
            hores_imputades_facturables: data.hores_imputades_facturables ?? null,
            desviacio_geovalla: Boolean(data.desviacio_geovalla),
            justificacio_geovalla: data.justificacio_geovalla || null,
          };
          setOrdre(mapped);
          await carregarEstatFotos();

          // Guardar xifrat a IndexedDB si tenim el PIN
          const sessionPin = sessionStorage.getItem("sevalor_session_pin");
          const saltStr = localStorage.getItem("sevalor_sentinel_salt");
          if (sessionPin && saltStr) {
            const saltBytes = new Uint8Array(saltStr.split(",").map(Number));
            const { cipherTextHex, ivHex } = await encryptWithPin(
              JSON.stringify(data),
              sessionPin,
              saltBytes
            );
            await db.ordres.put({
              id: mapped.id,
              ciphertext: cipherTextHex,
              iv: ivHex,
            });
          }
        }
      }
    } catch (err: any) {
      if (err.message.includes("PIN incorrecte")) {
        setOfflineError("PIN incorrecte. Torna-ho a provar.");
        setShowPinModal(true);
      } else {
        setOrdre(null);
        setOfflineError(err.message);
      }
    } finally {
      if (!showPinModal) setLoading(false);
    }
  };

  const [iniciantTrajecte, setIniciantTrajecte] = useState(false);

  const handleIniciarTrajecte = async () => {
    setIniciantTrajecte(true);
    try {
      await apiFetch(`/operari/feines/${id}/iniciar-trajecte`, {
        method: "PUT",
      });
      setOrdre((prev) => (prev ? { ...prev, estat: "EN_RUTA" } : null));
      alert("Trajecte iniciat! Vehicle i feina en ruta.");
    } catch (e: any) {
      alert("Error iniciant trajecte: " + e.message);
    } finally {
      setIniciantTrajecte(false);
    }
  };

  useEffect(() => {
    loadFeina();
    apiFetch<any>("/auth/me")
      .then((me) => {
        if (me && me.feature_copilot_ia === false) setHasCopilotIa(false);
      })
      .catch(() => {});
  }, [id]);

  const getAssetIcon = (tipus: string) => {
    switch (tipus?.toUpperCase()) {
      case "SERVIDOR":
        return <Server className="w-5 h-5" />;
      case "XARXA":
        return <HardDrive className="w-5 h-5" />;
      case "IOT":
        return <Cpu className="w-5 h-5" />;
      case "MOBILE":
        return <Smartphone className="w-5 h-5" />;
      default:
        return <Settings className="w-5 h-5" />;
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-surface dark:bg-slate-950 text-on-surface dark:text-slate-100 transition-colors p-4 space-y-4">
      {tipusFotoActiva && (
        <CameraCapture
          onCapture={handleCaptureFotoQA}
          onCancel={() => setTipusFotoActiva(null)}
        />
      )}

      {/* Stitch Top Sub-navigation Header */}
      <div className="flex items-center justify-between bg-surface-container-lowest dark:bg-slate-900 p-3 rounded-xl border border-outline-variant/20 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => router.back()}
            className="w-9 h-9 rounded-lg bg-surface-container-low dark:bg-slate-800 hover:bg-surface-container flex items-center justify-center text-primary dark:text-white transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant dark:text-slate-400 block">
              Execució d&apos;Ordre
            </span>
            <h1 className="text-base font-extrabold text-primary dark:text-slate-100 leading-tight">
              Fitxa 360 - {ordre ? ordre.codi : id}
            </h1>
          </div>
        </div>
        {ordre && (
          <span
            className={`text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full border ${
              ordre.estat === "PENDENT"
                ? "bg-amber-500/10 text-amber-600 border-amber-500/20"
                : ordre.estat === "EN_RUTA" || ordre.estat === "EN_CURS"
                ? "bg-secondary-container/15 text-secondary border-secondary-container/30"
                : "bg-primary-fixed text-on-primary-fixed-variant border-primary/20"
            }`}
          >
            {ordre.estat}
          </span>
        )}
      </div>

      {/* AES-GCM Offline Unlock Modal */}
      {showPinModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-container-lowest dark:bg-slate-900 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-4 border border-outline-variant/30">
            <h3 className="text-lg font-extrabold text-primary dark:text-white text-center">
              Desbloqueig Offline
            </h3>
            <p className="text-xs text-on-surface-variant text-center">
              Introdueix el teu PIN per desxifrar les dades locals (AES-GCM 256).
            </p>
            {offlineError && (
              <p className="text-xs text-error font-bold text-center">
                {offlineError}
              </p>
            )}
            <input
              type="password"
              maxLength={4}
              value={offlinePin}
              onChange={(e) =>
                setOfflinePin(e.target.value.replace(/\D/g, ""))
              }
              className="w-full px-4 py-3 text-center text-2xl tracking-widest font-mono font-bold rounded-xl border border-outline-variant dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-secondary-container text-primary dark:text-white"
              placeholder="••••"
            />
            <button
              onClick={() => loadFeina(offlinePin)}
              disabled={offlinePin.length !== 4}
              className="w-full py-3 rounded-xl text-sm font-bold bg-secondary-container hover:brightness-110 text-white transition-all disabled:opacity-50"
            >
              Desxifrar Fitxa
            </button>
            <button
              onClick={() => router.back()}
              className="w-full py-2 rounded-xl text-xs font-bold text-on-surface-variant hover:text-primary dark:hover:text-slate-300 transition-colors"
            >
              Tornar
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-on-surface-variant">
          <Wrench className="w-8 h-8 animate-spin mx-auto mb-2 text-primary" />
          <p className="text-xs font-bold uppercase tracking-wider">
            Carregant dades...
          </p>
        </div>
      ) : !ordre ? (
        <div className="text-center py-12 bg-surface-container-lowest dark:bg-slate-900 rounded-xl shadow-sm border border-outline-variant/30 dark:border-slate-800">
          <FileText className="w-8 h-8 mx-auto text-outline mb-2" />
          <p className="text-sm font-bold text-primary dark:text-slate-300">
            {isOffline
              ? "No s'ha pogut desxifrar la fitxa offline (falta PIN)."
              : "No s'ha trobat l'ordre de treball."}
          </p>
        </div>
      ) : (
        <>
          {/* Capçalera de l'Ordre Stitch Detail Card */}
          <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3 relative overflow-hidden">
            <div className="absolute top-0 left-0 bottom-0 w-1.5 bg-secondary-container" />
            <div className="pl-2 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="font-mono text-xs font-bold text-secondary bg-secondary-container/15 px-2 py-0.5 rounded">
                    {ordre.codi}
                  </span>
                  <h2 className="text-lg font-extrabold text-primary dark:text-slate-100 mt-1.5 leading-snug">
                    {ordre.titol}
                  </h2>
                  <p className="text-xs font-semibold text-on-surface-variant dark:text-slate-400 mt-0.5">
                    {ordre.client}
                  </p>
                </div>
              </div>

              {ordre.descripcio && (
                <div className="p-3 rounded-lg bg-surface-container-low dark:bg-slate-800/60 text-xs text-on-surface dark:text-slate-300 leading-relaxed">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                    Instruccions Tècniques
                  </span>
                  {ordre.descripcio}
                </div>
              )}

              {ordre.adreca && (
                <div className="flex items-center gap-2 text-xs text-on-surface-variant dark:text-slate-400 border-t border-surface-container dark:border-slate-800 pt-2.5">
                  <MapPin className="w-4 h-4 text-secondary shrink-0" />
                  <span className="font-medium">{ordre.adreca}</span>
                </div>
              )}

              {ordre.estat !== "TANCADA" && ordre.estat !== "COMPLERT" && (
                <div className="pt-2 border-t border-surface-container dark:border-slate-800 space-y-2">
                  {(ordre.hora_inici_real || ordre.hora_fi_real) && (
                    <div className="p-2.5 rounded-lg bg-surface-container-low dark:bg-slate-800/70 text-[11px] font-mono space-y-1 border border-outline-variant/20">
                      {ordre.hora_inici_real && (
                        <div className="flex items-center justify-between gap-2 text-on-surface dark:text-slate-200">
                          <span className="font-bold text-secondary">Inici GPS:</span>
                          <span>
                            {new Date(ordre.hora_inici_real).toLocaleTimeString("ca-ES", {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                            {ordre.gps_inici_lat != null && ordre.gps_inici_lng != null
                              ? ` (${Number(ordre.gps_inici_lat).toFixed(4)}, ${Number(ordre.gps_inici_lng).toFixed(4)})`
                              : ""}
                          </span>
                        </div>
                      )}
                      {ordre.hora_fi_real && (
                        <div className="flex items-center justify-between gap-2 text-on-surface dark:text-slate-200">
                          <span className="font-bold text-primary dark:text-sky-400">Final GPS:</span>
                          <span>
                            {new Date(ordre.hora_fi_real).toLocaleTimeString("ca-ES", {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                            {ordre.gps_fi_lat != null && ordre.gps_fi_lng != null
                              ? ` (${Number(ordre.gps_fi_lat).toFixed(4)}, ${Number(ordre.gps_fi_lng).toFixed(4)})`
                              : ""}
                            {ordre.hores_imputades_facturables != null
                              ? ` • ${Number(ordre.hores_imputades_facturables).toFixed(2)}h`
                              : ""}
                          </span>
                        </div>
                      )}
                      {ordre.desviacio_geovalla && (
                        <div className="pt-1.5 border-t border-outline-variant/20 flex items-start gap-1.5 text-amber-600 dark:text-amber-400 font-sans text-[11px] font-medium leading-tight">
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                          <span>
                            <strong>Excepció Geovalla autoritzada:</strong>{" "}
                            {ordre.justificacio_geovalla || "Desviació justificada"}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  <button
                    type="button"
                    data-testid="btn-comencar-feina-gps"
                    disabled={iniciantFeina}
                    onClick={() =>
                      handleMarcarTempsGps(ordre.estat === "EN_CURS" ? "final" : "inici")
                    }
                    className={`w-full min-h-[46px] text-white font-bold text-xs uppercase tracking-wider rounded-lg flex items-center justify-center gap-2 active:scale-95 transition-transform disabled:opacity-50 ${
                      ordre.estat === "EN_CURS" && !ordre.hora_fi_real
                        ? "bg-secondary-container"
                        : "bg-primary"
                    }`}
                  >
                    <MapPin className="w-4 h-4" />
                    {iniciantFeina
                      ? "Verificant Geovalla 50m..."
                      : ordre.estat !== "EN_CURS"
                      ? "Començar Feina (Inici Temps + GPS)"
                      : ordre.hora_fi_real
                      ? "Re-validar Posició GPS Final"
                      : "Finalitzar Temps Feina (Validar GPS Final)"}
                  </button>

                  {requereixJustificacioGPS && (
                    <div
                      data-testid="geofence-justification-box"
                      className="p-3 rounded-lg bg-error-container/25 border border-error space-y-2"
                    >
                      <p className="text-[11px] font-bold text-error uppercase">
                        Fora del radi de 50m de l&apos;obra (FR-005)
                      </p>
                      <textarea
                        value={justificacioGps}
                        onChange={(e) => setJustificacioGps(e.target.value)}
                        placeholder="Motiu de la desviació (ex: accés bloquejat, aparcament a 100m...)"
                        className="w-full p-2 text-xs rounded bg-surface-container-lowest border border-outline-variant text-on-surface"
                        rows={2}
                      />
                      <button
                        type="button"
                        disabled={iniciantFeina || !justificacioGps.trim()}
                        onClick={() => handleMarcarTempsGps(accioPendentGps)}
                        className="w-full py-2 bg-error text-white font-bold text-xs uppercase rounded active:scale-95 transition-transform disabled:opacity-50"
                      >
                        {iniciantFeina
                          ? "Registrant Excepció..."
                          : accioPendentGps === "inici"
                          ? "Confirmar Inici amb Justificació"
                          : "Confirmar Final amb Justificació"}
                      </button>
                    </div>
                  )}

                  {gpsFeedback && (
                    <p className="text-xs font-semibold text-secondary bg-secondary-container/20 p-2 rounded">
                      {gpsFeedback}
                    </p>
                  )}
                  {gpsError && (
                    <p className="text-xs font-semibold text-error bg-error-container/25 p-2 rounded">
                      {gpsError}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Semàfor de 3 Fotografies QA (FR-007) */}
          <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-extrabold uppercase tracking-wider text-primary dark:text-slate-100 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-primary" />
                  Protocol QA de 3 Fotografies
                </h3>
                <p className="text-[11px] text-on-surface-variant dark:text-slate-400">
                  Captura obligatòria en viu amb càmera abans de tancar
                </p>
              </div>
              <span
                data-testid="qa-photos-counter"
                className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full ${
                  estatFotos.protocol_complet
                    ? "bg-secondary-container/20 text-secondary border border-secondary"
                    : "bg-surface-container text-on-surface-variant"
                }`}
              >
                {estatFotos.fotos_pujades.length} / 3
              </span>
            </div>

            <div className="grid grid-cols-1 gap-2">
              {[
                { codi: "INICIAL" as TipusFotoQA, label: "1. Foto Inicial", desc: "Abans d'actuar a la instal·lació" },
                { codi: "INTERMEDIA" as TipusFotoQA, label: "2. Foto Intermèdia", desc: "Durant el muntatge o reparació" },
                { codi: "FINAL" as TipusFotoQA, label: "3. Foto Final", desc: "Resultat acabat i verificat" },
              ].map((item) => {
                const feta = estatFotos.fotos_pujades.includes(item.codi);
                return (
                  <div
                    key={item.codi}
                    data-testid={`qa-slot-${item.codi}`}
                    className={`p-3 rounded-lg border flex items-center justify-between ${
                      feta
                        ? "bg-secondary-container/10 border-secondary-container/40"
                        : "bg-surface-container-low dark:bg-slate-800/50 border-outline-variant/30"
                    }`}
                  >
                    <div>
                      <p className="font-bold text-xs text-on-surface dark:text-slate-200 flex items-center gap-1.5">
                        {feta && <CheckCircle2 className="w-3.5 h-3.5 text-secondary" />}
                        {item.label}
                      </p>
                      <p className="text-[10px] text-on-surface-variant dark:text-slate-400">{item.desc}</p>
                    </div>

                    <button
                      type="button"
                      data-testid={`btn-foto-${item.codi}`}
                      disabled={uploadingFoto}
                      onClick={() => setTipusFotoActiva(item.codi)}
                      className={`min-h-[38px] px-3 py-1.5 rounded-lg font-bold text-xs uppercase flex items-center gap-1.5 active:scale-95 transition-all shadow-sm ${
                        feta
                          ? "bg-surface-container-high text-on-surface dark:bg-slate-700 dark:text-white"
                          : "bg-primary text-white"
                      }`}
                    >
                      <Camera className="w-3.5 h-3.5" />
                      <span>{feta ? "Repetir" : "Capturar"}</span>
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Botons d'Acció Ràpida de l'Operari (Stitch 3-Column Action Grid) */}
          <div className="grid grid-cols-3 gap-2.5">
            <button
              onClick={handleIniciarTrajecte}
              disabled={
                iniciantTrajecte ||
                ordre.estat === "EN_RUTA" ||
                ordre.estat === "EN_CURS"
              }
              className="py-3 px-3 rounded-xl bg-primary-container hover:bg-primary text-white text-xs font-bold flex flex-col items-center justify-center gap-1.5 shadow-sm transition-all disabled:opacity-40 cursor-pointer active:scale-95"
            >
              <Navigation className="w-4 h-4" />
              <span>
                {ordre.estat === "EN_RUTA" ? "En Ruta" : "Iniciar Trajecte"}
              </span>
            </button>

            {hasCopilotIa && (
              <Link
                href={`/operari/feines/${ordre.id}/copilot`}
                className="py-3 px-3 rounded-xl bg-secondary-container hover:brightness-110 text-white text-xs font-bold flex flex-col items-center justify-center gap-1.5 shadow-sm transition-all text-center active:scale-95"
              >
                <Bot className="w-4 h-4" />
                <span>Copilot IA</span>
              </Link>
            )}

            {estatFotos.protocol_complet ? (
              <Link
                href={`/operari/feines/${ordre.id}/tancar`}
                data-testid="btn-anar-tancar-feina"
                className="py-3 px-3 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold flex flex-col items-center justify-center gap-1.5 shadow-sm transition-all text-center active:scale-95"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Tancar Feina</span>
              </Link>
            ) : (
              <button
                type="button"
                data-testid="btn-anar-tancar-feina"
                disabled
                title={`Falten ${estatFotos.falten.length} fotos QA per poder tancar`}
                className="py-3 px-2 rounded-xl bg-surface-container-high dark:bg-slate-800 text-on-surface-variant dark:text-slate-500 text-[11px] font-bold flex flex-col items-center justify-center gap-1 opacity-60 cursor-not-allowed text-center"
              >
                <Lock className="w-4 h-4" />
                <span>Falten {estatFotos.falten.length} Fotos</span>
              </button>
            )}
          </div>

          {/* Vehicle Assignat */}
          {ordre.vehicle && (
            <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-primary-fixed/40 dark:bg-blue-900/20 rounded-xl text-primary dark:text-blue-400">
                  <Truck className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-xs font-extrabold uppercase tracking-wider text-primary dark:text-slate-100">
                    Vehicle Assignat
                  </h4>
                  <p className="text-xs text-on-surface-variant">
                    {ordre.vehicle.model}
                  </p>
                </div>
              </div>
              <span className="font-mono text-xs font-bold bg-surface-container-high dark:bg-slate-800 px-2.5 py-1 rounded-lg text-primary dark:text-slate-300">
                {ordre.vehicle.matricula}
              </span>
            </div>
          )}

          {/* Plànol Tècnic Assignat */}
          {ordre.planol_id ? (
            <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 bg-primary/10 rounded-xl text-primary">
                    <Layers className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-extrabold uppercase tracking-wider text-primary dark:text-slate-100">
                      Plànol Tècnic Assignat
                    </h4>
                    <p className="text-[11px] font-mono text-secondary font-bold">
                      {ordre.planol_codi || "PLN"} • {ordre.planol_tipus_fitxer || "DOCUMENT"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <Link
                    href={`/operari/planols?planol=${ordre.planol_id}&ordre_id=${ordre.id}`}
                    className="px-3 py-1.5 rounded-lg bg-secondary-container hover:brightness-110 text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm active:scale-95 cursor-pointer"
                  >
                    <Layers className="w-3.5 h-3.5" />
                    <span>Editar As-Built</span>
                  </Link>
                  <a
                    href={`/api/v1/operari/planols/${ordre.planol_id}/fitxer`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2.5 py-1.5 rounded-lg border border-outline-variant/60 bg-surface-container-lowest text-on-surface hover:bg-surface-container text-xs font-semibold flex items-center gap-1 transition-all"
                  >
                    <ExternalLink className="w-3 h-3 text-primary" />
                    <span>PDF</span>
                  </a>
                </div>
              </div>
              <div className="p-2.5 bg-surface-container-low dark:bg-slate-800/60 rounded-lg text-xs font-medium text-slate-800 dark:text-slate-200">
                {ordre.planol_titol || "Plànol d'emplaçament o instal·lació d'obra"}
              </div>
            </div>
          ) : null}

          {/* Materials de Picking */}
          <div className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-primary dark:text-slate-300 flex items-center gap-1.5">
                <Package className="w-4 h-4 text-secondary" />
                Materials Assignats ({ordre.linies_picking?.length || 0})
              </h3>
              <Link
                href="/operari/material"
                className="text-[11px] font-bold text-secondary hover:underline"
              >
                Anar a Picking →
              </Link>
            </div>
            {!ordre.linies_picking || ordre.linies_picking.length === 0 ? (
              <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-dashed border-outline-variant/40 dark:border-slate-800 text-center text-xs text-on-surface-variant">
                Cap material de picking vinculat a aquesta feina.
              </div>
            ) : (
              <div className="space-y-2">
                {ordre.linies_picking.map((linia) => (
                  <div
                    key={linia.id}
                    className="bg-surface-container-lowest dark:bg-slate-900 p-3.5 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm flex items-center justify-between"
                  >
                    <div>
                      <h4 className="text-xs font-bold text-primary dark:text-slate-100">
                        {linia.article_nom}
                      </h4>
                      <p className="text-[11px] font-mono text-on-surface-variant mt-0.5">
                        Carregat: {linia.quantitat_carregada_pick_in} /{" "}
                        {linia.quantitat_prevista}
                      </p>
                    </div>
                    <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-lg bg-surface-container-low dark:bg-slate-800 text-primary dark:text-slate-300">
                      {linia.quantitat_prevista} uts
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Eines i Equips en Custòdia */}
          <div className="space-y-2">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-primary dark:text-slate-300 px-1 flex items-center gap-1.5">
              <Wrench className="w-4 h-4 text-amber-500" />
              Eines en Custòdia ({ordre.eines_assignades?.length || 0})
            </h3>
            {!ordre.eines_assignades || ordre.eines_assignades.length === 0 ? (
              <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-dashed border-outline-variant/40 dark:border-slate-800 text-center text-xs text-on-surface-variant">
                Cap eina o maquinària en custòdia per a aquest operari.
              </div>
            ) : (
              <div className="space-y-2">
                {ordre.eines_assignades.map((eina) => (
                  <div
                    key={eina.id}
                    className="bg-surface-container-lowest dark:bg-slate-900 p-3.5 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm flex items-center justify-between"
                  >
                    <div>
                      <h4 className="text-xs font-bold text-primary dark:text-slate-100">
                        {eina.nom}
                      </h4>
                      <p className="text-[10px] font-mono text-on-surface-variant mt-0.5">
                        {eina.model || "Standard"} • SN: {eina.numero_serie}
                      </p>
                    </div>
                    <span className="text-[10px] font-bold px-2.5 py-1 rounded-full bg-secondary-container/15 text-secondary border border-secondary-container/30">
                      {eina.estat}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Màquines i Actius de la Finca */}
          {ordre.assets && ordre.assets.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-primary dark:text-slate-300 px-1">
                Màquines i Actius de la Finca ({ordre.assets.length})
              </h3>
              <div className="space-y-2">
                {ordre.assets.map((asset) => (
                  <div
                    key={asset.id}
                    className="bg-surface-container-lowest dark:bg-slate-900 p-3.5 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm flex items-center gap-3"
                  >
                    <div className="p-2 bg-surface-container-low dark:bg-slate-800 rounded-lg text-primary dark:text-slate-400">
                      {getAssetIcon(asset.tipus)}
                    </div>
                    <div className="flex-1">
                      <h4 className="text-xs font-bold text-primary dark:text-slate-100">
                        {asset.nom}
                      </h4>
                      <p className="text-[10px] font-mono text-on-surface-variant">
                        {asset.model} • SN: {asset.num_serie}
                      </p>
                    </div>
                    <span className="text-[9px] font-bold px-2 py-1 rounded bg-surface-container-low dark:bg-slate-800 text-on-surface-variant dark:text-slate-300">
                      {asset.estat}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
