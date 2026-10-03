"use client";

import React, { useState, useRef, useEffect } from "react";
import { Mic, Square, Play, Pause, Trash2, CheckCircle2, AlertCircle } from "lucide-react";

interface VoiceRecorderProps {
  onRecordComplete: (audioBlob: Blob) => void;
  onClear?: () => void;
  maxSeconds?: number;
}

export default function VoiceRecorder({
  onRecordComplete,
  onClear,
  maxSeconds = 30,
}: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  const startRecording = async () => {
    setError(null);
    audioChunksRef.current = [];
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Determinar MIME type suportat per WebRTC / MediaRecorder
      let mimeType = "audio/webm;codecs=opus";
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        if (MediaRecorder.isTypeSupported("audio/webm")) {
          mimeType = "audio/webm";
        } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
          mimeType = "audio/mp4";
        } else {
          mimeType = "";
        }
      }

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const finalMime = recorder.mimeType || "audio/webm;codecs=opus";
        const audioBlob = new Blob(audioChunksRef.current, { type: finalMime });
        if (audioBlob.size > 0) {
          const url = URL.createObjectURL(audioBlob);
          setAudioUrl(url);
          onRecordComplete(audioBlob);
        }
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop());
          streamRef.current = null;
        }
      };

      recorder.start(250); // trossos cada 250ms
      setIsRecording(true);
      setElapsed(0);

      const startTime = Date.now();
      timerRef.current = setInterval(() => {
        const seconds = Math.floor((Date.now() - startTime) / 1000);
        setElapsed(seconds);
        if (seconds >= maxSeconds) {
          stopRecording();
        }
      }, 250);
    } catch (err: any) {
      console.error("Error en accedir al micròfon:", err);
      setError("No s'ha pogut accedir al micròfon. Comprova els permisos del navegador.");
    }
  };

  const stopRecording = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  const handlePlayToggle = () => {
    if (!audioUrl) return;
    if (!audioElementRef.current) {
      audioElementRef.current = new Audio(audioUrl);
      audioElementRef.current.onended = () => setIsPlaying(false);
    }
    if (isPlaying) {
      audioElementRef.current.pause();
      setIsPlaying(false);
    } else {
      audioElementRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleClear = () => {
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current = null;
    }
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }
    setAudioUrl(null);
    setIsPlaying(false);
    setElapsed(0);
    if (onClear) onClear();
  };

  return (
    <div className="w-full bg-slate-50 dark:bg-slate-800/60 p-4 rounded-xl border border-slate-200 dark:border-slate-700 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-300 flex items-center gap-2">
          <Mic className="w-4 h-4 text-emerald-500" />
          Nota de Veu (Màx. {maxSeconds}s)
        </span>
        {isRecording && (
          <span className="text-xs font-mono font-bold text-rose-500 animate-pulse flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            {elapsed}s / {maxSeconds}s
          </span>
        )}
      </div>

      {error && (
        <div className="p-2.5 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 rounded-lg text-rose-600 dark:text-rose-400 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!isRecording && !audioUrl && (
        <button
          type="button"
          onClick={startRecording}
          className="w-full py-3 rounded-xl border-2 border-dashed border-emerald-500/50 hover:border-emerald-500 bg-emerald-500/5 hover:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold text-xs flex items-center justify-center gap-2 transition-all active:scale-98"
        >
          <Mic className="w-4 h-4" />
          Enregistrar Àudio Real
        </button>
      )}

      {isRecording && (
        <button
          type="button"
          onClick={stopRecording}
          className="w-full py-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-rose-600/30 transition-all active:scale-98"
        >
          <Square className="w-4 h-4" />
          Aturar Gravació ({elapsed}s)
        </button>
      )}

      {audioUrl && !isRecording && (
        <div className="flex items-center justify-between gap-2 p-2 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <button
              type="button"
              onClick={handlePlayToggle}
              className="p-2 rounded-lg bg-emerald-500 text-white hover:bg-emerald-600 transition-colors shrink-0"
              title={isPlaying ? "Pausar" : "Reproduir"}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1 truncate">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                Àudio enregistrat ({elapsed}s)
              </span>
              <span className="text-[10px] text-slate-400">Prêt per enviar a transcripció</span>
            </div>
          </div>

          <button
            type="button"
            onClick={handleClear}
            className="p-2 text-slate-400 hover:text-rose-500 transition-colors shrink-0"
            title="Eliminar i tornar a gravar"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
