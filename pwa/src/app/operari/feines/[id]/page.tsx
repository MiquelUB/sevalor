"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Settings, Cpu, HardDrive, Server, Smartphone, Wrench, FileText } from "lucide-react";
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

interface OrdreDetall {
  id: string;
  codi: string;
  titol: string;
  client: string;
  estat: string;
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
            client: data.client?.rao_social || "Client",
            estat: data.estat || "PENDENT",
            assets: data.assets || [],
          });
        } catch (decErr) {
          throw new Error("PIN incorrecte o error de desxifratge.");
        }

      } else {
        const data = await apiFetch<any>(`/operari/feines/${id}`);
        if (data) {
          const mapped = {
            id: String(data.id),
            codi: data.codi || "OT-00",
            titol: data.titol || "Detall de l'Ordre",
            client: data.client?.rao_social || "Client",
            estat: data.estat || "PENDENT",
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
          <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100">{ordre.titol}</h2>
            <p className="text-xs text-slate-500 mt-1">{ordre.client} • {ordre.estat}</p>
          </div>

          <h3 className="text-sm font-bold mt-4 mb-2 text-slate-700 dark:text-slate-300 px-1">
            Màquines i Actius Assignats
          </h3>
          
          {ordre.assets.length === 0 ? (
            <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 text-center shadow-sm">
              <Settings className="w-8 h-8 mx-auto text-slate-300 dark:text-slate-700 mb-2" />
              <p className="text-sm font-bold text-slate-600 dark:text-slate-400">Cap màquina associada</p>
            </div>
          ) : (
            <div className="space-y-3">
              {ordre.assets.map(asset => (
                <div key={asset.id} className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-3">
                  <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-lg text-slate-500 dark:text-slate-400">
                    {getAssetIcon(asset.tipus)}
                  </div>
                  <div className="flex-1">
                    <h4 className="text-sm font-bold text-slate-800 dark:text-slate-100">{asset.nom}</h4>
                    <p className="text-[10px] font-mono text-slate-500">{asset.model} • SN: {asset.num_serie}</p>
                  </div>
                  <span className="text-[9px] font-bold px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                    {asset.estat}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
