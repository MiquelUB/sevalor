"use client";

import { useState, useRef, useEffect } from "react";
import { Mic, Square, Camera, Send, AlertCircle } from "lucide-react";
import { db } from "@/lib/offline/db";

export default function SensoryInputForm({ pin, onSubmitted }: { pin?: string; onSubmitted?: () => void }) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [photoBlob, setPhotoBlob] = useState<Blob | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    return () => stopMediaTracks();
  }, []);

  const stopMediaTracks = () => {
    if (videoRef.current?.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((t) => t.stop());
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setAudioBlob(blob);
        chunksRef.current = [];
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);

      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => {
          if (prev >= 30) {
            stopRecording();
            return 30;
          }
          return prev + 1;
        });
      }, 1000);
    } catch (err) {
      console.error("No s'ha pogut accedir al micròfon", err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
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

  const sendData = async () => {
    if (!audioBlob) return;

    // TODO: Cridar backend (o Workbox SyncQueue)
    const formData = new FormData();
    formData.append("audio", audioBlob, "incidencia.webm");
    if (photoBlob) formData.append("foto", photoBlob, "foto.webp");

    try {
      // Registrar a la cua offline
      await db.syncQueue.add({
        url: "/api/v1/operari_pwa/incidencies",
        method: "POST",
        body: formData, // En IndexedDB es pot guardar Blob però l'API necessitarà tractament multipart
        timestamp: Date.now()
      });
      
      // Netegem
      setAudioBlob(null);
      setPhotoBlob(null);
      setRecordingTime(0);
      alert("Enviat a la cua. Es sincronitzarà en recuperar la cobertura.");
      onSubmitted?.();
    } catch (err) {
      console.error("Error encuant l'enviament", err);
    }
  };

  return (
    <div className="p-4 bg-gray-900 text-white rounded-lg shadow-xl w-full max-w-md mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-lg flex items-center">
          <AlertCircle className="mr-2 text-red-500" /> Nova Incidència
        </h3>
        <span className="text-xs text-gray-400">Fluxe de 30s</span>
      </div>

      {/* Visor de Càmera Ocult si tenim foto */}
      {!photoBlob && (
        <div className="relative bg-black rounded-lg aspect-video mb-4 overflow-hidden border border-gray-700 flex flex-col justify-center items-center">
          <video ref={videoRef} className="absolute inset-0 w-full h-full object-cover" muted playsInline />
          <button onClick={startCamera} className="z-10 bg-gray-800 p-2 rounded text-sm flex items-center">
            <Camera className="mr-2" size={16} /> Obrir Càmera
          </button>
          <button 
            onClick={capturePhoto} 
            className="absolute bottom-2 z-10 bg-white text-black p-2 rounded-full font-bold shadow-lg"
          >
            Capturar
          </button>
        </div>
      )}

      {photoBlob && (
        <div className="mb-4 bg-green-900/50 border border-green-500 rounded p-2 text-sm text-green-300">
          ✅ Foto capturada.
        </div>
      )}

      {/* Controls d'Àudio */}
      <div className="flex items-center justify-between bg-gray-800 p-4 rounded-lg mb-6">
        <div className="flex flex-col">
          <span className="text-sm font-semibold">Bitàcola de Veu</span>
          <span className={`text-2xl font-mono ${recordingTime > 20 ? 'text-red-400' : 'text-gray-300'}`}>
            00:{recordingTime.toString().padStart(2, '0')} / 00:30
          </span>
        </div>
        
        {isRecording ? (
          <button onClick={stopRecording} className="p-4 bg-red-600 rounded-full shadow-[0_0_15px_rgba(220,38,38,0.6)] animate-pulse">
            <Square fill="white" size={24} />
          </button>
        ) : (
          <button onClick={startRecording} className="p-4 bg-blue-600 rounded-full hover:bg-blue-500 transition-colors">
            <Mic size={24} />
          </button>
        )}
      </div>

      {/* Botó d'Enviar Bloquejat fins tenir àudio */}
      <button 
        onClick={sendData}
        disabled={!audioBlob}
        className={`w-full py-4 rounded-lg font-bold text-lg flex items-center justify-center transition-all ${
          audioBlob 
            ? "bg-green-600 hover:bg-green-500 cursor-pointer" 
            : "bg-gray-700 text-gray-500 cursor-not-allowed"
        }`}
      >
        <Send className="mr-2" /> Enviar Informe Pericial
      </button>
    </div>
  );
}
