"use client";

import React, { useState, useEffect } from "react";
import {
  MapPin,
  Truck,
  ClipboardList,
  PackageCheck,
  CheckCircle2,
  X,
  AlertCircle,
  Clock,
  ChevronRight,
} from "lucide-react";
import { localDB } from "@/lib/db";

interface VehicleItem {
  id: string;
  matricula: string;
  marca: string;
  model: string;
  odometre_acumulat?: number | null;
}

interface MorningBriefingProps {
  isOpen: boolean;
  onClose: () => void;
  onCompleted: () => void;
}

export default function MorningBriefing({
  isOpen,
  onClose,
  onCompleted,
}: MorningBriefingProps) {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Dades dels passos
  const [jornadaId, setJornadaId] = useState<string>("");
  const [vehicles, setVehicles] = useState<VehicleItem[]>([]);
  const [selectedVehicleId, setSelectedVehicleId] = useState<string>("");
  const [kmInicials, setKmInicials] = useState<string>("");
  const [feinesDia, setFeinesDia] = useState<any[]>([]);
  const [materialsPicking, setMaterialsPicking] = useState<any[]>([]);

  useEffect(() => {
    if (!isOpen) return;

    // Comprovar si ja hi ha una jornada activa al magatzem local
    const saved = localStorage.getItem("sevalor_jornada_activa");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed?.id) {
          setJornadaId(parsed.id);
          setStep(2);
        }
      } catch {
        // Ignorar
      }
    }

    // Carregar llista real de la flota de vehicles
    async function carregarVehicles() {
      if (navigator.onLine) {
        try {
          const res = await fetch("/api/v1/operari/vehicles", { credentials: "include" });
          if (res.ok) {
            const data: VehicleItem[] = await res.json();
            setVehicles(data);
          }
        } catch {
          // Mode offline
        }
      }
    }
    carregarVehicles();
  }, [isOpen]);

  if (!isOpen) return null;

  const obtenirGPS = (): Promise<{ latitud: number; longitud: number }> => {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("El dispositiu no disposa de geolocalització GPS."));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (p) => resolve({ latitud: p.coords.latitude, longitud: p.coords.longitude }),
        () => reject(new Error("Permís de GPS denegat o senyal GPS insuficient.")),
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    });
  };

  const handleStep1Fitxar = async () => {
    setLoading(true);
    setError(null);
    try {
      const coords = await obtenirGPS();
      const nowIso = new Date().toISOString();
      let novaJornadaId = crypto.randomUUID();

      if (navigator.onLine) {
        const res = await fetch("/api/v1/operari/jornada/inici", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            latitud: coords.latitud,
            longitud: coords.longitud,
            lat: coords.latitud,
            lon: coords.longitud,
          }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "Error en registrar l'inici de jornada al servidor.");
        }
        const data = await res.json();
        novaJornadaId = data.id;
      } else {
        await localDB.sync_queue.add({
          id: crypto.randomUUID(),
          bloc_uuid: crypto.randomUUID(),
          acció: "FITXAR_JORNADA",
          payload: {
            tipus: "INICI",
            latitud: coords.latitud,
            longitud: coords.longitud,
            timestamp: nowIso,
          },
          timestamp: Date.now(),
          intents: 0,
        });
      }

      await localDB.fichajes.put({
        id: novaJornadaId,
        empresa_id: "",
        usuari_id: "",
        estat: "EN_CURS",
        hora_inici: nowIso,
        latitud_inici: coords.latitud,
        longitud_inici: coords.longitud,
        estat_sync: navigator.onLine ? "SINCRONITZAT" : "PENDENT",
      });

      const guardada = {
        id: novaJornadaId,
        data_inici: nowIso,
        lat_inici: coords.latitud,
        lon_inici: coords.longitud,
      };
      localStorage.setItem("sevalor_jornada_activa", JSON.stringify(guardada));
      window.dispatchEvent(new Event("sevalor-jornada-updated"));
      setJornadaId(novaJornadaId);
      setStep(2);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error iniciant el torn GPS.");
    } finally {
      setLoading(false);
    }
  };

  const handleStep2Vehicle = async () => {
    setLoading(true);
    setError(null);
    try {
      if (selectedVehicleId.trim()) {
        const kmVal = kmInicials ? parseInt(kmInicials, 10) : 0;
        if (navigator.onLine && jornadaId) {
          const res = await fetch(`/api/v1/operari/jornada/${jornadaId}/vehicle`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
              vehicle_id: selectedVehicleId.trim(),
              km_actuals: kmVal,
              km_inicials: kmVal,
              fotos_check_in: ["checkin_frontal.webp"],
            }),
          });
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Error assignant el vehicle a la jornada.");
          }
        }

        // Actualitzar estat de la jornada al localStorage
        const saved = localStorage.getItem("sevalor_jornada_activa");
        if (saved) {
          try {
            const parsed = JSON.parse(saved);
            parsed.vehicle_id = selectedVehicleId;
            parsed.km_inicials = kmVal;
            localStorage.setItem("sevalor_jornada_activa", JSON.stringify(parsed));
            window.dispatchEvent(new Event("sevalor-jornada-updated"));
          } catch {
            // Ignorar
          }
        }
      }

      // Carregar feines del dia per al Pas 3
      if (navigator.onLine) {
        const resFeines = await fetch("/api/v1/operari/feines", { credentials: "include" });
        if (resFeines.ok) {
          const dadesFeines = await resFeines.json();
          setFeinesDia(dadesFeines || []);
        }
      } else {
        const offlineFeines = await localDB.ordres.toArray();
        setFeinesDia(offlineFeines || []);
      }

      setStep(3);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error processant el vehicle.");
    } finally {
      setLoading(false);
    }
  };

  const handleStep3ToStep4 = async () => {
    setLoading(true);
    setError(null);
    try {
      if (navigator.onLine) {
        const resMat = await fetch("/api/v1/operari/picking/materials", {
          credentials: "include",
        });
        if (resMat.ok) {
          const dadesMat = await resMat.json();
          setMaterialsPicking(dadesMat || []);
        }
      } else {
        const offlinePicking = await localDB.picking.toArray();
        setMaterialsPicking(offlinePicking || []);
      }
      setStep(4);
    } catch {
      setStep(4);
    } finally {
      setLoading(false);
    }
  };

  const handleFinishBriefing = async () => {
    if (jornadaId) {
      await localDB.fichajes.update(jornadaId, { estat: "EN_CURS" }).catch(() => {});
    }
    onCompleted();
    onClose();
  };

  return (
    <div
      data-testid="morning-briefing-modal"
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200"
    >
      <div className="bg-surface-container-lowest text-on-surface w-full max-w-md rounded-2xl shadow-2xl border border-outline-variant/30 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Capçalera del Wizard */}
        <div className="bg-primary text-on-primary p-4 flex items-center justify-between shrink-0 shadow-sm">
          <div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-secondary-container animate-pulse" />
              <p className="text-[11px] font-bold uppercase tracking-wider text-on-primary-container">
                Assistent Matinal • Pas {step} de 4
              </p>
            </div>
            <h2 className="text-lg font-black tracking-tight mt-0.5">Inici de Torn Operatiu</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg bg-white/10 hover:bg-white/20 active:scale-95 transition-transform"
          >
            <X className="w-5 h-5 text-on-primary" />
          </button>
        </div>

        {/* Indicador de passos */}
        <div className="grid grid-cols-4 border-b border-outline-variant/20 bg-surface-container-low text-[11px] font-bold uppercase text-center shrink-0">
          <div className={`py-2 border-b-2 ${step === 1 ? "border-primary text-primary" : "border-transparent text-on-surface-variant"}`}>
            1. GPS
          </div>
          <div className={`py-2 border-b-2 ${step === 2 ? "border-primary text-primary" : "border-transparent text-on-surface-variant"}`}>
            2. Flota
          </div>
          <div className={`py-2 border-b-2 ${step === 3 ? "border-primary text-primary" : "border-transparent text-on-surface-variant"}`}>
            3. Feines
          </div>
          <div className={`py-2 border-b-2 ${step === 4 ? "border-secondary text-secondary" : "border-transparent text-on-surface-variant"}`}>
            4. Picking
          </div>
        </div>

        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {error && (
            <div
              data-testid="briefing-error"
              className="p-3 rounded-xl bg-error-container text-on-error-container text-xs font-bold flex items-center gap-2 border border-error/20"
            >
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* PAS 1: Fitxatge GPS */}
          {step === 1 && (
            <div className="space-y-4 text-center py-4">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 text-primary mx-auto flex items-center justify-center">
                <MapPin className="w-8 h-8" />
              </div>
              <div>
                <h3 className="text-base font-bold text-on-surface">1. Fitxatge GPS d&apos;Entrada</h3>
                <p className="text-xs text-on-surface-variant mt-1 max-w-xs mx-auto">
                  Es capturarà la geolocalització exacta i s&apos;obrirà el teu registre de jornada laboral (FR-004).
                </p>
              </div>

              <button
                type="button"
                data-testid="briefing-step1-btn"
                disabled={loading}
                onClick={handleStep1Fitxar}
                className="w-full min-h-[50px] bg-primary text-on-primary font-bold rounded-xl flex items-center justify-center gap-2 active:scale-95 transition-transform disabled:opacity-50 shadow-md"
              >
                <Clock className="w-5 h-5" />
                {loading ? "Obtenint coordenades GPS..." : "Fitxar Entrada de Torn"}
              </button>
            </div>
          )}

          {/* PAS 2: Check-in de Vehicle */}
          {step === 2 && (
            <div className="space-y-4 py-2">
              <div className="flex items-center gap-2.5 pb-2 border-b border-outline-variant/20">
                <div className="w-10 h-10 rounded-xl bg-secondary-container/20 text-secondary flex items-center justify-center shrink-0">
                  <Truck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-on-surface">2. Assignació de Vehicle i Odòmetre</h3>
                  <p className="text-[11px] text-on-surface-variant">Selecciona la furgoneta o camió assignat avui.</p>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-on-surface mb-1.5">
                  Furgoneta / Vehicle
                </label>
                <select
                  data-testid="select-briefing-vehicle"
                  value={selectedVehicleId}
                  onChange={(e) => {
                    const vId = e.target.value;
                    setSelectedVehicleId(vId);
                    const sel = vehicles.find((v) => v.id === vId);
                    if (sel && sel.odometre_acumulat) {
                      setKmInicials(String(sel.odometre_acumulat));
                    }
                  }}
                  className="w-full min-h-[46px] p-2.5 rounded-xl border border-outline-variant bg-surface-container-low text-on-surface text-sm font-medium"
                >
                  <option value="">Sense vehicle (acompanyant o a peu)</option>
                  {vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.matricula} — {v.marca} {v.model} ({v.odometre_acumulat || 0} km)
                    </option>
                  ))}
                </select>
              </div>

              {selectedVehicleId && (
                <div>
                  <label className="block text-xs font-bold uppercase text-on-surface mb-1.5">
                    Quilòmetres Inicials (Odòmetre)
                  </label>
                  <input
                    type="number"
                    data-testid="input-briefing-km"
                    value={kmInicials}
                    onChange={(e) => setKmInicials(e.target.value)}
                    placeholder="Ex: 124500"
                    className="w-full min-h-[46px] p-2.5 rounded-xl border border-outline-variant bg-surface-container-low text-on-surface text-sm font-mono font-bold"
                  />
                </div>
              )}

              <button
                type="button"
                data-testid="briefing-step2-btn"
                disabled={loading}
                onClick={handleStep2Vehicle}
                className="w-full min-h-[50px] bg-primary text-on-primary font-bold rounded-xl flex items-center justify-center gap-2 active:scale-95 transition-transform disabled:opacity-50 shadow-md"
              >
                <span>Continuar a les Feines</span>
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          )}

          {/* PAS 3: Resum de Feines */}
          {step === 3 && (
            <div className="space-y-4 py-2">
              <div className="flex items-center gap-2.5 pb-2 border-b border-outline-variant/20">
                <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
                  <ClipboardList className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-on-surface">
                    3. Feines Assignades ({feinesDia.length})
                  </h3>
                  <p className="text-[11px] text-on-surface-variant">Ordres de treball planificades per a la teva colla.</p>
                </div>
              </div>

              <div className="max-h-56 overflow-y-auto space-y-2.5 pr-1">
                {feinesDia.length === 0 ? (
                  <div className="p-4 rounded-xl bg-surface-container-low border border-dashed border-outline-variant text-center">
                    <p className="text-xs font-bold text-on-surface">Cap ordre de treball pendent per avui</p>
                    <p className="text-[11px] text-on-surface-variant mt-0.5">
                      Podràs afegir-ne una de nova o esperar assignació del cap tècnic.
                    </p>
                  </div>
                ) : (
                  feinesDia.map((f, idx) => (
                    <div
                      key={f.id || idx}
                      className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[10px] font-bold text-primary">
                          {f.codi || `#${idx + 1}`}
                        </span>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-surface-container text-on-surface">
                          {f.estat || "PENDENT"}
                        </span>
                      </div>
                      <p className="font-bold text-sm text-on-surface">{f.titol}</p>
                      {f.adreca && (
                        <p className="text-on-surface-variant flex items-center gap-1 text-[11px]">
                          <MapPin className="w-3.5 h-3.5 shrink-0 text-primary" />
                          <span className="truncate">{f.adreca}</span>
                        </p>
                      )}
                    </div>
                  ))
                )}
              </div>

              <button
                type="button"
                data-testid="briefing-step3-btn"
                disabled={loading}
                onClick={handleStep3ToStep4}
                className="w-full min-h-[50px] bg-primary text-on-primary font-bold rounded-xl flex items-center justify-center gap-2 active:scale-95 transition-transform disabled:opacity-50 shadow-md"
              >
                <span>Revisar Càrrega de Materials (Pick-In)</span>
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          )}

          {/* PAS 4: Confirmació de Picking */}
          {step === 4 && (
            <div className="space-y-4 py-2">
              <div className="flex items-center gap-2.5 pb-2 border-b border-outline-variant/20">
                <div className="w-10 h-10 rounded-xl bg-secondary-container/20 text-secondary flex items-center justify-center shrink-0">
                  <PackageCheck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-on-surface">4. Confirmació de Càrrega (Pick-In)</h3>
                  <p className="text-[11px] text-on-surface-variant">
                    Revisa el material carregat a la furgoneta abans de sortir.
                  </p>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-xs">
                <p className="font-bold text-on-surface">
                  Catàleg de magatzem disponible: {materialsPicking.length} referències.
                </p>
                <p className="text-[11px] text-on-surface-variant mt-1">
                  Les línies de picking s&apos;actualitzen automàticament al magatzem sobirà a mesura que les consumeixes.
                </p>
              </div>

              <button
                type="button"
                data-testid="briefing-finish-btn"
                onClick={handleFinishBriefing}
                className="w-full min-h-[52px] bg-secondary text-on-secondary font-bold rounded-xl flex items-center justify-center gap-2 active:scale-95 transition-transform shadow-md"
              >
                <CheckCircle2 className="w-5 h-5" />
                <span>Iniciar Jornada i Començar Ruta</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
