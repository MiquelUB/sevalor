"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  HardHat,
  Building2,
  ArrowRight,
  ShieldCheck,
  Smartphone,
  Laptop,
  WifiOff,
  Clock,
  FileCheck2,
  Boxes,
  Sun,
  Moon,
  LogOut,
  ChevronRight,
  ShieldAlert,
  Server,
  Layers,
  Sparkles,
} from "lucide-react";
import { useChameleon } from "@/lib/chameleon";
import { getAuthToken, clearAuthToken } from "@/lib/api";

interface StoredUser {
  nom?: string;
  cognoms?: string;
  email?: string;
  nif?: string;
  rol?: string;
  empresa_nom?: string;
}

export default function TenantGatewayPage() {
  const router = useRouter();
  const { brand, loading } = useChameleon();

  const [isDark, setIsDark] = useState<boolean>(true);
  const [hostname, setHostname] = useState<string>("");
  const [currentUser, setCurrentUser] = useState<StoredUser | null>(null);
  const [hasToken, setHasToken] = useState<boolean>(false);
  const [isSuperadminHost, setIsSuperadminHost] = useState<boolean>(false);

  useEffect(() => {
    // 1. Configuració de Tema (Fosc per defecte)
    const savedTheme = localStorage.getItem("sevalor_theme");
    if (savedTheme === "light") {
      setIsDark(false);
      document.documentElement.classList.remove("dark");
    } else {
      setIsDark(true);
      document.documentElement.classList.add("dark");
    }

    // 2. Detecció de Hostname i Host de Superadmin
    if (typeof window !== "undefined") {
      const currentHost = window.location.hostname.toLowerCase();
      setHostname(currentHost);

      const adminHost = (
        process.env.NEXT_PUBLIC_PLATFORM_ADMIN_HOST ||
        process.env.PLATFORM_ADMIN_HOST ||
        "sevalor-sevalor-pwa.80opze.easypanel.host"
      ).toLowerCase();

      // Només el host mestre central és superadmin host; les empreses creades MAI ho són
      const isMasterAdmin = currentHost === adminHost;
      setIsSuperadminHost(isMasterAdmin);

      // 3. Comprovació de sessió activa
      const token = getAuthToken();
      setHasToken(Boolean(token));

      const rawUser = localStorage.getItem("sevalor_user");
      if (rawUser) {
        try {
          const parsed = JSON.parse(rawUser);
          setCurrentUser(parsed);
        } catch {
          // Ignorar error de parsing
        }
      }
    }
  }, []);

  const toggleTheme = () => {
    if (isDark) {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("sevalor_theme", "light");
      setIsDark(false);
    } else {
      document.documentElement.classList.add("dark");
      localStorage.setItem("sevalor_theme", "dark");
      setIsDark(true);
    }
  };

  const handleLogout = () => {
    clearAuthToken();
    setCurrentUser(null);
    setHasToken(false);
  };

  const handleResumeSession = () => {
    const rol = currentUser?.rol?.toUpperCase();
    if (rol === "OPERARI" || rol === "CAPATAZ") {
      router.push("/operari/feines");
    } else if (
      rol === "BOSS" ||
      rol === "ENGINYER" ||
      rol === "SECRETARIA" ||
      rol === "COMPTABILITAT"
    ) {
      router.push("/gestio");
    } else if (rol === "SUPERADMIN") {
      router.push("/superadmin/telemetria");
    } else {
      router.push("/gestio");
    }
  };

  // Nom de l'empresa resolt pel Chameleon o fallback net
  const empresaNom =
    brand?.empresa_nom ||
    (hostname ? hostname.split(".")[0].toUpperCase() : "SEVALOR SUITE");

  return (
    <div className="min-h-screen bg-surface text-on-surface flex flex-col justify-between selection:bg-secondary selection:text-on-secondary transition-colors duration-300">
      {/* 1. BARRA SUPERIOR AMB IDENTITAT CORPORATIVA */}
      <header className="w-full border-b border-outline/10 bg-surface-container/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {brand?.logotip_path ? (
              <img
                src={brand.logotip_path}
                alt={empresaNom}
                className="h-9 w-auto max-w-[160px] object-contain rounded"
              />
            ) : (
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center font-bold text-white shadow-sm transition-transform hover:scale-105"
                style={{
                  backgroundColor: brand?.primari_hsl
                    ? `hsl(${brand.primari_hsl})`
                    : "hsl(var(--color-primary))",
                }}
              >
                {empresaNom.slice(0, 2).toUpperCase()}
              </div>
            )}
            <div className="flex flex-col">
              <span className="font-semibold text-sm sm:text-base tracking-tight leading-tight text-on-surface">
                {loading ? "Carregant empresa..." : empresaNom}
              </span>
              <span className="text-[11px] text-on-surface-variant font-mono">
                {hostname || "sevalor.suite"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-high border border-outline/15 text-[11px] font-medium text-on-surface-variant">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              Plataforma Activa · RGPD UE
            </div>

            <button
              onClick={toggleTheme}
              aria-label="Canviar mode de color"
              className="p-2 rounded-lg bg-surface-container hover:bg-surface-container-high border border-outline/15 text-on-surface-variant transition-colors"
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* 2. CONTINGUT PRINCIPAL / PORTAL D'ACCÉS */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-12 flex flex-col justify-center">
        {/* Banner de sessió activa (si l'usuari ja s'ha identificat) */}
        {hasToken && currentUser && (
          <div className="mb-8 p-4 rounded-xl bg-surface-container border border-primary/30 shadow-md flex flex-col sm:flex-row items-center justify-between gap-4 animate-in fade-in slide-in-from-top-2 duration-300">
            <div className="flex items-center gap-3 text-left w-full sm:w-auto">
              <div className="w-10 h-10 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold shrink-0">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs text-on-surface-variant">
                  Sessió corporativa activa detectada
                </p>
                <p className="text-sm font-semibold text-on-surface">
                  {currentUser.nom
                    ? `${currentUser.nom} ${currentUser.cognoms || ""}`
                    : currentUser.email || currentUser.nif || "Usuari autenticat"}
                  <span className="ml-2 inline-block px-2 py-0.5 text-[10px] font-mono rounded bg-secondary/15 text-secondary border border-secondary/30">
                    {currentUser.rol || "ACTIU"}
                  </span>
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
              <button
                onClick={handleResumeSession}
                className="px-4 py-2 rounded-lg bg-primary hover:bg-primary/90 text-on-primary text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
              >
                Continuar a la meva àrea
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleLogout}
                title="Tancar sessió per accedir amb un altre usuari"
                className="p-2 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-on-surface-variant transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Hero d'introducció */}
        <div className="text-center max-w-2xl mx-auto mb-8 sm:mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface-container-high border border-outline/15 text-xs font-medium text-on-surface-variant mb-4">
            <Layers className="w-3.5 h-3.5 text-secondary" />
            <span>Portal d'Accés de Treball</span>
          </div>
          <h1 className="text-2xl sm:text-4xl font-bold tracking-tight text-on-surface mb-3">
            On vols accedir avui?
          </h1>
          <p className="text-sm sm:text-base text-on-surface-variant leading-relaxed">
            Tria el teu entorn de treball segons la teva funció a{" "}
            <span className="font-semibold text-on-surface">{empresaNom}</span>.
          </p>
        </div>

        {/* Graella de Decisió: Els 2 portals (Operaris vs Gestió) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 lg:gap-8 items-stretch">
          {/* TARGETA 1: TERMINAL D'OPERARI (CAMP I MOBILITAT) */}
          <div className="group relative rounded-2xl bg-surface-container/70 border border-outline/15 hover:border-primary/50 transition-all duration-300 p-6 sm:p-8 flex flex-col justify-between hover:shadow-xl hover:shadow-primary/5">
            <div>
              {/* Capçalera Targeta */}
              <div className="flex items-start justify-between mb-6">
                <div className="w-14 h-14 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 dark:text-emerald-400 flex items-center justify-center transition-transform group-hover:scale-105">
                  <HardHat className="w-7 h-7" />
                </div>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  <Smartphone className="w-3.5 h-3.5" />
                  PWA Mòbil · Terreny
                </span>
              </div>

              {/* Títol i Descripció */}
              <h2 className="text-xl sm:text-2xl font-bold text-on-surface mb-2 flex items-center gap-2">
                Terminal d'Operaris
              </h2>
              <p className="text-xs sm:text-sm text-on-surface-variant mb-6 leading-relaxed">
                Interfície tàctil optimitzada per a tècnics de camp, mantenidors,
                instal·ladors i capatassos sota el "Flux dels 30 segons".
              </p>

              {/* Llista de Funcionalitats */}
              <ul className="space-y-3 mb-8 text-xs sm:text-sm text-on-surface-variant">
                <li className="flex items-start gap-2.5">
                  <Clock className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Autenticació ràpida:</strong> Login instantani per PIN de 4
                    dígits i NIF de treballador.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <FileCheck2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Ordres de Treball:</strong> Fitxatge geolocalitzat, plànols de
                    camp i tancament d'intervencions.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <WifiOff className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>100% Offline-first:</strong> Operativa autònoma sense
                    cobertura amb xifratge criptogràfic local AES-GCM.
                  </span>
                </li>
              </ul>
            </div>

            {/* Acció Principal */}
            <div>
              <Link
                href="/operari/login"
                className="w-full inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl font-semibold text-sm transition-all shadow-md group/btn bg-emerald-600 hover:bg-emerald-500 text-white hover:shadow-emerald-600/20"
              >
                <span>Entrar al Terminal d'Operaris</span>
                <ArrowRight className="w-4 h-4 transition-transform group-hover/btn:translate-x-1" />
              </Link>
              <p className="text-center text-[11px] text-on-surface-variant/80 mt-2.5">
                Accés per a operaris i capatassos en ruta
              </p>
            </div>
          </div>

          {/* TARGETA 2: OFICINA TÈCNICA I GESTIÓ (DASHBOARD) */}
          <div className="group relative rounded-2xl bg-surface-container/70 border border-outline/15 hover:border-secondary/50 transition-all duration-300 p-6 sm:p-8 flex flex-col justify-between hover:shadow-xl hover:shadow-secondary/5">
            <div>
              {/* Capçalera Targeta */}
              <div className="flex items-start justify-between mb-6">
                <div
                  className="w-14 h-14 rounded-xl flex items-center justify-center transition-transform group-hover:scale-105"
                  style={{
                    backgroundColor: "hsl(var(--color-secondary-container) / 0.2)",
                    color: "hsl(var(--color-secondary-container))",
                    border: "1px solid hsl(var(--color-secondary-container) / 0.4)",
                  }}
                >
                  <Building2 className="w-7 h-7" />
                </div>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-secondary/10 text-secondary border border-secondary/20">
                  <Laptop className="w-3.5 h-3.5" />
                  Oficina · Seguretat 2FA
                </span>
              </div>

              {/* Títol i Descripció */}
              <h2 className="text-xl sm:text-2xl font-bold text-on-surface mb-2 flex items-center gap-2">
                Oficina i Gestió
              </h2>
              <p className="text-xs sm:text-sm text-on-surface-variant mb-6 leading-relaxed">
                Tauler central per a enginyers de projectes, administració,
                secretaria i direcció tècnica i general.
              </p>

              {/* Llista de Funcionalitats */}
              <ul className="space-y-3 mb-8 text-xs sm:text-sm text-on-surface-variant">
                <li className="flex items-start gap-2.5">
                  <ShieldCheck className="w-4 h-4 text-secondary shrink-0 mt-0.5" />
                  <span>
                    <strong>Seguretat corporativa:</strong> Correu, contrasenya xifrada i
                    segon factor d'autenticació TOTP (2FA).
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <Boxes className="w-4 h-4 text-secondary shrink-0 mt-0.5" />
                  <span>
                    <strong>Planificació i Estoc:</strong> Despatx de quadrilles, mapa
                    d'intervencions, compres i magatzem central.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <FileCheck2 className="w-4 h-4 text-secondary shrink-0 mt-0.5" />
                  <span>
                    <strong>Comptabilitat i Legal:</strong> Facturació Veri*factu RD
                    1007/2023, pressupostos i contractes de manteniment.
                  </span>
                </li>
              </ul>
            </div>

            {/* Acció Principal */}
            <div>
              <Link
                href="/gestio/login"
                className="w-full inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl font-semibold text-sm transition-all shadow-md group/btn bg-primary hover:bg-primary/90 text-on-primary hover:shadow-primary/20"
                style={{
                  backgroundColor: brand?.primari_hsl
                    ? `hsl(${brand.primari_hsl})`
                    : undefined,
                }}
              >
                <span>Entrar a Oficina i Gestió</span>
                <ArrowRight className="w-4 h-4 transition-transform group-hover/btn:translate-x-1" />
              </Link>
              <p className="text-center text-[11px] text-on-surface-variant/80 mt-2.5">
                Accés per a Enginyers, Secretaria, Comptabilitat i Direcció
              </p>
            </div>
          </div>
        </div>

        {/* Avís informatiu d'accés exclusiu */}
        <div className="mt-8 sm:mt-10 p-3.5 rounded-xl bg-surface-container-low border border-outline/10 text-center max-w-xl mx-auto">
          <p className="text-[12px] text-on-surface-variant">
            💡 <strong>Consell d'accés:</strong> Pots desar aquesta pàgina a les
            teves adreces d'interès per entrar directament al teu portal de treball
            sense haver d'escriure rutes manuals.
          </p>
        </div>
      </main>

      {/* 3. PEU DE PÀGINA SOBIRÀ */}
      <footer className="w-full border-t border-outline/10 bg-surface-container/30 py-6 mt-6">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] text-on-surface-variant">
          <div className="flex items-center gap-2">
            <Server className="w-3.5 h-3.5 text-secondary" />
            <span>
              Infraestructura Sobirana Hetzner (UE) · RGPD Compliant · Veri*factu RD
              1007/2023
            </span>
          </div>

          <div className="flex items-center gap-4 font-mono">
            <span>{empresaNom}</span>
            <span>·</span>
            <span>Sevalor Suite v4.0</span>

            {/* SUPERADMIN NOMÉS VISIBLE EN EL HOST CENTRAL DE LA PLATAFORMA (MAI A LES EMPRESES CREARES) */}
            {isSuperadminHost && (
              <>
                <span>·</span>
                <Link
                  href="/superadmin/login"
                  className="hover:text-secondary underline underline-offset-2 transition-colors flex items-center gap-1"
                >
                  <ShieldAlert className="w-3 h-3 text-red-400" />
                  SaaS Master Admin
                </Link>
              </>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}
