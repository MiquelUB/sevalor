"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CheckCircle2, Download, FileText, XCircle } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";

interface PressupostPublicData {
  id: string;
  numero: string;
  titol: string;
  descripcio?: string | null;
  adreca_obra?: string | null;
  data_pressupost?: string | null;
  referencia_client?: string | null;
  elaborat_per?: string | null;
  vehicle_nom?: string | null;
  eines_resum?: Array<{ id?: string; nom: string; model?: string | null }>;
  desplacament_km?: number | null;
  desplacament_preu_km?: number | null;
  desplacament_import_fix?: number | null;
  estat: string;
  subtotal_brut?: number;
  descompte_global_pct?: number;
  descompte_global_import?: number;
  base_imposable: number;
  quota_iva: number;
  total: number;
  validesa_dies: number;
  forma_pagament?: string | null;
  percentatge_acompte?: number;
  termini_execucio?: string | null;
  notes_exclusions?: string | null;
  mencio_legal?: string | null;
  linies: Array<{
    seccio?: string | null;
    concepte: string;
    detall?: string | null;
    quantitat: number;
    preu_unitari: number;
    descompte_pct?: number;
    tipus_iva?: number;
    subtotal?: number;
  }>;
  created_at?: string | null;
  motiu_canvis_client?: string | null;
  client_nom?: string | null;
  client_nif?: string | null;
  client_adreca?: string | null;
  client_persona_contacte?: string | null;
  empresa: {
    nom: string;
    nif?: string | null;
    adreca?: string | null;
    primari_hsl?: string;
    secundari_hsl?: string;
  };
}

