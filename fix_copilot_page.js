const fs = require('fs');
const path = 'pwa/src/app/gestio/copilot/page.tsx';
let content = fs.readFileSync(path, 'utf8');

const novaPagina = `"use client";
import React from "react";
import { Sparkles, Layers, Send } from "lucide-react";
import { apiFetch } from "@/lib/api";

export default function CopilotEntrenament() {
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6 w-full animate-fade-in">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 dark:text-white flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-indigo-500" />
            Entrenament Copilot (RAG)
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Gestiona la Base de Coneixement de la teva IA local. El xat està disponible en tot moment a la icona flotant inferior dreta.
          </p>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 rounded-lg shadow p-6 border-l-4 border-indigo-500">
        <div className="flex items-center gap-3 mb-4">
          <div className="bg-indigo-100 dark:bg-indigo-900/50 p-2 rounded-full">
            <Layers className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-800 dark:text-white">Base de Coneixement</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Afegeix manuals, protocols i FAQs corporatives a l'entrenament local de l'IA.</p>
          </div>
        </div>

        <form onSubmit={async (e) => {
          e.preventDefault();
          const form = e.target;
          const dades = {
            titol: form.elements.namedItem("titol").value,
            contingut: form.elements.namedItem("contingut").value,
            tags: form.elements.namedItem("tags").value
          };
          try {
            const res = await apiFetch("/gestio/copilot/rag", {
              method: "POST",
              body: JSON.stringify(dades)
            });
            if (res.ok) {
              alert("Document afegit correctament a la xarxa neuronal local.");
              form.reset();
            } else {
              alert("Error afegint document.");
            }
          } catch (err) {
            alert("Error de xarxa en contactar amb el backend.");
          }
        }} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Títol del Protocol / Document</label>
            <input type="text" name="titol" required className="mt-1 block w-full rounded-xl border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2.5 border" placeholder="Ex: Protocol d'Actuació Manteniment Bomba..." />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Informació o Contingut</label>
            <textarea name="contingut" required rows="8" className="mt-1 block w-full rounded-xl border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2.5 border" placeholder="Descriu pas a pas el protocol o detalls tècnics..."></textarea>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Paraules Clau (Tags, separats per coma)</label>
            <input type="text" name="tags" className="mt-1 block w-full rounded-xl border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2.5 border" placeholder="ex: manteniment, bomba, hidràulic" />
          </div>
          
          <div className="pt-2">
            <button type="submit" className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-bold rounded-xl text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors">
              <Send className="mr-2 h-4 w-4" /> Entrenar Sistema Local
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
`;

fs.writeFileSync(path, novaPagina, 'utf8');
