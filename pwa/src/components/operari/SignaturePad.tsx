"use client";

import React, { useRef, useState, useEffect } from "react";

interface SignaturePadProps {
  onSave: (base64Signature: string) => void;
  onClear?: () => void;
}

export default function SignaturePad({ onSave, onClear }: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasDrawn, setHasDrawn] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.strokeStyle = "#022448";
        ctx.lineWidth = 2.5;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
      }
    }
  }, []);

  const getCoordinates = (
    e: React.MouseEvent | React.TouchEvent | MouseEvent | TouchEvent
  ) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };

    const rect = canvas.getBoundingClientRect();
    if ("touches" in e) {
      return {
        x: e.touches[0].clientX - rect.left,
        y: e.touches[0].clientY - rect.top,
      };
    } else {
      return {
        x: (e as React.MouseEvent).clientX - rect.left,
        y: (e as React.MouseEvent).clientY - rect.top,
      };
    }
  };

  const startDrawing = (e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    setIsDrawing(true);
    setHasDrawn(true);
    const coords = getCoordinates(e);
    const ctx = canvasRef.current?.getContext("2d");
    if (ctx) {
      ctx.beginPath();
      ctx.moveTo(coords.x, coords.y);
    }
  };

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    if (!isDrawing) return;
    const coords = getCoordinates(e);
    const ctx = canvasRef.current?.getContext("2d");
    if (ctx) {
      ctx.lineTo(coords.x, coords.y);
      ctx.stroke();
    }
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const handleClear = () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (canvas && ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.beginPath();
    }
    setHasDrawn(false);
    if (onClear) onClear();
  };

  const handleSave = () => {
    const canvas = canvasRef.current;
    if (canvas) {
      const dataUrl = canvas.toDataURL("image/png");
      onSave(dataUrl);
    }
  };

  return (
    <div className="flex flex-col items-center gap-3 w-full max-w-md mx-auto">
      <div className="flex items-center justify-between w-full px-1">
        <h3 className="text-xs font-extrabold uppercase tracking-wider text-primary dark:text-white flex items-center gap-1.5">
          <span className="material-symbols-outlined text-base text-secondary">
            draw
          </span>
          Signatura del Client / Operari
        </h3>
        <span className="text-[10px] font-mono text-on-surface-variant">
          Traç Digital Certificat
        </span>
      </div>

      {/* Stitch Tactile Signature Canvas Container with Corner Marks */}
      <div className="relative border-2 border-dashed border-outline-variant dark:border-slate-700 rounded-xl w-full overflow-hidden bg-surface-container-lowest dark:bg-slate-950 touch-none shadow-inner">
        {/* Corner Reference Marks */}
        <div className="absolute top-2 left-2 w-3 h-3 border-t-2 border-l-2 border-primary/40 pointer-events-none" />
        <div className="absolute top-2 right-2 w-3 h-3 border-t-2 border-r-2 border-primary/40 pointer-events-none" />
        <div className="absolute bottom-2 left-2 w-3 h-3 border-b-2 border-l-2 border-primary/40 pointer-events-none" />
        <div className="absolute bottom-2 right-2 w-3 h-3 border-b-2 border-r-2 border-primary/40 pointer-events-none" />

        {/* Baseline & Watermark */}
        {!hasDrawn && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none select-none opacity-40">
            <span className="material-symbols-outlined text-3xl text-outline mb-1">
              gesture
            </span>
            <span className="text-xs font-bold uppercase tracking-widest text-outline">
              Signa aquí dins del requadre
            </span>
          </div>
        )}
        <div className="absolute bottom-8 left-6 right-6 border-b border-outline-variant/40 pointer-events-none" />

        <canvas
          ref={canvasRef}
          width={350}
          height={200}
          className="w-full h-[200px] cursor-crosshair touch-none relative z-10"
          onMouseDown={startDrawing}
          onMouseMove={draw}
          onMouseUp={stopDrawing}
          onMouseLeave={stopDrawing}
          onTouchStart={startDrawing}
          onTouchMove={draw}
          onTouchEnd={stopDrawing}
        />
      </div>

      <div className="flex gap-2.5 w-full mt-1">
        <button
          type="button"
          onClick={handleClear}
          className="flex-1 px-4 py-3 bg-surface-container-high dark:bg-slate-800 text-on-surface dark:text-slate-200 rounded-xl text-xs font-bold uppercase tracking-wider hover:bg-surface-container-highest transition-colors flex items-center justify-center gap-1.5"
        >
          <span className="material-symbols-outlined text-sm">ink_eraser</span>
          Netejar
        </button>
        <button
          type="button"
          onClick={handleSave}
          className="flex-1 px-4 py-3 bg-secondary-container text-white rounded-xl text-xs font-bold uppercase tracking-wider hover:brightness-110 transition-all shadow-md flex items-center justify-center gap-1.5"
        >
          <span className="material-symbols-outlined text-sm">verified</span>
          Guardar Signatura
        </button>
      </div>
    </div>
  );
}
