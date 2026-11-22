"use client";
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Sparkles, X, Send, ExternalLink, Bot, Camera } from "lucide-react";
import { apiFetch, getAuthToken } from "@/lib/api";
import {
  CopilotErrorModal,
  extractCopilotPopupError,
  type CopilotPopupError,
} from "@/components/CopilotErrorModal";

export default function CopilotWidget({ isMobile = false }: { isMobile?: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [hasCopilotIa, setHasCopilotIa] = useState<boolean>(false);
  const [iaStatus, setIaStatus] = useState<{
    estat: string;
    model_actiu?: string;
    latencia_ms?: number | null;
    error?: string;
  } | null>(null);
  const [obert, setObert] = useState(false);
  const [missatgeXat, setMissatgeXat] = useState("");
  const [conversaXat, setConversaXat] = useState<any[]>([
    { sender: "bot", text: "Hola! Sóc l'assistent intel·ligent. Què necessites consultar?" }
  ]);
  const [carregant, setCarregant] = useState(false);
  const [imatgeB64, setImatgeB64] = useState<string | null>(null);
  const [executantAccio, setExecutantAccio] = useState(false);
  const [popupError, setPopupError] = useState<CopilotPopupError | null>(null);
  const [ultimaPreguntaFallida, setUltimaPreguntaFallida] = useState<string | null>(null);

  // El Copilot MAI es pot renderitzar a pàgines de login ni sense autenticació prèvia
  const isAuthPage =
    !pathname ||
    pathname === "/" ||
    pathname.includes("/login") ||
    pathname.startsWith("/login");

  useEffect(() => {
    if (isAuthPage) {
      setIsAuthenticated(false);
      setHasCopilotIa(false);
      setObert(false);
      return;
    }

    const token = getAuthToken();
    if (!token) {
      setIsAuthenticated(false);
      setHasCopilotIa(false);
      setObert(false);
      return;
    }

    const loadCopilotState = () => {
      apiFetch<any>("/auth/me")
        .then((res) => {
          if (res && res.id && res.feature_copilot_ia !== false) {
            setIsAuthenticated(true);
            setHasCopilotIa(true);
            if (!isMobile) {
              apiFetch<any>("/gestio/copilot/ia-status")
                .then((st) => setIaStatus(st || null))
                .catch(() => setIaStatus({ estat: "OFFLINE" }));
            }
          } else {
            setIsAuthenticated(false);
            setHasCopilotIa(false);
            setObert(false);
          }
        })
        .catch(() => {
          setIsAuthenticated(false);
          setHasCopilotIa(false);
          setObert(false);
        });
    };

    loadCopilotState();
  }, [pathname, isAuthPage, isMobile]);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImatgeB64(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const confirmarAccio = async (actionContext: any, mIdx: number) => {
    setExecutantAccio(true);
    try {
      const dades: any = await apiFetch("/gestio/copilot/action/confirm", {
        method: "POST",
        body: JSON.stringify({ action: actionContext.action, payload: actionContext.payload }),
      });
      
      // Update message to show success
      setConversaXat(prev => {
        const newArr = [...prev];
        newArr[mIdx].actionContext = null; // Hide the action box
        newArr[mIdx].text = newArr[mIdx].text + "\n\n✅ " + (dades?.missatge || "Acció executada amb èxit.");
        return newArr;
      });
    } catch (err) {
      alert("Error a l'executar l'acció.");
    } finally {
      setExecutantAccio(false);
    }
  };

  const enviarMissatgeXat = async (msgOpcional?: string) => {
    const textFinal =
      (msgOpcional ?? missatgeXat).trim() || (imatgeB64 ? "Analitza aquesta imatge tècnica." : "");
    if (!textFinal) return;

    setConversaXat((prev) => [...prev, { sender: "user", text: textFinal }]);
    if (!msgOpcional) setMissatgeXat("");
    setCarregant(true);
    const imgEnviar = imatgeB64;
    setImatgeB64(null);

    try {
      const endpoint = isMobile ? "/operari/copilot/xat" : "/gestio/copilot/xat";
      const historial = conversaXat
        .filter((m) => !m.error && m.text)
        .slice(-6)
        .map((m) => ({
          role: m.sender === "user" ? "user" : "assistant",
          content: m.text,
        }));
      const dades: any = await apiFetch(endpoint, {
        method: "POST",
        body: JSON.stringify({ pregunta: textFinal, imatge_b64: imgEnviar, historial }),
      });

      const toolRes = dades?.tool_resultat || dades?.metadata?.tool_resultat;
      const requiresConf = Boolean(toolRes?.requires_confirmation);
      setConversaXat((prev) => [
        ...prev,
        {
          sender: "bot",
          text: dades?.resposta || (requiresConf ? toolRes?.missatge : ""),
          links: Array.isArray(dades?.enllacos) ? dades.enllacos : [],
          subagent: dades?.subagent_utilitzat || null,
          latencyMs: dades?.temps_inferencia_ms ?? null,
          actionContext: requiresConf ? toolRes : null,
        },
      ]);
    } catch (err: any) {
      const structured = extractCopilotPopupError(err);
      if (structured) {
        setUltimaPreguntaFallida(textFinal);
        setPopupError(structured);
      }
      setConversaXat((prev) => [
        ...prev,
        {
          sender: "bot",
          text: structured
            ? `${structured.titol}: ${structured.message}`
            : err?.message || "Error de connexió amb l'Assistent AI.",
          error: true,
        },
      ]);
    } finally {
      setCarregant(false);
    }
  };

  if (isAuthPage || !isAuthenticated || !hasCopilotIa) return null;

  return (
    <>
      {/* Botó Flotant Global */}
      <button
        onClick={() => {
          setObert(true);
          if (!isMobile) {
            apiFetch<any>("/gestio/copilot/ia-status")
              .then((st) => setIaStatus(st || null))
              .catch(() => setIaStatus({ estat: "OFFLINE" }));
          }
        }}
        title="Obrir Sevalor Copilot IA"
        className={`fixed p-4 rounded-full bg-primary text-on-primary shadow-xl hover:bg-primary/90 transition-all z-50 flex items-center justify-center ${obert ? 'hidden' : ''} ${isMobile ? "bottom-20 right-4" : "bottom-6 right-6"}`}
      >
        <Sparkles className="w-6 h-6" />
      </button>

      {/* Pop-Up Window */}
      {obert && (
        <div className={`fixed z-50 bg-surface-container-lowest dark:bg-slate-900 flex flex-col overflow-hidden shadow-2xl border-outline-variant/40 dark:border-slate-800 ${isMobile ? "inset-0 w-full h-full pb-[60px]" : "bottom-6 right-6 w-96 h-[550px] border rounded-2xl"}`}>
          {/* Header */}
          <div className="p-3 bg-primary text-on-primary flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <Bot className="w-5 h-5 shrink-0" />
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <h4 className="font-bold text-sm truncate">Sevalor Copilot</h4>
                  {!isMobile && iaStatus && (
                    <span
                      className={`px-1.5 py-0.5 rounded-full text-[9px] font-mono font-bold ${
                        iaStatus.estat === "ONLINE"
                          ? "bg-emerald-400 text-slate-950"
                          : "bg-amber-300 text-slate-950"
                      }`}
                    >
                      {iaStatus.estat === "ONLINE"
                        ? `LIVE${iaStatus.latencia_ms != null ? ` ${iaStatus.latencia_ms}ms` : ""}`
                        : "OFFLINE"}
                    </span>
                  )}
                </div>
                {!isMobile && iaStatus?.model_actiu && iaStatus.estat === "ONLINE" && (
                  <p className="text-[10px] text-white/75 font-mono truncate">{iaStatus.model_actiu}</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {!isMobile && (
                <Link
                  href="/gestio/copilot"
                  onClick={() => setObert(false)}
                  className="px-2 py-1 rounded-md text-[10px] font-semibold bg-white/15 hover:bg-white/25 transition-colors"
                  title="Obrir Centre Complet del Copilot"
                >
                  Centre IA
                </Link>
              )}
              <button onClick={() => setObert(false)} className="hover:bg-primary-container p-1 rounded-md transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Avís si node offline */}
          {!isMobile && iaStatus && iaStatus.estat !== "ONLINE" && (
            <div className="px-3 py-2 bg-amber-50 dark:bg-amber-950/50 border-b border-amber-200 dark:border-amber-900 text-[11px] text-amber-900 dark:text-amber-200 flex items-center justify-between gap-2">
              <span className="truncate">{iaStatus.error || "Node IA local fora de línia."}</span>
              <Link href="/gestio/copilot" onClick={() => setObert(false)} className="font-bold underline shrink-0">
                Estat
              </Link>
            </div>
          )}

          {/* Chat Messages */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3 bg-surface-container-low dark:bg-slate-900">
            {conversaXat.length <= 1 && (
              <div className="flex flex-wrap gap-1.5">
                {[
                  "Quin estoc tenim sota mínims?",
                  "Quin equip està treballant avui?",
                  "Estat dels vehicles i ITV",
                ].map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => enviarMissatgeXat(q)}
                    className="text-[10px] px-2.5 py-1 rounded-full bg-surface-container-lowest border border-outline-variant/50 text-on-surface hover:border-primary hover:text-primary transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
            {conversaXat.map((m, idx) => (
              <div key={idx} className={`flex flex-col ${m.sender === "user" ? "items-end" : "items-start"}`}>
                <div
                  className={`max-w-[85%] p-3 rounded-2xl text-xs leading-relaxed whitespace-pre-wrap ${
                    m.sender === "user"
                      ? "bg-primary text-on-primary rounded-br-none"
                      : m.error
                      ? "bg-rose-50 border border-rose-300 text-rose-900 rounded-bl-none font-medium"
                      : "bg-surface-container-lowest border border-outline-variant/40 text-on-surface rounded-bl-none shadow-sm"
                  }`}
                >
                  {m.text}
                </div>
                {m.sender === "bot" && (m.subagent || m.latencyMs != null) && (
                  <span className="text-[9px] font-mono text-on-surface-variant/80 mt-0.5 pl-1">
                    {m.subagent ? `Agent: ${m.subagent}` : ""}
                    {m.subagent && m.latencyMs != null ? " · " : ""}
                    {m.latencyMs != null ? `${m.latencyMs} ms` : ""}
                  </span>
                )}
                {m.actionContext && (
                  <div className="mt-2 p-2 bg-primary/10 border border-primary/30 rounded-xl">
                    <p className="text-[10px] font-bold text-primary mb-1">Requereix Confirmació:</p>
                    <pre className="text-[9px] text-on-surface bg-surface-container p-1.5 rounded mb-2 overflow-x-auto">
                      {JSON.stringify(m.actionContext.payload, null, 2)}
                    </pre>
                    <div className="flex gap-2">
                      <button 
                        onClick={() => confirmarAccio(m.actionContext, idx)}
                        disabled={executantAccio}
                        className="flex-1 bg-primary text-on-primary py-1 rounded text-[10px] font-bold hover:bg-primary/90 disabled:opacity-50"
                      >
                        {executantAccio ? "Processant..." : "Aprovar i Executar"}
                      </button>
                    </div>
                  </div>
                )}

                {m.links && m.links.length > 0 && (
                  <div className="flex flex-col items-start gap-1 mt-1 pl-1">
                    {m.links.map((link: any, lIdx: number) => (
                      <a
                        key={lIdx}
                        href={link.url}
                        className="text-[10px] bg-surface-container text-on-surface px-2 py-0.5 rounded flex items-center gap-1 hover:bg-surface-container-high transition-colors"
                      >
                        <ExternalLink className="w-3 h-3" />
                        {link.titol}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {carregant && (
              <div className="flex items-start">
                <div className="bg-surface-container-lowest border border-outline-variant/40 text-on-surface p-3 rounded-2xl rounded-bl-none shadow-sm text-xs flex items-center gap-2">
                  <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-primary/80 rounded-full animate-bounce delay-75"></div>
                  <div className="w-2 h-2 bg-primary rounded-full animate-bounce delay-150"></div>
                </div>
              </div>
            )}
          </div>

          {/* Chat Input */}

          <div className="p-3 border-t border-outline-variant/30 dark:border-slate-800 bg-surface-container-lowest dark:bg-slate-850">
            {imatgeB64 && (
              <div className="mb-2 relative inline-block">
                <img src={imatgeB64} alt="Upload preview" className="h-16 w-16 object-cover rounded-lg border border-outline-variant" />
                <button onClick={() => setImatgeB64(null)} className="absolute -top-2 -right-2 bg-rose-500 text-white rounded-full p-0.5">
                  <X className="w-3 h-3" />
                </button>
              </div>
            )}
            <div className="flex items-center gap-2">
              <label className="p-2 text-on-surface-variant hover:text-primary cursor-pointer bg-surface-container dark:bg-slate-800 hover:bg-surface-container-high rounded-xl transition-colors">
                <Camera className="w-5 h-5" />
                <input type="file" accept="image/*" capture="environment" className="hidden" onChange={handleImageUpload} />
              </label>
              <input
                type="text"

              value={missatgeXat}
              onChange={(e) => setMissatgeXat(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") enviarMissatgeXat();
              }}
              placeholder="Fes la teva consulta..."
              className="flex-1 bg-surface-container dark:bg-slate-800 border border-transparent rounded-xl px-3 py-2 text-xs text-on-surface dark:text-slate-100 placeholder:text-on-surface-variant focus:outline-none focus:border-primary focus:bg-surface-container-lowest transition-all"
            />
              <button
                onClick={() => enviarMissatgeXat()}
                disabled={carregant || (!missatgeXat.trim() && !imatgeB64)}
                className="p-2 rounded-xl bg-primary hover:bg-primary/90 disabled:opacity-50 text-on-primary transition-all shadow"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      <CopilotErrorModal
        error={popupError}
        onClose={() => setPopupError(null)}
        onOpenConfig={!isMobile ? () => router.push("/gestio/copilot") : undefined}
        onRetry={
          ultimaPreguntaFallida
            ? () => {
                const retryPrompt = ultimaPreguntaFallida;
                setUltimaPreguntaFallida(null);
                enviarMissatgeXat(retryPrompt);
              }
            : undefined
        }
        canCheckStatus={!isMobile}
      />
    </>
  );
}