export default function PressupostPublicPage() {
  const params = useParams();
  const token = String(params.token || "");

  const [data, setData] = useState<PressupostPublicData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [comentari, setComentari] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const carregar = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${getApiBaseUrl()}/public/pressupostos/${encodeURIComponent(token)}`);
        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}));
          throw new Error(errBody.detail || "No s'ha trobat el pressupost sol·licitat.");
        }
        const json = (await res.json()) as PressupostPublicData;
        setData(json);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Error carregant el pressupost.");
      } finally {
        setLoading(false);
      }
    };
    if (token) carregar();
  }, [token]);

  const handleRespondre = async (accio: "APROVAR" | "REBUTJAR") => {
    if (!data) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(
        `${getApiBaseUrl()}/public/pressupostos/${encodeURIComponent(token)}/respondre`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            accio,
            comentari: comentari.trim() || null,
          }),
        }
      );
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || "No s'ha pogut registrar la teva resposta.");
      }
      const updated = await res.json();
      setData((prev) =>
        prev
          ? {
              ...prev,
              estat: updated.estat,
              motiu_canvis_client:
                accio === "REBUTJAR" ? comentari.trim() || prev.motiu_canvis_client : prev.motiu_canvis_client,
            }
          : prev
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en enviar la resposta.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-xs font-mono text-slate-500">
        Carregant pressupost...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
        <div className="max-w-md w-full rounded-2xl border border-rose-200 bg-white p-6 text-center space-y-2 shadow-sm">
          <XCircle className="w-8 h-8 text-rose-600 mx-auto" />
          <h1 className="text-base font-bold text-slate-900">Enllaç invàlid o caducat</h1>
          <p className="text-xs text-slate-600">{error || "Pressupost no disponible."}</p>
        </div>
      </div>
    );
  }

  const primaryHsl = data.empresa?.primari_hsl || "150 40 20";
  const hasRecursos = Boolean(
    data.vehicle_nom ||
      (data.eines_resum && data.eines_resum.length > 0) ||
      (data.desplacament_km && data.desplacament_km > 0) ||
      (data.desplacament_import_fix && data.desplacament_import_fix > 0)
  );

  // Agrupar línies per secció preservant l'ordre
  const seccions: Array<{ nom: string | null; linies: PressupostPublicData["linies"] }> = [];
  for (const lin of data.linies) {
    const sec = (lin.seccio || "").trim() || null;
    if (seccions.length > 0 && seccions[seccions.length - 1].nom === sec) {
      seccions[seccions.length - 1].linies.push(lin);
    } else {
      seccions.push({ nom: sec, linies: [lin] });
    }
  }

  return (
    <div
      className="min-h-screen bg-slate-50 py-10 px-4"
      style={{ ["--color-primary" as string]: primaryHsl }}
    >
      <div className="max-w-3xl mx-auto bg-white rounded-2xl border border-slate-200 shadow-lg overflow-hidden">
        <div
          className="px-6 py-5 text-white flex flex-wrap items-center justify-between gap-4"
          style={{ backgroundColor: `hsl(${primaryHsl})` }}
        >
          <div>
            <p className="text-xs uppercase tracking-widest opacity-80">Pressupost Comercial</p>
            <h1 className="text-xl font-bold mt-0.5">{data.empresa.nom}</h1>
            {data.empresa.nif && <p className="text-xs opacity-80">NIF: {data.empresa.nif}</p>}
          </div>
          <div className="text-right">
            <span className="font-mono text-sm font-bold block">N.º {data.numero}</span>
            <span className="inline-block mt-1 rounded-full bg-white/20 px-3 py-0.5 text-[11px] font-bold">
              {data.estat}
            </span>
          </div>
        </div>

        <div className="p-6 space-y-6 text-sm text-slate-700">
          <div className="flex flex-wrap justify-between gap-4 border-b border-slate-100 pb-4 text-xs">
            <div>
              <span className="text-slate-400 uppercase font-bold block">Client</span>
              <p className="font-bold text-slate-900 text-sm">{data.client_nom || "Client"}</p>
              {data.client_nif && <p className="text-slate-500">NIF: {data.client_nif}</p>}
              {data.client_adreca && <p className="text-slate-500">{data.client_adreca}</p>}
              {data.client_persona_contacte && (
                <p className="text-slate-500">Atenció: {data.client_persona_contacte}</p>
              )}
            </div>
            <div className="text-right">
              <span className="text-slate-400 uppercase font-bold block">Validesa</span>
              <p className="font-semibold">{data.validesa_dies} dies</p>
              {data.referencia_client && (
                <p className="text-slate-500">Ref: {data.referencia_client}</p>
              )}
              <a
                href={`${getApiBaseUrl()}/public/pressupostos/${encodeURIComponent(token)}/pdf`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 mt-1 text-xs font-bold hover:underline"
                style={{ color: `hsl(${primaryHsl})` }}
              >
                <Download className="w-3.5 h-3.5" /> Descarregar PDF oficial
              </a>
            </div>
          </div>

          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <FileText className="w-4 h-4" />
              <span>{data.titol}</span>
            </h2>
            {data.descripcio && (
              <p className="text-xs text-slate-600 mt-1 whitespace-pre-line">{data.descripcio}</p>
            )}
            {data.adreca_obra && (
              <p className="text-xs text-slate-600 mt-1">
                <strong>Ubicació dels treballs:</strong> {data.adreca_obra}
              </p>
            )}
          </div>

          {hasRecursos && (
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-xs space-y-1">
              <div className="font-semibold text-slate-500">Recursos operatius previstos</div>
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-slate-700">
                {data.vehicle_nom && (
                  <span>
                    <strong>Vehicle:</strong> {data.vehicle_nom}
                  </span>
                )}
                {data.desplacament_km != null && data.desplacament_km > 0 && (
                  <span>
                    <strong>Desplaçament:</strong> {data.desplacament_km} km
                  </span>
                )}
                {data.eines_resum && data.eines_resum.length > 0 && (
                  <span>
                    <strong>Eines:</strong> {data.eines_resum.map((e) => e.nom).join(", ")}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Partides */}
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-3 py-2.5">Descripció</th>
                  <th className="px-3 py-2.5 text-right">Quantitat</th>
                  <th className="px-3 py-2.5 text-right">Preu unitari</th>
                  <th className="px-3 py-2.5 text-right">IVA</th>
                  <th className="px-3 py-2.5 text-right">Import</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.linies.length === 0 ? (
                  <tr>
                    <td className="px-3 py-3">{data.titol}</td>
                    <td className="px-3 py-3 text-right">1.00</td>
                    <td className="px-3 py-3 text-right">{Number(data.total).toFixed(2)} €</td>
                    <td className="px-3 py-3 text-right">0%</td>
                    <td className="px-3 py-3 text-right font-semibold">
                      {Number(data.total).toFixed(2)} €
                    </td>
                  </tr>
                ) : (
                  seccions.map((sec, sIdx) => (
                    <React.Fragment key={sIdx}>
                      {sec.nom && (
                        <tr className="bg-slate-100/80">
                          <td colSpan={5} className="px-3 py-2 font-semibold text-slate-800">
                            {sec.nom}
                          </td>
                        </tr>
                      )}
                      {sec.linies.map((lin, i) => (
                        <tr key={`${sIdx}-${i}`}>
                          <td className="px-3 py-2.5">
                            <div className="font-medium text-slate-900">{lin.concepte}</div>
                            {lin.detall && (
                              <div className="text-[11px] text-slate-500 whitespace-pre-line">
                                {lin.detall}
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2.5 text-right tabular-nums">
                            {Number(lin.quantitat).toFixed(2)}
                          </td>
                          <td className="px-3 py-2.5 text-right tabular-nums">
                            {Number(lin.preu_unitari).toFixed(2)} €
                          </td>
                          <td className="px-3 py-2.5 text-right tabular-nums">
                            {Number(lin.tipus_iva ?? 21).toFixed(0)}%
                          </td>
                          <td className="px-3 py-2.5 text-right font-semibold tabular-nums">
                            {Number(lin.subtotal ?? lin.quantitat * lin.preu_unitari).toFixed(2)} €
                          </td>
                        </tr>
                      ))}
                    </React.Fragment>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 flex flex-wrap items-center justify-between gap-4 text-xs">
            <div className="flex flex-wrap gap-6">
              {data.descompte_global_pct && data.descompte_global_pct > 0 ? (
                <>
                  <div>
                    <span className="text-slate-500 block">Subtotal</span>
                    <span className="font-semibold tabular-nums">
                      {Number(data.subtotal_brut ?? data.base_imposable).toFixed(2)} €
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">
                      Descompte ({data.descompte_global_pct}%)
                    </span>
                    <span className="font-semibold tabular-nums text-rose-700">
                      -{Number(data.descompte_global_import ?? 0).toFixed(2)} €
                    </span>
                  </div>
                </>
              ) : null}
              <div>
                <span className="text-slate-500 block">Base Imposable</span>
                <span className="font-bold tabular-nums">{Number(data.base_imposable).toFixed(2)} €</span>
              </div>
              <div>
                <span className="text-slate-500 block">Quota IVA</span>
                <span className="font-bold tabular-nums">{Number(data.quota_iva).toFixed(2)} €</span>
              </div>
            </div>
            <div className="text-right">
              <span className="text-slate-500 block">TOTAL PRESSUPOST</span>
              <span
                className="text-2xl font-black tabular-nums"
                style={{ color: `hsl(${primaryHsl})` }}
              >
                {Number(data.total).toFixed(2)} €
              </span>
            </div>
          </div>

          {(data.forma_pagament || data.termini_execucio || data.notes_exclusions || data.mencio_legal) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs border-t border-slate-100 pt-4">
              <div>
                <h3 className="font-bold text-slate-800 mb-1">Condicions</h3>
                <ul className="list-disc pl-4 space-y-1 text-slate-600">
                  {data.forma_pagament && <li>Forma de pagament: {data.forma_pagament}</li>}
                  {data.percentatge_acompte && data.percentatge_acompte > 0 ? (
                    <li>
                      Acompte a l&apos;acceptació: {data.percentatge_acompte}% (
                      {((Number(data.total || 0) * data.percentatge_acompte) / 100).toFixed(2)} €)
                    </li>
                  ) : null}
                  {data.termini_execucio && <li>Termini d&apos;execució: {data.termini_execucio}</li>}
                  <li>Validesa de l&apos;oferta: {data.validesa_dies} dies</li>
                </ul>
              </div>
              {(data.notes_exclusions || data.mencio_legal) && (
                <div>
                  <h3 className="font-bold text-slate-800 mb-1">Notes i exclusions</h3>
                  {data.notes_exclusions && (
                    <p className="text-slate-600 whitespace-pre-line">{data.notes_exclusions}</p>
                  )}
                  {data.mencio_legal && (
                    <p className="text-slate-500 mt-1 whitespace-pre-line">{data.mencio_legal}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {data.estat === "PENDENT" ? (
            <div className="space-y-3 pt-2 border-t border-slate-100">
              <textarea
                rows={2}
                value={comentari}
                onChange={(e) => setComentari(e.target.value)}
                placeholder="Observacions opcionals (o motiu si demaneu canvis)..."
                className="w-full rounded-xl border border-slate-200 p-3 text-xs"
              />
              <div className="flex flex-wrap gap-3 justify-end">
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => handleRespondre("REBUTJAR")}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs font-bold text-rose-700 hover:bg-rose-100 cursor-pointer disabled:opacity-50"
                >
                  <XCircle className="w-4 h-4" /> Demanar Canvis
                </button>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => handleRespondre("APROVAR")}
                  className="inline-flex items-center gap-1.5 rounded-xl px-5 py-2.5 text-xs font-bold text-white cursor-pointer disabled:opacity-50"
                  style={{ backgroundColor: `hsl(${primaryHsl})` }}
                >
                  <CheckCircle2 className="w-4 h-4" /> Acceptar Pressupost
                </button>
              </div>
            </div>
          ) : (
            <div
              className={`rounded-xl p-4 text-xs font-semibold flex items-center gap-2 ${
                data.estat === "APROVAT"
                  ? "bg-emerald-50 border border-emerald-200 text-emerald-800"
                  : "bg-rose-50 border border-rose-200 text-rose-800"
              }`}
            >
              {data.estat === "APROVAT" ? (
                <>
                  <CheckCircle2 className="w-5 h-5" />
                  <span>
                    Pressupost acceptat! El nostre equip tècnic es posarà en contacte ben aviat per programar la intervenció.
                  </span>
                </>
              ) : (
                <>
                  <XCircle className="w-5 h-5" />
                  <span>
                    S&apos;han sol·licitat canvis sobre aquest pressupost
                    {data.motiu_canvis_client ? `: "${data.motiu_canvis_client}"` : "."}
                  </span>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
