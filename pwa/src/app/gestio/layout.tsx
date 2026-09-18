"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import CopilotWidget from "@/components/CopilotWidget";
import { usePathname, useRouter } from "next/navigation";
import {
  GestioProvider,
  useGestio,
  RolGestio,
} from "@/lib/gestio-context";
import { clearAuthToken, apiFetch } from "@/lib/api";
import {
  Compass,
  MapPin,
  Users,
  Package,
  Receipt,
  Truck,
  Factory,
  HardHat,
  Search,
  Sun,
  Moon,
  Shield,
  Bell,
  Settings,
  X,
  LogOut,
  ExternalLink,
  Layers,
  Building2,
  Sparkles,
} from "lucide-react";

function GestioLayoutContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { rolActiu, setRolActiu, spotlightObert, setSpotlightObert, isDark, toggleTheme } = useGestio();
  const [cercaSpotlight, setCercaSpotlight] = useState("");
  const [usuari, setUsuari] = useState<{ nom?: string; rol?: string } | null>(null);

  const handleLogout = () => {
    clearAuthToken();
    router.push("/gestio/login");
  };

  const navLinks = [
    { label: "Torre de Control GIS", href: "/gestio/mapa", icon: Compass, badge: "GIS" },
    { label: "Clients i Finques", href: "/gestio/clients", icon: Users, badge: "CLI" },
    { label: "Magatzem & Inventari", href: "/gestio/magatzem", icon: Package, badge: "STK" },
    { label: "Flota & Vehicles", href: "/gestio/flota", icon: Truck, badge: "FLT" },
    { label: "Proveïdors & CAE", href: "/gestio/proveidors", icon: Factory, badge: "PRV" },
    { label: "Equip & Operaris", href: "/gestio/operaris", icon: HardHat, badge: "RRHH" },
    { label: "Plànols & Xarxes GIS", href: "/gestio/planols", icon: Layers, badge: "CAD" },
    { label: "Notificacions & Xat", href: "/gestio/notificacions", icon: Bell, badge: "CHAT" },
    { label: "Copilot IA & Peritatge", href: "/gestio/copilot", icon: Sparkles, badge: "IA" },
    { label: "Comptabilitat & Veri*factu", href: "/gestio/comptabilitat", icon: Receipt, badge: "SIF" },
    { label: "Configuració & Marca", href: "/gestio/configuracio", icon: Settings, badge: "CFG" },
  ];

  // Base de dades per al meta-cercador Spotlight (carregada des del backend)
  const [itemsSpotlight, setItemsSpotlight] = useState<any[]>([]);
  const [empresa, setEmpresa] = useState<{ nom?: string; nif?: string } | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("sevalor_user");
      if (stored) {
        setUsuari(JSON.parse(stored));
      }
    } catch {}

    if (pathname === "/gestio/login") return;

    apiFetch("/auth/me")
      .then((me: any) => {
        if (me) {
          setUsuari(me);
          if (me.rol) setRolActiu(me.rol);
        }
      })
      .catch(() => {});

    apiFetch("/spotlight/items")
      .then((data: any[]) => setItemsSpotlight(data))
      .catch(() => setItemsSpotlight([]));
    apiFetch("/gestio/configuracio/empresa")
      .then((data: any) => setEmpresa(data))
      .catch(() => setEmpresa(null));
  }, [pathname]);

  if (pathname === "/gestio/login") return <div className="min-h-screen bg-slate-50 dark:bg-slate-950">{children}</div>;

  const resultatsFiltrats = itemsSpotlight.filter((item) => {
    // Spec 001 RF-03: Veto d'Enginyer (ocultar resultats financers)
    if (rolActiu === "ENGINYER" && item.esFinancera) return false;
    return (
      item.titol.toLowerCase().includes(cercaSpotlight.toLowerCase()) ||
      item.desc.toLowerCase().includes(cercaSpotlight.toLowerCase())
    );
  });

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 font-sans transition-colors duration-200 flex flex-col">
      {/* CAPÇALERA SUPERIOR */}
      <header className="h-14 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-4 z-40 sticky top-0 shadow-sm transition-colors">
        <div className="flex items-center gap-4">
          <Link href="/gestio/mapa" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-emerald-600 flex items-center justify-center font-bold text-white shadow-lg shadow-emerald-600/20">
              <MapPin className="w-5 h-5" />
            </div>
            <span className="font-extrabold text-lg tracking-tight hidden sm:block text-slate-800 dark:text-white">
              SEVALOR
            </span>
            <span className="text-[10px] font-mono uppercase bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 px-1.5 py-0.5 rounded font-bold border border-slate-200 dark:border-slate-700">
              Oficina Tècnica
            </span>
          </Link>
        </div>

        {/* Eines capçalera */}
        <div className="flex items-center gap-3">
          {/* Cerca Ràpida (Spotlight) */}
          <button
            onClick={() => setSpotlightObert(true)}
            className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 rounded-lg text-sm text-slate-500 dark:text-slate-400 transition-colors border border-slate-200 dark:border-slate-700 shadow-inner"
          >
            <Search className="w-4 h-4" />
            <span>Cerca global...</span>
            <span className="text-[10px] font-mono bg-white dark:bg-slate-900 px-1 rounded shadow-sm">
              Ctrl+K
            </span>
          </button>

          {/* Veto d'Enginyer (Simulador de Rols per Testing) */}
          <div className="flex items-center gap-1.5 px-2 py-1 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
            <Shield className="w-3.5 h-3.5 text-amber-600 dark:text-amber-500" />
            <select
              value={rolActiu}
              onChange={(e) => setRolActiu(e.target.value as RolGestio)}
              className="bg-transparent text-xs font-bold text-amber-700 dark:text-amber-400 outline-none cursor-pointer"
            >
              <option value="BOSS">Rol: Administrador (SaaS)</option>
              <option value="ENGINYER">Rol: Enginyer (Veto Financer)</option>
            </select>
          </div>

          <button
            onClick={toggleTheme}
            className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300 transition-colors"
          >
            {isDark ? <Sun className="w-4 h-4 text-amber-500" /> : <Moon className="w-4 h-4 text-blue-500" />}
          </button>

          {/* Perfil d'usuari i Logout */}
          <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
            <div className="w-7 h-7 rounded-full bg-emerald-700 text-white font-bold flex items-center justify-center text-xs">
              {(usuari?.nom || "U").charAt(0).toUpperCase()}
            </div>
            <div className="hidden xl:block text-left">
              <p className="text-xs font-bold text-white leading-tight">{usuari?.nom || "Usuari Oficina"}</p>
              <p className="text-[10px] text-slate-400">{rolActiu}</p>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-900/50 text-slate-400 hover:text-rose-300 transition-colors ml-1"
              title="Tancar Sessió"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* CONTENIDOR PRINCIPAL AMB SIDEBAR */}
      <div className="flex-1 flex">
        {/* SIDEBAR DE GESTIÓ */}
        <aside className="w-60 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col justify-between shrink-0 shadow-sm">
          <div className="p-3 space-y-4">
            <div>
              <p className="px-3 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5">
                Central de Comandament
              </p>
              <nav className="space-y-1">
                {navLinks.map((link) => {
                  const Icon = link.icon;
                  const isActive = pathname === link.href;

                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                        isActive
                          ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/20 font-bold"
                          : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <Icon className={`w-4 h-4 ${isActive ? "text-white" : "text-slate-500 dark:text-slate-400"}`} />
                        <span>{link.label}</span>
                      </div>
                      <span
                        className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                          isActive
                            ? "bg-emerald-700 text-emerald-100"
                            : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400"
                        }`}
                      >
                        {link.badge}
                      </span>
                    </Link>
                  );
                })}
              </nav>
            </div>

            <div>
              <p className="px-3 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5">
                Accessos Ràpids
              </p>
              <div className="space-y-1">
                <Link
                  href="/operari/feines"
                  className="flex items-center justify-between px-3 py-1.5 rounded-xl text-xs text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <span className="flex items-center gap-2">
                    <ExternalLink className="w-3.5 h-3.5 text-blue-500" />
                    PWA Operaris (Camp)
                  </span>
                </Link>
              </div>
            </div>
          </div>

          {/* Dades de l'Organització / Tenant (Aïllament RLS) */}
          <div className="p-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60">
            <div className="p-2.5 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm">
              <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                <Building2 className="w-4 h-4" />
                <span className="text-[10px] font-mono uppercase font-bold tracking-wider">Tenant Hetzner</span>
              </div>
              <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100 mt-1 truncate">
                {empresa?.nom || "Carregant..."}
              </h4>
              <p className="text-[10px] font-mono text-slate-500">{empresa?.nif || ""}</p>
            </div>
          </div>
        </aside>

        {/* CONTINGUT DE LA PÀGINA DE GESTIÓ */}
        <main className="flex-1 flex flex-col overflow-hidden bg-slate-50 dark:bg-slate-950">
          {children}
        </main>
      </div>

      <CopilotWidget />

      {/* MODAL SPOTLIGHT META-SEARCH (<200 ms) */}
      {spotlightObert && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-start justify-center pt-24 p-4 animate-fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col">
            <div className="p-3 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2">
              <Search className="w-5 h-5 text-slate-400 ml-1" />
              <input
                type="text"
                autoFocus
                value={cercaSpotlight}
                onChange={(e) => setCercaSpotlight(e.target.value)}
                placeholder="Cercar per codi OT, client, parcela o referència..."
                className="flex-1 bg-transparent text-sm font-medium text-slate-800 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none"
              />
              <button
                onClick={() => setSpotlightObert(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="max-h-80 overflow-y-auto p-2 space-y-1">
              {resultatsFiltrats.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-400">
                  Cap resultat trobat per a "{cercaSpotlight}".
                </div>
              ) : (
                resultatsFiltrats.map((item, idx) => (
                  <div
                    key={idx}
                    onClick={() => {
                      setSpotlightObert(false);
                      router.push(item.ref);
                    }}
                    className="p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer flex items-center justify-between transition-colors"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {item.tipus}
                        </span>
                        <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100">
                          {item.titol}
                        </h4>
                      </div>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                        {item.desc}
                      </p>
                    </div>
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold">
                      Navegar &rarr;
                    </span>
                  </div>
                ))
              )}
            </div>

            <div className="p-2.5 bg-slate-50 dark:bg-slate-850 border-t border-slate-200 dark:border-slate-800 text-[10px] font-mono text-slate-400 flex items-center justify-between">
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