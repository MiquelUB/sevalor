"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Building2,
  CheckCircle2,
  Copy,
  Download,
  Edit3,
  ExternalLink,
  Eye,
  FileText,
  Mail,
  MapPin,
  MessageCircle,
  Navigation,
  Package,
  Plus,
  Search,
  Send,
  Sparkles,
  Trash2,
  Truck,
  Wrench,
  X,
} from "lucide-react";
import { apiFetch, extractTenantId, getApiBaseUrl, getAuthToken } from "@/lib/api";

export interface PressupostLinia {
  article_id?: string | null;
  vehicle_id?: string | null;
  eina_id?: string | null;
  seccio?: string | null;
  tipus_linia?: string;
  concepte: string;
  detall?: string | null;
  quantitat: number;
  preu_unitari: number;
  descompte_pct: number;
  tipus_iva: number;
  subtotal?: number;
}

export interface EinaResumItem {
  id: string;
  nom: string;
  model?: string | null;
  numero_serie?: string | null;
}

export interface PressupostItem {
  id: string;
  client_id: string;
  client_nom?: string | null;
  client_rao_social?: string | null;
  client_nif?: string | null;
  client_adreca?: string | null;
  client_codi_postal?: string | null;
  client_poblacio?: string | null;
  client_provincia?: string | null;
  client_persona_contacte?: string | null;
  client_email?: string | null;
  client_telefon?: string | null;
  client_te_telegram: boolean;

  numero: string;
  titol?: string | null;
  descripcio?: string | null;
  data_pressupost?: string | null;
  validesa_dies: number;
  referencia_client?: string | null;
  elaborat_per?: string | null;

  finca_id?: string | null;
  adreca_obra?: string | null;
  vehicle_id?: string | null;
  vehicle_nom?: string | null;
  eines_ids?: string[];
  eines_resum?: EinaResumItem[];
  desplacament_km?: number | null;
  desplacament_preu_km?: number | null;
  desplacament_import_fix?: number | null;

  subtotal_brut?: number;
  descompte_global_pct?: number;
  descompte_global_import?: number;
  base_imposable: number;
  quota_iva: number;
  total: number;

  forma_pagament?: string | null;
  percentatge_acompte?: number;
  import_acompte?: number;
  termini_execucio?: string | null;
  notes_exclusions?: string | null;
  mencio_legal?: string | null;
  nom_signant_client?: string | null;

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

export interface ClientOption {
  id: string;
  codi?: string;
  rao_social: string;
  nif: string;
  email?: string | null;
  telefon?: string | null;
  adreca_fiscal?: string | null;
  codi_postal?: string | null;
  poblacio?: string | null;
  provincia?: string | null;
  persona_contacte?: string | null;
  dades_contacte?: string | null;
}

export interface FincaOption {
  id: string;
  nom: string;
  adreca?: string | null;
}

export interface VehicleOption {
  id: string;
  matricula: string;
  marca?: string | null;
  model?: string | null;
  estat_semafor?: string | null;
  cost_per_km_eur?: number | null;
}

export interface EinaOption {
  id: string;
  nom: string;
  model?: string | null;
  numero_serie?: string | null;
  estat?: string | null;
}

export interface ArticleMagatzemOption {
  id: string;
  referencia_inventari: string;
  nom: string;
  unitat_mesura?: string;
  preu_venda: number;
  estoc_disponible?: number;
}

interface BaremaConfigOption {
  preu_hora_standard_eur?: number;
  tarifa_urgencia_eur?: number;
  suplement_desplacament_eur?: number;
  partides?: Array<{ codi: string; descripcio: string; unitat: string; preu_eur: number }>;
}

const SECCIONS_SUGGERIDES = [
  "Mà d'obra i instal·lació",
  "Materials i subministraments",
  "Desplaçament i vehicle",
  "Eines i maquinària",
  "Altres conceptes",
];

function r2(val: number): number {
  return Math.round((val + Number.EPSILON) * 100) / 100;
}

function buildAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  const tenantId = extractTenantId();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (tenantId) {
    headers["X-Empresa-ID"] = tenantId;
    headers["X-Tenant-ID"] = tenantId;
  }
  return headers;
}

