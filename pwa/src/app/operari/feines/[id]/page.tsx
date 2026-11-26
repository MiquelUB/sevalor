"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Settings,
  Cpu,
  HardDrive,
  Server,
  Smartphone,
  Wrench,
  FileText,
  Bot,
  Truck,
  Package,
  Navigation,
  CheckCircle2,
  MapPin,
  Layers,
  ExternalLink,
  Camera,
  ShieldCheck,
  Lock,
  AlertTriangle,
  Play,
  Square,
  ChevronRight,
  PenTool,
  Receipt,
} from "lucide-react";
import CameraCapture from "@/components/CameraCapture";
import SignaturePad from "@/components/operari/SignaturePad";
import { apiFetch, extractTenantId, getApiBaseUrl, getAuthToken } from "@/lib/api";
import { db } from "@/lib/offline/db";
import { encryptWithPin, decryptWithPin } from "@/lib/crypto";

type TipusFotoQA = "INICIAL" | "INTERMEDIA" | "FINAL";

interface EstatFotosQA {
  fotos_pujades: TipusFotoQA[];
  protocol_complet: boolean;
  falten: TipusFotoQA[];
}

interface Asset {
  id: string;
  nom: string;
  model: string;
  tipus: string;
  num_serie: string;
  estat: string;
}

interface LiniaPicking {
  id: string;
  article_id: string;
  article_nom: string;
  quantitat_prevista: number;
  quantitat_carregada_pick_in: number;
  quantitat_retornada_pick_out?: number;
  quantitat_mermada?: number;
  unitat_mesura?: string;
  origen_estoc?: string;
}

interface EinaCustodia {
  id: string;
  nom: string;
  model?: string;
  numero_serie: string;
  referencia_fabricant?: string | null;
  estat: string;
  ordre_treball_id?: string | null;
  incidencies?: string | null;
}

interface TramTemps {
  id: string;
  hora_inici: string;
  hora_fi?: string | null;
  durada_segons: number;
  gps_inici_lat?: number | null;
  gps_inici_lng?: number | null;
  gps_fi_lat?: number | null;
  gps_fi_lng?: number | null;
  desviacio_geovalla?: boolean;
  justificacio_gps?: string | null;
}

interface OrdreDetall {
  id: string;
  codi: string;
  titol: string;
  descripcio?: string;
  client: string;
  estat: string;
  adreca?: string;
  vehicle?: { id: string; matricula: string; marca?: string; model: string };
  linies_picking?: LiniaPicking[];
  eines_assignades?: EinaCustodia[];
  assets: Asset[];
  planol_id?: string | null;
  planol_titol?: string | null;
  planol_codi?: string | null;
  planol_tipus_fitxer?: string | null;
  hora_inici_real?: string | null;
  hora_fi_real?: string | null;
  gps_inici_lat?: number | null;
  gps_inici_lng?: number | null;
  gps_fi_lat?: number | null;
  gps_fi_lng?: number | null;
  hores_imputades_facturables?: number | null;
  desviacio_geovalla?: boolean;
  justificacio_geovalla?: string | null;
  te_tram_obert?: boolean;
  tram_actiu_inici?: string | null;
  temps_acumulat_segons?: number;
  trams_temps?: TramTemps[];
  signatura_client_path?: string | null;
  nom_receptor?: string | null;
  dni_receptor?: string | null;
  observacions_tancament?: string | null;
  data_signatura?: string | null;
}

