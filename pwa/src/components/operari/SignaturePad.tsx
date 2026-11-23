"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";

interface SignaturePadProps {
  onSave: (base64Signature: string) => void;
  onClear?: () => void;
  disabled?: boolean;
}

export default function SignaturePad({ onSave, onClear, disabled = false }: SignaturePadProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasDrawn, setHasDrawn] = useState(false);

  const applyStrokeStyle = useCallback((ctx: CanvasRenderingContext2D) => {
    const computed =
      typeof window !== "undefined"
        ? getComputedStyle(document.documentElement).getPropertyValue("--color-primary").trim()
        : "";
    ctx.strokeStyle = computed ? `hsl(${computed})` : "#0f172a";
    ctx.lineWidth = 2.6;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }, []);

  const syncCanvasDimensions = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const cssWidth = Math.max(240, Math.floor(container.clientWidth));
    const cssHeight = 200;
    const dpr = typeof window !== "undefined" ? Math.min(window.devicePixelRatio || 1, 2) : 1;
    const targetW = Math.floor(cssWidth * dpr);
    const targetH = Math.floor(cssHeight * dpr);

    if (canvas.width === targetW && canvas.height === targetH) {
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        applyStrokeStyle(ctx);
      }
      return;
    }

    // Preservar el traç existent si es redimensiona el viewport
    let prevSnapshot: HTMLCanvasElement | null = null;
    if (canvas.width > 0 && canvas.height > 0) {
      prevSnapshot = document.createElement("canvas");
      prevSnapshot.width = canvas.width;
      prevSnapshot.height = canvas.height;
      const snapCtx = prevSnapshot.getContext("2d");
      if (snapCtx) snapCtx.drawImage(canvas, 0, 0);
    }

    canvas.width = targetW;
    canvas.height = targetH;

    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      if (prevSnapshot) {
        ctx.drawImage(prevSnapshot, 0, 0, targetW, targetH);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      applyStrokeStyle(ctx);
    }
  }, [applyStrokeStyle]);

  useEffect(() => {
    syncCanvasDimensions();
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver(() => {
      syncCanvasDimensions();
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [syncCanvasDimensions]);

  const getCoordinates = (
    e: React.MouseEvent | React.TouchEvent | MouseEvent | TouchEvent
  ) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };

    const rect = canvas.getBoundingClientRect();
    if ("touches" in e && e.touches.length > 0) {
      return {
        x: e.touches[0].clientX - rect.left,
        y: e.touches[0].clientY - rect.top,
      };
    }
    const mouseEvt = e as React.MouseEvent;
    return {
      x: mouseEvt.clientX - rect.left,
      y: mouseEvt.clientY - rect.top,
    };
  };

  const startDrawing = (e: React.MouseEvent | React.TouchEvent) => {
    if (disabled) return;
    if ("touches" in e) {
      e.preventDefault();
    }
    setIsDrawing(true);
    setHasDrawn(true);
    const coords = getCoordinates(e);
    const ctx = canvasRef.current?.getContext("2d");
    if (ctx) {
      applyStrokeStyle(ctx);
      ctx.beginPath();
      ctx.moveTo(coords.x, coords.y);
      // Punt inicial per a traços molt curts o tocs d'un sol dit
      ctx.lineTo(coords.x + 0.1, coords.y + 0.1);
      ctx.stroke();
    }
  };

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    if (disabled || !isDrawing) return;
    if ("touches" in e) {
      e.preventDefault();
    }
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
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.restore();
      ctx.beginPath();
      applyStrokeStyle(ctx);
    }
    setHasDrawn(false);
    if (onClear) onClear();
  };

  const handleSave = () => {
    const canvas = canvasRef.current;
    if (!canvas || !hasDrawn || disabled) return;
    // Compositar sobre fons blanc per garantir llegibilitat a la Fulla 360° i PDFs
    const exportCanvas = document.createElement("canvas");
    exportCanvas.width = canvas.width;
    exportCanvas.height = canvas.height;
    const exportCtx = exportCanvas.getContext("2d");
    if (exportCtx) {
      exportCtx.fillStyle = "#ffffff";
      exportCtx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
      exportCtx.drawImage(canvas, 0, 0);
      onSave(exportCanvas.toDataURL("image/png"));
      return;
    }
    onSave(canvas.toDataURL("image/png"));
  };

  return (
    <div className="flex flex-col items-center gap-3 w-full max-w-md mx-auto">
      <div className="flex items-center justify-between w-full px-1">
        <h3 className="text-xs font-extrabold uppercase tracking-wider text-primary dark:text-white flex items-center gap-1.5">
          <span className="material-symbols-outlined text-base text-secondary">
            draw
          </span>
          Signatura del Client / Receptor
        </h3>
        <span className="text-[10px] font-mono text-on-surface-variant">
          Traç Digital Certificat
        </span>
      </div>

      {/* Stitch Tactile Signature Canvas Container with Corner Marks */}
      <div
        ref={containerRef}
        className="relative border-2 border-dashed border-outline-variant dark:border-slate-600 rounded-xl w-full overflow-hidden bg-white touch-none shadow-inner"
      >
        {/* Corner Reference Marks */}
        <div className="absolute top-2 left-2 w-3 h-3 border-t-2 border-l-2 border-primary/40 pointer-events-none" />
        <div className="absolute top-2 right-2 w-3 h-3 border-t-2 border-r-2 border-primary/40 pointer-events-none" />
        <div className="absolute bottom-2 left-2 w-3 h-3 border-b-2 border-l-2 border-primary/40 pointer-events-none" />
        <div className="absolute bottom-2 right-2 w-3 h-3 border-b-2 border-r-2 border-primary/40 pointer-events-none" />

        {/* Baseline & Watermark */}
        {!hasDrawn && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none select-none opacity-45">
            <span className="material-symbols-outlined text-3xl text-slate-400 mb-1">
              gesture
            </span>
            <span className="text-xs font-bold uppercase tracking-widest text-slate-500">
              Signa aquí dins del requadre
            </span>
          </div>
        )}
        <div className="absolute bottom-8 left-6 right-6 border-b border-slate-300 pointer-events-none" />

        <canvas
          ref={canvasRef}
          data-testid="signature-canvas"
          className="block w-full h-[200px] cursor-crosshair touch-none relative z-10"
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
          disabled={disabled}
          onClick={handleClear}
          className="flex-1 px-4 py-3 bg-surface-container-high dark:bg-slate-800 text-on-surface dark:text-slate-200 rounded-xl text-xs font-bold uppercase tracking-wider hover:bg-surface-container-highest transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
        >
          <span className="material-symbols-outlined text-sm">ink_eraser</span>
          Netejar
        </button>
        <button
          type="button"
          data-testid="btn-guardar-signatura"
          disabled={disabled || !hasDrawn}
          onClick={handleSave}
          className="flex-1 px-4 py-3 bg-secondary-container text-white rounded-xl text-xs font-bold uppercase tracking-wider hover:brightness-110 transition-all shadow-md flex items-center justify-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span className="material-symbols-outlined text-sm">verified</span>
          {disabled ? "Desant..." : "Guardar Signatura"}
        </button>
      </div>
    </div>
  );
}
