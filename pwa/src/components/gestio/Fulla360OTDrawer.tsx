"use client";

import React from "react";
import {
  X,
  FileText,
  MapPin,
  Users,
  Calendar,
  Package,
  Wrench,
  Clock,
  Layers,
  Edit,
  Truck,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Tag,
  Phone,
  ShieldCheck,
  UserPlus,
} from "lucide-react";
import Link from "next/link";
import { Feina } from "@/components/gestio/Map";

interface Fulla360OTDrawerProps {
  feina: Feina | null;
  isOpen: boolean;
  onClose: () => void;
  onEdit?: (feinaId: string) => void;
  onFocusMapa?: (feinaId: string) => void;
}

export function Fulla360OTDrawer({
  feina,
  isOpen,
  onClose,
  onEdit,
  onFocusMapa,
}: Fulla360OTDrawerProps) {
  if (!isOpen || !feina) return null;

  const materials = feina.linies_picking || [];
  const eines = feina.eines || [];

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/50 backdrop-blur-xs transition-opacity animate-in fade-in duration-150"
        onClick={onClose}
      />

      {/* Slide-over Drawer Panel */}
      <div className="relative w-full max-w-2xl bg-surface-container-lowest dark:bg-slate-900 h-full shadow-2xl flex flex-col border-l border-outline-variant/30 z-10 transition-transform duration-300 animate-in slide-in-from-right">
        {/* Header */}
        <div className="p-lg border-b border-outline-variant/20 flex items-center justify-between bg-surface-container-low/60 dark:bg-slate-800/50">
          <div className="flex items-center gap-md">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-full bg-primary text-white">
                  {feina.codi}
                </span>
                <span
                  className={`text-[10px] font-label-caps px-2 py-0.5 rounded-full font-bold uppercase ${
                    feina.estat === "PENDENT"
                      ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                      : feina.estat === "ASSIGNADA" || feina.estat === "PROGRAMADA"
                      ? "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300"
                      : ["COMPLETADA", "FINALITZADA", "TANCADA"].includes(feina.estat)
                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                      : "bg-primary/10 text-primary"
                  }`}
                >
                  {feina.estat}
                </span>
              </div>
              <h2 className="font-section-title text-base text-on-surface dark:text-white mt-1 line-clamp-1">
                Fulla 360° — {feina.titol}
              </h2>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-xl transition-colors cursor-pointer"
            title="Tancar Fulla 360°"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body (Scrollable) */}
        <div className="flex-1 overflow-y-auto p-lg space-y-lg">
          {/* 1. Resum Tècnic de la Feina */}
          <section className="bg-surface-container-low dark:bg-slate-800/40 p-md rounded-xl border border-outline-variant/30 space-y-sm">
            <span className="font-label-caps text-on-surface-variant uppercase block text-[11px]">
              Descripció Tècnica i Abast
            </span>
            <p className="text-sm text-on-surface dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
              {feina.descripcio || "Sense descripció tècnica registrada per a aquesta intervenció."}
            </p>
            <div className="flex items-center gap-md pt-2 border-t border-outline-variant/20 text-xs text-on-surface-variant">
              <span className="flex items-center gap-1 font-mono">
                <Calendar className="w-3.5 h-3.5 text-primary" />
                Data: {feina.data_planificacio || "Sense data"}
              </span>
              <span className="font-mono text-outline">
                Versió: v{feina.versio || 1}
              </span>
            </div>
          </section>

          {/* 2. Client i Localització */}
          <section className="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div className="bg-surface-container-lowest dark:bg-slate-900 p-md rounded-xl border border-outline-variant/30">
              <span className="font-label-caps text-on-surface-variant uppercase block mb-xs text-[11px] flex items-center gap-1">
                <Users className="w-3.5 h-3.5 text-primary" />
                <span>Client Titular</span>
              </span>
              <p className="font-body-strong text-primary dark:text-emerald-400 text-sm">
                {feina.client_nom || "Client no especificat"}
              </p>
            </div>

            <div className="bg-surface-container-lowest dark:bg-slate-900 p-md rounded-xl border border-outline-variant/30">
              <span className="font-label-caps text-on-surface-variant uppercase block mb-xs text-[11px] flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-secondary" />
                <span>Ubicació de Camp</span>
              </span>
              <p className="text-xs text-on-surface dark:text-slate-300">
                {feina.adreca || "Sense adreça registrada"}
              </p>
              {feina.latitud && feina.longitud && (
                <p className="text-[10px] font-mono text-outline mt-1">
                  GPS: {feina.latitud.toFixed(5)}, {feina.longitud.toFixed(5)}
                </p>
              )}
            </div>
          </section>

          {/* 3. Assignació Operativa & Colla de Treball */}
          <section className="bg-surface-container-lowest dark:bg-slate-900 p-md rounded-xl border border-outline-variant/30 space-y-md">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/20">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-primary" />
                <h3 className="font-body-strong text-sm text-on-surface dark:text-white">
                  Quadrilla Assignada a l&apos;Ordre
                </h3>
                {feina.operaris_assignats && feina.operaris_assignats.length > 0 && (
                  <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                    {feina.operaris_assignats.length} {feina.operaris_assignats.length === 1 ? "operari" : "treballadors"}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {onEdit && (
                  <button
                    type="button"
                    onClick={() => {
                      onEdit(feina.id);
                      onClose();
                    }}
                    className="px-2.5 py-1 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface text-[11px] font-bold transition-colors flex items-center gap-1 cursor-pointer"
                    title="Modificar els membres de la colla o capataz"
                  >
                    <Edit className="w-3 h-3 text-primary" />
                    <span>Modificar Colla</span>
                  </button>
                )}
                {onFocusMapa && (
                  <button
                    type="button"
                    onClick={() => {
                      onFocusMapa(feina.id);
                      onClose();
                    }}
                    className="px-2.5 py-1 rounded-lg bg-primary/10 hover:bg-primary text-primary hover:text-white text-[11px] font-bold transition-colors flex items-center gap-1 cursor-pointer"
                  >
                    <MapPin className="w-3 h-3" />
                    <span>Veure al Mapa</span>
                  </button>
                )}
              </div>
            </div>

            {/* Cap de Colla Responsable */}
            <div className="p-3 rounded-xl bg-primary/5 dark:bg-primary/10 border border-primary/20 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-primary text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-xs">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-primary text-white uppercase">
                      Cap de Colla · Responsable
                    </span>
                  </div>
                  <h4 className="text-sm font-bold text-on-surface dark:text-white mt-0.5">
                    {feina.cap_de_colla_nom || "Pendent d'assignar responsable"}
                  </h4>
                  <p className="text-[11px] text-on-surface-variant">
                    Responsable de la signatura, coordinació i conformitat al terreny
                  </p>
                </div>
              </div>
            </div>

            {/* Llistat de treballadors de la Colla */}
            {feina.operaris_assignats && feina.operaris_assignats.length > 0 ? (
              <div className="space-y-1.5">
                <span className="font-label-caps text-on-surface-variant uppercase block text-[10px]">
                  Membres de la Colla Assignats (Única Ordre Compartida)
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {feina.operaris_assignats.map((op) => (
                    <div
                      key={op.id}
                      className={`p-2.5 rounded-lg border flex items-center justify-between text-xs transition-colors ${
                        op.es_cap_de_colla
                          ? "border-primary/40 bg-primary/5 dark:bg-primary/10"
                          : "border-outline-variant/30 bg-surface-container-low/40 dark:bg-slate-800/40"
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <div
                          className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-[11px] shrink-0 ${
                            op.es_cap_de_colla
                              ? "bg-primary text-white"
                              : "bg-surface-container-high text-on-surface"
                          }`}
                        >
                          {op.nom[0]}
                          {op.cognoms ? op.cognoms[0] : ""}
                        </div>
                        <div className="min-w-0">
                          <p className="font-bold text-on-surface dark:text-white truncate">
                            {op.nom} {op.cognoms || ""}
                          </p>
                          <span className="text-[10px] text-on-surface-variant font-mono block truncate">
                            {op.es_cap_de_colla ? "Cap de Colla (Líder)" : op.rol || "Operari de Camp"}
                          </span>
                        </div>
                      </div>
                      {op.telefon && (
                        <a
                          href={`tel:${op.telefon}`}
                          className="p-1 rounded text-primary hover:bg-primary/10 transition-colors ml-1 shrink-0"
                          title={`Trucar a ${op.nom}`}
                        >
                          <Phone className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : feina.cap_de_colla_nom ? (
              <div className="p-3 rounded-lg border border-dashed border-outline-variant/40 bg-surface-container-low/20 text-xs text-on-surface-variant">
                <p>
                  Treball individual: La feina està assignada únicament a <strong>{feina.cap_de_colla_nom}</strong> com a responsable directe, sense altres operaris de suport.
                </p>
              </div>
            ) : (
              <div className="p-4 rounded-lg border border-dashed border-outline-variant/40 bg-surface-container-low/30 text-center text-xs text-on-surface-variant">
                <Users className="w-5 h-5 mx-auto mb-1 text-outline opacity-60" />
                <p>Cap equip ni cap de colla assignat a aquesta feina.</p>
              </div>
            )}
          </section>

          {/* 4. MATERIALS ASSIGNATS (FULLA DE PICKING) */}
          <section className="space-y-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-body-strong text-sm text-on-surface dark:text-white flex items-center gap-1.5">
                <Package className="w-4 h-4 text-primary" />
                <span>Material Assignat (Fulla de Picking)</span>
                <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                  {materials.length} {materials.length === 1 ? "article" : "articles"}
                </span>
              </h3>
            </div>

            {materials.length === 0 ? (
              <div className="p-6 rounded-xl border border-dashed border-outline-variant/40 text-center bg-surface-container-low/30">
                <Package className="w-6 h-6 text-outline mx-auto mb-1.5 opacity-60" />
                <p className="text-xs text-on-surface-variant">
                  Cap material reservat a la fulla de picking d&apos;aquesta ordre de treball.
                </p>
              </div>
            ) : (
              <div className="border border-outline-variant/30 rounded-xl overflow-hidden bg-surface-container-lowest dark:bg-slate-900 shadow-xs">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface-container-low dark:bg-slate-800/60 text-on-surface-variant border-b border-outline-variant/20 text-[11px] font-label-caps uppercase">
                    <tr>
                      <th className="py-2.5 px-3">Ref / Article</th>
                      <th className="py-2.5 px-3 text-center">Quantitat Prevista</th>
                      <th className="py-2.5 px-3 text-right">Estat Picking</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/10">
                    {materials.map((mat, idx) => (
                      <tr key={mat.id || idx} className="hover:bg-surface-container-low/40">
                        <td className="py-2.5 px-3">
                          <span className="font-mono text-[11px] font-bold text-primary mr-1.5">
                            [{mat.referencia_inventari || "S/REF"}]
                          </span>
                          <span className="font-medium text-on-surface dark:text-slate-200">
                            {mat.article_nom || "Article"}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-center font-data-tabular font-bold text-secondary">
                          {mat.quantitat_prevista} {mat.unitat_mesura || "uts"}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                            RESERVAT
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* 5. EINES I EQUIPS EN CUSTÒDIA */}
          <section className="space-y-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-body-strong text-sm text-on-surface dark:text-white flex items-center gap-1.5">
                <Wrench className="w-4 h-4 text-secondary" />
                <span>Eines i Equips en Custòdia</span>
                <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded-full bg-secondary-container/15 text-secondary">
                  {eines.length} {eines.length === 1 ? "eina" : "eines"}
                </span>
              </h3>
            </div>

            {eines.length === 0 ? (
              <div className="p-6 rounded-xl border border-dashed border-outline-variant/40 text-center bg-surface-container-low/30">
                <Wrench className="w-6 h-6 text-outline mx-auto mb-1.5 opacity-60" />
                <p className="text-xs text-on-surface-variant">
                  Cap eina ni maquinària en custòdia assignada a aquesta ordre de treball.
                </p>
              </div>
            ) : (
              <div className="border border-outline-variant/30 rounded-xl overflow-hidden bg-surface-container-lowest dark:bg-slate-900 divide-y divide-outline-variant/10 shadow-xs">
                {eines.map((eina, idx) => (
                  <div key={eina.id || idx} className="p-3 flex items-center justify-between hover:bg-surface-container-low/40">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-secondary-container/15 text-secondary flex items-center justify-center shrink-0">
                        <Wrench className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="text-xs font-bold text-on-surface dark:text-white">
                            {eina.nom}
                          </h4>
                          {eina.model && (
                            <span className="text-[11px] text-on-surface-variant">
                              ({eina.model})
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] font-mono text-outline mt-0.5">
                          SN: {eina.numero_serie}
                        </p>
                      </div>
                    </div>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">
                      {eina.estat || "CUSTODIADA"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* Footer Actions */}
        <div className="p-lg border-t border-outline-variant/20 bg-surface-container-low/40 dark:bg-slate-800/40 flex items-center justify-between">
          <div className="flex items-center gap-sm">
            <Link
              href="/gestio/planols"
              className="py-2 px-3 rounded-xl bg-surface-container-high hover:bg-surface-container-highest text-on-surface text-xs font-body-strong transition-colors"
            >
              Plànols GIS
            </Link>
            <Link
              href="/gestio/comptabilitat"
              className="py-2 px-3 rounded-xl bg-surface-container-high hover:bg-surface-container-highest text-on-surface text-xs font-body-strong transition-colors"
            >
              Facturació SIF
            </Link>
          </div>

          <div className="flex items-center gap-sm">
            {onEdit && (
              <button
                type="button"
                onClick={() => {
                  onEdit(feina.id);
                  onClose();
                }}
                className="py-2 px-4 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
              >
                <Edit className="w-3.5 h-3.5" />
                <span>Editar Ordre</span>
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="py-2 px-4 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface text-xs font-body-strong transition-colors cursor-pointer"
            >
              Tancar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
