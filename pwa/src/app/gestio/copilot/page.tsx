"use client";
import React, { useState } from "react";
import { Sparkles, Layers, Send, CheckCircle2, AlertCircle } from "lucide-react";
import { apiFetch } from "@/lib/api";

export default function CopilotEntrenament() {
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6 w-full animate-fade-in">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display-lg font-bold text-primary flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-secondary" />
            Entrenament Copilot (RAG)
          </h1>
          <p className="text-sm text-on-surface-variant mt-1">
            Gestiona la Base de Coneixement del teu Disc Sobirà i node IA local. El xat està disponible en tot moment a la icona flotant inferior dreta.
          </p>
        </div>
      </div>

      {feedback && (
        <div
          className={`p-3 rounded-xl border text-xs font-body-strong flex items-center gap-2 ${
            feedback.type === "ok"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-error-container/30 border-error/40 text-error"
          }`}
        >
          {feedback.type === "ok" ? (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0" />
          )}
          <span>{feedback.text}</span>
        </div>
      )}

      <div className="bg-surface-container-lowest rounded-xl shadow-sm border border-outline-variant/40 p-6 border-l-4 border-l-primary">
        <div className="flex items-center gap-3 mb-4">
          <div className="bg-primary/10 p-2 rounded-full">
            <Layers className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h2 className="text-xl font-section-title font-bold text-on-surface">Base de Coneixement</h2>
            <p className="text-sm text-on-surface-variant">
              Afegeix manuals, protocols i FAQs corporatives directament al directori <span className="font-mono text-xs">10_protocols_i_manuals/procediments_interns</span>.
            </p>
          </div>
        </div>

        <form onSubmit={async (e) => {
          e.preventDefault();
          const form = e.target as HTMLFormElement;
          const dades = {
            titol: (form.elements.namedItem("titol") as HTMLInputElement).value,
            contingut: (form.elements.namedItem("contingut") as HTMLTextAreaElement).value,
            tags: (form.elements.namedItem("tags") as HTMLInputElement).value
          };
          setSubmitting(true);
          setFeedback(null);
          try {
            await apiFetch("/gestio/copilot/rag/document", {
              method: "POST",
              body: JSON.stringify(dades)
            });
            setFeedback({
              type: "ok",
              text: "Document afegit i vectoritzat correctament al disc sobirà local.",
            });
            form.reset();
          } catch (err: any) {
            setFeedback({
              type: "err",
              text: `Error afegint document: ${err.message || "Error de xarxa"}`,
            });
          } finally {
            setSubmitting(false);
          }
        }} className="space-y-4">
          <div>
            <label className="block font-label-caps text-xs uppercase text-on-surface-variant mb-1">
              Títol del Protocol / Document
            </label>
            <input type="text" name="titol" required className="mt-1 block w-full rounded-xl border-outline-variant bg-surface-container-low text-on-surface shadow-sm focus:border-primary focus:ring-primary p-2.5 border text-sm outline-none" placeholder="Ex: Protocol d'Actuació Manteniment Bomba..." />
          </div>
          
          <div>
            <label className="block font-label-caps text-xs uppercase text-on-surface-variant mb-1">
              Informació o Contingut
            </label>
            <textarea name="contingut" required rows={8} className="mt-1 block w-full rounded-xl border-outline-variant bg-surface-container-low text-on-surface shadow-sm focus:border-primary focus:ring-primary p-2.5 border text-sm outline-none" placeholder="Descriu pas a pas el protocol o detalls tècnics..."></textarea>
          </div>
          
          <div>
            <label className="block font-label-caps text-xs uppercase text-on-surface-variant mb-1">
              Paraules Clau (Tags, separats per coma)
            </label>
            <input type="text" name="tags" className="mt-1 block w-full rounded-xl border-outline-variant bg-surface-container-low text-on-surface shadow-sm focus:border-primary focus:ring-primary p-2.5 border text-sm outline-none" placeholder="ex: manteniment, bomba, hidràulic" />
          </div>
          
          <div className="pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center px-5 py-2.5 border border-transparent shadow-sm text-sm font-body-strong rounded-xl text-on-primary bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary transition-colors disabled:opacity-60 cursor-pointer"
            >
              <Send className="mr-2 h-4 w-4" />
              {submitting ? "Desant al disc..." : "Entrenar Sistema Local"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