export async function descarregarPdfPressupostAutenticat(
  pressupostId: string,
  numero?: string
): Promise<void> {
  const res = await fetch(`${getApiBaseUrl()}/gestio/pressupostos/${pressupostId}/pdf`, {
    headers: buildAuthHeaders(),
    credentials: "include",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Error HTTP ${res.status} generant el PDF del pressupost.`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const opened = window.open(url, "_blank", "noopener,noreferrer");
  if (!opened) {
    const a = document.createElement("a");
    a.href = url;
    a.download = `PRESSUPOST_${(numero || pressupostId).replace(/[^\w.-]+/g, "_")}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

// ---------------------------------------------------------------------------
// Modal de Previsualització HTML Oficial (amb accions Editar / PDF / Enviar)
// ---------------------------------------------------------------------------

interface PrevisualitzarPressupostModalProps {
  pressupost: PressupostItem;
  onClose: () => void;
  onEdit?: (pressupost: PressupostItem) => void;
  onSend?: (pressupost: PressupostItem) => void;
  showGoToPressupostosLink?: boolean;
}

export function PrevisualitzarPressupostModal({
  pressupost,
  onClose,
  onEdit,
  onSend,
  showGoToPressupostosLink = false,
}: PrevisualitzarPressupostModalProps) {
  const [htmlDoc, setHtmlDoc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const carregarHtml = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${getApiBaseUrl()}/gestio/pressupostos/${pressupost.id}/html`, {
        headers: buildAuthHeaders(),
        credentials: "include",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `No s'ha pogut carregar la vista prèvia (${res.status}).`);
      }
      const text = await res.text();
      setHtmlDoc(text);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error carregant la vista prèvia HTML.");
    } finally {
      setLoading(false);
    }
  }, [pressupost.id]);

  useEffect(() => {
    carregarHtml();
  }, [carregarHtml]);

  const handlePdf = async () => {
    setDownloadingPdf(true);
    setError(null);
    try {
      await descarregarPdfPressupostAutenticat(pressupost.id, pressupost.numero);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error generant el PDF.");
    } finally {
      setDownloadingPdf(false);
    }
  };

  const editable = pressupost.estat !== "APROVAT";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-primary/60 backdrop-blur-sm p-3 sm:p-5">
      <div className="w-full max-w-5xl h-[92vh] rounded-2xl bg-surface-container-lowest border border-outline-variant/40 shadow-2xl flex flex-col overflow-hidden">
        <div className="px-5 py-3.5 border-b border-outline-variant/30 bg-surface-container-low flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <span className="text-[11px] font-semibold text-secondary block">
              Vista prèvia oficial · {pressupost.numero}
            </span>
            <h3 className="text-sm sm:text-base font-bold text-on-surface truncate">
              {pressupost.titol || pressupost.numero} — {pressupost.client_nom || "Client"}
            </h3>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {editable && onEdit && (
              <button
                type="button"
                onClick={() => onEdit(pressupost)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-xs font-semibold text-on-surface hover:bg-surface-container cursor-pointer"
              >
                <Edit3 className="w-3.5 h-3.5 text-secondary" />
                Editar Pressupost
              </button>
            )}
            <button
              type="button"
              disabled={downloadingPdf}
              onClick={handlePdf}
              className="inline-flex items-center gap-1.5 rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-xs font-semibold text-on-surface hover:bg-surface-container disabled:opacity-50 cursor-pointer"
            >
              <Download className="w-3.5 h-3.5 text-primary" />
              {downloadingPdf ? "Generant PDF..." : "Descarregar PDF"}
            </button>
            {onSend && (
              <button
                type="button"
                onClick={() => onSend(pressupost)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-semibold text-on-primary hover:opacity-90 cursor-pointer"
              >
                <Send className="w-3.5 h-3.5" />
                Enviar al Client
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-on-surface-variant hover:bg-surface-container cursor-pointer"
              title="Tancar"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {error && (
          <div className="mx-5 mt-3 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium">
            {error}
          </div>
        )}

        <div className="flex-1 bg-surface-container overflow-hidden">
          {loading ? (
            <div className="h-full flex items-center justify-center text-xs font-mono text-on-surface-variant animate-pulse">
              Renderitzant plantilla oficial del pressupost...
            </div>
          ) : htmlDoc ? (
            <iframe
              title={`Vista prèvia pressupost ${pressupost.numero}`}
              srcDoc={htmlDoc}
              sandbox="allow-same-origin"
              className="w-full h-full border-0"
            />
          ) : null}
        </div>

        {showGoToPressupostosLink && (
          <div className="px-5 py-2.5 border-t border-outline-variant/30 bg-surface-container-low flex items-center justify-between text-xs">
            <Link
              href="/gestio/pressupostos"
              className="text-primary font-semibold hover:underline inline-flex items-center gap-1"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Anar al llistat de Pressupostos
            </Link>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-outline-variant/60 px-3 py-1.5 font-medium text-on-surface hover:bg-surface-container cursor-pointer"
            >
              Tancar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Modal d'Enviament Multi-Canal (amb accés ràpid a Editar i Previsualitzar)
// ---------------------------------------------------------------------------

interface EnviarPressupostModalProps {
  pressupost: PressupostItem;
  onClose: () => void;
  onSent?: (missatge: string) => void;
  onEdit?: (pressupost: PressupostItem) => void;
  onPreview?: (pressupost: PressupostItem) => void;
  showGoToPressupostosLink?: boolean;
}

export function EnviarPressupostModal({
  pressupost,
  onClose,
  onSent,
  onEdit,
  onPreview,
  showGoToPressupostosLink = false,
}: EnviarPressupostModalProps) {
  const [emailDesti, setEmailDesti] = useState(
    pressupost.email_destinatari || pressupost.client_email || ""
  );
  const [emailAssumpte, setEmailAssumpte] = useState(
    `Pressupost ${pressupost.numero}${pressupost.titol ? ` — ${pressupost.titol}` : ""}`
  );
  const [emailCos, setEmailCos] = useState(
    `Bon dia${pressupost.client_nom ? ` ${pressupost.client_nom}` : ""},\n\n` +
      `Us fem arribar el pressupost ${pressupost.numero}${
        pressupost.titol ? ` (${pressupost.titol})` : ""
      } per un import total de ${Number(pressupost.total || 0).toFixed(2)} €.\n\n` +
      (pressupost.acceptacio_url
        ? `Podeu consultar-lo i acceptar-lo directament en línia aquí:\n${pressupost.acceptacio_url}\n\n`
        : "") +
      `Restem a la vostra disposició per a qualsevol consulta.`
  );
  const [sendingChannel, setSendingChannel] = useState<"EMAIL" | "TELEGRAM" | null>(null);
  const [openingPdf, setOpeningPdf] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mailtoFallback, setMailtoFallback] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  const registrarCanal = async (canal: string, destinatari?: string) => {
    try {
      await apiFetch(`/gestio/pressupostos/${pressupost.id}/registrar-enviament`, {
        method: "POST",
        body: JSON.stringify({ canal, destinatari }),
      });
    } catch {
      // Non-blocking audit mark
    }
  };

  const handleObrirPdf = async () => {
    setOpeningPdf(true);
    setError(null);
    try {
      await descarregarPdfPressupostAutenticat(pressupost.id, pressupost.numero);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error generant el PDF del pressupost.");
    } finally {
      setOpeningPdf(false);
    }
  };

  const handleEnviarEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    setSendingChannel("EMAIL");
    setError(null);
    setMailtoFallback(null);
    try {
      const res = await apiFetch<{
        status: string;
        smtp_enviat: boolean;
        missatge: string;
        mailto_url?: string;
      }>(`/gestio/pressupostos/${pressupost.id}/enviar-email`, {
        method: "POST",
        body: JSON.stringify({
          email_destinatari: emailDesti.trim(),
          assumpte: emailAssumpte.trim(),
          missatge: emailCos.trim(),
        }),
      });
      if (res.smtp_enviat) {
        onSent?.(res.missatge);
        onClose();
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
    setSendingChannel("TELEGRAM");
    setError(null);
    try {
      await apiFetch(`/gestio/pressupostos/${pressupost.id}/enviar-telegram`, {
        method: "POST",
      });
      onSent?.(`Pressupost ${pressupost.numero} enviat per Telegram amb botons d'acceptació.`);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error enviant per Telegram.");
    } finally {
      setSendingChannel(null);
    }
  };

  const handleCopiarEnllac = async () => {
    if (!pressupost.acceptacio_url) return;
    try {
      await navigator.clipboard.writeText(pressupost.acceptacio_url);
      setCopiedLink(true);
      await registrarCanal("ENLLAC");
      onSent?.("Enllaç d'acceptació copiat al porta-retalls.");
    } catch {
      setError("No s'ha pogut copiar automàticament; copia la URL manualment.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-primary/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="w-full max-w-2xl rounded-2xl bg-surface-container-lowest border border-outline-variant/40 p-6 shadow-2xl space-y-5 my-8">
        <div className="flex items-start justify-between gap-3 border-b border-outline-variant/30 pb-3">
          <div>
            <span className="text-[11px] font-semibold text-secondary">
              Enviament de pressupost · {pressupost.numero}
            </span>
            <h3 className="text-lg font-bold text-on-surface mt-0.5">
              {pressupost.titol || pressupost.numero} — {pressupost.client_nom || "Client"}
            </h3>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Import total:{" "}
              <strong className="font-data-tabular text-primary">
                {Number(pressupost.total || 0).toFixed(2)} €
              </strong>
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            {onPreview && (
              <button
                type="button"
                onClick={() => onPreview(pressupost)}
                className="inline-flex items-center gap-1 rounded-lg border border-outline-variant/60 px-2.5 py-1.5 text-xs font-semibold text-on-surface hover:bg-surface-container cursor-pointer"
              >
                <Eye className="w-3.5 h-3.5 text-primary" />
                Previsualitzar
              </button>
            )}
            {pressupost.estat !== "APROVAT" && onEdit && (
              <button
                type="button"
                onClick={() => onEdit(pressupost)}
                className="inline-flex items-center gap-1 rounded-lg border border-outline-variant/60 px-2.5 py-1.5 text-xs font-semibold text-on-surface hover:bg-surface-container cursor-pointer"
              >
                <Edit3 className="w-3.5 h-3.5 text-secondary" />
                Editar abans d&apos;enviar
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1 text-on-surface-variant hover:bg-surface-container cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium">
            {error}
          </div>
        )}

        <form
          onSubmit={handleEnviarEmail}
          className="rounded-xl border border-outline-variant/40 bg-surface p-4 space-y-3 text-xs"
        >
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <h4 className="font-bold text-on-surface flex items-center gap-2">
              <Mail className="w-4 h-4 text-primary" />
              1. Enviar per Correu Electrònic (PDF oficial + Enllaç d&apos;acceptació)
            </h4>
            <button
              type="button"
              disabled={openingPdf}
              onClick={handleObrirPdf}
              className="text-primary hover:underline font-semibold inline-flex items-center gap-1 cursor-pointer disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5" />
              {openingPdf ? "Generant PDF..." : "Descarregar PDF"}
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <div>
              <label className="block font-medium text-on-surface-variant mb-1">
                Email del client *
              </label>
              <input
                type="email"
                required
                value={emailDesti}
                onChange={(e) => setEmailDesti(e.target.value)}
                placeholder="client@empresa.cat"
                className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-on-surface"
              />
            </div>
            <div>
              <label className="block font-medium text-on-surface-variant mb-1">Assumpte *</label>
              <input
                type="text"
                required
                value={emailAssumpte}
                onChange={(e) => setEmailAssumpte(e.target.value)}
                className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-on-surface"
              />
            </div>
          </div>
          <div>
            <label className="block font-medium text-on-surface-variant mb-1">
              Missatge al client
            </label>
            <textarea
              rows={4}
              value={emailCos}
              onChange={(e) => setEmailCos(e.target.value)}
              className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest p-2.5 text-on-surface"
            />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            {mailtoFallback ? (
              <a
                href={mailtoFallback}
                onClick={() => registrarCanal("EMAIL_MANUAL", emailDesti)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3.5 py-2 font-semibold text-white hover:bg-amber-500"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Obrir al meu client de correu (Mailto)
              </a>
            ) : (
              <span className="text-[11px] text-on-surface-variant">
                S&apos;adjuntarà automàticament el PDF oficial generat amb la plantilla corporativa.
              </span>
            )}
            <button
              type="submit"
              disabled={sendingChannel !== null}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 font-semibold text-on-primary hover:opacity-90 disabled:opacity-50 cursor-pointer"
            >
              <Send className="w-3.5 h-3.5" />
              {sendingChannel === "EMAIL" ? "Enviant Email..." : "Enviar per Email"}
            </button>
          </div>
        </form>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div className="rounded-xl border border-outline-variant/40 bg-surface p-4 flex flex-col justify-between space-y-3">
            <div>
              <h4 className="font-bold text-on-surface flex items-center gap-2">
                <Send className="w-4 h-4 text-sky-600" />
                2. Canal Telegram Bot
              </h4>
              <p className="text-[11px] text-on-surface-variant mt-1">
                {pressupost.client_te_telegram
                  ? "El client té Telegram actiu. Rebrà els botons d'acceptació a 1 clic."
                  : "Aquest client encara no ha vinculat el bot de Telegram."}
              </p>
            </div>
            <button
              type="button"
              disabled={!pressupost.client_te_telegram || sendingChannel !== null}
              onClick={handleEnviarTelegram}
              className="w-full rounded-lg bg-sky-600 px-3 py-2 font-semibold text-white hover:bg-sky-500 disabled:opacity-40 cursor-pointer"
            >
              {sendingChannel === "TELEGRAM" ? "Enviant..." : "Enviar per Telegram"}
            </button>
          </div>

          <div className="rounded-xl border border-outline-variant/40 bg-surface p-4 flex flex-col justify-between space-y-3">
            <div>
              <h4 className="font-bold text-on-surface flex items-center gap-2">
                <MessageCircle className="w-4 h-4 text-emerald-600" />
                3. Enllaç Directe / WhatsApp
              </h4>
              <p className="text-[11px] text-on-surface-variant mt-1">
                Comparteix la URL segura perquè el client pugui veure i acceptar el pressupost des del mòbil.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleCopiarEnllac}
                className="flex-1 rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 font-semibold text-on-surface hover:bg-surface-container inline-flex items-center justify-center gap-1 cursor-pointer"
              >
                <Copy className="w-3.5 h-3.5" />
                {copiedLink ? "Copiat!" : "Copiar Enllaç"}
              </button>
              {pressupost.acceptacio_url && (
                <a
                  href={`https://wa.me/${(pressupost.client_telefon || "").replace(/\D/g, "")}?text=${encodeURIComponent(
                    `Bon dia, us enviem el pressupost ${pressupost.numero} (${Number(
                      pressupost.total || 0
                    ).toFixed(2)} €). El podeu consultar i acceptar aquí: ${pressupost.acceptacio_url}`
                  )}`}
                  target="_blank"
                  rel="noreferrer"
                  onClick={() =>
                    registrarCanal("WHATSAPP", pressupost.client_telefon || undefined)
                  }
                  className="rounded-lg bg-emerald-600 px-3 py-2 font-semibold text-white hover:bg-emerald-500 inline-flex items-center gap-1"
                >
                  <MessageCircle className="w-3.5 h-3.5" /> WhatsApp
                </a>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-outline-variant/30 text-xs">
          {showGoToPressupostosLink ? (
            <Link
              href="/gestio/pressupostos"
              className="text-primary font-semibold hover:underline inline-flex items-center gap-1"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Veure tots els Pressupostos
            </Link>
          ) : (
            <span />
          )}
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-outline-variant/60 px-4 py-2 font-medium text-on-surface hover:bg-surface-container cursor-pointer"
          >
            Tancar
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Editor Complet de Pressupost (Creació i Edició abans d'enviar)
// ---------------------------------------------------------------------------

interface PressupostModalProps {
  onClose: () => void;
  onSaved?: (saved: PressupostItem, isNew: boolean, openPreview?: boolean) => void;
  initialPressupost?: PressupostItem | null;
  initialClientId?: string;
  clientsProp?: ClientOption[];
  esEnginyer?: boolean;
  autoOpenSendOnCreate?: boolean;
  showGoToPressupostosLink?: boolean;
}

export function PressupostModal({
  onClose,
  onSaved,
  initialPressupost = null,
  initialClientId = "",
  clientsProp,
  esEnginyer = false,
  autoOpenSendOnCreate = true,
  showGoToPressupostosLink = false,
}: PressupostModalProps) {
  const [editingTarget, setEditingTarget] = useState<PressupostItem | null>(initialPressupost);
  const isEditing = Boolean(editingTarget);

  // Catàlegs reals carregats des de l'API (Zero Mock)
  const [clients, setClients] = useState<ClientOption[]>(clientsProp || []);
  const [finques, setFinques] = useState<FincaOption[]>([]);
  const [articles, setArticles] = useState<ArticleMagatzemOption[]>([]);
  const [vehicles, setVehicles] = useState<VehicleOption[]>([]);
  const [eines, setEines] = useState<EinaOption[]>([]);
  const [barema, setBarema] = useState<BaremaConfigOption | null>(null);
  const [copilotActiu, setCopilotActiu] = useState(false);

  // Capçalera & metadades
  const todayIso = new Date().toISOString().split("T")[0];
  const [formClientId, setFormClientId] = useState(
    editingTarget?.client_id || initialClientId || ""
  );
  const [formNumero, setFormNumero] = useState(
    editingTarget?.numero || `P-${new Date().getFullYear()}/001`
  );
  const [formDataPressupost, setFormDataPressupost] = useState(
    editingTarget?.data_pressupost || todayIso
  );
  const [formValidesa, setFormValidesa] = useState(String(editingTarget?.validesa_dies || 30));
  const [formReferenciaClient, setFormReferenciaClient] = useState(
    editingTarget?.referencia_client || ""
  );
  const [formElaboratPer, setFormElaboratPer] = useState(editingTarget?.elaborat_per || "");

  // Dades autocompletades del client (editables per a aquest document)
  const [clientRaoSocial, setClientRaoSocial] = useState(
    editingTarget?.client_rao_social || editingTarget?.client_nom || ""
  );
  const [clientNif, setClientNif] = useState(editingTarget?.client_nif || "");
  const [clientAdreca, setClientAdreca] = useState(editingTarget?.client_adreca || "");
  const [clientCodiPostal, setClientCodiPostal] = useState(editingTarget?.client_codi_postal || "");
  const [clientPoblacio, setClientPoblacio] = useState(editingTarget?.client_poblacio || "");
  const [clientProvincia, setClientProvincia] = useState(editingTarget?.client_provincia || "");
  const [clientPersonaContacte, setClientPersonaContacte] = useState(
    editingTarget?.client_persona_contacte || ""
  );
  const [clientEmail, setClientEmail] = useState(editingTarget?.client_email || "");
  const [clientTelefon, setClientTelefon] = useState(editingTarget?.client_telefon || "");
  const [clientAutofilledBadge, setClientAutofilledBadge] = useState(false);

  // Objecte i ubicació de la feina
  const [formTitol, setFormTitol] = useState(editingTarget?.titol || "");
  const [formDescripcio, setFormDescripcio] = useState(editingTarget?.descripcio || "");
  const [formFincaId, setFormFincaId] = useState(editingTarget?.finca_id || "");
  const [formAdrecaObra, setFormAdrecaObra] = useState(editingTarget?.adreca_obra || "");

  // Recursos operatius: Vehicle, Desplaçament, Eines
  const [formVehicleId, setFormVehicleId] = useState(editingTarget?.vehicle_id || "");
  const [formDesplacamentKm, setFormDesplacamentKm] = useState(
    editingTarget?.desplacament_km != null ? String(editingTarget.desplacament_km) : ""
  );
  const [formDesplacamentPreuKm, setFormDesplacamentPreuKm] = useState(
    editingTarget?.desplacament_preu_km != null ? String(editingTarget.desplacament_preu_km) : ""
  );
  const [formDesplacamentFix, setFormDesplacamentFix] = useState(
    editingTarget?.desplacament_import_fix != null ? String(editingTarget.desplacament_import_fix) : ""
  );
  const [selectedEinaIds, setSelectedEinaIds] = useState<string[]>(editingTarget?.eines_ids || []);
  const [cercaEina, setCercaEina] = useState("");
  const [einaDropdownOpen, setEinaDropdownOpen] = useState(false);
  const einaBoxRef = useRef<HTMLDivElement>(null);

  // Partides i totals
  const [formDescompteGlobal, setFormDescompteGlobal] = useState(
    String(editingTarget?.descompte_global_pct ?? 0)
  );
  const [formLinies, setFormLinies] = useState<PressupostLinia[]>(() => {
    if (editingTarget?.linies && editingTarget.linies.length > 0) {
      return editingTarget.linies.map((l) => ({ ...l }));
    }
    if (editingTarget) {
      return [
        {
          seccio: "Treballs tècnics",
          tipus_linia: "MA_OBRA",
          concepte: editingTarget.titol || `Pressupost ${editingTarget.numero}`,
          detall: "",
          quantitat: 1,
          preu_unitari: Number(editingTarget.total || 0),
          descompte_pct: 0,
          tipus_iva: 0,
        },
      ];
    }
    return [
      {
        seccio: "Mà d'obra i instal·lació",
        tipus_linia: "MA_OBRA",
        concepte: "",
        detall: "",
        quantitat: 1,
        preu_unitari: 0,
        descompte_pct: 0,
        tipus_iva: 21,
      },
    ];
  });

  // Condicions, notes i exclusions (plantilla oficial)
  const [formFormaPagament, setFormFormaPagament] = useState(
    editingTarget?.forma_pagament || "Transferència bancària"
  );
  const [formPercentatgeAcompte, setFormPercentatgeAcompte] = useState(
    String(editingTarget?.percentatge_acompte ?? 0)
  );
  const [formTerminiExecucio, setFormTerminiExecucio] = useState(
    editingTarget?.termini_execucio || ""
  );
  const [formNotesExclusions, setFormNotesExclusions] = useState(
    editingTarget?.notes_exclusions || ""
  );
  const [formMencioLegal, setFormMencioLegal] = useState(editingTarget?.mencio_legal || "");

  // Cercador de material del magatzem
  const [cercaMaterial, setCercaMaterial] = useState("");
  const [materialDropdownOpen, setMaterialDropdownOpen] = useState(false);
  const [materialQt, setMaterialQt] = useState("1");
  const materialBoxRef = useRef<HTMLDivElement>(null);

  // Estats de procés i flux post-desat (Vista prèvia / Enviament)
  const [saving, setSaving] = useState(false);
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);
  const [previewItem, setPreviewItem] = useState<PressupostItem | null>(null);
  const [sendItem, setSendItem] = useState<PressupostItem | null>(null);

  // Helper per autocompletar totes les dades referents al client
  const aplicarDadesClient = useCallback((cli: ClientOption, overwriteAdrecaObra: boolean) => {
    setClientRaoSocial(cli.rao_social || "");
    setClientNif(cli.nif || "");
    setClientAdreca(cli.adreca_fiscal || "");
    setClientCodiPostal(cli.codi_postal || "");
    setClientPoblacio(cli.poblacio || "");
    setClientProvincia(cli.provincia || "");
    setClientPersonaContacte(cli.persona_contacte || "");
    setClientEmail(cli.email || "");
    setClientTelefon(cli.telefon || "");
    if (overwriteAdrecaObra) {
      const adrecaParts = [
        cli.adreca_fiscal,
        [cli.codi_postal, cli.poblacio].filter(Boolean).join(" "),
        cli.provincia,
      ].filter((p) => p && String(p).trim());
      setFormAdrecaObra(adrecaParts.join(", "));
    }
    setClientAutofilledBadge(true);
  }, []);

  // Càrrega inicial de catàlegs reals
  useEffect(() => {
    const loads: Promise<void>[] = [];

    if (!clientsProp || clientsProp.length === 0) {
      loads.push(
        apiFetch<ClientOption[]>("/gestio/clients?limit=200")
          .then((res) => setClients(Array.isArray(res) ? res : []))
          .catch(() => {})
      );
    }

    loads.push(
      apiFetch<ArticleMagatzemOption[]>("/gestio/magatzem/articles?limit=200")
        .then((res) => setArticles(Array.isArray(res) ? res : []))
        .catch(() => {})
    );

    loads.push(
      apiFetch<VehicleOption[]>("/gestio/flota/vehicles")
        .then((res) => setVehicles(Array.isArray(res) ? res : []))
        .catch(() => {})
    );

    loads.push(
      apiFetch<EinaOption[]>("/gestio/magatzem/eines")
        .then((res) => setEines(Array.isArray(res) ? res : []))
        .catch(() => {})
    );

    loads.push(
      apiFetch<BaremaConfigOption>("/gestio/configuracio/barema")
        .then((b) => {
          if (b) {
            setBarema(b);
            if (!editingTarget && b.suplement_desplacament_eur && b.suplement_desplacament_eur > 0) {
              setFormDesplacamentFix((prev) => (prev ? prev : String(b.suplement_desplacament_eur)));
            }
          }
        })
        .catch(() => {})
    );

    loads.push(
      apiFetch<{ feature_copilot_ia?: boolean; node_ia_actiu?: boolean }>(
        "/gestio/configuracio/empresa"
      )
        .then((cfg) =>
          setCopilotActiu(
            Boolean(cfg?.feature_copilot_ia === true && cfg?.node_ia_actiu === true)
          )
        )
        .catch(() => {})
    );

    if (!editingTarget) {
      loads.push(
        apiFetch<{ numero?: string; elaborat_per?: string | null }>(
          "/gestio/pressupostos/seguent-numero"
        )
          .then((res) => {
            if (res?.numero) setFormNumero(res.numero);
            if (res?.elaborat_per) setFormElaboratPer((prev) => prev || res.elaborat_per || "");
          })
          .catch(() => {})
      );
    }

    Promise.all(loads);
  }, [clientsProp, editingTarget]);

  // Si venim amb initialClientId en creació i arriben els clients, autocompletem automàticament!
  const didInitialAutofill = useRef(false);
  useEffect(() => {
    if (!isEditing && formClientId && clients.length > 0 && !didInitialAutofill.current) {
      const cli = clients.find((c) => c.id === formClientId);
      if (cli) {
        aplicarDadesClient(cli, !formAdrecaObra);
        didInitialAutofill.current = true;
      }
    }
  }, [isEditing, formClientId, clients, formAdrecaObra, aplicarDadesClient]);

  // Carregar finques del client seleccionat
  useEffect(() => {
    if (!formClientId) {
      setFinques([]);
      return;
    }
    apiFetch<FincaOption[]>(`/gestio/clients/${formClientId}/finques`)
      .then((res) => setFinques(Array.isArray(res) ? res : []))
      .catch(() => setFinques([]));
  }, [formClientId]);

  useEffect(() => {
    const onOutsideClick = (e: MouseEvent) => {
      if (materialBoxRef.current && !materialBoxRef.current.contains(e.target as Node)) {
        setMaterialDropdownOpen(false);
      }
      if (einaBoxRef.current && !einaBoxRef.current.contains(e.target as Node)) {
        setEinaDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", onOutsideClick);
    return () => document.removeEventListener("mousedown", onOutsideClick);
  }, []);

  const handleSelectClient = (newClientId: string) => {
    setFormClientId(newClientId);
    setFormFincaId("");
    const cli = clients.find((c) => c.id === newClientId);
    if (cli) {
      aplicarDadesClient(cli, true);
    } else {
      setClientRaoSocial("");
      setClientNif("");
      setClientAdreca("");
      setClientCodiPostal("");
      setClientPoblacio("");
      setClientProvincia("");
      setClientPersonaContacte("");
      setClientEmail("");
      setClientTelefon("");
      setClientAutofilledBadge(false);
    }
  };

  const handleSelectFinca = (fincaId: string) => {
    setFormFincaId(fincaId);
    const finca = finques.find((f) => f.id === fincaId);
    if (finca) {
      const label = [finca.nom, finca.adreca].filter(Boolean).join(" — ");
      if (label) setFormAdrecaObra(label);
    }
  };

  const handleSelectVehicle = (vehId: string) => {
    setFormVehicleId(vehId);
    const veh = vehicles.find((v) => v.id === vehId);
    if (veh && veh.cost_per_km_eur && veh.cost_per_km_eur > 0 && !formDesplacamentPreuKm) {
      setFormDesplacamentPreuKm(String(Number(veh.cost_per_km_eur).toFixed(2)));
    }
  };

  const dataValidesaCalculada = useMemo(() => {
    const baseDate = formDataPressupost ? new Date(`${formDataPressupost}T00:00:00`) : new Date();
    const dies = Math.max(1, Number(formValidesa || 30));
    baseDate.setDate(baseDate.getDate() + dies);
    return baseDate.toLocaleDateString("ca-ES");
  }, [formDataPressupost, formValidesa]);

  const articlesFiltrats = useMemo(() => {
    const q = cercaMaterial.trim().toLowerCase();
    const list = q
      ? articles.filter(
          (a) =>
            (a.nom || "").toLowerCase().includes(q) ||
            (a.referencia_inventari || "").toLowerCase().includes(q)
        )
      : articles;
    return list.slice(0, 12);
  }, [articles, cercaMaterial]);

  const einesFiltrades = useMemo(() => {
    const q = cercaEina.trim().toLowerCase();
    return eines
      .filter((e) => !selectedEinaIds.includes(e.id))
      .filter((e) => {
        if (!q) return true;
        return (
          (e.nom || "").toLowerCase().includes(q) ||
          (e.model || "").toLowerCase().includes(q) ||
          (e.numero_serie || "").toLowerCase().includes(q)
        );
      })
      .slice(0, 10);
  }, [eines, selectedEinaIds, cercaEina]);

  const selectedVehicleObj = useMemo(
    () => vehicles.find((v) => v.id === formVehicleId) || null,
    [vehicles, formVehicleId]
  );

  const selectedEinesObjs = useMemo(() => {
    const map = new Map(eines.map((e) => [e.id, e]));
    return selectedEinaIds.map((id) => {
      const found = map.get(id);
      if (found) return found;
      const fromSaved = editingTarget?.eines_resum?.find((er) => er.id === id);
      return fromSaved || { id, nom: "Eina seleccionada" };
    });
  }, [eines, selectedEinaIds, editingTarget]);

  const editorTotals = useMemo(() => {
    const basesBrutesPerIva: Record<string, number> = {};
    for (const l of formLinies) {
      const sub = r2(
        Number(l.quantitat || 0) *
          Number(l.preu_unitari || 0) *
          (1 - Number(l.descompte_pct || 0) / 100)
      );
      const key = String(Number(l.tipus_iva ?? 21));
      basesBrutesPerIva[key] = (basesBrutesPerIva[key] || 0) + sub;
    }
    const subtotalBrut = r2(Object.values(basesBrutesPerIva).reduce((a, b) => a + b, 0));
    const dtoGlobalPct = Math.min(100, Math.max(0, Number(formDescompteGlobal || 0)));
    const factorGlobal = 1 - dtoGlobalPct / 100;

    let base = 0;
    let iva = 0;
    for (const [k, bBrut] of Object.entries(basesBrutesPerIva)) {
      const bNet = r2(bBrut * factorGlobal);
      base += bNet;
      iva += r2(bNet * (Number(k) / 100));
    }
    base = r2(base);
    iva = r2(iva);
    const descompteGlobalImport = r2(subtotalBrut - base);
    const total = r2(base + iva);
    const pctAcompte = Math.min(100, Math.max(0, Number(formPercentatgeAcompte || 0)));
    const importAcompte = r2((total * pctAcompte) / 100);
    return {
      subtotalBrut,
      dtoGlobalPct,
      descompteGlobalImport,
      base,
      iva,
      total,
      importAcompte,
    };
  }, [formLinies, formDescompteGlobal, formPercentatgeAcompte]);

  const afegirLinia = (novaLinia: PressupostLinia) => {
    setFormLinies((prev) => {
      if (prev.length === 1 && !prev[0].concepte.trim() && Number(prev[0].preu_unitari) === 0) {
        return [novaLinia];
      }
      return [...prev, novaLinia];
    });
  };

  const afegirMaterialMagatzem = (art: ArticleMagatzemOption) => {
    const qt = Math.max(0.01, Number(materialQt || 1));
    afegirLinia({
      article_id: art.id,
      seccio: "Materials i subministraments",
      tipus_linia: "MATERIAL",
      concepte: `[${art.referencia_inventari}] ${art.nom}`,
      detall: art.unitat_mesura ? `Unitat: ${art.unitat_mesura}` : "",
      quantitat: qt,
      preu_unitari: esEnginyer ? 0 : Number(art.preu_venda || 0),
      descompte_pct: 0,
      tipus_iva: 21,
    });
    setCercaMaterial("");
    setMaterialQt("1");
    setMaterialDropdownOpen(false);
  };

  const afegirPartidaDesplacament = () => {
    const km = Number(formDesplacamentKm || 0);
    const preuKm = Number(formDesplacamentPreuKm || 0);
    const fix = Number(formDesplacamentFix || 0);
    const vehLabel = selectedVehicleObj
      ? [selectedVehicleObj.matricula, selectedVehicleObj.marca, selectedVehicleObj.model]
          .filter(Boolean)
          .join(" · ")
      : "";

    if (km > 0 && preuKm > 0) {
      afegirLinia({
        vehicle_id: formVehicleId || null,
        seccio: "Desplaçament i vehicle",
        tipus_linia: "DESPLACAMENT",
        concepte: vehLabel ? `Desplaçament (${vehLabel})` : "Desplaçament i transport",
        detall: `${km} km a ${preuKm.toFixed(2)} €/km${fix > 0 ? ` (+ tarifa base ${fix.toFixed(2)} €)` : ""}`,
        quantitat: fix > 0 ? 1 : km,
        preu_unitari: esEnginyer ? 0 : fix > 0 ? r2(km * preuKm + fix) : preuKm,
        descompte_pct: 0,
        tipus_iva: 21,
      });
    } else {
      afegirLinia({
        vehicle_id: formVehicleId || null,
        seccio: "Desplaçament i vehicle",
        tipus_linia: "DESPLACAMENT",
        concepte: vehLabel ? `Desplaçament (${vehLabel})` : "Desplaçament",
        detall: km > 0 ? `Trajecte previst: ${km} km` : "Desplaçament de l'equip tècnic al lloc d'obra",
        quantitat: 1,
        preu_unitari: esEnginyer ? 0 : Math.max(0, fix),
        descompte_pct: 0,
        tipus_iva: 21,
      });
    }
    setInfoMsg("Partida de desplaçament afegida a la taula.");
  };

  const afegirPartidaEines = () => {
    if (selectedEinesObjs.length === 0) {
      afegirLinia({
        seccio: "Eines i maquinària",
        tipus_linia: "EINA",
        concepte: "Ús d'eines i maquinària especialitzada",
        detall: "",
        quantitat: 1,
        preu_unitari: 0,
        descompte_pct: 0,
        tipus_iva: 21,
      });
      return;
    }
    const detallEines = selectedEinesObjs
      .map((e) => [e.nom, e.model, e.numero_serie ? `S/N ${e.numero_serie}` : null].filter(Boolean).join(" · "))
      .join(" | ");
    afegirLinia({
      eina_id: selectedEinesObjs.length === 1 ? selectedEinesObjs[0].id : null,
      seccio: "Eines i maquinària",
      tipus_linia: "EINA",
      concepte:
        selectedEinesObjs.length === 1
          ? `Ús de maquinària: ${selectedEinesObjs[0].nom}`
          : `Ús d'eines i maquinària (${selectedEinesObjs.length} equips)`,
      detall: detallEines,
      quantitat: 1,
      preu_unitari: 0,
      descompte_pct: 0,
      tipus_iva: 21,
    });
    setInfoMsg("Partida d'eines i maquinària afegida a la taula.");
  };

  const afegirPartidaMaObra = () => {
    const preuHora = esEnginyer ? 0 : Number(barema?.preu_hora_standard_eur || 0);
    afegirLinia({
      seccio: "Mà d'obra i instal·lació",
      tipus_linia: "MA_OBRA",
      concepte: "Mà d'obra tècnica especialitzada",
      detall: "Hores de muntatge, instal·lació i posada en marxa",
      quantitat: 1,
      preu_unitari: preuHora,
      descompte_pct: 0,
      tipus_iva: 21,
    });
  };

  const handlePropostaCopilot = async () => {
    const basePrompt = [formTitol.trim(), formDescripcio.trim()].filter(Boolean).join(" — ");
    if (!basePrompt) {
      setError("Escriu un títol o descripció de la feina perquè el Copilot IA redacti partides.");
      return;
    }
    setCopilotLoading(true);
    setError(null);
    setInfoMsg(null);
    try {
      const q = new URLSearchParams({ prompt: basePrompt });
      if (formClientId) q.set("client_id", formClientId);
      const res = await apiFetch<{
        draft?: {
          titol?: string;
          resum_tecnic?: string;
          linies?: Array<{
            seccio?: string;
            tipus_linia?: string;
            concepte: string;
            quantitat?: number;
            preu_unitari?: number | null;
          }>;
        };
        missatge?: string;
      }>(`/gestio/pressupostos/generar-ia?${q.toString()}`, { method: "POST" });

      if (res?.draft?.linies && res.draft.linies.length > 0) {
        setFormLinies(
          res.draft.linies.map((l) => ({
            seccio: l.seccio || "Materials i subministraments",
            tipus_linia: l.tipus_linia || "ALTRE",
            concepte: l.concepte,
            detall: "",
            quantitat: Math.max(0.01, Number(l.quantitat || 1)),
            preu_unitari: esEnginyer ? 0 : Number(l.preu_unitari ?? 0),
            descompte_pct: 0,
            tipus_iva: 21,
          }))
        );
        if (!formDescripcio.trim() && res.draft.resum_tecnic) {
          setFormDescripcio(res.draft.resum_tecnic);
        }
        setInfoMsg(res.missatge || "Partides proposades pel Copilot IA carregades per revisió HITL.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "El Node IA local no ha respost.");
    } finally {
      setCopilotLoading(false);
    }
  };

  const desarPressupost = async (accioPostDesat: "PREVIEW" | "CLOSE") => {
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
    try {
      const payloadLinies = liniesValides.map((l) => ({
        article_id: l.article_id || null,
        vehicle_id: l.vehicle_id || null,
        eina_id: l.eina_id || null,
        seccio: l.seccio?.trim() || null,
        tipus_linia: l.tipus_linia || "ALTRE",
        concepte: l.concepte.trim(),
        detall: l.detall?.trim() || null,
        quantitat: Math.max(0.01, Number(l.quantitat || 1)),
        preu_unitari: Math.max(0, Number(l.preu_unitari || 0)),
        descompte_pct: Math.min(100, Math.max(0, Number(l.descompte_pct || 0))),
        tipus_iva: Math.max(0, Number(l.tipus_iva ?? 21)),
      }));

      const commonBody = {
        client_id: formClientId,
        numero: formNumero.trim(),
        titol: formTitol.trim() || `Pressupost ${formNumero.trim()}`,
        descripcio: formDescripcio.trim() || null,
        data_pressupost: formDataPressupost || null,
        validesa_dies: Math.max(1, Number(formValidesa || 30)),
        referencia_client: formReferenciaClient.trim() || null,
        elaborat_per: formElaboratPer.trim() || null,
        client_rao_social: clientRaoSocial.trim() || null,
        client_nif: clientNif.trim() || null,
        client_adreca: clientAdreca.trim() || null,
        client_codi_postal: clientCodiPostal.trim() || null,
        client_poblacio: clientPoblacio.trim() || null,
        client_provincia: clientProvincia.trim() || null,
        client_persona_contacte: clientPersonaContacte.trim() || null,
        client_email: clientEmail.trim() || null,
        client_telefon: clientTelefon.trim() || null,
        finca_id: formFincaId || null,
        adreca_obra: formAdrecaObra.trim() || null,
        vehicle_id: formVehicleId || null,
        vehicle_nom: selectedVehicleObj
          ? [selectedVehicleObj.matricula, selectedVehicleObj.marca, selectedVehicleObj.model]
              .filter(Boolean)
              .join(" · ")
          : null,
        eines_ids: selectedEinaIds,
        desplacament_km: formDesplacamentKm !== "" ? Number(formDesplacamentKm) : null,
        desplacament_preu_km: formDesplacamentPreuKm !== "" ? Number(formDesplacamentPreuKm) : null,
        desplacament_import_fix: formDesplacamentFix !== "" ? Number(formDesplacamentFix) : null,
        descompte_global_pct: Math.min(100, Math.max(0, Number(formDescompteGlobal || 0))),
        forma_pagament: formFormaPagament.trim() || null,
        percentatge_acompte: Math.min(100, Math.max(0, Number(formPercentatgeAcompte || 0))),
        termini_execucio: formTerminiExecucio.trim() || null,
        notes_exclusions: formNotesExclusions.trim() || null,
        mencio_legal: formMencioLegal.trim() || null,
        total: editorTotals.total,
        linies: payloadLinies,
      };

      let saved: PressupostItem;
      const wasNew = !isEditing;
      if (isEditing && editingTarget) {
        saved = await apiFetch<PressupostItem>(`/gestio/pressupostos/${editingTarget.id}`, {
          method: "PUT",
          body: JSON.stringify(commonBody),
        });
      } else {
        saved = await apiFetch<PressupostItem>("/gestio/pressupostos", {
          method: "POST",
          body: JSON.stringify(commonBody),
        });
      }

      setEditingTarget(saved);
      onSaved?.(saved, wasNew, accioPostDesat === "PREVIEW");

      if (accioPostDesat === "PREVIEW") {
        setPreviewItem(saved);
      } else if (wasNew && autoOpenSendOnCreate) {
        setPreviewItem(saved);
      } else {
        onClose();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en desar el pressupost.");
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await desarPressupost("PREVIEW");
  };

  if (previewItem) {
    return (
      <PrevisualitzarPressupostModal
        pressupost={previewItem}
        onClose={onClose}
        onEdit={(p) => {
          setEditingTarget(p);
          setPreviewItem(null);
        }}
        onSend={(p) => {
          setPreviewItem(null);
          setSendItem(p);
        }}
        showGoToPressupostosLink={showGoToPressupostosLink}
      />
    );
  }

  if (sendItem) {
    return (
      <EnviarPressupostModal
        pressupost={sendItem}
        onClose={onClose}
        onPreview={(p) => {
          setSendItem(null);
          setPreviewItem(p);
        }}
        onEdit={(p) => {
          setEditingTarget(p);
          setSendItem(null);
        }}
        showGoToPressupostosLink={showGoToPressupostosLink}
      />
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-primary/60 backdrop-blur-sm p-3 sm:p-4 overflow-y-auto">
      <div className="w-full max-w-5xl max-h-[94vh] rounded-2xl bg-surface-container-lowest border border-outline-variant/40 shadow-2xl flex flex-col overflow-hidden">
        {/* Capçalera fixa del modal */}
        <div className="px-6 py-4 flex items-center justify-between border-b border-outline-variant/30 bg-surface-container-low shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary text-on-primary flex items-center justify-center shadow-sm">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-on-surface">
                {isEditing ? `Editar Pressupost ${formNumero}` : "Nou Pressupost Detallat"}
              </h3>
              <p className="text-[11px] text-on-surface-variant">
                Completa el client, descripció, vehicle, eines, desplaçament i partides. Podràs previsualitzar i editar el document abans d&apos;enviar-lo.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-on-surface-variant hover:bg-surface-container cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Cos scrollable */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-6 py-5 space-y-5 text-xs">
          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium">
              {error}
            </div>
          )}

          {infoMsg && (
            <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{infoMsg}</span>
            </div>
          )}

          {/* 1. CLIENT I METADADES DEL PRESSUPOST */}
          <section className="rounded-xl border border-outline-variant/40 bg-surface p-4 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h4 className="font-bold text-on-surface flex items-center gap-2 text-xs">
                <Building2 className="w-4 h-4 text-primary" />
                Dades del document i client
              </h4>
              {clientAutofilledBadge && (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 text-emerald-800 px-2.5 py-0.5 text-[10px] font-semibold">
                  <CheckCircle2 className="w-3 h-3" /> Dades del client autocompletades
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="sm:col-span-2">
                <label className="block font-semibold text-on-surface mb-1">Client *</label>
                <select
                  required
                  value={formClientId}
                  onChange={(e) => handleSelectClient(e.target.value)}
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-on-surface"
                >
                  <option value="">Selecciona un client...</option>
                  {clients.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.rao_social} ({c.nif})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Número pressupost *
                </label>
                <input
                  required
                  disabled={Boolean(editingTarget?.canal_enviament)}
                  value={formNumero}
                  onChange={(e) => setFormNumero(e.target.value)}
                  placeholder="P-2026/001"
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 font-mono text-on-surface disabled:opacity-60"
                />
              </div>
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Data pressupost
                </label>
                <input
                  type="date"
                  value={formDataPressupost}
                  onChange={(e) => setFormDataPressupost(e.target.value)}
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-on-surface"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Validesa (dies){" "}
                  <span className="font-normal text-on-surface-variant">
                    · fins al {dataValidesaCalculada}
                  </span>
                </label>
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={formValidesa}
                  onChange={(e) => setFormValidesa(e.target.value)}
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-on-surface"
                />
              </div>
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Referència del client
                </label>
                <input
                  value={formReferenciaClient}
                  onChange={(e) => setFormReferenciaClient(e.target.value)}
                  placeholder="Ex: SOL-2026-14 / Obra Nord"
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-on-surface"
                />
              </div>
              <div>
                <label className="block font-semibold text-on-surface mb-1">Elaborat per</label>
                <input
                  value={formElaboratPer}
                  onChange={(e) => setFormElaboratPer(e.target.value)}
                  placeholder="Nom del tècnic o responsable"
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-on-surface"
                />
              </div>
            </div>

            {/* Fitxa autocompletada del client */}
            {formClientId && (
              <div className="rounded-lg border border-outline-variant/40 bg-surface-container-lowest p-3 space-y-2.5">
                <div className="text-[11px] font-semibold text-on-surface-variant">
                  Dades fiscals i de contacte del client al document (autocompletades, editables si cal)
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  <div>
                    <label className="block text-[11px] text-on-surface-variant mb-0.5">
                      Raó social / Nom
                    </label>
                    <input
                      value={clientRaoSocial}
                      onChange={(e) => setClientRaoSocial(e.target.value)}
                      className="w-full rounded-md border border-outline-variant/50 bg-surface px-2.5 py-1.5 text-on-surface"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-on-surface-variant mb-0.5">
                      NIF / CIF
                    </label>
                    <input
                      value={clientNif}
                      onChange={(e) => setClientNif(e.target.value)}
                      className="w-full rounded-md border border-outline-variant/50 bg-surface px-2.5 py-1.5 font-mono text-on-surface"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-on-surface-variant mb-0.5">
                      Persona de contacte
                    </label>
                    <input
                      value={clientPersonaContacte}
                      onChange={(e) => setClientPersonaContacte(e.target.value)}
                      placeholder="Atenció a..."
                      className="w-full rounded-md border border-outline-variant/50 bg-surface px-2.5 py-1.5 text-on-surface"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-[11px] text-on-surface-variant mb-0.5">
                      Adreça fiscal
                    </label>
                    <input
                      value={clientAdreca}
                      onChange={(e) => setClientAdreca(e.target.value)}
                      className="w-full rounded-md border border-outline-variant/50 bg-surface px-2.5 py-1.5 text-on-surface"
                    />
                  </div>
                  <div className="grid grid-cols-3 gap-1.5">
                    <div>
                      <label className="block text-[11px] text-on-surface-variant mb-0.5">CP</label>
                      <input
                        value={clientCodiPostal}
                        onChange={(e) => setClientCodiPostal(e.target.value)}
                        className="w-full rounded-md border border-outline-variant/50 bg-surface px-2 py-1.5 text-on-surface"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] text-on-surface-variant mb-0.5">
                        Població
                      </label>
                      <input
                        value={clientPoblacio}
                        onChange={(e) => setClientPoblacio(e.target.value)}
                        className="w-full rounded-md border border-outline-variant/50 bg-surface px-2 py-1.5 text-on-surface"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] text-on-surface-variant mb-0.5">
                        Província
                      </label>
                      <input
                        value={clientProvincia}
                        onChange={(e) => setClientProvincia(e.target.value)}
                        className="w-full rounded-md border border-outline-variant/50 bg-surface px-2 py-1.5 text-on-surface"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-[11px] text-on-surface-variant mb-0.5">
                      Email client
                    </label>
                    <input
                      type="email"
                      value={clientEmail}
                      onChange={(e) => setClientEmail(e.target.value)}
                      className="w-full rounded-md border border-outline-variant/50 bg-surface px-2.5 py-1.5 text-on-surface"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-on-surface-variant mb-0.5">
                      Telèfon client
                    </label>
                    <input
                      value={clientTelefon}
                      onChange={(e) => setClientTelefon(e.target.value)}
                      className="w-full rounded-md border border-outline-variant/50 bg-surface px-2.5 py-1.5 text-on-surface"
                    />
                  </div>
                  {finques.length > 0 && (
                    <div>
                      <label className="block text-[11px] text-on-surface-variant mb-0.5">
                        Finca / Instal·lació del client
                      </label>
                      <select
                        value={formFincaId}
                        onChange={(e) => handleSelectFinca(e.target.value)}
                        className="w-full rounded-md border border-outline-variant/50 bg-surface px-2.5 py-1.5 text-on-surface"
                      >
                        <option value="">Selecciona finca (opcional)...</option>
                        {finques.map((f) => (
                          <option key={f.id} value={f.id}>
                            {f.nom}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              </div>
            )}
          </section>

          {/* 2. OBJECTE I DESCRIPCIÓ DE LA FEINA */}
          <section className="rounded-xl border border-outline-variant/40 bg-surface p-4 space-y-3">
            <h4 className="font-bold text-on-surface flex items-center gap-2 text-xs">
              <FileText className="w-4 h-4 text-primary" />
              Objecte i descripció de la feina
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Títol del projecte o servei *
                </label>
                <input
                  required
                  value={formTitol}
                  onChange={(e) => setFormTitol(e.target.value)}
                  placeholder="Ex: Instal·lació de reg automatitzat i posada en marxa"
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-on-surface"
                />
              </div>
              <div>
                <label className="block font-semibold text-on-surface mb-1 flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-on-surface-variant" />
                  Adreça / ubicació dels treballs
                </label>
                <input
                  value={formAdrecaObra}
                  onChange={(e) => setFormAdrecaObra(e.target.value)}
                  placeholder="Autocompletada del client o finca..."
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-on-surface"
                />
              </div>
            </div>
            <div>
              <label className="block font-semibold text-on-surface mb-1">
                Descripció general de la feina i abast tècnic
              </label>
              <textarea
                rows={3}
                value={formDescripcio}
                onChange={(e) => setFormDescripcio(e.target.value)}
                placeholder="Detalla els treballs a executar, abast de la intervenció, proves de funcionament i requisits previs..."
                className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest p-2.5 text-on-surface"
              />
            </div>
          </section>

          {/* 3. RECURSOS OPERATIUS: VEHICLE, DESPLAÇAMENT I EINES */}
          <section className="rounded-xl border border-outline-variant/40 bg-surface p-4 space-y-3">
            <h4 className="font-bold text-on-surface flex items-center gap-2 text-xs">
              <Truck className="w-4 h-4 text-primary" />
              Recursos previstos: vehicle, desplaçament i eines
            </h4>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Vehicle i Desplaçament */}
              <div className="rounded-lg border border-outline-variant/40 bg-surface-container-lowest p-3 space-y-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-on-surface flex items-center gap-1.5">
                    <Navigation className="w-3.5 h-3.5 text-primary" />
                    Vehicle i desplaçament
                  </span>
                  <button
                    type="button"
                    onClick={afegirPartidaDesplacament}
                    className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2.5 py-1 text-[11px] font-semibold text-primary hover:bg-primary/20 cursor-pointer"
                  >
                    <Plus className="w-3 h-3" /> Afegir partida desplaçament
                  </button>
                </div>

                <div>
                  <label className="block text-[11px] text-on-surface-variant mb-1">
                    Vehicle assignat previst
                  </label>
                  <select
                    value={formVehicleId}
                    onChange={(e) => handleSelectVehicle(e.target.value)}
                    className="w-full rounded-lg border border-outline-variant/60 bg-surface px-2.5 py-1.5 text-on-surface"
                  >
                    <option value="">Cap vehicle seleccionat...</option>
                    {vehicles.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.matricula}
                        {v.marca || v.model ? ` — ${[v.marca, v.model].filter(Boolean).join(" ")}` : ""}
                        {v.cost_per_km_eur && v.cost_per_km_eur > 0
                          ? ` (${Number(v.cost_per_km_eur).toFixed(2)} €/km)`
                          : ""}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-[11px] text-on-surface-variant mb-0.5">
                      Distància (km)
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      value={formDesplacamentKm}
                      onChange={(e) => setFormDesplacamentKm(e.target.value)}
                      placeholder="Ex: 40"
                      className="w-full rounded-md border border-outline-variant/60 bg-surface px-2 py-1.5 tabular-nums text-on-surface"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-on-surface-variant mb-0.5">
                      Preu €/km
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={formDesplacamentPreuKm}
                      onChange={(e) => setFormDesplacamentPreuKm(e.target.value)}
                      placeholder="Ex: 0.45"
                      className="w-full rounded-md border border-outline-variant/60 bg-surface px-2 py-1.5 tabular-nums text-on-surface"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-on-surface-variant mb-0.5">
                      Tarifa fixa (€)
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      value={formDesplacamentFix}
                      onChange={(e) => setFormDesplacamentFix(e.target.value)}
                      placeholder="Ex: 35.00"
                      className="w-full rounded-md border border-outline-variant/60 bg-surface px-2 py-1.5 tabular-nums text-on-surface"
                    />
                  </div>
                </div>
              </div>

              {/* Eines i Maquinària */}
              <div
                className="rounded-lg border border-outline-variant/40 bg-surface-container-lowest p-3 space-y-2.5"
                ref={einaBoxRef}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-on-surface flex items-center gap-1.5">
                    <Wrench className="w-3.5 h-3.5 text-primary" />
                    Eines i maquinària prevista
                  </span>
                  <button
                    type="button"
                    onClick={afegirPartidaEines}
                    className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2.5 py-1 text-[11px] font-semibold text-primary hover:bg-primary/20 cursor-pointer"
                  >
                    <Plus className="w-3 h-3" /> Afegir partida eines
                  </button>
                </div>

                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-on-surface-variant absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    type="text"
                    value={cercaEina}
                    onFocus={() => setEinaDropdownOpen(true)}
                    onChange={(e) => {
                      setCercaEina(e.target.value);
                      setEinaDropdownOpen(true);
                    }}
                    placeholder={
                      eines.length > 0
                        ? "Cercar eina o maquinària de l'inventari..."
                        : "No hi ha eines registrades al magatzem"
                    }
                    className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-outline-variant/60 bg-surface text-on-surface"
                  />
                  {einaDropdownOpen && einesFiltrades.length > 0 && (
                    <div className="absolute left-0 right-0 top-full mt-1 z-30 max-h-44 overflow-y-auto rounded-xl border border-outline-variant/60 bg-surface-container-lowest shadow-xl divide-y divide-outline-variant/20">
                      {einesFiltrades.map((eina) => (
                        <button
                          key={eina.id}
                          type="button"
                          onClick={() => {
                            setSelectedEinaIds((prev) => [...prev, eina.id]);
                            setCercaEina("");
                            setEinaDropdownOpen(false);
                          }}
                          className="w-full px-3 py-2 text-left hover:bg-surface-container flex items-center justify-between gap-2 cursor-pointer"
                        >
                          <div className="min-w-0">
                            <span className="font-medium text-on-surface">{eina.nom}</span>
                            {eina.model && (
                              <span className="ml-1.5 text-[10px] text-on-surface-variant">
                                ({eina.model})
                              </span>
                            )}
                          </div>
                          {eina.numero_serie && (
                            <span className="font-mono text-[10px] text-on-surface-variant shrink-0">
                              S/N {eina.numero_serie}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {selectedEinesObjs.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {selectedEinesObjs.map((eina) => (
                      <span
                        key={eina.id}
                        className="inline-flex items-center gap-1 rounded-full bg-primary/10 text-primary px-2.5 py-1 text-[11px] font-medium"
                      >
                        <span>
                          {eina.nom}
                          {eina.model ? ` · ${eina.model}` : ""}
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            setSelectedEinaIds((prev) => prev.filter((id) => id !== eina.id))
                          }
                          className="hover:text-rose-600 cursor-pointer"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-on-surface-variant">
                    Selecciona eines de l&apos;inventari per incloure-les al document i traspassar-les a l&apos;OT.
                  </p>
                )}
              </div>
            </div>
          </section>

          {/* 4. PARTIDES DEL PRESSUPOST (SECCIONS, MATERIALS, MÀ D'OBRA, COPILOT) */}
          <section className="space-y-3">
            <div className="rounded-xl border border-outline-variant/40 bg-surface p-3 space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-bold text-xs text-on-surface flex items-center gap-1.5">
                  <Package className="w-4 h-4 text-primary" />
                  Partides del pressupost
                </span>
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    type="button"
                    onClick={afegirPartidaMaObra}
                    className="inline-flex items-center gap-1 rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-2.5 py-1.5 font-semibold text-on-surface hover:bg-surface-container cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5 text-primary" /> Mà d&apos;obra
                    {!esEnginyer && barema?.preu_hora_standard_eur
                      ? ` (${Number(barema.preu_hora_standard_eur).toFixed(2)} €/h)`
                      : ""}
                  </button>
                  {copilotActiu && (
                    <button
                      type="button"
                      disabled={copilotLoading}
                      onClick={handlePropostaCopilot}
                      className="inline-flex items-center gap-1 rounded-lg bg-secondary-container px-2.5 py-1.5 font-semibold text-on-secondary-container hover:opacity-90 cursor-pointer disabled:opacity-50"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      {copilotLoading ? "Consultant IA..." : "Proposta Copilot IA"}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() =>
                      setFormLinies((prev) => [
                        ...prev,
                        {
                          seccio: prev[prev.length - 1]?.seccio || "Altres conceptes",
                          tipus_linia: "ALTRE",
                          concepte: "",
                          detall: "",
                          quantitat: 1,
                          preu_unitari: 0,
                          descompte_pct: 0,
                          tipus_iva: 21,
                        },
                      ])
                    }
                    className="inline-flex items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1.5 font-semibold text-primary hover:bg-primary/20 cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" /> Afegir línia
                  </button>
                </div>
              </div>

              {articles.length > 0 && (
                <div className="flex flex-col sm:flex-row gap-2" ref={materialBoxRef}>
                  <div className="relative flex-1">
                    <Search className="w-3.5 h-3.5 text-on-surface-variant absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type="text"
                      value={cercaMaterial}
                      onFocus={() => setMaterialDropdownOpen(true)}
                      onChange={(e) => {
                        setCercaMaterial(e.target.value);
                        setMaterialDropdownOpen(true);
                      }}
                      placeholder="Cercar material del magatzem per nom o referència per afegir-lo..."
                      className="w-full pl-8 pr-3 py-2 rounded-lg border border-outline-variant/60 bg-surface-container-lowest text-on-surface"
                    />
                    {materialDropdownOpen && articlesFiltrats.length > 0 && (
                      <div className="absolute left-0 right-0 top-full mt-1 z-30 max-h-52 overflow-y-auto rounded-xl border border-outline-variant/60 bg-surface-container-lowest shadow-xl divide-y divide-outline-variant/20">
                        {articlesFiltrats.map((art) => (
                          <button
                            key={art.id}
                            type="button"
                            onClick={() => afegirMaterialMagatzem(art)}
                            className="w-full px-3 py-2 text-left hover:bg-surface-container flex items-center justify-between gap-2 cursor-pointer"
                          >
                            <div className="min-w-0">
                              <span className="font-mono text-[10px] font-bold text-primary mr-1.5">
                                [{art.referencia_inventari}]
                              </span>
                              <span className="font-medium text-on-surface">{art.nom}</span>
                              {art.estoc_disponible !== undefined && (
                                <span className="ml-2 text-[10px] text-on-surface-variant">
                                  Estoc: {Number(art.estoc_disponible).toFixed(2)}{" "}
                                  {art.unitat_mesura || "uts"}
                                </span>
                              )}
                            </div>
                            {!esEnginyer && (
                              <span className="font-data-tabular font-bold text-secondary shrink-0">
                                {Number(art.preu_venda || 0).toFixed(2)} €
                              </span>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="w-24">
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      value={materialQt}
                      onChange={(e) => setMaterialQt(e.target.value)}
                      title="Quantitat a afegir"
                      placeholder="Qt."
                      className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-2.5 py-2 tabular-nums text-on-surface"
                    />
                  </div>
                </div>
              )}

              {barema?.partides && barema.partides.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap pt-1">
                  <span className="text-[11px] text-on-surface-variant font-medium">
                    Partides del barema:
                  </span>
                  {barema.partides.slice(0, 6).map((p) => (
                    <button
                      key={p.codi}
                      type="button"
                      onClick={() =>
                        afegirLinia({
                          seccio: "Mà d'obra i instal·lació",
                          tipus_linia: "MA_OBRA",
                          concepte: `${p.descripcio} (${p.codi})`,
                          detall: `Unitat: ${p.unitat}`,
                          quantitat: 1,
                          preu_unitari: esEnginyer ? 0 : Number(p.preu_eur || 0),
                          descompte_pct: 0,
                          tipus_iva: 21,
                        })
                      }
                      className="rounded-full border border-outline-variant/60 bg-surface-container-lowest px-2.5 py-0.5 text-[11px] text-on-surface hover:bg-surface-container cursor-pointer"
                    >
                      + {p.descripcio}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <datalist id="seccions-pressupost-list">
              {SECCIONS_SUGGERIDES.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>

            <div className="overflow-x-auto rounded-xl border border-outline-variant/40">
              <table className="w-full text-left">
                <thead className="bg-surface-container-low text-on-surface-variant">
                  <tr>
                    <th className="px-2.5 py-2 w-40">Secció</th>
                    <th className="px-2.5 py-2 min-w-[230px]">Concepte i detall</th>
                    <th className="px-2 py-2 w-20">Qt.</th>
                    {!esEnginyer && (
                      <>
                        <th className="px-2 py-2 w-24">Preu u. (€)</th>
                        <th className="px-2 py-2 w-16">Dto %</th>
                        <th className="px-2 py-2 w-20">IVA %</th>
                        <th className="px-2 py-2 w-24 text-right">Import</th>
                      </>
                    )}
                    <th className="px-2 py-2 w-10"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant/25">
                  {formLinies.map((lin, idx) => {
                    const sub = r2(
                      Number(lin.quantitat || 0) *
                        Number(lin.preu_unitari || 0) *
                        (1 - Number(lin.descompte_pct || 0) / 100)
                    );
                    return (
                      <tr key={idx} className="align-top">
                        <td className="px-2.5 py-2">
                          <input
                            type="text"
                            list="seccions-pressupost-list"
                            value={lin.seccio || ""}
                            onChange={(e) =>
                              setFormLinies((prev) =>
                                prev.map((it, i) =>
                                  i === idx ? { ...it, seccio: e.target.value } : it
                                )
                              )
                            }
                            placeholder="Opcional..."
                            className="w-full rounded border border-outline-variant/60 bg-surface-container-lowest px-2 py-1 text-[11px] text-on-surface"
                          />
                        </td>
                        <td className="px-2.5 py-2 space-y-1">
                          <div className="flex items-center gap-1.5">
                            <input
                              type="text"
                              required
                              value={lin.concepte}
                              onChange={(e) =>
                                setFormLinies((prev) =>
                                  prev.map((it, i) =>
                                    i === idx ? { ...it, concepte: e.target.value } : it
                                  )
                                )
                              }
                              placeholder="Concepte principal..."
                              className="w-full rounded border border-outline-variant/60 bg-surface-container-lowest px-2 py-1 font-medium text-on-surface"
                            />
                            {lin.article_id && (
                              <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-bold text-primary">
                                MAT
                              </span>
                            )}
                          </div>
                          <input
                            type="text"
                            value={lin.detall || ""}
                            onChange={(e) =>
                              setFormLinies((prev) =>
                                prev.map((it, i) =>
                                  i === idx ? { ...it, detall: e.target.value } : it
                                )
                              )
                            }
                            placeholder="Detall o especificació de la partida (opcional)..."
                            className="w-full rounded border border-outline-variant/40 bg-surface px-2 py-1 text-[11px] text-on-surface-variant"
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
                            className="w-full rounded border border-outline-variant/60 bg-surface-container-lowest px-2 py-1 tabular-nums text-on-surface"
                          />
                        </td>
                        {!esEnginyer && (
                          <>
                            <td className="px-2 py-2">
                              <input
                                type="number"
                                step="0.01"
                                min="0"
                                value={lin.preu_unitari}
                                onChange={(e) =>
                                  setFormLinies((prev) =>
                                    prev.map((it, i) =>
                                      i === idx
                                        ? { ...it, preu_unitari: Number(e.target.value) }
                                        : it
                                    )
                                  )
                                }
                                className="w-full rounded border border-outline-variant/60 bg-surface-container-lowest px-2 py-1 tabular-nums text-on-surface"
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
                                      i === idx
                                        ? { ...it, descompte_pct: Number(e.target.value) }
                                        : it
                                    )
                                  )
                                }
                                className="w-full rounded border border-outline-variant/60 bg-surface-container-lowest px-2 py-1 tabular-nums text-on-surface"
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
                                className="w-full rounded border border-outline-variant/60 bg-surface-container-lowest px-1.5 py-1 text-on-surface"
                              >
                                <option value={21}>21%</option>
                                <option value={10}>10%</option>
                                <option value={4}>4%</option>
                                <option value={0}>0%</option>
                              </select>
                            </td>
                            <td className="px-2 py-2 text-right font-semibold tabular-nums text-on-surface">
                              {sub.toFixed(2)} €
                            </td>
                          </>
                        )}
                        <td className="px-2 py-2 text-center">
                          <button
                            type="button"
                            disabled={formLinies.length <= 1}
                            onClick={() =>
                              setFormLinies((prev) => prev.filter((_, i) => i !== idx))
                            }
                            className="p-1 text-rose-600 disabled:opacity-30 cursor-pointer"
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

            {!esEnginyer && (
              <div className="rounded-xl bg-surface border border-outline-variant/40 p-4 flex flex-wrap items-center justify-between gap-4">
                <div className="flex flex-wrap items-center gap-5">
                  <div>
                    <label className="block text-[11px] text-on-surface-variant mb-0.5">
                      Descompte global (%)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      value={formDescompteGlobal}
                      onChange={(e) => setFormDescompteGlobal(e.target.value)}
                      className="w-24 rounded-md border border-outline-variant/60 bg-surface-container-lowest px-2.5 py-1 tabular-nums text-on-surface"
                    />
                  </div>
                  <div>
                    <span className="text-on-surface-variant block">Subtotal</span>
                    <span className="font-semibold tabular-nums text-on-surface">
                      {editorTotals.subtotalBrut.toFixed(2)} €
                    </span>
                  </div>
                  {editorTotals.descompteGlobalImport > 0 && (
                    <div>
                      <span className="text-on-surface-variant block">
                        Descompte ({editorTotals.dtoGlobalPct}%)
                      </span>
                      <span className="font-semibold tabular-nums text-rose-700">
                        -{editorTotals.descompteGlobalImport.toFixed(2)} €
                      </span>
                    </div>
                  )}
                  <div>
                    <span className="text-on-surface-variant block">Base imposable</span>
                    <span className="font-bold tabular-nums text-on-surface">
                      {editorTotals.base.toFixed(2)} €
                    </span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block">Quota IVA</span>
                    <span className="font-bold tabular-nums text-on-surface">
                      {editorTotals.iva.toFixed(2)} €
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-on-surface-variant block">Total pressupost</span>
                  <span className="text-xl font-black text-primary tabular-nums">
                    {editorTotals.total.toFixed(2)} €
                  </span>
                </div>
              </div>
            )}
          </section>

          {/* 5. CONDICIONS, NOTES I EXCLUSIONS (PLANTILLA OFICIAL) */}
          <section className="rounded-xl border border-outline-variant/40 bg-surface p-4 space-y-3">
            <h4 className="font-bold text-on-surface text-xs">
              Condicions comercials, notes i exclusions
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Forma de pagament
                </label>
                <input
                  value={formFormaPagament}
                  onChange={(e) => setFormFormaPagament(e.target.value)}
                  placeholder="Ex: Transferència bancària 30 dies"
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-on-surface"
                />
              </div>
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Acompte a l&apos;acceptació (%)
                  {editorTotals.importAcompte > 0 && (
                    <span className="font-normal text-primary ml-1">
                      · {editorTotals.importAcompte.toFixed(2)} €
                    </span>
                  )}
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="5"
                  value={formPercentatgeAcompte}
                  onChange={(e) => setFormPercentatgeAcompte(e.target.value)}
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 tabular-nums text-on-surface"
                />
              </div>
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Termini d&apos;execució o lliurament
                </label>
                <input
                  value={formTerminiExecucio}
                  onChange={(e) => setFormTerminiExecucio(e.target.value)}
                  placeholder="Ex: 5 dies laborables des de l'acceptació"
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-3 py-2 text-on-surface"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Notes i exclusions
                </label>
                <textarea
                  rows={2}
                  value={formNotesExclusions}
                  onChange={(e) => setFormNotesExclusions(e.target.value)}
                  placeholder="Obra civil, permisos municipals o altres exclusions..."
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest p-2.5 text-on-surface"
                />
              </div>
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Menció legal (exempció o ISP, opcional)
                </label>
                <textarea
                  rows={2}
                  value={formMencioLegal}
                  onChange={(e) => setFormMencioLegal(e.target.value)}
                  placeholder="Ex: Operació amb inversió del subjecte passiu (Art. 84.U.2n.f LIVA)..."
                  className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest p-2.5 text-on-surface"
                />
              </div>
            </div>
          </section>

          {/* Peu d'accions */}
          <div className="flex flex-wrap items-center justify-end gap-2 pt-3 border-t border-outline-variant/30">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-outline-variant/60 px-4 py-2 font-medium text-on-surface hover:bg-surface-container cursor-pointer"
            >
              Cancel·lar
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => desarPressupost("CLOSE")}
              className="rounded-lg border border-primary/40 bg-primary/10 px-4 py-2 font-semibold text-primary hover:bg-primary/20 disabled:opacity-50 cursor-pointer"
            >
              {saving ? "Desant..." : isEditing ? "Desar i tancar" : "Desar esborrany"}
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-5 py-2 font-semibold text-on-primary hover:opacity-90 disabled:opacity-50 cursor-pointer"
            >
              <Eye className="w-4 h-4" />
              {saving
                ? "Desant..."
                : isEditing
                  ? "Desar i previsualitzar"
                  : "Crear i previsualitzar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