function formatSegonsHMS(totalSegons: number): string {
  const safe = Math.max(0, Math.floor(totalSegons));
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = safe % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function acumulatPreviLabel(acumulatSegons: number): string {
  if (acumulatSegons <= 0) return "";
  return ` (+ ${formatSegonsHMS(acumulatSegons)} previs)`;
}

export default function LlistaMaquinesPage() {
  const { id } = useParams() as { id: string };
  const router = useRouter();

  const [ordre, setOrdre] = useState<OrdreDetall | null>(null);
  const [hasCopilotIa, setHasCopilotIa] = useState<boolean>(true);
  const [loading, setLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(false);
  const [showPinModal, setShowPinModal] = useState(false);
  const [offlinePin, setOfflinePin] = useState("");
  const [offlineError, setOfflineError] = useState<string | null>(null);

  // Cronòmetre en viu multi-tram (obrir/tancar/reprendre)
  const [tempsTranscorregut, setTempsTranscorregut] = useState<string>("00:00:00");
  const [tempsSessioActual, setTempsSessioActual] = useState<string>("00:00:00");
  const [horesLiveEstimades, setHoresLiveEstimades] = useState<number>(0);

  useEffect(() => {
    const tramObert = Boolean(
      ordre?.te_tram_obert ||
        (ordre?.estat === "EN_CURS" && ordre?.hora_inici_real && !ordre?.hora_fi_real)
    );
    const iniciActiu = ordre?.tram_actiu_inici || ordre?.hora_inici_real;
    const acumulatPrevi = Math.max(
      ordre?.temps_acumulat_segons || 0,
      !(ordre?.trams_temps?.length) && ordre?.hores_imputades_facturables
        ? Math.round(Number(ordre.hores_imputades_facturables) * 3600)
        : 0
    );

    if (tramObert && iniciActiu) {
      const actualitzarCronometre = () => {
        const iniciMs = new Date(iniciActiu).getTime();
        const segonsSessio = Math.max(0, Math.floor((Date.now() - iniciMs) / 1000));
        const totalSegons = acumulatPrevi + segonsSessio;
        setTempsSessioActual(formatSegonsHMS(segonsSessio));
        setTempsTranscorregut(formatSegonsHMS(totalSegons));
        setHoresLiveEstimades(
          totalSegons > 0 ? Math.max(0.01, Number((totalSegons / 3600).toFixed(2))) : 0.01
        );
      };
      actualitzarCronometre();
      const interval = setInterval(actualitzarCronometre, 1000);
      return () => clearInterval(interval);
    }
  }, [
    ordre?.te_tram_obert,
    ordre?.estat,
    ordre?.tram_actiu_inici,
    ordre?.hora_inici_real,
    ordre?.hora_fi_real,
    ordre?.temps_acumulat_segons,
  ]);

  // Geovalla i inici/final en temps de feina (FR-005)
  const [iniciantFeina, setIniciantFeina] = useState(false);
  const [requereixJustificacioGPS, setRequereixJustificacioGPS] = useState(false);
  const [accioPendentGps, setAccioPendentGps] = useState<"inici" | "final">("inici");
  const [justificacioGps, setJustificacioGps] = useState("");
  const [gpsFeedback, setGpsFeedback] = useState<string | null>(null);
  const [gpsError, setGpsError] = useState<string | null>(null);

  // Semàfor 3 Fotos QA (FR-007)
  const [estatFotos, setEstatFotos] = useState<EstatFotosQA>({
    fotos_pujades: [],
    protocol_complet: false,
    falten: ["INICIAL", "INTERMEDIA", "FINAL"],
  });
  const [tipusFotoActiva, setTipusFotoActiva] = useState<TipusFotoQA | null>(null);
  const [uploadingFoto, setUploadingFoto] = useState(false);

  const carregarEstatFotos = async () => {
    if (typeof navigator !== "undefined" && !navigator.onLine) return;
    try {
      const data = await apiFetch<any>(`/operari/feines/${id}/fotos`);
      if (data) {
        const fotosDict = data.fotos || {};
        const pujades: TipusFotoQA[] = [];
        if (fotosDict.inicial) pujades.push("INICIAL");
        if (fotosDict.intermedia) pujades.push("INTERMEDIA");
        if (fotosDict.final) pujades.push("FINAL");

        const tot: TipusFotoQA[] = ["INICIAL", "INTERMEDIA", "FINAL"];
        const falten = tot.filter((t) => !pujades.includes(t));
        setEstatFotos({
          fotos_pujades: pujades,
          protocol_complet: Boolean(data.protocol_complet || pujades.length === 3),
          falten,
        });
      }
    } catch {
      // mode offline
    }
  };

  const obtenirGPS = async (): Promise<{
    latitud: number | null;
    longitud: number | null;
    gpsAvis?: string;
  }> => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      return { latitud: null, longitud: null, gpsAvis: "Navegador sense API de geolocalització" };
    }

    const intentarPosicio = (highAccuracy: boolean, timeoutMs: number) =>
      new Promise<{ latitud: number; longitud: number }>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
          (pos) => resolve({ latitud: pos.coords.latitude, longitud: pos.coords.longitude }),
          (err) => reject(err),
          {
            enableHighAccuracy: highAccuracy,
            timeout: timeoutMs,
            maximumAge: highAccuracy ? 15000 : 60000,
          }
        );
      });

    try {
      return await intentarPosicio(true, 8000);
    } catch {
      try {
        return await intentarPosicio(false, 6000);
      } catch (err: unknown) {
        const geoErr = err as { code?: number; message?: string };
        const msg =
          geoErr?.code === 1
            ? "Permís GPS denegat al navegador"
            : "Senyal GPS no disponible al dispositiu";
        return { latitud: null, longitud: null, gpsAvis: msg };
      }
    }
  };

  const handleMarcarTempsGps = async (accio: "inici" | "final") => {
    setIniciantFeina(true);
    setAccioPendentGps(accio);
    setGpsError(null);
    setGpsFeedback(null);
    try {
      const coords = await obtenirGPS();
      const endpoint =
        accio === "inici"
          ? `/operari/feines/${id}/comencar`
          : `/operari/feines/${id}/finalitzar-temps`;

      const data = await apiFetch<any>(endpoint, {
        method: "PUT",
        body: JSON.stringify({
          lat: coords.latitud,
          lng: coords.longitud,
          lon: coords.longitud,
          desviacio_justificada: Boolean(justificacioGps.trim()),
          justificacio_gps: justificacioGps.trim() || undefined,
        }),
      });

      setOrdre((prev) =>
        prev
          ? {
              ...prev,
              estat: data.estat || (accio === "inici" ? "EN_CURS" : "PAUSADA"),
              hora_inici_real:
                data.hora_inici_real !== undefined
                  ? data.hora_inici_real
                  : accio === "inici" && !prev.hora_inici_real
                  ? new Date().toISOString()
                  : prev.hora_inici_real,
              hora_fi_real:
                data.hora_fi_real !== undefined
                  ? data.hora_fi_real
                  : accio === "final"
                  ? new Date().toISOString()
                  : null,
              te_tram_obert:
                data.te_tram_obert !== undefined
                  ? Boolean(data.te_tram_obert)
                  : accio === "inici",
              tram_actiu_inici:
                data.tram_actiu_inici !== undefined
                  ? data.tram_actiu_inici
                  : accio === "inici"
                  ? new Date().toISOString()
                  : null,
              temps_acumulat_segons:
                data.temps_acumulat_segons !== undefined
                  ? Number(data.temps_acumulat_segons)
                  : prev.temps_acumulat_segons ?? 0,
              trams_temps: Array.isArray(data.trams_temps)
                ? data.trams_temps
                : prev.trams_temps || [],
              gps_inici_lat: data.gps_inici_lat ?? prev.gps_inici_lat,
              gps_inici_lng: data.gps_inici_lng ?? prev.gps_inici_lng,
              gps_fi_lat: data.gps_fi_lat ?? prev.gps_fi_lat,
              gps_fi_lng: data.gps_fi_lng ?? prev.gps_fi_lng,
              hores_imputades_facturables:
                data.hores_imputades_facturables ?? prev.hores_imputades_facturables,
              desviacio_geovalla: data.desviacio_geovalla ?? prev.desviacio_geovalla,
              justificacio_geovalla: data.justificacio_geovalla ?? prev.justificacio_geovalla,
            }
          : null
      );
      setRequereixJustificacioGPS(false);
      setJustificacioGps("");
      const coordsSuffix =
        coords.latitud != null && coords.longitud != null
          ? ` (GPS: ${coords.latitud.toFixed(4)}, ${coords.longitud.toFixed(4)})`
          : "";
      const avisSuffix = coords.gpsAvis ? ` (${coords.gpsAvis})` : "";
      setGpsFeedback(
        accio === "inici"
          ? `Feina iniciada! Temps real en curs${coordsSuffix}${avisSuffix}`
          : `Feina finalitzada! Total temps registrat: ${
              data.hores_imputades_facturables != null
                ? Number(data.hores_imputades_facturables).toFixed(2)
                : "0.00"
            } h${coordsSuffix}${avisSuffix}`
      );
    } catch (e: unknown) {
      const detail = e instanceof Error ? e.message : "Error registrant el temps de feina";
      if (
        detail.includes("50m") ||
        detail.toLowerCase().includes("geovalla") ||
        detail.toLowerCase().includes("desviaci")
      ) {
        setRequereixJustificacioGPS(true);
      }
      setGpsError(detail);
    } finally {
      setIniciantFeina(false);
    }
  };

  const handleCaptureFotoQA = async (blob: Blob) => {
    if (!tipusFotoActiva) return;
    const tipus = tipusFotoActiva;
    setTipusFotoActiva(null);
    setUploadingFoto(true);
    setGpsError(null);

    try {
      const formData = new FormData();
      formData.append("tipus", tipus);
      formData.append("foto", blob, `ot_${id}_foto_${tipus.toLowerCase()}.webp`);
      formData.append("fitxer", blob, `ot_${id}_foto_${tipus.toLowerCase()}.webp`);

      await apiFetch(`/operari/feines/${id}/fotos`, {
        method: "POST",
        body: formData,
      });

      await carregarEstatFotos();
    } catch (e: unknown) {
      setGpsError(e instanceof Error ? e.message : "Error pujant la fotografia");
    } finally {
      setUploadingFoto(false);
    }
  };

  const loadFeina = async (pin?: string) => {
    setLoading(true);
    setOfflineError(null);
    const checkOffline = typeof navigator !== "undefined" && !navigator.onLine;
    setIsOffline(checkOffline);

    try {
      if (checkOffline) {
        const storedPin = pin || sessionStorage.getItem("sevalor_session_pin");
        if (!storedPin) {
          setShowPinModal(true);
          setLoading(false);
          return;
        }

        const record = await db.ordres.get(id);
        if (!record) {
          throw new Error("Dades no trobades a la memòria cau offline.");
        }

        const saltStr = localStorage.getItem("sevalor_sentinel_salt");
        if (!saltStr)
          throw new Error("No s'ha trobat la sal criptogràfica del dispositiu.");
        const saltBytes = new Uint8Array(saltStr.split(",").map(Number));

        try {
          const decryptedStr = await decryptWithPin(
            record.ciphertext,
            record.iv,
            storedPin,
            saltBytes
          );
          const data = JSON.parse(decryptedStr);

          sessionStorage.setItem("sevalor_session_pin", storedPin);
          setShowPinModal(false);

          setOrdre({
            id: String(data.id),
            codi: data.codi || "OT-00",
            titol: data.titol || "Detall de l'Ordre",
            descripcio: data.descripcio,
            client: data.client?.rao_social || "Client",
            estat: data.estat || "PENDENT",
            adreca: data.adreca || "",
            vehicle: data.vehicle,
            linies_picking: data.linies_picking || [],
            eines_assignades: data.eines_assignades || [],
            assets: data.assets || [],
            planol_id: data.planol_id || null,
            planol_titol: data.planol_titol || null,
            planol_codi: data.planol_codi || null,
            planol_tipus_fitxer: data.planol_tipus_fitxer || null,
            hora_inici_real: data.hora_inici_real || null,
            hora_fi_real: data.hora_fi_real || null,
            gps_inici_lat: data.gps_inici_lat ?? null,
            gps_inici_lng: data.gps_inici_lng ?? null,
            gps_fi_lat: data.gps_fi_lat ?? null,
            gps_fi_lng: data.gps_fi_lng ?? null,
            hores_imputades_facturables: data.hores_imputades_facturables ?? null,
            desviacio_geovalla: Boolean(data.desviacio_geovalla),
            justificacio_geovalla: data.justificacio_geovalla || null,
            te_tram_obert: Boolean(data.te_tram_obert),
            tram_actiu_inici: data.tram_actiu_inici || null,
            temps_acumulat_segons: Number(data.temps_acumulat_segons || 0),
            trams_temps: Array.isArray(data.trams_temps) ? data.trams_temps : [],
            signatura_client_path: data.signatura_client_path || null,
            nom_receptor: data.nom_receptor || null,
            dni_receptor: data.dni_receptor || null,
            observacions_tancament: data.observacions_tancament || null,
            data_signatura: data.data_signatura || null,
          });
          if (data.nom_receptor) setNomReceptor(data.nom_receptor);
          if (data.dni_receptor) setDniReceptor(data.dni_receptor);
          if (data.observacions_tancament) setObservacionsTancament(data.observacions_tancament);
        } catch {
          throw new Error("PIN incorrecte o error de desxifratge.");
        }
      } else {
        const data = await apiFetch<any>(`/operari/feines/${id}`);
        if (data) {
          const mapped: OrdreDetall = {
            id: String(data.id),
            codi: data.codi || "OT-00",
            titol: data.titol || "Detall de l'Ordre",
            descripcio: data.descripcio,
            client: data.client?.rao_social || "Client",
            estat: data.estat || "PENDENT",
            adreca: data.adreca || "",
            vehicle: data.vehicle,
            linies_picking: data.linies_picking || [],
            eines_assignades: data.eines_assignades || [],
            assets: data.assets || [],
            planol_id: data.planol_id || null,
            planol_titol: data.planol_titol || null,
            planol_codi: data.planol_codi || null,
            planol_tipus_fitxer: data.planol_tipus_fitxer || null,
            hora_inici_real: data.hora_inici_real || null,
            hora_fi_real: data.hora_fi_real || null,
            gps_inici_lat: data.gps_inici_lat ?? null,
            gps_inici_lng: data.gps_inici_lng ?? null,
            gps_fi_lat: data.gps_fi_lat ?? null,
            gps_fi_lng: data.gps_fi_lng ?? null,
            hores_imputades_facturables: data.hores_imputades_facturables ?? null,
            desviacio_geovalla: Boolean(data.desviacio_geovalla),
            justificacio_geovalla: data.justificacio_geovalla || null,
            te_tram_obert: Boolean(data.te_tram_obert),
            tram_actiu_inici: data.tram_actiu_inici || null,
            temps_acumulat_segons: Number(data.temps_acumulat_segons || 0),
            trams_temps: Array.isArray(data.trams_temps) ? data.trams_temps : [],
            signatura_client_path: data.signatura_client_path || null,
            nom_receptor: data.nom_receptor || null,
            dni_receptor: data.dni_receptor || null,
            observacions_tancament: data.observacions_tancament || null,
            data_signatura: data.data_signatura || null,
          };
          setOrdre(mapped);
          if (mapped.nom_receptor) setNomReceptor(mapped.nom_receptor);
          if (mapped.dni_receptor) setDniReceptor(mapped.dni_receptor);
          if (mapped.observacions_tancament) setObservacionsTancament(mapped.observacions_tancament);
          await carregarEstatFotos();

          // Guardar xifrat a IndexedDB si tenim el PIN
          const sessionPin = sessionStorage.getItem("sevalor_session_pin");
          const saltStr = localStorage.getItem("sevalor_sentinel_salt");
          if (sessionPin && saltStr) {
            const saltBytes = new Uint8Array(saltStr.split(",").map(Number));
            const { cipherTextHex, ivHex } = await encryptWithPin(
              JSON.stringify(data),
              sessionPin,
              saltBytes
            );
            await db.ordres.put({
              id: mapped.id,
              ciphertext: cipherTextHex,
              iv: ivHex,
            });
          }
        }
      }
    } catch (err: any) {
      if (err.message.includes("PIN incorrecte")) {
        setOfflineError("PIN incorrecte. Torna-ho a provar.");
        setShowPinModal(true);
      } else {
        setOrdre(null);
        setOfflineError(err.message);
      }
    } finally {
      if (!showPinModal) setLoading(false);
    }
  };

  const [iniciantTrajecte, setIniciantTrajecte] = useState(false);
  const [trajecteFeedback, setTrajecteFeedback] = useState<string | null>(null);
  const [trajecteError, setTrajecteError] = useState<string | null>(null);

  // Box 6: Signatura de conformitat del client inline
  const [nomReceptor, setNomReceptor] = useState("");
  const [dniReceptor, setDniReceptor] = useState("");
  const [observacionsTancament, setObservacionsTancament] = useState("");
  const [desantSignatura, setDesantSignatura] = useState(false);
  const [signaturaFeedback, setSignaturaFeedback] = useState<string | null>(null);
  const [signaturaError, setSignaturaError] = useState<string | null>(null);
  const [mostrarReSignar, setMostrarReSignar] = useState(false);
  const [finalitzantOrdre, setFinalitzantOrdre] = useState(false);

  const handleIniciarTrajecte = async () => {
    setIniciantTrajecte(true);
    setTrajecteFeedback(null);
    setTrajecteError(null);
    try {
      const res = await apiFetch<{ missatge?: string }>(`/operari/feines/${id}/iniciar-trajecte`, {
        method: "PUT",
      });
      setOrdre((prev) =>
        prev
          ? {
              ...prev,
              estat: ["PENDENT", "ASSIGNADA", "PROGRAMADA"].includes(prev.estat)
                ? "EN_RUTA"
                : prev.estat,
            }
          : null
      );
      setTrajecteFeedback(res?.missatge || "Trajecte iniciat! Vehicle en ruta (ETA 25 min).");
    } catch (e: unknown) {
      setTrajecteError(
        e instanceof Error ? e.message : "No s'ha pogut iniciar el trajecte."
      );
    } finally {
      setIniciantTrajecte(false);
    }
  };

  const scrollToSection = (sectionId: string) => {
    if (typeof document === "undefined") return;
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const handleGuardarSignaturaInline = async (base64Signature: string) => {
    setDesantSignatura(true);
    setSignaturaError(null);
    setSignaturaFeedback(null);
    try {
      const nomClean = nomReceptor.trim() || undefined;
      const dniClean = dniReceptor.trim().toUpperCase() || undefined;
      const obsClean = observacionsTancament.trim() || undefined;

      if (typeof navigator !== "undefined" && navigator.onLine) {
        const res = await apiFetch<any>(`/operari/feines/${id}/signatura`, {
          method: "PUT",
          body: JSON.stringify({
            signatura_base64: base64Signature,
            nom_receptor: nomClean,
            dni_receptor: dniClean,
            observacions: obsClean,
          }),
        });
        setOrdre((prev) =>
          prev
            ? {
                ...prev,
                signatura_client_path: res?.signatura_client_path || "DESADA",
                nom_receptor: res?.nom_receptor ?? nomClean ?? prev.nom_receptor,
                dni_receptor: res?.dni_receptor ?? dniClean ?? prev.dni_receptor,
                observacions_tancament:
                  res?.observacions_tancament ?? obsClean ?? prev.observacions_tancament,
                data_signatura: res?.data_signatura || new Date().toISOString(),
              }
            : null
        );
        setMostrarReSignar(false);
        setSignaturaFeedback(
          "Signatura de conformitat del client desada al disc de l'empresa."
        );
      } else {
        await db.sync_queue.add({
          action: "TANCAR_ORDRE",
          payload: {
            ordre_id: id,
            signatura_base64: base64Signature,
            nom_receptor: nomClean,
            dni_receptor: dniClean,
            nom_signant: nomClean,
            dni_signant: dniClean,
            observacions: obsClean,
            hores: ordre?.hores_imputades_facturables ?? undefined,
            data_tancament: new Date().toISOString(),
          },
          status: "pending",
          createdAt: Date.now(),
        });
        setOrdre((prev) =>
          prev
            ? {
                ...prev,
                signatura_client_path: "OFFLINE_PENDENT",
                nom_receptor: nomClean ?? prev.nom_receptor,
                dni_receptor: dniClean ?? prev.dni_receptor,
                observacions_tancament: obsClean ?? prev.observacions_tancament,
                data_signatura: new Date().toISOString(),
              }
            : null
        );
        setMostrarReSignar(false);
        setSignaturaFeedback(
          "Signatura desada a la cua offline. Se sincronitzarà en recuperar connexió."
        );
      }
    } catch (e: unknown) {
      setSignaturaError(
        e instanceof Error ? e.message : "No s'ha pogut desar la signatura del client."
      );
    } finally {
      setDesantSignatura(false);
    }
  };

  const handleFinalitzarOrdreInline = async () => {
    setFinalitzantOrdre(true);
    setSignaturaError(null);
    setSignaturaFeedback(null);
    try {
      const horesAImputar =
        ordre?.hores_imputades_facturables != null && ordre.hores_imputades_facturables > 0
          ? ordre.hores_imputades_facturables
          : undefined;
      const res = await apiFetch<any>(`/operari/feines/${id}/finalitzar`, {
        method: "PUT",
        body: JSON.stringify({
          nom_receptor: nomReceptor.trim() || undefined,
          dni_receptor: dniReceptor.trim().toUpperCase() || undefined,
          observacions: observacionsTancament.trim() || undefined,
          hores: horesAImputar,
        }),
      });
      setOrdre((prev) =>
        prev
          ? {
              ...prev,
              estat: res?.estat || "COMPLERT",
              te_tram_obert: false,
              nom_receptor: res?.nom_receptor ?? prev.nom_receptor,
              dni_receptor: res?.dni_receptor ?? prev.dni_receptor,
              observacions_tancament:
                res?.observacions_tancament ?? prev.observacions_tancament,
              signatura_client_path:
                res?.signatura_client_path ?? prev.signatura_client_path,
              data_signatura: res?.data_signatura ?? prev.data_signatura,
            }
          : null
      );
      setSignaturaFeedback("Ordre finalitzada i tancada correctament!");
    } catch (e: unknown) {
      setSignaturaError(
        e instanceof Error ? e.message : "No s'ha pogut tancar l'ordre de treball."
      );
    } finally {
      setFinalitzantOrdre(false);
    }
  };

  useEffect(() => {
    loadFeina();
    apiFetch<any>("/auth/me")
      .then((me) => {
        if (me && me.feature_copilot_ia === false) setHasCopilotIa(false);
      })
      .catch(() => {});
  }, [id]);

  const getAssetIcon = (tipus: string) => {
    switch (tipus?.toUpperCase()) {
      case "SERVIDOR":
        return <Server className="w-5 h-5" />;
      case "XARXA":
        return <HardDrive className="w-5 h-5" />;
      case "IOT":
        return <Cpu className="w-5 h-5" />;
      case "MOBILE":
        return <Smartphone className="w-5 h-5" />;
      default:
        return <Settings className="w-5 h-5" />;
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-surface dark:bg-slate-950 text-on-surface dark:text-slate-100 transition-colors p-4 space-y-4">
      {tipusFotoActiva && (
        <CameraCapture
          onCapture={handleCaptureFotoQA}
          onCancel={() => setTipusFotoActiva(null)}
        />
      )}

      {/* Stitch Top Sub-navigation Header */}
      <div className="flex items-center justify-between bg-surface-container-lowest dark:bg-slate-900 p-3 rounded-xl border border-outline-variant/20 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => router.back()}
            className="w-9 h-9 rounded-lg bg-surface-container-low dark:bg-slate-800 hover:bg-surface-container flex items-center justify-center text-primary dark:text-white transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant dark:text-slate-400 block">
              Execució d&apos;Ordre
            </span>
            <h1 className="text-base font-extrabold text-primary dark:text-slate-100 leading-tight">
              Fitxa 360 - {ordre ? ordre.codi : id}
            </h1>
          </div>
        </div>
        {ordre && (
          <span
            className={`text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full border ${
              ordre.estat === "PENDENT"
                ? "bg-amber-500/10 text-amber-600 border-amber-500/20"
                : ordre.estat === "EN_RUTA" || ordre.estat === "EN_CURS"
                ? "bg-secondary-container/15 text-secondary border-secondary-container/30"
                : "bg-primary-fixed text-on-primary-fixed-variant border-primary/20"
            }`}
          >
            {ordre.estat}
          </span>
        )}
      </div>

      {/* AES-GCM Offline Unlock Modal */}
      {showPinModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-container-lowest dark:bg-slate-900 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-4 border border-outline-variant/30">
            <h3 className="text-lg font-extrabold text-primary dark:text-white text-center">
              Desbloqueig Offline
            </h3>
            <p className="text-xs text-on-surface-variant text-center">
              Introdueix el teu PIN per desxifrar les dades locals (AES-GCM 256).
            </p>
            {offlineError && (
              <p className="text-xs text-error font-bold text-center">
                {offlineError}
              </p>
            )}
            <input
              type="password"
              maxLength={4}
              value={offlinePin}
              onChange={(e) =>
                setOfflinePin(e.target.value.replace(/\D/g, ""))
              }
              className="w-full px-4 py-3 text-center text-2xl tracking-widest font-mono font-bold rounded-xl border border-outline-variant dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-secondary-container text-primary dark:text-white"
              placeholder="••••"
            />
            <button
              onClick={() => loadFeina(offlinePin)}
              disabled={offlinePin.length !== 4}
              className="w-full py-3 rounded-xl text-sm font-bold bg-secondary-container hover:brightness-110 text-white transition-all disabled:opacity-50"
            >
              Desxifrar Fitxa
            </button>
            <button
              onClick={() => router.back()}
              className="w-full py-2 rounded-xl text-xs font-bold text-on-surface-variant hover:text-primary dark:hover:text-slate-300 transition-colors"
            >
              Tornar
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-on-surface-variant">
          <Wrench className="w-8 h-8 animate-spin mx-auto mb-2 text-primary" />
          <p className="text-xs font-bold uppercase tracking-wider">
            Carregant dades...
          </p>
        </div>
      ) : !ordre ? (
        <div className="text-center py-12 bg-surface-container-lowest dark:bg-slate-900 rounded-xl shadow-sm border border-outline-variant/30 dark:border-slate-800">
          <FileText className="w-8 h-8 mx-auto text-outline mb-2" />
          <p className="text-sm font-bold text-primary dark:text-slate-300">
            {isOffline
              ? "No s'ha pogut desxifrar la fitxa offline (falta PIN)."
              : "No s'ha trobat l'ordre de treball."}
          </p>
        </div>
      ) : (
        <>
          {/* BOX 1: CAPÇALERA DE L'ORDRE I CONTROL DE TEMPS */}
          <section
            id="box-feina"
            data-testid="box-1-feina"
            className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3 relative overflow-hidden"
          >
            <div className="absolute top-0 left-0 bottom-0 w-1.5 bg-secondary-container" />
            <div className="pl-2 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-primary text-white text-xs font-extrabold flex items-center justify-center shrink-0">
                      1
                    </span>
                    <span className="font-mono text-xs font-bold text-secondary bg-secondary-container/15 px-2 py-0.5 rounded">
                      {ordre.codi}
                    </span>
                  </div>
                  <h2 className="text-lg font-extrabold text-primary dark:text-slate-100 mt-1.5 leading-snug">
                    {ordre.titol}
                  </h2>
                  <p className="text-xs font-semibold text-on-surface-variant dark:text-slate-400 mt-0.5">
                    {ordre.client}
                  </p>
                </div>
              </div>

              {ordre.descripcio && (
                <div className="p-3 rounded-lg bg-surface-container-low dark:bg-slate-800/60 text-xs text-on-surface dark:text-slate-300 leading-relaxed">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                    Instruccions Tècniques
                  </span>
                  {ordre.descripcio}
                </div>
              )}

              {ordre.adreca && (
                <div className="flex items-center gap-2 text-xs text-on-surface-variant dark:text-slate-400 border-t border-surface-container dark:border-slate-800 pt-2.5">
                  <MapPin className="w-4 h-4 text-secondary shrink-0" />
                  <span className="font-medium">{ordre.adreca}</span>
                </div>
              )}

              {(() => {
                const trams = ordre.trams_temps || [];
                const isTancadaDefinitivament =
                  ordre.estat === "TANCADA" || ordre.estat === "COMPLERT";
                const isTramObert = Boolean(
                  !isTancadaDefinitivament &&
                    (ordre.te_tram_obert ||
                      (ordre.estat === "EN_CURS" &&
                        ordre.hora_inici_real &&
                        !ordre.hora_fi_real))
                );
                const teHistorialPrevi = Boolean(
                  trams.length > 0 ||
                    (ordre.temps_acumulat_segons || 0) > 0 ||
                    ordre.hora_fi_real ||
                    (ordre.hores_imputades_facturables &&
                      Number(ordre.hores_imputades_facturables) > 0)
                );
                const horesTreballades = Number(ordre.hores_imputades_facturables || 0);
                const acumulatSegons = ordre.temps_acumulat_segons || 0;

                return (
                  <div className="pt-2 border-t border-surface-container dark:border-slate-800 space-y-3">
                    {/* BOTONS INDIVIDUALS INICIAR FEINA / FINALITZAR FEINA + GPS */}
                    {!isTancadaDefinitivament && (
                      <div className="space-y-3">
                        {isTramObert && (
                          <div className="p-3.5 rounded-xl bg-secondary-container/10 border border-secondary-container/30 space-y-2">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="w-2.5 h-2.5 rounded-full bg-secondary-container animate-pulse" />
                                <span className="text-xs font-extrabold uppercase tracking-wider text-secondary">
                                  Feina en Curs
                                </span>
                              </div>
                              <span className="font-mono text-lg font-black text-primary dark:text-slate-100">
                                ⏱️ {tempsTranscorregut}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-[11px] text-on-surface-variant dark:text-slate-400 border-t border-secondary-container/20 pt-2">
                              <span>
                                Sessió actual:{" "}
                                <strong className="font-mono text-slate-800 dark:text-slate-200">
                                  {tempsSessioActual}
                                </strong>
                                {acumulatPreviLabel(acumulatSegons)}
                              </span>
                              <span className="font-bold text-secondary font-mono">
                                ~{horesLiveEstimades.toFixed(2)} h
                              </span>
                            </div>
                          </div>
                        )}

                        <div className="grid grid-cols-2 gap-2.5">
                          <button
                            type="button"
                            data-testid="btn-iniciar-feina-gps"
                            disabled={iniciantFeina || isTramObert}
                            onClick={() => handleMarcarTempsGps("inici")}
                            className="min-h-[52px] px-3 py-2.5 bg-primary hover:brightness-110 text-white font-bold text-xs uppercase tracking-wider rounded-xl flex flex-col items-center justify-center gap-1 shadow-sm active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                          >
                            <div className="flex items-center gap-1.5">
                              <Play className="w-4 h-4 text-secondary-container fill-current" />
                              <span>
                                {iniciantFeina && accioPendentGps === "inici"
                                  ? "Registrant GPS..."
                                  : "Iniciar Feina"}
                              </span>
                            </div>
                            <span className="text-[10px] font-medium normal-case tracking-normal opacity-80 flex items-center gap-1">
                              <MapPin className="w-3 h-3" />
                              Inici temps + GPS
                            </span>
                          </button>

                          <button
                            type="button"
                            data-testid="btn-finalitzar-feina-gps"
                            disabled={iniciantFeina || !isTramObert}
                            onClick={() => handleMarcarTempsGps("final")}
                            className="min-h-[52px] px-3 py-2.5 bg-secondary-container hover:brightness-110 text-white font-bold text-xs uppercase tracking-wider rounded-xl flex flex-col items-center justify-center gap-1 shadow-sm active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                          >
                            <div className="flex items-center gap-1.5">
                              <Square className="w-3.5 h-3.5 fill-current" />
                              <span>
                                {iniciantFeina && accioPendentGps === "final"
                                  ? "Registrant GPS..."
                                  : "Finalitzar Feina"}
                              </span>
                            </div>
                            <span className="text-[10px] font-medium normal-case tracking-normal opacity-90 flex items-center gap-1">
                              <MapPin className="w-3 h-3" />
                              Fi temps + GPS
                            </span>
                          </button>
                        </div>

                        <p className="text-[11px] text-center text-on-surface-variant dark:text-slate-400">
                          {isTramObert
                            ? "Prem Finalitzar Feina per aturar el temps real i desar la ubicació GPS."
                            : "Prem Iniciar Feina per activar el temps real i registrar la posició GPS."}
                        </p>
                      </div>
                    )}

                    {/* RESUM DE TEMPS TREBALLAT (SENSE DADES ECONÒMIQUES) */}
                    {teHistorialPrevi && (
                      <div className="p-3.5 rounded-xl bg-surface-container-low dark:bg-slate-800/80 border border-secondary-container/35 space-y-3">
                        <div className="flex items-center justify-between border-b border-outline-variant/20 dark:border-slate-700/60 pb-2">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-secondary" />
                            <span className="text-xs font-extrabold uppercase tracking-wider text-primary dark:text-slate-100">
                              {isTramObert
                                ? "Temps Acumulat Previ"
                                : "Còmput Total de Treball"}
                            </span>
                          </div>
                          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-secondary-container/20 text-secondary">
                            {trams.length > 0 ? `${trams.length} trams` : "Registrat"}
                          </span>
                        </div>

                        {/* Targeta Resum Temps Treballat (Sense preus ni tarifes) */}
                        <div className="p-3 rounded-lg bg-secondary-container/15 border border-secondary-container/40 flex items-center justify-between">
                          <div>
                            <span className="text-[10px] font-extrabold uppercase tracking-wider text-secondary block">
                              Total temps real treballat
                            </span>
                            <span className="text-xs text-on-surface-variant dark:text-slate-400">
                              Registre acumulat amb posició GPS
                            </span>
                          </div>
                          <div className="text-right">
                            <span className="text-xl font-mono font-black text-primary dark:text-slate-100">
                              {horesTreballades.toFixed(2)} h
                            </span>
                            <span className="block text-xs font-mono font-bold text-secondary">
                              {formatSegonsHMS(acumulatSegons)}
                            </span>
                          </div>
                        </div>

                        {/* Llista de trams (Iniciar / Finalitzar) */}
                        {trams.length > 0 && (
                          <div className="space-y-1.5">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant block">
                              Registre de trams horaris ({trams.length})
                            </span>
                            <div className="space-y-1">
                              {trams.map((tram, idx) => {
                                const dtIni = new Date(tram.hora_inici);
                                const dtFi = tram.hora_fi ? new Date(tram.hora_fi) : null;
                                const mateixDia =
                                  dtFi &&
                                  dtIni.toDateString() === dtFi.toDateString();
                                const iniciFmt = dtIni.toLocaleTimeString(
                                  "ca-ES",
                                  { hour: "2-digit", minute: "2-digit" }
                                );
                                const iniciComplet = mateixDia
                                  ? iniciFmt
                                  : `${dtIni.toLocaleDateString("ca-ES", {
                                      day: "2-digit",
                                      month: "2-digit",
                                    })} ${iniciFmt}`;
                                const fiFmt = dtFi
                                  ? mateixDia
                                    ? dtFi.toLocaleTimeString("ca-ES", {
                                        hour: "2-digit",
                                        minute: "2-digit",
                                      })
                                    : `${dtFi.toLocaleDateString("ca-ES", {
                                        day: "2-digit",
                                        month: "2-digit",
                                      })} ${dtFi.toLocaleTimeString("ca-ES", {
                                        hour: "2-digit",
                                        minute: "2-digit",
                                      })}`
                                  : "En curs";
                                const hasGpsInici =
                                  tram.gps_inici_lat != null && tram.gps_inici_lng != null;
                                const hasGpsFi =
                                  tram.gps_fi_lat != null && tram.gps_fi_lng != null;
                                return (
                                  <div
                                    key={tram.id}
                                    className="px-2.5 py-2 rounded-lg bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/15 space-y-1 text-[11px]"
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-2">
                                        <span className="font-bold text-primary dark:text-slate-200">
                                          #{idx + 1}
                                        </span>
                                        <span className="font-mono text-slate-700 dark:text-slate-300">
                                          {iniciComplet} → {fiFmt}
                                        </span>
                                      </div>
                                      <span className="font-mono font-bold text-secondary">
                                        {tram.hora_fi
                                          ? formatSegonsHMS(tram.durada_segons)
                                          : "Actiu"}
                                      </span>
                                    </div>
                                    {(hasGpsInici || hasGpsFi) && (
                                      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10px] font-mono text-on-surface-variant dark:text-slate-400">
                                        {hasGpsInici && (
                                          <span className="inline-flex items-center gap-1">
                                            <MapPin className="w-3 h-3 text-secondary shrink-0" />
                                            Inici: {Number(tram.gps_inici_lat).toFixed(4)}, {Number(tram.gps_inici_lng).toFixed(4)}
                                          </span>
                                        )}
                                        {hasGpsFi && (
                                          <span className="inline-flex items-center gap-1">
                                            <MapPin className="w-3 h-3 text-primary shrink-0" />
                                            Final: {Number(tram.gps_fi_lat).toFixed(4)}, {Number(tram.gps_fi_lng).toFixed(4)}
                                          </span>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {ordre.desviacio_geovalla && (
                          <div className="pt-1 flex items-start gap-1.5 text-amber-600 dark:text-amber-400 text-[11px] font-medium leading-tight">
                            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                            <span>
                              <strong>Excepció Geovalla autoritzada:</strong>{" "}
                              {ordre.justificacio_geovalla || "Desviació justificada"}
                            </span>
                          </div>
                        )}
                      </div>
                    )}

                    {requereixJustificacioGPS && (
                      <div
                        data-testid="geofence-justification-box"
                        className="p-3 rounded-lg bg-error-container/25 border border-error space-y-2"
                      >
                        <p className="text-[11px] font-bold text-error uppercase">
                          Fora del radi de 50m de l&apos;obra (FR-005)
                        </p>
                        <textarea
                          value={justificacioGps}
                          onChange={(e) => setJustificacioGps(e.target.value)}
                          placeholder="Motiu de la desviació (ex: accés bloquejat, aparcament a 100m...)"
                          className="w-full p-2 text-xs rounded bg-surface-container-lowest border border-outline-variant text-on-surface"
                          rows={2}
                        />
                        <button
                          type="button"
                          disabled={iniciantFeina || !justificacioGps.trim()}
                          onClick={() => handleMarcarTempsGps(accioPendentGps)}
                          className="w-full py-2 bg-error text-white font-bold text-xs uppercase rounded active:scale-95 transition-transform disabled:opacity-50"
                        >
                          {iniciantFeina
                            ? "Registrant Excepció..."
                            : accioPendentGps === "inici"
                            ? "Confirmar Obertura amb Justificació"
                            : "Confirmar Tancament amb Justificació"}
                        </button>
                      </div>
                    )}

                    {gpsFeedback && (
                      <p className="text-xs font-semibold text-secondary bg-secondary-container/20 p-2 rounded">
                        {gpsFeedback}
                      </p>
                    )}
                    {gpsError && (
                      <p className="text-xs font-semibold text-error bg-error-container/25 p-2 rounded">
                        {gpsError}
                      </p>
                    )}
                  </div>
                );
              })()}
            </div>
          </section>

          {/* ============================================================== */}
          {/* BOX 2: VEHICLE ASSIGNAT + PICKING FURGONETA + ACCIONS RÀPIDES  */}
          {/* ============================================================== */}
          <section
            id="box-vehicle"
            data-testid="box-2-vehicle"
            className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary text-white text-xs font-extrabold flex items-center justify-center shrink-0">
                  2
                </span>
                <div>
                  <h3 className="text-sm font-extrabold text-primary dark:text-slate-100 leading-tight">
                    Vehicle assignat i ruta
                  </h3>
                  <p className="text-[11px] text-on-surface-variant dark:text-slate-400">
                    Fulla de picking de la furgoneta i accions operatives
                  </p>
                </div>
              </div>
              {ordre.vehicle && (
                <span className="font-mono text-xs font-bold bg-surface-container-high dark:bg-slate-800 px-2.5 py-1 rounded-lg text-primary dark:text-slate-200 shrink-0">
                  {ordre.vehicle.matricula}
                </span>
              )}
            </div>

            {ordre.vehicle ? (
              <div className="space-y-2">
                <Link
                  href={`/operari/vehicles?vehicle_id=${ordre.vehicle.id}&ordre_id=${ordre.id}&tab=ESTOC`}
                  data-testid="link-vehicle-picking"
                  className="p-3 rounded-xl bg-surface-container-low dark:bg-slate-800/70 hover:bg-surface-container dark:hover:bg-slate-800 border border-outline-variant/30 dark:border-slate-700 flex items-center justify-between gap-3 transition-colors group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="p-2.5 bg-primary/10 dark:bg-primary/20 rounded-xl text-primary dark:text-slate-100 shrink-0">
                      <Truck className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-extrabold text-primary dark:text-slate-100 truncate">
                        {[ordre.vehicle.marca, ordre.vehicle.model].filter(Boolean).join(" ") ||
                          "Furgoneta assignada"}
                      </p>
                      <p className="text-[11px] font-semibold text-secondary">
                        Obrir fulla de picking de la furgoneta
                      </p>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-secondary shrink-0 group-hover:translate-x-0.5 transition-transform" />
                </Link>

                <div className="flex items-center justify-end gap-3 px-1">
                  <Link
                    href={`/operari/vehicles?vehicle_id=${ordre.vehicle.id}&ordre_id=${ordre.id}&tab=CONTROL`}
                    className="text-[11px] font-semibold text-on-surface-variant hover:text-primary dark:text-slate-400 dark:hover:text-slate-200 underline-offset-2 hover:underline"
                  >
                    Check-in / Odòmetre
                  </Link>
                  <Link
                    href={`/operari/vehicles?vehicle_id=${ordre.vehicle.id}&ordre_id=${ordre.id}&tab=REPOSTATGE`}
                    className="text-[11px] font-semibold text-on-surface-variant hover:text-primary dark:text-slate-400 dark:hover:text-slate-200 underline-offset-2 hover:underline"
                  >
                    Repostatge
                  </Link>
                </div>
              </div>
            ) : (
              <Link
                href={`/operari/vehicles?ordre_id=${ordre.id}&tab=ESTOC`}
                data-testid="link-vehicle-picking"
                className="p-3 rounded-xl bg-surface-container-low/70 dark:bg-slate-800/50 border border-dashed border-outline-variant/40 dark:border-slate-700 flex items-center justify-between gap-2 text-xs text-on-surface-variant hover:border-primary/40 transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <Truck className="w-4 h-4 text-outline shrink-0" />
                  <span>Cap vehicle vinculat — Consultar flota i picking furgoneta</span>
                </div>
                <ChevronRight className="w-4 h-4 shrink-0" />
              </Link>
            )}

            {/* Botons d'Acció Ràpida: Iniciar Trajecte, Copilot IA, Fotos */}
            <div className={`grid gap-2.5 ${hasCopilotIa ? "grid-cols-3" : "grid-cols-2"}`}>
              <button
                type="button"
                data-testid="btn-iniciar-trajecte"
                onClick={handleIniciarTrajecte}
                disabled={
                  iniciantTrajecte ||
                  ordre.estat === "EN_RUTA" ||
                  ordre.estat === "EN_CURS" ||
                  ordre.estat === "COMPLERT" ||
                  ordre.estat === "TANCADA"
                }
                className="py-3 px-2.5 rounded-xl bg-primary-container hover:bg-primary text-white text-xs font-bold flex flex-col items-center justify-center gap-1.5 shadow-sm transition-all disabled:opacity-45 cursor-pointer active:scale-95"
              >
                <Navigation className="w-4 h-4" />
                <span className="leading-tight text-center">
                  {iniciantTrajecte
                    ? "Activant..."
                    : ordre.estat === "EN_RUTA"
                    ? "En Ruta"
                    : "Iniciar Trajecte"}
                </span>
              </button>

              {hasCopilotIa && (
                <Link
                  href={`/operari/feines/${ordre.id}/copilot`}
                  data-testid="btn-copilot-ia"
                  className="py-3 px-2.5 rounded-xl bg-secondary-container hover:brightness-110 text-white text-xs font-bold flex flex-col items-center justify-center gap-1.5 shadow-sm transition-all text-center active:scale-95"
                >
                  <Bot className="w-4 h-4" />
                  <span className="leading-tight">Copilot IA</span>
                </Link>
              )}

              <button
                type="button"
                data-testid="btn-acces-fotos"
                onClick={() => scrollToSection("box-fotos")}
                className={`py-3 px-2.5 rounded-xl text-xs font-bold flex flex-col items-center justify-center gap-1.5 shadow-sm transition-all cursor-pointer active:scale-95 ${
                  estatFotos.protocol_complet
                    ? "bg-secondary-container/15 text-secondary border border-secondary-container/40"
                    : "bg-primary hover:bg-primary-container text-white"
                }`}
              >
                <Camera className="w-4 h-4" />
                <span className="leading-tight">
                  Fotos ({estatFotos.fotos_pujades.length}/3)
                </span>
              </button>
            </div>

            {trajecteFeedback && (
              <p className="text-xs font-semibold text-secondary bg-secondary-container/15 px-3 py-2 rounded-lg">
                {trajecteFeedback}
              </p>
            )}
            {trajecteError && (
              <p className="text-xs font-semibold text-error bg-error-container/25 px-3 py-2 rounded-lg">
                {trajecteError}
              </p>
            )}
          </section>

          {/* ============================================================== */}
          {/* BOX 3: PICKING DEL MATERIAL                                    */}
          {/* ============================================================== */}
          <section
            id="box-material"
            data-testid="box-3-material"
            className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary text-white text-xs font-extrabold flex items-center justify-center shrink-0">
                  3
                </span>
                <div>
                  <h3 className="text-sm font-extrabold text-primary dark:text-slate-100 leading-tight flex items-center gap-1.5">
                    <Package className="w-4 h-4 text-secondary" />
                    <span>Picking del material ({ordre.linies_picking?.length || 0})</span>
                  </h3>
                  <p className="text-[11px] text-on-surface-variant dark:text-slate-400">
                    Pick-In matinal, consum a furgoneta i Pick-Out de sobrants
                  </p>
                </div>
              </div>
              <Link
                href={`/operari/material?ordre_id=${ordre.id}&fase=PICK_IN`}
                data-testid="link-picking-material"
                className="px-2.5 py-1.5 rounded-lg bg-secondary-container/15 hover:bg-secondary-container/25 text-secondary text-xs font-bold flex items-center gap-1 shrink-0 transition-colors"
              >
                <span>Picking</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {!ordre.linies_picking || ordre.linies_picking.length === 0 ? (
              <div className="p-4 rounded-xl border border-dashed border-outline-variant/40 dark:border-slate-800 text-center space-y-2.5 bg-surface-container-low/40 dark:bg-slate-800/30">
                <p className="text-xs text-on-surface-variant dark:text-slate-400">
                  Cap material de picking vinculat a aquesta feina.
                </p>
                <Link
                  href={`/operari/material?ordre_id=${ordre.id}&fase=OBRA`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-bold shadow-sm"
                >
                  <Truck className="w-3.5 h-3.5" />
                  <span>Agafar peça de la furgoneta</span>
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {ordre.linies_picking.map((linia) => {
                  const carregatComplet =
                    linia.quantitat_prevista > 0 &&
                    linia.quantitat_carregada_pick_in >= linia.quantitat_prevista;
                  const unitat = linia.unitat_mesura || "uts";
                  return (
                    <Link
                      key={linia.id}
                      href={`/operari/material?ordre_id=${ordre.id}&fase=${
                        carregatComplet ? "PICK_OUT" : "PICK_IN"
                      }`}
                      className={`p-3 rounded-xl border flex items-center justify-between gap-2 transition-colors ${
                        carregatComplet
                          ? "bg-secondary-container/10 border-secondary-container/35"
                          : "bg-surface-container-low/60 dark:bg-slate-800/50 border-outline-variant/25 dark:border-slate-800 hover:border-primary/40"
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {carregatComplet && (
                            <CheckCircle2 className="w-3.5 h-3.5 text-secondary shrink-0" />
                          )}
                          <h4 className="text-xs font-bold text-primary dark:text-slate-100 truncate">
                            {linia.article_nom}
                          </h4>
                          {linia.origen_estoc === "FURGONETA" && (
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-secondary-container/15 text-secondary">
                              Furgoneta
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] font-mono text-on-surface-variant dark:text-slate-400 mt-0.5">
                          Pick-In: {linia.quantitat_carregada_pick_in} / {linia.quantitat_prevista} {unitat}
                          {linia.quantitat_retornada_pick_out
                            ? ` · Retorn: ${linia.quantitat_retornada_pick_out}`
                            : ""}
                        </p>
                      </div>
                      <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-lg bg-surface-container-lowest dark:bg-slate-800 text-primary dark:text-slate-200 border border-outline-variant/20 shrink-0">
                        {linia.quantitat_prevista} {unitat}
                      </span>
                    </Link>
                  );
                })}

                <div className="grid grid-cols-2 gap-2 pt-1">
                  <Link
                    href={`/operari/material?ordre_id=${ordre.id}&fase=PICK_IN`}
                    className="py-2 px-3 rounded-lg bg-primary text-white text-xs font-bold text-center shadow-sm hover:brightness-110 transition-all"
                  >
                    Fer Pick-In (Nau)
                  </Link>
                  <Link
                    href={`/operari/material?ordre_id=${ordre.id}&fase=PICK_OUT`}
                    className="py-2 px-3 rounded-lg bg-surface-container-high dark:bg-slate-800 text-primary dark:text-slate-100 text-xs font-bold text-center hover:bg-surface-container transition-colors"
                  >
                    Devolució Pick-Out
                  </Link>
                </div>
              </div>
            )}
          </section>

          {/* ============================================================== */}
          {/* BOX 4: EINES EN CUSTÒDIA (LINK A /operari/material BOX EINES)  */}
          {/* ============================================================== */}
          <section
            id="box-eines"
            data-testid="box-4-eines"
            className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary text-white text-xs font-extrabold flex items-center justify-center shrink-0">
                  4
                </span>
                <div>
                  <h3 className="text-sm font-extrabold text-primary dark:text-slate-100 leading-tight flex items-center gap-1.5">
                    <Wrench className="w-4 h-4 text-amber-500" />
                    <span>Eines en custòdia ({ordre.eines_assignades?.length || 0})</span>
                  </h3>
                  <p className="text-[11px] text-on-surface-variant dark:text-slate-400">
                    Pick-In de sortida i Pick-Out de retorn d&apos;eines
                  </p>
                </div>
              </div>
              <Link
                href={`/operari/material?ordre_id=${ordre.id}&fase=EINES`}
                data-testid="link-picking-eines"
                className="px-2.5 py-1.5 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 text-amber-700 dark:text-amber-300 text-xs font-bold flex items-center gap-1 shrink-0 transition-colors"
              >
                <span>Box Eines</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {!ordre.eines_assignades || ordre.eines_assignades.length === 0 ? (
              <div className="p-4 rounded-xl border border-dashed border-outline-variant/40 dark:border-slate-800 text-center space-y-2.5 bg-surface-container-low/40 dark:bg-slate-800/30">
                <p className="text-xs text-on-surface-variant dark:text-slate-400">
                  Cap eina o maquinària en custòdia assignada a aquesta ordre.
                </p>
                <Link
                  href={`/operari/material?ordre_id=${ordre.id}&fase=EINES`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-bold shadow-sm"
                >
                  <Wrench className="w-3.5 h-3.5" />
                  <span>Agafar eina del magatzem (Pick-In)</span>
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {ordre.eines_assignades.map((eina) => (
                  <Link
                    key={eina.id}
                    href={`/operari/material?ordre_id=${ordre.id}&fase=EINES`}
                    className="p-3 rounded-xl bg-surface-container-low/60 dark:bg-slate-800/50 border border-outline-variant/25 dark:border-slate-800 hover:border-amber-500/40 flex items-center justify-between gap-2 transition-colors"
                  >
                    <div className="min-w-0">
                      <h4 className="text-xs font-bold text-primary dark:text-slate-100 truncate">
                        {eina.nom}
                      </h4>
                      <p className="text-[11px] font-mono text-on-surface-variant dark:text-slate-400 mt-0.5 truncate">
                        {eina.model || "Estàndard"} · SN: {eina.numero_serie}
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span
                        className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${
                          eina.estat === "EN_VEHICLE"
                            ? "bg-primary/10 text-primary dark:text-sky-300 border-primary/25"
                            : eina.estat === "AVARIADA"
                            ? "bg-error-container/40 text-error border-error/30"
                            : "bg-secondary-container/15 text-secondary border-secondary-container/30"
                        }`}
                      >
                        {eina.estat === "EN_VEHICLE" ? "En Furgoneta" : eina.estat}
                      </span>
                      <ChevronRight className="w-3.5 h-3.5 text-on-surface-variant" />
                    </div>
                  </Link>
                ))}

                <Link
                  href={`/operari/material?ordre_id=${ordre.id}&fase=EINES`}
                  className="w-full py-2.5 px-3 rounded-lg bg-surface-container-high dark:bg-slate-800 hover:bg-surface-container text-primary dark:text-slate-100 text-xs font-bold flex items-center justify-center gap-1.5 transition-colors"
                >
                  <Wrench className="w-3.5 h-3.5 text-amber-600" />
                  <span>Gestionar Pick-In / Pick-Out d&apos;Eines</span>
                </Link>
              </div>
            )}
          </section>

          {/* ============================================================== */}
          {/* BOX 5: CAPTURA D'IMATGES (PROTOCOL QA 3 FOTOGRAFIES)           */}
          {/* ============================================================== */}
          <section
            id="box-fotos"
            data-testid="box-5-fotos"
            className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3 scroll-mt-16"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary text-white text-xs font-extrabold flex items-center justify-center shrink-0">
                  5
                </span>
                <div>
                  <h3 className="text-sm font-extrabold text-primary dark:text-slate-100 leading-tight flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-primary" />
                    <span>Captura d&apos;imatges (Protocol QA)</span>
                  </h3>
                  <p className="text-[11px] text-on-surface-variant dark:text-slate-400">
                    Captura obligatòria en viu amb càmera abans de tancar
                  </p>
                </div>
              </div>
              <span
                data-testid="qa-photos-counter"
                className={`text-xs font-mono font-bold px-2.5 py-0.5 rounded-full shrink-0 ${
                  estatFotos.protocol_complet
                    ? "bg-secondary-container/20 text-secondary border border-secondary"
                    : "bg-surface-container text-on-surface-variant"
                }`}
              >
                {estatFotos.fotos_pujades.length} / 3
              </span>
            </div>

            <div className="grid grid-cols-1 gap-2">
              {[
                { codi: "INICIAL" as TipusFotoQA, label: "1. Foto Inicial", desc: "Abans d'actuar a la instal·lació" },
                { codi: "INTERMEDIA" as TipusFotoQA, label: "2. Foto Intermèdia", desc: "Durant el muntatge o reparació" },
                { codi: "FINAL" as TipusFotoQA, label: "3. Foto Final", desc: "Resultat acabat i verificat" },
              ].map((item) => {
                const feta = estatFotos.fotos_pujades.includes(item.codi);
                return (
                  <div
                    key={item.codi}
                    data-testid={`qa-slot-${item.codi}`}
                    className={`p-3 rounded-lg border flex items-center justify-between ${
                      feta
                        ? "bg-secondary-container/10 border-secondary-container/40"
                        : "bg-surface-container-low dark:bg-slate-800/50 border-outline-variant/30"
                    }`}
                  >
                    <div>
                      <p className="font-bold text-xs text-on-surface dark:text-slate-200 flex items-center gap-1.5">
                        {feta && <CheckCircle2 className="w-3.5 h-3.5 text-secondary" />}
                        {item.label}
                      </p>
                      <p className="text-[11px] text-on-surface-variant dark:text-slate-400">
                        {item.desc}
                      </p>
                    </div>

                    <button
                      type="button"
                      data-testid={`btn-foto-${item.codi}`}
                      disabled={uploadingFoto}
                      onClick={() => setTipusFotoActiva(item.codi)}
                      className={`min-h-[38px] px-3 py-1.5 rounded-lg font-bold text-xs flex items-center gap-1.5 active:scale-95 transition-all shadow-sm cursor-pointer ${
                        feta
                          ? "bg-surface-container-high text-on-surface dark:bg-slate-700 dark:text-white"
                          : "bg-primary text-white"
                      }`}
                    >
                      <Camera className="w-3.5 h-3.5" />
                      <span>{feta ? "Repetir" : "Capturar"}</span>
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between pt-1 border-t border-outline-variant/15">
              <span className="text-[11px] text-on-surface-variant dark:text-slate-400">
                Tens fotos òrfenes fetes fora de l&apos;ordre?
              </span>
              <Link
                href="/operari/camera"
                className="text-[11px] font-bold text-secondary hover:underline"
              >
                Obrir Càmera d&apos;Obra
              </Link>
            </div>
          </section>

          {/* ============================================================== */}
          {/* BOX 6: SIGNATURA DE CONFORMITAT DEL CLIENT I TANCAMENT         */}
          {/* ============================================================== */}
          <section
            id="box-signatura"
            data-testid="box-6-signatura"
            className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-4 scroll-mt-16"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary text-white text-xs font-extrabold flex items-center justify-center shrink-0">
                  6
                </span>
                <div>
                  <h3 className="text-sm font-extrabold text-primary dark:text-slate-100 leading-tight flex items-center gap-1.5">
                    <PenTool className="w-4 h-4 text-secondary" />
                    <span>Signatura de conformitat del client</span>
                  </h3>
                  <p className="text-[11px] text-on-surface-variant dark:text-slate-400">
                    Validació presencial del client i tancament de l&apos;ordre
                  </p>
                </div>
              </div>
              {ordre.signatura_client_path && (
                <span className="text-[10px] font-extrabold px-2.5 py-1 rounded-full bg-secondary-container/20 text-secondary border border-secondary-container/40 shrink-0">
                  Signada
                </span>
              )}
            </div>

            {signaturaFeedback && (
              <div className="p-3 rounded-xl bg-secondary-container/15 border border-secondary-container/35 text-xs font-semibold text-secondary">
                {signaturaFeedback}
              </div>
            )}
            {signaturaError && (
              <div className="p-3 rounded-xl bg-error-container/30 border border-error/40 text-xs font-semibold text-error">
                {signaturaError}
              </div>
            )}

            {ordre.signatura_client_path && !mostrarReSignar ? (
              <div
                data-testid="signatura-confirmada-card"
                className="p-4 rounded-xl bg-secondary-container/10 border border-secondary-container/35 space-y-2.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 text-secondary">
                    <CheckCircle2 className="w-5 h-5 shrink-0" />
                    <div>
                      <p className="text-xs font-extrabold text-primary dark:text-white">
                        Conformitat del client registrada
                      </p>
                      <p className="text-[11px] text-on-surface-variant dark:text-slate-300">
                        {ordre.nom_receptor || ordre.client}
                        {ordre.dni_receptor ? ` · DNI/NIF: ${ordre.dni_receptor}` : ""}
                      </p>
                    </div>
                  </div>
                  {ordre.estat !== "COMPLERT" && ordre.estat !== "TANCADA" && (
                    <button
                      type="button"
                      onClick={() => setMostrarReSignar(true)}
                      className="text-[11px] font-bold text-primary dark:text-slate-200 underline underline-offset-2 cursor-pointer"
                    >
                      Tornar a signar
                    </button>
                  )}
                </div>

                {ordre.data_signatura && (
                  <p className="text-[11px] font-mono text-on-surface-variant dark:text-slate-400">
                    Signada el{" "}
                    {new Date(ordre.data_signatura).toLocaleString("ca-ES", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                )}

                {ordre.observacions_tancament && (
                  <p className="text-xs text-on-surface dark:text-slate-300 bg-surface-container-lowest/80 dark:bg-slate-800/60 p-2.5 rounded-lg">
                    {ordre.observacions_tancament}
                  </p>
                )}
              </div>
            ) : ordre.estat !== "COMPLERT" && ordre.estat !== "TANCADA" ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                      Nom del receptor
                    </label>
                    <input
                      type="text"
                      data-testid="input-nom-receptor-fitxa"
                      value={nomReceptor}
                      onChange={(e) => setNomReceptor(e.target.value)}
                      placeholder="Nom i cognoms"
                      maxLength={150}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                      DNI / NIF receptor
                    </label>
                    <input
                      type="text"
                      data-testid="input-dni-receptor-fitxa"
                      value={dniReceptor}
                      onChange={(e) => setDniReceptor(e.target.value.toUpperCase())}
                      placeholder="12345678A"
                      maxLength={30}
                      className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                    Observacions de conformitat (opcional)
                  </label>
                  <textarea
                    data-testid="input-observacions-fitxa"
                    value={observacionsTancament}
                    onChange={(e) => setObservacionsTancament(e.target.value)}
                    placeholder="Notes d'entrega, incidències resoltes o recomanacions al client..."
                    rows={2}
                    maxLength={2000}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-white resize-none"
                  />
                </div>

                <SignaturePad
                  onSave={handleGuardarSignaturaInline}
                  disabled={desantSignatura}
                />

                {mostrarReSignar && (
                  <button
                    type="button"
                    onClick={() => setMostrarReSignar(false)}
                    className="w-full py-2 text-xs font-semibold text-on-surface-variant hover:text-primary cursor-pointer"
                  >
                    Cancel·lar canvi de signatura
                  </button>
                )}
              </div>
            ) : null}

            {/* Barra de Tancament definitiu de l'Ordre */}
            {ordre.estat === "COMPLERT" || ordre.estat === "TANCADA" ? (
              <div className="p-3 rounded-xl bg-primary/10 border border-primary/25 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-primary dark:text-slate-100">
                  <CheckCircle2 className="w-4 h-4 text-secondary shrink-0" />
                  <span className="text-xs font-bold">
                    Ordre finalitzada i enviada a oficina tècnica
                  </span>
                </div>
                <Link
                  href="/operari/feines"
                  className="text-xs font-bold text-secondary hover:underline shrink-0"
                >
                  Tornar
                </Link>
              </div>
            ) : estatFotos.protocol_complet ? (
              <div className="space-y-2 pt-2 border-t border-outline-variant/20">
                <button
                  type="button"
                  data-testid="btn-finalitzar-ordre-inline"
                  disabled={finalitzantOrdre}
                  onClick={handleFinalitzarOrdreInline}
                  className="w-full py-3.5 px-4 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-extrabold uppercase tracking-wider flex items-center justify-center gap-2 shadow-md transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
                >
                  <CheckCircle2 className="w-4 h-4 text-secondary-container" />
                  <span>
                    {finalitzantOrdre
                      ? "Tancant ordre..."
                      : "Finalitzar i Tancar Ordre de Treball"}
                  </span>
                </button>
                <Link
                  href={`/operari/feines/${ordre.id}/tancar`}
                  data-testid="btn-anar-tancar-feina"
                  className="w-full py-2.5 px-3 rounded-xl bg-surface-container-low dark:bg-slate-800 text-on-surface-variant dark:text-slate-300 text-xs font-bold flex items-center justify-center gap-1.5 hover:bg-surface-container transition-colors"
                >
                  <Receipt className="w-3.5 h-3.5" />
                  <span>Escanejar tiquets de despesa i tancar</span>
                </Link>
              </div>
            ) : (
              <div className="p-3 rounded-xl bg-surface-container-low dark:bg-slate-800/70 border border-outline-variant/30 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Lock className="w-4 h-4 text-on-surface-variant shrink-0" />
                  <p className="text-[11px] text-on-surface-variant dark:text-slate-300 leading-snug">
                    Falten <strong>{estatFotos.falten.length}</strong> fotos QA ({estatFotos.falten.join(", ")}) al Box 5 per poder tancar l&apos;ordre.
                  </p>
                </div>
                <button
                  type="button"
                  data-testid="btn-anar-tancar-feina"
                  onClick={() => scrollToSection("box-fotos")}
                  className="px-2.5 py-1.5 rounded-lg bg-primary text-white text-[11px] font-bold shrink-0 cursor-pointer"
                >
                  Anar a Fotos
                </button>
              </div>
            )}
          </section>

          {/* Plànol Tècnic Assignat (Documentació complementària d'obra) */}
          {ordre.planol_id ? (
            <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 bg-primary/10 rounded-xl text-primary">
                    <Layers className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-extrabold text-primary dark:text-slate-100">
                      Plànol tècnic assignat
                    </h4>
                    <p className="text-[11px] font-mono text-secondary font-bold">
                      {ordre.planol_codi || "PLN"} • {ordre.planol_tipus_fitxer || "DOCUMENT"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <Link
                    href={`/operari/planols?planol=${ordre.planol_id}&ordre_id=${ordre.id}`}
                    className="px-3 py-1.5 rounded-lg bg-secondary-container hover:brightness-110 text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm active:scale-95 cursor-pointer"
                  >
                    <Layers className="w-3.5 h-3.5" />
                    <span>Editar As-Built</span>
                  </Link>
                  <button
                    type="button"
                    onClick={async () => {
                      if (!ordre.planol_id) return;
                      try {
                        const token = getAuthToken();
                        const tenantId = extractTenantId();
                        const headers: Record<string, string> = {};
                        if (token) headers["Authorization"] = `Bearer ${token}`;
                        if (tenantId) {
                          headers["X-Empresa-ID"] = tenantId;
                          headers["X-Tenant-ID"] = tenantId;
                        }
                        const res = await fetch(
                          `${getApiBaseUrl()}/operari/planols/${ordre.planol_id}/fitxer`,
                          { headers, credentials: "include" }
                        );
                        if (!res.ok) throw new Error(`HTTP ${res.status}`);
                        const blob = await res.blob();
                        const url = URL.createObjectURL(blob);
                        window.open(url, "_blank", "noopener,noreferrer");
                        setTimeout(() => URL.revokeObjectURL(url), 60_000);
                      } catch {
                        alert("No s'ha pogut obrir el fitxer original del plànol.");
                      }
                    }}
                    className="px-2.5 py-1.5 rounded-lg border border-outline-variant/60 bg-surface-container-lowest text-on-surface hover:bg-surface-container text-xs font-semibold flex items-center gap-1 transition-all cursor-pointer"
                  >
                    <ExternalLink className="w-3 h-3 text-primary" />
                    <span>PDF</span>
                  </button>
                </div>
              </div>
              <div className="p-2.5 bg-surface-container-low dark:bg-slate-800/60 rounded-lg text-xs font-medium text-slate-800 dark:text-slate-200">
                {ordre.planol_titol || "Plànol d'emplaçament o instal·lació d'obra"}
              </div>
            </div>
          ) : null}

          {/* Màquines i Actius de la Finca */}
          {ordre.assets && ordre.assets.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-extrabold text-primary dark:text-slate-300 px-1">
                Màquines i actius de la finca ({ordre.assets.length})
              </h3>
              <div className="space-y-2">
                {ordre.assets.map((asset) => (
                  <div
                    key={asset.id}
                    className="bg-surface-container-lowest dark:bg-slate-900 p-3.5 rounded-xl border border-outline-variant/25 dark:border-slate-800 shadow-sm flex items-center gap-3"
                  >
                    <div className="p-2 bg-surface-container-low dark:bg-slate-800 rounded-lg text-primary dark:text-slate-400">
                      {getAssetIcon(asset.tipus)}
                    </div>
                    <div className="flex-1">
                      <h4 className="text-xs font-bold text-primary dark:text-slate-100">
                        {asset.nom}
                      </h4>
                      <p className="text-[10px] font-mono text-on-surface-variant">
                        {asset.model} • SN: {asset.num_serie}
                      </p>
                    </div>
                    <span className="text-[9px] font-bold px-2 py-1 rounded bg-surface-container-low dark:bg-slate-800 text-on-surface-variant dark:text-slate-300">
                      {asset.estat}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
