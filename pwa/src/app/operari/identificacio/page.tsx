"use client";

import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { getApiBaseUrl } from "@/lib/api";

export default function IdentificacioPage() {
  const [operariId, setOperariId] = useState<string | null>(null);
  const [nom, setNom] = useState<string>("");

  useEffect(() => {
    // Obtenir user des de localStorage
    const userStr = localStorage.getItem("sevalor_user");
    if (userStr) {
      try {
        const user = JSON.parse(userStr);
        setOperariId(user.id);
        setNom(`${user.nom || ''} ${user.cognoms || ''}`.trim());
      } catch (e) {}
    }
  }, []);

  if (!operariId) {
    return <div className="p-4 text-center mt-20">Carregant identificació...</div>;
  }

  // Generem URL per l'endpoint públic
  const baseUrl = getApiBaseUrl().replace('/api/v1', '');
  const publicUrl = `${baseUrl}/api/v1/public/identificacio/${operariId}`;

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-64px)] p-6 bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <div className="bg-white dark:bg-slate-900 p-8 rounded-2xl shadow-xl flex flex-col items-center w-full max-w-sm border border-slate-200 dark:border-slate-800">
        <h1 className="text-2xl font-bold mb-2 text-center text-slate-900 dark:text-slate-100">Acreditació CAE</h1>
        <p className="text-slate-500 dark:text-slate-400 text-center mb-8 text-sm">
          Mostreu aquest codi a l'inspector o client per validar la vostra identitat i documentació d'empresa.
        </p>

        <div className="bg-white p-4 border-4 border-emerald-500 dark:border-emerald-600 rounded-xl mb-6 shadow-sm">
          <QRCodeSVG 
            value={publicUrl} 
            size={200}
            level="H"
            includeMargin={true}
          />
        </div>

        <h2 className="text-xl font-semibold text-slate-800 dark:text-slate-200">{nom}</h2>
        <div className="mt-4 inline-flex items-center px-4 py-1.5 rounded-full text-sm font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
          <span className="w-2.5 h-2.5 mr-2.5 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
          Acreditació Activa
        </div>
        <div className="mt-8 text-[10px] text-slate-400 uppercase tracking-widest font-semibold text-center">
          Escanegeu per descarregar <br/>Certificats i PDF de l'empresa
        </div>
      </div>
    </div>
  );
}
