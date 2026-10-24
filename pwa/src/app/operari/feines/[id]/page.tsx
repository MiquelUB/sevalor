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
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { db } from "@/lib/offline/db";
import { encryptWithPin, decryptWithPin } from "@/lib/crypto";

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
          };
          setOrdre(mapped);

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

            <Link
              href={`/operari/feines/${ordre.id}/tancar`}
              className="py-3 px-3 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold flex flex-col items-center justify-center gap-1.5 shadow-sm transition-all text-center active:scale-95"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Tancar Feina</span>
            </Link>
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
