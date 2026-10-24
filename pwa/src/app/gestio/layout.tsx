"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import CopilotWidget from "@/components/CopilotWidget";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  GestioProvider,
  useGestio,
} from "@/lib/gestio-context";
import { clearAuthToken, apiFetch } from "@/lib/api";
import {
  Shield,
  Search,
  Sun,
  Moon,
  X,
  LogOut,
  ExternalLink,
} from "lucide-react";

function GestioLayoutContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { rolActiu, setRolActiu, spotlightObert, setSpotlightObert, isDark, toggleTheme } = useGestio();
  const [cercaSpotlight, setCercaSpotlight] = useState("");
  const [isEmbed, setIsEmbed] = useState(false);
  const [vistaResultats, setVistaResultats] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setIsEmbed(window.location.search.includes("embed=true") || window.self !== window.top);
      setVistaResultats(window.location.search.includes("vista=resultats"));
    }
  }, [pathname]);

  const [usuari, setUsuari] = useState<{ nom?: string; rol?: string; is_impersonation?: boolean } | null>(null);

  const handleLogout = () => {
    clearAuthToken();
    window.location.href = "/gestio/login";
  };

  const navLinks = [
    { label: "Dashboard", href: "/gestio", icon: "dashboard", badge: "GIS" },
    { label: "Mapa en Temps Real", href: "/gestio/mapa", icon: "explore", badge: "MAP" },
    { label: "Clients", href: "/gestio/clients", icon: "group", badge: "CLI" },
    { label: "Magatzem", href: "/gestio/magatzem", icon: "inventory_2", badge: "STK" },
    { label: "Vehicles", href: "/gestio/flota", icon: "local_shipping", badge: "FLT" },
    { label: "Operaris", href: "/gestio/operaris", icon: "engineering", badge: "RRHH" },
    { label: "Plànols", href: "/gestio/planols", icon: "map", badge: "CAD" },
    { label: "Proveïdors & CAE", href: "/gestio/proveidors", icon: "factory", badge: "PRV" },
    { label: "Contractes", href: "/gestio/contractes", icon: "description", badge: "CTR" },
    { label: "Comptabilitat", href: "/gestio/comptabilitat", icon: "receipt_long", badge: "SIF" },
    { label: "Notificacions", href: "/gestio/notificacions", icon: "notifications", badge: "CHAT" },
    { label: "Copilot IA", href: "/gestio/copilot", icon: "auto_awesome", badge: "IA" },
    { label: "Configuració", href: "/gestio/configuracio", icon: "settings", badge: "CFG" },
  ];

  // Base de dades per al meta-cercador Spotlight (carregada des del backend)
  const [itemsSpotlight, setItemsSpotlight] = useState<any[]>([]);
  const [empresa, setEmpresa] = useState<{
    nom?: string;
    nif?: string;
    feature_copilot_ia?: boolean;
  } | null>(null);

  useEffect(() => {
    if (pathname === "/gestio/login") return;

    let tokenIsImpersonation = false;
    if (typeof window !== "undefined") {
      try {
        const match = document.cookie.match(new RegExp("(^| )sevalor_access_token=([^;]+)"));
        const token = match ? decodeURIComponent(match[2]) : null;
        if (token) {
          const parts = token.split(".");
          if (parts.length === 3) {
            const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
            tokenIsImpersonation = Boolean(payload?.is_impersonation);
          }
        }
      } catch {}
    }

    try {
      const stored = localStorage.getItem("sevalor_user");
      if (stored) {
        const u = JSON.parse(stored);
        const isImpersonating = Boolean(u.is_impersonation || tokenIsImpersonation);
        setUsuari({ ...u, is_impersonation: isImpersonating });
        if (u.rol === "SUPERADMIN" && !isImpersonating) {
          router.push("/superadmin/telemetria");
          return;
        }
      }
    } catch {}

    apiFetch("/auth/me")
      .then((me: any) => {
        if (me) {
          const isImpersonating = Boolean(me.is_impersonation || tokenIsImpersonation);
          setUsuari({ ...me, is_impersonation: isImpersonating });
          if (me.rol) setRolActiu(me.rol);
          if (me.rol === "SUPERADMIN" && !isImpersonating) {
            router.push("/superadmin/telemetria");
          }
        }
      })
      .catch(() => {});

    apiFetch("/spotlight/items")
      .then((data: any[]) => setItemsSpotlight(data || []))
      .catch(() => setItemsSpotlight([]));
    apiFetch("/gestio/configuracio/empresa")
      .then((data: any) => setEmpresa(data))
      .catch(() => setEmpresa(null));
  }, [pathname]);

  if (pathname === "/gestio/login") {
    return <div className="min-h-screen bg-surface">{children}</div>;
  }

  const resultatsFiltrats = itemsSpotlight.filter((item) => {
    // Spec 001 RF-03: Veto d'Enginyer (ocultar resultats financers)
    if (rolActiu === "ENGINYER" && item.esFinancera) return false;
    return (
      item.titol.toLowerCase().includes(cercaSpotlight.toLowerCase()) ||
      item.desc.toLowerCase().includes(cercaSpotlight.toLowerCase())
    );
  });

  if (isEmbed) {
    return (
      <div className="flex flex-col h-full w-full bg-surface overflow-hidden">
        <main className="flex-1 flex flex-col h-full w-full overflow-hidden">{children}</main>
      </div>
    );
  }

  const currentSectionLabel =
    navLinks.find((l) => l.href === pathname)?.label || "Dashboard";

  return (
    <div className="min-h-screen bg-surface font-body-base text-on-surface transition-colors duration-200">
      {/* SIDEBAR FIX ESQUERRA (Stitch 240px Navy) */}
      <aside className="fixed left-0 top-0 h-full w-[240px] bg-primary text-on-primary z-50 flex flex-col transition-all duration-200 shadow-xl">
        {/* Brand Header */}
        <div className="p-md flex items-center justify-between gap-sm mb-sm border-b border-primary-container/60">
          <Link href="/gestio" className="flex items-center gap-sm min-w-0">
            <div className="w-9 h-9 rounded-lg bg-secondary-container text-on-secondary-container flex items-center justify-center font-bold shadow-md shrink-0">
              <span className="material-symbols-outlined text-[20px]">agriculture</span>
            </div>
            <div className="flex flex-col min-w-0">
              <span className="font-display-lg text-lg text-white tracking-tight truncate">
                {empresa?.nom || "Sevalor"}
              </span>
              <span className="text-[10px] font-mono text-on-primary-container uppercase tracking-wider truncate">
                {empresa?.nif || "SEVALOR SUITE"}
              </span>
            </div>
          </Link>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 space-y-xs overflow-y-auto custom-scrollbar py-xs">
          {navLinks
            .filter((link) => {
              if (link.href === "/gestio/copilot" && empresa && empresa.feature_copilot_ia === false) {
                return false;
              }
              return true;
            })
            .map((link) => {
            const isActive =
              link.href === "/gestio"
                ? pathname === "/gestio"
                : pathname.startsWith(link.href);

            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center justify-between px-md py-sm transition-colors gap-md ${
                  isActive
                    ? "border-l-4 border-secondary-container bg-primary-container text-white"
                    : "text-on-primary-container hover:bg-primary-container/60 hover:text-white"
                }`}
              >
                <div className="flex items-center gap-md min-w-0">
                  <span className="material-symbols-outlined text-[20px] shrink-0">
                    {link.icon}
                  </span>
                  <span className="font-body-strong text-sm truncate">{link.label}</span>
                </div>
                <span
                  className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded shrink-0 ${
                    isActive
                      ? "bg-secondary-container text-on-secondary-container"
                      : "bg-primary-container/70 text-on-primary-container"
                  }`}
                >
                  {link.badge}
                </span>
              </Link>
            );
          })}

          <div className="pt-sm mt-sm border-t border-primary-container/50 px-md">
            <Link
              href="/operari/feines"
              className="flex items-center justify-between py-sm px-sm rounded-lg text-xs text-on-primary-container hover:bg-primary-container hover:text-white transition-colors"
            >
              <span className="flex items-center gap-sm font-body-strong">
                <span className="material-symbols-outlined text-[18px] text-secondary-container">
                  smartphone
                </span>
                PWA Operaris (Camp)
              </span>
              <ExternalLink className="w-3.5 h-3.5 opacity-75" />
            </Link>
          </div>
        </nav>

        {/* User Profile Footer */}
        <div className="mt-auto p-md border-t border-primary-container flex items-center justify-between gap-sm bg-primary/95">
          <div className="flex items-center gap-sm min-w-0">
            <div className="w-9 h-9 rounded-full bg-primary-container border border-outline-variant/40 text-white font-bold flex items-center justify-center text-sm shrink-0">
              {(usuari?.nom || "M").charAt(0).toUpperCase()}
            </div>
            <div className="flex flex-col min-w-0">
              <span className="font-body-strong text-white text-sm truncate">
                {usuari?.nom || "Oficina Tècnica"}
              </span>
              <span className="text-xs text-on-primary-container truncate">
                {rolActiu}
              </span>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="p-2 rounded-lg text-on-primary-container hover:bg-error hover:text-white transition-colors shrink-0"
            title="Tancar Sessió"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </aside>

      {/* ÀREA DRETA (Header doble + Main) */}
      <div className="pl-[240px] flex flex-col min-h-screen">
        {/* CAPÇALERA DOBLE STITCH */}
        <header className="fixed top-0 left-[240px] right-0 h-32 bg-surface/85 backdrop-blur-md z-40 flex flex-col shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
          {/* Barra Superior (Cerca global + Accions) */}
          <div className="h-16 px-xl flex items-center justify-between border-b border-surface-container-highest">
            <div
              onClick={() => setSpotlightObert(true)}
              className="flex items-center bg-surface-container-low px-md py-xs rounded-lg w-96 border border-outline-variant cursor-pointer hover:border-primary transition-colors"
            >
              <span className="material-symbols-outlined text-outline text-[20px]">search</span>
              <input
                readOnly
                onFocus={() => setSpotlightObert(true)}
                className="bg-transparent border-none outline-none ml-sm w-full text-sm text-on-surface placeholder:text-outline cursor-pointer"
                placeholder="Cerca global (Ctrl+K)..."
                type="text"
              />
              <span className="text-[10px] font-mono bg-surface-container-lowest px-1.5 py-0.5 rounded border border-outline-variant/50 text-on-surface-variant">
                Ctrl+K
              </span>
            </div>

            <div className="flex items-center gap-md">
              {/* Banner compacte si és sessió d'impersonació Superadmin */}
              {usuari?.is_impersonation && (
                <div className="bg-secondary-container text-on-secondary-container px-3 py-1 rounded-full text-xs font-bold flex items-center gap-2 shadow-sm">
                  <Shield className="w-3.5 h-3.5 shrink-0" />
                  <span>Impersonació: {empresa?.nom || "Actiu"}</span>
                  <button
                    onClick={() => {
                      clearAuthToken();
                      window.location.href = "/superadmin/login";
                    }}
                    className="ml-1 px-2 py-0.5 bg-primary text-white rounded-full text-[10px] hover:opacity-90"
                  >
                    Sortir
                  </button>
                </div>
              )}

              <button
                onClick={toggleTheme}
                className="p-2 rounded-lg hover:bg-surface-container-high text-on-surface-variant hover:text-primary transition-colors"
                title="Commutar Tema"
              >
                {isDark ? (
                  <Sun className="w-4 h-4 text-secondary-container" />
                ) : (
                  <Moon className="w-4 h-4" />
                )}
              </button>

              <Link
                href="/gestio/copilot"
                className="p-2 rounded-lg hover:bg-surface-container-high text-on-surface-variant hover:text-primary transition-colors"
                title="Copilot IA & Ajuda Tècnica"
              >
                <span className="material-symbols-outlined text-[22px]">help</span>
              </Link>

              <Link
                href="/gestio/notificacions"
                className="relative p-2 rounded-lg hover:bg-surface-container-high text-on-surface-variant hover:text-primary transition-colors"
                title="Notificacions i Alertes"
              >
                <span className="material-symbols-outlined text-[22px]">notifications</span>
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full"></span>
              </Link>
            </div>
          </div>

          {/* Sub-barra de pestanyes (FEINA / RESULTATS) i Breadcrumb */}
          <div className="h-16 px-xl flex items-center justify-between">
            <nav className="flex h-full gap-lg">
              <Link
                href="/gestio"
                onClick={() => {
                  setVistaResultats(false);
                  setTimeout(() => window.dispatchEvent(new Event("sevalor-vista-change")), 10);
                }}
                className={`flex items-center h-full px-sm font-label-caps text-label-caps uppercase tracking-wider transition-all ${
                  pathname === "/gestio" && !vistaResultats
                    ? "text-secondary-container border-b-2 border-secondary-container font-bold"
                    : "text-on-surface-variant hover:text-primary"
                }`}
              >
                FEINA
              </Link>
              <Link
                href="/gestio?vista=resultats"
                onClick={() => {
                  setVistaResultats(true);
                  setTimeout(() => window.dispatchEvent(new Event("sevalor-vista-change")), 10);
                }}
                className={`flex items-center h-full px-sm font-label-caps text-label-caps uppercase tracking-wider transition-all ${
                  pathname === "/gestio" && vistaResultats
                    ? "text-secondary-container border-b-2 border-secondary-container font-bold"
                    : "text-on-surface-variant hover:text-primary"
                }`}
              >
                RESULTATS
              </Link>
              <Link
                href="/gestio/mapa"
                className={`flex items-center h-full px-sm font-label-caps text-label-caps uppercase tracking-wider transition-all ${
                  pathname === "/gestio/mapa"
                    ? "text-secondary-container border-b-2 border-secondary-container font-bold"
                    : "text-on-surface-variant hover:text-primary"
                }`}
              >
                MAPA EN TEMPS REAL
              </Link>
              <Link
                href="/gestio/planols"
                className={`flex items-center h-full px-sm font-label-caps text-label-caps uppercase tracking-wider transition-all ${
                  pathname === "/gestio/planols"
                    ? "text-secondary-container border-b-2 border-secondary-container font-bold"
                    : "text-on-surface-variant hover:text-primary"
                }`}
              >
                BIBLIOTECA DE PLÀNOLS
              </Link>
            </nav>

            <nav className="hidden md:flex items-center text-xs text-on-surface-variant gap-xs">
              <span className="material-symbols-outlined text-[14px]">home</span>
              <span>/</span>
              <Link href="/gestio" className="hover:text-primary">
                Sevalor
              </Link>
              <span>/</span>
              <span className="font-body-strong text-primary">{currentSectionLabel}</span>
            </nav>
          </div>
        </header>

        {/* CONTINGUT PRINCIPAL */}
        <main className="relative pt-32 p-xl bg-surface min-h-screen flex-1 flex flex-col">
          {children}
        </main>
      </div>

      <CopilotWidget />

      {/* MODAL SPOTLIGHT META-SEARCH (<200 ms) */}
      {spotlightObert && (
        <div className="fixed inset-0 bg-primary/60 backdrop-blur-sm z-50 flex items-start justify-center pt-24 p-4 animate-fade-in">
          <div className="bg-surface-container-lowest border border-outline-variant/40 rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col">
            <div className="p-3 border-b border-outline-variant/30 flex items-center gap-2 bg-surface-container-low">
              <Search className="w-5 h-5 text-outline ml-1" />
              <input
                type="text"
                autoFocus
                value={cercaSpotlight}
                onChange={(e) => setCercaSpotlight(e.target.value)}
                placeholder="Cercar per codi OT, client, parcel·la o referència..."
                className="flex-1 bg-transparent text-sm font-medium text-on-surface placeholder:text-outline focus:outline-none"
              />
              <button
                onClick={() => setSpotlightObert(false)}
                className="p-1 rounded-lg text-outline hover:text-on-surface"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="max-h-80 overflow-y-auto p-2 space-y-1">
              {resultatsFiltrats.length === 0 ? (
                <div className="p-6 text-center text-xs text-outline">
                  Cap resultat trobat per a &quot;{cercaSpotlight}&quot;.
                </div>
              ) : (
                resultatsFiltrats.map((item, idx) => (
                  <div
                    key={idx}
                    onClick={() => {
                      setSpotlightObert(false);
                      router.push(item.ref);
                    }}
                    className="p-2.5 rounded-xl hover:bg-surface-container-low cursor-pointer flex items-center justify-between transition-colors"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                          {item.tipus}
                        </span>
                        <h4 className="text-xs font-bold text-on-surface">
                          {item.titol}
                        </h4>
                      </div>
                      <p className="text-[11px] text-on-surface-variant mt-0.5">
                        {item.desc}
                      </p>
                    </div>
                    <span className="text-[10px] text-secondary font-bold">
                      Navegar &rarr;
                    </span>
                  </div>
                ))
              )}
            </div>

            <div className="p-2.5 bg-surface-container-low border-t border-outline-variant/30 text-[10px] font-mono text-outline flex items-center justify-between">
              <span>Navega amb fletxes o ratolí</span>
              <span>ESC per tancar</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function GestioLayout({ children }: { children: React.ReactNode }) {
  return (
    <GestioProvider>
      <GestioLayoutContent>{children}</GestioLayoutContent>
    </GestioProvider>
  );
}