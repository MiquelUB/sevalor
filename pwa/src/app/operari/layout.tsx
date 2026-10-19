"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Briefcase,
  Package,
  Truck,
  Layers,
  Receipt,
  AlertTriangle,
  Sun,
  Moon,
  Bell,
  Volume2,
  QrCode,
} from "lucide-react";
import CopilotWidget from "@/components/CopilotWidget";
import NotificationCenter from "@/components/operari/NotificationCenter";

export default function OperariLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const isLoginPage = pathname === "/operari/login";

  // Gestió de Dark / Light Mode (Mandat de la Constitució i el disseny de la PWA)
  const [isDark, setIsDark] = useState<boolean>(false);
  const [campanaActiva, setCampanaActiva] = useState<boolean>(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem("sevalor_theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (savedTheme === "dark" || (!savedTheme && prefersDark)) {
      setIsDark(true);
      document.documentElement.classList.add("dark");
    } else {
      setIsDark(false);
      document.documentElement.classList.remove("dark");
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

  // So acústic de la campana (Spec 013 RF-04 / Spec 016 RF-01)
  const handleCampanaClick = () => {
    setCampanaActiva(!campanaActiva);
    try {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, ctx.currentTime); // 880 Hz
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.4);
    } catch {
      // Ignorar si el navegador bloqueja l'àudio context
    }
  };

  const navItems = [
    { label: "Feines", href: "/operari/feines", icon: Briefcase, materialIcon: "assignment" },
    { label: "Material", href: "/operari/material", icon: Package, materialIcon: "inventory_2" },
    { label: "Vehicles", href: "/operari/vehicles", icon: Truck, materialIcon: "local_shipping" },
    { label: "Plànols", href: "/operari/planols", icon: Layers, materialIcon: "map" },
    { label: "ID/CAE", href: "/operari/identificacio", icon: QrCode, materialIcon: "qr_code_2" },
    { label: "Tiquets", href: "/operari/tiquets", icon: Receipt, materialIcon: "receipt_long" },
    { label: "SOS", href: "/operari/incidencies", icon: AlertTriangle, materialIcon: "report_problem", isSos: true },
  ];

  return (
    <div className="min-h-screen bg-surface-container-low dark:bg-slate-950 text-on-surface dark:text-slate-100 select-none font-sans transition-colors duration-200 antialiased">
      <main className="max-w-md mx-auto min-h-screen bg-surface dark:bg-slate-900 shadow-2xl flex flex-col relative pb-24">
        {/* Top Utility / App Bar Stitch Soft-Industrial (Exclòs a login) */}
        {!isLoginPage && (
          <header className="sticky top-0 z-30 bg-primary text-white px-4 py-2.5 flex items-center justify-between shadow-md border-b border-white/10">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-secondary-container text-white flex items-center justify-center shadow-sm">
                <span className="material-symbols-outlined text-base" style={{ fontVariationSettings: "'FILL' 1" }}>
                  agriculture
                </span>
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-extrabold tracking-tight leading-none text-white">
                  Sevalor
                </span>
                <span className="text-[9px] font-mono tracking-widest uppercase text-on-primary-container leading-none mt-0.5">
                  SEVALOR PWA v4.0
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleCampanaClick}
                className={`p-1.5 rounded-lg flex items-center gap-1 transition-colors ${
                  campanaActiva
                    ? "bg-error text-white animate-pulse shadow-sm"
                    : "bg-white/10 hover:bg-white/20 text-white/80"
                }`}
                title="Campana d'Incidències Acústica (Spec 013 RF-04 / Spec 016 RF-01)"
              >
                <Bell className="w-3.5 h-3.5" />
                <Volume2 className="w-3 h-3" />
              </button>

              <button
                onClick={toggleTheme}
                className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white/90 transition-colors flex items-center gap-1"
                title="Commutar Mode Clar / Fosc"
              >
                {isDark ? (
                  <>
                    <Sun className="w-3.5 h-3.5 text-amber-300" />
                    <span className="text-[10px] font-bold">Clar</span>
                  </>
                ) : (
                  <>
                    <Moon className="w-3.5 h-3.5 text-sky-200" />
                    <span className="text-[10px] font-bold">Fosc</span>
                  </>
                )}
              </button>
            </div>
          </header>
        )}

        {/* Notificacions Offline/Sync */}
        <NotificationCenter />

        {/* Contingut de la Pàgina */}
        <div className="flex-1 flex flex-col">{children}</div>

        {/* Barra de navegació inferior persistent Stitch Mobile Navigation Bar */}
        {!isLoginPage && (
          <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-md h-20 bg-surface-container-lowest/95 dark:bg-slate-900/95 backdrop-blur-md border-t border-outline-variant/25 dark:border-slate-800 px-1.5 pb-safe flex items-center justify-around z-40 shadow-[0_-4px_20px_rgba(2,36,72,0.06)]">
            {navItems.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/operari/feines" && pathname?.startsWith(item.href));

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex flex-col items-center justify-center py-1.5 px-2 rounded-xl transition-all relative ${
                    item.isSos
                      ? isActive
                        ? "text-error font-extrabold scale-105"
                        : "text-error/85 hover:text-error"
                      : isActive
                      ? "text-secondary font-extrabold"
                      : "text-on-surface-variant dark:text-slate-400 hover:text-primary dark:hover:text-slate-200"
                  }`}
                >
                  {isActive && !item.isSos && (
                    <span className="w-1.5 h-1.5 rounded-full bg-secondary-container mb-0.5" />
                  )}
                  <span
                    className={`material-symbols-outlined text-[22px] leading-none ${
                      item.isSos ? "animate-pulse" : ""
                    }`}
                    style={
                      isActive || item.isSos
                        ? { fontVariationSettings: "'FILL' 1" }
                        : undefined
                    }
                  >
                    {item.materialIcon}
                  </span>
                  <span className="text-[9px] font-bold uppercase tracking-tighter mt-1">
                    {item.label}
                  </span>
                </Link>
              );
            })}
          </nav>
        )}
      </main>

      {!isLoginPage && <CopilotWidget isMobile={true} />}
    </div>
  );
}
