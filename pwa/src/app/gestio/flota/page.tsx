"use client";
import { apiFetch, getApiBaseUrl } from "@/lib/api";

import React, { useState, useEffect } from "react";
import {
  Truck,
  Shield,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Fuel,
  BatteryCharging,
  Zap,
  Activity,
  Plus,
  Search,
  Filter,
  RefreshCw,
  FileText,
  Wrench,
  Car,
  ChevronRight,
  AlertCircle,
  Check,
  X,
  PlusCircle,
  HelpCircle,
  ExternalLink,
  Edit,
  User,
  Paperclip,
  Download,
  Upload,
} from "lucide-react";

interface VehicleItem {
  id: string;
  matricula: string;
  marca: string;
  model: string;
  tipus: string;
  distintiu_ambiental: string | null;
  estat: string;
  odometre_acumulat: number;
  horometre_acumulat: number;
  conductor_habitual_id: string | null;
  conductor_nom: string | null;
  ordre_treball_activa_id?: string | null;
  ordre_treball_activa_codi?: string | null;
  ordre_treball_activa_titol?: string | null;
  operari_assignat_nom?: string | null;
  data_proxima_itv: string | null;
  estat_itv: string;
  data_caducitat_asseguranca: string | null;
  companyia_asseguradora: string | null;
  polissa_asseguranca: string | null;
  carnet_necessari: string;
  historial_reparacions: string | null;
  dies_propera_itv: number | null;
  alerta_itv_cadena?: string;
  regim_adquisicio: string;
  renting_limit_km?: number | null;
  odometre_inici_contracte?: number;
  data_inici_contracte?: string | null;
  data_fi_contracte?: string | null;
  quota_mensual_eur?: number;
  tarifa_diaria_eur?: number;
  preu_km_exces_eur?: number;
  valor_residual_eur?: number | null;
  fianca_eur?: number | null;
  km_recorreguts_contracte?: number;
  dies_restants_contracte?: number | null;
  ocupacio_temps_percent?: number | null;
  desviacio_ritme_percent?: number | null;
  cost_fix_meritat_eur?: number;
  cost_penalitzacio_km_eur?: number;
  despesa_combustible_acumulada_eur?: number;
  despesa_manteniment_acumulada_eur?: number;
  manteniment_computable_tco_eur?: number;
  cost_total_acumulat_eur?: number;
  cost_per_km_eur?: number;
  alerta_contracte_venciment?: boolean;
  renting_ocupacio_percent?: number | null;
  renting_alerta?: boolean;
  renting_nivell_alerta?: string | null;
  alerta_renting_km?: string | null;
  consum_format?: string;
  consum_l_100km: number | null;
  consum_mitjana_historica: number | null;
  consum_adblue_litres: number;
  anomalia_consum: boolean;
  anomalia_descartada: boolean;
  descarte_detalls?: {
    motiu: string;
    observacions?: string;
    data_resolucio: string;
  };
}

interface OperariItem {
  id: string;
  nom: string;
  cognoms?: string;
  rol?: string;
  especialitat?: string;
}

interface DocumentFlotaItem {
  id: string;
  nom_original: string;
  tipus_document: string;
  mida_bytes?: number;
  created_at?: string;
}

