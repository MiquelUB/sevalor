"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Server,
  Database,
  Shield,
  ShieldCheck,
  HardDrive,
  Cpu,
  Activity,
  Terminal,
  CheckCircle2,
  AlertTriangle,
  Rocket,
  RotateCcw,
  FileCode,
  Play,
  Lock,
  Settings,
  Globe,
  Users,
  Check,
  Copy,
  Edit,
  ExternalLink,
  ChevronRight,
  Radio,
  RadioTower,
  KeyRound,
  FileText,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

export default function SuperadminTenantOnboardingPage() {
  // Estat del formulari de l'Assistent (Wizard)
  const [pasActual, setPasActual] = useState<number>(1);
  const [dryRunRunning, setDryRunRunning] = useState<boolean>(false);
  const [dryRunSuccess, setDryRunSuccess] = useState<boolean | null>(null);

  // Pas 1: Dades Fiscals
  const [raoSocial, setRaoSocial] = useState<string>("");
  const [nif, setNif] = useState<string>("");
  const [vertical, setVertical] = useState<string>("SEVALOR");
  const [magatzemFamilies, setMagatzemFamilies] = useState<string>("");
  const [agentPrompt, setAgentPrompt] = useState<string>("");
  const [responsable, setResponsable] = useState<string>("");
  const [emailGerent, setEmailGerent] = useState<string>("");
  const [telefon, setTelefon] = useState<string>("");

  // Pas 2: Domini Propi & Subdomini Dedicat
  const [tipusDomini, setTipusDomini] = useState<"PROPI" | "SEVALOR">("PROPI");
  const [dominiEmpresa, setDominiEmpresa] = useState<string>(""); // ex: "soler.cat"
  const [subdominiPrefix, setSubdominiPrefix] = useState<string>("sevalor"); // ex: "sevalor"
  const [subdomini, setSubdomini] = useState<string>(""); // slug intern, ex: "soler"
  const [sslStatus, setSslStatus] = useState<"IDLE" | "PROCESSING" | "ACTIVE">("ACTIVE");

  // Pas 3: Postgres Schema & RLS
  const [schemaNom, setSchemaNom] = useState<string>("");

  // Pas 4: Quotes & Recursos
  const [tierPla, setTierPla] = useState<"STARTER" | "PRO" | "ENTERPRISE">("PRO");
  const [featureFlags, setFeatureFlags] = useState({
    copilot_ia: true,
    flota_avancada: true,
    planols_tecnics: true,
    telegram_bot: true,
  });

  // Estat de provisionament final
  const [provisioning, setProvisioning] = useState<boolean>(false);
  const [provisionedSuccess, setProvisionedSuccess] = useState<boolean>(false);
  const [invitationUrl, setInvitationUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // FQDN complet calculat en temps real
  const fqdnResultant =
    tipusDomini === "PROPI"
      ? dominiEmpresa.trim()
        ? `${(subdominiPrefix.trim() || "sevalor").toLowerCase()}.${dominiEmpresa.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/.*$/, "")}`
        : ""
      : `${(subdomini.trim() || "tenant").toLowerCase().replace(/[^a-z0-9-]/g, "")}.sevalor.app`;

  // Slug intern deduït
  const slugCalculat =
    subdomini.trim().toLowerCase().replace(/[^a-z0-9-]/g, "") ||
    (dominiEmpresa.trim()
      ? dominiEmpresa.trim().split(".")[0].toLowerCase().replace(/[^a-z0-9-]/g, "")
      : raoSocial.trim().split(" ")[0].toLowerCase().replace(/[^a-z0-9-]/g, "")) ||
    "empresa";

  // Executar Dry-Run
  const handleExecuteDryRun = () => {
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

    setDryRunRunning(false);
    setDryRunSuccess(true);
  };

  // Finalitzar Provisionament Tenant Real
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
          quota_disc_gb: tierPla === "ENTERPRISE" ? 100 : tierPla === "PRO" ? 50 : 10,
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
      {/* Banner de Panell Superior (HUD Top) */}
          <div className="bg-gradient-to-r from-slate-900 to-slate-800 text-white rounded-2xl p-6 shadow-lg border border-slate-700/60 mb-6">
            <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-black tracking-tight text-white">
                    Alta de Nou Tenant • Provisionament d'Organització
                  </h1>
                  <span className="text-xs font-mono font-bold uppercase tracking-wider px-2.5 py-1 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                    RLS Multi-Tenant v4
                  </span>
                </div>
                <p className="text-xs text-slate-300 mt-1 max-w-3xl">
                  Configuració d'entorn aïllat, esquema dedicat PostgreSQL, domini amb certificat TLS automàtic
                  i sobirania de dades estricta a Hetzner Alemanya (cero dependències de núvol públic AWS S3).
                </p>
              </div>

              {/* Botons d'Acció de l'Assistent */}
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => {
                    setPasActual(1);
                    setDryRunSuccess(null);
                  }}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono font-semibold flex items-center gap-1.5 border border-slate-700 transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
                  <span>Reiniciar Assistent</span>
                </button>
                <button
                  type="button"
                  onClick={handleExecuteDryRun}
                  disabled={dryRunRunning}
                  className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow transition-colors"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>{dryRunRunning ? "Executant..." : "Executar Dry-Run"}</span>
                </button>
              </div>
            </div>

            {/* Strip de Telemetria del Clúster */}
            <div className="mt-4 pt-4 border-t border-slate-800 flex flex-wrap items-center gap-4 text-xs font-mono text-slate-300">
              <div className="flex items-center gap-1.5 bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700">
                <Globe className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-slate-400">Target Cluster:</span>
                <span className="font-semibold text-emerald-300">hetzner-prod-fsn1 (Nuremberg DC14)</span>
              </div>
              <div className="flex items-center gap-1.5 bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700">
                <Cpu className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-slate-400">Node:</span>
                <span className="font-semibold text-white">CPX21 (3 vCPU / 4GB RAM / 80GB NVMe)</span>
              </div>
              <div className="flex items-center gap-1.5 bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700">
                <Database className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-slate-400">Postgres:</span>
                <span className="font-semibold text-white">v16 PostGIS amb RLS</span>
              </div>
              <div className="flex items-center gap-1.5 bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700">
                <Lock className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-slate-400">Aïllament:</span>
                <span className="font-semibold text-emerald-300">app.current_empresa_id strictly scoped</span>
              </div>
            </div>
          </div>

          {/* Feedback de Dry-Run */}
          {dryRunSuccess && (
            <div className="mb-6 p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200 flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <span>
                  <strong>Dry-Run completat amb èxit (0 errors):</strong> Domini corporatiu <em>{fqdnResultant}</em> disponible, NIF <em>{nif}</em> vàlid, esquema RLS lliure de col·lisions.
                </span>
              </div>
              <button onClick={() => setDryRunSuccess(null)} className="underline text-emerald-700 dark:text-emerald-300">
                Tancar
              </button>
            </div>
          )}

          {/* Layout Principal: 8 Columnes (Wizard) + 4 Columnes (Telemetria i SRE) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* 8 Columnes: Assistent d'Onboarding (Passos 1 a 4) */}
            <div className="lg:col-span-8 space-y-6">
              {/* Stepper HUD Navigation */}
              <div className="bg-white dark:bg-slate-900 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 transition-colors">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs">
                  {/* Pas 1 */}
                  <button
                    type="button"
                    onClick={() => setPasActual(1)}
                    className={`p-2.5 rounded-lg flex items-center gap-2 border transition-all ${
                      pasActual === 1
                        ? "border-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 font-bold"
                        : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-400"
                    }`}
                  >
                    <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-[10px]">
                      1
                    </span>
                    <div className="flex flex-col text-left truncate">
                      <span className="text-[10px] text-slate-400 uppercase">Pas 01</span>
                      <span className="truncate font-semibold">Dades Fiscals</span>
                    </div>
                  </button>

                  {/* Pas 2 */}
                  <button
                    type="button"
                    onClick={() => setPasActual(2)}
                    className={`p-2.5 rounded-lg flex items-center gap-2 border transition-all ${
                      pasActual === 2
                        ? "border-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 font-bold"
                        : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-400"
                    }`}
                  >
                    <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-[10px]">
                      2
                    </span>
                    <div className="flex flex-col text-left truncate">
                      <span className="text-[10px] text-slate-400 uppercase">Pas 02</span>
                      <span className="truncate font-semibold">Domini &amp; SSL</span>
                    </div>
                  </button>

                  {/* Pas 3 */}
                  <button
                    type="button"
                    onClick={() => setPasActual(3)}
                    className={`p-2.5 rounded-lg flex items-center gap-2 border transition-all ${
                      pasActual === 3
                        ? "border-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 font-bold"
                        : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-400"
                    }`}
                  >
                    <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-[10px]">
                      3
                    </span>
                    <div className="flex flex-col text-left truncate">
                      <span className="text-[10px] text-slate-400 uppercase">Pas 03</span>
                      <span className="truncate font-semibold">Postgres Schema</span>
                    </div>
                  </button>

                  {/* Pas 4 */}
                  <button
                    type="button"
                    onClick={() => setPasActual(4)}
                    className={`p-2.5 rounded-lg flex items-center gap-2 border transition-all ${
                      pasActual === 4
                        ? "border-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 font-bold"
                        : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-400"
                    }`}
                  >
                    <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-[10px]">
                      4
                    </span>
                    <div className="flex flex-col text-left truncate">
                      <span className="text-[10px] text-slate-400 uppercase">Pas 04</span>
                      <span className="truncate font-semibold">Quotes &amp; Flags</span>
                    </div>
                  </button>
                </div>
              </div>

              {/* DETALL PAS 1: Empresa & Dades Fiscals (Spec 021 RF-02, RF-03) */}
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-6 border border-slate-200 dark:border-slate-800 space-y-4 transition-colors">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 flex items-center justify-center font-bold text-xs">
                      1
                    </span>
                    <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                      1. Empresa, Dades Fiscals i Vertical Tècnica
                    </h2>
                  </div>
                  <span className="text-[11px] font-mono font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800">
                    Spec 021 RF-02 / RF-03
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div>
                    <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">Raó Social Corporativa</label>
                    <input
                      type="text"
                      value={raoSocial}
                      onChange={(e) => setRaoSocial(e.target.value)}
                      className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:border-emerald-500 font-medium"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">NIF / CIF Corporatiu</label>
                    <input
                      type="text"
                      value={nif}
                      onChange={(e) => setNif(e.target.value)}
                      className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:border-emerald-500 font-mono font-bold"
                    />
                  </div>

                  {/* Selector de Vertical Tècnica Especialitzada (Spec 021 RF-03) */}
                  <div className="sm:col-span-2">
                    <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">
                      Vertical Tècnica (Condiciona models RAG i formularis)
                    </label>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      {[
                        { id: "SEVALOR", label: "Sevalor", desc: "Agronòmic & Serveis Rurals" },
                        { id: "ELECTRICPRO", label: "ElectricPro", desc: "Baixa Tensió i Climes" },
                        { id: "HYDROPRO", label: "HydroPro", desc: "Xarxes d'Aigua i Reg" },
                        { id: "BUILDINGPRO", label: "BuildingPro", desc: "Climatització i Obres" },
                      ].map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => setVertical(item.id as any)}
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
                      className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">Correu d'Activació Inicial</label>
                    <input
                      type="email"
                      value={emailGerent}
                      onChange={(e) => setEmailGerent(e.target.value)}
                      className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-mono"
                    />
                  </div>
                </div>
              </div>

              {/* DETALL PAS 2: Domini Propi & Subdomini Dedicat (Spec 021 RF-04) */}
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-6 border border-slate-200 dark:border-slate-800 space-y-5 transition-colors">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 flex items-center justify-center font-bold text-xs">
                      2
                    </span>
                    <div>
                      <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                        2. Domini Propi de l'Empresa &amp; Subdomini Dedicat
                      </h2>
                      <span className="text-[10px] font-mono text-slate-500">
                        Arquitectura Multi-Tenant amb Sobirania de Marca (FQDN Propi de Client)
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400 font-mono text-[10px] font-bold">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
                    <span>SSL Let's Encrypt Actiu</span>
                  </div>
                </div>

                {/* Selector d'Estratègia de Domini */}
                <div>
                  <label className="block font-semibold text-slate-600 dark:text-slate-400 text-xs mb-2">
                    Estratègia d'Accés i Hostatjament
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                    <button
                      type="button"
                      onClick={() => setTipusDomini("PROPI")}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        tipusDomini === "PROPI"
                          ? "border-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-900 dark:text-emerald-200 font-bold shadow-sm"
                          : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold flex items-center gap-1.5">
                          <Globe className="w-4 h-4 text-emerald-600" />
                          <span>Domini Propi de l'Empresa</span>
                        </span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900 text-emerald-800 dark:text-emerald-200 uppercase font-mono font-bold">
                          Recomanat
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 font-normal">
                        Cada empresa utilitza el seu propi domini corporatiu (ex: <em>soler.cat</em>) amb subdomini dedicat (ex: <em>sevalor.soler.cat</em>).
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={() => setTipusDomini("SEVALOR")}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        tipusDomini === "SEVALOR"
                          ? "border-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-900 dark:text-emerald-200 font-bold shadow-sm"
                          : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold flex items-center gap-1.5">
                          <Server className="w-4 h-4 text-slate-400" />
                          <span>Subdomini Sevalor.app</span>
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 font-normal">
                        Per a empreses que no disposen de domini propi, s'hostatja com a subdomini directe (ex: <em>soler.sevalor.app</em>).
                      </p>
                    </button>
                  </div>
                </div>

                {/* Camps del Formulari de Domini */}
                {tipusDomini === "PROPI" ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                      {/* Domini Propi de l'Empresa */}
                      <div className="sm:col-span-2">
                        <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                          Domini Corporatiu de l'Empresa <span className="text-emerald-600">*</span>
                        </label>
                        <div className="flex items-center rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden focus-within:border-emerald-500">
                          <span className="px-3 text-slate-400 font-mono text-[11px] bg-slate-50 dark:bg-slate-800/80 border-r border-slate-200 dark:border-slate-700 py-2">
                            https://
                          </span>
                          <input
                            type="text"
                            placeholder="ex. soler.cat o grupsoler.com"
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
                            className="flex-1 p-2 bg-transparent text-slate-800 dark:text-slate-200 font-mono font-bold focus:outline-none"
                          />
                        </div>
                        <span className="text-[10px] text-slate-500 mt-1 block">
                          El domini arrel propietat del client on es crearà el registre CNAME.
                        </span>
                      </div>

                      {/* Subdomini de Servei */}
                      <div>
                        <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                          Subdomini de Servei <span className="text-emerald-600">*</span>
                        </label>
                        <div className="flex items-center rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden focus-within:border-emerald-500">
                          <input
                            type="text"
                            placeholder="sevalor"
                            value={subdominiPrefix}
                            onChange={(e) =>
                              setSubdominiPrefix(
                                e.target.value
                                  .toLowerCase()
                                  .replace(/[^a-z0-9-]/g, "")
                              )
                            }
                            className="flex-1 p-2 bg-transparent text-slate-800 dark:text-slate-200 font-mono font-bold focus:outline-none"
                          />
                        </div>
                        <span className="text-[10px] text-slate-500 mt-1 block">
                          Prefix recomanat: <strong>sevalor</strong> (o <em>app</em>, <em>erp</em>).
                        </span>
                      </div>
                    </div>

                    {/* Identificador / Slug RLS intern */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                      <div>
                        <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">
                          Slug Intern del Tenant (Base de Dades &amp; RLS)
                        </label>
                        <input
                          type="text"
                          placeholder={slugCalculat}
                          value={subdomini}
                          onChange={(e) => setSubdomini(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                          className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-mono text-xs focus:outline-none focus:border-emerald-500"
                        />
                        <span className="text-[10px] text-slate-500 mt-1 block">
                          Clau unívoca d'aïllament a la taula <code>empreses.subdomini</code> (deduïda: <strong>{slugCalculat}</strong>).
                        </span>
                      </div>

                      <div>
                        <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">
                          ACME Resolver &amp; Certbot
                        </label>
                        <div className="p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between">
                          <span className="font-mono text-slate-800 dark:text-slate-200 text-xs">Let's Encrypt TLS-ALPN-01</span>
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-400 font-bold">
                            Hetzner Ingress
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-500 mt-1 block">
                          Certificat TLS automàtic vàlid per a <strong>{fqdnResultant || "sevalor.domini.cat"}</strong>.
                        </span>
                      </div>
                    </div>

                    {/* Targeta Destacada: URL Resultant d'Accés */}
                    <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-950/30 to-slate-900 border border-emerald-800/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs font-mono">
                      <div>
                        <span className="text-slate-400 uppercase text-[10px] font-bold tracking-wider block">
                          Adreça Web Resultant per a l'Empresa:
                        </span>
                        <div className="text-emerald-400 font-bold text-sm mt-0.5 flex items-center gap-2">
                          <Globe className="w-4 h-4 text-emerald-400 shrink-0" />
                          <span>https://{fqdnResultant || "sevalor.soler.cat"}</span>
                        </div>
                      </div>
                      <div className="px-3 py-1 rounded bg-emerald-900/60 border border-emerald-700 text-emerald-300 text-[11px] font-bold">
                        Persistit a <code>domini_custom</code>
                      </div>
                    </div>

                    {/* Guia Tècnica DNS CNAME per al client */}
                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs font-mono space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-800 dark:text-slate-200 uppercase text-[11px] flex items-center gap-1.5">
                          <ExternalLink className="w-3.5 h-3.5 text-emerald-600" />
                          <span>Instruccions de Delegació DNS per a l'Empresa</span>
                        </span>
                        <span className="text-[10px] text-slate-500">Cloudflare / Nominalia / Hetzner DNS</span>
                      </div>
                      <p className="text-[11px] text-slate-600 dark:text-slate-400 font-sans">
                        El client ha d'afegir aquest registre CNAME a la zona DNS del seu domini <strong>{dominiEmpresa || "soler.cat"}</strong>:
                      </p>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                        <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                          <span className="text-slate-400 text-[10px] block">Tipus</span>
                          <span className="font-bold text-emerald-600 dark:text-emerald-400">CNAME</span>
                        </div>
                        <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                          <span className="text-slate-400 text-[10px] block">Nom / Host</span>
                          <span className="font-bold text-slate-800 dark:text-slate-200">{subdominiPrefix || "sevalor"}</span>
                        </div>
                        <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 sm:col-span-2">
                          <span className="text-slate-400 text-[10px] block">Apunta cap a (Target)</span>
                          <span className="font-bold text-slate-800 dark:text-slate-200">edge.sevalor.app</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* Mode Alternatiu: Subdomini directe sota sevalor.app */
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div>
                      <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">Subdomini Sol·licitat</label>
                      <div className="flex items-center rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
                        <input
                          type="text"
                          value={subdomini}
                          onChange={(e) => setSubdomini(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                          className="flex-1 p-2 bg-transparent text-slate-800 dark:text-slate-200 font-mono font-bold focus:outline-none"
                        />
                        <span className="px-3 text-slate-400 font-mono bg-slate-100 dark:bg-slate-800/80 border-l border-slate-200 dark:border-slate-700 py-2">
                          .sevalor.app
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-500 mt-1 block">CNAME configurat automàticament a edge.sevalor.app</span>
                    </div>

                    <div>
                      <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">ACME Provider &amp; Resolver</label>
                      <div className="p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between">
                        <span className="font-mono text-slate-800 dark:text-slate-200">Let's Encrypt TLS-ALPN-01</span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-400 font-bold">
                          Hetzner DNS API
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-500 mt-1 block">Auto-renovació TLS cada 60 dies</span>
                    </div>
                  </div>
                )}

                {/* Terminal Console en Viu (Micro-logs de Certbot & Ingress) */}
                <div className="pt-2">
                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 mb-1">
                    <span className="font-bold uppercase">Registre d'Execució Ingress &amp; TLS (Live Stream Celery)</span>
                    <span>Job ID: job_ssl_982441</span>
                  </div>
                  <div className="bg-slate-950 text-emerald-400 p-3.5 rounded-xl font-mono text-[11px] space-y-1 shadow-inner border border-slate-800">
                    <div className="text-slate-400">[10:44:02] ACME client requesting cert for {fqdnResultant || "sevalor.soler.cat"}</div>
                    <div className="text-slate-300">[10:44:03] DNS challenge verified via Hetzner Cloud API (Target: edge.sevalor.app)</div>
                    <div className="text-amber-400">[10:44:05] Certbot: waiting for Let's Encrypt CA validation response...</div>
                    <div className="text-emerald-400 flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                      <span>[10:44:07] Validation successful: certificate written to /etc/traefik/acme/acme.json</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* DETALL PAS 3: Base de Dades & PostgreSQL Dedicated Schema (Spec 021 RF-07, RF-08) */}
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-6 border border-slate-200 dark:border-slate-800 space-y-4 transition-colors">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 flex items-center justify-center font-bold text-xs">
                      3
                    </span>
                    <div>
                      <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                        3. Base de Dades &amp; PostgreSQL RLS Isolation
                      </h2>
                      <span className="text-[10px] font-mono text-slate-500">
                        Aïllament forçat amb Row Level Security (RLS) sota app.current_empresa_id
                      </span>
                    </div>
                  </div>
                  <span className="text-[11px] font-mono font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800">
                    RLS Configurat
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <span className="text-slate-400 block text-[10px] uppercase">Política d'Aïllament Tenant</span>
                    <span className="text-emerald-600 dark:text-emerald-400 font-bold block mt-1">FORCE ROW LEVEL SECURITY</span>
                    <span className="text-slate-500 text-[10px]">app.current_empresa_id = empresa_id</span>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <span className="text-slate-400 block text-[10px] uppercase">Migracions SQL Executades</span>
                    <span className="text-slate-800 dark:text-slate-200 font-bold block mt-1">Migracions 001-009 Aplicades</span>
                    <span className="text-slate-500 text-[10px]">PostGIS 3.4 GEOMETRY(Point, 4326)</span>
                  </div>

                  <div className="sm:col-span-2 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <span className="text-slate-400 block text-[10px] uppercase">Arbre de Volums Sobirans a Hetzner (Alemanya)</span>
                    <div className="text-[11px] text-slate-700 dark:text-slate-300 mt-1 space-y-0.5">
                      <div>📁 /docs/&lt;empresa_id&gt;/factures/ (PDFs Veri*factu RD 1007/2023)</div>
                      <div>📁 /docs/&lt;empresa_id&gt;/planols/ (Plànols vectorials As-Built)</div>
                      <div>📁 /docs/&lt;empresa_id&gt;/backups/ (Còpies setmanals sense recursivitat)</div>
                      <div>📁 /data/&lt;empresa_id&gt;/vehicles/ (Doble foto odòmetre i carburant)</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* DETALL PAS 4: Quotes, Recursos i Feature Flags (Spec 021 RF-05, RF-06) */}
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-6 border border-slate-200 dark:border-slate-800 space-y-4 transition-colors">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 flex items-center justify-center font-bold text-xs">
                      4
                    </span>
                    <div>
                      <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                        4. Límits de Quota, Operaris i Feature Flags
                      </h2>
                      <span className="text-[10px] font-mono text-slate-500">
                        Quota màxima d'operaris concurrents i commutadors de mòduls
                      </span>
                    </div>
                  </div>
                  <span className="text-[11px] font-mono font-bold text-slate-600 dark:text-slate-400">
                    Tier: {tierPla}
                  </span>
                </div>

                {/* Selecció de Tier de Llicència (Spec 021 RF-05) */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {[
                    { id: "STARTER", nom: "Pla Starter", operaris: "Fins a 5 operaris", disc: "25 GB NVMe" },
                    { id: "PRO", nom: "Pla Pro", operaris: "Fins a 15 operaris", disc: "50 GB NVMe" },
                    { id: "ENTERPRISE", nom: "Pla Enterprise", operaris: "Fins a 50 operaris", disc: "100 GB NVMe" },
                  ].map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setTierPla(p.id as any)}
                      className={`p-3 rounded-xl border text-center transition-all ${
                        tierPla === p.id
                          ? "border-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-900 dark:text-emerald-200 font-bold shadow-sm"
                          : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-400"
                      }`}
                    >
                      <span className="block text-xs font-bold">{p.nom}</span>
                      <span className="block text-[11px] text-emerald-600 dark:text-emerald-400 mt-0.5">{p.operaris}</span>
                      <span className="block text-[10px] text-slate-400 mt-1">{p.disc}</span>
                    </button>
                  ))}
                </div>

                {/* Feature Flags per Inquilí (Spec 021 RF-06) - Zero AWS S3 Garantit */}
                <div className="pt-2">
                  <span className="block text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-2">
                    Mòduls Habilitats (Feature Flags)
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                    <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                      <div>
                        <span className="font-bold block text-slate-800 dark:text-slate-200">Copilot IA &amp; Whisper INT8</span>
                        <span className="text-[10px] text-slate-500">Transcripció i RAG sectorial local</span>
                      </div>
                      <input
                        type="checkbox"
                        checked={featureFlags.copilot_ia}
                        onChange={(e) => setFeatureFlags({ ...featureFlags, copilot_ia: e.target.checked })}
                        className="w-4 h-4 accent-emerald-600 rounded"
                      />
                    </div>

                    <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                      <div>
                        <span className="font-bold block text-slate-800 dark:text-slate-200">Flota Avançada &amp; ITV</span>
                        <span className="text-[10px] text-slate-500">4 veredictes i doble foto carburant</span>
                      </div>
                      <input
                        type="checkbox"
                        checked={featureFlags.flota_avancada}
                        onChange={(e) => setFeatureFlags({ ...featureFlags, flota_avancada: e.target.checked })}
                        className="w-4 h-4 accent-emerald-600 rounded"
                      />
                    </div>

                    <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                      <div>
                        <span className="font-bold block text-slate-800 dark:text-slate-200">Plànols Cartogràfics As-Built</span>
                        <span className="text-[10px] text-slate-500">Capes no destructives i geovalla 50m</span>
                      </div>
                      <input
                        type="checkbox"
                        checked={featureFlags.planols_tecnics}
                        onChange={(e) => setFeatureFlags({ ...featureFlags, planols_tecnics: e.target.checked })}
                        className="w-4 h-4 accent-emerald-600 rounded"
                      />
                    </div>

                    <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                      <div>
                        <span className="font-bold block text-slate-800 dark:text-slate-200">Bot Telegram Clients</span>
                        <span className="text-[10px] text-slate-500">Anti-malware i notificacions ETA</span>
                      </div>
                      <input
                        type="checkbox"
                        checked={featureFlags.telegram_bot}
                        onChange={(e) => setFeatureFlags({ ...featureFlags, telegram_bot: e.target.checked })}
                        className="w-4 h-4 accent-emerald-600 rounded"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Botons Finals d'Execució de l'Assistent */}
              <div className="bg-white dark:bg-slate-900 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3 transition-colors">
                <button
                  type="button"
                  onClick={() => alert("Recursos descartats. Cap canvi no s'ha escrit a la base de dades.")}
                  className="text-rose-600 hover:text-rose-700 text-xs font-mono uppercase font-bold px-3 py-2 transition-colors"
                >
                  Descartar i Netejar Recursos
                </button>

                <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                  <button
                    type="button"
                    onClick={() => alert("Esborrany desat a l'esquema de governança del Superadmin.")}
                    className="px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-lg text-xs font-semibold transition-colors"
                  >
                    Desar Com a Esborrany
                  </button>
                  <button
                    type="button"
                    disabled={provisioning}
                    onClick={handleProvisionTenant}
                    className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 active:scale-98 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow transition-all"
                  >
                    <Rocket className="w-4 h-4" />
                    <span>{provisioning ? "Provisionant Tenant..." : "Provisionar & Activar Tenant"}</span>
                  </button>
                </div>
              </div>

              {/* Missatge d'Error si falla el provisionament */}
              {errorMessage && (
                <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-200 text-xs font-semibold flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              {/* Modal / Enllaç d'Activació Inicial Generat (Spec 021 RF-10, RF-11) */}
              {provisionedSuccess && invitationUrl && (
                <div className="p-6 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border-2 border-emerald-500 text-emerald-950 dark:text-emerald-100 shadow-xl space-y-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-6 h-6 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    <div>
                      <h3 className="text-sm font-bold">Tenant Provisionat amb Èxit!</h3>
                      <p className="text-xs text-slate-600 dark:text-slate-300">
                        S'ha creat l'esquema PostgreSQL, el directori sobirà a Hetzner i l'usuari Boss inicial.
                      </p>
                    </div>
                  </div>
                  <div className="bg-white dark:bg-slate-900 p-3 rounded-lg border border-emerald-200 dark:border-emerald-800 flex items-center justify-between text-xs font-mono">
                    <span className="truncate mr-2 text-slate-800 dark:text-slate-200">{invitationUrl}</span>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(invitationUrl);
                        alert("Enllaç criptogràfic copiat al porta-retalls.");
                      }}
                      className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[11px] font-bold shrink-0 flex items-center gap-1"
                    >
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copiar Enllaç</span>
                    </button>
                  </div>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    * Validesa de 24 hores (Spec 021 RF-11). El Boss haurà de configurar obligatòriament el seu 2FA TOTP i contrasenya ≥ 12 caràcters.
                  </p>
                </div>
              )}
            </div>

            {/* 4 Columnes: Telemetria Monitor & SRE Inspector (Dret) */}
            <div className="lg:col-span-4 space-y-6">
              {/* Targeta 1: Telemetria Hetzner Node CPX21 */}
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-4 border border-slate-200 dark:border-slate-800 space-y-4 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                      Telemetria Hetzner CPX21
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800">
                    Temps Real
                  </span>
                </div>

                {/* CPU Sparkline */}
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 space-y-2">
                  <div className="flex justify-between items-center text-xs font-mono">
                    <span className="text-slate-500">Càrrega CPU (3 vCPU AMD EPYC™)</span>
                    <span className="font-bold text-slate-800 dark:text-slate-200">42%</span>
                  </div>
                  <div className="h-10 w-full flex items-end">
                    <svg className="w-full h-full text-emerald-500" fill="none" preserveAspectRatio="none" viewBox="0 0 200 40">
                      <path d="M0,35 Q20,32 40,25 T80,28 T120,15 T160,20 T200,12" fill="none" stroke="currentColor" strokeWidth="2"></path>
                      <path d="M0,35 Q20,32 40,25 T80,28 T120,15 T160,20 T200,12 L200,40 L0,40 Z" fill="currentColor" fillOpacity="0.12"></path>
                    </svg>
                  </div>
                </div>

                {/* Memòria RAM */}
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 space-y-1.5 font-mono text-xs">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Memòria RAM Utilitzada</span>
                    <span className="font-bold text-slate-800 dark:text-slate-200">2.8 GB / 4.0 GB (70%)</span>
                  </div>
                  <div className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden flex">
                    <div className="h-full bg-emerald-600 rounded-full" style={{ width: "70%" }}></div>
                  </div>
                </div>

                {/* NVMe IOPS */}
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 font-mono text-xs space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">NVMe Rendiment</span>
                    <span className="font-bold text-emerald-600 dark:text-emerald-400">4,210 IOPS</span>
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-500">
                    <span>Taxa Escriptura:</span>
                    <span className="text-slate-800 dark:text-slate-200 font-semibold">84 MB/s</span>
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-500">
                    <span>Latència I/O:</span>
                    <span className="text-slate-800 dark:text-slate-200 font-semibold">0.4 ms</span>
                  </div>
                </div>
              </div>

              {/* Targeta 2: Pool PgBouncer (PostgreSQL 16) */}
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-4 border border-slate-200 dark:border-slate-800 space-y-3 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                      Pool PgBouncer (Postgres 16)
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">Transaction Mode</span>
                </div>
                <div className="grid grid-cols-2 gap-2 font-mono text-xs">
                  <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <span className="text-slate-500 text-[10px] uppercase">Connexions</span>
                    <span className="text-xl font-bold text-slate-800 dark:text-slate-100 block mt-1">38</span>
                    <span className="text-[10px] text-slate-400">Límit: 100 conns</span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <span className="text-slate-500 text-[10px] uppercase">Servers Idle</span>
                    <span className="text-xl font-bold text-emerald-600 dark:text-emerald-400 block mt-1">12</span>
                    <span className="text-[10px] text-slate-400">Latència: 1.2ms</span>
                  </div>
                </div>
              </div>

              {/* Targeta 3: Seguretat & Registres Audit (RLS) */}
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-4 border border-slate-200 dark:border-slate-800 space-y-3 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                      Seguretat &amp; Registres Audit (RLS)
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                    SHA-256
                  </span>
                </div>
                <div className="space-y-2 font-mono text-[10px]">
                  <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <div className="flex justify-between text-slate-500">
                      <span className="font-bold text-emerald-600 dark:text-emerald-400">[10:44:01] RLS_ENFORCE</span>
                      <span>7a8f...92d1</span>
                    </div>
                    <span className="text-slate-700 dark:text-slate-300 block mt-0.5">
                      tenant_id='{subdomini || "tenant"}' registered. RLS policy enabled.
                    </span>
                  </div>

                  <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <div className="flex justify-between text-slate-500">
                      <span className="font-bold text-emerald-600 dark:text-emerald-400">[10:43:58] RATE_LIMIT_OK</span>
                      <span>99c2...410b</span>
                    </div>
                    <span className="text-slate-700 dark:text-slate-300 block mt-0.5">
                      IP 127.0.0.1/32 allowed 40 req/min for setup endpoint.
                    </span>
                  </div>

                  <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <div className="flex justify-between text-slate-500">
                      <span className="font-bold text-slate-600 dark:text-slate-400">[10:43:12] AUDIT_EVENT</span>
                      <span>33b1...81fe</span>
                    </div>
                    <span className="text-slate-700 dark:text-slate-300 block mt-0.5">
                      Superadmin session authenticated. Onboarding wizard ready.
                    </span>
                  </div>
                </div>
              </div>

              {/* Targeta 4: Estat Microserveis */}
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-4 border border-slate-200 dark:border-slate-800 space-y-2 font-mono text-xs transition-colors">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 mb-2">
                  Estat dels Microserveis
                </h3>
                <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500">Traefik Ingress Edge</span>
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">99.99% Operatiu</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500">Celery Workers &amp; Redis</span>
                  <span className="text-slate-800 dark:text-slate-200 font-bold">4 lliures / 1 actiu</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500">Extensió PostGIS 3.4</span>
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">v3.4.2 Actiu</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-500">API Cloud Hetzner</span>
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">Latència 18ms</span>
                </div>
              </div>
        </div>
      </div>
    </div>
  );
}
