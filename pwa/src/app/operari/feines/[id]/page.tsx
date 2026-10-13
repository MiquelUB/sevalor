"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Settings, Cpu, HardDrive, Server, Smartphone, Wrench, FileText, Bot, Truck, Package, Navigation, CheckCircle2, MapPin } from "lucide-react";
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
        if (!saltStr) throw new Error("No s'ha trobat la sal criptogràfica del dispositiu.");
        const saltBytes = new Uint8Array(saltStr.split(",").map(Number));

        try {
          const decryptedStr = await decryptWithPin(record.ciphertext, record.iv, storedPin, saltBytes);
          const data = JSON.parse(decryptedStr);
          
          // Si el PIN era correcte, el guardem en sessió
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
        } catch (decErr) {
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
            const { cipherTextHex, ivHex } = await encryptWithPin(JSON.stringify(data), sessionPin, saltBytes);
            await db.ordres.put({ id: mapped.id, ciphertext: cipherTextHex, iv: ivHex });
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
      await apiFetch(`/operari/feines/${id}/iniciar-trajecte`, { method: "PUT" });
      setOrdre(prev => prev ? { ...prev, estat: "EN_RUTA" } : null);
      alert("Trajecte iniciat! Vehicle i feina en ruta.");
    } catch (e: any) {
      alert("Error iniciant trajecte: " + e.message);
    } finally {
      setIniciantTrajecte(false);
    }
  };

  useEffect(() => {
    loadFeina();
  }, [id]);

  const getAssetIcon = (tipus: string) => {
    switch(tipus?.toUpperCase()) {
      case "SERVIDOR": return <Server className="w-5 h-5" />;
      case "XARXA": return <HardDrive className="w-5 h-5" />;
      case "IOT": return <Cpu className="w-5 h-5" />;
      case "MOBILE": return <Smartphone className="w-5 h-5" />;
      default: return <Settings className="w-5 h-5" />;
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors p-4 space-y-4">
      <div className="flex items-center gap-3 mb-2">
        <button
          onClick={() => router.back()}
          className="p-2 rounded-full hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">
          Fitxa 360 - {ordre ? ordre.codi : id}
        </h1>
      </div>

      
      {showPinModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white text-center">Desbloqueig Offline</h3>
            <p className="text-xs text-slate-500 text-center">
              Introdueix el teu PIN per desxifrar les dades locals (AES-GCM 256).
            </p>
            {offlineError && <p className="text-xs text-red-500 font-bold text-center">{offlineError}</p>}
            <input
              type="password"
              maxLength={4}
              value={offlinePin}
              onChange={(e) => setOfflinePin(e.target.value.replace(/\D/g, ''))}
              className="w-full px-4 py-3 text-center text-2xl tracking-widest font-mono font-bold rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 text-slate-900 dark:text-white"
              placeholder="••••"
            />
            <button
              onClick={() => loadFeina(offlinePin)}
              disabled={offlinePin.length !== 4}
              className="w-full py-3 rounded-xl text-sm font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-colors disabled:opacity-50"
            >
              Desxifrar Fitxa
            </button>
            <button
              onClick={() => router.back()}
              className="w-full py-2 rounded-xl text-xs font-bold text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
            >
              Tornar
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-10 text-slate-400">
          <Wrench className="w-8 h-8 animate-spin mx-auto mb-2" />
          <p className="text-xs">Carregant dades...</p>
        </div>
      ) : !ordre ? (
        <div className="text-center py-10 bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800">
          <FileText className="w-8 h-8 mx-auto text-slate-400 mb-2" />
          <p className="text-sm font-bold text-slate-700 dark:text-slate-300">
            {isOffline ? "No s'ha pogut desxifrar la fitxa offline (falta PIN)." : "No s'ha trobat l'ordre de treball."}
          </p>
        </div>
      ) : (
        <>
          {/* Capçalera de l'Ordre */}
          <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
            <div className="flex items-start justify-between">
              <div>
                <span className="font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 px-2 py-0.5 rounded">
                  {ordre.codi}
                </span>
                <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mt-1">{ordre.titol}</h2>
                <p className="text-xs text-slate-500">{ordre.client}</p>
              </div>
              <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${
                ordre.estat === "PENDENT"
                  ? "bg-amber-500/10 text-amber-600 border-amber-500/20"
                  : ordre.estat === "EN_RUTA" || ordre.estat === "EN_CURS"
                  ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                  : "bg-blue-500/10 text-blue-600 border-blue-500/20"
              }`}>
                {ordre.estat}
              </span>
            </div>

            {ordre.adreca && (
              <div className="flex items-center gap-1.5 text-xs text-slate-500 border-t border-slate-100 dark:border-slate-800 pt-2">
                <MapPin className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                <span>{ordre.adreca}</span>
              </div>
            )}
          </div>

          {/* Botons d'Acció Ràpida de l'Operari */}
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={handleIniciarTrajecte}
              disabled={iniciantTrajecte || ordre.estat === "EN_RUTA" || ordre.estat === "EN_CURS"}
              className="py-2.5 px-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold flex flex-col items-center justify-center gap-1 shadow transition-colors disabled:opacity-40 cursor-pointer"
            >
              <Navigation className="w-4 h-4" />
              <span>{ordre.estat === "EN_RUTA" ? "En Ruta" : "Iniciar Trajecte"}</span>
            </button>

            <Link
              href={`/operari/feines/${ordre.id}/copilot`}
              className="py-2.5 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex flex-col items-center justify-center gap-1 shadow transition-colors text-center"
            >
              <Bot className="w-4 h-4" />
              <span>Copilot IA</span>
            </Link>

            <Link
              href={`/operari/feines/${ordre.id}/tancar`}
              className="py-2.5 px-3 rounded-xl bg-slate-800 dark:bg-slate-100 hover:bg-slate-700 dark:hover:bg-white text-white dark:text-slate-900 text-xs font-bold flex flex-col items-center justify-center gap-1 shadow transition-colors text-center"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Tancar Feina</span>
            </Link>
          </div>

          {/* Vehicle Assignat */}
          {ordre.vehicle && (
            <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-blue-600 dark:text-blue-400">
                  <Truck className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100">Vehicle Assignat</h4>
                  <p className="text-xs text-slate-500">{ordre.vehicle.model}</p>
                </div>
              </div>
              <span className="font-mono text-xs font-bold bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded text-slate-700 dark:text-slate-300">
                {ordre.vehicle.matricula}
              </span>
            </div>
          )}

          {/* Materials de Picking */}
          <div className="space-y-2">
            <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300 px-1 flex items-center gap-1.5">
              <Package className="w-4 h-4 text-emerald-500" />
              Materials Assignats ({ordre.linies_picking?.length || 0})
            </h3>
            {(!ordre.linies_picking || ordre.linies_picking.length === 0) ? (
              <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-center text-xs text-slate-400">
                Cap material de picking vinculat a aquesta feina.
              </div>
            ) : (
              <div className="space-y-2">
                {ordre.linies_picking.map((linia) => (
                  <div key={linia.id} className="bg-white dark:bg-slate-900 p-3 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100">{linia.article_nom}</h4>
                      <p className="text-[10px] text-slate-400">Carregat: {linia.quantitat_carregada_pick_in} / {linia.quantitat_prevista}</p>
                    </div>
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                      {linia.quantitat_prevista} uts
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Eines i Equips en Custòdia */}
          <div className="space-y-2">
            <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300 px-1 flex items-center gap-1.5">
              <Wrench className="w-4 h-4 text-amber-500" />
              Eines en Custòdia ({ordre.eines_assignades?.length || 0})
            </h3>
            {(!ordre.eines_assignades || ordre.eines_assignades.length === 0) ? (
              <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-center text-xs text-slate-400">
                Cap eina o maquinària en custòdia per a aquest operari.
              </div>
            ) : (
              <div className="space-y-2">
                {ordre.eines_assignades.map((eina) => (
                  <div key={eina.id} className="bg-white dark:bg-slate-900 p-3 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100">{eina.nom}</h4>
                      <p className="text-[10px] font-mono text-slate-400">{eina.model || "Standard"} • SN: {eina.numero_serie}</p>
                    </div>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
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
              <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300 px-1">
                Màquines i Actius de la Finca ({ordre.assets.length})
              </h3>
              <div className="space-y-2">
                {ordre.assets.map(asset => (
                  <div key={asset.id} className="bg-white dark:bg-slate-900 p-3 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-3">
                    <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-lg text-slate-500 dark:text-slate-400">
                      {getAssetIcon(asset.tipus)}
                    </div>
                    <div className="flex-1">
                      <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100">{asset.nom}</h4>
                      <p className="text-[10px] font-mono text-slate-500">{asset.model} • SN: {asset.num_serie}</p>
                    </div>
                    <span className="text-[9px] font-bold px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
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
