"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import SignaturePad from "@/components/operari/SignaturePad";
import TiquetScanner from "@/components/operari/TiquetScanner";
import { db } from "@/lib/offline/db";

export default function TancarFeinaPage() {
  const params = useParams();
  const router = useRouter();
  const [signatureSaved, setSignatureSaved] = useState(false);

  const feinaId = params.id as string;

  const handleSaveSignature = async (base64Signature: string) => {
    // Save to sync_queue
    await db.sync_queue.add({
      action: "TANCAR_ORDRE",
      payload: {
        ordre_id: feinaId,
        signatura_base64: base64Signature,
        data_tancament: new Date().toISOString(),
      },
      status: "pending",
      createdAt: Date.now(),
    });

    setSignatureSaved(true);
    alert("Signatura desada. Sincronització pendent a la cua.");
  };

  const handleFinalize = () => {
    router.push("/operari/feines");
  };

  return (
    <div className="p-4 max-w-lg mx-auto flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-[var(--color-primary)]">
        Tancament de Jornada / Feina
      </h1>
      
      <p className="text-sm text-gray-600">
        Per favor, escaneja els tiquets de combustible necessaris abans de signar el tancament de la feina.
      </p>

      <div className="bg-gray-50 p-4 rounded-lg border">
        <TiquetScanner />
      </div>

      <div className="bg-gray-50 p-4 rounded-lg border mt-4">
        {!signatureSaved ? (
          <SignaturePad onSave={handleSaveSignature} />
        ) : (
          <div className="text-center p-6 text-green-700 bg-green-50 rounded border border-green-200">
            <svg className="w-12 h-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
            </svg>
            <h3 className="font-semibold text-lg">Signatura desada correctament</h3>
            <p className="text-sm mt-1">La feina s'ha tancat i sincronitzat (o s'ha posat a la cua).</p>
          </div>
        )}
      </div>

      {signatureSaved && (
        <button
          onClick={handleFinalize}
          className="w-full mt-4 px-4 py-3 text-white font-medium rounded shadow-sm hover:opacity-90"
          style={{ backgroundColor: "var(--color-primary, #0284c7)" }}
        >
          Tornar a Feines
        </button>
      )}
    </div>
  );
}
