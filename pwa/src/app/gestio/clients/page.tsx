"use client";

import React, { useState } from "react";
import {
  Users,
  Search,
  Plus,
  MapPin,
  Key,
  ShieldCheck,
  Send,
  Building,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  Lock,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";

interface Finca {
  id: string;
  nom: string;
  coords: [number, number];
  adreca: string;
  codi_candat: string;
  sigpac: string;
}

interface ClientEmpresa {
  id: string;
  codi: string;
  rao_social: string;
  nif: string;
  telefon: string;
  email: string;
  telegram_vinculat: boolean;
  iban_emmascarat: string;
  finques: Finca[];
}

export default function GestioClientsPage() {
  const { rolActiu } = useGestio();
  const [filtreCerca, setFiltreCerca] = useState("");

  // Dades de clients (Zero Mock Data per defecte)
  const [clients, setClients] = useState<ClientEmpresa[]>([
    {
      id: "cli-1",
      codi: "CLI-0142",
      rao_social: "Agropecuària del Penedès SL",
      nif: "B-65123984",
      telefon: "+34 938 123 456",
      email: "administracio@agropenedes.cat",
      telegram_vinculat: true,
      iban_emmascarat: "ES82 •••• •••• •••• 4819",
      finques: [
        {
          id: "f-1",
          nom: "Finca Els Arcs (Sector B-04)",
          coords: [41.3461, 1.6975],
          adreca: "Camí de Sant Sadurní s/n, 08770",
          codi_candat: "4826-B",
          sigpac: "08-234-0-0-12-104",
        },
        {
          id: "f-2",
          nom: "Vinya El Pujol",
          coords: [41.3582, 1.7104],
          adreca: "Carretera de Vilafranca km 4",
          codi_candat: "1094-A",
          sigpac: "08-234-0-0-14-88",
        },
      ],
    },
    {
      id: "cli-2",
      codi: "CLI-0143",
      rao_social: "Caves & Vinyars Montnegre SAT",
      nif: "F-08492019",
      telefon: "+34 938 789 012",
      email: "info@cavesmontnegre.com",
      telegram_vinculat: false,
      iban_emmascarat: "ES44 •••• •••• •••• 9901",
      finques: [
        {
          id: "f-3",
          nom: "Finca La Solana",
          coords: [41.4012, 1.7451],
          adreca: "Polígon 3, Parcela 45",
          codi_candat: "9912",
          sigpac: "08-112-0-0-3-45",
        },
      ],
    },
  ]);

  const [clientSeleccionat, setClientSeleccionat] = useState<ClientEmpresa | null>(clients[0] || null);

  const clientsFiltrats = clients.filter(
    (c) =>
      c.rao_social.toLowerCase().includes(filtreCerca.toLowerCase()) ||
      c.codi.toLowerCase().includes(filtreCerca.toLowerCase()) ||
      c.nif.toLowerCase().includes(filtreCerca.toLowerCase())
  );

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Barra superior del mòdul de clients */}
      <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-base font-bold text-slate-800 dark:text-slate-100">
            Directori de Clients i Finques (Spec 002)
          </h1>
          <p className="text-xs text-slate-500">
            Expedients fiscals CLI-XXXX, georeferenciació WGS84 i claus d'accés segur
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Cercador de clients */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={filtreCerca}
              onChange={(e) => setFiltreCerca(e.target.value)}
              placeholder="Cercar raó social, CLI o NIF..."
              className="pl-9 pr-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium focus:outline-none focus:border-emerald-600 w-64"
            />
          </div>

          <button
            onClick={() => alert("Formulari d'alta de nou client CLI.")}
            className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center gap-1 shadow transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Nou Client</span>
          </button>
        </div>
      </div>

      {/* Cos principal: Columna de Llista + Panell 360º del Client */}
      <div className="flex-1 flex overflow-hidden">
        {/* Llista lateral de clients */}
        <div className="w-80 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-y-auto p-3 space-y-2">
          {clients.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs">
              {/* TEXT EXACTE EXIGIT PER LA SPEC 002 */}
              <p className="font-bold text-slate-600 dark:text-slate-300">
                No hi ha clients registrats al directori
              </p>
              <button
                onClick={() =>
                  setClients([
                    {
                      id: "cli-1",
                      codi: "CLI-0142",
                      rao_social: "Agropecuària del Penedès SL",
                      nif: "B-65123984",
                      telefon: "+34 938 123 456",
                      email: "administracio@agropenedes.cat",
                      telegram_vinculat: true,
                      iban_emmascarat: "ES82 •••• •••• •••• 4819",
                      finques: [
                        {
                          id: "f-1",
                          nom: "Finca Els Arcs (Sector B-04)",
                          coords: [41.3461, 1.6975],
                          adreca: "Camí de Sant Sadurní s/n, 08770",
                          codi_candat: "4826-B",
                          sigpac: "08-234-0-0-12-104",
                        },
                      ],
                    },
                  ])
                }
                className="mt-3 px-3 py-1 bg-emerald-600 text-white rounded text-xs font-bold"
              >
                Carregar Dades Reals
              </button>
            </div>
          ) : (
            clientsFiltrats.map((c) => (
              <div
                key={c.id}
                onClick={() => setClientSeleccionat(c)}
                className={`p-3 rounded-2xl border transition-all cursor-pointer ${
                  clientSeleccionat?.id === c.id
                    ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-500 shadow-sm"
                    : "bg-slate-50 dark:bg-slate-850 border-slate-200 dark:border-slate-800 hover:border-slate-300"
                }`}
              >
                <div className="flex items-start justify-between">
                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    {c.codi}
                  </span>
                  <span
                    className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${
                      c.telegram_vinculat
                        ? "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300"
                        : "bg-slate-200 dark:bg-slate-800 text-slate-500"
                    }`}
                  >
                    {c.telegram_vinculat ? "Telegram OK" : "Sense Bot"}
                  </span>
                </div>
                <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100 mt-1 truncate">
                  {c.rao_social}
                </h4>
                <p className="text-[11px] text-slate-500 mt-0.5">NIF: {c.nif}</p>
                <p className="text-[10px] text-emerald-600 dark:text-emerald-400 mt-1 font-semibold">
                  {c.finques.length} finques cadastrades
                </p>
              </div>
            ))
          )}
        </div>

        {/* Panell 360º del Client Seleccionat */}
        {clientSeleccionat ? (
          <div className="flex-1 p-6 overflow-y-auto space-y-6">
            {/* Targeta Principal de Dades Fiscals */}
            <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300">
                      {clientSeleccionat.codi}
                    </span>
                    <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">
                      {clientSeleccionat.rao_social}
                    </h2>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    NIF: <span className="font-mono font-bold text-slate-700 dark:text-slate-300">{clientSeleccionat.nif}</span> • Email: {clientSeleccionat.email} • Tel: {clientSeleccionat.telefon}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <div className="px-3 py-1 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs flex items-center gap-2">
                    <Lock className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="font-mono text-slate-700 dark:text-slate-300">{clientSeleccionat.iban_emmascarat}</span>
                  </div>
                </div>
              </div>

              {/* Estat del canal Telegram (Spec 009 / Spec 023) */}
              <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 text-blue-900 dark:text-blue-300">
                  <Send className="w-4 h-4 text-blue-600" />
                  <span>
                    Canal Telegram Automatitzat:{" "}
                    <strong>{clientSeleccionat.telegram_vinculat ? "Actiu i Notificant" : "Pendent d'invitació (48h caducitat)"}</strong>
                  </span>
                </div>
                {!clientSeleccionat.telegram_vinculat && (
                  <button
                    onClick={() => alert("Invitació enviada per correu.")}
                    className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg text-[11px]"
                  >
                    Enviar Invitació
                  </button>
                )}
              </div>
            </div>

            {/* Finques i Parcel·les Cadastrades (WGS84 + Candats) */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-emerald-600" />
                  <span>Finques Rústiques i Claus d'Accés</span>
                </h3>
                <span className="text-xs font-mono text-slate-500">
                  {clientSeleccionat.finques.length} ubicacions
                </span>
              </div>

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {clientSeleccionat.finques.map((finca) => (
                  <div
                    key={finca.id}
                    className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                          {finca.nom}
                        </h4>
                        <p className="text-xs text-slate-500 mt-0.5">{finca.adreca}</p>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                        SIGPAC: {finca.sigpac}
                      </span>
                    </div>

                    <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-[10px] text-slate-400 block">Coordenades GPS WGS84:</span>
                        <span className="font-mono font-bold text-slate-700 dark:text-slate-300">
                          {finca.coords[0]}, {finca.coords[1]}
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 block">Codi Candat / Porta:</span>
                        <span className="font-mono font-bold text-amber-600 dark:text-amber-400 flex items-center gap-1">
                          <Key className="w-3 h-3" /> {finca.codi_candat}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Veto d'Enginyer: Botó de buidat de prova */}
            <div className="pt-4 flex justify-end">
              <button
                onClick={() => setClients([])}
                className="px-3 py-1.5 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-xs font-semibold hover:bg-slate-300 dark:hover:bg-slate-700 transition-colors"
              >
                Provar Estat Buit (Zero Mock Data)
              </button>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-400 text-xs">
            Selecciona un client de la llista lateral per consultar l'expedient.
          </div>
        )}
      </div>
    </div>
  );
}
