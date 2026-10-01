"use client";

import React, { useState, useRef } from "react";
import { db } from "@/lib/offline/db";

export default function TiquetScanner() {
  const [preview, setPreview] = useState<string | null>(null);
  const [amount, setAmount] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (ev) => {
      if (ev.target?.result) {
        setPreview(ev.target.result as string);
      }
    };
    reader.readAsDataURL(file);
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
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    
    alert("Tiquet desat a la cua de sincronització (Offline).");
  };

  return (
    <div className="flex flex-col items-center gap-4 p-4 border rounded shadow-sm bg-white">
      <h2 className="text-lg font-semibold text-[var(--color-primary)]">Escàner de Tiquets</h2>
      
      {!preview ? (
        <div className="flex flex-col items-center gap-2">
          <p className="text-sm text-gray-500">Captura o puja la foto del tiquet de combustible.</p>
          <input 
            type="file" 
            accept="image/*" 
            capture="environment" 
            ref={fileInputRef}
            onChange={handleCapture}
            className="hidden"
          />
          <button 
            onClick={() => fileInputRef.current?.click()}
            className="px-4 py-2 bg-[var(--color-primary)] text-white rounded hover:opacity-90"
            style={{ backgroundColor: "var(--color-primary, #0284c7)" }}
          >
            Fer Foto / Pujar
          </button>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 w-full">
          <img src={preview} alt="Tiquet preview" className="max-h-64 object-contain rounded border" />
          
          <div className="w-full">
            <label className="block text-sm text-gray-700 mb-1">Import Total (€) (Opcional - L'OCR l'extraurà automàticament)</label>
            <input 
              type="number" 
              step="0.01" 
              value={amount}
              onChange={e => setAmount(e.target.value)}
              className="w-full border rounded p-2"
              placeholder="Ex: 45.50"
            />
          </div>

          <div className="flex gap-2 w-full mt-2">
            <button 
              onClick={() => setPreview(null)}
              className="flex-1 px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
            >
              Cancel·lar
            </button>
            <button 
              onClick={handleSave}
              className="flex-1 px-4 py-2 text-white rounded hover:opacity-90"
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
