"use client";

import React from "react";

interface EvolucioPunt {
  mes: string;
  ingressos: number;
  despeses: number;
  ebitda_pct: number;
}

interface VerticalMarge {
  vertical: string;
  marge_eur: number;
}

export function Evolucio12MChart({ data }: { data: EvolucioPunt[] }) {
  const maxVal = Math.max(
    1,
    ...data.flatMap((d) => [Math.abs(d.ingressos), Math.abs(d.despeses)])
  );

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">
            Evolució 12 Mesos (Ingressos vs. Despeses)
          </h3>
          <p className="text-xs text-slate-500">
            Dades reals SQL en base a factures emeses i estructura
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-primary" />
            Ingressos
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-slate-300" />
            Despeses
          </span>
        </div>
      </div>

      <div className="grid grid-cols-12 items-end gap-2 pt-4 h-44 border-b border-slate-100">
        {data.map((d) => {
          const hIng = Math.max(4, Math.round((d.ingressos / maxVal) * 100));
          const hDesp = Math.max(4, Math.round((d.despeses / maxVal) * 100));
          return (
            <div
              key={d.mes}
              className="group relative flex flex-col items-center justify-end h-full"
              title={`${d.mes} | Ingressos: ${d.ingressos.toFixed(2)} € | Despeses: ${d.despeses.toFixed(2)} €`}
            >
              <div className="flex items-end gap-0.5 w-full justify-center h-32">
                <div
                  className="w-2.5 rounded-t bg-primary transition-all"
                  style={{ height: `${hIng}%` }}
                />
                <div
                  className="w-2.5 rounded-t bg-slate-300 transition-all"
                  style={{ height: `${hDesp}%` }}
                />
              </div>
              <span className="mt-1.5 text-[10px] text-slate-500 font-medium">
                {d.mes.slice(5)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function WaterfallChart({
  waterfall,
}: {
  waterfall: Record<string, number>;
}) {
  const steps = [
    { key: "facturacio_bruta", label: "Facturació", pos: true },
    { key: "cost_materials_i_merma", label: "Materials/Merma", pos: false },
    { key: "cost_ma_obra_directa", label: "Mà d'Obra", pos: false },
    { key: "cost_tiquets_i_flota", label: "Tiquets/Flota", pos: false },
    { key: "despeses_fixes", label: "Fixes", pos: false },
    { key: "benefici_net_ebitda", label: "EBITDA Net", pos: true },
  ];
  const maxAbs = Math.max(
    1,
    ...steps.map((s) => Math.abs(Number(waterfall[s.key] || 0)))
  );

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="text-sm font-semibold text-slate-900">
        Cascada de Resultats (Waterfall P&amp;L)
      </h3>
      <p className="mb-4 text-xs text-slate-500">
        Desglossament del marge brut fins a l&apos;EBITDA operatiu
      </p>
      <div className="space-y-2.5">
        {steps.map((s) => {
          const val = Number(waterfall[s.key] || 0);
          const pct = Math.min(100, Math.round((Math.abs(val) / maxAbs) * 100));
          const isNeg = val < 0;
          return (
            <div key={s.key} className="grid grid-cols-12 items-center gap-2 text-xs">
              <span className="col-span-4 text-slate-600 truncate">{s.label}</span>
              <div className="col-span-5 h-3 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    s.key === "benefici_net_ebitda"
                      ? val >= 0
                        ? "bg-emerald-600"
                        : "bg-rose-600"
                      : isNeg
                      ? "bg-amber-500"
                      : "bg-primary"
                  }`}
                  style={{ width: `${Math.max(2, pct)}%` }}
                />
              </div>
              <span
                className={`col-span-3 text-right font-semibold tabular-nums ${
                  isNeg ? "text-rose-700" : "text-slate-900"
                }`}
              >
                {val.toLocaleString("ca-ES", { minimumFractionDigits: 2 })} €
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function TresoreriaProjeccioChart({
  cashFlowReal,
  p30,
  p60,
  p90,
  guardacaixaIva,
}: {
  cashFlowReal: number;
  p30: number;
  p60: number;
  p90: number;
  guardacaixaIva: number;
}) {
  const punts = [
    { label: "Avui", val: cashFlowReal },
    { label: "+30d", val: p30 },
    { label: "+60d", val: p60 },
    { label: "+90d", val: p90 },
  ];
  const minV = Math.min(0, ...punts.map((p) => p.val));
  const maxV = Math.max(100, ...punts.map((p) => p.val));
  const span = Math.max(1, maxV - minV);

  const coords = punts
    .map((p, idx) => {
      const x = 25 + idx * 80;
      const y = 110 - ((p.val - minV) / span) * 85;
      return `${x},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">
            Projecció de Tresoreria (30 / 60 / 90 dies)
          </h3>
          <p className="text-xs text-slate-500">
            Inclou venciments de cobrament i Burn Rate mensual
          </p>
        </div>
        <span className="rounded-md bg-amber-50 border border-amber-200 px-2 py-1 text-[11px] font-medium text-amber-800">
          Guardacaixa IVA 303: {guardacaixaIva.toFixed(2)} €
        </span>
      </div>

      <svg viewBox="0 0 300 130" className="w-full h-36">
        <line x1="15" y1="110" x2="285" y2="110" stroke="#e2e8f0" strokeWidth="1" />
        <polyline
          fill="none"
          stroke="currentColor"
          className="text-primary"
          strokeWidth="2.5"
          points={coords}
        />
        {punts.map((p, idx) => {
          const x = 25 + idx * 80;
          const y = 110 - ((p.val - minV) / span) * 85;
          return (
            <g key={p.label}>
              <circle
                cx={x}
                cy={y}
                r="4"
                className={p.val < 0 ? "fill-rose-600" : "fill-primary"}
              />
              <text
                x={x}
                y="125"
                textAnchor="middle"
                className="fill-slate-500 text-[10px]"
              >
                {p.label}
              </text>
              <text
                x={x}
                y={Math.max(12, y - 8)}
                textAnchor="middle"
                className="fill-slate-800 text-[9px] font-semibold"
              >
                {p.val.toFixed(0)}€
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function AgingBarChart({
  aging,
  retencionsExcloses,
}: {
  aging: Record<string, number>;
  retencionsExcloses: number;
}) {
  const trams = [
    { key: "AL_DIA", label: "Al dia", color: "bg-emerald-500" },
    { key: "1_30_DIES", label: "1-30 dies", color: "bg-amber-400" },
    { key: "31_60_DIES", label: "31-60 dies", color: "bg-orange-500" },
    { key: "CRITIC_MES_90", label: "Crític >90d", color: "bg-rose-600" },
  ];
  const total = Math.max(
    1,
    trams.reduce((acc, t) => acc + Number(aging[t.key] || 0), 0)
  );

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">
            Semàfor d&apos;Aging d&apos;Impagats
          </h3>
          <p className="text-xs text-slate-500">
            Exclou {retencionsExcloses.toFixed(2)} € de retencions garantia (4308)
          </p>
        </div>
      </div>

      <div className="flex h-4 w-full overflow-hidden rounded-full bg-slate-100 mb-4">
        {trams.map((t) => {
          const val = Number(aging[t.key] || 0);
          const w = (val / total) * 100;
          if (w <= 0) return null;
          return (
            <div
              key={t.key}
              className={t.color}
              style={{ width: `${w}%` }}
              title={`${t.label}: ${val.toFixed(2)} €`}
            />
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        {trams.map((t) => (
          <div
            key={t.key}
            className="flex items-center justify-between rounded-lg bg-slate-50 px-2.5 py-1.5"
          >
            <span className="flex items-center gap-1.5 text-slate-700">
              <span className={`h-2 w-2 rounded-full ${t.color}`} />
              {t.label}
            </span>
            <span className="font-semibold tabular-nums text-slate-900">
              {Number(aging[t.key] || 0).toFixed(2)} €
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MargesVerticalChart({
  verticals,
}: {
  verticals: VerticalMarge[];
}) {
  const maxM = Math.max(1, ...verticals.map((v) => Math.abs(v.marge_eur)));
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="text-sm font-semibold text-slate-900">
        Marges per Línia de Negoci (Vertical)
      </h3>
      <p className="mb-3 text-xs text-slate-500">
        Instal·lacions, manteniments i avaries (PVP - PMP materials)
      </p>
      {verticals.length === 0 ? (
        <p className="text-xs text-slate-400 py-6 text-center">
          Sense ordres de treball imputades al període.
        </p>
      ) : (
        <div className="space-y-2.5">
          {verticals.map((v) => {
            const pct = Math.round((Math.abs(v.marge_eur) / maxM) * 100);
            return (
              <div key={v.vertical} className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="font-medium text-slate-700">{v.vertical}</span>
                  <span className="font-semibold tabular-nums text-slate-900">
                    {v.marge_eur.toFixed(2)} €
                  </span>
                </div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.max(4, pct)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