export default function GestioFlotaPage() {
  const [vehicles, setVehicles] = useState<VehicleItem[]>([]);
  const [operaris, setOperaris] = useState<OperariItem[]>([]);
  const [carregant, setCarregant] = useState<boolean>(true);
  const [cerca, setCerca] = useState<string>("");
  const [filtreTipus, setFiltreTipus] = useState<string>("TOTS");
  const [filtreEstat, setFiltreEstat] = useState<string>("TOTS");

  // Estat del formulari / modal d'ITV
  const [modalItvObert, setModalItvObert] = useState<boolean>(false);
  const [vehicleSeleccionatItv, setVehicleSeleccionatItv] = useState<VehicleItem | null>(null);
  const [veredicteItv, setVeredicteItv] = useState<"FAVORABLE" | "LEVE" | "DESFAVORABLE" | "NEGATIVA">("FAVORABLE");
  const [dataNovaItv, setDataNovaItv] = useState<string>("");
  const [defectesItv, setDefectesItv] = useState<string>("");

  // Estat del formulari / modal de Descarte d'Anomalia de Consum
  const [modalDescarteObert, setModalDescarteObert] = useState<boolean>(false);
  const [vehicleSeleccionatConsum, setVehicleSeleccionatConsum] = useState<VehicleItem | null>(null);
  const [motiuTipificat, setMotiuTipificat] = useState<string>("CARREGA_PESADA");
  const [observacionsDescarte, setObservacionsDescarte] = useState<string>("");

  // Estat del formulari / modal de Nou Vehicle
  const [modalNouVehicleObert, setModalNouVehicleObert] = useState<boolean>(false);
  const [hasCopilotIa, setHasCopilotIa] = useState<boolean>(true);
  const [ocrLoading, setOcrLoading] = useState<boolean>(false);
  const [creantVehicle, setCreantVehicle] = useState<boolean>(false);
  const [novaMatricula, setNovaMatricula] = useState<string>("");
  const [novaMarca, setNovaMarca] = useState<string>("");
  const [nouModel, setNouModel] = useState<string>("");
  const [nouTipus, setNouTipus] = useState<string>("DIESEL");
  const [nouDistintiu, setNouDistintiu] = useState<string>("C");
  const [nouOdometre, setNouOdometre] = useState<number>(0);
  const [nouRegim, setNouRegim] = useState<string>("PROPIETAT");
  const [nouLimitKm, setNouLimitKm] = useState<number | string>("");
  const [nouOdometreInici, setNouOdometreInici] = useState<number | string>(0);
  const [novaDataIniciContracte, setNovaDataIniciContracte] = useState<string>("");
  const [novaDataFiContracte, setNovaDataFiContracte] = useState<string>("");
  const [novaQuotaMensual, setNovaQuotaMensual] = useState<number | string>("");
  const [novaTarifaDiaria, setNovaTarifaDiaria] = useState<number | string>("");
  const [nouPreuKmExces, setNouPreuKmExces] = useState<number | string>("");
  const [nouValorResidual, setNouValorResidual] = useState<number | string>("");
  const [novaFianca, setNovaFianca] = useState<number | string>("");
  const [nouConductorId, setNouConductorId] = useState<string>("");
  const [nouConsumReal, setNouConsumReal] = useState<number | string>("");
  const [nouConsumMitjana, setNouConsumMitjana] = useState<number | string>("");
  const [nouConsumAdblue, setNouConsumAdblue] = useState<number | string>(0);
  
  const [nouEstatItv, setNouEstatItv] = useState<string>("FAVORABLE");
  const [novaDataItv, setNovaDataItv] = useState<string>("");
  const [novaDataAsseguranca, setNovaDataAsseguranca] = useState<string>("");
  const [novaPolissaAsseguranca, setNovaPolissaAsseguranca] = useState<string>("");
  const [arxiuAsseguranca, setArxiuAsseguranca] = useState<File | null>(null);
  const [arxiuITV, setArxiuITV] = useState<File | null>(null);
  const [arxiuReparacio, setArxiuReparacio] = useState<File | null>(null);
  const [novaCompanyiaAsseguranca, setNovaCompanyiaAsseguranca] = useState<string>("");
  const [nouCarnet, setNouCarnet] = useState<string>("B");
  const [fitxersAdjunts, setFitxersAdjunts] = useState<{ file: File; tipus: string; nom: string }[]>([]);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const modalFileInputRef = React.useRef<HTMLInputElement | null>(null);

  // Estat del formulari / modal d'Edició de Vehicle (Fitxa del Vehicle)
  const [modalEdicioObert, setModalEdicioObert] = useState<boolean>(false);
  const [vehicleAEditar, setVehicleAEditar] = useState<VehicleItem | null>(null);
  const [guardantEdicio, setGuardantEdicio] = useState<boolean>(false);
  const [editMatricula, setEditMatricula] = useState<string>("");
  const [editMarca, setEditMarca] = useState<string>("");
  const [editModel, setEditModel] = useState<string>("");
  const [editTipus, setEditTipus] = useState<string>("DIESEL");
  const [editDistintiu, setEditDistintiu] = useState<string>("C");
  const [editEstat, setEditEstat] = useState<string>("OPERATIU");
  const [editConductorId, setEditConductorId] = useState<string>("");
  const [editOdometre, setEditOdometre] = useState<number>(0);
  const [editRegim, setEditRegim] = useState<string>("PROPIETAT");
  const [editLimitKm, setEditLimitKm] = useState<number | string>("");
  const [editOdometreInici, setEditOdometreInici] = useState<number | string>(0);
  const [editDataIniciContracte, setEditDataIniciContracte] = useState<string>("");
  const [editDataFiContracte, setEditDataFiContracte] = useState<string>("");
  const [editQuotaMensual, setEditQuotaMensual] = useState<number | string>("");
  const [editTarifaDiaria, setEditTarifaDiaria] = useState<number | string>("");
  const [editPreuKmExces, setEditPreuKmExces] = useState<number | string>("");
  const [editValorResidual, setEditValorResidual] = useState<number | string>("");
  const [editFianca, setEditFianca] = useState<number | string>("");
  const [editConsumL100km, setEditConsumL100km] = useState<number | string>("");
  const [editConsumMitjana, setEditConsumMitjana] = useState<number | string>("");
  const [editConsumAdblue, setEditConsumAdblue] = useState<number | string>(0);
  const [editEstatItv, setEditEstatItv] = useState<string>("FAVORABLE");
  const [editDataItv, setEditDataItv] = useState<string>("");
  const [editDataAsseguranca, setEditDataAsseguranca] = useState<string>("");
  const [editCompanyiaAsseguranca, setEditCompanyiaAsseguranca] = useState<string>("");
  const [editPolissaAsseguranca, setEditPolissaAsseguranca] = useState<string>("");
  const [editCarnet, setEditCarnet] = useState<string>("B");
  const [editHistorialReparacions, setEditHistorialReparacions] = useState<string>("");

  // Documents del vehicle a editar
  const [documentsVehicle, setDocumentsVehicle] = useState<DocumentFlotaItem[]>([]);
  const [carregantDocs, setCarregantDocs] = useState<boolean>(false);
  const [pujantDocVehicle, setPujantDocVehicle] = useState<boolean>(false);
  const [nouDocTipus, setNouDocTipus] = useState<string>("FITXA_TECNICA");
  const editFileInputRef = React.useRef<HTMLInputElement | null>(null);

  const processFilesOcr = async (files: File[]) => {
    if (!files || files.length === 0) return;
    setOcrLoading(true);
    try {
      const formData = new FormData();
      files.forEach((f) => formData.append("files", f));
      formData.append("file", files[0]); // Compatibilitat retroactiva

      const data = await apiFetch<any>("/gestio/flota/ocr-draft", {
        method: "POST",
        body: formData,
      });

      if (data) {
        if (data.matricula) setNovaMatricula(data.matricula);
        if (data.marca) setNovaMarca(data.marca);
        if (data.model) setNouModel(data.model);
        if (data.tipus) setNouTipus(data.tipus);
        if (data.distintiu_ambiental) setNouDistintiu(data.distintiu_ambiental);
        if (data.odometre_acumulat !== null && data.odometre_acumulat !== undefined) {
          setNouOdometre(Number(data.odometre_acumulat));
        }
        if (data.regim_adquisicio) {
          setNouRegim(data.regim_adquisicio);
          if (["RENTING", "LEASING", "LLOGUER"].includes(data.regim_adquisicio) && data.renting_limit_km) {
            setNouLimitKm(Number(data.renting_limit_km));
          } else {
            setNouLimitKm("");
          }
        } else {
          setNouRegim("PROPIETAT");
          setNouLimitKm("");
        }
        if (data.companyia_asseguradora) setNovaCompanyiaAsseguranca(data.companyia_asseguradora);
        if (data.polissa_asseguranca) setNovaPolissaAsseguranca(data.polissa_asseguranca);
        if (data.data_caducitat_asseguranca) setNovaDataAsseguranca(data.data_caducitat_asseguranca);
        if (data.estat_itv) setNouEstatItv(data.estat_itv);
        if (data.data_proxima_itv) setNovaDataItv(data.data_proxima_itv);
        if (data.carnet_necessari) setNouCarnet(data.carnet_necessari);

        // Auto-assignar fitxers als inputs del formulari segons detecció
        const docTypes: { [nom: string]: string } = {};
        if (Array.isArray(data.documents_processats)) {
          data.documents_processats.forEach((doc: any) => {
            if (doc?.nom) docTypes[doc.nom] = doc.tipus_detectat;
          });
        }

        const nousAdjunts: { file: File; tipus: string; nom: string }[] = [];
        files.forEach((f) => {
          const tipusDetectat = docTypes[f.name] || "GENERAL";
          nousAdjunts.push({ file: f, tipus: tipusDetectat, nom: f.name });

          const nomLower = f.name.toLowerCase();
          if (
            tipusDetectat === "ITV" ||
            nomLower.includes("itv") ||
            nomLower.includes("fitxa") ||
            nomLower.includes("tecnica")
          ) {
            setArxiuITV(f);
          } else if (
            tipusDetectat === "ASSEGURANCA" ||
            nomLower.includes("asseguran") ||
            nomLower.includes("seguro") ||
            nomLower.includes("polissa")
          ) {
            setArxiuAsseguranca(f);
          } else if (
            tipusDetectat === "MANTENIMENT" ||
            nomLower.includes("reparac") ||
            nomLower.includes("oli") ||
            nomLower.includes("taller") ||
            nomLower.includes("factura")
          ) {
            setArxiuReparacio(f);
          } else if (files.length === 1 && !arxiuITV) {
            setArxiuITV(f);
          }
        });

        setFitxersAdjunts((prev) => {
          const map = new Map<string, { file: File; tipus: string; nom: string }>();
          prev.forEach((item) => map.set(item.nom, item));
          nousAdjunts.forEach((item) => map.set(item.nom, item));
          return Array.from(map.values());
        });

        setModalNouVehicleObert(true);
      }
    } catch (err: any) {
      alert("Error processant OCR del vehicle: " + (err?.message || err));
    } finally {
      setOcrLoading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      if (modalFileInputRef.current) {
        modalFileInputRef.current.value = "";
      }
    }
  };

  const handleOcrUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    await processFilesOcr(Array.from(files));
  };

  // Carregar vehicles des del backend
  const fetchVehicles = async () => {
    setCarregant(true);
    try {
      const data = await apiFetch<VehicleItem[]>("/gestio/flota");
      setVehicles(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Error carregant vehicles:", err);
      setVehicles([]);
    } finally {
      setCarregant(false);
    }
  };

  // Carregar operaris per als selectors de conductor
  const fetchOperaris = async () => {
    try {
      const data = await apiFetch<OperariItem[]>("/gestio/operaris");
      setOperaris(Array.isArray(data) ? data : []);
    } catch {
      setOperaris([]);
    }
  };

  useEffect(() => {
    fetchVehicles();
    fetchOperaris();
    apiFetch<any>("/gestio/configuracio/empresa")
      .then((c) => {
        if (c && c.feature_copilot_ia === false) setHasCopilotIa(false);
      })
      .catch(() => {});

    // Evitar que arrossegar fitxers al navegador provoqui navegació a file:/// (Error de seguretat navegador)
    const handleGlobalDragOver = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
    };
    const handleGlobalDrop = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const droppedFiles = e.dataTransfer?.files;
      if (droppedFiles && droppedFiles.length > 0) {
        processFilesOcr(Array.from(droppedFiles));
      }
    };

    window.addEventListener("dragover", handleGlobalDragOver);
    window.addEventListener("drop", handleGlobalDrop);
    return () => {
      window.removeEventListener("dragover", handleGlobalDragOver);
      window.removeEventListener("drop", handleGlobalDrop);
    };
  }, []);

  // Registrar resolució d'ITV (Spec 006 RF-18)
  const handleRegistrarItv = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vehicleSeleccionatItv) return;

    try {
      await apiFetch("/gestio/flota/registrar-itv", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehicle_id: vehicleSeleccionatItv.id,
          veredicte: veredicteItv,
          data_proxima_itv: dataNovaItv || new Date(Date.now() + 365 * 86400000).toISOString().split("T")[0],
          defectes_detectats: defectesItv,
        }),
      });
      setModalItvObert(false);
      fetchVehicles();
    } catch {
      // Fallback optimista si no hi ha backend
      setVehicles((prev) =>
        prev.map((v) => {
          if (v.id === vehicleSeleccionatItv.id) {
            const nouEstat =
              veredicteItv === "FAVORABLE"
                ? "OPERATIU"
                : veredicteItv === "LEVE"
                ? "LEVE"
                : veredicteItv === "DESFAVORABLE"
                ? "DESFAVORABLE"
                : "INACTIVAT";
            return { ...v, estat: nouEstat, data_proxima_itv: dataNovaItv };
          }
          return v;
        })
      );
      setModalItvObert(false);
    }
  };

  // Descartar anomalia de consum (Spec 006 RF-16)
  const handleDescartarAnomalia = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vehicleSeleccionatConsum) return;

    try {
      await apiFetch("/gestio/flota/descartar-anomalia-consum", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehicle_id: vehicleSeleccionatConsum.id,
          motiu_tipificat: motiuTipificat,
          observacions: observacionsDescarte,
        }),
      });

      // Actualització optimista
      setVehicles((prev) =>
        prev.map((v) => {
          if (v.id === vehicleSeleccionatConsum.id) {
            return {
              ...v,
              anomalia_consum: false,
              anomalia_descartada: true,
              descarte_detalls: {
                motiu: motiuTipificat,
                observacions: observacionsDescarte,
                data_resolucio: new Date().toISOString().split("T")[0],
              },
            };
          }
          return v;
        })
      );
      setModalDescarteObert(false);
    } catch {
      setModalDescarteObert(false);
    }
  };

  // Obrir formulari net de Nou Vehicle
  const handleObrirModalNouVehicle = () => {
    setNovaMatricula("");
    setNovaMarca("");
    setNouModel("");
    setNouTipus("DIESEL");
    setNouDistintiu("C");
    setNouOdometre(0);
    setNouRegim("PROPIETAT");
    setNouLimitKm("");
    setNouOdometreInici(0);
    setNovaDataIniciContracte("");
    setNovaDataFiContracte("");
    setNovaQuotaMensual("");
    setNovaTarifaDiaria("");
    setNouPreuKmExces("");
    setNouValorResidual("");
    setNovaFianca("");
    setNouConductorId("");
    setNouConsumReal("");
    setNouConsumMitjana("");
    setNouConsumAdblue(0);
    setNouEstatItv("FAVORABLE");
    setNovaDataItv("");
    setNovaDataAsseguranca("");
    setNovaCompanyiaAsseguranca("");
    setNovaPolissaAsseguranca("");
    setNouCarnet("B");
    setFitxersAdjunts([]);
    setArxiuITV(null);
    setArxiuAsseguranca(null);
    setArxiuReparacio(null);
    setModalNouVehicleObert(true);
  };

  // Donar d'alta nou vehicle (Spec 006 RF-05)
  const handleCrearVehicle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!novaMatricula || !novaMarca || !nouModel) return;

    setCreantVehicle(true);
    try {
      const res = await apiFetch<any>("/gestio/flota", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          matricula: novaMatricula,
          marca: novaMarca,
          model: nouModel,
          tipus: nouTipus,
          distintiu_ambiental: nouDistintiu,
          odometre_acumulat: nouOdometre,
          conductor_habitual_id: nouConductorId || null,
          regim_adquisicio: nouRegim,
          renting_limit_km: ["RENTING", "LEASING", "LLOGUER"].includes(nouRegim) && nouLimitKm !== "" ? Number(nouLimitKm) : null,
          odometre_inici_contracte: Number(nouOdometreInici) || 0,
          data_inici_contracte: novaDataIniciContracte || null,
          data_fi_contracte: novaDataFiContracte || null,
          quota_mensual_eur: novaQuotaMensual !== "" ? Number(novaQuotaMensual) : 0,
          tarifa_diaria_eur: novaTarifaDiaria !== "" ? Number(novaTarifaDiaria) : 0,
          preu_km_exces_eur: nouPreuKmExces !== "" ? Number(nouPreuKmExces) : 0,
          valor_residual_eur: nouValorResidual !== "" ? Number(nouValorResidual) : null,
          fianca_eur: novaFianca !== "" ? Number(novaFianca) : null,
          consum_l_100km: nouTipus === "REMOLC" ? null : (nouConsumReal !== "" ? Number(nouConsumReal) : null),
          consum_mitjana_historica: nouTipus === "REMOLC" ? null : (nouConsumMitjana !== "" ? Number(nouConsumMitjana) : null),
          consum_adblue_litres: nouTipus === "DIESEL" && nouConsumAdblue !== "" ? Number(nouConsumAdblue) : 0,
          estat_itv: nouEstatItv,
          data_proxima_itv: novaDataItv || null,
          data_caducitat_asseguranca: novaDataAsseguranca || null,
          companyia_asseguradora: novaCompanyiaAsseguranca || null,
          polissa_asseguranca: novaPolissaAsseguranca || null,
          carnet_necessari: nouCarnet,
        }),
      });

      const nouVehicleId = res?.id;

      // Si s'han adjuntat fitxers (ITV, Assegurança, Reparació), els pugem al vehicle
      if (nouVehicleId) {
        const docsAEnviar: { file: File; tipus: string }[] = [];
        if (arxiuITV) docsAEnviar.push({ file: arxiuITV, tipus: "FITXA_TECNICA" });
        if (arxiuAsseguranca) docsAEnviar.push({ file: arxiuAsseguranca, tipus: "ASSEGURANCA" });
        if (arxiuReparacio) docsAEnviar.push({ file: arxiuReparacio, tipus: "MANTENIMENT" });

        fitxersAdjunts.forEach((adj) => {
          const jaHiEs = docsAEnviar.some((d) => d.file.name === adj.file.name);
          if (!jaHiEs) {
            docsAEnviar.push({
              file: adj.file,
              tipus:
                adj.tipus === "ITV"
                  ? "FITXA_TECNICA"
                  : adj.tipus === "ASSEGURANCA"
                  ? "ASSEGURANCA"
                  : adj.tipus === "MANTENIMENT"
                  ? "MANTENIMENT"
                  : "ALTRES",
            });
          }
        });

        for (const item of docsAEnviar) {
          try {
            const docFormData = new FormData();
            docFormData.append("file", item.file);
            docFormData.append("tipus_document", item.tipus);
            await apiFetch(`/gestio/flota/${nouVehicleId}/documents`, {
              method: "POST",
              body: docFormData,
            });
          } catch (uploadErr) {
            console.warn("No s'ha pogut vincular automàticament el document:", uploadErr);
          }
        }
      }

      setModalNouVehicleObert(false);
      setFitxersAdjunts([]);
      setArxiuITV(null);
      setArxiuAsseguranca(null);
      setArxiuReparacio(null);
      fetchVehicles();
    } catch (err: any) {
      alert("Error al crear el vehicle: " + (err.message || "Error desconegut"));
    } finally {
      setCreantVehicle(false);
    }
  };

  // Obrir modal de Fitxa del Vehicle / Edició
  const handleObrirEdicioVehicle = async (veh: VehicleItem) => {
    setVehicleAEditar(veh);
    setEditMatricula(veh.matricula || "");
    setEditMarca(veh.marca || "");
    setEditModel(veh.model || "");
    setEditTipus(veh.tipus || "DIESEL");
    setEditDistintiu(veh.distintiu_ambiental || "C");
    setEditEstat(veh.estat || "OPERATIU");
    setEditConductorId(veh.conductor_habitual_id || "");
    setEditOdometre(veh.odometre_acumulat || 0);
    setEditRegim(veh.regim_adquisicio || "PROPIETAT");
    setEditLimitKm(veh.renting_limit_km !== null && veh.renting_limit_km !== undefined ? veh.renting_limit_km : "");
    setEditOdometreInici(veh.odometre_inici_contracte !== null && veh.odometre_inici_contracte !== undefined ? veh.odometre_inici_contracte : 0);
    setEditDataIniciContracte(veh.data_inici_contracte || "");
    setEditDataFiContracte(veh.data_fi_contracte || "");
    setEditQuotaMensual(veh.quota_mensual_eur !== null && veh.quota_mensual_eur !== undefined && veh.quota_mensual_eur > 0 ? veh.quota_mensual_eur : "");
    setEditTarifaDiaria(veh.tarifa_diaria_eur !== null && veh.tarifa_diaria_eur !== undefined && veh.tarifa_diaria_eur > 0 ? veh.tarifa_diaria_eur : "");
    setEditPreuKmExces(veh.preu_km_exces_eur !== null && veh.preu_km_exces_eur !== undefined && veh.preu_km_exces_eur > 0 ? veh.preu_km_exces_eur : "");
    setEditValorResidual(veh.valor_residual_eur !== null && veh.valor_residual_eur !== undefined ? veh.valor_residual_eur : "");
    setEditFianca(veh.fianca_eur !== null && veh.fianca_eur !== undefined ? veh.fianca_eur : "");
    setEditConsumL100km(veh.consum_l_100km !== null && veh.consum_l_100km !== undefined ? veh.consum_l_100km : "");
    setEditConsumMitjana(veh.consum_mitjana_historica !== null && veh.consum_mitjana_historica !== undefined ? veh.consum_mitjana_historica : "");
    setEditConsumAdblue(veh.consum_adblue_litres !== null && veh.consum_adblue_litres !== undefined ? veh.consum_adblue_litres : 0);
    setEditEstatItv(veh.estat_itv || "FAVORABLE");
    setEditDataItv(veh.data_proxima_itv || "");
    setEditDataAsseguranca(veh.data_caducitat_asseguranca || "");
    setEditCompanyiaAsseguranca(veh.companyia_asseguradora || "");
    setEditPolissaAsseguranca(veh.polissa_asseguranca || "");
    setEditCarnet(veh.carnet_necessari || "B");
    setEditHistorialReparacions(veh.historial_reparacions || "");
    setModalEdicioObert(true);

    // Carregar documents del vehicle
    try {
      setCarregantDocs(true);
      const docs = await apiFetch<DocumentFlotaItem[]>(`/gestio/flota/${veh.id}/documents`);
      setDocumentsVehicle(Array.isArray(docs) ? docs : []);
    } catch {
      setDocumentsVehicle([]);
    } finally {
      setCarregantDocs(false);
    }
  };

  // Guardar canvis de la Fitxa del Vehicle
  const handleGuardarEdicio = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vehicleAEditar) return;

    setGuardantEdicio(true);
    try {
      await apiFetch(`/gestio/flota/${vehicleAEditar.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          matricula: editMatricula,
          marca: editMarca,
          model: editModel,
          tipus: editTipus,
          distintiu_ambiental: editDistintiu,
          estat: editEstat,
          conductor_habitual_id: editConductorId || null,
          odometre_acumulat: Number(editOdometre) || 0,
          regim_adquisicio: editRegim,
          renting_limit_km: ["RENTING", "LEASING", "LLOGUER"].includes(editRegim) && editLimitKm !== "" ? Number(editLimitKm) : null,
          odometre_inici_contracte: Number(editOdometreInici) || 0,
          data_inici_contracte: editDataIniciContracte || null,
          data_fi_contracte: editDataFiContracte || null,
          quota_mensual_eur: editQuotaMensual !== "" ? Number(editQuotaMensual) : 0,
          tarifa_diaria_eur: editTarifaDiaria !== "" ? Number(editTarifaDiaria) : 0,
          preu_km_exces_eur: editPreuKmExces !== "" ? Number(editPreuKmExces) : 0,
          valor_residual_eur: editValorResidual !== "" ? Number(editValorResidual) : null,
          fianca_eur: editFianca !== "" ? Number(editFianca) : null,
          consum_l_100km: editTipus === "REMOLC" ? null : (editConsumL100km !== "" ? Number(editConsumL100km) : null),
          consum_mitjana_historica: editTipus === "REMOLC" ? null : (editConsumMitjana !== "" ? Number(editConsumMitjana) : null),
          consum_adblue_litres: editTipus === "DIESEL" && editConsumAdblue !== "" ? Number(editConsumAdblue) : 0,
          estat_itv: editEstatItv,
          data_proxima_itv: editDataItv || null,
          data_caducitat_asseguranca: editDataAsseguranca || null,
          companyia_asseguradora: editCompanyiaAsseguranca || null,
          polissa_asseguranca: editPolissaAsseguranca || null,
          carnet_necessari: editCarnet,
          historial_reparacions: editHistorialReparacions || null,
        }),
      });

      setModalEdicioObert(false);
      fetchVehicles();
    } catch (err: any) {
      alert("Error al guardar les dades del vehicle: " + (err.message || err));
    } finally {
      setGuardantEdicio(false);
    }
  };

  // Pujar nou document directament des de la fitxa editable
  const handlePujarDocumentDirecte = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !vehicleAEditar) return;

    setPujantDocVehicle(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("tipus_document", nouDocTipus);
      await apiFetch(`/gestio/flota/${vehicleAEditar.id}/documents`, {
        method: "POST",
        body: fd,
      });
      // Refrescar llista de documents
      const docs = await apiFetch<DocumentFlotaItem[]>(`/gestio/flota/${vehicleAEditar.id}/documents`);
      setDocumentsVehicle(Array.isArray(docs) ? docs : []);
    } catch (err: any) {
      alert("Error pujant el document: " + (err.message || err));
    } finally {
      setPujantDocVehicle(false);
      if (editFileInputRef.current) editFileInputRef.current.value = "";
    }
  };

  // Filtrar vehicles (amb coalescència segura per evitar null.toLowerCase() crashes)
  const vehiclesFiltrats = vehicles.filter((v) => {
    if (filtreTipus !== "TOTS" && v.tipus !== filtreTipus) return false;
    if (filtreEstat !== "TOTS") {
      if (filtreEstat === "OPERATIU") {
        if (v.estat !== "OPERATIU" && v.estat !== "ASSIGNAT") return false;
      } else if (filtreEstat === "ASSIGNAT") {
        if (v.estat !== "ASSIGNAT" && !v.ordre_treball_activa_codi) return false;
      } else if (v.estat !== filtreEstat) {
        return false;
      }
    }
    if (!cerca || !cerca.trim()) return true;
    const q = cerca.toLowerCase().trim();
    return (
      (v.matricula || "").toLowerCase().includes(q) ||
      (v.marca || "").toLowerCase().includes(q) ||
      (v.model || "").toLowerCase().includes(q) ||
      (v.conductor_nom || "").toLowerCase().includes(q) ||
      (v.operari_assignat_nom || "").toLowerCase().includes(q) ||
      (v.ordre_treball_activa_codi || "").toLowerCase().includes(q) ||
      (v.distintiu_ambiental || "").toLowerCase().includes(q) ||
      (v.regim_adquisicio || "").toLowerCase().includes(q) ||
      (v.companyia_asseguradora || "").toLowerCase().includes(q) ||
      (v.polissa_asseguranca || "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="flex-1 p-6 space-y-6 overflow-y-auto bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors">
      {/* CAPÇALERA SUPERIOR */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              <Truck className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              Gestió de Flota, ITV & Consum (Spec 006)
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 font-bold">
              RLS VEHICLES SCHEME
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Fitxa integral editable, telemetria de consum, 4 veredictes d'ITV i llindars de rènting 90/95/100%
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchVehicles}
            disabled={carregant}
            className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-mono font-bold flex items-center gap-1.5 border border-slate-300 dark:border-slate-700 shadow-sm transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${carregant ? "animate-spin text-emerald-500" : ""}`} />
            <span>Refrescar</span>
          </button>
          <div className="flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              accept="image/*,.pdf,application/pdf,.md,.txt,text/markdown,text/plain"
              onChange={handleOcrUpload}
            />
            {hasCopilotIa && (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  const f = e.dataTransfer?.files;
                  if (f && f.length > 0) processFilesOcr(Array.from(f));
                }}
                disabled={ocrLoading}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm cursor-pointer transition-all ${ocrLoading ? 'opacity-50 pointer-events-none' : ''}`}
                title="Clica o arrossega un o diversos documents: Targeta ITV, Pòlissa Assegurança, Reparació (PDF, Markdown .md o Imatges)"
              >
                {ocrLoading ? <span className="animate-spin text-lg leading-none">⚙</span> : <span className="text-lg leading-none">✨</span>}
                <span>{ocrLoading ? 'Processant IA...' : 'Alta OCR Multi-Document'}</span>
              </button>
            )}
            <button
              onClick={handleObrirModalNouVehicle}
              className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Registrar Nou Vehicle</span>
            </button>
          </div>
        </div>
      </div>

      {/* BARRA DE FILTRES I CERCA FUNCIONAL */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-2 flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400" />
          <input
            type="text"
            disabled={vehicles.length === 0}
            placeholder={vehicles.length === 0 ? "Cercador deshabilitat (Dia 0)" : "Filtrar per matrícula, marca, model, distintiu DGT o conductor..."}
            value={cerca}
            onChange={(e) => setCerca(e.target.value)}
            className="w-full text-xs bg-transparent border-none focus:outline-none text-slate-900 dark:text-slate-100 placeholder:text-slate-400 font-mono disabled:opacity-50"
          />
          {cerca && (
            <button
              onClick={() => setCerca("")}
              className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              title="Esborrar cerca"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Filtre per tipus */}
          <select
            value={filtreTipus}
            onChange={(e) => setFiltreTipus(e.target.value)}
            className="text-xs bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1.5 font-mono text-slate-700 dark:text-slate-300 focus:outline-none"
          >
            <option value="TOTS">Tots els tipus</option>
            <option value="DIESEL">Dièsel</option>
            <option value="GASOLINA">Gasolina</option>
            <option value="EV">100% Elèctric (EV)</option>
            <option value="PHEV">Híbrid Enchufable (PHEV)</option>
            <option value="MAQUINARIA">Maquinària</option>
            <option value="REMOLC">Remolc</option>
          </select>

          {/* Filtre per estat */}
          <select
            value={filtreEstat}
            onChange={(e) => setFiltreEstat(e.target.value)}
            className="text-xs bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1.5 font-mono text-slate-700 dark:text-slate-300 focus:outline-none"
          >
            <option value="TOTS">Tots els estats</option>
            <option value="OPERATIU">Operatiu (Verd)</option>
            <option value="ASSIGNAT">Assignat a Obra / OT (Blau)</option>
            <option value="LEVE">Operatiu Defectes Lleus</option>
            <option value="DESFAVORABLE">ITV Desfavorable (Immobilitzat)</option>
            <option value="INACTIVAT">ITV Negativa (Grua)</option>
            <option value="EN_TALLER">En Taller</option>
            <option value="INCIDENCIA">Incidència</option>
            <option value="BAIXA">Baixa</option>
          </select>
        </div>
      </div>

      {/* TAULA DE FLOTA O ESTAT BUIT CANÒNIC ZERO MOCK DATA */}
      {vehicles.length === 0 ? (
        <div className="p-12 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-800 text-center space-y-4 bg-white dark:bg-slate-900/60 shadow-sm">
          <div className="w-14 h-14 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto border border-emerald-200 dark:border-emerald-800">
            <Truck className="w-7 h-7" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100 font-mono">
              No hi ha vehicles registrats a la flota
            </h3>
            <p className="text-xs text-slate-500 font-mono max-w-md mx-auto">
              Estat canònic de Dia 0. Registra el primer vehicle, furgoneta, pick-up, maquinària o remolc per iniciar la gestió de flota.
            </p>
          </div>
          <button
            onClick={handleObrirModalNouVehicle}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold shadow transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Registrar nou vehicle / actiu</span>
          </button>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 font-mono text-[10px] uppercase text-slate-500 dark:text-slate-400">
                  <th className="p-3.5">Matrícula & Id</th>
                  <th className="p-3.5">Tipus & Distintiu DGT</th>
                  <th className="p-3.5">Marca & Model</th>
                  <th className="p-3.5 text-center">Règim & Rènting</th>
                  <th className="p-3.5">Custodi / Conductor</th>
                  <th className="p-3.5 text-center">Odòmetre / Horòmetre</th>
                  <th className="p-3.5 text-center">Estat Operatiu</th>
                  <th className="p-3.5 text-left">Consum & Telemetria</th>
                  <th className="p-3.5 text-right">ITV & Veredicte</th>
                  <th className="p-3.5 text-center">Accions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800 font-mono text-[11px]">
                {vehiclesFiltrats.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="p-8 text-center text-slate-500 dark:text-slate-400 font-mono">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Search className="w-6 h-6 text-slate-400" />
                        <p className="font-bold text-xs text-slate-700 dark:text-slate-300">
                          No s'ha trobat cap vehicle que coincideixi amb la cerca «{cerca}»
                        </p>
                        <p className="text-[11px] text-slate-400">
                          Prova de modificar els termes de cerca o restablir els filtres.
                        </p>
                        <button
                          onClick={() => {
                            setCerca("");
                            setFiltreTipus("TOTS");
                            setFiltreEstat("TOTS");
                          }}
                          className="mt-2 px-3 py-1 rounded-lg bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-bold hover:bg-slate-300 dark:hover:bg-slate-600 transition-colors"
                        >
                          Netejar filtres i cerca
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  vehiclesFiltrats.map((v) => (
                    <tr
                      key={v.id}
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors group cursor-pointer"
                      onClick={() => handleObrirEdicioVehicle(v)}
                    >
                      {/* 1. Matrícula */}
                      <td className="p-3.5">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900 dark:text-white px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 tracking-wider">
                            {v.matricula}
                          </span>
                        </div>
                      </td>

                      {/* 2. Tipologia & Distintiu DGT (RF-01) */}
                      <td className="p-3.5">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold text-slate-600 dark:text-slate-300">
                            {v.tipus}
                          </span>
                          {/* Distintiu ambiental DGT inmutable */}
                          <span
                            className={`text-[9px] font-bold px-1.5 py-0.2 rounded border ${
                              v.distintiu_ambiental === "ZERO"
                                ? "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800"
                                : v.distintiu_ambiental === "ECO"
                                ? "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800"
                                : v.distintiu_ambiental === "C"
                                ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-400"
                                : v.distintiu_ambiental === "B"
                                ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800"
                                : "bg-slate-200 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-400"
                            }`}
                          >
                            DGT: {v.distintiu_ambiental || "SENSE"}
                          </span>
                        </div>
                      </td>

                      {/* 3. Marca i Model */}
                      <td className="p-3.5">
                        <p className="font-bold text-slate-900 dark:text-white">{v.marca}</p>
                        <p className="text-[10px] text-slate-500">{v.model}</p>
                      </td>

                      {/* 4. Règim d'Adquisició & Llindars Rènting / Lísing / Lloguer */}
                      <td className="p-3.5 text-center">
                        {(v.regim_adquisicio === "RENTING" || v.regim_adquisicio === "LEASING" || v.regim_adquisicio === "LLOGUER") && v.renting_limit_km ? (
                          <div className="space-y-1 inline-block text-left w-36">
                            <div className="flex items-center justify-between text-[10px]">
                              <span className="text-slate-500 font-bold">
                                {v.regim_adquisicio === "RENTING" ? "Rènting" : v.regim_adquisicio === "LEASING" ? "Lísing" : "Lloguer"}
                              </span>
                              <span
                                className={`font-bold ${
                                  (v.renting_ocupacio_percent || 0) >= 100
                                    ? "text-rose-500"
                                    : (v.renting_ocupacio_percent || 0) >= 95
                                    ? "text-orange-500"
                                    : (v.renting_ocupacio_percent || 0) >= 90
                                    ? "text-amber-500"
                                    : "text-slate-400"
                                }`}
                              >
                                {v.renting_ocupacio_percent || 0}%
                              </span>
                            </div>
                            {/* Barra de progrés */}
                            <div className="w-full h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                              <div
                                className={`h-full transition-all ${
                                  (v.renting_ocupacio_percent || 0) >= 100
                                    ? "bg-rose-500"
                                    : (v.renting_ocupacio_percent || 0) >= 95
                                    ? "bg-orange-500"
                                    : (v.renting_ocupacio_percent || 0) >= 90
                                    ? "bg-amber-500"
                                    : "bg-emerald-500"
                                }`}
                                style={{ width: `${Math.min(100, v.renting_ocupacio_percent || 0)}%` }}
                              ></div>
                            </div>
                            {v.km_recorreguts_contracte !== undefined && v.renting_limit_km ? (
                              <p className="text-[9px] text-slate-400 font-mono">
                                {v.km_recorreguts_contracte.toLocaleString()} / {v.renting_limit_km.toLocaleString()} km
                              </p>
                            ) : null}
                            {(v.cost_total_acumulat_eur || 0) > 0 && (
                              <p className="text-[9px] text-indigo-600 dark:text-indigo-400 font-mono font-semibold">
                                TCO: {v.cost_total_acumulat_eur?.toLocaleString()} € ({v.cost_per_km_eur?.toFixed(2)} €/km)
                              </p>
                            )}
                            {v.renting_alerta && (
                              <p className="text-[9px] font-bold text-amber-500">
                                {v.renting_nivell_alerta === "RITME_EXCES_KM" ? "Ritme excessiu km" : `Límit ${v.renting_nivell_alerta} assolit!`}
                              </p>
                            )}
                            {v.alerta_contracte_venciment && (
                              <p className="text-[9px] font-bold text-rose-500">
                                Venciment ({v.dies_restants_contracte}d)!
                              </p>
                            )}
                          </div>
                        ) : (
                          <div className="inline-flex flex-col items-center gap-1">
                            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[10px] font-mono font-medium">
                              <span
                                className={`w-1.5 h-1.5 rounded-full ${
                                  v.regim_adquisicio === "PROPIETAT"
                                    ? "bg-emerald-500"
                                    : v.regim_adquisicio === "LLOGUER"
                                    ? "bg-blue-500"
                                    : v.regim_adquisicio === "LEASING"
                                    ? "bg-indigo-500"
                                    : "bg-purple-500"
                                }`}
                              ></span>
                              <span>
                                {v.regim_adquisicio === "PROPIETAT"
                                  ? "Compra"
                                  : v.regim_adquisicio === "LLOGUER"
                                  ? "Lloguer"
                                  : v.regim_adquisicio === "LEASING"
                                  ? "Lísing"
                                  : v.regim_adquisicio === "SUBSTITUCIO"
                                  ? "Substitució"
                                  : v.regim_adquisicio}
                              </span>
                            </div>
                            {(v.cost_total_acumulat_eur || 0) > 0 && (
                              <span className="text-[9px] text-indigo-600 dark:text-indigo-400 font-mono font-semibold">
                                TCO: {v.cost_total_acumulat_eur?.toLocaleString()} €
                              </span>
                            )}
                            {v.alerta_contracte_venciment && (
                              <span className="text-[9px] font-bold text-rose-500">
                                Venciment ({v.dies_restants_contracte}d)!
                              </span>
                            )}
                          </div>
                        )}
                      </td>

                      {/* 5. Custodi / Conductor & OT Activa */}
                      <td className="p-3.5">
                        <div className="space-y-1">
                          <p className="font-semibold text-slate-800 dark:text-slate-200">
                            {v.conductor_nom || v.operari_assignat_nom || (
                              <span className="text-slate-400 italic">Sense assignar</span>
                            )}
                          </p>
                          {v.ordre_treball_activa_codi && (
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border border-blue-200 dark:border-blue-800 shadow-sm"
                                title={`Assignat a l'ordre de treball ${v.ordre_treball_activa_codi}${v.ordre_treball_activa_titol ? `: ${v.ordre_treball_activa_titol}` : ""}`}
                              >
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
                                {v.ordre_treball_activa_codi}
                              </span>
                            </div>
                          )}
                        </div>
                      </td>

                      {/* 6. Odòmetre Acumulat Continu */}
                      <td className="p-3.5 text-center">
                        <span className="font-bold text-slate-900 dark:text-white">
                          {(v.odometre_acumulat || 0).toLocaleString()} km
                        </span>
                      </td>

                      {/* 7. Estat Operatiu (7 estats canònics) */}
                      <td className="p-3.5 text-center">
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                            v.estat === "ASSIGNAT"
                              ? "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800"
                              : v.estat === "OPERATIU"
                              ? "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800"
                              : v.estat === "LEVE"
                              ? "bg-lime-100 text-lime-800 border-lime-300 dark:bg-lime-950 dark:text-lime-300 dark:border-lime-800"
                              : v.estat === "EN_TALLER"
                              ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-400 dark:border-amber-800"
                              : v.estat === "DESFAVORABLE"
                              ? "bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-400 dark:border-rose-800"
                              : v.estat === "INACTIVAT"
                              ? "bg-red-200 text-red-900 border-red-400 dark:bg-red-950 dark:text-red-300 dark:border-red-800"
                              : "bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-400"
                          }`}
                        >
                          {v.estat === "ASSIGNAT"
                            ? "Assignat (OT)"
                            : v.estat === "LEVE"
                            ? "Operatiu (Defectes Lleus)"
                            : v.estat}
                        </span>
                      </td>

                      {/* 8. Consum & Telemetria (RF-16) */}
                      <td className="p-3.5 text-left" onClick={(e) => e.stopPropagation()}>
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[11px] font-bold text-slate-800 dark:text-slate-200">
                              {v.consum_format || (v.consum_l_100km !== null && v.consum_l_100km !== undefined ? `${v.consum_l_100km} L/100km` : "Sense dades")}
                            </span>
                            {v.anomalia_consum && (
                              <button
                                onClick={() => {
                                  setVehicleSeleccionatConsum(v);
                                  setModalDescarteObert(true);
                                }}
                                className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-700 hover:bg-amber-200 flex items-center gap-0.5"
                                title="Anomalia de consum >10%. Clica per descartar amb motiu tipificat."
                              >
                                <AlertTriangle className="w-2.5 h-2.5" />
                                <span>&gt;10% Anomalia</span>
                              </button>
                            )}
                            {v.anomalia_descartada && (
                              <span className="text-[9px] text-slate-400" title={`Descartat: ${v.descarte_detalls?.motiu}`}>
                                (Justificat)
                              </span>
                            )}
                          </div>
                          {v.consum_mitjana_historica !== null && v.consum_mitjana_historica !== undefined && (
                            <p className="text-[9px] text-slate-400">
                              Mitjana històrica: {v.consum_mitjana_historica}
                            </p>
                          )}
                          {v.tipus === "DIESEL" && v.consum_adblue_litres > 0 && (
                            <p className="text-[9px] text-cyan-600 dark:text-cyan-400 font-medium">
                              AdBlue: {v.consum_adblue_litres} L
                            </p>
                          )}
                        </div>
                      </td>

                      {/* 9. ITV & Veredicte (RF-18) */}
                      <td className="p-3.5 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="space-y-1 inline-block text-right">
                          <p className="text-[10px] text-slate-500">
                            {v.data_proxima_itv ? `Venciment: ${v.data_proxima_itv}` : "ITV pendent"}
                          </p>
                          <button
                            onClick={() => {
                              setVehicleSeleccionatItv(v);
                              setDataNovaItv(
                                new Date(Date.now() + 365 * 86400000).toISOString().split("T")[0]
                              );
                              setModalItvObert(true);
                            }}
                            className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700"
                          >
                            Resoldre ITV
                          </button>
                        </div>
                      </td>

                      {/* 10. Accions */}
                      <td className="p-3.5 text-center" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => handleObrirEdicioVehicle(v)}
                          className="px-2.5 py-1 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 hover:bg-emerald-100 dark:hover:bg-emerald-900/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 font-bold text-[10px] flex items-center gap-1 mx-auto transition-colors"
                          title="Obrir fitxa i editar paràmetres del vehicle"
                        >
                          <Edit className="w-3 h-3" />
                          <span>Fitxa / Editar</span>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL 1: RESOLUCIÓ D'ITV EN 4 VEREDICTES (Spec 006 RF-18) */}
      {modalItvObert && vehicleSeleccionatItv && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 space-y-4 shadow-xl text-slate-900 dark:text-slate-100">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <h3 className="font-bold text-sm font-mono">
                  Resolució d'ITV: {vehicleSeleccionatItv.matricula}
                </h3>
              </div>
              <button
                onClick={() => setModalItvObert(false)}
                className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleRegistrarItv} className="space-y-4 text-xs font-mono">
              {/* Selecció dels 4 Veredictes */}
              <div className="space-y-2">
                <label className="font-bold text-slate-700 dark:text-slate-300">
                  Veredicte Oficial de la Inspecció (4 Vies):
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setVeredicteItv("FAVORABLE")}
                    className={`p-3 rounded-xl border text-left space-y-1 transition-colors ${
                      veredicteItv === "FAVORABLE"
                        ? "border-emerald-600 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-300"
                        : "border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Favorable Neta</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">
                      El vehicle recupera l'estat Operatiu [Verd].
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setVeredicteItv("LEVE")}
                    className={`p-3 rounded-xl border text-left space-y-1 transition-colors ${
                      veredicteItv === "LEVE"
                        ? "border-lime-600 bg-lime-50 text-lime-900 dark:bg-lime-950/60 dark:text-lime-300"
                        : "border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5 text-lime-600 dark:text-lime-400">
                      <Check className="w-4 h-4" />
                      <span>Favorable DL</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">
                      Operatiu [Verd Clar] amb defectes lleus a manteniment.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setVeredicteItv("DESFAVORABLE")}
                    className={`p-3 rounded-xl border text-left space-y-1 transition-colors ${
                      veredicteItv === "DESFAVORABLE"
                        ? "border-rose-600 bg-rose-50 text-rose-900 dark:bg-rose-950/60 dark:text-rose-300"
                        : "border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
                      <AlertTriangle className="w-4 h-4" />
                      <span>Desfavorable</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">
                      Immobilitzat + 2 mesos de termini + obertura d'OT a taller.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setVeredicteItv("NEGATIVA")}
                    className={`p-3 rounded-xl border text-left space-y-1 transition-colors ${
                      veredicteItv === "NEGATIVA"
                        ? "border-red-700 bg-red-50 text-red-900 dark:bg-red-950/60 dark:text-red-300"
                        : "border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5 text-red-700 dark:text-red-400">
                      <ShieldAlert className="w-4 h-4" />
                      <span>Negativa</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">
                      Immobilització total + avís obligatori de grua.
                    </p>
                  </button>
                </div>
              </div>

              {/* Data nova ITV */}
              <div className="space-y-1">
                <label className="font-bold text-slate-700 dark:text-slate-300">
                  Nova Data de Venciment:
                </label>
                <input
                  type="date"
                  required
                  value={dataNovaItv}
                  onChange={(e) => setDataNovaItv(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                />
              </div>

              {/* Defectes detectats si no és favorable neta */}
              {veredicteItv !== "FAVORABLE" && (
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Defectes detectats en l'informe oficial:
                  </label>
                  <textarea
                    rows={3}
                    placeholder="Descriu els defectes lleus o greus reflectits a la inspecció..."
                    value={defectesItv}
                    onChange={(e) => setDefectesItv(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
              )}

              {/* Botons d'acció */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalItvObert(false)}
                  className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 font-bold"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow"
                >
                  Confirmar Resolució ITV
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: DESCARTE TIPICAT D'ANOMALIA DE CONSUM (>10%) (Spec 006 RF-16) */}
      {modalDescarteObert && vehicleSeleccionatConsum && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 space-y-4 shadow-xl text-slate-900 dark:text-slate-100">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Fuel className="w-5 h-5 text-amber-500" />
                <h3 className="font-bold text-sm font-mono">
                  Descartar Anomalia de Consum: {vehicleSeleccionatConsum.matricula}
                </h3>
              </div>
              <button
                onClick={() => setModalDescarteObert(false)}
                className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-500 font-mono">
              Consum registrat ({vehicleSeleccionatConsum.consum_l_100km} L/100km) superior en més d'un 10% a la mitjana consolidada ({vehicleSeleccionatConsum.consum_mitjana_historica} L/100km).
            </p>

            <form onSubmit={handleDescartarAnomalia} className="space-y-4 text-xs font-mono">
              <div className="space-y-1">
                <label className="font-bold text-slate-700 dark:text-slate-300">
                  Motiu Tipificat Homologat:
                </label>
                <select
                  value={motiuTipificat}
                  onChange={(e) => setMotiuTipificat(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                >
                  <option value="CARREGA_PESADA">Càrrega pesada / arrastre de remolc</option>
                  <option value="CLIMATOLOGIA_ADVERSA">Climatologia adversa / ús intensiu de calefacció</option>
                  <option value="RUTA_MUNTANYA">Ruta de muntanya / pistes de terra</option>
                  <option value="FUGA_MECANICA">Pèrdua de combustible / fuga mecànica revisada en taller</option>
                  <option value="ALTRES">Altres motius justificats</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="font-bold text-slate-700 dark:text-slate-300">
                  Observacions / Justificació:
                </label>
                <textarea
                  rows={3}
                  placeholder="Detalla les circumstàncies de la desviació..."
                  value={observacionsDescarte}
                  onChange={(e) => setObservacionsDescarte(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalDescarteObert(false)}
                  className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 font-bold"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold shadow"
                >
                  Justificar & Tancar Anomalia
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: REGISTRE DE NOU VEHICLE / MAQUINÀRIA / REMOLC (Spec 006 RF-05) */}
      {modalNouVehicleObert && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 space-y-4 shadow-xl text-slate-900 dark:text-slate-100">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Car className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <h3 className="font-bold text-sm font-mono">Alta de Nou Vehicle a la Flota</h3>
              </div>
              <button
                onClick={() => setModalNouVehicleObert(false)}
                className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Zona Dropzone d'extracció Multi-Document IA dins la pròpia modal */}
            {hasCopilotIa && (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  const files = e.dataTransfer?.files;
                  if (files && files.length > 0) processFilesOcr(Array.from(files));
                }}
                onClick={() => modalFileInputRef.current?.click()}
                className={`p-3.5 rounded-xl border-2 border-dashed transition-all cursor-pointer text-center ${
                  ocrLoading
                    ? "border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/20"
                    : "border-slate-300 dark:border-slate-700 hover:border-indigo-500 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                }`}
              >
                <input
                  ref={modalFileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  accept="image/*,.pdf,application/pdf,.md,.txt,text/markdown,text/plain"
                  onChange={handleOcrUpload}
                />
                <div className="flex items-center justify-center gap-2 text-indigo-600 dark:text-indigo-400 font-mono text-xs font-bold">
                  {ocrLoading ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin text-indigo-500" />
                      <span>Extreient dades dels documents amb IA...</span>
                    </>
                  ) : (
                    <>
                      <FileText className="w-4 h-4 text-indigo-500" />
                      <span>Arrossega o clica per afegir documents (ITV, Assegurança, Factura en PDF, Markdown .md o imatges)</span>
                    </>
                  )}
                </div>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-1 font-mono">
                  L'OCR creua fitxa tècnica ITV, assegurança i manteniments en una única alta.
                </p>

                {/* Badges de documents processats */}
                {fitxersAdjunts.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2.5 justify-center">
                    {fitxersAdjunts.map((adj, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
                      >
                        <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                        <span>{adj.nom}</span>
                        <span className="opacity-60 text-[9px]">({adj.tipus})</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            <form onSubmit={handleCrearVehicle} className="space-y-4 text-xs font-mono">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Matrícula / Codi d'Actiu:
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: 4321-KMN o MINI-EXC-01"
                    value={novaMatricula}
                    onChange={(e) => setNovaMatricula(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs uppercase focus:outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Distintiu Ambiental DGT:
                  </label>
                  <select
                    value={nouDistintiu}
                    onChange={(e) => setNouDistintiu(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="ZERO">0 Emissions (Blau)</option>
                    <option value="ECO">ECO (Verd/Blau)</option>
                    <option value="C">C (Verd)</option>
                    <option value="B">B (Groc)</option>
                    <option value="SENSE">Sense Distintiu</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Marca:</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Ford, Renault, Toyota"
                    value={novaMarca}
                    onChange={(e) => setNovaMarca(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Model & Versió:</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Transit, Master L2H2"
                    value={nouModel}
                    onChange={(e) => setNouModel(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Tipus de Propulsió:
                  </label>
                  <select
                    value={nouTipus}
                    onChange={(e) => setNouTipus(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="DIESEL">Dièsel (Combustió)</option>
                    <option value="GASOLINA">Gasolina</option>
                    <option value="EV">100% Elèctric (EV)</option>
                    <option value="PHEV">Híbrid Enchufable (PHEV)</option>
                    <option value="MAQUINARIA">Maquinària d'Obra (Horòmetre)</option>
                    <option value="REMOLC">Remolc de Transport (Exempt Consum)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Conductor Habitual Assignat:
                  </label>
                  <select
                    value={nouConductorId}
                    onChange={(e) => setNouConductorId(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="">Sense conductor assignat</option>
                    {operaris.map((op) => (
                      <option key={op.id} value={op.id}>
                        {op.nom} {op.cognoms || ""} ({op.especialitat || "Operari"})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Règim d'Adquisició:
                  </label>
                  <select
                    value={nouRegim}
                    onChange={(e) => {
                      const val = e.target.value;
                      setNouRegim(val);
                      if (!["RENTING", "LEASING", "LLOGUER"].includes(val)) {
                        setNouLimitKm("");
                      }
                    }}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="PROPIETAT">Compra en Propietat (Sense límit de km)</option>
                    <option value="RENTING">Rènting (Arrendament operatiu OPEX)</option>
                    <option value="LEASING">Lísing (Arrendament financer amb opció compra)</option>
                    <option value="LLOGUER">Lloguer (Flota temporal / Rent-a-Car)</option>
                    <option value="SUBSTITUCIO">Vehicle de Substitució Temporal</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300 flex items-center justify-between">
                    <span>Límit Contractual (km):</span>
                    {["RENTING", "LEASING", "LLOGUER"].includes(nouRegim) ? (
                      <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">
                        {nouRegim === "RENTING" ? "Requerit per Rènting" : "Opcional"}
                      </span>
                    ) : (
                      <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">No aplica</span>
                    )}
                  </label>
                  {["RENTING", "LEASING", "LLOGUER"].includes(nouRegim) ? (
                    <input
                      type="number"
                      min={1000}
                      placeholder="Ex: 120000"
                      value={nouLimitKm}
                      onChange={(e) => setNouLimitKm(e.target.value ? Number(e.target.value) : "")}
                      className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    />
                  ) : (
                    <div className="w-full p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-mono text-xs flex items-center gap-1.5 cursor-not-allowed">
                      <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
                      <span>Exempt — Compra en propietat</span>
                    </div>
                  )}
                </div>
              </div>

              {/* SECCIÓ DETALLS DE CONTRACTE & FINANCES */}
              {["RENTING", "LEASING", "LLOGUER"].includes(nouRegim) && (
                <div className="p-3.5 rounded-xl bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 space-y-3">
                  <div className="flex items-center gap-1.5 font-bold text-xs text-amber-800 dark:text-amber-300">
                    <span>Paràmetres Contractuals i Financers ({nouRegim}):</span>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="space-y-1">
                      <label className="font-bold text-slate-700 dark:text-slate-300">Data Inici Contracte:</label>
                      <input
                        type="date"
                        value={novaDataIniciContracte}
                        onChange={(e) => setNovaDataIniciContracte(e.target.value)}
                        className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="font-bold text-slate-700 dark:text-slate-300">Data Fi Contracte:</label>
                      <input
                        type="date"
                        value={novaDataFiContracte}
                        onChange={(e) => setNovaDataFiContracte(e.target.value)}
                        className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="font-bold text-slate-700 dark:text-slate-300">Odòmetre a l'Inici (km):</label>
                      <input
                        type="number"
                        min={0}
                        placeholder="0"
                        value={nouOdometreInici}
                        onChange={(e) => setNouOdometreInici(e.target.value ? Number(e.target.value) : 0)}
                        className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    {["RENTING", "LEASING"].includes(nouRegim) ? (
                      <div className="space-y-1">
                        <label className="font-bold text-slate-700 dark:text-slate-300">Quota Mensual (€):</label>
                        <input
                          type="number"
                          step="0.01"
                          min={0}
                          placeholder="Ex: 450.00"
                          value={novaQuotaMensual}
                          onChange={(e) => setNovaQuotaMensual(e.target.value)}
                          className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                        />
                      </div>
                    ) : (
                      <div className="space-y-1">
                        <label className="font-bold text-slate-700 dark:text-slate-300">Tarifa Diària (€/dia):</label>
                        <input
                          type="number"
                          step="0.01"
                          min={0}
                          placeholder="Ex: 35.00"
                          value={novaTarifaDiaria}
                          onChange={(e) => setNovaTarifaDiaria(e.target.value)}
                          className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                        />
                      </div>
                    )}
                    <div className="space-y-1">
                      <label className="font-bold text-slate-700 dark:text-slate-300">Preu km Excés (€/km):</label>
                      <input
                        type="number"
                        step="0.0001"
                        min={0}
                        placeholder="Ex: 0.0800"
                        value={nouPreuKmExces}
                        onChange={(e) => setNouPreuKmExces(e.target.value)}
                        className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                      />
                    </div>
                    {nouRegim === "LEASING" ? (
                      <div className="space-y-1">
                        <label className="font-bold text-slate-700 dark:text-slate-300">Valor Residual Opció Compra (€):</label>
                        <input
                          type="number"
                          step="0.01"
                          min={0}
                          placeholder="Ex: 3500.00"
                          value={nouValorResidual}
                          onChange={(e) => setNouValorResidual(e.target.value)}
                          className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                        />
                      </div>
                    ) : nouRegim === "LLOGUER" ? (
                      <div className="space-y-1">
                        <label className="font-bold text-slate-700 dark:text-slate-300">Fiança Dipositada (€):</label>
                        <input
                          type="number"
                          step="0.01"
                          min={0}
                          placeholder="Ex: 300.00"
                          value={novaFianca}
                          onChange={(e) => setNovaFianca(e.target.value)}
                          className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                        />
                      </div>
                    ) : null}
                  </div>
                </div>
              )}

              {/* SECCIÓ DE TELEMETRIA I CONSUM (Spec 006 RF-16) */}
              <div className="p-3.5 rounded-xl bg-slate-100/60 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-3">
                <div className="flex items-center gap-1.5 font-bold text-xs text-slate-800 dark:text-slate-200">
                  <Fuel className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  <span>Dades de Consum & Telemetria:</span>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">
                      Odòmetre Inicial (km):
                    </label>
                    <input
                      type="number"
                      min={0}
                      value={nouOdometre}
                      onChange={(e) => setNouOdometre(Number(e.target.value))}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">
                      {nouTipus === "EV"
                        ? "Consum Real (kWh/100km):"
                        : nouTipus === "MAQUINARIA"
                        ? "Consum Real (L/h):"
                        : nouTipus === "REMOLC"
                        ? "Consum (Exempt):"
                        : "Consum Real (L/100km):"}
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min={0}
                      disabled={nouTipus === "REMOLC"}
                      placeholder={nouTipus === "REMOLC" ? "Exempt" : "Ex: 6.8"}
                      value={nouTipus === "REMOLC" ? "" : nouConsumReal}
                      onChange={(e) => setNouConsumReal(e.target.value ? Number(e.target.value) : "")}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none disabled:opacity-50"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">
                      Mitjana Històrica:
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min={0}
                      disabled={nouTipus === "REMOLC"}
                      placeholder={nouTipus === "REMOLC" ? "Exempt" : "Ex: 6.5"}
                      value={nouTipus === "REMOLC" ? "" : nouConsumMitjana}
                      onChange={(e) => setNouConsumMitjana(e.target.value ? Number(e.target.value) : "")}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none disabled:opacity-50"
                    />
                  </div>

                  {nouTipus === "DIESEL" && (
                    <div className="space-y-1 col-span-3">
                      <label className="font-bold text-slate-700 dark:text-slate-300 flex items-center justify-between">
                        <span>AdBlue Acumulat (Litres):</span>
                        <span className="text-[10px] text-cyan-600 dark:text-cyan-400 font-medium">
                          Segregació informativa dièsel (Spec 006)
                        </span>
                      </label>
                      <input
                        type="number"
                        step="0.5"
                        min={0}
                        placeholder="Ex: 12.5"
                        value={nouConsumAdblue}
                        onChange={(e) => setNouConsumAdblue(e.target.value ? Number(e.target.value) : 0)}
                        className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                      />
                    </div>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Assegurança (Companyia):</label>
                  <input
                    type="text"
                    placeholder="Ex: Mapfre, Allianz, AXA"
                    value={novaCompanyiaAsseguranca}
                    onChange={(e) => setNovaCompanyiaAsseguranca(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Caducitat Assegurança:</label>
                  <input
                    type="date"
                    value={novaDataAsseguranca}
                    onChange={(e) => setNovaDataAsseguranca(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
                
                <div className="space-y-1 col-span-2">
                  <label className="font-bold text-slate-700 dark:text-slate-300 flex justify-between">
                    <span>Pòlissa (Núm) i Document Assegurança:</span>
                    {arxiuAsseguranca && (
                      <span className="text-emerald-600 dark:text-emerald-400 font-mono text-[10px] font-bold">
                        ✓ {arxiuAsseguranca.name}
                      </span>
                    )}
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Ex: POL-9938221"
                      value={novaPolissaAsseguranca}
                      onChange={(e) => setNovaPolissaAsseguranca(e.target.value)}
                      className="w-1/2 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[11px] focus:outline-none"
                    />
                    <input
                      type="file"
                      accept="image/*,.pdf,application/pdf,.md,.txt,text/markdown,text/plain"
                      onChange={(e) => setArxiuAsseguranca(e.target.files?.[0] || null)}
                      className="w-1/2 p-1.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[10px] file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-[10px] file:bg-emerald-600 file:text-white"
                    />
                  </div>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1 col-span-2">
                  <label className="font-bold text-slate-700 dark:text-slate-300 flex justify-between">
                    <span>Documentació ITV (Fitxa Tècnica / Targeta ITV):</span>
                    {arxiuITV && (
                      <span className="text-emerald-600 dark:text-emerald-400 font-mono text-[10px] font-bold">
                        ✓ {arxiuITV.name}
                      </span>
                    )}
                  </label>
                  <input
                    type="file"
                    accept="image/*,.pdf,application/pdf,.md,.txt,text/markdown,text/plain"
                    onChange={(e) => setArxiuITV(e.target.files?.[0] || null)}
                    className="w-full p-1.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[10px] file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-[10px] file:bg-emerald-600 file:text-white"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Estat ITV actual:</label>
                  <select
                    value={nouEstatItv}
                    onChange={(e) => setNouEstatItv(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="FAVORABLE">Favorable Neta</option>
                    <option value="LEVE">Favorable amb Def. Lleus</option>
                    <option value="DESFAVORABLE">Desfavorable</option>
                    <option value="NEGATIVA">Negativa</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Data propera ITV:</label>
                  <input
                    type="date"
                    value={novaDataItv}
                    onChange={(e) => setNovaDataItv(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
                <div className="space-y-1 col-span-2">
                  <label className="font-bold text-slate-700 dark:text-slate-300 flex justify-between">
                    <span>Última Reparació / Canvi Oli (Factura o Justificant):</span>
                    {arxiuReparacio && (
                      <span className="text-emerald-600 dark:text-emerald-400 font-mono text-[10px] font-bold">
                        ✓ {arxiuReparacio.name}
                      </span>
                    )}
                  </label>
                  <input
                    type="file"
                    accept="image/*,.pdf,application/pdf,.md,.txt,text/markdown,text/plain"
                    onChange={(e) => setArxiuReparacio(e.target.files?.[0] || null)}
                    className="w-full p-1.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[10px] file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-[10px] file:bg-emerald-600 file:text-white"
                  />
                </div>
                <div className="space-y-1 col-span-2">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Carnet Requerit:</label>
                  <select
                    value={nouCarnet}
                    onChange={(e) => setNouCarnet(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="B">B (Turismes/Furgonetes)</option>
                    <option value="B+E">B+E (Remolc)</option>
                    <option value="C">C (Camions rígids)</option>
                    <option value="C+E">C+E (Tràilers)</option>
                    <option value="AM">AM / A1 (Motos)</option>
                    <option value="N/A">Maquinària exempta</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalNouVehicleObert(false)}
                  className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 font-bold"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={creantVehicle}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow disabled:opacity-50 flex items-center gap-2"
                >
                  {creantVehicle && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>{creantVehicle ? "Guardant i vinculant..." : "Donar d'Alta Vehicle"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 4: FITXA EDITABLE DEL VEHICLE (Spec 006 / Edició Completa) */}
      {modalEdicioObert && vehicleAEditar && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-3xl max-h-[92vh] overflow-y-auto rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 space-y-5 shadow-2xl text-slate-900 dark:text-slate-100">
            {/* Header Modal Edició */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center border border-emerald-200 dark:border-emerald-800">
                  <Edit className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm font-mono flex items-center gap-2">
                    Fitxa del Vehicle: {editMatricula || vehicleAEditar.matricula}
                    <span className="text-[10px] font-normal px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
                      {editMarca} {editModel}
                    </span>
                  </h3>
                  <p className="text-[11px] text-slate-400 font-mono">
                    Edició de dades tècniques, conductor habitual, consum i documents associats.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setModalEdicioObert(false)}
                className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleGuardarEdicio} className="space-y-4 text-xs font-mono">
              {/* BLOC 1: IDENTIFICACIÓ & TIPOLOGIA */}
              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-3">
                <h4 className="font-bold text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                  <Car className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  Identificació i Estat Operatiu
                </h4>
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Matrícula:</label>
                    <input
                      type="text"
                      required
                      value={editMatricula}
                      onChange={(e) => setEditMatricula(e.target.value.toUpperCase())}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none uppercase"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Marca:</label>
                    <input
                      type="text"
                      required
                      value={editMarca}
                      onChange={(e) => setEditMarca(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Model:</label>
                    <input
                      type="text"
                      required
                      value={editModel}
                      onChange={(e) => setEditModel(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Propulsió:</label>
                    <select
                      value={editTipus}
                      onChange={(e) => setEditTipus(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    >
                      <option value="DIESEL">Dièsel (Combustió)</option>
                      <option value="GASOLINA">Gasolina</option>
                      <option value="EV">100% Elèctric (EV)</option>
                      <option value="PHEV">Híbrid Enchufable (PHEV)</option>
                      <option value="MAQUINARIA">Maquinària d'Obra (Horòmetre)</option>
                      <option value="REMOLC">Remolc (Exempt Consum)</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Distintiu DGT:</label>
                    <select
                      value={editDistintiu}
                      onChange={(e) => setEditDistintiu(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    >
                      <option value="ZERO">0 Emissions (Blau)</option>
                      <option value="ECO">ECO (Verd/Blau)</option>
                      <option value="C">C (Verd)</option>
                      <option value="B">B (Groc)</option>
                      <option value="SENSE">Sense Distintiu</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Estat Operatiu:</label>
                    <select
                      value={editEstat}
                      onChange={(e) => setEditEstat(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    >
                      <option value="OPERATIU">Operatiu (Verd)</option>
                      <option value="ASSIGNAT">Assignat a Obra / OT (Blau)</option>
                      <option value="LEVE">Operatiu Defectes Lleus</option>
                      <option value="EN_TALLER">En Taller</option>
                      <option value="DESFAVORABLE">ITV Desfavorable (Immobilitzat)</option>
                      <option value="INACTIVAT">ITV Negativa (Grua)</option>
                      <option value="INCIDENCIA">Incidència</option>
                      <option value="BAIXA">Baixa</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* BLOC 2: CUSTÒDIA I RÈGIM CONTRACTUAL */}
              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                    Custòdia & Règim Contractual
                  </h4>
                  {vehicleAEditar?.ordre_treball_activa_codi && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
                      OT Activa: {vehicleAEditar.ordre_treball_activa_codi}
                    </span>
                  )}
                </div>
                {vehicleAEditar?.ordre_treball_activa_codi && (
                  <div className="p-2.5 rounded-lg bg-blue-50/70 dark:bg-blue-950/40 border border-blue-100 dark:border-blue-900/40 text-[11px] text-blue-900 dark:text-blue-200 space-y-0.5">
                    <p className="font-bold flex items-center gap-1.5">
                      <span>Ordre de Treball: {vehicleAEditar.ordre_treball_activa_codi}</span>
                      {vehicleAEditar.ordre_treball_activa_titol && (
                        <span className="font-normal text-blue-700 dark:text-blue-300">({vehicleAEditar.ordre_treball_activa_titol})</span>
                      )}
                    </p>
                    {vehicleAEditar.operari_assignat_nom && (
                      <p className="text-[10px] text-blue-800/80 dark:text-blue-300/80">
                        Responsable / Conductor en obra: <span className="font-semibold">{vehicleAEditar.operari_assignat_nom}</span>
                      </p>
                    )}
                  </div>
                )}
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">
                      Conductor Habitual:
                    </label>
                    <select
                      value={editConductorId}
                      onChange={(e) => setEditConductorId(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    >
                      <option value="">Sense conductor assignat</option>
                      {operaris.map((op) => (
                        <option key={op.id} value={op.id}>
                          {op.nom} {op.cognoms || ""} ({op.especialitat || "Operari"})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Règim Adquisició:</label>
                    <select
                      value={editRegim}
                      onChange={(e) => {
                        const val = e.target.value;
                        setEditRegim(val);
                        if (val !== "RENTING" && val !== "LLOGUER" && val !== "LEASING") setEditLimitKm("");
                      }}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    >
                      <option value="PROPIETAT">Compra en Propietat</option>
                      <option value="RENTING">Rènting</option>
                      <option value="LEASING">Lísing (Arrendament Financer)</option>
                      <option value="LLOGUER">Lloguer Temporer</option>
                      <option value="SUBSTITUCIO">Vehicle de Substitució</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300 flex items-center justify-between">
                      <span>Límit Contractual km:</span>
                      {editRegim === "RENTING" || editRegim === "LLOGUER" || editRegim === "LEASING" ? (
                        <span className="text-[10px] text-amber-600 font-medium">Requerit/Opcional</span>
                      ) : (
                        <span className="text-[10px] text-emerald-600 font-medium">Exempt</span>
                      )}
                    </label>
                    <input
                      type="number"
                      disabled={editRegim !== "RENTING" && editRegim !== "LLOGUER" && editRegim !== "LEASING"}
                      placeholder={editRegim === "RENTING" || editRegim === "LLOGUER" || editRegim === "LEASING" ? "Ex: 120000" : "Exempt"}
                      value={editLimitKm}
                      onChange={(e) => setEditLimitKm(e.target.value ? Number(e.target.value) : "")}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none disabled:opacity-50"
                    />
                  </div>
                </div>

                {/* Sub-panell de Paràmetres Financers i Contractuals si Rènting/Lísing/Lloguer */}
                {(editRegim === "RENTING" || editRegim === "LEASING" || editRegim === "LLOGUER") && (
                  <div className="mt-3 p-3.5 rounded-xl bg-indigo-50/60 dark:bg-indigo-950/20 border border-indigo-200 dark:border-indigo-900/50 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-indigo-700 dark:text-indigo-400">
                        {editRegim === "RENTING"
                          ? "Condicions Específiques de Rènting"
                          : editRegim === "LEASING"
                          ? "Condicions de Lísing Financer (Arrendament)"
                          : "Condicions de Contracte de Lloguer"}
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-medium">
                        Diferenciació Financera Activa
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      <div className="space-y-1">
                        <label className="font-bold text-slate-700 dark:text-slate-300">
                          Odòmetre Inici Contracte (km):
                        </label>
                        <input
                          type="number"
                          min={0}
                          placeholder="Ex: 45000"
                          value={editOdometreInici}
                          onChange={(e) => setEditOdometreInici(e.target.value)}
                          className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="font-bold text-slate-700 dark:text-slate-300">Data Inici Contracte:</label>
                        <input
                          type="date"
                          value={editDataIniciContracte}
                          onChange={(e) => setEditDataIniciContracte(e.target.value)}
                          className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="font-bold text-slate-700 dark:text-slate-300">Data Fi Contracte:</label>
                        <input
                          type="date"
                          value={editDataFiContracte}
                          onChange={(e) => setEditDataFiContracte(e.target.value)}
                          className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      {editRegim === "LLOGUER" ? (
                        <div className="space-y-1">
                          <label className="font-bold text-slate-700 dark:text-slate-300">Tarifa Diària (€/dia):</label>
                          <input
                            type="number"
                            step="0.01"
                            min={0}
                            placeholder="Ex: 35.00"
                            value={editTarifaDiaria}
                            onChange={(e) => setEditTarifaDiaria(e.target.value)}
                            className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                          />
                        </div>
                      ) : (
                        <div className="space-y-1">
                          <label className="font-bold text-slate-700 dark:text-slate-300">Quota Mensual (€/mes):</label>
                          <input
                            type="number"
                            step="0.01"
                            min={0}
                            placeholder="Ex: 480.00"
                            value={editQuotaMensual}
                            onChange={(e) => setEditQuotaMensual(e.target.value)}
                            className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                          />
                        </div>
                      )}

                      <div className="space-y-1">
                        <label className="font-bold text-slate-700 dark:text-slate-300">Preu km Excés (€/km):</label>
                        <input
                          type="number"
                          step="0.0001"
                          min={0}
                          placeholder="Ex: 0.0800"
                          value={editPreuKmExces}
                          onChange={(e) => setEditPreuKmExces(e.target.value)}
                          className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                        />
                      </div>

                      {editRegim === "LEASING" ? (
                        <div className="space-y-1">
                          <label className="font-bold text-slate-700 dark:text-slate-300">Valor Residual Opció Compra (€):</label>
                          <input
                            type="number"
                            step="0.01"
                            min={0}
                            placeholder="Ex: 3500.00"
                            value={editValorResidual}
                            onChange={(e) => setEditValorResidual(e.target.value)}
                            className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                          />
                        </div>
                      ) : editRegim === "LLOGUER" ? (
                        <div className="space-y-1">
                          <label className="font-bold text-slate-700 dark:text-slate-300">Fiança Dipositada (€):</label>
                          <input
                            type="number"
                            step="0.01"
                            min={0}
                            placeholder="Ex: 300.00"
                            value={editFianca}
                            onChange={(e) => setEditFianca(e.target.value)}
                            className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                          />
                        </div>
                      ) : null}
                    </div>
                  </div>
                )}
              </div>

              {/* BLOC 3: TELEMETRIA DE CONSUM & HISTÒRIC (Spec 006 RF-16) */}
              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-3">
                <h4 className="font-bold text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                  <Fuel className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  Telemetria de Consum & Quilometratge
                </h4>
                <div className="grid grid-cols-4 gap-3">
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Odòmetre (km):</label>
                    <input
                      type="number"
                      min={0}
                      value={editOdometre}
                      onChange={(e) => setEditOdometre(Number(e.target.value))}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">
                      {editTipus === "EV"
                        ? "Consum (kWh/100):"
                        : editTipus === "MAQUINARIA"
                        ? "Consum (L/h):"
                        : editTipus === "REMOLC"
                        ? "Consum:"
                        : "Consum (L/100km):"}
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min={0}
                      disabled={editTipus === "REMOLC"}
                      placeholder={editTipus === "REMOLC" ? "Exempt" : "Ex: 6.8"}
                      value={editTipus === "REMOLC" ? "" : editConsumL100km}
                      onChange={(e) => setEditConsumL100km(e.target.value ? Number(e.target.value) : "")}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none disabled:opacity-50"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Mitjana Històrica:</label>
                    <input
                      type="number"
                      step="0.1"
                      min={0}
                      disabled={editTipus === "REMOLC"}
                      placeholder={editTipus === "REMOLC" ? "Exempt" : "Ex: 6.5"}
                      value={editTipus === "REMOLC" ? "" : editConsumMitjana}
                      onChange={(e) => setEditConsumMitjana(e.target.value ? Number(e.target.value) : "")}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none disabled:opacity-50"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">AdBlue (Litres):</label>
                    <input
                      type="number"
                      step="0.5"
                      min={0}
                      disabled={editTipus !== "DIESEL"}
                      placeholder={editTipus === "DIESEL" ? "Ex: 12.0" : "No aplica"}
                      value={editTipus === "DIESEL" ? editConsumAdblue : ""}
                      onChange={(e) => setEditConsumAdblue(e.target.value ? Number(e.target.value) : 0)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none disabled:opacity-50"
                    />
                  </div>
                </div>
              </div>

              {/* BLOC 4: ITV, ASSEGURANÇA & CARNET */}
              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-3">
                <h4 className="font-bold text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  Estat Legal, ITV & Assegurança
                </h4>
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Estat ITV:</label>
                    <select
                      value={editEstatItv}
                      onChange={(e) => setEditEstatItv(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    >
                      <option value="FAVORABLE">Favorable Neta</option>
                      <option value="LEVE">Favorable amb Def. Lleus</option>
                      <option value="DESFAVORABLE">Desfavorable</option>
                      <option value="NEGATIVA">Negativa</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Data propera ITV:</label>
                    <input
                      type="date"
                      value={editDataItv}
                      onChange={(e) => setEditDataItv(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Carnet Requerit:</label>
                    <select
                      value={editCarnet}
                      onChange={(e) => setEditCarnet(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    >
                      <option value="B">B (Turismes/Furgonetes)</option>
                      <option value="B+E">B+E (Remolc)</option>
                      <option value="C">C (Camions rígids)</option>
                      <option value="C+E">C+E (Tràilers)</option>
                      <option value="AM">AM / A1 (Motos)</option>
                      <option value="N/A">Maquinària exempta</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Companyia Asseguradora:</label>
                    <input
                      type="text"
                      placeholder="Ex: Mapfre"
                      value={editCompanyiaAsseguranca}
                      onChange={(e) => setEditCompanyiaAsseguranca(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Pòlissa Assegurança:</label>
                    <input
                      type="text"
                      placeholder="Ex: POL-123456"
                      value={editPolissaAsseguranca}
                      onChange={(e) => setEditPolissaAsseguranca(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-bold text-slate-700 dark:text-slate-300">Caducitat Assegurança:</label>
                    <input
                      type="date"
                      value={editDataAsseguranca}
                      onChange={(e) => setEditDataAsseguranca(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* BLOC 5: HISTORIAL DE REPARACIONS I MANTENIMENTS */}
              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2">
                <h4 className="font-bold text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                  <Wrench className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  Historial de Reparacions & Manteniments
                </h4>
                <textarea
                  rows={3}
                  placeholder="Canvis d'oli, canvi de pneumàtics, manteniments d'ITV..."
                  value={editHistorialReparacions}
                  onChange={(e) => setEditHistorialReparacions(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                />
              </div>

              {/* BLOC 6: DOCUMENTS ASSOCIATS AL VEHICLE */}
              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                    <Paperclip className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                    Documents Vinculats ({documentsVehicle.length})
                  </h4>
                  <div className="flex items-center gap-2">
                    <select
                      value={nouDocTipus}
                      onChange={(e) => setNouDocTipus(e.target.value)}
                      className="text-[10px] bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-2 py-1 font-mono focus:outline-none"
                    >
                      <option value="FITXA_TECNICA">Fitxa Tècnica / ITV</option>
                      <option value="ASSEGURANCA">Assegurança</option>
                      <option value="MANTENIMENT">Factura / Reparació</option>
                      <option value="ALTRES">Altres</option>
                    </select>
                    <input
                      ref={editFileInputRef}
                      type="file"
                      className="hidden"
                      accept="image/*,.pdf,application/pdf,.md,.txt,text/markdown,text/plain"
                      onChange={handlePujarDocumentDirecte}
                    />
                    <button
                      type="button"
                      disabled={pujantDocVehicle}
                      onClick={() => editFileInputRef.current?.click()}
                      className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-[10px] flex items-center gap-1 shadow-sm transition-colors disabled:opacity-50"
                    >
                      <Upload className="w-3 h-3" />
                      <span>{pujantDocVehicle ? "Pujant..." : "Afegir Document"}</span>
                    </button>
                  </div>
                </div>

                {carregantDocs ? (
                  <p className="text-[10px] text-slate-400 py-2 flex items-center gap-1.5">
                    <RefreshCw className="w-3 h-3 animate-spin text-emerald-500" />
                    Carregant documents...
                  </p>
                ) : documentsVehicle.length === 0 ? (
                  <p className="text-[10px] text-slate-400 italic py-1">
                    No hi ha documents adjunts per a aquest vehicle.
                  </p>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    {documentsVehicle.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center justify-between p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 text-[10px]"
                      >
                        <div className="flex items-center gap-2 truncate">
                          <FileText className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                          <div className="truncate">
                            <p className="font-bold truncate">{doc.nom_original}</p>
                            <span className="text-[9px] text-slate-400 font-mono">
                              {doc.tipus_document} {doc.mida_bytes ? `• ${(doc.mida_bytes / 1024).toFixed(1)} KB` : ""}
                            </span>
                          </div>
                        </div>
                        <a
                          href={`${getApiBaseUrl()}/gestio/flota/${vehicleAEditar.id}/documents/${doc.id}/descarregar`}
                          target="_blank"
                          rel="noreferrer"
                          className="p-1 rounded text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 flex-shrink-0"
                          title="Descarregar document"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </a>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* BOTONS D'ACCIÓ MODAL EDICIÓ */}
              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalEdicioObert(false)}
                  className="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-bold"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardantEdicio}
                  className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow disabled:opacity-50 flex items-center gap-2"
                >
                  {guardantEdicio && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>{guardantEdicio ? "Guardant dades..." : "Guardar Modificacions"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
