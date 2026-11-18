"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Briefcase,
  Check,
  CheckCircle2,
  Copy,
  Download,
  Edit3,
  ExternalLink,
  FileText,
  Mail,
  MessageCircle,
  Plus,
  RefreshCw,
  Search,
  Send,
  Trash2,
  X,
  XCircle,
} from "lucide-react";
import { apiFetch, getApiBaseUrl } from "@/lib/api";
import { useGestio } from "@/lib/gestio-context";

interface PressupostLinia {
  article_id?: string | null;
  concepte: string;
  quantitat: number;
  preu_unitari: number;
  descompte_pct: number;
  tipus_iva: number;
  subtotal?: number;
}

interface PressupostItem {
  id: string;
  client_id: string;
  client_nom?: string | null;
  client_email?: string | null;
  client_telefon?: string | null;
  client_te_telegram: boolean;
  numero: string;
  titol?: string | null;
  descripcio?: string | null;
  base_imposable: number;
  quota_iva: number;
  total: number;
  validesa_dies: number;
  estat: string;
  canal_enviament?: string | null;
  email_destinatari?: string | null;
  data_enviament?: string | null;
  acceptacio_url?: string | null;
  ordre_treball_id?: string | null;
  motiu_canvis_client?: string | null;
  linies: PressupostLinia[];
  created_at: string;
}

interface ClientOption {
  id: string;
  rao_social: string;
  nif: string;
  email?: string | null;
  telefon?: string | null;
}

function r2(val: number): number {
  return Math.round((val + Number.EPSILON) * 100) / 100;
}

function badgeEstat(estat: string): string {
  const up = (estat || "").toUpperCase();
  if (up === "APROVAT") return "bg-emerald-100 text-emerald-800 border-emerald-200";
  if (up === "REBUTJAT") return "bg-rose-100 text-rose-800 border-rose-200";
  return "bg-amber-100 text-amber-800 border-amber-200";
}

function PressupostosContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { rolActiu } = useGestio();
  const esEnginyer = (rolActiu || "").toUpperCase() === "ENGINYER";

  const paramId = searchParams.get("id") || "";
  const paramEnviar = searchParams.get("enviar") === "1";
  const paramClientId = searchParams.get("client_id") || "";

  const [pressupostos, setPressupostos] = useState<PressupostItem[]>([]);
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [cerca, setCerca] = useState("");
  const [filtreEstat, setFiltreEstat] = useState<"TOTS" | "PENDENT" | "APROVAT" | "REBUTJAT">("TOTS");

  // Modal Creació / Edició Pressupost
  const [modalEditor, setModalEditor] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formClientId, setFormClientId] = useState("");
  const [formNumero, setFormNumero] = useState("");
  const [formTitol, setFormTitol] = useState("");
  const [formDescripcio, setFormDescripcio] = useState("");
  const [formValidesa, setFormValidesa] = useState("30");
  const [formLinies, setFormLinies] = useState<PressupostLinia[]>([
    { concepte: "", quantitat: 1, preu_unitari: 0, descompte_pct: 0, tipus_iva: 21 },
  ]);
  const [saving, setSaving] = useState(false);

  // Modal Enviament Multi-Canal
  const [sendModalItem, setSendModalItem] = useState<PressupostItem | null>(null);
  const [emailDesti, setEmailDesti] = useState("");
  const [emailAssumpte, setEmailAssumpte] = useState("");
  const [emailCos, setEmailCos] = useState("");
  const [sendingChannel, setSendingChannel] = useState<"EMAIL" | "TELEGRAM" | null>(null);
  const [mailtoFallback, setMailtoFallback] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [handledParamId, setHandledParamId] = useState<string | null>(null);

  const carregarDades = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [presRes, cliRes] = await Promise.all([
        apiFetch<PressupostItem[]>("/gestio/pressupostos"),
        apiFetch<ClientOption[]>("/gestio/clients?limit=200").catch(() => []),
      ]);
      setPressupostos(Array.isArray(presRes) ? presRes : []);
      setClients(Array.isArray(cliRes) ? cliRes : []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error carregant els pressupostos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    carregarDades();
  }, [carregarDades]);

  const obrirModalEnviar = useCallback((p: PressupostItem) => {
    setSendModalItem(p);
    setEmailDesti(p.email_destinatari || p.client_email || "");
    setEmailAssumpte(`Pressupost ${p.numero}${p.titol ? ` — ${p.titol}` : ""}`);
    setEmailCos(
      `Bon dia${p.client_nom ? ` ${p.client_nom}` : ""},\n\n` +
        `Us fem arribar el pressupost ${p.numero}${p.titol ? ` (${p.titol})` : ""} per un import total de ${Number(p.total).toFixed(2)} €.\n\n` +
        (p.acceptacio_url
          ? `Podeu consultar-lo i acceptar-lo directament en línia aquí:\n${p.acceptacio_url}\n\n`
          : "") +
        `Restem a la vostra disposició per a qualsevol consulta.`
    );
    setMailtoFallback(null);
    setCopiedLink(false);
  }, []);

  useEffect(() => {
    if (paramId && paramId !== handledParamId && pressupostos.length > 0) {
      const found = pressupostos.find((p) => p.id === paramId);
      if (found) {
        if (paramEnviar) {
          obrirModalEnviar(found);
        }
        setHandledParamId(paramId);
      }
    }
  }, [paramId, paramEnviar, pressupostos, handledParamId, obrirModalEnviar]);

  const editorTotals = useMemo(() => {
    const basesPerIva: Record<string, number> = {};
    for (const l of formLinies) {
      const sub = r2(
        Number(l.quantitat || 0) * Number(l.preu_unitari || 0) * (1 - Number(l.descompte_pct || 0) / 100)
      );
      const key = String(Number(l.tipus_iva ?? 21));
      basesPerIva[key] = (basesPerIva[key] || 0) + sub;
    }
    const base = r2(Object.values(basesPerIva).reduce((a, b) => a + b, 0));
    let iva = 0;
    for (const [k, b] of Object.entries(basesPerIva)) {
      iva += r2(b * (Number(k) / 100));
    }
    iva = r2(iva);
    return { base, iva, total: r2(base + iva) };
  }, [formLinies]);

  const filtrats = useMemo(() => {
    return pressupostos.filter((p) => {
      if (paramClientId && p.client_id !== paramClientId) return false;
      if (filtreEstat !== "TOTS" && p.estat.toUpperCase() !== filtreEstat) return false;
      if (!cerca.trim()) return true;
      const t = cerca.trim().toLowerCase();
      return (
        (p.numero || "").toLowerCase().includes(t) ||
        (p.titol || "").toLowerCase().includes(t) ||
        (p.client_nom || "").toLowerCase().includes(t)
      );
    });
  }, [pressupostos, filtreEstat, cerca, paramClientId]);

  const stats = useMemo(() => {
    const pendents = pressupostos.filter((p) => p.estat === "PENDENT").length;
    const enviats = pressupostos.filter((p) => Boolean(p.canal_enviament)).length;
    const aprovats = pressupostos.filter((p) => p.estat === "APROVAT");
    const totalAprovat = aprovats.reduce((acc, p) => acc + Number(p.total || 0), 0);
    return {
      total: pressupostos.length,
      pendents,
      enviats,
      aprovatsCount: aprovats.length,
      totalAprovat,
    };
  }, [pressupostos]);

  const obrirNouPressupost = () => {
    const numSuggerit = `PRES-${new Date().getFullYear()}-${String(Date.now()).slice(-4)}`;
    setEditingId(null);
    setFormClientId(paramClientId || "");
    setFormNumero(numSuggerit);
    setFormTitol("");
    setFormDescripcio("");
    setFormValidesa("30");
    setFormLinies([
      { concepte: "", quantitat: 1, preu_unitari: 0, descompte_pct: 0, tipus_iva: 21 },
    ]);
    setModalEditor(true);
  };

  const obrirEditarPressupost = (p: PressupostItem) => {
    setEditingId(p.id);
    setFormClientId(p.client_id);
    setFormNumero(p.numero);
    setFormTitol(p.titol || "");
    setFormDescripcio(p.descripcio || "");
    setFormValidesa(String(p.validesa_dies || 30));
    setFormLinies(
      p.linies && p.linies.length > 0
        ? p.linies.map((l) => ({ ...l }))
        : [
            {
              concepte: p.titol || `Pressupost ${p.numero}`,
              quantitat: 1,
              preu_unitari: Number(p.total || 0),
              descompte_pct: 0,
              tipus_iva: 0,
            },
          ]
    );
    setModalEditor(true);
  };

  const handleDesarPressupost = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formClientId) {
      setError("Selecciona un client.");
      return;
    }
    const liniesValides = formLinies.filter((l) => l.concepte.trim().length > 0);
    if (liniesValides.length === 0) {
      setError("Afegeix com a mínim una partida amb descripció.");
      return;
    }
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const payloadLinies = liniesValides.map((l) => ({
        article_id: l.article_id || null,
        concepte: l.concepte.trim(),
        quantitat: Math.max(0.01, Number(l.quantitat || 1)),
        preu_unitari: Math.max(0, Number(l.preu_unitari || 0)),
        descompte_pct: Math.min(100, Math.max(0, Number(l.descompte_pct || 0))),
        tipus_iva: Math.max(0, Number(l.tipus_iva ?? 21)),
      }));

      let saved: PressupostItem;
      if (editingId) {
        saved = await apiFetch<PressupostItem>(`/gestio/pressupostos/${editingId}`, {
          method: "PUT",
          body: JSON.stringify({
            client_id: formClientId,
            titol: formTitol.trim() || `Pressupost ${formNumero}`,
            descripcio: formDescripcio.trim() || null,
            validesa_dies: Number(formValidesa || 30),
            linies: payloadLinies,
          }),
        });
        setSuccessMsg(`Pressupost ${saved.numero} actualitzat correctament.`);
      } else {
        saved = await apiFetch<PressupostItem>("/gestio/pressupostos", {
          method: "POST",
          body: JSON.stringify({
            client_id: formClientId,
            numero: formNumero.trim(),
            titol: formTitol.trim() || `Pressupost ${formNumero}`,
            descripcio: formDescripcio.trim() || null,
            validesa_dies: Number(formValidesa || 30),
            total: editorTotals.total,
            linies: payloadLinies,
          }),
        });
        setSuccessMsg(`Pressupost ${saved.numero} creat. Ara ja el pots enviar al client!`);
      }
      setModalEditor(false);
      await carregarDades();
      if (!editingId) {
        obrirModalEnviar(saved);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en desar el pressupost.");
    } finally {
      setSaving(false);
    }
  };

  const handleEnviarEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sendModalItem) return;
    setSendingChannel("EMAIL");
    setError(null);
    setMailtoFallback(null);
    try {
      const res = await apiFetch<{
        status: string;
        smtp_enviat: boolean;
        missatge: string;
        mailto_url?: string;
        acceptacio_url?: string;
      }>(`/gestio/pressupostos/${sendModalItem.id}/enviar-email`, {
        method: "POST",
        body: JSON.stringify({
          email_destinatari: emailDesti.trim(),
          assumpte: emailAssumpte.trim(),
          missatge: emailCos.trim(),
        }),
      });
      if (res.smtp_enviat) {
        setSuccessMsg(res.missatge);
        setSendModalItem(null);
        await carregarDades();
      } else {
        setMailtoFallback(res.mailto_url || null);
        setError(res.missatge);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error enviant el pressupost per correu.");
    } finally {
      setSendingChannel(null);
    }
  };

  const handleEnviarTelegram = async () => {
    if (!sendModalItem) return;
    setSendingChannel("TELEGRAM");
    setError(null);
    try {
      await apiFetch(`/gestio/pressupostos/${sendModalItem.id}/enviar-telegram`, {
        method: "POST",
      });
      setSuccessMsg(`Pressupost ${sendModalItem.numero} enviat per Telegram amb botons d'acceptació!`);
      setSendModalItem(null);
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error enviant per Telegram.");
    } finally {
      setSendingChannel(null);
    }
  };

  const handleRegistrarEnviamentCanal = async (canal: string, destin?: string) => {
    if (!sendModalItem) return;
    try {
      await apiFetch(`/gestio/pressupostos/${sendModalItem.id}/registrar-enviament`, {
        method: "POST",
        body: JSON.stringify({ canal, destinatari: destin }),
      });
      await carregarDades();
    } catch {
      // Non-blocking audit mark
    }
  };

  const handleCopiarEnllac = async () => {
    if (!sendModalItem?.acceptacio_url) return;
    try {
      await navigator.clipboard.writeText(sendModalItem.acceptacio_url);
      setCopiedLink(true);
      await handleRegistrarEnviamentCanal("ENLLAC");
      setSuccessMsg("Enllaç d'acceptació copiat al porta-retalls!");
    } catch {
      setError("No s'ha pogut copiar automàticament; selecciona i copia la URL manualment.");
    }
  };

  const handleConvertirOT = async (p: PressupostItem) => {
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await apiFetch<{ ordre_treball_id: string; codi_ot: string }>(
        `/gestio/pressupostos/${p.id}/convertir-ot`,
        {
          method: "POST",
          body: JSON.stringify({ forcar_si_pendent: p.estat === "PENDENT" }),
        }
      );
      await carregarDades();
      setSuccessMsg(`Ordre de Treball ${res.codi_ot} creada des del pressupost ${p.numero}.`);
      router.push(`/gestio/feines?id=${res.ordre_treball_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en convertir a Ordre de Treball.");
    }
  };

  const handleCanviarEstat = async (p: PressupostItem, accio: "aprovar" | "rebutjar") => {
    setError(null);
    try {
      await apiFetch(`/gestio/pressupostos/${p.id}/${accio}`, { method: "POST" });
      await carregarDades();
      setSuccessMsg(
        accio === "aprovar"
          ? `Pressupost ${p.numero} marcat com a APROVAT.`
          : `Pressupost ${p.numero} marcat com a REBUTJAT.`
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error actualitzant l'estat.");
    }
  };

  return (
    <div className="flex-1 flex flex-col space-y-lg w-full animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-md pb-md border-b border-outline-variant/30">
        <div>
          <span className="font-label-caps text-secondary uppercase tracking-widest text-[11px]">
            Cicle Comercial HITL · Pressupostos &amp; Acceptació Client
          </span>
          <h1 className="font-display-lg text-2xl md:text-3xl text-primary mt-0.5 flex items-center gap-2.5">
            <FileText className="w-6 h-6 text-secondary shrink-0" />
            <span>Pressupostos i Enviament a Clients</span>
          </h1>
          <p className="text-sm text-on-surface-variant mt-1">
            Prepara partides detallades, descarrega el PDF corporatiu i envia el pressupost per Email, Telegram, WhatsApp o enllaç d&apos;acceptació.
          </p>
        </div>

        <div className="flex items-center gap-sm flex-wrap">
          <button
            type="button"
            onClick={carregarDades}
            disabled={loading}
            className="px-3.5 py-2.5 rounded-xl bg-surface-container-lowest border border-outline-variant/60 text-xs font-body-strong text-on-surface hover:bg-surface-container flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Actualitzar</span>
          </button>

          <button
            type="button"
            onClick={obrirNouPressupost}
            className="px-4 py-2.5 rounded-xl bg-primary hover:bg-primary/90 text-on-primary text-xs font-body-strong flex items-center gap-2 shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>+ Nou Pressupost</span>
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-md">
        <div className="p-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm">
          <span className="font-label-caps text-[10px] uppercase text-on-surface-variant block">
            Total Pressupostos
          </span>
          <span className="font-data-tabular text-2xl font-bold text-primary mt-1 block">
            {stats.total}
          </span>
        </div>
        <div className="p-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm">
          <span className="font-label-caps text-[10px] uppercase text-on-surface-variant block">
            Pendents d&apos;Acceptació
          </span>
          <span className="font-data-tabular text-2xl font-bold text-amber-600 mt-1 block">
            {stats.pendents}
          </span>
        </div>
        <div className="p-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm">
          <span className="font-label-caps text-[10px] uppercase text-on-surface-variant block">
            Enviats al Client
          </span>
          <span className="font-data-tabular text-2xl font-bold text-secondary mt-1 block">
            {stats.enviats}
          </span>
        </div>
        <div className="p-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm">
          <span className="font-label-caps text-[10px] uppercase text-on-surface-variant block">
            Aprovats ({stats.aprovatsCount})
          </span>
          <span className="font-data-tabular text-2xl font-bold text-emerald-700 mt-1 block">
            {esEnginyer ? "—" : `${stats.totalAprovat.toFixed(2)} €`}
          </span>
        </div>
      </div>

      {error && (
        <div className="p-md rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium flex items-center justify-between gap-2">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)}>
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="p-md rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4" />
            {successMsg}
          </span>
          <button type="button" onClick={() => setSuccessMsg(null)}>
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Cerca i filtres */}
      <div className="p-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-md">
        <div className="relative flex-1 max-w-lg">
          <Search className="w-4 h-4 text-on-surface-variant absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={cerca}
            onChange={(e) => setCerca(e.target.value)}
            placeholder="Cercar per número, títol o client..."
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/60 text-xs text-on-surface focus:border-primary outline-none"
          />
        </div>
        <div className="flex items-center gap-xs flex-wrap">
          {(["TOTS", "PENDENT", "APROVAT", "REBUTJAT"] as const).map((est) => (
            <button
              key={est}
              type="button"
              onClick={() => setFiltreEstat(est)}
              className={`px-3 py-1.5 rounded-full text-xs font-body-strong cursor-pointer ${
                filtreEstat === est
                  ? "bg-primary text-on-primary shadow-sm"
                  : "bg-surface-container-low text-on-surface-variant hover:bg-surface-container-high"
              }`}
            >
              {est}
            </button>
          ))}
        </div>
      </div>

      {/* Taula de Pressupostos */}
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/40 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-2xl text-center text-xs font-mono text-on-surface-variant animate-pulse">
            Carregant pressupostos...
          </div>
        ) : filtrats.length === 0 ? (
          <div className="p-2xl text-center space-y-3">
            <FileText className="w-10 h-10 text-outline mx-auto opacity-50" />
            <p className="text-sm font-semibold text-primary">Cap pressupost trobat</p>
            <p className="text-xs text-on-surface-variant">
              Crea un pressupost nou des d&apos;aquí o des del botó &quot;Generar Pressupost&quot; d&apos;una Ordre de Treball.
            </p>
            <button
              type="button"
              onClick={obrirNouPressupost}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary text-on-primary text-xs font-bold cursor-pointer"
            >
              <Plus className="w-4 h-4" /> Nou Pressupost
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant/40 text-[10px] font-label-caps uppercase text-on-surface-variant">
                  <th className="py-3 px-4">Número</th>
                  <th className="py-3 px-4">Títol &amp; Client</th>
                  <th className="py-3 px-4">Enviament</th>
                  {!esEnginyer && <th className="py-3 px-4 text-right">Import Total</th>}
                  <th className="py-3 px-4">Estat</th>
                  <th className="py-3 px-4 text-right">Accions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/25">
                {filtrats.map((p) => (
                  <tr key={p.id} className="hover:bg-surface-container-low/50">
                    <td className="py-3 px-4 whitespace-nowrap">
                      <span className="font-mono font-bold text-primary">{p.numero}</span>
                      <span className="block text-[10px] text-on-surface-variant">
                        {new Date(p.created_at).toLocaleDateString()}
                      </span>
                    </td>
                    <td className="py-3 px-4 min-w-[200px]">
                      <p className="font-bold text-on-surface">{p.titol || p.numero}</p>
                      <p className="text-[11px] text-on-surface-variant">
                        {p.client_nom || "Client"}
                        {p.linies.length > 0 ? ` · ${p.linies.length} partides` : ""}
                      </p>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      {p.canal_enviament ? (
                        <div>
                          <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 text-primary px-2 py-0.5 text-[10px] font-bold">
                            <Send className="w-2.5 h-2.5" /> {p.canal_enviament}
                          </span>
                          {p.data_enviament && (
                            <span className="block text-[10px] text-on-surface-variant mt-0.5">
                              {new Date(p.data_enviament).toLocaleString("ca-ES", {
                                day: "2-digit",
                                month: "2-digit",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-[11px] text-amber-700 font-medium">
                          No enviat encara
                        </span>
                      )}
                    </td>
                    {!esEnginyer && (
                      <td className="py-3 px-4 text-right whitespace-nowrap font-data-tabular font-bold text-slate-900 dark:text-white">
                        {Number(p.total || 0).toFixed(2)} €
                      </td>
                    )}
                    <td className="py-3 px-4 whitespace-nowrap">
                      <span
                        className={`text-[10px] px-2.5 py-0.5 rounded-full border font-bold uppercase ${badgeEstat(
                          p.estat
                        )}`}
                      >
                        {p.estat}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <div className="inline-flex items-center gap-1.5 flex-wrap justify-end">
                        <button
                          type="button"
                          onClick={() => obrirModalEnviar(p)}
                          className="px-2.5 py-1.5 rounded-lg bg-primary text-white text-[11px] font-bold hover:opacity-90 inline-flex items-center gap-1 cursor-pointer"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>Enviar</span>
                        </button>
                        <a
                          href={`${getApiBaseUrl()}/gestio/pressupostos/${p.id}/pdf`}
                          target="_blank"
                          rel="noreferrer"
                          className="px-2 py-1.5 rounded-lg border border-outline-variant/60 text-[11px] font-semibold text-on-surface hover:bg-surface-container inline-flex items-center gap-1"
                        >
                          <Download className="w-3.5 h-3.5" /> PDF
                        </a>
                        {p.estat === "PENDENT" && (
                          <>
                            <button
                              type="button"
                              onClick={() => obrirEditarPressupost(p)}
                              className="p-1.5 rounded-lg border border-outline-variant/60 text-secondary hover:bg-surface-container cursor-pointer"
                              title="Editar partides"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleCanviarEstat(p, "aprovar")}
                              className="p-1.5 rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 cursor-pointer"
                              title="Marcar com a Aprovat"
                            >
                              <Check className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleCanviarEstat(p, "rebutjar")}
                              className="p-1.5 rounded-lg border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 cursor-pointer"
                              title="Marcar com a Rebutjat"
                            >
                              <XCircle className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}
                        {p.estat === "APROVAT" && !p.ordre_treball_id && (
                          <button
                            type="button"
                            onClick={() => handleConvertirOT(p)}
                            className="px-2.5 py-1.5 rounded-lg bg-secondary text-white text-[11px] font-bold hover:opacity-90 inline-flex items-center gap-1 cursor-pointer"
                          >
                            <Briefcase className="w-3.5 h-3.5" />
                            <span>Crear OT</span>
                          </button>
                        )}
                        {p.ordre_treball_id && (
                          <Link
                            href={`/gestio/feines?id=${p.ordre_treball_id}`}
                            className="px-2 py-1 rounded-lg bg-emerald-100 text-emerald-800 text-[10px] font-bold inline-flex items-center gap-1"
                          >
                            <Briefcase className="w-3 h-3" /> OT Vinculada
                          </Link>
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

      {/* MODAL CREAR / EDITAR PRESSUPOST */}
      {modalEditor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 overflow-y-auto">
          <div className="w-full max-w-4xl rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                {editingId ? `Editar Pressupost ${formNumero}` : "Nou Pressupost Detallat"}
              </h3>
              <button type="button" onClick={() => setModalEditor(false)}>
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>

            <form onSubmit={handleDesarPressupost} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold mb-1">Client *</label>
                  <select
                    required
                    value={formClientId}
                    onChange={(e) => setFormClientId(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2"
                  >
                    <option value="">Selecciona client...</option>
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.rao_social} ({c.nif})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-semibold mb-1">Número Pressupost *</label>
                  <input
                    required
                    disabled={Boolean(editingId)}
                    value={formNumero}
                    onChange={(e) => setFormNumero(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2 font-mono disabled:opacity-60"
                  />
                </div>
                <div>
                  <label className="block font-semibold mb-1">Validesa (dies)</label>
                  <input
                    type="number"
                    min={1}
                    max={365}
                    value={formValidesa}
                    onChange={(e) => setFormValidesa(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold mb-1">Títol / Concepte General *</label>
                  <input
                    required
                    value={formTitol}
                    onChange={(e) => setFormTitol(e.target.value)}
                    placeholder="Ex: Substitució caldera i posada en marxa"
                    className="w-full rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block font-semibold mb-1">Observacions / Abast tècnic</label>
                  <input
                    value={formDescripcio}
                    onChange={(e) => setFormDescripcio(e.target.value)}
                    placeholder="Detalls d'execució, terminis o garantia..."
                    className="w-full rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2"
                  />
                </div>
              </div>

              {/* Partides */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold uppercase text-slate-600">Partides del Pressupost</span>
                  <button
                    type="button"
                    onClick={() =>
                      setFormLinies((prev) => [
                        ...prev,
                        { concepte: "", quantitat: 1, preu_unitari: 0, descompte_pct: 0, tipus_iva: 21 },
                      ])
                    }
                    className="inline-flex items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1 font-semibold text-primary hover:bg-primary/20 cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" /> Afegir Partida
                  </button>
                </div>

                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
                  <table className="w-full text-left">
                    <thead className="bg-slate-50 dark:bg-slate-800 text-slate-600">
                      <tr>
                        <th className="px-2.5 py-2 min-w-[220px]">Concepte</th>
                        <th className="px-2 py-2 w-20">Qt.</th>
                        <th className="px-2 py-2 w-24">Preu u. (€)</th>
                        <th className="px-2 py-2 w-20">Dto %</th>
                        <th className="px-2 py-2 w-20">IVA %</th>
                        <th className="px-2 py-2 w-24 text-right">Subtotal</th>
                        <th className="px-2 py-2 w-10"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {formLinies.map((lin, idx) => {
                        const sub = r2(
                          Number(lin.quantitat || 0) *
                            Number(lin.preu_unitari || 0) *
                            (1 - Number(lin.descompte_pct || 0) / 100)
                        );
                        return (
                          <tr key={idx}>
                            <td className="px-2.5 py-2">
                              <input
                                type="text"
                                required
                                value={lin.concepte}
                                onChange={(e) =>
                                  setFormLinies((prev) =>
                                    prev.map((it, i) => (i === idx ? { ...it, concepte: e.target.value } : it))
                                  )
                                }
                                placeholder="Mà d'obra / Material / Desplaçament..."
                                className="w-full rounded border border-slate-200 dark:border-slate-700 px-2 py-1"
                              />
                            </td>
                            <td className="px-2 py-2">
                              <input
                                type="number"
                                step="0.01"
                                min="0.01"
                                value={lin.quantitat}
                                onChange={(e) =>
                                  setFormLinies((prev) =>
                                    prev.map((it, i) =>
                                      i === idx ? { ...it, quantitat: Number(e.target.value) } : it
                                    )
                                  )
                                }
                                className="w-full rounded border border-slate-200 dark:border-slate-700 px-2 py-1 tabular-nums"
                              />
                            </td>
                            <td className="px-2 py-2">
                              <input
                                type="number"
                                step="0.01"
                                min="0"
                                value={lin.preu_unitari}
                                onChange={(e) =>
                                  setFormLinies((prev) =>
                                    prev.map((it, i) =>
                                      i === idx ? { ...it, preu_unitari: Number(e.target.value) } : it
                                    )
                                  )
                                }
                                className="w-full rounded border border-slate-200 dark:border-slate-700 px-2 py-1 tabular-nums"
                              />
                            </td>
                            <td className="px-2 py-2">
                              <input
                                type="number"
                                step="0.1"
                                min="0"
                                max="100"
                                value={lin.descompte_pct}
                                onChange={(e) =>
                                  setFormLinies((prev) =>
                                    prev.map((it, i) =>
                                      i === idx ? { ...it, descompte_pct: Number(e.target.value) } : it
                                    )
                                  )
                                }
                                className="w-full rounded border border-slate-200 dark:border-slate-700 px-2 py-1 tabular-nums"
                              />
                            </td>
                            <td className="px-2 py-2">
                              <select
                                value={lin.tipus_iva}
                                onChange={(e) =>
                                  setFormLinies((prev) =>
                                    prev.map((it, i) =>
                                      i === idx ? { ...it, tipus_iva: Number(e.target.value) } : it
                                    )
                                  )
                                }
                                className="w-full rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-1.5 py-1"
                              >
                                <option value={21}>21%</option>
                                <option value={10}>10%</option>
                                <option value={4}>4%</option>
                                <option value={0}>0%</option>
                              </select>
                            </td>
                            <td className="px-2 py-2 text-right font-semibold tabular-nums">
                              {sub.toFixed(2)} €
                            </td>
                            <td className="px-2 py-2 text-center">
                              <button
                                type="button"
                                disabled={formLinies.length <= 1}
                                onClick={() => setFormLinies((prev) => prev.filter((_, i) => i !== idx))}
                                className="p-1 text-rose-600 disabled:opacity-30"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 p-4 flex items-center justify-between">
                <div className="flex gap-6">
                  <div>
                    <span className="text-slate-500 block">Base Imposable</span>
                    <span className="font-bold tabular-nums">{editorTotals.base.toFixed(2)} €</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Quota IVA</span>
                    <span className="font-bold tabular-nums">{editorTotals.iva.toFixed(2)} €</span>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-slate-500 block">TOTAL PRESSUPOST</span>
                  <span className="text-xl font-black text-primary tabular-nums">
                    {editorTotals.total.toFixed(2)} €
                  </span>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalEditor(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-primary px-5 py-2 font-semibold text-white hover:opacity-90 disabled:opacity-50"
                >
                  {saving ? "Desant..." : editingId ? "Desar Canvis" : "Crear i Enviar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL ENVIAR PRESSUPOST MULTI-CANAL */}
      {sendModalItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 overflow-y-auto">
          <div className="w-full max-w-2xl rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl space-y-5 my-8">
            <div className="flex items-start justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-secondary">
                  Enviament de Pressupost · {sendModalItem.numero}
                </span>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                  {sendModalItem.titol || sendModalItem.numero} — {sendModalItem.client_nom}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Import total: <strong>{Number(sendModalItem.total).toFixed(2)} €</strong>
                </p>
              </div>
              <button type="button" onClick={() => setSendModalItem(null)}>
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>

            {/* Canal 1: Enviar per Email amb PDF adjunt */}
            <form
              onSubmit={handleEnviarEmail}
              className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 space-y-3 text-xs"
            >
              <div className="flex items-center justify-between">
                <h4 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Mail className="w-4 h-4 text-primary" />
                  1. Enviar per Correu Electrònic (PDF + Enllaç d&apos;acceptació)
                </h4>
                <a
                  href={`${getApiBaseUrl()}/gestio/pressupostos/${sendModalItem.id}/pdf`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary hover:underline font-semibold inline-flex items-center gap-1"
                >
                  <Download className="w-3.5 h-3.5" /> Previsualitzar PDF
                </a>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label className="block font-medium text-slate-600 mb-1">Email del client *</label>
                  <input
                    type="email"
                    required
                    value={emailDesti}
                    onChange={(e) => setEmailDesti(e.target.value)}
                    placeholder="client@empresa.cat"
                    className="w-full rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-600 mb-1">Assumpte *</label>
                  <input
                    type="text"
                    required
                    value={emailAssumpte}
                    onChange={(e) => setEmailAssumpte(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2"
                  />
                </div>
              </div>
              <div>
                <label className="block font-medium text-slate-600 mb-1">Missatge al client</label>
                <textarea
                  rows={4}
                  value={emailCos}
                  onChange={(e) => setEmailCos(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 dark:border-slate-700 p-2.5"
                />
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                {mailtoFallback ? (
                  <a
                    href={mailtoFallback}
                    onClick={() => handleRegistrarEnviamentCanal("EMAIL_MANUAL", emailDesti)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3.5 py-2 font-semibold text-white hover:bg-amber-500"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    Obrir al meu client de correu (Mailto)
                  </a>
                ) : (
                  <span className="text-[11px] text-slate-500">
                    S&apos;adjuntarà automàticament el PDF oficial del pressupost.
                  </span>
                )}
                <button
                  type="submit"
                  disabled={sendingChannel !== null}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 font-semibold text-white hover:opacity-90 disabled:opacity-50 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  {sendingChannel === "EMAIL" ? "Enviant Email..." : "Enviar per Email"}
                </button>
              </div>
            </form>

            {/* Canal 2: Telegram i Canal 3: Enllaç / WhatsApp */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 flex flex-col justify-between space-y-3">
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <Send className="w-4 h-4 text-sky-600" />
                    2. Canal Telegram Bot
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {sendModalItem.client_te_telegram
                      ? "El client té Telegram actiu. Rebrà els botons d'acceptació a 1 clic."
                      : "Aquest client encara no ha vinculat el bot de Telegram."}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={!sendModalItem.client_te_telegram || sendingChannel !== null}
                  onClick={handleEnviarTelegram}
                  className="w-full rounded-lg bg-sky-600 px-3 py-2 font-semibold text-white hover:bg-sky-500 disabled:opacity-40 cursor-pointer"
                >
                  {sendingChannel === "TELEGRAM" ? "Enviant..." : "Enviar per Telegram"}
                </button>
              </div>

              <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 flex flex-col justify-between space-y-3">
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <MessageCircle className="w-4 h-4 text-emerald-600" />
                    3. Enllaç Directe / WhatsApp
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Comparteix la URL segura perquè el client pugui veure i acceptar el pressupost des del mòbil.
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleCopiarEnllac}
                    className="flex-1 rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2 font-semibold hover:bg-slate-50 inline-flex items-center justify-center gap-1 cursor-pointer"
                  >
                    <Copy className="w-3.5 h-3.5" />
                    {copiedLink ? "Copiat!" : "Copiar Enllaç"}
                  </button>
                  {sendModalItem.acceptacio_url && (
                    <a
                      href={`https://wa.me/${(sendModalItem.client_telefon || "").replace(/\D/g, "")}?text=${encodeURIComponent(
                        `Bon dia, us enviem el pressupost ${sendModalItem.numero} (${Number(sendModalItem.total).toFixed(2)} €). El podeu consultar i acceptar aquí: ${sendModalItem.acceptacio_url}`
                      )}`}
                      target="_blank"
                      rel="noreferrer"
                      onClick={() => handleRegistrarEnviamentCanal("WHATSAPP", sendModalItem.client_telefon || undefined)}
                      className="rounded-lg bg-emerald-600 px-3 py-2 font-semibold text-white hover:bg-emerald-500 inline-flex items-center gap-1"
                    >
                      <MessageCircle className="w-3.5 h-3.5" /> WhatsApp
                    </a>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function GestioPressupostosPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-xs font-mono text-slate-500 animate-pulse">
          Carregant mòdul de pressupostos...
        </div>
      }
    >
      <PressupostosContent />
    </Suspense>
  );
}
