"use client";

import React, { useState, useEffect, useRef } from "react";
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
  Upload,
  Image as ImageIcon,
  Trash2,
  Eye,
  Palette,
  Check,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

function hslToHex(hslStr: string): string {
  try {
    const parts = hslStr
      .replace(/[%deg,]/g, " ")
      .trim()
      .split(/\s+/)
      .map(Number);
    if (parts.length < 3 || parts.some(isNaN)) return "#10b981";
    const h = ((parts[0] % 360) + 360) % 360;
    const s = Math.min(100, Math.max(0, parts[1])) / 100;
    const l = Math.min(100, Math.max(0, parts[2])) / 100;

    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
    const m = l - c / 2;
    let r = 0,
      g = 0,
      b = 0;

    if (h < 60) {
      r = c; g = x; b = 0;
    } else if (h < 120) {
      r = x; g = c; b = 0;
    } else if (h < 180) {
      r = 0; g = c; b = x;
    } else if (h < 240) {
      r = 0; g = x; b = c;
    } else if (h < 300) {
      r = x; g = 0; b = c;
    } else {
      r = c; g = 0; b = x;
    }

    const toHex = (val: number) => {
      const hex = Math.round((val + m) * 255).toString(16);
      return hex.length === 1 ? "0" + hex : hex;
    };
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
  } catch {
    return "#10b981";
  }
}

