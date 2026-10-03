"use client";

import React, { useState } from "react";
import { Camera, CheckCircle2 } from "lucide-react";
import CameraCapture from "./CameraCapture";

interface CameraInputProps {
  onCapture: (blob: Blob) => void;
  label?: string;
  captured?: boolean;
}

export default function CameraInput({ onCapture, label = "Capturar Foto", captured = false }: CameraInputProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className={`w-full flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed transition-colors ${
          captured 
            ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400" 
            : "border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
        }`}
      >
        {captured ? <CheckCircle2 className="w-8 h-8 mb-2" /> : <Camera className="w-8 h-8 mb-2" />}
        <span className="text-sm font-bold">{captured ? "Capturat ✓" : label}</span>
      </button>

      {isOpen && (
        <CameraCapture 
          onCapture={(blob) => {
            onCapture(blob);
            setIsOpen(false);
          }} 
          onCancel={() => setIsOpen(false)} 
        />
      )}
    </>
  );
}
