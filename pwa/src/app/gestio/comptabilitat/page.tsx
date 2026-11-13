"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Banknote,
  Building2,
  CheckCircle2,
  Download,
  FileCheck2,
  FileText,
  Lock,
  Plus,
  QrCode,
  Receipt,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Users,
  X,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch } from "@/lib/api";
import {
  AgingBarChart,
  Evolucio12MChart,
  MargesVerticalChart,
  TresoreriaProjeccioChart,
  WaterfallChart,
} from "@/components/comptabilitat/EconomicCharts";

interface Factura {
  id: string;
  numero_factura: number;
  serie: string;
  client_id: string;
  base_imposable: number;
  quota_iva: number;
  import_retencio: number;
  import_suplits: number;
  liquid_exigible: number;
  hash_sha256: string;
  hash_anterior?: string;
  estat_cobrament: string;
  estat_enviament: string;
}

interface DashboardEconomic {
  facturacio_neta: number;
  cost_directe_obra: number;
  marge_brut_eur: number;
  marge_brut_pct: number;
  despeses_fixes_estructura: number;
  ebitda_operatiu_eur: number;
  ebitda_operatiu_pct: number;
  break_even_facturacio_necessaria: number;
  break_even_assolit: boolean;
  alertes_erosio_marge: Array<{
    article_id: string;
    referencia: string;
    nom: string;
    preu_cost_mitja: number;
    preu_cost_ultim: number;
    preu_venda_tarifa: number;
    marge_actual_pct: number;
    llindar_minim_pct: number;
  }>;
  capital_immobilitzat_90d_eur: number;
  cash_flow_operatiu_real: number;
  burn_rate_mes_seguent: number;
  guardacaixa_fiscal_iva_303: number;
  projeccio_tresoreria_30d: number;
  projeccio_tresoreria_60d: number;
  projeccio_tresoreria_90d: number;
  dso_dies_mitjana_cobrament: number;
  aging_impagats: Record<string, number>;
  total_retencions_garantia_4308_excloses_aging: number;
  cost_flota_eur_km_mitja: number;
  mrr_mensual_actiu: number;
  cobertura_estructura_mrr_pct: number;
  alerta_concentracio_pareto_25pct: boolean;
  waterfall_mensual: Record<string, number>;
  evolucio_12m: Array<{
    mes: string;
    ingressos: number;
    despeses: number;
    ebitda_pct: number;
  }>;
  marges_per_vertical: Array<{ vertical: string; marge_eur: number }>;
}

interface WIPControl {
  total_wip_valorat_pvp: number;
  total_cost_wip_avancat: number;
  nombre_ots_en_wip: number;
  nombre_ots_envellides_critiques: number;
  items: Array<{
    ordre_treball_id: string;
    codi_ot: string;
    client_id: string;
    dies_en_wip: number;
    valor_wip_pvp: number;
    cost_wip_avancat: number;
    es_wip_envellit_alerta: boolean;
  }>;
}

interface RetencioGarantia {
  id: string;
  tipus: string;
  factura_client_id?: string;
  import_retingut: number;
  data_retencio: string;
  data_venciment_garantia: string;
  dies_fins_venciment: number;
  estat: string;
  alerta_venciment_proper: boolean;
}

interface Art80Item {
  factura_id: string;
  numero_factura: number;
  serie: string;
  data_emissio: string;
  data_limit_art80: string;
  base_imposable: number;
  quota_iva: number;
  dies_impagada: number;
  estat_art80: string;
}

interface OperariCost {
  usuari_id: string;
  nom_complet: string;
  cost_hora_referencia: number;
  salari_brut_i_ss_visible: string | null;
  hores_fitxades_mes: number;
  hores_imputades_ot_mes: number;
  ratio_eficiencia_pct: number;
  cost_hora_efectiu_mensual: number | null;
  alerta_improductivitat: boolean;
}

interface ContracteMRR {
  contracte_id: string;
  codi_contracte: string;
  quota_mensual_mrr: number;
  cost_real_ots_periode: number;
  marge_net_contracte: number;
  sinistralitat_pct: number;
  semafor: string;
}

