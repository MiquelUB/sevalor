"use client";

import React, { useState, useEffect } from "react";
import {
  Server,
  Database,
  ShieldCheck,
  Cpu,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Rocket,
  RotateCcw,
  Play,
  Lock,
  Globe,
  Users,
  Copy,
  ExternalLink,
  Sparkles,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

export default function SuperadminTenantOnboardingPage() {
  const [pasActual, setPasActual] = useState<number>(1);
  const [dryRunRunning, setDryRunRunning] = useState<boolean>(false);
  const [dryRunSuccess, setDryRunSuccess] = useState<boolean | null>(null);

  // Pas 1: Dades Fiscals & Marca Camaleó
  const [raoSocial, setRaoSocial] = useState<string>("");
  const [nif, setNif] = useState<string>("");
  const [vertical, setVertical] = useState<string>("SEVALOR");
  const [magatzemFamilies, setMagatzemFamilies] = useState<string>("");
  const [agentPrompt, setAgentPrompt] = useState<string>("");
  const [responsable, setResponsable] = useState<string>("");
  const [emailGerent, setEmailGerent] = useState<string>("");
  const [telefon, setTelefon] = useState<string>("");
  const [primariHsl, setPrimariHsl] = useState<string>("142 71% 25%");
  const [secundariHsl, setSecundariHsl] = useState<string>("38 92% 50%");
  const [accentHsl, setAccentHsl] = useState<string>("160 84% 39%");

  // Pas 2: Domini Propi & Verificació Real DNS
  const [tipusDomini, setTipusDomini] = useState<"PROPI" | "SEVALOR">("PROPI");
  const [dominiEmpresa, setDominiEmpresa] = useState<string>("");
  const [subdominiPrefix, setSubdominiPrefix] = useState<string>("sevalor");
  const [subdomini, setSubdomini] = useState<string>("");
  const [dnsResult, setDnsResult] = useState<any>(null);
  const [checkingDns, setCheckingDns] = useState<boolean>(false);

  // Pas 4: Quotes d'Operaris (Llicència Variable) & Buffer Diari
  const [tierPla, setTierPla] = useState<"STARTER" | "PRO" | "ENTERPRISE">("PRO");
  const [quotaOperaris, setQuotaOperaris] = useState<number>(15);
  const [quotaBufferMb, setQuotaBufferMb] = useState<number>(500);
  const [featureFlags, setFeatureFlags] = useState({
    copilot_ia: true,
    flota_avancada: true,
    planols_tecnics: true,
    telegram_bot: true,
  });

  // Telemetria real del servidor (Zero Mock)
  const [liveKpis, setLiveKpis] = useState<any>(null);

  // Estat de provisionament final
  const [provisioning, setProvisioning] = useState<boolean>(false);
  const [provisionedSuccess, setProvisionedSuccess] = useState<boolean>(false);
  const [invitationUrl, setInvitationUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<any>("/superadmin/telemetria/kpis")
      .then((res) => setLiveKpis(res))
      .catch(() => setLiveKpis(null));
  }, []);

  const fqdnResultant =
    tipusDomini === "PROPI"
      ? dominiEmpresa.trim()
        ? `${(subdominiPrefix.trim() || "sevalor").toLowerCase()}.${dominiEmpresa.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/.*$/, "")}`
        : ""
      : `${(subdomini.trim() || "tenant").toLowerCase().replace(/[^a-z0-9-]/g, "")}.sevalor.app`;

  const slugCalculat =
    subdomini.trim().toLowerCase().replace(/[^a-z0-9-]/g, "") ||
    (dominiEmpresa.trim()
      ? dominiEmpresa.trim().split(".")[0].toLowerCase().replace(/[^a-z0-9-]/g, "")
      : raoSocial.trim().split(" ")[0].toLowerCase().replace(/[^a-z0-9-]/g, "")) ||
    "empresa";

  const handleCheckDnsLive = async () => {
    if (!fqdnResultant) {
      setErrorMessage("Introdueix primer el domini de l'empresa per verificar la redirecció DNS.");
      return;
    }
    setCheckingDns(true);
    setDnsResult(null);
    setErrorMessage(null);
    try {
      const res = await apiFetch<any>("/superadmin/tenants/verificar-dns", {
        method: "POST",
        body: JSON.stringify({ fqdn: fqdnResultant }),
      });
      setDnsResult(res);
    } catch (err: any) {
      setDnsResult({
        resolt: false,
        fqdn: fqdnResultant,
        detall: err.message || "Error comprovant el registre DNS.",
      });
    } finally {
      setCheckingDns(false);
    }
  };

  const handleExecuteDryRun = async () => {
    setDryRunRunning(true);
    setDryRunSuccess(null);
    setErrorMessage(null);

    if (!raoSocial.trim() || !nif.trim() || !emailGerent.trim()) {
      setDryRunRunning(false);
      setDryRunSuccess(false);
      setErrorMessage("Cal indicar Raó Social, NIF i Email del gerent abans de verificar.");
      return;
    }

    if (tipusDomini === "PROPI") {
      if (!dominiEmpresa.trim() || !dominiEmpresa.includes(".")) {
        setDryRunRunning(false);
        setDryRunSuccess(false);
        setErrorMessage("Cal indicar un domini propi d'empresa vàlid (exemple: soler.cat).");
        return;
      }
    } else {
      if (!subdomini.trim()) {
        setDryRunRunning(false);
        setDryRunSuccess(false);
        setErrorMessage("Cal indicar un subdomini vàlid per a sevalor.app.");
        return;
      }
    }

    await handleCheckDnsLive();
    setDryRunRunning(false);
    setDryRunSuccess(true);
  };

  const handleResetForm = () => {
    setRaoSocial("");
    setNif("");
    setResponsable("");
    setEmailGerent("");
    setDominiEmpresa("");
    setSubdomini("");
    setDnsResult(null);
    setDryRunSuccess(null);
    setErrorMessage(null);
    setPasActual(1);
  };

  const handleProvisionTenant = async () => {
    setProvisioning(true);
    setErrorMessage(null);
    try {
      const nomParts = responsable.trim().split(" ");
      const nom = nomParts[0] || "Gerent";
      const cognoms = nomParts.slice(1).join(" ") || "General";

      const subdominiFinal = slugCalculat;
      const dominiCustomFinal = tipusDomini === "PROPI" && fqdnResultant ? fqdnResultant : undefined;

      const data = await apiFetch<any>("/superadmin/tenants/onboarding", {
        method: "POST",
        body: JSON.stringify({
          rao_social: raoSocial.trim(),
          nif: nif.trim().toUpperCase(),
          subdomini: subdominiFinal,
          domini_custom: dominiCustomFinal,
          vertical: vertical.trim(),
          magatzem_families_default: magatzemFamilies.trim() || undefined,
          agent_prompt_system: agentPrompt.trim() || undefined,
          pla_subscripcio: tierPla,
          quota_operaris: Number(quotaOperaris),
          quota_buffer_mb: Number(quotaBufferMb),
          quota_disc_gb: tierPla === "ENTERPRISE" ? 100 : tierPla === "PRO" ? 50 : 10,
          primari_hsl: primariHsl.trim(),
          secundari_hsl: secundariHsl.trim(),
          accent_hsl: accentHsl.trim(),
          boss_nif: nif.trim().toUpperCase(),
          boss_nom: nom,
          boss_cognoms: cognoms,
          boss_email: emailGerent.trim().toLowerCase(),
          boss_telefon: telefon.trim() || "+34600000000",
          feature_flags: featureFlags,
        }),
      });

      setProvisionedSuccess(true);
      const hostAcceso = dominiCustomFinal || `${subdominiFinal}.sevalor.app`;
      setInvitationUrl(data?.tenant?.enllac_activacio_2fa || `https://${hostAcceso}/activacio`);
    } catch (err: any) {
      setErrorMessage(err.message || "Error durant el provisionament del tenant.");
    } finally {
      setProvisioning(false);
    }
  };

  return (
    <div className="flex-1 p-6 md:p-8 max-w-7xl w-full">
      {/* Banner de Panell Superior */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 text-white rounded-2xl p-6 shadow-lg border border-slate-700/60 mb-6">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-black tracking-tight text-white">
                Alta de Nou Tenant • Provisionament d'Empresa i Redirecció DNS
              </h1>
              <span className="text-xs font-mono font-bold uppercase tracking-wider px-2.5 py-1 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                RLS Multi-Tenant + DNS CNAME
              </span>
            </div>
            <p className="text-xs text-slate-300 mt-1 max-w-3xl">
              Configuració d'entorn aïllat PostgreSQL RLS, verificació real de redirecció DNS del subdomini de l'empresa cap al nostre servidor, quota d'operaris per llicència i Buffer Diari a Hetzner.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={handleResetForm}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono font-semibold flex items-center gap-1.5 border border-slate-700 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
              <span>Netejar Formulari</span>
            </button>
            <button
              type="button"
              onClick={handleExecuteDryRun}
              disabled={dryRunRunning}
              className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow transition-colors"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{dryRunRunning ? "Verificant..." : "Verificar Pre-Alta & DNS"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Feedback de Dry-Run */}
      {dryRunSuccess && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200 flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            <span>
              <strong>Pre-validació completada:</strong> Domini <em>{fqdnResultant}</em>, NIF <em>{nif}</em> i quota inicial de <em>{quotaOperaris} operaris</em> preparats per a l'alta.
            </span>
          </div>
          <button onClick={() => setDryRunSuccess(null)} className="underline text-emerald-700 dark:text-emerald-300">
            Tancar
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* 8 Columnes: Assistent d'Onboarding */}
        <div className="lg:col-span-8 space-y-6">
          {/* PAS 1: Empresa, Dades Fiscals, Vertical i Colors Camaleó */}
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-6 border border-slate-200 dark:border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 flex items-center justify-center font-bold text-xs">
                  1
                </span>
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                  1. Empresa, Dades Fiscals, Vertical i Marca Camaleó
                </h2>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">Raó Social Corporativa</label>
                <input
                  type="text"
                  value={raoSocial}
                  onChange={(e) => setRaoSocial(e.target.value)}
                  placeholder="ex. Instal·lacions Soler S.L."
                  className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-medium"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">NIF / CIF Corporatiu</label>
                <input
                  type="text"
                  value={nif}
                  onChange={(e) => setNif(e.target.value)}
                  placeholder="ex. B12345678"
                  className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-mono font-bold"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">
                  Vertical Tècnica Especialitzada
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[
                    { id: "SEVALOR", label: "Sevalor", desc: "Agronòmic & Reg", hsl: ["142 71% 25%", "38 92% 50%", "160 84% 39%"] },
                    { id: "ELECTRICPRO", label: "ElectricPro", desc: "Baixa Tensió REBT", hsl: ["210 100% 15%", "38 92% 50%", "190 90% 50%"] },
                    { id: "HYDROPRO", label: "HydroPro", desc: "Aigua i Fontaneria", hsl: ["199 89% 28%", "170 80% 40%", "45 93% 47%"] },
                    { id: "BUILDINGPRO", label: "BuildingPro", desc: "Climatització i Obres", hsl: ["25 85% 35%", "38 92% 50%", "15 80% 45%"] },
                  ].map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        setVertical(item.id);
                        setPrimariHsl(item.hsl[0]);
                        setSecundariHsl(item.hsl[1]);
                        setAccentHsl(item.hsl[2]);
                      }}
                      className={`p-2.5 rounded-lg border text-left transition-all ${
                        vertical === item.id
                          ? "border-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 font-bold shadow-sm"
                          : "border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800"
                      }`}
                    >
                      <span className="block text-xs font-bold">{item.label}</span>
                      <span className="block text-[10px] text-slate-500">{item.desc}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">Responsable Gerència (Boss)</label>
                <input
                  type="text"
                  value={responsable}
                  onChange={(e) => setResponsable(e.target.value)}
                  placeholder="Nom i cognoms del gerent"
                  className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">Correu d'Activació Inicial (2FA)</label>
                <input
                  type="email"
                  value={emailGerent}
                  onChange={(e) => setEmailGerent(e.target.value)}
                  placeholder="gerencia@empresa.cat"
                  className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-mono"
                />
              </div>

              {/* Tokens HSL Camaleó */}
              <div className="sm:col-span-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-2 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Colors Corporatius HSL (Chameleon UI Engine)</span>
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono">
                  <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800 p-2 rounded-lg border border-slate-200 dark:border-slate-700">
                    <span className="w-4 h-4 rounded-full shrink-0 border" style={{ backgroundColor: `hsl(${primariHsl})` }} />
                    <input
                      type="text"
                      value={primariHsl}
                      onChange={(e) => setPrimariHsl(e.target.value)}
                      className="w-full bg-transparent text-xs font-bold focus:outline-none"
                      title="Primari HSL"
                    />
                  </div>
                  <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800 p-2 rounded-lg border border-slate-200 dark:border-slate-700">
                    <span className="w-4 h-4 rounded-full shrink-0 border" style={{ backgroundColor: `hsl(${secundariHsl})` }} />
                    <input
                      type="text"
                      value={secundariHsl}
                      onChange={(e) => setSecundariHsl(e.target.value)}
                      className="w-full bg-transparent text-xs font-bold focus:outline-none"
                      title="Secundari HSL"
                    />
                  </div>
                  <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800 p-2 rounded-lg border border-slate-200 dark:border-slate-700">
                    <span className="w-4 h-4 rounded-full shrink-0 border" style={{ backgroundColor: `hsl(${accentHsl})` }} />
                    <input
                      type="text"
                      value={accentHsl}
                      onChange={(e) => setAccentHsl(e.target.value)}
                      className="w-full bg-transparent text-xs font-bold focus:outline-none"
                      title="Accent HSL"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* PAS 2: Domini Propi & Redirecció DNS cap al nostre servidor */}
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-6 border border-slate-200 dark:border-slate-800 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 flex items-center justify-center font-bold text-xs">
                  2
                </span>
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                    2. Redirecció DNS del Subdomini de l'Empresa al Nostre Servidor
                  </h2>
                  <span className="text-[10px] font-mono text-slate-500">
                    Comprovació en viu del registre CNAME / A abans d'activar el tenant
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={handleCheckDnsLive}
                disabled={checkingDns}
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-bold shadow-sm transition-colors"
              >
                {checkingDns ? "Verificant DNS..." : "Comprovar Redirecció DNS en Viu"}
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <button
                type="button"
                onClick={() => setTipusDomini("PROPI")}
                className={`p-3 rounded-xl border text-left transition-all ${
                  tipusDomini === "PROPI"
                    ? "border-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-900 dark:text-emerald-200 font-bold"
                    : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-400"
                }`}
              >
                <span className="font-bold flex items-center gap-1.5 mb-1">
                  <Globe className="w-4 h-4 text-emerald-600" />
                  <span>Subdomini sobre el Domini de l'Empresa (Recomanat)</span>
                </span>
                <p className="text-[11px] text-slate-500 font-normal">
                  L'empresa redirecciona el seu subdomini (ex: <em>sevalor.soler.cat</em>) cap a <code>edge.sevalor.app</code>.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setTipusDomini("SEVALOR")}
                className={`p-3 rounded-xl border text-left transition-all ${
                  tipusDomini === "SEVALOR"
                    ? "border-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-900 dark:text-emerald-200 font-bold"
                    : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-400"
                }`}
              >
                <span className="font-bold flex items-center gap-1.5 mb-1">
                  <Server className="w-4 h-4 text-slate-400" />
                  <span>Subdomini Directe sota Sevalor.app</span>
                </span>
                <p className="text-[11px] text-slate-500 font-normal">
                  Si l'empresa no té domini propi, s'utilitza <em>empresa.sevalor.app</em>.
                </p>
              </button>
            </div>

            {tipusDomini === "PROPI" ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                  <div className="sm:col-span-2">
                    <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                      Domini Corporatiu de l'Empresa
                    </label>
                    <input
                      type="text"
                      placeholder="ex. soler.cat"
                      value={dominiEmpresa}
                      onChange={(e) =>
                        setDominiEmpresa(
                          e.target.value
                            .toLowerCase()
                            .replace(/^https?:\/\//, "")
                            .replace(/\/.*$/, "")
                            .replace(/[^a-z0-9.-]/g, "")
                        )
                      }
                      className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 font-mono font-bold"
                    />
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                      Prefix del Subdomini
                    </label>
                    <input
                      type="text"
                      placeholder="sevalor"
                      value={subdominiPrefix}
                      onChange={(e) => setSubdominiPrefix(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                      className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 font-mono font-bold"
                    />
                  </div>
                </div>

                {/* Instruccions de Redirecció DNS CNAME */}
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs font-mono space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800 dark:text-slate-200 uppercase text-[11px] flex items-center gap-1.5">
                      <ExternalLink className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Pas Obligatori al Proveïdor DNS de l'Empresa ({dominiEmpresa || "empresa.cat"})</span>
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600 dark:text-slate-400 font-sans">
                    Per donar d'alta l'empresa amb el seu subdomini, cal afegir aquest registre al seu panell DNS perquè apunti al nostre servidor:
                  </p>
                  <div className="grid grid-cols-3 gap-2 pt-1">
                    <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                      <span className="text-slate-400 text-[10px] block">Tipus</span>
                      <span className="font-bold text-emerald-600">CNAME</span>
                    </div>
                    <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                      <span className="text-slate-400 text-[10px] block">Host / Subdomini</span>
                      <span className="font-bold text-slate-800 dark:text-slate-200">{subdominiPrefix || "sevalor"}</span>
                    </div>
                    <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                      <span className="text-slate-400 text-[10px] block">Destí (Nostre Servidor)</span>
                      <span className="font-bold text-slate-800 dark:text-slate-200">edge.sevalor.app</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-xs">
                <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">Subdomini Sol·licitat</label>
                <div className="flex items-center rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
                  <input
                    type="text"
                    value={subdomini}
                    onChange={(e) => setSubdomini(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                    className="flex-1 p-2 bg-transparent font-mono font-bold focus:outline-none"
                  />
                  <span className="px-3 text-slate-400 font-mono bg-slate-100 dark:bg-slate-800/80 border-l py-2">
                    .sevalor.app
                  </span>
                </div>
              </div>
            )}

            {/* Resultat Real de la Sonda DNS (Zero Mock) */}
            {dnsResult && (
              <div
                className={`p-3.5 rounded-xl border font-mono text-xs space-y-1 ${
                  dnsResult.resolt
                    ? "bg-emerald-50 dark:bg-emerald-950/60 border-emerald-300 text-emerald-900 dark:text-emerald-200"
                    : "bg-amber-50 dark:bg-amber-950/60 border-amber-300 text-amber-900 dark:text-amber-200"
                }`}
              >
                <div className="font-bold">
                  Sonda DNS Real per a {dnsResult.fqdn}: {dnsResult.resolt ? "RESOLT CORRECTAMENT" : "ENCARA NO RESOLT"}
                </div>
                <div>{dnsResult.detall}</div>
                {Array.isArray(dnsResult.ips_detectades) && dnsResult.ips_detectades.length > 0 && (
                  <div className="text-[10px]">IPs detectades: {dnsResult.ips_detectades.join(", ")}</div>
                )}
              </div>
            )}
          </div>

          {/* PAS 3: Aïllament RLS i Arquitectura Buffer Diari vs Disc Local de l'Empresa */}
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-6 border border-slate-200 dark:border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 flex items-center justify-center font-bold text-xs">
                  3
                </span>
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                    3. Aïllament PostgreSQL RLS & Arquitectura de Dades Lleugera (Buffer Diari)
                  </h2>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
              <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                <span className="text-slate-400 block text-[10px] uppercase">Servidor Hetzner (Nostre)</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-bold block mt-1">NOMÉS FEINES D'AVUI (BUFFER DIARI)</span>
                <span className="text-slate-500 text-[10px]">
                  Emmagatzematge ràpid i lleuger sota /data/&lt;id&gt; i /docs/&lt;id&gt;
                </span>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                <span className="text-slate-400 block text-[10px] uppercase">Disc Dur de l'Empresa (Client)</span>
                <span className="text-blue-600 dark:text-blue-400 font-bold block mt-1">ARXIU MESTRE HISTÒRIC & PLÀNOLS EXTRES</span>
                <span className="text-slate-500 text-[10px]">
                  Els plànols fora de l'OT del dia es consulten a l'ordinador del client
                </span>
              </div>
            </div>
          </div>

          {/* PAS 4: Número d'Operaris per Llicència, Buffer Diari i Feature Flags */}
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-6 border border-slate-200 dark:border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 flex items-center justify-center font-bold text-xs">
                  4
                </span>
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                    4. Número d'Operaris Assignats per Llicència & Feature Flags
                  </h2>
                  <span className="text-[10px] font-mono text-slate-500">
                    El nombre d'operaris és totalment editable i pot variar amb el temps per a la facturació Veri*factu
                  </span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Número d'Operaris per Llicència
                </label>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={quotaOperaris}
                  onChange={(e) => setQuotaOperaris(Math.max(1, Number(e.target.value)))}
                  className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 font-mono font-bold text-sm"
                />
                <span className="text-[10px] text-slate-400 block mt-0.5">
                  Editable en qualsevol moment des del CRM
                </span>
              </div>

              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Pla de Referència
                </label>
                <select
                  value={tierPla}
                  onChange={(e) => {
                    const v = e.target.value as "STARTER" | "PRO" | "ENTERPRISE";
                    setTierPla(v);
                    setQuotaOperaris(v === "ENTERPRISE" ? 50 : v === "PRO" ? 15 : 5);
                  }}
                  className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 font-mono font-bold"
                >
                  <option value="STARTER">STARTER (5 operaris base)</option>
                  <option value="PRO">PRO (15 operaris base)</option>
                  <option value="ENTERPRISE">ENTERPRISE (50 operaris base)</option>
                </select>
              </div>

              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Buffer Diari al Servidor (MB)
                </label>
                <input
                  type="number"
                  min={100}
                  max={5000}
                  value={quotaBufferMb}
                  onChange={(e) => setQuotaBufferMb(Math.max(100, Number(e.target.value)))}
                  className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 font-mono font-bold"
                />
                <span className="text-[10px] text-slate-400 block mt-0.5">
                  Per a les ordres de treball d'avui
                </span>
              </div>
            </div>

            <div className="pt-2">
              <span className="block text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-2">
                Mòduls Habilitats (Feature Flags)
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <label className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center justify-between cursor-pointer">
                  <div>
                    <span className="font-bold block text-slate-800 dark:text-slate-200">Copilot IA &amp; Whisper</span>
                    <span className="text-[10px] text-slate-500">Transcripció i RAG sectorial</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={featureFlags.copilot_ia}
                    onChange={(e) => setFeatureFlags({ ...featureFlags, copilot_ia: e.target.checked })}
                    className="w-4 h-4 accent-emerald-600 rounded"
                  />
                </label>

                <label className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center justify-between cursor-pointer">
                  <div>
                    <span className="font-bold block text-slate-800 dark:text-slate-200">Flota Avançada &amp; ITV</span>
                    <span className="text-[10px] text-slate-500">Control de vehicles i carburant</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={featureFlags.flota_avancada}
                    onChange={(e) => setFeatureFlags({ ...featureFlags, flota_avancada: e.target.checked })}
                    className="w-4 h-4 accent-emerald-600 rounded"
                  />
                </label>

                <label className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center justify-between cursor-pointer">
                  <div>
                    <span className="font-bold block text-slate-800 dark:text-slate-200">Plànols Cartogràfics As-Built</span>
                    <span className="text-[10px] text-slate-500">Capes no destructives + Arxiu extern</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={featureFlags.planols_tecnics}
                    onChange={(e) => setFeatureFlags({ ...featureFlags, planols_tecnics: e.target.checked })}
                    className="w-4 h-4 accent-emerald-600 rounded"
                  />
                </label>

                <label className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center justify-between cursor-pointer">
                  <div>
                    <span className="font-bold block text-slate-800 dark:text-slate-200">Bot Telegram Clients</span>
                    <span className="text-[10px] text-slate-500">Canal directe d'incidències</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={featureFlags.telegram_bot}
                    onChange={(e) => setFeatureFlags({ ...featureFlags, telegram_bot: e.target.checked })}
                    className="w-4 h-4 accent-emerald-600 rounded"
                  />
                </label>
              </div>
            </div>
          </div>

          {/* Botons Finals d'Execució */}
          <div className="bg-white dark:bg-slate-900 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3">
            <button
              type="button"
              onClick={handleResetForm}
              className="text-rose-600 hover:text-rose-700 text-xs font-mono uppercase font-bold px-3 py-2 transition-colors"
            >
              Netejar i Reiniciar
            </button>

            <button
              type="button"
              disabled={provisioning}
              onClick={handleProvisionTenant}
              className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold flex items-center gap-2 shadow transition-all"
            >
              <Rocket className="w-4 h-4" />
              <span>{provisioning ? "Provisionant Empresa a PostgreSQL..." : "Provisionar & Activar Empresa"}</span>
            </button>
          </div>

          {errorMessage && (
            <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-200 text-xs font-semibold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {provisionedSuccess && invitationUrl && (
            <div className="p-6 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border-2 border-emerald-500 text-emerald-950 dark:text-emerald-100 shadow-xl space-y-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-6 h-6 text-emerald-600 dark:text-emerald-400 shrink-0" />
                <div>
                  <h3 className="text-sm font-bold">Empresa Provisionada amb Èxit!</h3>
                  <p className="text-xs text-slate-600 dark:text-slate-300">
                    S'ha registrat l'empresa amb llicència per a {quotaOperaris} operaris i s'ha generat l'enllaç d'activació 2FA per al Gerent.
                  </p>
                </div>
              </div>
              <div className="bg-white dark:bg-slate-900 p-3 rounded-lg border border-emerald-200 dark:border-emerald-800 flex items-center justify-between text-xs font-mono">
                <span className="truncate mr-2 text-slate-800 dark:text-slate-200">{invitationUrl}</span>
                <button
                  onClick={() => navigator.clipboard.writeText(invitationUrl)}
                  className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[11px] font-bold shrink-0 flex items-center gap-1"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copiar Enllaç</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 4 Columnes: Resum en Viu de l'Alta i Estat Real del Servidor (Zero Mock) */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-5 border border-slate-200 dark:border-slate-800 space-y-3 font-mono text-xs">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-500" />
              <span>Resum de Configuració del Nou Client</span>
            </h3>
            <div className="space-y-2 pt-1 text-[11px]">
              <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500">Empresa:</span>
                <span className="font-bold text-slate-900 dark:text-white">{raoSocial || "—"}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500">NIF:</span>
                <span className="font-bold text-slate-900 dark:text-white">{nif || "—"}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500">Domini FQDN:</span>
                <span className="font-bold text-emerald-600">{fqdnResultant || "—"}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500">Operaris Llicenciats:</span>
                <span className="font-bold text-purple-600">{quotaOperaris} operaris</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Buffer Diari Hetzner:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">{quotaBufferMb} MB</span>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-5 border border-slate-200 dark:border-slate-800 space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-500" />
                <span>Estat Real del Servidor</span>
              </h3>
              <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400">
                LIVE PROBE
              </span>
            </div>

            {!liveKpis ? (
              <p className="text-[11px] text-slate-400">Consultant mètriques reals del node...</p>
            ) : (
              <div className="space-y-2 text-[11px]">
                <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500">CPU Real:</span>
                  <span className="font-bold">
                    {liveKpis.cpu_ia_telemetry?.cpu_utilization_percent ?? "—"}%
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500">RAM Real:</span>
                  <span className="font-bold">
                    {liveKpis.cpu_ia_telemetry?.ram_utilization_mb
                      ? `${(liveKpis.cpu_ia_telemetry.ram_utilization_mb / 1024).toFixed(1)} GB`
                      : "—"}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500">Pool asyncpg:</span>
                  <span className="font-bold">
                    {liveKpis.concurrency?.db_pool_active ?? 0} / {liveKpis.concurrency?.db_pool_max ?? "—"}
                  </span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-500">Empreses Actives:</span>
                  <span className="font-bold text-emerald-600">
                    {Array.isArray(liveKpis.tenants) ? liveKpis.tenants.length : 0}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
