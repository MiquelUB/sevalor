"use client";

import React, { useEffect, useRef, useState } from "react";
import { Camera, X, RefreshCcw } from "lucide-react";

interface CameraCaptureProps {
  onCapture: (blob: Blob) => void;
  onCancel: () => void;
}

export default function CameraCapture({ onCapture, onCancel }: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");

  const startCamera = async (mode: "environment" | "user") => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
    }
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: mode,
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        },
        audio: false,
      });
      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
      setError(null);
    } catch (err: any) {
      console.error("Error accessing camera:", err);
      setError("No s'ha pogut accedir a la càmera. Comprova els permisos del navegador.");
    }
  };

  useEffect(() => {
    startCamera(facingMode);
    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facingMode]);

  const handleCapture = () => {
    if (!videoRef.current || !canvasRef.current) return;
    
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const context = canvas.getContext("2d");
    
    if (!context) return;

    // Set canvas dimensions to match video stream
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    // Draw current frame
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Convert to WebP and pass to parent
    canvas.toBlob(
      (blob) => {
        if (blob) {
          // Play a fake shutter sound or UI feedback if needed
          onCapture(blob);
        }
      },
      "image/webp",
      0.82
    );
  };

  const toggleCamera = () => {
    setFacingMode(prev => prev === "environment" ? "user" : "environment");
  };

  return (
    <div className="fixed inset-0 z-50 bg-black flex flex-col">
      <div className="p-4 flex justify-between items-center bg-black/50 absolute top-0 w-full z-10">
        <button onClick={onCancel} className="text-white p-2 bg-slate-800/80 rounded-full active:scale-95 transition-transform">
          <X className="w-6 h-6" />
        </button>
        <button onClick={toggleCamera} className="text-white p-2 bg-slate-800/80 rounded-full active:scale-95 transition-transform">
          <RefreshCcw className="w-6 h-6" />
        </button>
      </div>

      <div className="flex-1 relative flex items-center justify-center bg-black overflow-hidden">
        {error ? (
          <div className="text-red-500 p-4 text-center">
            <p className="font-bold text-lg mb-2">Error de càmera</p>
            <p className="text-sm">{error}</p>
          </div>
        ) : (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-cover"
          />
        )}
      </div>

      <div className="h-32 bg-black pb-8 pt-4 flex items-center justify-center">
        <button
          onClick={handleCapture}
          disabled={!!error}
          className="w-20 h-20 rounded-full bg-white border-4 border-slate-300 flex items-center justify-center active:bg-slate-200 active:scale-95 transition-all disabled:opacity-50"
        >
          <Camera className="w-8 h-8 text-slate-800" />
        </button>
      </div>
      
      {/* Hidden canvas for image extraction */}
      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}
