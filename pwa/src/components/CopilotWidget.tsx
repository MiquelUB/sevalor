"use client";
import React, { useState } from "react";
import { Sparkles, X, Send, ExternalLink, Bot, MessageSquare } from "lucide-react";
import { apiFetch } from "@/lib/api";

export default function CopilotWidget() {
  const [obert, setObert] = useState(false);
  const [missatgeXat, setMissatgeXat] = useState("");
  const [conversaXat, setConversaXat] = useState<any[]>([
    { sender: "bot", text: "Hola! Sóc l'assistent intel·ligent. Què necessites consultar?" }
  ]);
  const [carregant, setCarregant] = useState(false);

  const enviarMissatgeXat = async (msgOpcional?: string) => {
    const textFinal = msgOpcional || missatgeXat;
    if (!textFinal.trim()) return;

    setConversaXat((prev) => [...prev, { sender: "user", text: textFinal }]);
    setMissatgeXat("");
    setCarregant(true);

    try {
      const res = await apiFetch("/gestio/copilot/xat", {
        method: "POST",
        body: JSON.stringify({ pregunta: textFinal }),
      });
      if (res.ok) {
        const dades = await res.json();
        setConversaXat((prev) => [
          ...prev,
          { sender: "bot", text: dades.resposta, links: dades.enllacos || [] },
        ]);
      } else {
        const errorData = await res.json();
        setConversaXat((prev) => [
          ...prev,
          { sender: "bot", text: errorData.detail || "Error processant la consulta.", error: true },
        ]);
      }
    } catch (err) {
      setConversaXat((prev) => [
        ...prev,
        { sender: "bot", text: "Error de connexió amb l'Assistent AI.", error: true },
      ]);
    } finally {
      setCarregant(false);
    }
  };

  return (
    <>
      {/* Botó Flotant Global */}
      <button
        onClick={() => setObert(true)}
        className={`fixed bottom-6 right-6 p-4 rounded-full bg-indigo-600 text-white shadow-xl hover:bg-indigo-700 transition-all z-50 flex items-center justify-center ${obert ? 'hidden' : ''}`}
      >
        <Sparkles className="w-6 h-6" />
      </button>

      {/* Pop-Up Window */}
      {obert && (
        <div className="fixed bottom-6 right-6 w-96 h-[550px] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl flex flex-col z-50 overflow-hidden flex flex-col">
          {/* Header */}
          <div className="p-3 bg-indigo-600 text-white flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5" />
              <h4 className="font-bold text-sm">Sevalor Copilot</h4>
            </div>
            <button onClick={() => setObert(false)} className="hover:bg-indigo-700 p-1 rounded-md transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Chat Messages */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3 bg-slate-50 dark:bg-slate-900">
            {conversaXat.map((m, idx) => (
              <div key={idx} className={`flex flex-col ${m.sender === "user" ? "items-end" : "items-start"}`}>
                <div
                  className={`max-w-[85%] p-3 rounded-2xl text-xs leading-relaxed ${
                    m.sender === "user"
                      ? "bg-indigo-600 text-white rounded-br-none"
                      : m.error
                      ? "bg-rose-50 border border-rose-300 text-rose-900 rounded-bl-none font-medium"
                      : "bg-white border border-slate-200 text-slate-800 rounded-bl-none shadow-sm"
                  }`}
                >
                  {m.text}
                </div>
                {m.links && m.links.length > 0 && (
                  <div className="flex flex-col items-start gap-1 mt-1 pl-1">
                    {m.links.map((link: any, lIdx: number) => (
                      <a
                        key={lIdx}
                        href={link.url}
                        className="text-[10px] bg-slate-200 text-slate-700 px-2 py-0.5 rounded flex items-center gap-1 hover:bg-slate-300 transition-colors"
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
                <div className="bg-white border border-slate-200 text-slate-800 p-3 rounded-2xl rounded-bl-none shadow-sm text-xs flex items-center gap-2">
                  <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce delay-75"></div>
                  <div className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce delay-150"></div>
                </div>
              </div>
            )}
          </div>

          {/* Chat Input */}
          <div className="p-3 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-850 flex items-center gap-2">
            <input
              type="text"
              value={missatgeXat}
              onChange={(e) => setMissatgeXat(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") enviarMissatgeXat();
              }}
              placeholder="Fes la teva consulta..."
              className="flex-1 bg-slate-100 dark:bg-slate-800 border border-transparent rounded-xl px-3 py-2 text-xs text-slate-800 dark:text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 focus:bg-white transition-all"
            />
            <button
              onClick={() => enviarMissatgeXat()}
              disabled={carregant || !missatgeXat.trim()}
              className="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white transition-all shadow"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
