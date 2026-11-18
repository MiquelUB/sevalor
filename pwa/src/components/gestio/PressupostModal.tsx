"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  FileText,
  Mail,
  MessageCircle,
  Package,
  Plus,
  Search,
  Send,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { apiFetch, getApiBaseUrl } from "@/lib/api";

export interface PressupostLinia {
  article_id?: string | null;
  concepte: string;
  quantitat: number;
  preu_unitari: number;
  descompte_pct: number;
  tipus_iva: number;
  subtotal?: number;
}

export interface PressupostItem {
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

export interface ClientOption {
  id: string;
  rao_social: string;
  nif: string;
  email?: string | null;
  telefon?: string | null;
}

export interface ArticleMagatzemOption {
  id: string;
  referencia_inventari: string;
  nom: string;
  unitat_mesura?: string;
  preu_venda: number;
  estoc_disponible?: number;
}

function r2(val: number): number {
  return Math.round((val + Number.EPSILON) * 100) / 100;
}

interface EnviarPressupostModalProps {
  pressupost: PressupostItem;
  onClose: () => void;
  onSent?: (missatge: string) => void;
  showGoToPressupostosLink?: boolean;
}

export function EnviarPressupostModal({
  pressupost,
  onClose,
  onSent,
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
        <div className="flex items-start justify-between border-b border-outline-variant/30 pb-3">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-secondary">
              Enviament de Pressupost · {pressupost.numero}
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
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-on-surface-variant hover:bg-surface-container cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
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
          <div className="flex items-center justify-between">
            <h4 className="font-bold text-on-surface flex items-center gap-2">
              <Mail className="w-4 h-4 text-primary" />
              1. Enviar per Correu Electrònic (PDF + Enllaç d&apos;acceptació)
            </h4>
            <a
              href={`${getApiBaseUrl()}/gestio/pressupostos/${pressupost.id}/pdf`}
              target="_blank"
              rel="noreferrer"
              className="text-primary hover:underline font-semibold inline-flex items-center gap-1"
            >
              <Download className="w-3.5 h-3.5" /> Previsualitzar PDF
            </a>
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
                S&apos;adjuntarà automàticament el PDF oficial del pressupost.
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

interface PressupostModalProps {
  onClose: () => void;
  onSaved?: (saved: PressupostItem, isNew: boolean) => void;
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
  const isEditing = Boolean(initialPressupost);

  const [clients, setClients] = useState<ClientOption[]>(clientsProp || []);
  const [articles, setArticles] = useState<ArticleMagatzemOption[]>([]);
  const [copilotActiu, setCopilotActiu] = useState(false);

  const [formClientId, setFormClientId] = useState(
    initialPressupost?.client_id || initialClientId || ""
  );
  const [formNumero, setFormNumero] = useState(
    initialPressupost?.numero ||
      `PRES-${new Date().getFullYear()}-${String(Date.now()).slice(-4)}`
  );
  const [formTitol, setFormTitol] = useState(initialPressupost?.titol || "");
  const [formDescripcio, setFormDescripcio] = useState(initialPressupost?.descripcio || "");
  const [formValidesa, setFormValidesa] = useState(
    String(initialPressupost?.validesa_dies || 30)
  );
  const [formLinies, setFormLinies] = useState<PressupostLinia[]>(() => {
    if (initialPressupost?.linies && initialPressupost.linies.length > 0) {
      return initialPressupost.linies.map((l) => ({ ...l }));
    }
    if (initialPressupost) {
      return [
        {
          concepte: initialPressupost.titol || `Pressupost ${initialPressupost.numero}`,
          quantitat: 1,
          preu_unitari: Number(initialPressupost.total || 0),
          descompte_pct: 0,
          tipus_iva: 0,
        },
      ];
    }
    return [{ concepte: "", quantitat: 1, preu_unitari: 0, descompte_pct: 0, tipus_iva: 21 }];
  });

  // Cercador de material del magatzem per afegir en 1 clic
  const [cercaMaterial, setCercaMaterial] = useState("");
  const [materialDropdownOpen, setMaterialDropdownOpen] = useState(false);
  const [materialQt, setMaterialQt] = useState("1");
  const materialBoxRef = useRef<HTMLDivElement>(null);

  const [saving, setSaving] = useState(false);
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);
  const [createdToSend, setCreatedToSend] = useState<PressupostItem | null>(null);

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
    Promise.all(loads);
  }, [clientsProp]);

