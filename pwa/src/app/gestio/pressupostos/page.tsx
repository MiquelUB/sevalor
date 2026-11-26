"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Briefcase,
  Check,
  CheckCircle2,
  Download,
  Edit3,
  Eye,
  FileText,
  Plus,
  RefreshCw,
  Search,
  Send,
  X,
  XCircle,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useGestio } from "@/lib/gestio-context";
import {
  ClientOption,
  descarregarPdfPressupostAutenticat,
  EnviarPressupostModal,
  PressupostItem,
  PressupostModal,
  PrevisualitzarPressupostModal,
} from "@/components/gestio/PressupostModal";
import { Fulla360OTModal } from "@/components/gestio/Fulla360OTModal";

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
  // Imports comercials de venda al client visibles per a ENGINYER, SECRETARIA i BOSS
  const amagarImportsComercials = false;
  void rolActiu;

  const paramId = searchParams.get("id") || "";
  const paramEnviar = searchParams.get("enviar") === "1";
  const paramRevisar = searchParams.get("revisar") === "1";
  const paramEditar = searchParams.get("editar") === "1";
  const paramClientId = searchParams.get("client_id") || "";

  const [pressupostos, setPressupostos] = useState<PressupostItem[]>([]);
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [pdfLoadingId, setPdfLoadingId] = useState<string | null>(null);

  const [cerca, setCerca] = useState("");
  const [filtreEstat, setFiltreEstat] = useState<"TOTS" | "PENDENT" | "APROVAT" | "REBUTJAT">("TOTS");

  const [editorState, setEditorState] = useState<{
    open: boolean;
    item: PressupostItem | null;
  }>({ open: false, item: null });
  const [previewModalItem, setPreviewModalItem] = useState<PressupostItem | null>(null);
  const [sendModalItem, setSendModalItem] = useState<PressupostItem | null>(null);
  const [convertirOTItem, setConvertirOTItem] = useState<PressupostItem | null>(null);
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

  useEffect(() => {
    if (paramId && paramId !== handledParamId && pressupostos.length > 0) {
      const found = pressupostos.find((p) => p.id === paramId);
      if (found) {
        if (paramEditar && found.estat !== "APROVAT") {
          setEditorState({ open: true, item: found });
        } else if (paramRevisar) {
          setPreviewModalItem(found);
        } else if (paramEnviar) {
          setSendModalItem(found);
        }
        setHandledParamId(paramId);
      }
    }
  }, [paramId, paramEnviar, paramRevisar, paramEditar, pressupostos, handledParamId]);

  const filtrats = useMemo(() => {
    return pressupostos.filter((p) => {
      if (paramClientId && p.client_id !== paramClientId) return false;
      if (filtreEstat !== "TOTS" && p.estat.toUpperCase() !== filtreEstat) return false;
      if (!cerca.trim()) return true;
      const t = cerca.trim().toLowerCase();
      return (
        (p.numero || "").toLowerCase().includes(t) ||
        (p.titol || "").toLowerCase().includes(t) ||
        (p.client_nom || "").toLowerCase().includes(t) ||
        (p.vehicle_nom || "").toLowerCase().includes(t)
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

  const handleDescarregarPdf = async (p: PressupostItem) => {
    setPdfLoadingId(p.id);
    setError(null);
    try {
      await descarregarPdfPressupostAutenticat(p.id, p.numero);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error generant el PDF del pressupost.");
    } finally {
      setPdfLoadingId(null);
    }
  };

  const handleConvertirOT = (p: PressupostItem) => {
    setError(null);
    setSuccessMsg(null);
    setConvertirOTItem(p);
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
            Prepara partides detallades amb vehicle, eines i desplaçament, previsualitza i edita la plantilla oficial abans d&apos;enviar-la.
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
            onClick={() => setEditorState({ open: true, item: null })}
            className="px-4 py-2.5 rounded-xl bg-primary hover:bg-primary/90 text-on-primary text-xs font-body-strong flex items-center gap-2 shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Nou pressupost</span>
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
            {amagarImportsComercials ? "—" : `${stats.totalAprovat.toFixed(2)} €`}
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
            placeholder="Cercar per número, títol, client o vehicle..."
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
              Crea un pressupost nou des d&apos;aquí, des del Dashboard o des d&apos;una Ordre de Treball.
            </p>
            <button
              type="button"
              onClick={() => setEditorState({ open: true, item: null })}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary text-on-primary text-xs font-bold cursor-pointer"
            >
              <Plus className="w-4 h-4" /> Nou pressupost
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
                  {!amagarImportsComercials && <th className="py-3 px-4 text-right">Import Total</th>}
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
                        {p.data_pressupost
                          ? new Date(`${p.data_pressupost}T00:00:00`).toLocaleDateString("ca-ES")
                          : new Date(p.created_at).toLocaleDateString("ca-ES")}
                      </span>
                    </td>
                    <td className="py-3 px-4 min-w-[220px]">
                      <p className="font-bold text-on-surface">{p.titol || p.numero}</p>
                      <p className="text-[11px] text-on-surface-variant">
                        {p.client_nom || "Client"}
                        {p.linies.length > 0 ? ` · ${p.linies.length} partides` : ""}
                        {p.vehicle_nom ? ` · ${p.vehicle_nom}` : ""}
                        {p.eines_resum && p.eines_resum.length > 0
                          ? ` · ${p.eines_resum.length} eines`
                          : ""}
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
                          Esborrany (no enviat)
                        </span>
                      )}
                    </td>
                    {!amagarImportsComercials && (
                      <td className="py-3 px-4 text-right whitespace-nowrap font-data-tabular font-bold text-on-surface">
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
                          onClick={() => setPreviewModalItem(p)}
                          className="px-2.5 py-1.5 rounded-lg border border-outline-variant/60 text-[11px] font-semibold text-on-surface hover:bg-surface-container inline-flex items-center gap-1 cursor-pointer"
                          title="Previsualitzar document oficial"
                        >
                          <Eye className="w-3.5 h-3.5 text-primary" />
                          <span>Veure</span>
                        </button>
                        {p.estat !== "APROVAT" && (
                          <button
                            type="button"
                            onClick={() => setEditorState({ open: true, item: p })}
                            className="px-2.5 py-1.5 rounded-lg border border-outline-variant/60 text-[11px] font-semibold text-secondary hover:bg-surface-container inline-flex items-center gap-1 cursor-pointer"
                            title="Editar pressupost"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                            <span>Editar</span>
                          </button>
                        )}
                        <button
                          type="button"
                          disabled={pdfLoadingId === p.id}
                          onClick={() => handleDescarregarPdf(p)}
                          className="px-2 py-1.5 rounded-lg border border-outline-variant/60 text-[11px] font-semibold text-on-surface hover:bg-surface-container inline-flex items-center gap-1 cursor-pointer disabled:opacity-50"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>{pdfLoadingId === p.id ? "..." : "PDF"}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => setSendModalItem(p)}
                          className="px-2.5 py-1.5 rounded-lg bg-primary text-on-primary text-[11px] font-bold hover:opacity-90 inline-flex items-center gap-1 cursor-pointer"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>Enviar</span>
                        </button>
                        {p.estat === "PENDENT" && (
                          <>
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

      {editorState.open && (
        <PressupostModal
          initialPressupost={editorState.item}
          initialClientId={paramClientId}
          clientsProp={clients}
          esEnginyer={amagarImportsComercials}
          autoOpenSendOnCreate={false}
          onClose={() => setEditorState({ open: false, item: null })}
          onSaved={(saved, isNew) => {
            carregarDades();
            if (isNew) {
              setSuccessMsg(
                `Pressupost ${saved.numero} creat. El pots revisar, editar o enviar quan vulguis.`
              );
            } else {
              setSuccessMsg(`Pressupost ${saved.numero} actualitzat correctament.`);
            }
          }}
        />
      )}

      {previewModalItem && (
        <PrevisualitzarPressupostModal
          pressupost={previewModalItem}
          onClose={() => setPreviewModalItem(null)}
          onEdit={(p) => {
            setPreviewModalItem(null);
            setEditorState({ open: true, item: p });
          }}
          onSend={(p) => {
            setPreviewModalItem(null);
            setSendModalItem(p);
          }}
        />
      )}

      {sendModalItem && (
        <EnviarPressupostModal
          pressupost={sendModalItem}
          onClose={() => setSendModalItem(null)}
          onPreview={(p) => {
            setSendModalItem(null);
            setPreviewModalItem(p);
          }}
          onEdit={(p) => {
            setSendModalItem(null);
            setEditorState({ open: true, item: p });
          }}
          onSent={(msg) => {
            setSuccessMsg(msg);
            carregarDades();
          }}
        />
      )}

      {convertirOTItem && (
        <Fulla360OTModal
          mode="FROM_PRESSUPOST"
          isOpen={true}
          initialPressupost={convertirOTItem}
          onClose={() => setConvertirOTItem(null)}
          onSuccess={(created) => {
            const numPres = convertirOTItem.numero;
            setConvertirOTItem(null);
            carregarDades();
            setSuccessMsg(
              `Ordre de Treball ${created?.codi || ""} creada des del pressupost ${numPres} amb equip, vehicle, hores, picking i eines assignats.`
            );
            if (created?.id) {
              router.push(`/gestio/feines?id=${created.id}`);
            }
          }}
        />
      )}
    </div>
  );
}

export default function GestioPressupostosPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-xs font-mono text-on-surface-variant animate-pulse">
          Carregant mòdul de pressupostos...
        </div>
      }
    >
      <PressupostosContent />
    </Suspense>
  );
}
