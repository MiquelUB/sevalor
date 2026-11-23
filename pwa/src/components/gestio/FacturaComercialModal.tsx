"use client";

import React, { useEffect, useState } from "react";
import {
  X,
  FileText,
  ExternalLink,
  Loader2,
  Receipt,
  CheckCircle2,
  Clock,
  AlertCircle,
} from "lucide-react";
import { apiFetch, extractTenantId, getApiBaseUrl, getAuthToken } from "@/lib/api";

export interface FacturaLiniaComercial {
  id: string;
  concepte: string;
  quantitat: number;
  preu_venda_unitari: number;
  tipus_iva: number;
  descompte_aplicat_pct: number;
  subtotal: number;
  obra_id?: string | null;
}

export interface FacturaComercialDetall {
  id: string;
  client_id?: string | null;
  client_nom?: string | null;
  client_nif?: string | null;
  serie: string;
  numero_factura: number;
  data_emissio: string;
  data_venciment?: string | null;
  estat_document: string;
  estat_cobrament: string;
  base_imposable: number;
  quota_iva: number;
  import_suplits: number;
  import_retencio: number;
  import_retencio_garantia_4308: number;
  liquid_exigible: number;
  es_inversio_subjecte_passiu: boolean;
  ordres_treball_codis: string[];
  linies: FacturaLiniaComercial[];
}

interface FacturaComercialModalProps {
  facturaId: string | null;
  onClose: () => void;
}

