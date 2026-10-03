"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Server,
  Activity,
  UserPlus,
  ShieldCheck,
  FileCode,
  Sun,
  Moon,
  Radio,
  ExternalLink,
  LogOut,
  Terminal,
  Shield,
  Layers,
  Building2,
  HardDrive,
  Cpu,
  CheckCircle2,
  Menu,
  X,
} from "lucide-react";
import { clearAuthToken } from "@/lib/api";

export default function SuperadminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [isDark, setIsDark] = useState<boolean>(true);
  const [mobileOpen, setMobileOpen] = useState<boolean>(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  if (pathname?.startsWith("/superadmin/login")) {
    return <div className="min-h-screen bg-slate-50 dark:bg-slate-950">{children}</div>;
  }

  useEffect(() => {
    const saved = localStorage.getItem("sevalor_theme");
    if (saved === "light") {
      setIsDark(false);
      document.documentElement.classList.remove("dark");
    } else {
      setIsDark(true);
      document.documentElement.classList.add("dark");
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
    router.push("/superadmin/login");
  };

  const navSections = [
    {
      title: "SRE & Salut",
      links: [
        {
          label: "Telemetria & Salut",
          href: "/superadmin/telemetria",
          icon: Activity,
          badge: "SRE",
          desc: "Torre de control & Uptime",
        },
      ],
    },
    {
      title: "Governança Tenants",
      links: [
        {
          label: "Gestió d'Empreses",
          href: "/superadmin/empreses",
          icon: Server,
          badge: "TENANTS",
          desc: "Llicències, estats & quotes",
        },
        {
          label: "Nou Onboarding",
          href: "/superadmin/tenants/onboarding",
          icon: UserPlus,
          badge: "WIZARD",
          desc: "Assistent d'alta en 4 passos",
        },
      ],
    },
    {
      title: "Seguretat & Compliance",
      links: [
        {
          label: "Seguretat Zero-Trust",
          href: "/superadmin/seguretat",
          icon: ShieldCheck,
          badge: "ZERO-TRUST",
          desc: "IP Allowlist, 2FA & RLS",
        },
        {
          label: "Auditoria & RGPD",
          href: "/superadmin/auditoria",
          icon: FileCode,
          badge: "GDPR",
          desc: "Destrucció & Traces d'error",
        },
      ],
    },
  ];

  const isLinkActive = (href: string) => {
    if (href === "/superadmin/telemetria") {
      return pathname === "/superadmin/telemetria" || pathname === "/superadmin";
    }
    if (href === "/superadmin/empreses") {
      return pathname?.startsWith("/superadmin/empreses") || pathname === "/superadmin/tenants";
    }
    if (href === "/superadmin/tenants/onboarding") {
      return pathname === "/superadmin/tenants/onboarding";
    }
    if (href === "/superadmin/seguretat") {
      return pathname?.startsWith("/superadmin/seguretat");
    }
    if (href === "/superadmin/auditoria") {
      return pathname?.startsWith("/superadmin/auditoria");
    }
    return pathname === href;
  };

  const renderSidebarLinks = () => (
    <>
      <div className="p-3 space-y-5 overflow-y-auto">
        {navSections.map((section, sIdx) => (
          <div key={sIdx}>
            <p className="px-3 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5">
              {section.title}
            </p>
            <nav className="space-y-1">
              {section.links.map((link) => {
                const Icon = link.icon;
                const isActive = isLinkActive(link.href);

                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs transition-all ${
                      isActive
                        ? "bg-emerald-600 text-white font-bold shadow-md shadow-emerald-600/20"
                        : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/80 font-medium"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Icon
                        className={`w-4 h-4 shrink-0 ${
                          isActive ? "text-white" : "text-slate-500 dark:text-slate-400"
                        }`}
                      />
                      <div className="truncate text-left">
                        <span className="block truncate">{link.label}</span>
                      </div>
                    </div>
                    <span
                      className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded shrink-0 ml-1.5 ${
                        isActive
                          ? "bg-emerald-700 text-emerald-100"
                          : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700"
                      }`}
                    >
                      {link.badge}
                    </span>
                  </Link>
                );
              })}
            </nav>
          </div>
        ))}
      </div>

      {/* PEU DEL SIDEBAR: ESTAT INFRAESTRUCTURA HETZNER */}
      <div className="p-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/60 space-y-2">
        <div className="p-2.5 rounded-xl bg-white dark:bg-slate-800/70 border border-slate-200 dark:border-slate-700/80 shadow-sm space-y-1">
          <div className="flex items-center justify-between text-[10px] font-mono">
            <span className="text-slate-500 dark:text-slate-400 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-500" />
              SRE Nuremberg
            </span>
            <span className="font-bold text-emerald-600 dark:text-emerald-400">99.9% UPTIME</span>
          </div>
          <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 dark:text-slate-400">
            <span>Hetzner CPX21</span>
            <span>PostgreSQL 16 RLS</span>
          </div>
        </div>

        <p className="px-1 text-[9px] font-mono text-slate-400 text-center">
          Dades 100% sobiranes a la UE • RGPD
        </p>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 font-sans transition-colors duration-200 flex flex-col">
      {/* CAPÇALERA SUPERADMIN D'ALTA DENSITAT */}
      <header className="h-14 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-4 z-40 sticky top-0 shadow-sm transition-colors">
        {/* Logo, Hamburger & Node Info */}
        <div className="flex items-center gap-2 sm:gap-3">
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-1.5 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Menu de navegació"
          >
            {mobileOpen ? <X className="w-5 h-5 text-emerald-500" /> : <Menu className="w-5 h-5" />}
          </button>
          <Link href="/superadmin/telemetria" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-emerald-600 flex items-center justify-center font-black text-white text-xs tracking-wider shadow-lg shadow-emerald-600/20">
              HQ
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-sm tracking-tight text-slate-900 dark:text-white">
                  SEVALOR Superadmin
                </span>
                <span className="text-[9px] font-mono uppercase bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 px-1.5 py-0.5 rounded border border-emerald-300 dark:border-emerald-700 font-bold">
                  SaaS SRE
                </span>
              </div>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-mono hidden sm:block">
                Hetzner CPX21 Nuremberg • DC14 Europa
              </p>
            </div>
          </Link>
        </div>

        {/* Eines capçalera dreta: IP Allowlist, 2FA, Enllaç a Gestió, Theme, Logout */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* IP Allowlist Actiu (Zero-Trust) */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-[11px] font-mono">
            <Radio className="w-3 h-3 text-emerald-500 animate-pulse" />
            <span className="text-slate-500 dark:text-slate-400">Allowlist:</span>
            <span className="text-emerald-600 dark:text-emerald-400 font-bold">Zero-Trust Actiu</span>
          </div>

          {/* 2FA Enforced */}
          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/60 dark:border-emerald-800 dark:text-emerald-300 border text-[11px] font-mono">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            <span>2FA TOTP</span>
          </div>

          {/* Accés ràpid a l'Oficina Tècnica */}
          <Link
            href="/gestio"
            className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white px-2.5 py-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Obrir tauler d'Oficina Tècnica"
          >
            <ExternalLink className="w-3.5 h-3.5 text-blue-500" />
            <span className="hidden sm:inline font-medium">Oficina Tècnica</span>
          </Link>

          {/* Commutador Tema Clar / Fosc */}
          <button
            onClick={toggleTheme}
            className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300 transition-colors"
            title="Commutar Tema Clar / Fosc"
          >
            {isDark ? <Sun className="w-4 h-4 text-amber-500" /> : <Moon className="w-4 h-4 text-blue-500" />}
          </button>

          {/* Tancar sessió */}
          <button
            onClick={handleLogout}
            className="p-1.5 rounded-lg bg-slate-100 hover:bg-rose-100 dark:bg-slate-800 dark:hover:bg-rose-950/50 text-slate-600 hover:text-rose-600 dark:text-slate-400 dark:hover:text-rose-400 transition-colors"
            title="Tancar Sessió Superadmin"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* MOBILE DRAWER */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/60 md:hidden backdrop-blur-xs flex"
          onClick={() => setMobileOpen(false)}
        >
          <aside
            className="w-72 bg-white dark:bg-slate-900 h-full flex flex-col justify-between shadow-2xl p-0 overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-emerald-600 flex items-center justify-center font-bold text-white text-xs">
                  HQ
                </div>
                <span className="font-extrabold text-xs text-slate-900 dark:text-white">
                  SEVALOR Superadmin
                </span>
              </div>
              <button
                onClick={() => setMobileOpen(false)}
                className="p-1 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            {renderSidebarLinks()}
          </aside>
        </div>
      )}

      {/* CONTENIDOR PRINCIPAL AMB SIDEBAR D'ESTIL TWENTY CRM */}
      <div className="flex-1 flex overflow-hidden">
        {/* SIDEBAR ESQUERRA D'ALTA DENSITAT (DESKTOP) */}
        <aside className="hidden md:flex w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex-col justify-between shrink-0 shadow-sm transition-colors">
          {renderSidebarLinks()}
        </aside>

        {/* CONTINGUT PRINCIPAL SUPERADMIN */}
        <main className="flex-1 flex flex-col overflow-y-auto bg-slate-50 dark:bg-slate-950">
          {children}
        </main>
      </div>
    </div>
  );
}