interface TiquetDespesa {
  id: string;
  categoria: string;
  data_tiquet: string;
  nif_emissor?: string;
  rao_social?: string;
  base_imposable: number;
  quota_iva: number;
  import_total: number;
  estat_aprovacio: string;
  estat_fiscal: string;
  requereix_aprovacio_boss: boolean;
  custodia_paper_confirmada: boolean;
}

interface Norma43Moviment {
  data_operacio: string;
  concepte: string;
  import_moviment: number;
  saldo_resultant: number;
  huella_sha256: string;
  duplicat_rebutjat: boolean;
  factura_suggerida_id?: string;
}

type TabKey =
  | "DASHBOARD"
  | "VERIFACTU"
  | "WIP_CONTROL"
  | "OPERARIS_MRR"
  | "TIQUETS"
  | "NORMA43";

export default function GestioComptabilitatPage() {
  const { rolActiu } = useGestio();
  const [tabActiva, setTabActiva] = useState<TabKey>("DASHBOARD");
  const [criteriCaixa, setCriteriCaixa] = useState(false);
  const [periode, setPeriode] = useState("MES_ACTUAL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dashboard, setDashboard] = useState<DashboardEconomic | null>(null);
  const [factures, setFactures] = useState<Factura[]>([]);
  const [wip, setWip] = useState<WIPControl | null>(null);
  const [retencions, setRetencions] = useState<RetencioGarantia[]>([]);
  const [art80, setArt80] = useState<Art80Item[]>([]);
  const [operarisCost, setOperarisCost] = useState<OperariCost[]>([]);
  const [contractesMrr, setContractesMrr] = useState<ContracteMRR[]>([]);
  const [tiquets, setTiquets] = useState<TiquetDespesa[]>([]);

  // Estat Norma 43
  const [textC43, setTextC43] = useState("");
  const [movimentsC43, setMovimentsC43] = useState<Norma43Moviment[]>([]);

  // Modal Emissió Factura Veri*factu
  const [modalFactura, setModalFactura] = useState(false);
  const [clientIdInput, setClientIdInput] = useState("");
  const [concepteInput, setConcepteInput] = useState("");
  const [preuInput, setPreuInput] = useState("0");
  const [esIsp, setEsIsp] = useState(false);
  const [retGarantiaPct, setRetGarantiaPct] = useState("0");

  const carregarDades = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dashRes, factRes, wipRes, retRes, art80Res, opRes, mrrRes, tiqRes] =
        await Promise.all([
          apiFetch<DashboardEconomic>(
            `/gestio/comptabilitat/dashboard-economic?criteri_caixa=${criteriCaixa}`
          ),
          apiFetch<Factura[]>("/gestio/comptabilitat/factures"),
          apiFetch<WIPControl>("/gestio/comptabilitat/wip-control"),
          apiFetch<RetencioGarantia[]>("/gestio/comptabilitat/retencions-garantia"),
          apiFetch<Art80Item[]>("/gestio/comptabilitat/art80-incobrables"),
          apiFetch<OperariCost[]>("/gestio/comptabilitat/operaris-cost-efectiu"),
          apiFetch<ContracteMRR[]>("/gestio/comptabilitat/contractes-mrr-auditoria"),
          apiFetch<TiquetDespesa[]>("/gestio/comptabilitat/tiquets"),
        ]);

      setDashboard(dashRes);
      setFactures(factRes || []);
      setWip(wipRes);
      setRetencions(retRes || []);
      setArt80(art80Res || []);
      setOperarisCost(opRes || []);
      setContractesMrr(mrrRes || []);
      setTiquets(tiqRes || []);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error carregant la suite econòmica";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (rolActiu !== "ENGINYER") {
      carregarDades();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rolActiu, criteriCaixa, periode]);

  if (rolActiu === "ENGINYER") {
    return (
      <div className="flex min-h-[70vh] items-center justify-center p-6">
        <div className="max-w-md rounded-2xl border border-rose-200 bg-rose-50/70 p-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-rose-100 text-rose-700">
            <Lock className="h-7 w-7" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">
            Veto d&apos;Enginyer (HTTP 403 Forbidden)
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Per mandat constitucional (Zero-Trust C-05), el rol{" "}
            <strong>ENGINYER</strong> té bloquejat l&apos;accés a comptabilitat,
            EBITDA, IBANs i salaris reals.
          </p>
        </div>
      </div>
    );
  }

  const handleEmetreFactura = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const avui = new Date().toISOString().slice(0, 10);
      await apiFetch("/gestio/comptabilitat/factures/emetre", {
        method: "POST",
        body: JSON.stringify({
          client_id: clientIdInput,
          serie: "F",
          data_emissio: avui,
          data_venciment: avui,
          es_inversio_subjecte_passiu: esIsp,
          retencio_garantia_pct: Number(retGarantiaPct || 0),
          linies: [
            {
              concepte: concepteInput,
              quantitat: 1,
              preu_venda_unitari: Number(preuInput || 0),
              tipus_iva_pct: esIsp ? 0 : 21,
            },
          ],
        }),
      });
      setModalFactura(false);
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en emetre factura");
    }
  };

  const handleAuditarTiquet = async (id: string, accio: "APROVAT" | "REBUTJAT") => {
    try {
      await apiFetch(`/gestio/comptabilitat/tiquets/${id}/auditar`, {
        method: "POST",
        body: JSON.stringify({ accio, custodia_paper_confirmada: true }),
      });
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error auditant tiquet");
    }
  };

  const handleReclamarGarantia = async (id: string) => {
    try {
      await apiFetch(`/gestio/comptabilitat/retencions-garantia/${id}/reclamar`, {
        method: "POST",
      });
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error reclamant garantia");
    }
  };

  const handleConciliarNorma43 = async (confirmarHitl: boolean) => {
    if (!textC43.trim()) return;
    try {
      const res = await apiFetch<Norma43Moviment[]>(
        "/gestio/comptabilitat/norma43/conciliar",
        {
          method: "POST",
          body: JSON.stringify({
            contingut_c43: textC43,
            confirmar_conciliacio_hitl: confirmarHitl,
          }),
        }
      );
      setMovimentsC43(res || []);
      if (confirmarHitl) await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error conciliant CSB 43");
    }
  };

  const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode }> = [
    { key: "DASHBOARD", label: "Suite Econòmica & KPIs", icon: <TrendingUp className="h-4 w-4" /> },
    { key: "VERIFACTU", label: "Veri*factu, Art.80 & 4308", icon: <QrCode className="h-4 w-4" /> },
    { key: "WIP_CONTROL", label: "WIP Obra en Curs", icon: <Activity className="h-4 w-4" /> },
    { key: "OPERARIS_MRR", label: "Operaris & MRR", icon: <Users className="h-4 w-4" /> },
    { key: "TIQUETS", label: "Tiquets de Camp", icon: <Receipt className="h-4 w-4" /> },
    { key: "NORMA43", label: "Banc Norma 43", icon: <Banknote className="h-4 w-4" /> },
  ];

  return (
    <div className="space-y-6 p-6">
      {/* Capçalera Executiva amb Selector Global (RF-01, RF-02) */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Suite de Control Financer i Comptabilitat (Spec 007 v5.0)
          </h1>
          <p className="text-sm text-slate-500">
            P&amp;L en temps real, Veri*factu RD 1007/2023, Tresoreria 30/60/90d i Auditoria Zero-Mock
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={periode}
            onChange={(e) => setPeriode(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700"
          >
            <option value="MES_ACTUAL">Mes Actual</option>
            <option value="TRIMESTRE_ACTUAL">Trimestre Actual</option>
            <option value="YTD">Acumulat Any (YTD)</option>
            <option value="EXERCICI_FISCAL">Exercici Fiscal Complet</option>
          </select>

          <button
            type="button"
            onClick={() => setCriteriCaixa((prev) => !prev)}
            className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${
              criteriCaixa
                ? "border-primary bg-primary/10 text-primary"
                : "border-slate-200 bg-white text-slate-700"
            }`}
          >
            Criteri: {criteriCaixa ? "Caixa Analític" : "Meritació (Devengo)"}
          </button>

          <button
            type="button"
            onClick={carregarDades}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Actualitzar
          </button>

          <button
            type="button"
            onClick={() => setModalFactura(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-semibold text-white hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            Emetre Factura Veri*factu
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          <span className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </span>
          <button onClick={() => setError(null)}>
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Navegació per Pestanyes */}
      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTabActiva(t.key)}
            className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition ${
              tabActiva === t.key
                ? "bg-primary text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* TAB 1: DASHBOARD ECONÒMIC & 5 GRÀFIQUES */}
      {tabActiva === "DASHBOARD" && dashboard && (
        <div className="space-y-6">
          {/* KPIs Principals */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-xs font-medium text-slate-500">Facturació Neta &amp; Marge Brut</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
                {Number(dashboard.facturacio_neta).toFixed(2)} €
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Marge Brut:{" "}
                <span className="font-semibold text-emerald-700">
                  {Number(dashboard.marge_brut_eur).toFixed(2)} € ({Number(dashboard.marge_brut_pct).toFixed(1)}%)
                </span>
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-xs font-medium text-slate-500">EBITDA Operatiu &amp; Break-Even</p>
              <p
                className={`mt-1 text-2xl font-bold tabular-nums ${
                  Number(dashboard.ebitda_operatiu_eur) >= 0 ? "text-emerald-700" : "text-rose-700"
                }`}
              >
                {Number(dashboard.ebitda_operatiu_eur).toFixed(2)} €
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Break-Even: {Number(dashboard.break_even_facturacio_necessaria).toFixed(2)} €{" "}
                {dashboard.break_even_assolit ? "✅ Assolit" : "⏳ Pendent"}
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-xs font-medium text-slate-500">Burn Rate &amp; Guardacaixa IVA 303</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
                {Number(dashboard.burn_rate_mes_seguent).toFixed(2)} €
              </p>
              <p className="mt-1 text-xs text-amber-700 font-medium">
                Reserva AEAT IVA: {Number(dashboard.guardacaixa_fiscal_iva_303).toFixed(2)} €
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-xs font-medium text-slate-500">MRR Actiu &amp; DSO Cobrament</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-primary">
                {Number(dashboard.mrr_mensual_actiu).toFixed(2)} €/mes
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Cobertura Fixes: {Number(dashboard.cobertura_estructura_mrr_pct).toFixed(1)}% · DSO:{" "}
                {Number(dashboard.dso_dies_mitjana_cobrament).toFixed(0)}d
              </p>
            </div>
          </div>

          {/* Alertes Estratègiques (Pareto + Erosió Marge + Capital Immobilitzat) */}
          {(dashboard.alerta_concentracio_pareto_25pct ||
            dashboard.alertes_erosio_marge.length > 0 ||
            Number(dashboard.capital_immobilitzat_90d_eur) > 0) && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {dashboard.alerta_concentracio_pareto_25pct && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
                  <strong>Risc Concentració Pareto (&gt;25%):</strong> Un sol client supera el 25% de la facturació.
                </div>
              )}
              {dashboard.alertes_erosio_marge.length > 0 && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-900">
                  <strong>Erosió de Marge ({dashboard.alertes_erosio_marge.length} articles):</strong> Puja de cost de proveïdor detectada.
                </div>
              )}
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700">
                <strong>Capital Immobilitzat (&gt;90d):</strong>{" "}
                {Number(dashboard.capital_immobilitzat_90d_eur).toFixed(2)} € en estoc sense rotació.
              </div>
            </div>
          )}

          {/* Les 5 Gràfiques Interactives */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Evolucio12MChart data={dashboard.evolucio_12m || []} />
            <WaterfallChart waterfall={dashboard.waterfall_mensual || {}} />
            <TresoreriaProjeccioChart
              cashFlowReal={Number(dashboard.cash_flow_operatiu_real || 0)}
              p30={Number(dashboard.projeccio_tresoreria_30d || 0)}
              p60={Number(dashboard.projeccio_tresoreria_60d || 0)}
              p90={Number(dashboard.projeccio_tresoreria_90d || 0)}
              guardacaixaIva={Number(dashboard.guardacaixa_fiscal_iva_303 || 0)}
            />
            <AgingBarChart
              aging={dashboard.aging_impagats || {}}
              retencionsExcloses={Number(dashboard.total_retencions_garantia_4308_excloses_aging || 0)}
            />
          </div>

          <MargesVerticalChart verticals={dashboard.marges_per_vertical || []} />
        </div>
      )}

      {/* TAB 2: VERIFACTU, ART. 80 LIVA I RETENCIONS 5% */}
      {tabActiva === "VERIFACTU" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
            <div className="border-b border-slate-100 px-5 py-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-900">
                Factures Emeses (Encadenament SHA-256 Veri*factu)
              </h2>
              <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-medium">
                <ShieldCheck className="h-4 w-4" /> SIF Inalterable
              </span>
            </div>
            {factures.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                Estat Dia 0 real: Encara no s&apos;ha emès cap factura en aquest tenant.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="px-4 py-3">Número</th>
                      <th className="px-4 py-3">Base</th>
                      <th className="px-4 py-3">IVA</th>
                      <th className="px-4 py-3">Líquid Exigible</th>
                      <th className="px-4 py-3">Estat</th>
                      <th className="px-4 py-3">Hash SHA-256</th>
                      <th className="px-4 py-3 text-right">Descàrregues</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {factures.map((f) => (
                      <tr key={f.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-semibold text-slate-900">
                          {f.serie}-{f.numero_factura}
                        </td>
                        <td className="px-4 py-3 tabular-nums">{Number(f.base_imposable).toFixed(2)} €</td>
                        <td className="px-4 py-3 tabular-nums">{Number(f.quota_iva).toFixed(2)} €</td>
                        <td className="px-4 py-3 font-semibold tabular-nums">
                          {Number(f.liquid_exigible).toFixed(2)} €
                        </td>
                        <td className="px-4 py-3">
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium">
                            {f.estat_cobrament}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-[11px] text-slate-500">
                          {f.hash_sha256.slice(0, 14)}...
                        </td>
                        <td className="px-4 py-3 text-right space-x-2">
                          <a
                            href={`/api/v1/gestio/comptabilitat/factures/${f.id}/pdf`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-primary hover:underline"
                          >
                            <Download className="h-3.5 w-3.5" /> PDF
                          </a>
                          <a
                            href={`/api/v1/gestio/comptabilitat/factures/${f.id}/xml`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-slate-600 hover:underline"
                          >
                            <FileText className="h-3.5 w-3.5" /> XML
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Retencions Garantia 5% i Art. 80 */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">
                Retencions per Garantia d&apos;Obra 5% (Compte 4308)
              </h3>
              {retencions.length === 0 ? (
                <p className="text-xs text-slate-500">Sense retencions de garantia registrades.</p>
              ) : (
                <div className="space-y-2 text-xs">
                  {retencions.map((r) => (
                    <div
                      key={r.id}
                      className="flex items-center justify-between rounded-lg border border-slate-100 p-3"
                    >
                      <div>
                        <p className="font-semibold text-slate-900">
                          {Number(r.import_retingut).toFixed(2)} € ({r.estat})
                        </p>
                        <p className="text-slate-500">
                          Venciment: {r.data_venciment_garantia} ({r.dies_fins_venciment}d)
                        </p>
                      </div>
                      {r.alerta_venciment_proper && r.estat !== "RECLAMADA" && (
                        <button
                          onClick={() => handleReclamarGarantia(r.id)}
                          className="rounded-lg bg-primary px-2.5 py-1.5 font-semibold text-white"
                        >
                          Reclamar Alliberament
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">
                Recuperació IVA Incobrables (Art. 80 LIVA · 180-270d)
              </h3>
              {art80.length === 0 ? (
                <p className="text-xs text-slate-500">
                  Cap factura en finestra legal d&apos;incobrables Art. 80 LIVA.
                </p>
              ) : (
                <div className="space-y-2 text-xs">
                  {art80.map((a) => (
                    <div
                      key={a.factura_id}
                      className="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 p-3"
                    >
                      <div>
                        <p className="font-semibold text-slate-900">
                          {a.serie}-{a.numero_factura} · IVA recuperable: {Number(a.quota_iva).toFixed(2)} €
                        </p>
                        <p className="text-amber-800">
                          {a.dies_impagada} dies impagada · Límit: {a.data_limit_art80} ({a.estat_art80})
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: WIP OBRA EN CURS NO FACTURADA */}
      {tabActiva === "WIP_CONTROL" && wip && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Valor WIP Pendent de Facturar (PVP)</p>
              <p className="text-xl font-bold text-slate-900">{Number(wip.total_wip_valorat_pvp).toFixed(2)} €</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Cost Avançat per l&apos;Empresa</p>
              <p className="text-xl font-bold text-slate-900">{Number(wip.total_cost_wip_avancat).toFixed(2)} €</p>
            </div>
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
              <p className="text-xs text-rose-700">OTs Envellides Crítiques (&gt;7 dies)</p>
              <p className="text-xl font-bold text-rose-800">{wip.nombre_ots_envellides_critiques}</p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            {wip.items.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-6">
                Cap ordre de treball pendent de facturar (WIP = 0).
              </p>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2">Codi OT</th>
                    <th className="px-3 py-2">Dies en WIP</th>
                    <th className="px-3 py-2">Valor PVP</th>
                    <th className="px-3 py-2">Cost Avançat</th>
                    <th className="px-3 py-2">Alerta</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {wip.items.map((item) => (
                    <tr key={item.ordre_treball_id}>
                      <td className="px-3 py-2 font-semibold">{item.codi_ot}</td>
                      <td className="px-3 py-2">{item.dies_en_wip} dies</td>
                      <td className="px-3 py-2 tabular-nums">{Number(item.valor_wip_pvp).toFixed(2)} €</td>
                      <td className="px-3 py-2 tabular-nums">{Number(item.cost_wip_avancat).toFixed(2)} €</td>
                      <td className="px-3 py-2">
                        {item.es_wip_envellit_alerta ? (
                          <span className="rounded-full bg-rose-100 px-2 py-0.5 text-rose-800 font-semibold">
                            WIP Envellit &gt;7d
                          </span>
                        ) : (
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-800">
                            Normal
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: OPERARIS COST HORA EFECTIU & SINISTRALITAT MRR */}
      {tabActiva === "OPERARIS_MRR" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">
              Cost Hora Efectiu Dinàmic d&apos;Operaris
            </h3>
            {operarisCost.length === 0 ? (
              <p className="text-xs text-slate-500">Sense operaris actius registrats.</p>
            ) : (
              <div className="space-y-2 text-xs">
                {operarisCost.map((op) => (
                  <div key={op.usuari_id} className="rounded-lg border border-slate-100 p-3 flex justify-between items-center">
                    <div>
                      <p className="font-semibold text-slate-900">{op.nom_complet}</p>
                      <p className="text-slate-500">
                        Salari+SS: {op.salari_brut_i_ss_visible} · Eficiència: {Number(op.ratio_eficiencia_pct).toFixed(1)}%
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-slate-900">
                        {op.cost_hora_efectiu_mensual !== null
                          ? `${Number(op.cost_hora_efectiu_mensual).toFixed(2)} €/h`
                          : "100% Improductiu / Baixa"}
                      </p>
                      <p className="text-[11px] text-slate-500">
                        Ref: {Number(op.cost_hora_referencia).toFixed(2)} €/h
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">
              Auditoria de Sinistralitat de Contractes MRR
            </h3>
            {contractesMrr.length === 0 ? (
              <p className="text-xs text-slate-500">Cap contracte MRR actiu.</p>
            ) : (
              <div className="space-y-2 text-xs">
                {contractesMrr.map((c) => (
                  <div key={c.contracte_id} className="rounded-lg border border-slate-100 p-3 flex justify-between items-center">
                    <div>
                      <p className="font-semibold text-slate-900">{c.codi_contracte}</p>
                      <p className="text-slate-500">
                        Quota: {Number(c.quota_mensual_mrr).toFixed(2)} € · Cost OTs: {Number(c.cost_real_ots_periode).toFixed(2)} €
                      </p>
                    </div>
                    <span
                      className={`rounded-full px-2.5 py-1 font-semibold ${
                        c.semafor === "RENDIBLE"
                          ? "bg-emerald-100 text-emerald-800"
                          : c.semafor === "ALERTA_EROSIO"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-rose-100 text-rose-800"
                      }`}
                    >
                      {Number(c.sinistralitat_pct).toFixed(1)}% · {c.semafor}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 5: TIQUETS DE DESPESA DE CAMP */}
      {tabActiva === "TIQUETS" && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-900 mb-4">
            Bústia d&apos;Auditoria de Tiquets (Control &gt;100 € i NIF Art. 97 LIVA)
          </h2>
          {tiquets.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-6">
              Cap tiquet de despesa pendent ni registrat al sistema.
            </p>
          ) : (
            <div className="space-y-2 text-xs">
              {tiquets.map((t) => (
                <div
                  key={t.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-100 p-3"
                >
                  <div>
                    <p className="font-semibold text-slate-900">
                      {t.categoria} · {Number(t.import_total).toFixed(2)} € (IVA: {Number(t.quota_iva).toFixed(2)} €)
                    </p>
                    <p className="text-slate-500">
                      {t.data_tiquet} · NIF: {t.nif_emissor || "SENSE NIF (No deduïble)"} · {t.estat_aprovacio}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {t.requereix_aprovacio_boss && (
                      <span className="rounded bg-amber-100 px-2 py-0.5 font-semibold text-amber-900">
                        &gt;100€ Només BOSS
                      </span>
                    )}
                    {t.estat_aprovacio === "PENDENT_AUDITORIA" && (
                      <>
                        <button
                          onClick={() => handleAuditarTiquet(t.id, "APROVAT")}
                          className="rounded-lg bg-emerald-600 px-2.5 py-1 text-white font-semibold"
                        >
                          Aprovar
                        </button>
                        <button
                          onClick={() => handleAuditarTiquet(t.id, "REBUTJAT")}
                          className="rounded-lg bg-rose-600 px-2.5 py-1 text-white font-semibold"
                        >
                          Rebutjar
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 6: CONCILIACIÓ BANCÀRIA CSB 43 */}
      {tabActiva === "NORMA43" && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Conciliació Bancària Idempotent (AEB Norma 43 / CSB 43)
              </h2>
              <p className="text-xs text-slate-500">
                Enganxa el contingut d&apos;un fitxer .c43 / .n43 o línies YYYY-MM-DD|Concepte|Import|Saldo
              </p>
            </div>
            <Building2 className="h-5 w-5 text-slate-400" />
          </div>

          <textarea
            rows={5}
            value={textC43}
            onChange={(e) => setTextC43(e.target.value)}
            placeholder="2026-11-12|Transferència Client ABC|1210.00|15420.50"
            className="w-full rounded-lg border border-slate-200 p-3 font-mono text-xs"
          />

          <div className="flex gap-2">
            <button
              onClick={() => handleConciliarNorma43(false)}
              className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700"
            >
              Previsualitzar Creuament
            </button>
            <button
              onClick={() => handleConciliarNorma43(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-semibold text-white"
            >
              <FileCheck2 className="h-4 w-4" />
              Confirmar Conciliació HITL
            </button>
          </div>

          {movimentsC43.length > 0 && (
            <div className="space-y-1.5 text-xs pt-2">
              {movimentsC43.map((m) => (
                <div
                  key={m.huella_sha256}
                  className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"
                >
                  <span>
                    {m.data_operacio} · {m.concepte} ({Number(m.import_moviment).toFixed(2)} €)
                  </span>
                  <span className="font-semibold">
                    {m.duplicat_rebutjat
                      ? "Duplicat Rebutjat (Idempotent)"
                      : m.factura_suggerida_id
                      ? "Conciliat amb Factura"
                      : "Sense coincidència"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* MODAL EMISSIÓ FACTURA VERI*FACTU */}
      {modalFactura && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">
                Nova Factura Veri*factu (Sèrie F)
              </h3>
              <button onClick={() => setModalFactura(false)}>
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </div>
            <form onSubmit={handleEmetreFactura} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  UUID Client
                </label>
                <input
                  required
                  value={clientIdInput}
                  onChange={(e) => setClientIdInput(e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  Concepte de la línia
                </label>
                <input
                  required
                  value={concepteInput}
                  onChange={(e) => setConcepteInput(e.target.value)}
                  placeholder="Servei tècnic / Instal·lació"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Import Base (€)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={preuInput}
                    onChange={(e) => setPreuInput(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Retenció Garantia 4308 (%)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={retGarantiaPct}
                    onChange={(e) => setRetGarantiaPct(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2"
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  checked={esIsp}
                  onChange={(e) => setEsIsp(e.target.checked)}
                />
                <span>Inversió del Subjecte Passiu (ISP 0% IVA Art. 84)</span>
              </label>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setModalFactura(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-primary px-4 py-2 font-semibold text-white"
                >
                  Emetre i Encadenar SHA-256
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