export function FacturaComercialModal({ facturaId, onClose }: FacturaComercialModalProps) {
  const [detall, setDetall] = useState<FacturaComercialDetall | null>(null);
  const [loading, setLoading] = useState(false);
  const [openingPdf, setOpeningPdf] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!facturaId) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<FacturaComercialDetall>(
          `/gestio/operativa-financera/factures/${facturaId}`
        );
        if (!cancelled) setDetall(data);
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "No s'ha pogut carregar el detall del document.");
          setDetall(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [facturaId]);

  if (!facturaId) return null;

  const handleObrirPdf = async () => {
    setOpeningPdf(true);
    setError(null);
    try {
      const token = getAuthToken();
      const tenantId = extractTenantId();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (tenantId) {
        headers["X-Empresa-ID"] = tenantId;
        headers["X-Tenant-ID"] = tenantId;
      }
      const res = await fetch(
        `${getApiBaseUrl()}/gestio/operativa-financera/factures/${facturaId}/pdf`,
        { headers, credentials: "include" }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Error HTTP ${res.status} generant el PDF`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error obrint el PDF del document.");
    } finally {
      setOpeningPdf(false);
    }
  };

  const esPrefactura = detall?.estat_document === "ESBORRANY_PREFACTURA";

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl max-h-[90vh] bg-surface-container-lowest dark:bg-slate-900 rounded-2xl border border-outline-variant/40 shadow-2xl flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-outline-variant/25 bg-surface-container-low/70 dark:bg-slate-800/60 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <Receipt className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-sm font-extrabold text-primary">
                  {detall
                    ? `${detall.serie}-${String(detall.numero_factura).padStart(4, "0")}`
                    : "Document Comercial"}
                </span>
                {detall && (
                  <span
                    className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                      esPrefactura
                        ? "bg-amber-100 text-amber-900 border border-amber-300"
                        : "bg-emerald-100 text-emerald-800 border border-emerald-300"
                    }`}
                  >
                    {esPrefactura ? "Pre-factura (Esborrany)" : detall.estat_document}
                  </span>
                )}
              </div>
              <p className="text-xs text-on-surface-variant truncate mt-0.5">
                {detall?.client_nom || "Consulta comercial de client"}
                {detall?.client_nif ? ` · NIF ${detall.client_nif}` : ""}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              disabled={openingPdf || loading || !detall}
              onClick={handleObrirPdf}
              className="px-3.5 py-2 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold inline-flex items-center gap-1.5 shadow-sm transition-all disabled:opacity-50 cursor-pointer"
            >
              {openingPdf ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <ExternalLink className="w-3.5 h-3.5" />
              )}
              <span>{openingPdf ? "Generant PDF..." : "Veure PDF"}</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-xl text-on-surface-variant hover:bg-surface-container transition-colors cursor-pointer"
              title="Tancar"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {loading ? (
            <div className="py-12 text-center text-xs font-mono text-on-surface-variant flex flex-col items-center gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
              <span>Carregant detall comercial del document...</span>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-error-container/25 border border-error text-error text-xs font-semibold flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : detall ? (
            <>
              {/* Metadades i OTs vinculades */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-3 rounded-xl bg-surface-container-low dark:bg-slate-800/50 border border-outline-variant/25">
                  <span className="text-[10px] font-label-caps uppercase text-on-surface-variant block">
                    Data Emissió
                  </span>
                  <span className="font-mono font-bold text-on-surface dark:text-white mt-0.5 block">
                    {new Date(detall.data_emissio).toLocaleDateString("ca-ES")}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-surface-container-low dark:bg-slate-800/50 border border-outline-variant/25">
                  <span className="text-[10px] font-label-caps uppercase text-on-surface-variant block">
                    Venciment
                  </span>
                  <span className="font-mono font-bold text-on-surface dark:text-white mt-0.5 block">
                    {detall.data_venciment
                      ? new Date(detall.data_venciment).toLocaleDateString("ca-ES")
                      : "—"}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-surface-container-low dark:bg-slate-800/50 border border-outline-variant/25">
                  <span className="text-[10px] font-label-caps uppercase text-on-surface-variant block">
                    Estat Cobrament
                  </span>
                  <span className="font-bold text-on-surface dark:text-white mt-0.5 inline-flex items-center gap-1">
                    {detall.estat_cobrament === "COBRADA" ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Clock className="w-3.5 h-3.5 text-amber-600" />
                    )}
                    {detall.estat_cobrament}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-surface-container-low dark:bg-slate-800/50 border border-outline-variant/25">
                  <span className="text-[10px] font-label-caps uppercase text-on-surface-variant block">
                    Ordres Vinculades
                  </span>
                  <span className="font-mono font-bold text-primary mt-0.5 block truncate">
                    {detall.ordres_treball_codis.length > 0
                      ? detall.ordres_treball_codis.join(", ")
                      : "—"}
                  </span>
                </div>
              </div>

              {/* Taula de línies comercials */}
              <div className="border border-outline-variant/30 rounded-xl overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface-container-low dark:bg-slate-800/60 border-b border-outline-variant/25 text-[10px] font-label-caps uppercase text-on-surface-variant">
                    <tr>
                      <th className="py-2.5 px-3">Concepte</th>
                      <th className="py-2.5 px-3 text-right">Quantitat</th>
                      <th className="py-2.5 px-3 text-right">Preu Unit.</th>
                      <th className="py-2.5 px-3 text-right">IVA</th>
                      <th className="py-2.5 px-3 text-right">Subtotal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/15">
                    {detall.linies.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-6 text-center text-on-surface-variant">
                          Cap línia registrada en aquest document.
                        </td>
                      </tr>
                    ) : (
                      detall.linies.map((lin) => (
                        <tr key={lin.id} className="hover:bg-surface-container-low/40">
                          <td className="py-2.5 px-3 font-medium text-on-surface dark:text-slate-100">
                            {lin.concepte}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono">
                            {Number(lin.quantitat).toFixed(2)}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono">
                            {Number(lin.preu_venda_unitari).toFixed(2)} €
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-on-surface-variant">
                            {Number(lin.tipus_iva).toFixed(0)}%
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono font-bold text-on-surface dark:text-white">
                            {Number(lin.subtotal).toFixed(2)} €
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Resum d'imports comercials */}
              <div className="flex justify-end">
                <div className="w-full sm:w-80 p-4 rounded-xl bg-surface-container-low dark:bg-slate-800/60 border border-outline-variant/30 space-y-2 text-xs">
                  <div className="flex justify-between text-on-surface-variant">
                    <span>Base Imposable</span>
                    <span className="font-mono font-semibold text-on-surface dark:text-white">
                      {Number(detall.base_imposable).toFixed(2)} €
                    </span>
                  </div>
                  <div className="flex justify-between text-on-surface-variant">
                    <span>Quota IVA</span>
                    <span className="font-mono font-semibold text-on-surface dark:text-white">
                      {Number(detall.quota_iva).toFixed(2)} €
                    </span>
                  </div>
                  {Number(detall.import_suplits || 0) > 0 && (
                    <div className="flex justify-between text-on-surface-variant">
                      <span>Suplerts</span>
                      <span className="font-mono">{Number(detall.import_suplits).toFixed(2)} €</span>
                    </div>
                  )}
                  {Number(detall.import_retencio || 0) > 0 && (
                    <div className="flex justify-between text-on-surface-variant">
                      <span>Retenció IRPF</span>
                      <span className="font-mono">-{Number(detall.import_retencio).toFixed(2)} €</span>
                    </div>
                  )}
                  {Number(detall.import_retencio_garantia_4308 || 0) > 0 && (
                    <div className="flex justify-between text-on-surface-variant">
                      <span>Retenció Garantia</span>
                      <span className="font-mono">
                        -{Number(detall.import_retencio_garantia_4308).toFixed(2)} €
                      </span>
                    </div>
                  )}
                  <div className="pt-2 border-t border-outline-variant/30 flex justify-between items-baseline">
                    <span className="font-extrabold uppercase tracking-wider text-primary">
                      Total Client
                    </span>
                    <span className="font-mono text-lg font-black text-primary">
                      {Number(detall.liquid_exigible).toFixed(2)} €
                    </span>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="py-10 text-center text-xs text-on-surface-variant flex flex-col items-center gap-2">
              <FileText className="w-6 h-6 opacity-50" />
              <span>Document no disponible.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
