"use client";

import React, { useState } from "react";
import { db } from "@/lib/offline/db";
import CameraInput from "@/components/CameraInput";

export default function TiquetScanner() {
  const [preview, setPreview] = useState<string | null>(null);
  const [amount, setAmount] = useState<string>("");

  const handleCameraCapture = (blob: Blob) => {
    const reader = new FileReader();
    reader.onload = (ev) => {
      if (ev.target?.result) {
        setPreview(ev.target.result as string);
      }
    };
    reader.readAsDataURL(blob);
  };

  const handleSave = async () => {
    if (!preview) return;
    
    // Add to sync queue for backend to process OCR
    await db.sync_queue.add({
      action: "CREAR_TIQUET",
      payload: {
        imatge_base64: preview,
        import_manual: amount ? parseFloat(amount) : null,
        data_captura: new Date().toISOString(),
      },
      status: "pending",
      createdAt: Date.now(),
    });

    // Reset
    setPreview(null);
    setAmount("");
    
    alert("Tiquet desat a la cua de sincronització (Offline).");
  };

  return (
    <div className="flex flex-col items-center gap-4 p-4 border rounded shadow-sm bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
      <h2 className="text-lg font-semibold text-[var(--color-primary)]">Escàner de Tiquets</h2>
      
      {!preview ? (
        <div className="flex flex-col items-center gap-3 w-full">
          <p className="text-xs text-gray-500 text-center">
            Captura la foto del tiquet de combustible directament amb la càmera en viu (Bloqueig de galeria).
          </p>
          <CameraInput 
            onCapture={handleCameraCapture} 
            label="Capturar Tiquet (Càmera en Viu)" 
          />
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 w-full">
          <img src={preview} alt="Tiquet preview" className="max-h-64 object-contain rounded border border-slate-300 dark:border-slate-700" />
          
          <div className="w-full">
            <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
              Import Total (€) (Opcional - L'OCR l'extraurà automàticament)
            </label>
            <input 
              type="number" 
              step="0.01" 
              value={amount}
              onChange={e => setAmount(e.target.value)}
              className="w-full border rounded-lg p-2 text-sm bg-slate-50 dark:bg-slate-800 border-slate-300 dark:border-slate-700"
              placeholder="Ex: 45.50"
            />
          </div>

          <div className="flex gap-2 w-full mt-2">
            <button 
              onClick={() => setPreview(null)}
              className="flex-1 px-4 py-2 bg-gray-200 dark:bg-slate-800 text-gray-800 dark:text-gray-200 text-xs font-bold rounded-lg hover:bg-gray-300 transition-colors"
            >
              Cancel·lar
            </button>
            <button 
              onClick={handleSave}
              className="flex-1 px-4 py-2 text-white text-xs font-bold rounded-lg hover:opacity-90 transition-opacity"
              style={{ backgroundColor: "var(--color-secondary, #10b981)" }}
            >
              Desar Tiquet
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
