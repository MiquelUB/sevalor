"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Server,
  Activity,
  UserPlus,
  ShieldCheck,
  Sun,
  Moon,
  Globe,
  Radio,
  ExternalLink,
  Cpu,
} from "lucide-react";

export default function SuperadminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [isDark, setIsDark] = useState<boolean>(true);
  if (pathname === "/superadmin/login") return <div className="min-h-screen bg-slate-50 dark:bg-slate-950">{children}</div>;

  useEffect(() => {
    const saved = localStorage.getItem("sevalor_theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
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

  const navLinks = [
    {
      label: "Onboarding de Tenants",
      href: "/superadmin/tenants/onboarding",
      icon: UserPlus,
      spec: "Spec 021",
    },
    {
      label: "Telemetria & Salut",
      href: "/superadmin/telemetria",
      icon: Activity,
      spec: "Spec 022",
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 font-sans transition-colors duration-200 flex flex-col">
      {/* CAPÇALERA SUPERADMIN D'ALTA DENSITAT SRE */}
      <header className="h-14 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-4 z-40 sticky top-0 shadow-sm transition-colors">
        {/* Logo & Node Info */}
        <div className="flex items-center gap-4">
          <Link href="/superadmin/telemetria" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center font-black text-white text-xs tracking-wider shadow">
              HQ
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-sm tracking-tight text-slate-900 dark:text-white">
                  SEVALOR Superadmin
                </span>
                <span className="text-[9px] font-mono uppercase bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 px-1 py-0.5 rounded border border-emerald-300 dark:border-emerald-700 font-bold">
                  SaaS SRE
                </span>
              </div>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-mono hidden sm:block">
                Hetzner CPX21 • Nuremberg DC14
              </p>
            </div>
          </Link>

          {/* Navegació de pestanyes de Superadmin */}
          <nav className="flex items-center gap-1 ml-4 border-l border-slate-200 dark:border-slate-800 pl-4">
            {navLinks.map((link) => {
              const Icon = link.icon;
              const isActive = pathname.startsWith(link.href);

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition-all ${
                    isActive
                      ? "bg-emerald-600 text-white font-bold shadow"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-800"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{link.label}</span>
                  <span className="text-[9px] text-emerald-100 dark:text-emerald-200/80 hidden md:inline">
                    ({link.spec})
                  </span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Dreta: IP Allowlist, 2FA, Theme */}
        <div className="flex items-center gap-3">
          {/* IP Allowlist (Spec 022 RF-18) */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-[11px] font-mono">
            <Radio className="w-3 h-3 text-emerald-500 animate-pulse" />
            <span className="text-slate-500 dark:text-slate-400">IP Allowlist:</span>
            <span className="text-emerald-600 dark:text-emerald-400 font-bold">185.12.x.x (Zero-Trust)</span>
          </div>

          {/* 2FA Enforced (Spec 022 RF-19) */}
          <div className="hidden md:flex items-center gap-1 px-2 py-1 rounded bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/60 dark:border-emerald-800 dark:text-emerald-300 border text-[11px] font-mono">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>2FA TOTP Actiu</span>
          </div>

          {/* Enllaç a Oficina / Gestio */}
          <Link
            href="/gestio/mapa"
            className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white px-2 py-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <ExternalLink className="w-3.5 h-3.5 text-blue-500" />
            <span className="hidden sm:inline">Oficina Tècnica</span>
          </Link>

          {/* Commutador Mode Clar / Fosc */}
          <button
            onClick={toggleTheme}
            className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300 transition-colors"
            title="Commutar Tema Clar / Fosc"
          >
            {isDark ? <Sun className="w-4 h-4 text-amber-500" /> : <Moon className="w-4 h-4 text-blue-500" />}
          </button>
        </div>
      </header>

      {/* Contingut principal */}
      <main className="flex-1 flex flex-col">{children}</main>
    </div>
  );
}
