"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Save,
  AlertTriangle,
  ShieldCheck,
  PowerOff,
  Zap,
  Activity,
  Users,
  HardDrive,
  Eye,
  CheckCircle2,
  FileText,
  Radio,
  Building2,
  Sparkles,
  Layers,
  Truck,
  MessageSquare,
  Globe,
  Cpu,
} from "lucide-react";
import { apiFetch, setAuthToken } from "@/lib/api";

export default function EmpresaDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [tenant, setTenant] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [certificatUrl, setCertificatUrl] = useState<string | null>(null);

  // Form states
  const [estat, setEstat] = useState("ACTIU");
  const [pla, setPla] = useState("STARTER");
  const [dominiCustom, setDominiCustom] = useState("");
  const [subdomini, setSubdomini] = useState("");
  const [features, setFeatures] = useState({
    feature_copilot_ia: false,
    feature_flota: true,
    feature_planols: false,
    feature_telegram: true,
    node_ia_url: "",
    node_ia_actiu: false,
  });

  const fetchTenant = async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const data = await apiFetch<any>(`/superadmin/tenants/${params.id}`);
      if (data) {
        setTenant(data);
        setEstat(data.estat_pagament || data.estat || "ACTIU");
        setPla(data.pla_subscripcio || data.pla || "STARTER");
        setDominiCustom(data.domini_custom || "");
        setSubdomini(data.subdomini || "");
        setFeatures({
          feature_copilot_ia: Boolean(data.feature_copilot_ia),
          feature_flota: Boolean(data.feature_flota),
          feature_planols: Boolean(data.feature_planols),
          feature_telegram: Boolean(data.feature_telegram),
          node_ia_url: data.node_ia_url || "",
          node_ia_actiu: Boolean(data.node_ia_actiu),
        });
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Error al carregar el tenant.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenant();
  }, [params.id]);

  const handleSave = async () => {
    setSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      // 1. Guardar Estat
      if (estat !== tenant.estat_pagament) {
        await apiFetch(`/superadmin/tenants/${params.id}/estat`, {
          method: "PUT",
          body: JSON.stringify({ estat }),
        });
      }

      // 2. Guardar Quota / Pla (Quota Guard validation on backend)
      if (pla !== tenant.pla_subscripcio) {
        await apiFetch(`/superadmin/tenants/${params.id}/quota`, {
          method: "PUT",
          body: JSON.stringify({ pla_subscripcio: pla }),
        });
      }

      // 3. Guardar Feature Flags
      await apiFetch(`/superadmin/tenants/${params.id}/feature-flags`, {
        method: "PUT",
        body: JSON.stringify(features),
      });

      // 4. Guardar Domini / Subdomini si han canviat
      if (
        dominiCustom !== (tenant.domini_custom || "") ||
        subdomini !== (tenant.subdomini || "")
      ) {
        await apiFetch(`/superadmin/tenants/${params.id}/domini`, {
          method: "PUT",
          body: JSON.stringify({
            domini_custom: dominiCustom.trim() || null,
            subdomini: subdomini.trim() || undefined,
          }),
        });
      }

      setSuccessMessage("Configuració del tenant desada correctament a PostgreSQL.");
      fetchTenant();
    } catch (err: any) {
      setErrorMessage(err.message || "Error en desar els canvis del tenant.");
    } finally {
      setSaving(false);
    }
  };

  const handleImpersonate = async () => {
    if (!confirm("Vols iniciar sessió com a administrador tècnic per a aquest tenant? (Màx 2 hores, només lectura sobre finances)")) {
      return;
    }
    try {
      const data = await apiFetch<any>(`/superadmin/tenants/${params.id}/impersonate`, {
        method: "POST",
      });
      if (data?.access_token) {
        setAuthToken(data.access_token);
        localStorage.setItem("sevalor_user", JSON.stringify({
          ...data,
          is_impersonation: true,
          empresa_id: params.id,
          rol: "SUPERADMIN",
        }));
        localStorage.setItem("sevalor_tenant_id", params.id);
        window.location.href = "/gestio";
      }
    } catch (e: any) {
      alert("Error d'impersonació: " + (e.message || "Desconegut"));
    }
  };

  const handleDestroy = async () => {
    const confirmText = prompt(
      `ATENCIÓ: Aquesta acció iniciarà la BAIXA CERTIFICADA del tenant "${tenant?.nom || tenant?.rao_social}".\n` +
      `Es generarà un certificat de destrucció criptogràfic (RGPD) i s'establirà una custòdia de 30 dies abans de la purga irreversible.\n` +
      `Per confirmar, escriu exactament: ELIMINAR`
    );

    if (confirmText !== "ELIMINAR") {
      alert("Acció cancel·lada.");
      return;
    }

    try {
      const res = await apiFetch<any>(`/superadmin/tenants/${params.id}/destruccio`, {
        method: "POST",
      });
      if (res && res.certificat_url) {
        setCertificatUrl(res.certificat_url);
        alert("Tenant marcat com a ELIMINAT. Certificat generat amb èxit.");
      }
      fetchTenant();
    } catch (e: any) {
      alert("Error en l'offboarding: " + (e.message || "Desconegut"));
    }
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-xs font-mono text-slate-400">
        Carregant dades del tenant des de PostgreSQL...
      </div>
    );
  }

  if (!tenant && errorMessage) {
    return (
      <div className="p-8 max-w-xl mx-auto space-y-4">
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs font-mono">
          {errorMessage}
        </div>
        <Link
          href="/superadmin/empreses"
          className="inline-flex items-center gap-1 text-xs font-bold text-slate-600 dark:text-slate-300 hover:underline"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Tornar al llistat
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-4 md:p-8 space-y-6 w-full">
      {/* NAVEGACIÓ ENRERE */}
      <Link
        href="/superadmin/empreses"
        className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Tornar a Gestió de Tenants</span>
      </Link>

      {/* CAPÇALERA DE GOVERNANÇA */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-2xl font-black text-slate-900 dark:text-white">
              {tenant?.nom || tenant?.rao_social}
            </h1>
            <span className="text-xs px-2.5 py-1 rounded-lg font-mono bg-emerald-50 dark:bg-emerald-950/70 text-emerald-700 dark:text-emerald-400 font-bold border border-emerald-300 dark:border-emerald-800 flex items-center gap-1.5">
              <span>{tenant?.domini_custom || `${tenant?.subdomini}.sevalor.app`}</span>
              {tenant?.domini_custom && (
                <span className="px-1.5 py-0.2 rounded bg-emerald-200 dark:bg-emerald-900 text-emerald-900 dark:text-emerald-200 text-[9px] uppercase font-bold">
                  Domini Propi
                </span>
              )}
            </span>
          </div>
          <p className="text-xs font-mono text-slate-500 dark:text-slate-400 mt-1">
            NIF: {tenant?.nif || "N/A"} • ID: {tenant?.id} • Vertical: {tenant?.vertical || "SEVALOR"}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleImpersonate}
            className="px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-mono font-bold flex items-center gap-1.5 border border-slate-300 dark:border-slate-700 transition-colors shadow-sm"
            title="Sessió segura d'impersonació"
          >
            <Eye className="w-3.5 h-3.5 text-blue-500" />
            <span>Impersonació (2h)</span>
          </button>

          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-colors shadow disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? "Desant a PostgreSQL..." : "Desar Canvis"}</span>
          </button>
        </div>
      </div>

      {/* MISSATGES DE FEEDBACK */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs font-mono flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/70 border border-emerald-300 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs font-mono flex items-center gap-2.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {certificatUrl && (
        <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-950/70 border border-blue-300 dark:border-blue-800 text-blue-800 dark:text-blue-200 text-xs font-mono flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-blue-500" />
            <span>Certificat de destrucció generat al disc sobirà: {certificatUrl}</span>
          </div>
          <Link
            href={`/api/v1/superadmin/tenants/auditoria/certificats/${params.id}/descarregar`}
            target="_blank"
            className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-500"
          >
            Descarregar PDF
          </Link>
        </div>
      )}

      {/* FORMULARI DE CONFIGURACIÓ DE TENANT */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* BLOC 1: CICLE DE VIDA SAAS */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-500" />
              <span>Cicle de Vida SaaS (Estat Pagament)</span>
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-bold">
              RLS SESSION
            </span>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">
              Estat del Client
            </label>
            <select
              value={estat}
              onChange={(e) => setEstat(e.target.value)}
              className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-xs rounded-xl p-2.5 font-mono focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="TRIAL">TRIAL (Període de prova 14 dies)</option>
              <option value="ACTIU">ACTIU (Subscripció al corrent de pagament)</option>
              <option value="SUSPES_PAGAMENT">SUSPÈS (Bloqueig per impagament de quota)</option>
              <option value="MANTENIMENT">MANTENIMENT (Accés temporalment restringit)</option>
              <option value="BAIXA_OFFBOARDING">BAIXA (En període de custòdia 30 dies)</option>
              <option value="ELIMINAT">ELIMINAT (Purga certificada RGPD)</option>
            </select>
          </div>

          <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed font-sans">
            La transició a <strong>SUSPES_PAGAMENT</strong> invalida immediatament les sessions JWT dels operaris i impedeix noves connexions, conservant la integritat de les dades segons la clàusula Zero-Trust.
          </p>
        </div>

        {/* BLOC 2: LLICÈNCIA & QUOTA GUARD */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-purple-500" />
              <span>Pla de Llicència & Quota Guard</span>
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 font-bold border border-purple-200 dark:border-purple-800">
              PROTECTED
            </span>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">
              Pla Subscrit
            </label>
            <select
              value={pla}
              onChange={(e) => setPla(e.target.value)}
              className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-xs rounded-xl p-2.5 font-mono focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="STARTER">STARTER (Fins a 5 operaris actius)</option>
              <option value="PRO">PRO (Fins a 15 operaris actius)</option>
              <option value="ENTERPRISE">ENTERPRISE (Fins a 50 operaris actius)</option>
            </select>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 flex items-center justify-between text-xs font-mono">
            <span className="text-slate-500 dark:text-slate-400">Operaris actius actuals:</span>
            <span className="font-bold text-slate-900 dark:text-white">
              {tenant?.operaris_actius || 0} operaris
            </span>
          </div>

          <p className="text-[11px] text-amber-600 dark:text-amber-400 leading-relaxed font-sans">
            <strong>Quota Guard:</strong> El backend rebutjarà qualsevol intent de downgrade si el nombre d'operaris actius ({tenant?.operaris_actius || 0}) supera el límit del nou pla sol·licitat.
          </p>
        </div>

        {/* BLOC: DOMINI D'EMPRESA & CONFIGURACIÓ DNS CNAME */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm md:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <Globe className="w-4 h-4 text-emerald-500" />
              <span>Domini Propi de l'Empresa &amp; Subdomini (DNS CNAME)</span>
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 font-bold border border-emerald-200 dark:border-emerald-800">
              FQDN SOBIRÀ
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                Domini d'Accés de l'Empresa (FQDN Complet)
              </label>
              <div className="flex items-center rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 overflow-hidden focus-within:border-emerald-500">
                <span className="px-3 text-slate-400 font-mono text-[11px] bg-slate-100 dark:bg-slate-800/80 border-r border-slate-200 dark:border-slate-700 py-2.5">
                  https://
                </span>
                <input
                  type="text"
                  placeholder="ex. sevalor.soler.cat"
                  value={dominiCustom}
                  onChange={(e) => setDominiCustom(e.target.value.toLowerCase().trim())}
                  className="w-full bg-transparent p-2.5 text-slate-900 dark:text-white font-mono font-bold focus:outline-none"
                />
              </div>
              <span className="text-[10px] text-slate-500 mt-1 block">
                Exemple: <strong>sevalor.soler.cat</strong> (deixar buit si s'utilitza només subdomini de sevalor.app).
              </span>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                Slug / Subdomini Intern RLS (Base de Dades)
              </label>
              <input
                type="text"
                placeholder="ex. soler"
                value={subdomini}
                onChange={(e) => setSubdomini(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-xs rounded-xl p-2.5 font-mono focus:ring-emerald-500 focus:border-emerald-500"
              />
              <span className="text-[10px] text-slate-500 mt-1 block">
                Identificador únic d'inquilí emmagatzemat a <code>empreses.subdomini</code>.
              </span>
            </div>
          </div>

          {/* Guia CNAME */}
          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs font-mono space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-bold text-slate-700 dark:text-slate-300">
                Configuració CNAME requerida al DNS del client ({dominiCustom || "sevalor.soler.cat"}):
              </span>
              <span className="text-emerald-600 dark:text-emerald-400 font-bold">Let's Encrypt TLS-ALPN-01</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-[11px]">
              <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <span className="text-slate-400 text-[10px] block">Tipus</span>
                <span className="font-bold text-emerald-600">CNAME</span>
              </div>
              <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <span className="text-slate-400 text-[10px] block">Nom</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">
                  {dominiCustom ? dominiCustom.split(".")[0] : "sevalor"}
                </span>
              </div>
              <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <span className="text-slate-400 text-[10px] block">Destí (Target)</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">edge.sevalor.app</span>
              </div>
            </div>
          </div>
        </div>

        {/* BLOC 3: INTERRUPTORS DINÀMICS DE MÒDULS (FEATURE FLAGS) */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm md:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-500" />
              <span>Interruptors Dinàmics de Mòduls (Feature Flags per Tenant)</span>
            </h2>
            <span className="text-[10px] font-mono text-slate-400">
              Commutació en viu sense reinici de servei
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Copilot IA */}
            <label className="flex items-start gap-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors cursor-pointer">
              <input
                type="checkbox"
                checked={features.feature_copilot_ia}
                onChange={(e) =>
                  setFeatures({ ...features, feature_copilot_ia: e.target.checked })
                }
                className="w-4 h-4 mt-0.5 text-emerald-600 rounded border-slate-300 dark:border-slate-700 focus:ring-emerald-500"
              />
              <div>
                <div className="flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-blue-500" />
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    Copilot d'IA
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
                  Peritatge de fotos, memòries tècniques & OCR
                </p>
              </div>
            </label>

            {/* Flota Avançada */}
            <label className="flex items-start gap-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors cursor-pointer">
              <input
                type="checkbox"
                checked={features.feature_flota}
                onChange={(e) =>
                  setFeatures({ ...features, feature_flota: e.target.checked })
                }
                className="w-4 h-4 mt-0.5 text-emerald-600 rounded border-slate-300 dark:border-slate-700 focus:ring-emerald-500"
              />
              <div>
                <div className="flex items-center gap-1.5">
                  <Truck className="w-3.5 h-3.5 text-orange-500" />
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    Flota Avançada
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
                  Control d'ITVs, assegurances i geolocalització
                </p>
              </div>
            </label>

            {/* Plànols Tècnics */}
            <label className="flex items-start gap-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors cursor-pointer">
              <input
                type="checkbox"
                checked={features.feature_planols}
                onChange={(e) =>
                  setFeatures({ ...features, feature_planols: e.target.checked })
                }
                className="w-4 h-4 mt-0.5 text-emerald-600 rounded border-slate-300 dark:border-slate-700 focus:ring-emerald-500"
              />
              <div>
                <div className="flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-indigo-500" />
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    Plànols Tècnics
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
                  Visor vectorial de xarxes de reg & REBT
                </p>
              </div>
            </label>

            {/* Bot Telegram */}
            <label className="flex items-start gap-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors cursor-pointer">
              <input
                type="checkbox"
                checked={features.feature_telegram}
                onChange={(e) =>
                  setFeatures({ ...features, feature_telegram: e.target.checked })
                }
                className="w-4 h-4 mt-0.5 text-emerald-600 rounded border-slate-300 dark:border-slate-700 focus:ring-emerald-500"
              />
              <div>
                <div className="flex items-center gap-1.5">
                  <MessageSquare className="w-3.5 h-3.5 text-sky-500" />
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    Bot de Telegram
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
                  Canal directe d'incidències amb clients finals
                </p>
              </div>
            </label>
          </div>

          {/* CONFIGURACIÓ DE L'ORDINADOR DEDICAT D'IA SOBIRÀ (CONSTITUCIÓ §2.V) */}
          <div className="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-emerald-500" />
                <span>Ordinador Dedicat de la Seu (Constitució §2.V - Zero Cloud Egress)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-xs">
                <input
                  type="checkbox"
                  checked={features.node_ia_actiu}
                  onChange={(e) =>
                    setFeatures({ ...features, node_ia_actiu: e.target.checked })
                  }
                  className="w-4 h-4 text-emerald-600 rounded border-slate-300 dark:border-slate-700 focus:ring-emerald-500"
                />
                <span className="font-semibold text-slate-700 dark:text-slate-300">Activat</span>
              </label>
            </div>
            <div>
              <input
                type="text"
                placeholder="URL de l'ordinador dedicat (ex. https://ia.empresa.cat/v1)"
                value={features.node_ia_url}
                onChange={(e) =>
                  setFeatures({ ...features, node_ia_url: e.target.value.trim() })
                }
                className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-xs rounded-xl p-2.5 font-mono focus:ring-emerald-500 focus:border-emerald-500"
              />
              <p className="text-[10px] text-slate-400 mt-1">
                La IA mai s'executa a Hetzner. Aquesta URL apunta exclusivament a l'equip físic situat a la seu del client.
              </p>
            </div>
          </div>
        </div>

        {/* BLOC 4: ZONA DE PERILL & OFBOARDING RGPD */}
        <div className="bg-rose-50/60 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/60 p-5 rounded-2xl shadow-sm md:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-rose-700 dark:text-rose-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span>Zona de Perill • Baixa Certificada & Purga RGPD (Spec 04 US7)</span>
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-300 dark:border-rose-800 font-bold">
              IRREVERSIBLE
            </span>
          </div>

          <p className="text-xs text-rose-700 dark:text-rose-300 leading-relaxed">
            L'execució d'aquesta ordre marca el tenant com a <strong>ELIMINAT</strong>, genera un Certificat Oficial de Destrucció de Dades en format PDF signat criptogràficament i programa la purga irreversible de bases de dades i fitxers després d'un període de custòdia de 30 dies. El certificat es conserva durant 5 anys per compliment legal.
          </p>

          <div className="pt-2">
            <button
              onClick={handleDestroy}
              className="bg-rose-600 hover:bg-rose-700 text-white px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-colors shadow"
            >
              <PowerOff className="w-4 h-4" />
              <span>Executar Baixa Certificada (Offboarding RGPD)</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