function hexToHsl(hex: string): string {
  try {
    let cleanHex = hex.replace("#", "").trim();
    if (cleanHex.length === 3) {
      cleanHex = cleanHex
        .split("")
        .map((c) => c + c)
        .join("");
    }
    if (cleanHex.length !== 6) return "142 71% 25%";

    const r = parseInt(cleanHex.substring(0, 2), 16) / 255;
    const g = parseInt(cleanHex.substring(2, 4), 16) / 255;
    const b = parseInt(cleanHex.substring(4, 6), 16) / 255;

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const delta = max - min;
    let l = (max + min) / 2;
    let s = 0;
    let h = 0;

    if (delta !== 0) {
      s = delta / (1 - Math.abs(2 * l - 1));
      if (max === r) {
        h = ((g - b) / delta) % 6;
      } else if (max === g) {
        h = (b - r) / delta + 2;
      } else {
        h = (r - g) / delta + 4;
      }
      h = Math.round(h * 60);
      if (h < 0) h += 360;
    }

    return `${h} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
  } catch {
    return "142 71% 25%";
  }
}

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

  // Logotip de la nova empresa
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoBase64, setLogoBase64] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSelectLogo = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage("La imatge seleccionada supera el límit màxim permès de 10 MB.");
      return;
    }

    setErrorMessage(null);
    setLogoFile(file);
    const previewUrl = URL.createObjectURL(file);
    setLogoPreview(previewUrl);

    const reader = new FileReader();
    reader.onload = () => {
      setLogoBase64(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleClearLogo = () => {
    setLogoFile(null);
    setLogoPreview(null);
    setLogoBase64(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Pas 2: Model de Dominis Desacoblat (Fase 2)
  // Camp 1 (Obligatori): Slug / Subdomini base de garantia
  const [slug, setSlug] = useState<string>("");
  const [slugManual, setSlugManual] = useState<boolean>(false);

  // Camp 2 (Opcional): Domini personalitzat extern propi
  const [dominiCustom, setDominiCustom] = useState<string>("");
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

  // Càlcul intel·ligent del slug intern únic a PostgreSQL RLS
  const slugFromRao = raoSocial
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

  const slugCalculat =
    (slug.trim() ? slug.trim().toLowerCase().replace(/[^a-z0-9-]/g, "") : "") ||
    (slugFromRao && !["sevalor", "admin", "api", "superadmin", "billing", "app"].includes(slugFromRao)
      ? slugFromRao
      : "") ||
    `tenant-${Date.now().toString().slice(-4)}`;

  const dominiCustomNet = dominiCustom
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/\/.*$/, "")
    .replace(/[^a-z0-9.-]/g, "");

  const fqdnResultant = dominiCustomNet || `${slugCalculat}.sevalor.cat`;

  // Extracció de peces del domini per a la instrucció DNS CNAME
  const dominiParts = dominiCustomNet ? dominiCustomNet.split(".").filter(Boolean) : [];
  const cnameHost =
    dominiParts.length > 2
      ? dominiParts.slice(0, dominiParts.length - 2).join(".")
      : dominiParts.length === 2
      ? dominiParts[0]
      : dominiParts[0] || "subdomini";

  const cnameRootDomain =
    dominiParts.length >= 2
      ? dominiParts.slice(-2).join(".")
      : dominiCustomNet || "empresa.cat";

  const handleCheckDnsLive = async () => {
    if (!dominiCustomNet) {
      setErrorMessage("Introdueix primer un domini personalitzat extern per verificar la redirecció DNS.");
      return;
    }
    setCheckingDns(true);
    setDnsResult(null);
    setErrorMessage(null);
    try {
      const res = await apiFetch<any>("/superadmin/tenants/verificar-dns", {
        method: "POST",
        body: JSON.stringify({ domini: dominiCustomNet, fqdn: dominiCustomNet }),
      });
      setDnsResult(res);
    } catch (err: any) {
      setDnsResult({
        resolt: false,
        fqdn: dominiCustomNet,
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

    if (!slugCalculat || slugCalculat.length < 2) {
      setDryRunRunning(false);
      setDryRunSuccess(false);
      setErrorMessage("Cal indicar un slug / subdomini intern de garantia vàlid (mínim 2 caràcters).");
      return;
    }

    if (dominiCustomNet) {
      await handleCheckDnsLive();
    }
    setDryRunRunning(false);
    setDryRunSuccess(true);
  };

  const handleResetForm = () => {
    setRaoSocial("");
    setNif("");
    setResponsable("");
    setEmailGerent("");
    setSlug("");
    setSlugManual(false);
    setDominiCustom("");
    setDnsResult(null);
    setDryRunSuccess(null);
    setErrorMessage(null);
    handleClearLogo();
    setPasActual(1);
  };

  const handleProvisionTenant = async () => {
    setProvisioning(true);
    setErrorMessage(null);
    try {
      const nomParts = responsable.trim().split(" ");
      const nom = nomParts[0] || "Gerent";
      const cognoms = nomParts.slice(1).join(" ") || "General";

      const slugFinal = slugCalculat;
      const dominiCustomFinal = dominiCustomNet || undefined;

      const data = await apiFetch<any>("/superadmin/tenants/onboarding", {
        method: "POST",
        body: JSON.stringify({
          rao_social: raoSocial.trim(),
          nif: nif.trim().toUpperCase(),
          slug: slugFinal,
          subdomini: slugFinal,
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
          logotip_base64: logoBase64 || undefined,
          boss_nif: nif.trim().toUpperCase(),
          boss_nom: nom,
          boss_cognoms: cognoms,
          boss_email: emailGerent.trim().toLowerCase(),
          boss_telefon: telefon.trim() || "+34600000000",
          feature_flags: featureFlags,
        }),
      });

      // Si s'ha seleccionat un fitxer de logo, assegurem també la pujada al seu endpoint sobirà
      if (logoFile && data?.tenant?.id) {
        try {
          const fd = new FormData();
          fd.append("fitxer", logoFile);
          await apiFetch(`/superadmin/empreses/${data.tenant.id}/logotip`, {
            method: "POST",
            body: fd,
          });
        } catch {
          // Conserva el flux principal si ja s'ha processat
        }
      }

      setProvisionedSuccess(true);
      const hostAcceso = dominiCustomFinal || `${slugFinal}.sevalor.cat`;
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
                <label className="block font-semibold text-slate-600 dark:text-slate-400 mb-1">
                  NIF / CIF Corporatiu (Únic a la plataforma)
                </label>
                <input
                  type="text"
                  value={nif}
                  onChange={(e) => setNif(e.target.value)}
                  placeholder="ex. B67890123"
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

              {/* SUB-BLOC: LOGOTIP CORPORATIU & TOKENS HSL CAMALEÓ */}
              <div className="sm:col-span-2 pt-3 border-t border-slate-200 dark:border-slate-800 space-y-4">
                {/* 1. SELECCIÓ DE LOGOTIP OFICIAL */}
                <div>
                  <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-1.5 text-xs">
                    <ImageIcon className="w-3.5 h-3.5 text-emerald-500" />
                    <span>Logotip Oficial de l'Empresa (Emmagatzematge Hetzner /docs)</span>
                  </label>

                  <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 flex flex-wrap sm:flex-nowrap items-center gap-4">
                    {/* Visualitzador del logo o monograma dinàmic */}
                    <div className="w-16 h-16 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 p-1 flex items-center justify-center shrink-0 shadow-inner overflow-hidden">
                      {logoPreview ? (
                        <img
                          src={logoPreview}
                          alt="Logotip seleccionat"
                          className="max-h-full max-w-full object-contain"
                        />
                      ) : (
                        <div
                          className="w-full h-full rounded-lg flex items-center justify-center text-white font-black text-lg transition-colors"
                          style={{ backgroundColor: `hsl(${primariHsl})` }}
                        >
                          {(raoSocial.trim()
                            ? raoSocial.trim().split(" ").slice(0, 2).map((w) => w[0]?.toUpperCase()).join("")
                            : "SV") || "SV"}
                        </div>
                      )}
                    </div>

                    <div className="space-y-1.5 flex-1 min-w-[220px]">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                          {logoFile ? logoFile.name : "Monograma Dinàmic per Defecte"}
                        </span>
                        {logoFile ? (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold">
                            {(logoFile.size / 1024).toFixed(1)} KB
                          </span>
                        ) : (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                            Auto-generat
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        Admet <strong>PNG, JPG, WebP o SVG</strong> (màx 10 MB). Es verificarà per Magic Bytes i s'allotjarà al volum sobirà de l'empresa.
                      </p>

                      <div className="flex items-center gap-2 pt-1">
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept="image/png,image/jpeg,image/webp,image/svg+xml"
                          onChange={handleSelectLogo}
                          className="hidden"
                        />
                        <button
                          type="button"
                          onClick={() => fileInputRef.current?.click()}
                          className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm transition-colors"
                        >
                          <Upload className="w-3.5 h-3.5" />
                          <span>{logoFile ? "Canviar Logotip" : "Seleccionar Logotip"}</span>
                        </button>
                        {logoFile && (
                          <button
                            type="button"
                            onClick={handleClearLogo}
                            className="px-2.5 py-1.5 rounded-lg bg-slate-200 hover:bg-rose-100 text-slate-700 hover:text-rose-700 dark:bg-slate-700 dark:hover:bg-rose-950/60 dark:text-slate-300 dark:hover:text-rose-300 text-xs font-mono font-semibold flex items-center gap-1 transition-colors"
                            title="Eliminar selecció"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            <span>Treure</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* 2. SELECTORS DE COLOR HSL AMB PALETA VISUAL */}
                <div>
                  <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-1.5 text-xs">
                    <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
                    <span>Colors Corporatius HSL (Chameleon UI Engine)</span>
                  </label>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {/* Primari */}
                    <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-700 dark:text-slate-300">Primari</span>
                        <input
                          type="color"
                          value={hslToHex(primariHsl)}
                          onChange={(e) => setPrimariHsl(hexToHsl(e.target.value))}
                          className="w-6 h-6 rounded cursor-pointer border border-white shadow-sm p-0 bg-transparent"
                          title="Tria color primari"
                        />
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">
                        HEX: {hslToHex(primariHsl).toUpperCase()}
                      </div>
                      <input
                        type="text"
                        value={primariHsl}
                        onChange={(e) => setPrimariHsl(e.target.value)}
                        className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs rounded-lg p-2 font-mono font-bold"
                      />
                    </div>

                    {/* Secundari */}
                    <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-700 dark:text-slate-300">Secundari</span>
                        <input
                          type="color"
                          value={hslToHex(secundariHsl)}
                          onChange={(e) => setSecundariHsl(hexToHsl(e.target.value))}
                          className="w-6 h-6 rounded cursor-pointer border border-white shadow-sm p-0 bg-transparent"
                          title="Tria color secundari"
                        />
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">
                        HEX: {hslToHex(secundariHsl).toUpperCase()}
                      </div>
                      <input
                        type="text"
                        value={secundariHsl}
                        onChange={(e) => setSecundariHsl(e.target.value)}
                        className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs rounded-lg p-2 font-mono font-bold"
                      />
                    </div>

                    {/* Accent */}
                    <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-700 dark:text-slate-300">Accent</span>
                        <input
                          type="color"
                          value={hslToHex(accentHsl)}
                          onChange={(e) => setAccentHsl(hexToHsl(e.target.value))}
                          className="w-6 h-6 rounded cursor-pointer border border-white shadow-sm p-0 bg-transparent"
                          title="Tria color d'accent"
                        />
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">
                        HEX: {hslToHex(accentHsl).toUpperCase()}
                      </div>
                      <input
                        type="text"
                        value={accentHsl}
                        onChange={(e) => setAccentHsl(e.target.value)}
                        className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs rounded-lg p-2 font-mono font-bold"
                      />
                    </div>
                  </div>
                </div>

                {/* 3. SIMULADOR EN VIU DE MARCA */}
                <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-100/70 dark:bg-slate-950/70 space-y-2">
                  <div className="flex items-center justify-between text-[11px] font-mono font-bold text-slate-500">
                    <span className="flex items-center gap-1">
                      <Eye className="w-3.5 h-3.5 text-blue-500" />
                      <span>Previsualització en Viu de la Identitat Camaleó</span>
                    </span>
                    <span className="text-[10px] opacity-75">WCAG 2.1 AA</span>
                  </div>

                  <div
                    className="p-3 rounded-xl text-white flex items-center justify-between shadow-sm transition-colors"
                    style={{ backgroundColor: `hsl(${primariHsl})` }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-white/20 p-1 flex items-center justify-center overflow-hidden shrink-0">
                        {logoPreview ? (
                          <img src={logoPreview} alt="Logo" className="max-h-full max-w-full object-contain" />
                        ) : (
                          <span className="font-black text-xs">
                            {(raoSocial.trim()
                              ? raoSocial.trim().split(" ").slice(0, 2).map((w) => w[0]?.toUpperCase()).join("")
                              : "SV") || "SV"}
                          </span>
                        )}
                      </div>
                      <div>
                        <div className="text-xs font-black leading-tight">
                          {raoSocial.trim() || "Instal·lacions Soler S.L."}
                        </div>
                        <div className="text-[10px] opacity-80 font-mono">
                          {vertical} • {fqdnResultant || "sevalor.app"}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span
                        className="px-2 py-0.5 rounded-full text-[10px] font-bold text-slate-900 transition-colors"
                        style={{ backgroundColor: `hsl(${secundariHsl})` }}
                      >
                        {tierPla}
                      </span>
                      <span
                        className="w-2.5 h-2.5 rounded-full shadow-sm"
                        style={{ backgroundColor: `hsl(${accentHsl})` }}
                        title="Accent"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* PAS 2: Model de Dominis Desacoblat: Slug Base (Garantia) + Domini Extern (Opcional) */}
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-6 border border-slate-200 dark:border-slate-800 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 flex items-center justify-center font-bold text-xs">
                  2
                </span>
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                    2. Desacoblament de Dominis: Subdomini Base &amp; Domini Personalitzat
                  </h2>
                  <span className="text-[10px] font-mono text-slate-500">
                    Garantia d'accés immediat via subdomini intern + vinculació opcional de domini corporatiu del client
                  </span>
                </div>
              </div>
              {dominiCustomNet && (
                <button
                  type="button"
                  onClick={handleCheckDnsLive}
                  disabled={checkingDns}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-bold shadow-sm transition-colors"
                >
                  {checkingDns ? "Verificant DNS..." : "Comprovar DNS Extern en Viu"}
                </button>
              )}
            </div>

            <div className="p-3.5 rounded-xl border border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/50 dark:bg-emerald-950/30 text-xs">
              <span className="font-bold flex items-center gap-1.5 mb-1 text-emerald-800 dark:text-emerald-300">
                <Globe className="w-4 h-4 text-emerald-600" />
                <span>Arquitectura de Dominis Multi-Tenant Desacoblada</span>
              </span>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 font-normal">
                L'empresa disposa sempre d'un <strong>subdomini de garantia permanent</strong> (ex: <code>{slugCalculat}.sevalor.cat</code>) perquè pugui operar immediatament. Opcionalment, si el client vol el seu propi domini (ex: <code>sevalormante.projectexinoxano.cat</code>), el pot configurar ara o posteriorment des de la seva fitxa.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* CAMP 1: OBLIGATORI - SLUG / SUBDOMINI BASE */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block font-bold text-slate-700 dark:text-slate-300 text-xs">
                    Camp 1 (Obligatori): Slug / Subdomini de Garantia
                  </label>
                  <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 font-bold bg-emerald-100 dark:bg-emerald-950 px-2 py-0.5 rounded">
                    Immediat (Sense DNS)
                  </span>
                </div>
                <div className="flex items-center rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 overflow-hidden font-mono text-sm">
                  <span className="px-3 text-slate-400 text-xs bg-slate-100 dark:bg-slate-800/80 border-r border-slate-200 dark:border-slate-700 py-2.5">
                    https://
                  </span>
                  <input
                    type="text"
                    placeholder="nomempresa"
                    value={slug}
                    onChange={(e) => {
                      setSlugManual(true);
                      setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""));
                    }}
                    className="w-full bg-transparent p-2.5 font-bold text-slate-900 dark:text-white focus:outline-none"
                  />
                  <span className="px-3 text-emerald-600 dark:text-emerald-400 font-bold text-xs bg-emerald-50 dark:bg-emerald-950/60 border-l border-slate-200 dark:border-slate-700 py-2.5">
                    .sevalor.cat
                  </span>
                </div>
                <p className="text-[11px] text-slate-500">
                  Subdomini intern aïllat a PostgreSQL RLS. Actiu des del segon 1 de la creació sense dependre de proveïdors DNS externs.
                </p>
              </div>

              {/* CAMP 2: OPCIONAL - DOMINI PERSONALITZAT EXTERN */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block font-bold text-slate-700 dark:text-slate-300 text-xs">
                    Camp 2 (Opcional): Domini Corporatiu del Client
                  </label>
                  <span className="text-[10px] font-mono text-slate-500 bg-slate-200 dark:bg-slate-800 px-2 py-0.5 rounded">
                    Requereix CNAME/A
                  </span>
                </div>
                <div className="flex items-center rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 overflow-hidden font-mono text-sm">
                  <span className="px-3 text-slate-400 text-xs bg-slate-100 dark:bg-slate-800/80 border-r border-slate-200 dark:border-slate-700 py-2.5">
                    https://
                  </span>
                  <input
                    type="text"
                    placeholder="ex. sevalormante.projectexinoxano.cat o erp.soler.cat"
                    value={dominiCustom}
                    onChange={(e) =>
                      setDominiCustom(
                        e.target.value
                          .toLowerCase()
                          .replace(/^https?:\/\//, "")
                          .replace(/\/.*$/, "")
                          .replace(/[^a-z0-9.-]/g, "")
                      )
                    }
                    className="w-full bg-transparent p-2.5 font-bold text-slate-900 dark:text-white focus:outline-none"
                  />
                </div>
                <p className="text-[11px] text-slate-500">
                  Si s'especifica, l'empresa també respondrà per aquest domini un cop el client configuri el seu DNS. Si encara no propaga, no bloquejarà l'alta.
                </p>
              </div>
            </div>

            {/* Instruccions de Redirecció DNS si hi ha domini custom */}
            {dominiCustomNet ? (
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs font-mono space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-800 dark:text-slate-200 uppercase text-[11px] flex items-center gap-1.5">
                    <ExternalLink className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Configuració DNS requerida al proveïdor del client ({cnameRootDomain})</span>
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 dark:text-slate-400 font-sans">
                  Perquè <strong>{dominiCustomNet}</strong> carregui la plataforma, el client ha de crear aquest registre:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                  <div className="p-2.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                    <span className="text-slate-400 text-[10px] block font-bold">Registre Tipus A (Recomanat)</span>
                    <span className="font-bold text-emerald-600 block text-xs">IP 178.104.83.189</span>
                    <span className="text-[10px] text-slate-500">Host: {cnameHost}</span>
                  </div>
                  <div className="p-2.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                    <span className="text-slate-400 text-[10px] block font-bold">Registre Tipus CNAME</span>
                    <span className="font-bold text-slate-800 dark:text-slate-200 block break-all text-[11px]">
                      sevalor-sevalor-pwa.80opze.easypanel.host
                    </span>
                    <span className="text-[10px] text-slate-500">Host: {cnameHost}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-3 rounded-xl bg-slate-100/70 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-400 flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                <span>
                  Sense domini extern. L'empresa quedarà disponible immediatament a <strong>https://{slugCalculat}.sevalor.cat</strong>.
                </span>
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
                  Sonda DNS Real per a {dnsResult.domini || dnsResult.fqdn}: {dnsResult.resolt ? "RESOLT CORRECTAMENT" : "ENCARA NO RESOLT"}
                </div>
                <div>{dnsResult.missatge || dnsResult.detall}</div>
                {Array.isArray(dnsResult.ips) && dnsResult.ips.length > 0 && (
                  <div className="text-[10px]">IPs detectades: {dnsResult.ips.join(", ")}</div>
                )}
                {Array.isArray(dnsResult.ips_detectades) && dnsResult.ips_detectades.length > 0 && (
                  <div className="text-[10px]">IPs detectades: {dnsResult.ips_detectades.join(", ")}</div>
                )}
                {dnsResult.cname_detectat && (
                  <div className="text-[10px]">CNAME detectat: {dnsResult.cname_detectat}</div>
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

            <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs font-mono flex items-center justify-between">
              <span className="text-slate-600 dark:text-slate-400">Identificador intern PostgreSQL (RLS Tenant Slug):</span>
              <span className="font-bold text-emerald-700 dark:text-emerald-300">{slugCalculat}</span>
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
