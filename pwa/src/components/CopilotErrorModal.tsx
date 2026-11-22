"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  RefreshCw,
  ServerOff,
  Settings2,
  ShieldAlert,
  X,
} from "lucide-react";
import { apiFetch, type ApiStructuredError } from "@/lib/api";

export interface CopilotPopupError {
  status: number;
  code: string;
  motiu: string;
  titol: string;
  message: string;
  passos_solucio: string[];
}

const DEFAULT_SOLUTIONS: Record<
  string,
  { titol: string; passos: string[] }
> = {
  TUNEL_OFFLINE: {
    titol: "Ordinador dedicat de l'empresa desconnectat",
    passos: [
      "Comprova que el mini-PC dedicat de l'oficina estigui encès i amb connexió a Internet.",
      "Verifica que el servei de l'agent sobirà (sevalor-vault-agent) estigui en execució.",
      "Un cop connectat, prem «Comprovar connexió» i torna a enviar la consulta.",
    ],
  },
  LLM_OFFLINE: {
    titol: "Motor d'IA local (LM Studio) aturat o sense model carregat",
    passos: [
      "Obre LM Studio al mini-PC dedicat de l'empresa.",
      "Comprova que hi hagi un model carregat i activa el «Local Server» al port 1234.",
      "Torna a enviar la consulta des del xat.",
    ],
  },
  COPILOT_DESACTIVAT: {
    titol: "Mòdul Copilot IA desactivat",
    passos: [
      "Contacta amb l'administrador (Superadmin) per activar la llicència i el node IA d'aquesta empresa.",
      "Un cop activat, recarrega la sessió per iniciar el Copilot.",
    ],
  },
  PROMPT_PENDENT: {
    titol: "System Prompt del Copilot pendent de configurar",
    passos: [
      "Obre la pestanya de configuració del Copilot a /gestio/copilot (rol Direcció o Admin).",
      "Defineix el System Prompt de la vertical de l'empresa i prem Desar.",
      "Torna al xat i reintenta la consulta.",
    ],
  },
};

export function extractCopilotPopupError(err: unknown): CopilotPopupError | null {
  if (!err || typeof err !== "object") return null;
  const e = err as ApiStructuredError;
  const status = typeof e.status === "number" ? e.status : 0;
  const code = String(e.code || "").toUpperCase();
  const msg = String(e.message || "");

  const isCopilot503 =
    status === 503 ||
    code === "NODE_IA_OFFLINE" ||
    code === "COPILOT_DESACTIVAT" ||
    code === "NODE_EMPRESA_OFFLINE";
  const isPrompt422 =
    status === 422 &&
    (code === "COPILOT_NOT_CONFIGURED" || msg.includes("COPILOT_NOT_CONFIGURED"));

  if (!isCopilot503 && !isPrompt422) return null;

  let motiu = String(e.motiu || "").toUpperCase();
  if (!motiu) {
    if (isPrompt422) {
      motiu = "PROMPT_PENDENT";
    } else if (code === "COPILOT_DESACTIVAT") {
      motiu = "COPILOT_DESACTIVAT";
    } else if (msg.toLowerCase().includes("lm studio") || msg.includes("1234")) {
      motiu = "LLM_OFFLINE";
    } else {
      motiu = "TUNEL_OFFLINE";
    }
  }

  const fallback =
    DEFAULT_SOLUTIONS[motiu] ||
    DEFAULT_SOLUTIONS[code] ||
    DEFAULT_SOLUTIONS.TUNEL_OFFLINE;

  return {
    status: status || (isPrompt422 ? 422 : 503),
    code: code || (isPrompt422 ? "COPILOT_NOT_CONFIGURED" : "NODE_IA_OFFLINE"),
    motiu,
    titol: e.titol?.trim() || fallback.titol,
    message: msg.trim() || fallback.titol,
    passos_solucio:
      Array.isArray(e.passos_solucio) && e.passos_solucio.length > 0
        ? e.passos_solucio
        : fallback.passos,
  };
}

interface CopilotErrorModalProps {
  error: CopilotPopupError | null;
  onClose: () => void;
  onRetry?: () => void;
  onOpenConfig?: () => void;
  canCheckStatus?: boolean;
}

