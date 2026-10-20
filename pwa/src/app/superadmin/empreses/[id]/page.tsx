"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
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
  Building2,
  Sparkles,
  Layers,
  Truck,
  MessageSquare,
  Globe,
  Cpu,
  Receipt,
  Plus,
  Trash2,
  ArchiveRestore,
  LifeBuoy,
  History,
  PauseCircle,
  Download,
  Edit3,
  Check,
  Wifi,
  WifiOff,
} from "lucide-react";
import { apiFetch, getAuthToken, setAuthToken } from "@/lib/api";

interface EquipIaItem {
  nom: string;
  unitats: number;
  preu_unitari: number;
}

export default function EmpresaDetailPage({ params }: { params: { id: string } }) {
  const [tenant, setTenant] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [certificatUrl, setCertificatUrl] = useState<string | null>(null);

  // Form states - Governança i Llicència
  const [estat, setEstat] = useState("ACTIU");
  const [pla, setPla] = useState("STARTER");
  const [quotaOperaris, setQuotaOperaris] = useState<number>(5);
  const [quotaBufferMb, setQuotaBufferMb] = useState<number>(500);
  const [motiuQuota, setMotiuQuota] = useState<string>("");
  const [dominiCustom, setDominiCustom] = useState("");
  const [subdomini, setSubdomini] = useState("");
  const [dnsCheckResult, setDnsCheckResult] = useState<any>(null);
  const [checkingDns, setCheckingDns] = useState(false);

  // Chameleon HSL
  const [primariHsl, setPrimariHsl] = useState("142 71% 25%");
  const [secundariHsl, setSecundariHsl] = useState("38 92% 50%");
  const [accentHsl, setAccentHsl] = useState("160 84% 39%");

  // Feature flags
  const [features, setFeatures] = useState({
    feature_copilot_ia: false,
    feature_flota: true,
    feature_planols: false,
    feature_telegram: true,
    node_ia_url: "",
    node_ia_actiu: false,
  });

  // CRM Condicions Comercials & Equips IA (Venda)
  const [tarifaLlicenciaBase, setTarifaLlicenciaBase] = useState<number>(0);
  const [tarifaPerOperari, setTarifaPerOperari] = useState<number>(0);
  const [tarifaConfigIa, setTarifaConfigIa] = useState<number>(0);
  const [equipsIaVenuts, setEquipsIaVenuts] = useState<EquipIaItem[]>([]);
  const [notesCrm, setNotesCrm] = useState<string>("");

  // Facturació B2B Veri*factu (HITL)
  const [factures, setFactures] = useState<any[]>([]);
  const [editingPrefacturaId, setEditingPrefacturaId] = useState<string | null>(null);
  const [periodeFacturacio, setPeriodeFacturacio] = useState<string>(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [incloureOnboarding, setIncloureOnboarding] = useState<boolean>(true);
  const [concepteOnboarding, setConcepteOnboarding] = useState<string>("Onboarding / Llicència SaaS Sevalor");
  const [importOnboarding, setImportOnboarding] = useState<number>(150);

  const [incloureConfigIa, setIncloureConfigIa] = useState<boolean>(false);
  const [concepteConfigIa, setConcepteConfigIa] = useState<string>("Configuració i Desplegament IA Local");
  const [importConfigIa, setImportConfigIa] = useState<number>(0);

  const [factEquipsIa, setFactEquipsIa] = useState<EquipIaItem[]>([]);

  const [incloureOperaris, setIncloureOperaris] = useState<boolean>(true);
  const [factNumOperaris, setFactNumOperaris] = useState<number>(5);
  const [factPreuPerOperari, setFactPreuPerOperari] = useState<number>(25);
  const [ivaPercent, setIvaPercent] = useState<number>(21);
  const [notesFactura, setNotesFactura] = useState<string>("");
  const [savingFactura, setSavingFactura] = useState<boolean>(false);

  // Tiquets de Suport CRM
  const [tiquets, setTiquets] = useState<any[]>([]);
  const [nouTiquetAssumpte, setNouTiquetAssumpte] = useState<string>("");
  const [nouTiquetDescripcio, setNouTiquetDescripcio] = useState<string>("");
  const [nouTiquetPrioritat, setNouTiquetPrioritat] = useState<string>("NORMAL");
  const [creatingTiquet, setCreatingTiquet] = useState<boolean>(false);

  const fetchTenantAll = async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const [data, factData, tiqData] = await Promise.all([
        apiFetch<any>(`/superadmin/tenants/${params.id}`),
        apiFetch<any[]>(`/superadmin/crm/factures?empresa_id=${params.id}`),
        apiFetch<any[]>(`/superadmin/crm/tiquets?empresa_id=${params.id}`),
      ]);

      if (data) {
        setTenant(data);
        setEstat(data.estat_pagament || data.estat || "ACTIU");
        setPla(data.pla_subscripcio || data.pla || "STARTER");
        setQuotaOperaris(Number(data.quota_operaris ?? 5));
        setQuotaBufferMb(Number(data.quota_buffer_mb ?? 500));
        setDominiCustom(data.domini_custom || "");
        setSubdomini(data.subdomini || "");
        if (data.primari_hsl) setPrimariHsl(data.primari_hsl);
        if (data.secundari_hsl) setSecundariHsl(data.secundari_hsl);
        if (data.accent_hsl) setAccentHsl(data.accent_hsl);
        setFeatures({
          feature_copilot_ia: Boolean(data.feature_copilot_ia),
          feature_flota: Boolean(data.feature_flota),
          feature_planols: Boolean(data.feature_planols),
          feature_telegram: Boolean(data.feature_telegram),
          node_ia_url: data.node_ia_url || "",
          node_ia_actiu: Boolean(data.node_ia_actiu),
        });

        // CRM fields
        const tBase = Number(data.tarifa_llicencia_base ?? 0);
        const tOp = Number(data.tarifa_per_operari ?? 0);
        const tIa = Number(data.tarifa_config_ia ?? 0);
        const eqVenuts = Array.isArray(data.equips_ia_venuts) ? data.equips_ia_venuts : [];

        setTarifaLlicenciaBase(tBase);
        setTarifaPerOperari(tOp);
        setTarifaConfigIa(tIa);
        setEquipsIaVenuts(eqVenuts);
        setNotesCrm(data.notes_crm || "");

        // Inicialitzar valors per defecte d'esborrany de prefactura amb les tarifes del client
        if (!editingPrefacturaId) {
          setImportOnboarding(tBase);
          setIncloureOnboarding(tBase > 0);
          setImportConfigIa(tIa);
          setIncloureConfigIa(tIa > 0);
          setFactNumOperaris(Number(data.quota_operaris ?? 5));
          setFactPreuPerOperari(tOp);
          setIncloureOperaris(tOp > 0);
        }
      }
      setFactures(Array.isArray(factData) ? factData : []);
      setTiquets(Array.isArray(tiqData) ? tiqData : []);
    } catch (err: any) {
      setErrorMessage(err.message || "Error al carregar el tenant.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenantAll();
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

      // 2. Guardar Quota d'Operaris, Pla i Buffer Diari
      if (
        pla !== tenant.pla_subscripcio ||
        quotaOperaris !== Number(tenant.quota_operaris) ||
        quotaBufferMb !== Number(tenant.quota_buffer_mb)
      ) {
        await apiFetch(`/superadmin/tenants/${params.id}/quota`, {
          method: "PUT",
          body: JSON.stringify({
            pla_subscripcio: pla,
            quota_operaris: quotaOperaris,
            quota_buffer_mb: quotaBufferMb,
            motiu: motiuQuota.trim() || "Actualització manual des de fitxa CRM Superadmin",
          }),
        });
      }

      // 3. Guardar Condicions Comercials CRM & Equips IA (Venda)
      await apiFetch(`/superadmin/tenants/${params.id}/crm`, {
        method: "PUT",
        body: JSON.stringify({
          tarifa_llicencia_base: tarifaLlicenciaBase,
          tarifa_per_operari: tarifaPerOperari,
          tarifa_config_ia: tarifaConfigIa,
          equips_ia_venuts: equipsIaVenuts,
          notes_crm: notesCrm,
          quota_buffer_mb: quotaBufferMb,
        }),
      });

      // 4. Guardar Feature Flags
      await apiFetch(`/superadmin/tenants/${params.id}/feature-flags`, {
        method: "PUT",
        body: JSON.stringify(features),
      });

      // 5. Guardar Domini / Subdomini si han canviat
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

      // 6. Guardar Marca Camaleó (Constitució §2.VIII)
      await apiFetch(`/superadmin/empreses/${params.id}/camaleo`, {
        method: "PUT",
        body: JSON.stringify({
          primari_hsl: primariHsl.trim(),
          secundari_hsl: secundariHsl.trim(),
          accent_hsl: accentHsl.trim(),
        }),
      });

      setSuccessMessage("Configuració del tenant, llicència d'operaris i condicions CRM desades a PostgreSQL.");
      fetchTenantAll();
    } catch (err: any) {
      setErrorMessage(err.message || "Error en desar els canvis del tenant.");
    } finally {
      setSaving(false);
    }
  };

  const handleCheckDns = async () => {
    const fqdnToTest = dominiCustom.trim() || `${subdomini.trim()}.sevalor.app`;
    if (!fqdnToTest) return;
    setCheckingDns(true);
    setDnsCheckResult(null);
    try {
      const res = await apiFetch<any>("/superadmin/tenants/verificar-dns", {
        method: "POST",
        body: JSON.stringify({ fqdn: fqdnToTest }),
      });
      setDnsCheckResult(res);
    } catch (e: any) {
      setDnsCheckResult({ resolt: false, detall: e.message || "Error de resolució DNS" });
    } finally {
      setCheckingDns(false);
    }
  };

  // Càlcul en viu de l'esborrany de prefactura
  const subtotalOnboarding = incloureOnboarding ? Number(importOnboarding || 0) : 0;
  const subtotalConfigIa = incloureConfigIa ? Number(importConfigIa || 0) : 0;
  const subtotalEquips = factEquipsIa.reduce(
    (acc, item) => acc + Number(item.unitats || 0) * Number(item.preu_unitari || 0),
    0
  );
  const subtotalOperaris = incloureOperaris
    ? Number(factNumOperaris || 0) * Number(factPreuPerOperari || 0)
    : 0;
  const baseImposableCalculada =
    subtotalOnboarding + subtotalConfigIa + subtotalEquips + subtotalOperaris;
  const ivaImportCalculat = +(baseImposableCalculada * (Number(ivaPercent || 0) / 100)).toFixed(2);
  const totalFacturaCalculat = +(baseImposableCalculada + ivaImportCalculat).toFixed(2);

  const handleSavePrefactura = async () => {
    setSavingFactura(true);
    setErrorMessage(null);
    try {
      const payload = {
        empresa_id: params.id,
        periode_facturacio: periodeFacturacio,
        concepte_onboarding: incloureOnboarding ? concepteOnboarding : null,
        import_onboarding: subtotalOnboarding,
        concepte_config_ia: incloureConfigIa ? concepteConfigIa : null,
        import_config_ia: subtotalConfigIa,
        equips_ia_detall: factEquipsIa.map((eq) => ({
          nom: eq.nom,
          unitats: Number(eq.unitats),
          preu_unitari: Number(eq.preu_unitari),
          modalitat: "VENDA",
        })),
        num_operaris: incloureOperaris ? Number(factNumOperaris) : 0,
        preu_per_operari: incloureOperaris ? Number(factPreuPerOperari) : 0,
        iva_percent: Number(ivaPercent),
        notes: notesFactura || null,
      };

      if (editingPrefacturaId) {
        await apiFetch(`/superadmin/crm/prefactures/${editingPrefacturaId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        setSuccessMessage("Esborrany de prefactura actualitzat. Pendent de verificació humana (HITL).");
      } else {
        await apiFetch("/superadmin/crm/prefactures", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setSuccessMessage("Esborrany de prefactura creat (NO FINAL). Revisa'l i prem 'Verificar i Facturar' per emetre'l a Veri*factu.");
      }
      setEditingPrefacturaId(null);
      fetchTenantAll();
    } catch (e: any) {
      setErrorMessage(e.message || "Error en desar l'esborrany de prefactura.");
    } finally {
      setSavingFactura(false);
    }
  };

  const handleLoadPrefacturaToEdit = (f: any) => {
    setEditingPrefacturaId(f.id);
    setPeriodeFacturacio(f.periode_facturacio || "2026-10");
    setIncloureOnboarding(Number(f.import_onboarding) > 0 || Boolean(f.concepte_onboarding));
    setConcepteOnboarding(f.concepte_onboarding || "Onboarding / Llicència SaaS Sevalor");
    setImportOnboarding(Number(f.import_onboarding || 0));

    setIncloureConfigIa(Number(f.import_config_ia) > 0 || Boolean(f.concepte_config_ia));
    setConcepteConfigIa(f.concepte_config_ia || "Configuració i Desplegament IA Local");
    setImportConfigIa(Number(f.import_config_ia || 0));

    setFactEquipsIa(Array.isArray(f.equips_ia_detall) ? f.equips_ia_detall : []);
    setIncloureOperaris(Number(f.num_operaris) > 0 || Number(f.preu_per_operari) > 0);
    setFactNumOperaris(Number(f.num_operaris || 0));
    setFactPreuPerOperari(Number(f.preu_per_operari || 0));
    setIvaPercent(Number(f.iva_percent || 21));
    setNotesFactura(f.notes || "");
  };

  const handleVerificarIEmetreVerifactu = async (prefactura: any) => {
    const ok = confirm(
      `VERIFICACIÓ HUMANA OBLIGATÒRIA (HITL - Veri*factu):\n\n` +
        `Estàs a punt de verificar i emetre definitivament la factura per a "${tenant?.nom}" (${prefactura.periode_facturacio}) per un total de ${Number(prefactura.total_factura).toFixed(2)} €.\n\n` +
        `Un cop emesa, es signarà amb cadena SHA-256 Veri*factu i serà IMMUTABLE.\nVols confirmar l'emissió?`
    );
    if (!ok) return;

    try {
      await apiFetch(`/superadmin/crm/prefactures/${prefactura.id}/verificar-i-emetre`, {
        method: "POST",
      });
      setSuccessMessage("Factura verificada per humà i emesa amb segell criptogràfic Veri*factu!");
      fetchTenantAll();
    } catch (e: any) {
      setErrorMessage(e.message || "Error en emetre la factura Veri*factu.");
    }
  };

  const handleCanviarEstatCobrament = async (facturaId: string, estatCobrament: string, passarAHibernant: boolean) => {
    try {
      await apiFetch(`/superadmin/crm/factures/${facturaId}/estat-cobrament`, {
        method: "PATCH",
        body: JSON.stringify({
          estat_cobrament: estatCobrament,
          passar_a_hibernant: passarAHibernant,
        }),
      });
      setSuccessMessage(
        passarAHibernant
          ? "Factura marcada com a IMPAGADA i empresa passada a estat HIBERNANT."
          : `Estat de cobrament actualitzat a ${estatCobrament}.`
      );
      fetchTenantAll();
    } catch (e: any) {
      setErrorMessage(e.message || "Error actualitzant cobrament.");
    }
  };

  const handleDownloadFacturaPdf = async (facturaId: string, numFactura: string) => {
    try {
      const token = getAuthToken();
      const res = await fetch(`/api/v1/superadmin/crm/factures/${facturaId}/pdf`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("No s'ha pogut descarregar el PDF Veri*factu");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Factura_Verifactu_${numFactura || facturaId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e.message || "Error en descarregar PDF");
    }
  };

  const handleCrearTiquet = async () => {
    if (!nouTiquetAssumpte.trim() || !nouTiquetDescripcio.trim()) return;
    setCreatingTiquet(true);
    setErrorMessage(null);
    try {
      const res = await apiFetch<any>("/superadmin/crm/tiquets", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: params.id,
          assumpte: nouTiquetAssumpte.trim(),
          descripcio: nouTiquetDescripcio.trim(),
          prioritat: nouTiquetPrioritat,
        }),
      });
      setNouTiquetAssumpte("");
      setNouTiquetDescripcio("");
      if (res?.diagnostic_node?.advertencia) {
        setSuccessMessage(`Tiquet creat. Autodiagnòstic: ${res.diagnostic_node.advertencia}`);
      } else {
        setSuccessMessage("Tiquet d'incidència registrat al CRM.");
      }
      fetchTenantAll();
    } catch (e: any) {
      setErrorMessage(e.message || "Error en obrir el tiquet.");
    } finally {
      setCreatingTiquet(false);
    }
  };

  const handleTancarTiquet = async (tiquetId: string) => {
    const resolucio = prompt("Descriu la resolució de la incidència per a l'historial d'auditoria:");
    if (resolucio === null) return;
    try {
      await apiFetch(`/superadmin/crm/tiquets/${tiquetId}`, {
        method: "PATCH",
        body: JSON.stringify({ estat: "RESOLT", resolucio: resolucio || "Resolt per Suport Superadmin" }),
      });
      fetchTenantAll();
    } catch (e: any) {
      setErrorMessage(e.message || "Error en tancar el tiquet.");
    }
  };

  const handleDownloadFullDataZip = async () => {
    try {
      const token = getAuthToken();
      const res = await fetch(`/api/v1/superadmin/tenants/${params.id}/recuperar-dades`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Error generant l'arxiu ZIP de recuperació de dades");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `SEVALOR_EXPORT_${tenant?.subdomini || params.id}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e.message || "Error descarregant les dades de l'empresa.");
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
        localStorage.setItem(
          "sevalor_user",
          JSON.stringify({
            ...data,
            is_impersonation: true,
            empresa_id: params.id,
            rol: "SUPERADMIN",
          })
        );
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
        `Es generarà un certificat de destrucció criptogràfic (RGPD) i s'establirà una custòdia de 30 dies abans de la purga d'operativa.\n` +
        `Les factures B2B Veri*factu i els tiquets de suport es conservaran al CRM per obligació fiscal i traçabilitat.\n` +
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
      fetchTenantAll();
    } catch (e: any) {
      alert("Error en l'offboarding: " + (e.message || "Desconegut"));
    }
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-xs font-mono text-slate-400">
        Carregant fitxa CRM, facturació Veri*factu i tiquets del tenant des de PostgreSQL...
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
          <ArrowLeft className="w-3.5 h-3.5" /> Tornar al CRM de Clients
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-8 space-y-6 w-full">
      {/* NAVEGACIÓ ENRERE */}
      <Link
        href="/superadmin/empreses"
        className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Tornar al CRM de Clients i Llicències</span>
      </Link>

      {/* CAPÇALERA DE GOVERNANÇA CRM */}
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

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleDownloadFullDataZip}
            className="px-3 py-2 rounded-xl bg-blue-50 hover:bg-blue-100 dark:bg-blue-950/60 dark:hover:bg-blue-900/60 text-blue-700 dark:text-blue-300 text-xs font-mono font-bold flex items-center gap-1.5 border border-blue-200 dark:border-blue-800 transition-colors shadow-sm"
            title="Recuperar i exportar totes les dades de l'empresa en ZIP"
          >
            <ArchiveRestore className="w-3.5 h-3.5" />
            <span>Recuperar Dades (.zip)</span>
          </button>

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
            <span>{saving ? "Desant a PostgreSQL..." : "Desar Canvis CRM"}</span>
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

      {/* SECCIÓ 1: CICLE DE VIDA CRM (AMB ESTAT HIBERNANT) I QUOTA D'OPERARIS VARIABLE */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* BLOC 1: CICLE DE VIDA SAAS */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-500" />
              <span>Cicle de Vida CRM SaaS (Inclou Hibernació)</span>
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-bold">
              ZERO-TRUST GUARD
            </span>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">
              Estat del Client al CRM
            </label>
            <select
              value={estat}
              onChange={(e) => setEstat(e.target.value)}
              className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-xs rounded-xl p-2.5 font-mono focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="PROSPECTE">PROSPECTE (En negociació comercial)</option>
              <option value="TRIAL">TRIAL (Període de prova 14 dies)</option>
              <option value="ACTIU">ACTIU (Subscripció al corrent de pagament)</option>
              <option value="HIBERNANT">HIBERNANT (Període de gràcia per impagament — Accés pausat sense baixa)</option>
              <option value="SUSPES_PAGAMENT">SUSPÈS (Bloqueig estricte per impagament)</option>
              <option value="MANTENIMENT">MANTENIMENT (Accés temporalment restringit)</option>
              <option value="BAIXA_OFFBOARDING">BAIXA_OFFBOARDING (En període de custòdia 30 dies)</option>
              <option value="ELIMINAT">ELIMINAT (Purga certificada RGPD)</option>
            </select>
          </div>

          <div className="p-3 rounded-xl bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/70 text-[11px] text-amber-800 dark:text-amber-300 leading-relaxed">
            <strong>Opció HIBERNANT:</strong> Quan hi ha un impagament, en lloc de donar de baixa l'empresa immediatament, pots passar-la a <code>HIBERNANT</code> durant uns dies. Es congela l'accés dels operaris i enginyers però es preserven intactes totes les dades i configuracions per a una reactivació immediata.
          </div>
        </div>

        {/* BLOC 2: QUOTA D'OPERARIS PER LLICÈNCIA (DINÀMICA) & BUFFER DIARI */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <Users className="w-4 h-4 text-purple-500" />
              <span>Llicència d'Operaris Variable & Buffer Diari</span>
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 font-bold border border-purple-200 dark:border-purple-800">
              QUOTA GUARD ACTIU
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                Número d'Operaris Assignats
              </label>
              <input
                type="number"
                min={Math.max(1, Number(tenant?.operaris_actius || 1))}
                max={500}
                value={quotaOperaris}
                onChange={(e) => setQuotaOperaris(Math.max(1, Number(e.target.value)))}
                className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-xl p-2 font-mono font-bold"
              />
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Actius actuals: <strong>{tenant?.operaris_actius || 0}</strong>
              </span>
            </div>

            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                Tier Referència
              </label>
              <select
                value={pla}
                onChange={(e) => setPla(e.target.value)}
                className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-xl p-2 font-mono"
              >
                <option value="STARTER">STARTER</option>
                <option value="PRO">PRO</option>
                <option value="ENTERPRISE">ENTERPRISE</option>
              </select>
            </div>

            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                Buffer Diari Hetzner (MB)
              </label>
              <input
                type="number"
                min={100}
                max={10240}
                value={quotaBufferMb}
                onChange={(e) => setQuotaBufferMb(Math.max(100, Number(e.target.value)))}
                className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-xl p-2 font-mono font-bold"
              />
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Ús avui: <strong>{tenant?.buffer_utilitzat_mb || 0} MB</strong>
              </span>
            </div>
          </div>

          <div>
            <input
              type="text"
              placeholder="Motiu del canvi de quota d'operaris (ex. Campanya d'estiu +4 operaris)"
              value={motiuQuota}
              onChange={(e) => setMotiuQuota(e.target.value)}
              className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-xs rounded-xl p-2 font-mono"
            />
          </div>

          {Array.isArray(tenant?.historial_llicencia) && tenant.historial_llicencia.length > 0 && (
            <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-[10px] font-mono space-y-1 max-h-24 overflow-y-auto">
              <div className="font-bold text-slate-500 flex items-center gap-1">
                <History className="w-3 h-3" /> Historial d'Ampliacions / Reduccions d'Operaris:
              </div>
              {tenant.historial_llicencia.map((h: any) => (
                <div key={h.id} className="flex justify-between text-slate-600 dark:text-slate-300">
                  <span>
                    {h.operaris_anteriors} → <strong>{h.operaris_nous} operaris</strong> ({h.motiu || "Ajust"})
                  </span>
                  <span className="text-slate-400">{h.creat_a ? new Date(h.creat_a).toLocaleDateString() : ""}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* SECCIÓ 2: CONDICIONS COMERCIALS CRM & EQUIPS IA (VENDA — MAI RÈNTING) */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
          <div>
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
              <Building2 className="w-4 h-4 text-emerald-500" />
              <span>Condicions Comercials CRM & Inventari d'Equips IA Venuts (Només Venda, Opcional)</span>
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Tarifes editables per a aquest client. Els equips IA mai són de rènting: només venda directa i 100% editables (PC, Side, servidor local, etc.).
            </p>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 font-bold">
            EQUIPS IA: NOMÉS VENDA (0% RÈNTING)
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Tarifa Onboarding / Llicència Base (€)
            </label>
            <input
              type="number"
              step="0.01"
              value={tarifaLlicenciaBase}
              onChange={(e) => setTarifaLlicenciaBase(Number(e.target.value))}
              className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl p-2.5 font-mono font-bold"
            />
          </div>
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Preu per Operari Assignat (€ / operari)
            </label>
            <input
              type="number"
              step="0.01"
              value={tarifaPerOperari}
              onChange={(e) => setTarifaPerOperari(Number(e.target.value))}
              className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl p-2.5 font-mono font-bold"
            />
          </div>
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Tarifa Configuració IA (€)
            </label>
            <input
              type="number"
              step="0.01"
              value={tarifaConfigIa}
              onChange={(e) => setTarifaConfigIa(Number(e.target.value))}
              className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl p-2.5 font-mono font-bold"
            />
          </div>
        </div>

        {/* Llista editable d'Equips IA venuts a l'empresa */}
        <div className="space-y-2 pt-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
              Equips IA Venuts al Client (Opcional — Editable: PC, Side, MiniPC, etc.)
            </label>
            <button
              type="button"
              onClick={() =>
                setEquipsIaVenuts([...equipsIaVenuts, { nom: "PC Dedicat IA / Side", unitats: 1, preu_unitari: 850 }])
              }
              className="px-2.5 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-950 dark:hover:bg-emerald-900 text-emerald-700 dark:text-emerald-300 text-xs font-mono font-bold flex items-center gap-1 border border-emerald-200 dark:border-emerald-800"
            >
              <Plus className="w-3.5 h-3.5" /> Afegir Equip (Venda)
            </button>
          </div>

          {equipsIaVenuts.length === 0 ? (
            <p className="text-xs font-mono text-slate-400 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-dashed border-slate-200 dark:border-slate-800">
              Cap equip físic d'IA registrat en venda per a aquesta empresa (camp opcional).
            </p>
          ) : (
            <div className="space-y-2">
              {equipsIaVenuts.map((item, idx) => (
                <div key={idx} className="grid grid-cols-1 sm:grid-cols-12 gap-2 items-center bg-slate-50 dark:bg-slate-800/50 p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 text-xs font-mono">
                  <div className="sm:col-span-6">
                    <input
                      type="text"
                      placeholder="Descripció de l'equip (ex. PC IA Local, Side, NAS...)"
                      value={item.nom}
                      onChange={(e) => {
                        const copy = [...equipsIaVenuts];
                        copy[idx].nom = e.target.value;
                        setEquipsIaVenuts(copy);
                      }}
                      className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <input
                      type="number"
                      min={1}
                      placeholder="Unitats"
                      value={item.unitats}
                      onChange={(e) => {
                        const copy = [...equipsIaVenuts];
                        copy[idx].unitats = Number(e.target.value);
                        setEquipsIaVenuts(copy);
                      }}
                      className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 text-center"
                    />
                  </div>
                  <div className="sm:col-span-3">
                    <input
                      type="number"
                      step="0.01"
                      placeholder="Preu unitari (€)"
                      value={item.preu_unitari}
                      onChange={(e) => {
                        const copy = [...equipsIaVenuts];
                        copy[idx].preu_unitari = Number(e.target.value);
                        setEquipsIaVenuts(copy);
                      }}
                      className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 text-right"
                    />
                  </div>
                  <div className="sm:col-span-1 flex justify-end">
                    <button
                      type="button"
                      onClick={() => setEquipsIaVenuts(equipsIaVenuts.filter((_, i) => i !== idx))}
                      className="p-1.5 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950 rounded-lg"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Notes Comercials i Acords CRM
          </label>
          <textarea
            rows={2}
            value={notesCrm}
            onChange={(e) => setNotesCrm(e.target.value)}
            placeholder="Anotacions de seguiment comercial, acords de facturació o contactes administratius..."
            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl p-2.5 text-xs font-mono"
          />
        </div>
      </div>

      {/* SECCIÓ 3: FACTURACIÓ B2B VERI*FACTU AMB HUMAN-IN-THE-LOOP (HITL OBLIGATORI) */}
      <div className="bg-white dark:bg-slate-900 border-2 border-emerald-600/40 dark:border-emerald-700/50 p-6 rounded-2xl shadow-sm space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
          <div>
            <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-900 dark:text-white flex items-center gap-2">
              <Receipt className="w-4 h-4 text-emerald-500" />
              <span>Facturació SaaS B2B Veri*factu (Human-in-the-Loop Obligatori)</span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              El sistema mai genera cap factura final sense verificació humana. Primer es crea una <strong>Prefactura (Esborrany Editable)</strong> i només s'emet a Veri*factu quan un humà la verifica.
            </p>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded bg-amber-50 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800 font-bold">
            MAN-IN-THE-LOOP VERI*FACTU RD 1007/2023
          </span>
        </div>

        {/* Formulari d'Esborrany de Prefactura (4 Conceptes Editables i Opcionals) */}
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-xs font-mono font-bold uppercase text-slate-700 dark:text-slate-200">
              {editingPrefacturaId ? `Editant Esborrany de Prefactura #${editingPrefacturaId.slice(0, 8)}` : "1. Preparar Esborrany de Prefactura (No Final)"}
            </h3>
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="text-slate-500">Període:</span>
              <input
                type="text"
                value={periodeFacturacio}
                onChange={(e) => setPeriodeFacturacio(e.target.value)}
                placeholder="YYYY-MM"
                className="w-28 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 text-center font-bold"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            {/* Concepte 1: Onboarding / Llicència */}
            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
              <label className="flex items-center justify-between font-bold text-slate-800 dark:text-slate-200 cursor-pointer">
                <span className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={incloureOnboarding}
                    onChange={(e) => setIncloureOnboarding(e.target.checked)}
                    className="w-4 h-4 accent-emerald-600 rounded"
                  />
                  <span>1. Onboarding / Llicència (Opcional)</span>
                </span>
                <span className="font-mono text-emerald-600">{subtotalOnboarding.toFixed(2)} €</span>
              </label>
              {incloureOnboarding && (
                <div className="grid grid-cols-3 gap-2 pt-1">
                  <input
                    type="text"
                    value={concepteOnboarding}
                    onChange={(e) => setConcepteOnboarding(e.target.value)}
                    className="col-span-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 font-mono"
                  />
                  <input
                    type="number"
                    step="0.01"
                    value={importOnboarding}
                    onChange={(e) => setImportOnboarding(Number(e.target.value))}
                    className="bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 font-mono text-right font-bold"
                  />
                </div>
              )}
            </div>

            {/* Concepte 2: Configuració IA */}
            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
              <label className="flex items-center justify-between font-bold text-slate-800 dark:text-slate-200 cursor-pointer">
                <span className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={incloureConfigIa}
                    onChange={(e) => setIncloureConfigIa(e.target.checked)}
                    className="w-4 h-4 accent-emerald-600 rounded"
                  />
                  <span>2. Configuració IA (Opcional)</span>
                </span>
                <span className="font-mono text-emerald-600">{subtotalConfigIa.toFixed(2)} €</span>
              </label>
              {incloureConfigIa && (
                <div className="grid grid-cols-3 gap-2 pt-1">
                  <input
                    type="text"
                    value={concepteConfigIa}
                    onChange={(e) => setConcepteConfigIa(e.target.value)}
                    className="col-span-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 font-mono"
                  />
                  <input
                    type="number"
                    step="0.01"
                    value={importConfigIa}
                    onChange={(e) => setImportConfigIa(Number(e.target.value))}
                    className="bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 font-mono text-right font-bold"
                  />
                </div>
              )}
            </div>

            {/* Concepte 3: Equips IA (Venda — Mai Rènting, Múltiples Equips) */}
            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2 md:col-span-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-800 dark:text-slate-200">
                  3. Equips IA — Només Venda, Opcional (PC, Side, Servidor, etc.)
                </span>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-emerald-600">{subtotalEquips.toFixed(2)} €</span>
                  <button
                    type="button"
                    onClick={() =>
                      setFactEquipsIa([...factEquipsIa, { nom: "PC IA Dedicat / Side", unitats: 1, preu_unitari: 850 }])
                    }
                    className="px-2 py-1 rounded bg-emerald-600 text-white text-[11px] font-mono font-bold flex items-center gap-1"
                  >
                    <Plus className="w-3 h-3" /> Afegir Equip a Factura
                  </button>
                </div>
              </div>
              {factEquipsIa.length > 0 && (
                <div className="space-y-2 pt-1">
                  {factEquipsIa.map((eq, i) => (
                    <div key={i} className="grid grid-cols-12 gap-2 items-center font-mono">
                      <input
                        type="text"
                        value={eq.nom}
                        onChange={(e) => {
                          const c = [...factEquipsIa];
                          c[i].nom = e.target.value;
                          setFactEquipsIa(c);
                        }}
                        placeholder="Nom equip (ex. PC IA, Side...)"
                        className="col-span-6 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5"
                      />
                      <input
                        type="number"
                        min={1}
                        value={eq.unitats}
                        onChange={(e) => {
                          const c = [...factEquipsIa];
                          c[i].unitats = Number(e.target.value);
                          setFactEquipsIa(c);
                        }}
                        className="col-span-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 text-center"
                      />
                      <input
                        type="number"
                        step="0.01"
                        value={eq.preu_unitari}
                        onChange={(e) => {
                          const c = [...factEquipsIa];
                          c[i].preu_unitari = Number(e.target.value);
                          setFactEquipsIa(c);
                        }}
                        className="col-span-3 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 text-right"
                      />
                      <button
                        type="button"
                        onClick={() => setFactEquipsIa(factEquipsIa.filter((_, idx) => idx !== i))}
                        className="col-span-1 text-rose-500 flex justify-center"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Concepte 4: Operaris per Llicència */}
            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2 md:col-span-2">
              <label className="flex items-center justify-between font-bold text-slate-800 dark:text-slate-200 cursor-pointer">
                <span className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={incloureOperaris}
                    onChange={(e) => setIncloureOperaris(e.target.checked)}
                    className="w-4 h-4 accent-emerald-600 rounded"
                  />
                  <span>4. Operaris per Llicència (Opcional — Variable amb el temps)</span>
                </span>
                <span className="font-mono text-emerald-600">{subtotalOperaris.toFixed(2)} €</span>
              </label>
              {incloureOperaris && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1 font-mono">
                  <div>
                    <span className="text-[10px] text-slate-400 block">Núm. Operaris Facturats</span>
                    <input
                      type="number"
                      min={0}
                      value={factNumOperaris}
                      onChange={(e) => setFactNumOperaris(Number(e.target.value))}
                      className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 font-bold"
                    />
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">Preu per Operari (€)</span>
                    <input
                      type="number"
                      step="0.01"
                      value={factPreuPerOperari}
                      onChange={(e) => setFactPreuPerOperari(Number(e.target.value))}
                      className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 font-bold"
                    />
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">IVA (%)</span>
                    <input
                      type="number"
                      step="0.1"
                      value={ivaPercent}
                      onChange={(e) => setIvaPercent(Number(e.target.value))}
                      className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 font-bold"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-slate-200 dark:border-slate-700 font-mono text-xs">
            <div>
              <span>Base: <strong>{baseImposableCalculada.toFixed(2)} €</strong></span>
              <span className="mx-2">•</span>
              <span>IVA ({ivaPercent}%): <strong>{ivaImportCalculat.toFixed(2)} €</strong></span>
              <span className="mx-2">•</span>
              <span className="text-sm font-black text-emerald-600 dark:text-emerald-400">
                TOTAL PREFACTURA: {totalFacturaCalculat.toFixed(2)} €
              </span>
            </div>

            <div className="flex items-center gap-2">
              {editingPrefacturaId && (
                <button
                  type="button"
                  onClick={() => setEditingPrefacturaId(null)}
                  className="px-3 py-1.5 rounded-lg bg-slate-200 dark:bg-slate-700 text-xs font-bold"
                >
                  Cancel·lar Edició
                </button>
              )}
              <button
                type="button"
                disabled={savingFactura}
                onClick={handleSavePrefactura}
                className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 dark:bg-emerald-600 dark:hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-1.5 shadow"
              >
                <Save className="w-3.5 h-3.5" />
                <span>{editingPrefacturaId ? "Actualitzar Esborrany Prefactura" : "Desar Prefactura (Pendent d'Humà)"}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Taula d'Esborranys i Factures Veri*factu Emeses */}
        <div className="space-y-2">
          <h3 className="text-xs font-mono font-bold uppercase text-slate-600 dark:text-slate-400">
            2. Registre de Prefactures i Factures Veri*factu del Client ({factures.length})
          </h3>
          {factures.length === 0 ? (
            <div className="p-6 text-center text-xs font-mono text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
              Cap prefactura ni factura registrada per a aquesta empresa.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-xs font-mono border-collapse">
                <thead>
                  <tr className="bg-slate-100 dark:bg-slate-800 text-[10px] uppercase text-slate-500">
                    <th className="p-3">Núm / Període</th>
                    <th className="p-3">Estat Document</th>
                    <th className="p-3 text-right">Total</th>
                    <th className="p-3 text-center">Cobrament</th>
                    <th className="p-3 text-right">Acció Humana (HITL) / PDF</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {factures.map((f) => (
                    <tr key={f.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="p-3">
                        <div className="font-bold text-slate-900 dark:text-white">
                          {f.numero_factura || "ESBORRANY (SENSE NÚM.)"}
                        </div>
                        <div className="text-[10px] text-slate-500">Període: {f.periode_facturacio}</div>
                      </td>
                      <td className="p-3">
                        {f.estat === "ESBORRANY_PREFACTURA" ? (
                          <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 text-[10px] font-bold">
                            PREFACTURA NO FINAL (PENDENT D'HUMÀ)
                          </span>
                        ) : (
                          <div>
                            <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-[10px] font-bold">
                              EMESA VERI*FACTU
                            </span>
                            <div className="text-[9px] text-slate-400 mt-0.5">
                              SHA256: {f.hash_actual ? `${f.hash_actual.slice(0, 14)}...` : "—"}
                            </div>
                          </div>
                        )}
                      </td>
                      <td className="p-3 text-right font-bold text-slate-900 dark:text-white">
                        {Number(f.total_factura || 0).toFixed(2)} €
                      </td>
                      <td className="p-3 text-center">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            f.estat_cobrament === "COBRADA"
                              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                              : f.estat_cobrament === "IMPAGADA"
                              ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                              : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                          }`}
                        >
                          {f.estat_cobrament}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {f.estat === "ESBORRANY_PREFACTURA" ? (
                            <>
                              <button
                                onClick={() => handleLoadPrefacturaToEdit(f)}
                                className="px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-[10px] font-bold flex items-center gap-1"
                              >
                                <Edit3 className="w-3 h-3" /> Editar
                              </button>
                              <button
                                onClick={() => handleVerificarIEmetreVerifactu(f)}
                                className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold flex items-center gap-1 shadow-sm"
                              >
                                <Check className="w-3 h-3" /> Verificar i Facturar (Veri*factu)
                              </button>
                            </>
                          ) : (
                            <>
                              {f.estat_cobrament !== "COBRADA" && (
                                <button
                                  onClick={() => handleCanviarEstatCobrament(f.id, "COBRADA", false)}
                                  className="px-2 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-300 text-[10px] font-bold"
                                >
                                  Marcar Cobrada
                                </button>
                              )}
                              {f.estat_cobrament !== "IMPAGADA" && (
                                <button
                                  onClick={() => handleCanviarEstatCobrament(f.id, "IMPAGADA", true)}
                                  className="px-2 py-1 rounded bg-amber-50 text-amber-800 border border-amber-300 text-[10px] font-bold flex items-center gap-1"
                                  title="Marca la factura com a impagada i passa l'empresa a estat HIBERNANT"
                                >
                                  <PauseCircle className="w-3 h-3" /> Impagada → Hibernar
                                </button>
                              )}
                              <button
                                onClick={() => handleDownloadFacturaPdf(f.id, f.numero_factura)}
                                className="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white text-[10px] font-bold flex items-center gap-1"
                              >
                                <Download className="w-3 h-3" /> PDF Veri*factu
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* SECCIÓ 4: TIQUETS D'INCIDÈNCIA CRM AMB AUTODIAGNÒSTIC DE PC LOCAL APAGAT */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
          <div>
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
              <LifeBuoy className="w-4 h-4 text-blue-500" />
              <span>Tiquets d'Incidència CRM & Autodiagnòstic de l'Ordinador del Client</span>
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              En obrir un tiquet, el sistema comprova automàticament si l'ordinador central del client (<code>node_ia_url</code>) està apagat per advertir-ne immediatament. Es conserven permanentment per a auditoria.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 text-xs">
          <input
            type="text"
            placeholder="Assumpte de la incidència (ex. Operari no pot obrir plànol antic de caldera)"
            value={nouTiquetAssumpte}
            onChange={(e) => setNouTiquetAssumpte(e.target.value)}
            className="md:col-span-4 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl p-2.5 font-mono"
          />
          <input
            type="text"
            placeholder="Descripció detallada..."
            value={nouTiquetDescripcio}
            onChange={(e) => setNouTiquetDescripcio(e.target.value)}
            className="md:col-span-4 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl p-2.5 font-mono"
          />
          <select
            value={nouTiquetPrioritat}
            onChange={(e) => setNouTiquetPrioritat(e.target.value)}
            className="md:col-span-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl p-2.5 font-mono"
          >
            <option value="BAIXA">Prioritat BAIXA</option>
            <option value="NORMAL">Prioritat NORMAL</option>
            <option value="ALTA">Prioritat ALTA</option>
            <option value="CRITICA">Prioritat CRÍTICA</option>
          </select>
          <button
            type="button"
            disabled={creatingTiquet}
            onClick={handleCrearTiquet}
            className="md:col-span-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl p-2.5 font-mono font-bold flex items-center justify-center gap-1"
          >
            <Plus className="w-4 h-4" /> Obrir Tiquet
          </button>
        </div>

        {tiquets.length > 0 && (
          <div className="space-y-2 pt-2">
            {tiquets.map((t) => (
              <div
                key={t.id}
                className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 flex flex-wrap items-center justify-between gap-3 text-xs font-mono"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-slate-900 dark:text-white">{t.assumpte}</span>
                    <span className="px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-[10px] font-bold">
                      {t.estat} • {t.prioritat}
                    </span>
                    {t.pc_empresa_online_al_crear === false ? (
                      <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-300 text-[10px] font-bold flex items-center gap-1">
                        <WifiOff className="w-3 h-3" /> ADVERTÈNCIA: Ordinador del client APAGAT en obrir el tiquet
                      </span>
                    ) : t.pc_empresa_online_al_crear === true ? (
                      <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-[10px] font-bold flex items-center gap-1">
                        <Wifi className="w-3 h-3" /> PC del client ONLINE
                      </span>
                    ) : null}
                  </div>
                  <p className="text-[11px] text-slate-600 dark:text-slate-300 font-sans">{t.descripcio}</p>
                  {t.resolucio && (
                    <p className="text-[11px] text-emerald-700 dark:text-emerald-400">
                      Resolució: {t.resolucio}
                    </p>
                  )}
                </div>

                {t.estat !== "RESOLT" && (
                  <button
                    onClick={() => handleTancarTiquet(t.id)}
                    className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold"
                  >
                    Marcar Resolt
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* SECCIÓ 5: DOMINI D'EMPRESA & VERIFICACIÓ DNS EN VIU */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm md:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <Globe className="w-4 h-4 text-emerald-500" />
              <span>Domini Propi de l'Empresa &amp; Verificació Real de Redirecció DNS</span>
            </h2>
            <button
              type="button"
              onClick={handleCheckDns}
              disabled={checkingDns}
              className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold transition-colors"
            >
              {checkingDns ? "Comprovant DNS..." : "Verificar Redirecció DNS en Viu"}
            </button>
          </div>

          {dnsCheckResult && (
            <div
              className={`p-3 rounded-xl border text-xs font-mono ${
                dnsCheckResult.resolt
                  ? "bg-emerald-50 dark:bg-emerald-950/60 border-emerald-300 text-emerald-800 dark:text-emerald-200"
                  : "bg-amber-50 dark:bg-amber-950/60 border-amber-300 text-amber-800 dark:text-amber-200"
              }`}
            >
              <strong>Resultat Sonda DNS ({dnsCheckResult.fqdn}):</strong> {dnsCheckResult.detall}
              {Array.isArray(dnsCheckResult.ips_detectades) && dnsCheckResult.ips_detectades.length > 0 && (
                <span> • IPs: {dnsCheckResult.ips_detectades.join(", ")}</span>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                Domini d'Accés de l'Empresa (FQDN Complet)
              </label>
              <div className="flex items-center rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 overflow-hidden">
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
                className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-xs rounded-xl p-2.5 font-mono"
              />
            </div>
          </div>
        </div>

        {/* BLOC: IDENTITAT CORPORATIVA CAMALEÒNICA (CONSTITUCIÓ §2.VIII) */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm md:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-500" />
              <span>Identitat de Marca &amp; Tokens Camaleó (Constitució §2.VIII)</span>
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-700 dark:text-slate-300">Primari HSL</label>
                <div className="w-4 h-4 rounded-full border border-white shadow-sm" style={{ backgroundColor: `hsl(${primariHsl})` }} />
              </div>
              <input
                type="text"
                value={primariHsl}
                onChange={(e) => setPrimariHsl(e.target.value)}
                className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs rounded-xl p-2 font-mono font-bold"
              />
            </div>

            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-700 dark:text-slate-300">Secundari HSL</label>
                <div className="w-4 h-4 rounded-full border border-white shadow-sm" style={{ backgroundColor: `hsl(${secundariHsl})` }} />
              </div>
              <input
                type="text"
                value={secundariHsl}
                onChange={(e) => setSecundariHsl(e.target.value)}
                className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs rounded-xl p-2 font-mono font-bold"
              />
            </div>

            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-700 dark:text-slate-300">Accent HSL</label>
                <div className="w-4 h-4 rounded-full border border-white shadow-sm" style={{ backgroundColor: `hsl(${accentHsl})` }} />
              </div>
              <input
                type="text"
                value={accentHsl}
                onChange={(e) => setAccentHsl(e.target.value)}
                className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs rounded-xl p-2 font-mono font-bold"
              />
            </div>
          </div>
        </div>

        {/* BLOC 3: INTERRUPTORS DINÀMICS DE MÒDULS (FEATURE FLAGS) & ARXIU MESTRE DEL CLIENT */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm md:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-500" />
              <span>Interruptors Dinàmics de Mòduls & Node Local de l'Empresa (IA + Arxiu Històric)</span>
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <label className="flex items-start gap-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 cursor-pointer">
              <input
                type="checkbox"
                checked={features.feature_copilot_ia}
                onChange={(e) => setFeatures({ ...features, feature_copilot_ia: e.target.checked })}
                className="w-4 h-4 mt-0.5 text-emerald-600 rounded"
              />
              <div>
                <span className="text-xs font-bold text-slate-900 dark:text-white block">Copilot d'IA</span>
                <p className="text-[10px] text-slate-500">Peritatge de fotos i memòries tècniques</p>
              </div>
            </label>

            <label className="flex items-start gap-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 cursor-pointer">
              <input
                type="checkbox"
                checked={features.feature_flota}
                onChange={(e) => setFeatures({ ...features, feature_flota: e.target.checked })}
                className="w-4 h-4 mt-0.5 text-emerald-600 rounded"
              />
              <div>
                <span className="text-xs font-bold text-slate-900 dark:text-white block">Flota Avançada</span>
                <p className="text-[10px] text-slate-500">Control d'ITVs i carburant</p>
              </div>
            </label>

            <label className="flex items-start gap-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 cursor-pointer">
              <input
                type="checkbox"
                checked={features.feature_planols}
                onChange={(e) => setFeatures({ ...features, feature_planols: e.target.checked })}
                className="w-4 h-4 mt-0.5 text-emerald-600 rounded"
              />
              <div>
                <span className="text-xs font-bold text-slate-900 dark:text-white block">Plànols Tècnics</span>
                <p className="text-[10px] text-slate-500">Visor vectorial + Arxiu extern del client</p>
              </div>
            </label>

            <label className="flex items-start gap-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 cursor-pointer">
              <input
                type="checkbox"
                checked={features.feature_telegram}
                onChange={(e) => setFeatures({ ...features, feature_telegram: e.target.checked })}
                className="w-4 h-4 mt-0.5 text-emerald-600 rounded"
              />
              <div>
                <span className="text-xs font-bold text-slate-900 dark:text-white block">Bot de Telegram</span>
                <p className="text-[10px] text-slate-500">Canal directe d'incidències</p>
              </div>
            </label>
          </div>

          <div className="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-emerald-500" />
                <span>Ordinador Dedicat de l'Empresa (IA Local + Disc Dur Mestre de Plànols Històrics)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-xs">
                <input
                  type="checkbox"
                  checked={features.node_ia_actiu}
                  onChange={(e) => setFeatures({ ...features, node_ia_actiu: e.target.checked })}
                  className="w-4 h-4 text-emerald-600 rounded"
                />
                <span className="font-semibold text-slate-700 dark:text-slate-300">Activat</span>
              </label>
            </div>
            <div>
              <input
                type="text"
                placeholder="URL de l'ordinador dedicat de l'empresa (ex. https://ia.empresa.cat/v1)"
                value={features.node_ia_url}
                onChange={(e) => setFeatures({ ...features, node_ia_url: e.target.value.trim() })}
                className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-xs rounded-xl p-2.5 font-mono"
              />
              <p className="text-[10px] text-slate-500 mt-1">
                El servidor Hetzner només reté les feines d'avui (Buffer Diari). Qualsevol documentació o plànol històric no inclòs a l'OT del dia es consulta directament a aquest ordinador de l'empresa.
              </p>
            </div>
          </div>
        </div>

        {/* BLOC 4: RECUPERACIÓ DE DADES I BAIXA CERTIFICADA RGPD */}
        <div className="bg-rose-50/60 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/60 p-5 rounded-2xl shadow-sm md:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-rose-700 dark:text-rose-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span>Recuperació Integral de Dades & Baixa Certificada RGPD (Offboarding)</span>
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-300 dark:border-rose-800 font-bold">
              RETENCIÓ FISCAL GARANTIDA
            </span>
          </div>

          <p className="text-xs text-rose-700 dark:text-rose-300 leading-relaxed">
            Abans de donar de baixa l'empresa, pots descarregar un paquet <strong>.zip amb totes les seves dades operatives</strong> per lliurar-lo al client. Quan s'executa la baixa certificada RGPD, es purguen les dades operatives després de 30 dies, però <strong>el CRM manté permanentment les factures Veri*factu i els tiquets d'incidència</strong> per a traçabilitat i auditories fiscals.
          </p>

          <div className="pt-2 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleDownloadFullDataZip}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-colors shadow"
            >
              <ArchiveRestore className="w-4 h-4" />
              <span>Recuperar / Exportar Totes les Dades de l'Empresa (.zip)</span>
            </button>

            <button
              type="button"
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
