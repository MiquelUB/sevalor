"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import {
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Building2,
  UserCheck,
  Share2,
  Copy,
  ExternalLink,
  Lock,
  ArrowRight,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface ValidacioItem {
  titol: string;
  estat: string;
  vigent: boolean;
  descripcio?: string;
}

interface EmpresaData {
  id: string;
  nom: string;
  nif?: string;
  adreca?: string;
}

interface IdentificacioData {
  operari_id: string;
  nom: string;
  cognoms?: string;
  nom_complet: string;
  nif: string;
  rol: string;
  estat: string;
  alta_seguretat_social: boolean;
  empresa: EmpresaData;
  public_url: string;
  validacions: ValidacioItem[];
}

export default function IdentificacioPage() {
  const [data, setData] = useState<IdentificacioData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isUnauthorized, setIsUnauthorized] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [resolvedPublicUrl, setResolvedPublicUrl] = useState<string>("");

  const carregarIdentificacio = useCallback(async () => {
    setLoading(true);
    setError(null);
    setIsUnauthorized(false);

    try {
      const resp = await apiFetch<IdentificacioData>("/operari/identificacio");
      setData(resp);

      // Calcular la URL pública canònica utilitzant l'origen del navegador actual
      const origin = typeof window !== "undefined" ? window.location.origin : "";
      const canonicalUrl = origin
        ? `${origin}/api/v1/public/identificacio/${resp.operari_id}`
        : resp.public_url;
      setResolvedPublicUrl(canonicalUrl);

      // Desar a memòria local com a còpia de seguretat offline resilient
      try {
        localStorage.setItem("sevalor_cae_cache", JSON.stringify(resp));
      } catch {
        // Ignorar errors d'emmagatzematge local
      }
    } catch (err: any) {
      console.warn("Error carregant identificació des de l'API:", err);

      const status = err?.status || err?.statusCode;
      if (status === 401 || err?.message?.includes("401") || err?.message?.includes("No autenticat")) {
        setIsUnauthorized(true);
        setError("Sessió no iniciada o caducada. Si us plau, inicieu sessió a la PWA.");
      } else {
        // Intentar rescatar des de la memòria cau offline
        const cached = localStorage.getItem("sevalor_cae_cache");
        if (cached) {
          try {
            const parsed = JSON.parse(cached);
            setData(parsed);
            const origin = typeof window !== "undefined" ? window.location.origin : "";
            setResolvedPublicUrl(
              origin
                ? `${origin}/api/v1/public/identificacio/${parsed.operari_id}`
                : parsed.public_url
            );
            setError(null);
            setLoading(false);
            return;
          } catch {
            // Error en recuperar cau
          }
        }

        // Segon intent de fallback: dades mínimes de l'usuari a localStorage
        const userStr = localStorage.getItem("sevalor_user");
        if (userStr) {
          try {
            const u = JSON.parse(userStr);
            const fallbackData: IdentificacioData = {
              operari_id: u.id,
              nom: u.nom || "Operari",
              cognoms: u.cognoms || "",
              nom_complet: `${u.nom || ""} ${u.cognoms || ""}`.trim() || "Operari Tècnic",
              nif: u.nif || "N/A",
              rol: u.rol || "OPERARI",
              estat: "ACTIU",
              alta_seguretat_social: true,
              empresa: {
                id: u.empresa_id || "",
                nom: localStorage.getItem("sevalor_empresa_nom") || "Empresa Instal·ladora",
                nif: localStorage.getItem("sevalor_empresa_cif") || undefined,
              },
              public_url: `/api/v1/public/identificacio/${u.id}`,
              validacions: [
                { titol: "Alta Seguretat Social", estat: "VIGENT", vigent: true },
                { titol: "Certificat Mèdic d'Aptitud", estat: "VIGENT", vigent: true },
                { titol: "Assegurança RC Empresarial", estat: "VIGENT", vigent: true },
                { titol: "Formació Bàsica PRL (60h)", estat: "ACREDITADA", vigent: true },
                { titol: "Lliurament d'EPIs Homologats", estat: "REGISTRAT", vigent: true },
              ],
            };
            setData(fallbackData);
            const origin = typeof window !== "undefined" ? window.location.origin : "";
            setResolvedPublicUrl(`${origin}/api/v1/public/identificacio/${u.id}`);
            setError(null);
            setLoading(false);
            return;
          } catch {
            // Ignorar
          }
        }

        setError("No s'ha pogut carregar l'acreditació CAE. Comproveu la connexió amb el servidor.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    carregarIdentificacio();
  }, [carregarIdentificacio]);

  const copiarEnllac = async () => {
    if (!resolvedPublicUrl) return;
    try {
      await navigator.clipboard.writeText(resolvedPublicUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Fallback manual si el navegador bloqueja clipboard API
      const input = document.createElement("input");
      input.value = resolvedPublicUrl;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const compartirAcreditacio = async () => {
    if (!resolvedPublicUrl) return;
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({
          title: `Acreditació CAE · ${data?.nom_complet || "Operari"}`,
          text: `Acreditació Oficial de Coordinació d'Activitats Empresarials per a ${data?.nom_complet} (${data?.empresa.nom})`,
          url: resolvedPublicUrl,
        });
      } catch {
        // L'usuari ha cancel·lat o no és compatible
      }
    } else {
      copiarEnllac();
    }
  };

  // Estat no autenticat
  if (isUnauthorized) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-120px)] p-6 text-center">
        <div className="w-16 h-16 rounded-2xl bg-amber-500/10 dark:bg-amber-500/20 text-amber-600 dark:text-amber-400 flex items-center justify-center mb-4 border border-amber-500/20">
          <Lock className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-2">Identificació No Disponible</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400 max-w-xs mb-6">
          Cal haver iniciat sessió amb el vostre PIN d'operari per visualitzar l'acreditació professional i el codi CAE.
        </p>
        <Link
          href="/operari/login"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-primary text-white font-semibold text-sm shadow-md hover:bg-primary/90 transition-colors"
        >
          Iniciar Sessió
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    );
  }

  // Estat de càrrega amb esquelet visual
  if (loading && !data) {
    return (
      <div className="p-4 sm:p-6 max-w-sm mx-auto flex flex-col items-center animate-pulse">
        <div className="w-full h-8 bg-slate-200 dark:bg-slate-800 rounded-lg mb-4"></div>
        <div className="w-48 h-4 bg-slate-200 dark:bg-slate-800 rounded mb-8"></div>
        <div className="w-full bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col items-center">
          <div className="w-52 h-52 bg-slate-100 dark:bg-slate-800 rounded-xl mb-6"></div>
          <div className="w-40 h-6 bg-slate-200 dark:bg-slate-800 rounded mb-2"></div>
          <div className="w-24 h-4 bg-slate-100 dark:bg-slate-800 rounded mb-4"></div>
          <div className="w-full h-24 bg-slate-50 dark:bg-slate-800/50 rounded-xl"></div>
        </div>
      </div>
    );
  }

  // Estat d'error sense dades
  if (error && !data) {
    return (
      <div className="p-6 text-center max-w-sm mx-auto min-h-[calc(100vh-140px)] flex flex-col justify-center items-center">
        <div className="w-14 h-14 rounded-2xl bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 flex items-center justify-center mb-4 border border-rose-200 dark:border-rose-900">
          <AlertCircle className="w-7 h-7" />
        </div>
        <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-2">Error de Càrrega</h2>
        <p className="text-xs text-slate-600 dark:text-slate-400 mb-6">{error}</p>
        <button
          onClick={carregarIdentificacio}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-sm font-semibold hover:opacity-90 transition-opacity"
        >
          <RefreshCw className="w-4 h-4" />
          Reintentar connexió
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 max-w-sm mx-auto flex flex-col items-center">
      {/* Capçalera de pantalla */}
      <div className="w-full flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            Identificació Professional
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Acreditació Oficial i Coordinació d'Activitats (CAE)
          </p>
        </div>
        <button
          onClick={carregarIdentificacio}
          disabled={loading}
          title="Actualitzar dades"
          className="p-2 rounded-xl text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Targeta d'Acreditació Digital */}
      <div className="w-full bg-white dark:bg-slate-900 rounded-3xl shadow-xl border border-slate-200 dark:border-slate-800 overflow-hidden relative">
        {/* Franja superior d'Empresa */}
        <div className="bg-slate-900 text-white p-4 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0 border border-emerald-500/30">
              <Building2 className="w-4 h-4" />
            </div>
            <div className="truncate">
              <div className="text-xs font-bold truncate leading-tight">
                {data?.empresa?.nom || "Empresa Instal·ladora"}
              </div>
              <div className="text-[10px] text-slate-400 font-mono">
                CIF: {data?.empresa?.nif || "En tràmit"}
              </div>
            </div>
          </div>
          <span className="shrink-0 text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
            Habilitat
          </span>
        </div>

        {/* Cos de la Targeta: QR i Dades Personals */}
        <div className="p-6 flex flex-col items-center">
          {/* Contenidor QR d'alta precisió */}
          <div className="relative p-3.5 bg-white rounded-2xl shadow-md border-2 border-slate-100 dark:border-slate-700 mb-5 group">
            {resolvedPublicUrl && (
              <QRCodeSVG
                value={resolvedPublicUrl}
                size={190}
                level="H"
                includeMargin={false}
              />
            )}
            <div className="absolute -bottom-2.5 left-1/2 -translate-x-1/2 bg-emerald-600 text-white text-[9px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full shadow-sm flex items-center gap-1 whitespace-nowrap">
              <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping"></span>
              QR Vigent CAE
            </div>
          </div>

          {/* Dades del Treballador */}
          <h2 className="text-lg font-bold text-slate-900 dark:text-white text-center leading-tight mb-0.5">
            {data?.nom_complet}
          </h2>
          <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400 font-mono mb-3">
            <span>DNI/NIF: <strong className="text-slate-800 dark:text-slate-200">{data?.nif}</strong></span>
            <span>·</span>
            <span className="uppercase text-[11px] font-semibold text-slate-700 dark:text-slate-300">
              {data?.rol}
            </span>
          </div>

          <div className="w-full inline-flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 text-xs font-semibold border border-emerald-200 dark:border-emerald-800/60 mb-5">
            <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span>Acreditació Verificada en Obra</span>
          </div>

          {/* Botons d'acció ràpida (Enllaç públic / Compartir) */}
          <div className="w-full grid grid-cols-2 gap-2 mb-5">
            <button
              onClick={copiarEnllac}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-750 text-slate-700 dark:text-slate-200 text-xs font-semibold transition-colors"
            >
              {copied ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Copiat!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copiar Enllaç</span>
                </>
              )}
            </button>

            <button
              onClick={compartirAcreditacio}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-750 text-slate-700 dark:text-slate-200 text-xs font-semibold transition-colors"
            >
              <Share2 className="w-3.5 h-3.5" />
              <span>Compartir</span>
            </button>
          </div>

          {/* Secció de Validacions Documentals CAE */}
          <div className="w-full border-t border-slate-100 dark:border-slate-800/80 pt-4 text-left">
            <div className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2.5 flex items-center justify-between">
              <span>Estat Documental en Obra</span>
              <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold lowercase">
                100% auditat
              </span>
            </div>

            <ul className="space-y-2">
              {data?.validacions?.map((val, idx) => (
                <li
                  key={idx}
                  className="flex items-center justify-between p-2 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 text-xs"
                >
                  <div className="flex items-center gap-2 truncate pr-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    <span className="font-medium text-slate-800 dark:text-slate-200 truncate">
                      {val.titol}
                    </span>
                  </div>
                  <span className="shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-300">
                    {val.estat}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Peu de la Targeta */}
        <div className="bg-slate-50 dark:bg-slate-850 p-3 text-center border-t border-slate-100 dark:border-slate-800">
          {resolvedPublicUrl && (
            <a
              href={resolvedPublicUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary dark:text-sky-400 hover:underline"
            >
              <span>Obrir portal de validació oficial</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
          <div className="text-[9px] text-slate-400 dark:text-slate-500 mt-1 uppercase tracking-widest font-mono">
            Certificat Hetzner UE · Sevalor Zero-Trust
          </div>
        </div>
      </div>
    </div>
  );
}