export function CopilotErrorModal({
  error,
  onClose,
  onRetry,
  onOpenConfig,
  canCheckStatus = true,
}: CopilotErrorModalProps) {
  const [comprovant, setComprovant] = useState(false);
  const [estatProbe, setEstatProbe] = useState<{
    online: boolean;
    text: string;
  } | null>(null);

  useEffect(() => {
    setEstatProbe(null);
  }, [error]);

  useEffect(() => {
    if (!error) return;
    const onKeyDown = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [error, onClose]);

  if (!error) return null;

  const isLlmOffline = error.motiu === "LLM_OFFLINE";
  const isPromptPendent =
    error.motiu === "PROMPT_PENDENT" || error.code === "COPILOT_NOT_CONFIGURED";
  const isDesactivat =
    error.code === "COPILOT_DESACTIVAT" ||
    error.motiu === "FEATURE_COPILOT_DESACTIVAT" ||
    error.motiu === "NODE_IA_INACTIU";

  const accentBorderClass = isPromptPendent
    ? "border-l-primary"
    : isLlmOffline
    ? "border-l-warning"
    : isDesactivat
    ? "border-l-secondary"
    : "border-l-destructive";

  const iconContainerClass = isPromptPendent
    ? "bg-primary/10 text-primary"
    : isLlmOffline
    ? "bg-warning/15 text-secondary"
    : isDesactivat
    ? "bg-secondary/15 text-secondary"
    : "bg-error-container text-on-error-container";

  const comprovarConnexio = async () => {
    setComprovant(true);
    setEstatProbe(null);
    try {
      const st = await apiFetch<{
        estat?: string;
        model_actiu?: string;
        error?: string;
      }>("/gestio/copilot/ia-status");
      if (st?.estat === "ONLINE") {
        setEstatProbe({
          online: true,
          text: st.model_actiu
            ? `Connexió recuperada. Model actiu: ${st.model_actiu}`
            : "Connexió recuperada amb el PC dedicat i LM Studio.",
        });
      } else {
        setEstatProbe({
          online: false,
          text: st?.error || "El node d'IA local continua fora de línia.",
        });
      }
    } catch {
      setEstatProbe({
        online: false,
        text: "No s'ha pogut verificar l'estat del túnel WSS.",
      });
    } finally {
      setComprovant(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-on-surface/50 backdrop-blur-[2px] p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="copilot-error-modal-title"
      onClick={onClose}
    >
      <div
        className={`w-full max-w-lg rounded-2xl bg-surface-container-lowest text-on-surface border border-outline-variant/60 border-l-4 ${accentBorderClass} shadow-2xl overflow-hidden`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Capçalera */}
        <div className="px-6 pt-5 pb-4 flex items-start justify-between gap-4 border-b border-outline-variant/30">
          <div className="flex items-start gap-3.5">
            <div className={`p-2.5 rounded-xl shrink-0 ${iconContainerClass}`}>
              {isPromptPendent ? (
                <Settings2 className="w-5 h-5" />
              ) : isLlmOffline ? (
                <Cpu className="w-5 h-5" />
              ) : isDesactivat ? (
                <ShieldAlert className="w-5 h-5" />
              ) : (
                <ServerOff className="w-5 h-5" />
              )}
            </div>
            <div className="space-y-1">
              <div className="inline-flex items-center gap-2 text-xs font-mono text-on-surface-variant">
                <span className="px-2 py-0.5 rounded-md bg-surface-container border border-outline-variant/40">
                  HTTP {error.status}
                </span>
                <span>{error.motiu}</span>
              </div>
              <h2
                id="copilot-error-modal-title"
                className="text-base font-bold leading-snug text-on-surface"
              >
                {error.titol}
              </h2>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tancar diagnòstic"
            className="p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Cos diagnòstic + passos seqüencials */}
        <div className="px-6 py-5 space-y-4">
          <p className="text-sm leading-relaxed text-on-surface-variant">
            {error.message}
          </p>

          <div className="rounded-xl bg-surface-container-low border border-outline-variant/40 p-4 space-y-3">
            <p className="text-xs font-semibold text-on-surface">
              Passos per resoldre-ho
            </p>
            <ol className="space-y-2.5">
              {error.passos_solucio.map((pas, idx) => (
                <li
                  key={`${error.motiu}-pas-${idx}`}
                  className="flex items-start gap-3 text-xs leading-relaxed text-on-surface"
                >
                  <span className="w-5 h-5 rounded-full bg-surface-container-highest text-on-surface font-mono font-bold text-[11px] flex items-center justify-center shrink-0 mt-0.5">
                    {idx + 1}
                  </span>
                  <span>{pas}</span>
                </li>
              ))}
            </ol>
          </div>

          {estatProbe && (
            <div
              className={`p-3 rounded-xl border text-xs flex items-center gap-2.5 ${
                estatProbe.online
                  ? "bg-surface-container-low border-success/40 text-on-surface"
                  : "bg-error-container/50 border-destructive/30 text-on-error-container"
              }`}
            >
              {estatProbe.online ? (
                <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 shrink-0" />
              )}
              <span>{estatProbe.text}</span>
            </div>
          )}
        </div>

        {/* Accions */}
        <div className="px-6 py-4 bg-surface-container-low border-t border-outline-variant/30 flex flex-wrap items-center justify-end gap-2.5">
          {canCheckStatus && !isPromptPendent && !isDesactivat && (
            <button
              type="button"
              onClick={comprovarConnexio}
              disabled={comprovant}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-outline-variant/70 bg-surface-container-lowest text-xs font-semibold text-on-surface hover:border-primary transition-colors disabled:opacity-50 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${comprovant ? "animate-spin" : ""}`}
              />
              <span>{comprovant ? "Comprovant..." : "Comprovar connexió"}</span>
            </button>
          )}

          {isPromptPendent && onOpenConfig && (
            <button
              type="button"
              onClick={() => {
                onClose();
                onOpenConfig();
              }}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary text-on-primary text-xs font-semibold hover:opacity-90 transition-opacity cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <Settings2 className="w-3.5 h-3.5" />
              <span>Configurar prompt</span>
            </button>
          )}

          {onRetry && !isDesactivat && !isPromptPendent && (
            <button
              type="button"
              onClick={() => {
                onClose();
                onRetry();
              }}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary text-on-primary text-xs font-semibold hover:opacity-90 transition-opacity cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Reintentar consulta</span>
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-2 rounded-xl text-xs font-semibold text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Tancar
          </button>
        </div>
      </div>
    </div>
  );
}