  useEffect(() => {
    const onOutsideClick = (e: MouseEvent) => {
      if (materialBoxRef.current && !materialBoxRef.current.contains(e.target as Node)) {
        setMaterialDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", onOutsideClick);
    return () => document.removeEventListener("mousedown", onOutsideClick);
  }, []);

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

  const editorTotals = useMemo(() => {
    const basesPerIva: Record<string, number> = {};
    for (const l of formLinies) {
      const sub = r2(
        Number(l.quantitat || 0) *
          Number(l.preu_unitari || 0) *
          (1 - Number(l.descompte_pct || 0) / 100)
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

  const afegirMaterialMagatzem = (art: ArticleMagatzemOption) => {
    const qt = Math.max(0.01, Number(materialQt || 1));
    const novaLinia: PressupostLinia = {
      article_id: art.id,
      concepte: `[${art.referencia_inventari}] ${art.nom}`,
      quantitat: qt,
      preu_unitari: esEnginyer ? 0 : Number(art.preu_venda || 0),
      descompte_pct: 0,
      tipus_iva: 21,
    };
    setFormLinies((prev) => {
      if (prev.length === 1 && !prev[0].concepte.trim() && Number(prev[0].preu_unitari) === 0) {
        return [novaLinia];
      }
      return [...prev, novaLinia];
    });
    setCercaMaterial("");
    setMaterialQt("1");
    setMaterialDropdownOpen(false);
  };

  const handlePropostaCopilot = async () => {
    const basePrompt = [formTitol.trim(), formDescripcio.trim()].filter(Boolean).join(" — ");
    if (!basePrompt) {
      setError("Escriu un títol o descripció tècnica perquè el Copilot IA redacti partides.");
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
          linies?: Array<{ concepte: string; quantitat?: number; preu_unitari?: number | null }>;
        };
        missatge?: string;
      }>(`/gestio/pressupostos/generar-ia?${q.toString()}`, { method: "POST" });

      if (res?.draft?.linies && res.draft.linies.length > 0) {
        setFormLinies(
          res.draft.linies.map((l) => ({
            concepte: l.concepte,
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

  const handleSubmit = async (e: React.FormEvent) => {
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
      if (isEditing && initialPressupost) {
        saved = await apiFetch<PressupostItem>(`/gestio/pressupostos/${initialPressupost.id}`, {
          method: "PUT",
          body: JSON.stringify({
            client_id: formClientId,
            titol: formTitol.trim() || `Pressupost ${formNumero}`,
            descripcio: formDescripcio.trim() || null,
            validesa_dies: Number(formValidesa || 30),
            linies: payloadLinies,
          }),
        });
        onSaved?.(saved, false);
        onClose();
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
        onSaved?.(saved, true);
        if (autoOpenSendOnCreate) {
          setCreatedToSend(saved);
        } else {
          onClose();
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en desar el pressupost.");
    } finally {
      setSaving(false);
    }
  };

  if (createdToSend) {
    return (
      <EnviarPressupostModal
        pressupost={createdToSend}
        onClose={onClose}
        showGoToPressupostosLink={showGoToPressupostosLink}
      />
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-primary/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="w-full max-w-4xl rounded-2xl bg-surface-container-lowest border border-outline-variant/40 p-6 shadow-2xl space-y-4 my-8">
        <div className="flex items-center justify-between border-b border-outline-variant/30 pb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary text-on-primary flex items-center justify-center shadow-sm">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-on-surface">
                {isEditing ? `Editar Pressupost ${formNumero}` : "Nou Pressupost Detallat"}
              </h3>
              <p className="text-[11px] text-on-surface-variant">
                Prepara partides amb materials de magatzem o conceptes personalitzats i envia&apos;l en 1 clic.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-on-surface-variant hover:bg-surface-container cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

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

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold text-on-surface mb-1">Client *</label>
              <select
                required
                value={formClientId}
                onChange={(e) => setFormClientId(e.target.value)}
                className="w-full rounded-lg border border-outline-variant/60 bg-surface px-3 py-2 text-on-surface"
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
              <label className="block font-semibold text-on-surface mb-1">Número Pressupost *</label>
              <input
                required
                disabled={isEditing}
                value={formNumero}
                onChange={(e) => setFormNumero(e.target.value)}
                className="w-full rounded-lg border border-outline-variant/60 bg-surface px-3 py-2 font-mono text-on-surface disabled:opacity-60"
              />
            </div>
            <div>
              <label className="block font-semibold text-on-surface mb-1">Validesa (dies)</label>
              <input
                type="number"
                min={1}
                max={365}
                value={formValidesa}
                onChange={(e) => setFormValidesa(e.target.value)}
                className="w-full rounded-lg border border-outline-variant/60 bg-surface px-3 py-2 text-on-surface"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-on-surface mb-1">
                Títol / Concepte General *
              </label>
              <input
                required
                value={formTitol}
                onChange={(e) => setFormTitol(e.target.value)}
                placeholder="Ex: Substitució caldera i posada en marxa"
                className="w-full rounded-lg border border-outline-variant/60 bg-surface px-3 py-2 text-on-surface"
              />
            </div>
            <div>
              <label className="block font-semibold text-on-surface mb-1">
                Observacions / Abast tècnic
              </label>
              <input
                value={formDescripcio}
                onChange={(e) => setFormDescripcio(e.target.value)}
                placeholder="Detalls d'execució, terminis o garantia..."
                className="w-full rounded-lg border border-outline-variant/60 bg-surface px-3 py-2 text-on-surface"
              />
            </div>
          </div>

          {/* Selector ràpid de Materials del Magatzem + Accions */}
          <div className="rounded-xl border border-outline-variant/40 bg-surface p-3 space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-bold uppercase tracking-wider text-[11px] text-on-surface-variant flex items-center gap-1.5">
                <Package className="w-3.5 h-3.5 text-primary" />
                Afegir Material del Magatzem o Concepte
              </span>
              <div className="flex items-center gap-2 flex-wrap">
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
                        concepte: "",
                        quantitat: 1,
                        preu_unitari: 0,
                        descompte_pct: 0,
                        tipus_iva: 21,
                      },
                    ])
                  }
                  className="inline-flex items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1.5 font-semibold text-primary hover:bg-primary/20 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" /> Afegir Partida / Concepte
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
          </div>

          {/* Taula de Partides */}
          <div className="overflow-x-auto rounded-xl border border-outline-variant/40">
            <table className="w-full text-left">
              <thead className="bg-surface-container-low text-on-surface-variant">
                <tr>
                  <th className="px-2.5 py-2 min-w-[220px]">Concepte</th>
                  <th className="px-2 py-2 w-20">Qt.</th>
                  {!esEnginyer && (
                    <>
                      <th className="px-2 py-2 w-24">Preu u. (€)</th>
                      <th className="px-2 py-2 w-20">Dto %</th>
                      <th className="px-2 py-2 w-20">IVA %</th>
                      <th className="px-2 py-2 w-24 text-right">Subtotal</th>
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
                    <tr key={idx}>
                      <td className="px-2.5 py-2">
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
                            placeholder="Mà d'obra / Material / Desplaçament..."
                            className="w-full rounded border border-outline-variant/60 bg-surface-container-lowest px-2 py-1 text-on-surface"
                          />
                          {lin.article_id && (
                            <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-bold text-primary">
                              MAT
                            </span>
                          )}
                        </div>
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
            <div className="rounded-xl bg-surface border border-outline-variant/40 p-4 flex items-center justify-between">
              <div className="flex gap-6">
                <div>
                  <span className="text-on-surface-variant block">Base Imposable</span>
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
                <span className="text-on-surface-variant block">TOTAL PRESSUPOST</span>
                <span className="text-xl font-black text-primary tabular-nums">
                  {editorTotals.total.toFixed(2)} €
                </span>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-outline-variant/60 px-4 py-2 font-medium text-on-surface hover:bg-surface-container cursor-pointer"
            >
              Cancel·lar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-primary px-5 py-2 font-semibold text-on-primary hover:opacity-90 disabled:opacity-50 cursor-pointer"
            >
              {saving
                ? "Desant..."
                : isEditing
                  ? "Desar Canvis"
                  : autoOpenSendOnCreate
                    ? "Crear i Enviar Pressupost"
                    : "Crear Pressupost"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
