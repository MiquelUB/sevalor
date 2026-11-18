"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Briefcase,
  Plus,
  Search,
  RefreshCw,
  MapPin,
  Calendar,
  Clock,
  UserCheck,
  Edit,
  Eye,
  Package,
  Wrench,
  Filter,
  Receipt,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useGestio } from "@/lib/gestio-context";
import { Feina } from "@/components/gestio/Map";
import { CrearOTModal } from "@/components/gestio/CrearOTModal";
import { EditarOTModal } from "@/components/gestio/EditarOTModal";
import { Fulla360OTDrawer } from "@/components/gestio/Fulla360OTDrawer";

const ESTAT_CHIPS = [
  { id: "TOTES", label: "Totes" },
  { id: "PENDENT", label: "Pendents" },
  { id: "ASSIGNADA", label: "Assignades" },
  { id: "EN_CURS", label: "En Curs / Obra" },
  { id: "TANCADA", label: "Tancades" },
] as const;

type EstatFilter = (typeof ESTAT_CHIPS)[number]["id"];

const ESTATS_ACABADES = [
  "COMPLERT",
  "TANCADA",
  "COMPLETADA",
  "FINALITZADA",
  "EXECUTADA_PENDENT_VALIDACIO",
  "ALBARA_SIGNAT",
  "PREFACTURADA",
  "FACTURADA",
];

const ESTATS_PER_PREFACTURAR = [
  "COMPLERT",
  "TANCADA",
  "COMPLETADA",
  "FINALITZADA",
  "EXECUTADA_PENDENT_VALIDACIO",
  "ALBARA_SIGNAT",
];

function estatBadgeClass(estat: string): string {
  const up = (estat || "").toUpperCase();
  if (up === "PENDENT") return "bg-amber-100 text-amber-800 border-amber-200";
  if (up === "ASSIGNADA" || up === "PROGRAMADA")
    return "bg-secondary-container/25 text-secondary border-secondary/30";
  if (up === "EN_CURS" || up === "EN_OBRA" || up === "EN_RUTA")
    return "bg-emerald-100 text-emerald-800 border-emerald-200";
  if (up === "PREFACTURADA")
    return "bg-amber-100 text-amber-900 border-amber-300";
  if (ESTATS_ACABADES.includes(up))
    return "bg-primary/10 text-primary border-primary/20";
  if (up === "BLOQUEJADA" || up === "INCIDENCIA")
    return "bg-error-container/30 text-error border-error/30";
  return "bg-surface-container-high text-on-surface-variant border-outline-variant/40";
}

function FeinesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { rolActiu } = useGestio();

  const paramC = searchParams.get("c") || "";
  const paramId = searchParams.get("id") || "";

  const [feines, setFeines] = useState<Feina[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [cerca, setCerca] = useState<string>(paramC);
  const [filtreEstat, setFiltreEstat] = useState<EstatFilter>("TOTES");

  const [showCrearModal, setShowCrearModal] = useState<boolean>(false);
  const [editingFeinaId, setEditingFeinaId] = useState<string | null>(null);
  const [drawerFeina, setDrawerFeina] = useState<Feina | null>(null);
  const [prefacturantId, setPrefacturantId] = useState<string | null>(null);

  const handlePrefacturarOT = async (feinaId: string) => {
    setPrefacturantId(feinaId);
    setErrorMsg(null);
    try {
      const res = await apiFetch<{ id: string }>(
        `/gestio/comptabilitat/wip-control/${feinaId}/prefacturar`,
        { method: "POST" }
      );
      router.push(`/gestio/comptabilitat?tab=PREFACTURACIO&prefactura_id=${res.id}`);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Error enviant OT a prefacturació.");
    } finally {
      setPrefacturantId(null);
    }
  };

  useEffect(() => {
    if (paramC) setCerca(paramC);
  }, [paramC]);

  const carregarFeines = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const endpoint = paramC
        ? `/gestio/feines?limit=150&q=${encodeURIComponent(paramC)}`
        : "/gestio/feines?limit=150";
      const res = await apiFetch<any>(endpoint);
      const list: Feina[] = Array.isArray(res) ? res : res?.feines || [];
      setFeines(list);

      if (paramId) {
        const match = list.find((f) => f.id === paramId);
        if (match) {
          setDrawerFeina(match);
        } else {
          const single = await apiFetch<Feina>(`/gestio/feines/${paramId}`).catch(() => null);
          if (single) setDrawerFeina(single);
        }
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "Error carregant les ordres de treball.");
      setFeines([]);
    } finally {
      setLoading(false);
    }
  }, [paramC, paramId]);

  useEffect(() => {
    carregarFeines();
  }, [carregarFeines]);

  const feinesFiltrades = useMemo(() => {
    return feines.filter((f) => {
      if (filtreEstat !== "TOTES") {
        const up = (f.estat || "").toUpperCase();
        if (filtreEstat === "EN_CURS") {
          if (!["EN_CURS", "EN_OBRA", "EN_RUTA"].includes(up)) return false;
        } else if (filtreEstat === "TANCADA") {
          if (!ESTATS_ACABADES.includes(up)) return false;
        } else if (up !== filtreEstat) {
          return false;
        }
      }

      if (!cerca.trim()) return true;
      const term = cerca.trim().toLowerCase();
      return (
        (f.codi || "").toLowerCase().includes(term) ||
        (f.titol || "").toLowerCase().includes(term) ||
        (f.client_nom || "").toLowerCase().includes(term) ||
        (f.adreca || "").toLowerCase().includes(term) ||
        (f.cap_de_colla_nom || "").toLowerCase().includes(term)
      );
    });
  }, [feines, filtreEstat, cerca]);

  const stats = useMemo(() => {
    const totals = feines.length;
    const actives = feines.filter((f) =>
      ["PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_OBRA", "EN_RUTA"].includes(
        (f.estat || "").toUpperCase()
      )
    ).length;
    const pendents = feines.filter((f) => (f.estat || "").toUpperCase() === "PENDENT").length;
    const tancades = feines.filter((f) =>
      ESTATS_ACABADES.includes((f.estat || "").toUpperCase())
    ).length;
    return { totals, actives, pendents, tancades };
  }, [feines]);

  const potVeurePreus = rolActiu !== "ENGINYER";

  return (
    <div className="flex-1 flex flex-col space-y-lg w-full animate-fade-in">
      {/* Header Principal */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-md pb-md border-b border-outline-variant/30">
        <div>
          <span className="font-label-caps text-secondary uppercase tracking-widest text-[11px]">
            Operacions de Camp · Ordres de Treball
          </span>
          <h1 className="font-display-lg text-2xl md:text-3xl text-primary mt-0.5 flex items-center gap-2.5">
            <Briefcase className="w-6 h-6 text-secondary shrink-0" />
            <span>Fulla de Feines i Planificació</span>
          </h1>
          <p className="text-sm text-on-surface-variant mt-1">
            Control d&apos;ordres de treball, quadrilles assignades, reserves de picking al magatzem i seguiment 360°.
          </p>
        </div>

        <div className="flex items-center gap-sm flex-wrap">
          <button
            type="button"
            onClick={carregarFeines}
            disabled={loading}
            className="px-3.5 py-2.5 rounded-xl bg-surface-container-lowest border border-outline-variant/60 text-xs font-body-strong text-on-surface hover:bg-surface-container flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Actualitzar</span>
          </button>

          <Link
            href="/gestio/mapa"
            className="px-3.5 py-2.5 rounded-xl bg-surface-container-low border border-outline-variant/60 text-xs font-body-strong text-primary hover:bg-surface-container transition-colors flex items-center gap-1.5"
          >
            <MapPin className="w-3.5 h-3.5 text-secondary" />
            <span>Mapa GIS</span>
          </Link>

          <button
            type="button"
            onClick={() => setShowCrearModal(true)}
            className="px-4 py-2.5 rounded-xl bg-primary hover:bg-primary/90 text-on-primary text-xs font-body-strong flex items-center gap-2 shadow-sm transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>+ Nova Feina</span>
          </button>
        </div>
      </div>

      {/* KPIs reals de la taula OrdreTreball */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-md">
        <div className="p-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm">
          <span className="font-label-caps text-[10px] uppercase text-on-surface-variant block">
            Total Carregades
          </span>
          <span className="font-data-tabular text-2xl font-bold text-primary mt-1 block">
            {stats.totals}
          </span>
        </div>
        <div className="p-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm">
          <span className="font-label-caps text-[10px] uppercase text-on-surface-variant block">
            Actives / En Curs
          </span>
          <span className="font-data-tabular text-2xl font-bold text-secondary mt-1 block">
            {stats.actives}
          </span>
        </div>
        <div className="p-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm">
          <span className="font-label-caps text-[10px] uppercase text-on-surface-variant block">
            Pendents d&apos;Assignar
          </span>
          <span className="font-data-tabular text-2xl font-bold text-amber-600 mt-1 block">
            {stats.pendents}
          </span>
        </div>
        <div className="p-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm">
          <span className="font-label-caps text-[10px] uppercase text-on-surface-variant block">
            Tancades / Històric
          </span>
          <span className="font-data-tabular text-2xl font-bold text-emerald-700 mt-1 block">
            {stats.tancades}
          </span>
        </div>
      </div>

      {/* Barra de Cerca i Filtres */}
      <div className="p-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-md">
        <div className="relative flex-1 max-w-lg">
          <Search className="w-4 h-4 text-on-surface-variant absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={cerca}
            onChange={(e) => setCerca(e.target.value)}
            placeholder="Cercar per codi OT, client, adreça, títol o cap de colla..."
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/60 text-xs text-on-surface placeholder:text-on-surface-variant focus:border-primary outline-none"
          />
        </div>

        <div className="flex items-center gap-xs flex-wrap">
          <Filter className="w-3.5 h-3.5 text-on-surface-variant mr-1 hidden sm:inline" />
          {ESTAT_CHIPS.map((chip) => {
            const active = filtreEstat === chip.id;
            return (
              <button
                key={chip.id}
                type="button"
                onClick={() => setFiltreEstat(chip.id)}
                className={`px-3 py-1.5 rounded-full text-xs font-body-strong transition-colors cursor-pointer ${
                  active
                    ? "bg-primary text-on-primary shadow-sm"
                    : "bg-surface-container-low text-on-surface-variant hover:bg-surface-container-high"
                }`}
              >
                {chip.label}
              </button>
            );
          })}
        </div>
      </div>

      {errorMsg && (
        <div className="p-md rounded-xl bg-error-container/30 border border-error/40 text-error text-xs font-body-strong">
          {errorMsg}
        </div>
      )}

      {/* Taula d'Ordres de Treball */}
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/40 shadow-sm overflow-hidden flex-1">
        {loading ? (
          <div className="p-2xl text-center text-xs font-mono text-on-surface-variant animate-pulse">
            Carregant ordres de treball des del servidor...
          </div>
        ) : feinesFiltrades.length === 0 ? (
          <div className="p-2xl text-center space-y-md">
            <div className="w-12 h-12 rounded-2xl bg-surface-container-low text-primary mx-auto flex items-center justify-center">
              <Briefcase className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-section-title text-base text-primary">
                Cap ordre de treball trobada
              </h3>
              <p className="text-xs text-on-surface-variant mt-1 max-w-md mx-auto">
                {cerca || filtreEstat !== "TOTES"
                  ? "No hi ha coincidències per als filtres seleccionats. Prova de netejar la cerca."
                  : "Encara no s'ha registrat cap ordre de treball per a aquesta empresa."}
              </p>
            </div>
            {!cerca && filtreEstat === "TOTES" && (
              <button
                type="button"
                onClick={() => setShowCrearModal(true)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-on-primary text-xs font-body-strong hover:bg-primary/90 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>Crear Primera Ordre de Treball</span>
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant/40 text-[10px] font-label-caps uppercase text-on-surface-variant">
                  <th className="py-3 px-4">Codi</th>
                  <th className="py-3 px-4">Intervenció i Client</th>
                  <th className="py-3 px-4">Adreça</th>
                  <th className="py-3 px-4">Planificació</th>
                  <th className="py-3 px-4">Quadrilla</th>
                  <th className="py-3 px-4">Recursos / Hores</th>
                  {potVeurePreus && <th className="py-3 px-4 text-right">Tarifa/h</th>}
                  <th className="py-3 px-4">Estat</th>
                  <th className="py-3 px-4 text-right">Accions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/25 text-xs">
                {feinesFiltrades.map((f) => {
                  const hores = Number(f.hores_imputades_facturables || 0);
                  const pickingCount = (f.linies_picking || []).length;
                  const einesCount = (f.eines || []).length;

                  return (
                    <tr
                      key={f.id}
                      onClick={() => setDrawerFeina(f)}
                      className="hover:bg-surface-container-low/70 transition-colors cursor-pointer"
                    >
                      <td className="py-3 px-4 font-mono font-bold text-primary whitespace-nowrap">
                        {f.codi}
                      </td>
                      <td className="py-3 px-4 min-w-[200px]">
                        <p className="font-body-strong text-on-surface line-clamp-1">{f.titol}</p>
                        <p className="text-[11px] text-on-surface-variant truncate">
                          {f.client_nom || "Client sense nom"}
                        </p>
                      </td>
                      <td className="py-3 px-4 max-w-[220px]">
                        <span className="inline-flex items-center gap-1 text-on-surface-variant truncate max-w-full">
                          <MapPin className="w-3 h-3 text-secondary shrink-0" />
                          <span className="truncate">{f.adreca}</span>
                        </span>
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap font-data-tabular text-on-surface">
                        <span className="inline-flex items-center gap-1">
                          <Calendar className="w-3 h-3 text-primary/70" />
                          <span>{f.data_planificacio || "—"}</span>
                        </span>
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 text-on-surface">
                          <UserCheck className="w-3.5 h-3.5 text-secondary shrink-0" />
                          <span>{f.cap_de_colla_nom || "Pendent d'assignar"}</span>
                        </span>
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap font-data-tabular">
                        <div className="flex items-center gap-2 text-[11px] text-on-surface-variant">
                          <span className="inline-flex items-center gap-0.5" title="Hores computades">
                            <Clock className="w-3 h-3" /> {hores.toFixed(2)}h
                          </span>
                          <span className="inline-flex items-center gap-0.5" title="Línies picking">
                            <Package className="w-3 h-3" /> {pickingCount}
                          </span>
                          <span className="inline-flex items-center gap-0.5" title="Eines en custòdia">
                            <Wrench className="w-3 h-3" /> {einesCount}
                          </span>
                        </div>
                      </td>
                      {potVeurePreus && (
                        <td className="py-3 px-4 text-right font-data-tabular font-bold text-secondary whitespace-nowrap">
                          {f.preu_venda_hora_aplicat !== null &&
                          f.preu_venda_hora_aplicat !== undefined ? (
                            <div>
                              <span>{Number(f.preu_venda_hora_aplicat).toFixed(2)} €/h</span>
                              {hores > 0 && (
                                <span className="block text-[10px] font-mono text-primary">
                                  {(hores * Number(f.preu_venda_hora_aplicat)).toFixed(2)} €
                                </span>
                              )}
                            </div>
                          ) : (
                            "—"
                          )}
                        </td>
                      )}
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span
                          className={`text-[10px] font-label-caps px-2.5 py-0.5 rounded-full border font-bold uppercase ${estatBadgeClass(
                            f.estat
                          )}`}
                        >
                          {f.estat}
                        </span>
                      </td>
                      <td
                        className="py-3 px-4 text-right whitespace-nowrap"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="inline-flex items-center gap-1">
                          {potVeurePreus &&
                            ESTATS_PER_PREFACTURAR.includes((f.estat || "").toUpperCase()) &&
                            !f.factura_id && (
                              <button
                                type="button"
                                disabled={prefacturantId === f.id}
                                onClick={() => handlePrefacturarOT(f.id)}
                                className="px-2 py-1 rounded-lg bg-secondary/15 hover:bg-secondary text-secondary hover:text-white text-[11px] font-bold transition-colors cursor-pointer inline-flex items-center gap-1 disabled:opacity-50"
                                title="Enviar a Prefacturació per editar i facturar"
                              >
                                <Receipt className="w-3.5 h-3.5" />
                                <span>{prefacturantId === f.id ? "..." : "Prefacturar"}</span>
                              </button>
                            )}
                          {potVeurePreus &&
                            f.factura_id &&
                            f.factura_estat_document === "ESBORRANY_PREFACTURA" && (
                              <Link
                                href={`/gestio/comptabilitat?tab=PREFACTURACIO&prefactura_id=${f.factura_id}`}
                                className="px-2 py-1 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-900 text-[11px] font-bold transition-colors inline-flex items-center gap-1"
                                title="Editar Pre-factura en esborrany"
                              >
                                <Receipt className="w-3.5 h-3.5" />
                                <span>Editar Pre-factura</span>
                              </Link>
                            )}
                          <button
                            type="button"
                            onClick={() => setDrawerFeina(f)}
                            className="p-1.5 rounded-lg hover:bg-surface-container text-primary transition-colors cursor-pointer"
                            title="Obrir Fulla 360°"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingFeinaId(f.id)}
                            className="p-1.5 rounded-lg hover:bg-surface-container text-secondary transition-colors cursor-pointer"
                            title="Editar Ordre de Treball"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals i Drawer 360° */}
      {showCrearModal && (
        <CrearOTModal
          onClose={() => setShowCrearModal(false)}
          onSuccess={() => {
            carregarFeines();
          }}
        />
      )}

      {editingFeinaId && (
        <EditarOTModal
          feinaId={editingFeinaId}
          onClose={() => setEditingFeinaId(null)}
          onSuccess={() => {
            carregarFeines();
          }}
        />
      )}

      <Fulla360OTDrawer
        feina={drawerFeina}
        isOpen={Boolean(drawerFeina)}
        onClose={() => setDrawerFeina(null)}
        onEdit={(feinaId) => {
          setDrawerFeina(null);
          setEditingFeinaId(feinaId);
        }}
        onFocusMapa={() => {
          setDrawerFeina(null);
          router.push("/gestio/mapa");
        }}
        onPrefacturaCreated={() => {
          carregarFeines();
        }}
      />
    </div>
  );
}

export default function GestioFeinesPage() {
  return (
    <Suspense
      fallback={
        <div className="p-xl text-center text-xs font-mono text-on-surface-variant animate-pulse">
          Inicialitzant Fulla de Feines...
        </div>
      }
    >
      <FeinesContent />
    </Suspense>
  );
}
