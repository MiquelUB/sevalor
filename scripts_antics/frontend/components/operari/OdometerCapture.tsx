"use client";

import { useState, useRef, useEffect } from "react";
import { Camera, Car, CheckCircle } from "lucide-react";
import { db } from "@/lib/offline/db";

export default function OdometerCapture({ onSuccess }: { onSuccess: () => void }) {
  const [photoBlob, setPhotoBlob] = useState<Blob | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    startCamera();
    return () => stopMediaTracks();
  }, []);

  const stopMediaTracks = () => {
    if (videoRef.current?.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((t) => t.stop());
    }
  };

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { facingMode: "environment" } 
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
    } catch (err) {
      console.error("Error accedint a la càmera", err);
    }
  };

  const capturePhoto = () => {
    if (videoRef.current) {
      const canvas = document.createElement("canvas");
      canvas.width = videoRef.current.videoWidth;
      canvas.height = videoRef.current.videoHeight;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.drawImage(videoRef.current, 0, 0);
        canvas.toBlob(
          (blob) => {
            if (blob) setPhotoBlob(blob);
            stopMediaTracks();
          },
          "image/webp",
          0.8
        );
      }
    }
  };

  const submitOdometer = async () => {
    if (!photoBlob) return;
    setIsProcessing(true);

    const formData = new FormData();
    formData.append("foto_odometre", photoBlob, "odometre.webp");

    try {
      // Registrar a la cua offline. El Celery Worker (Backend) farà l'OCR
      await db.syncQueue.add({
        url: "/api/v1/operari_pwa/vehicles/odometre",
        method: "POST",
        body: formData,
        timestamp: Date.now()
      });
      
      setIsProcessing(false);
      onSuccess(); // Permet continuar amb el fitxatge
    } catch (err) {
      console.error("Error enviant foto odòmetre", err);
      setIsProcessing(false);
    }
  };

  return (
    <div className="p-4 bg-gray-900 text-white rounded-lg shadow-xl w-full max-w-md mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-lg flex items-center">
          <Car className="mr-2 text-blue-500" /> Control de Flota
        </h3>
        <span className="text-xs text-gray-400">Pas obligatori</span>
      </div>
      <p className="text-sm text-gray-300 mb-4">
        Per poder obrir la jornada, has de capturar el quadre de comandaments amb l'odòmetre visible. L'IA n'extraurà els quilòmetres.
      </p>

      {!photoBlob ? (
        <div className="relative bg-black rounded-lg aspect-video mb-4 overflow-hidden border border-gray-700 flex flex-col justify-center items-center">
          <video ref={videoRef} className="absolute inset-0 w-full h-full object-cover" muted playsInline />
          <button 
            onClick={capturePhoto} 
            className="absolute bottom-4 z-10 bg-white text-black px-6 py-2 rounded-full font-bold shadow-lg flex items-center"
          >
            <Camera className="mr-2" size={20} /> Capturar Odòmetre
          </button>
        </div>
      ) : (
        <div className="mb-4">
          <div className="bg-green-900/50 border border-green-500 rounded p-4 text-green-300 flex items-center mb-4">
            <CheckCircle className="mr-3" /> Foto capturada correctament.
          </div>
          <button 
            onClick={submitOdometer}
            disabled={isProcessing}
            className="w-full bg-blue-600 hover:bg-blue-500 py-3 rounded-lg font-bold flex justify-center items-center"
          >
            {isProcessing ? "Desant a la cua offline..." : "Confirmar i Fitxar Jornada"}
          </button>
          <button 
            onClick={() => { setPhotoBlob(null); startCamera(); }}
            className="w-full mt-2 bg-transparent text-gray-400 py-2"
          >
            Tornar a capturar
          </button>
        </div>
      )}
    </div>
  );
}
