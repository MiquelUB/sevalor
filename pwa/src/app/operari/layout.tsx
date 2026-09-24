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
} from "lucide-react";
import CopilotWidget from "@/components/CopilotWidget";

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
    // Sincronitzar amb el tema del sistema o localStorage
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
    { label: "Feines", href: "/operari/feines", icon: Briefcase },
    { label: "Material", href: "/operari/material", icon: Package },
    { label: "Vehicles", href: "/operari/vehicles", icon: Truck },
    { label: "Plànols", href: "/operari/planols", icon: Layers },
    { label: "Tiquets", href: "/operari/tiquets", icon: Receipt },
    { label: "SOS", href: "/operari/incidencies", icon: AlertTriangle, isSos: true },
  ];

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 select-none font-sans transition-colors duration-200">
      <main className="max-w-md mx-auto min-h-screen bg-white dark:bg-slate-900 shadow-2xl flex flex-col relative pb-16">
        {/* Barra ràpida de campanya acústica i selector de tema (Exclòs a login) */}
        {!isLoginPage && (
          <div className="bg-slate-800 dark:bg-slate-950 text-slate-300 text-[11px] px-4 py-1.5 flex items-center justify-between border-b border-slate-700/60 z-30">
            <div className="flex items-center gap-2">
              <button
                onClick={handleCampanaClick}
                className={`p-1 rounded-md flex items-center gap-1 transition-colors ${
                  campanaActiva
                    ? "bg-rose-600 text-white animate-pulse"
                    : "hover:bg-slate-700 text-slate-400"
                }`}
                title="Campana d'Incidències Acústica (Spec 013 RF-04 / Spec 016 RF-01)"
              >
                <Bell className="w-3.5 h-3.5" />
                <Volume2 className="w-3 h-3" />
              </button>
              <span className="text-[10px] font-mono tracking-tight text-slate-400">
                SEVALOR PWA v4.0
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={toggleTheme}
                className="p-1 rounded-md bg-slate-700/50 hover:bg-slate-700 text-slate-300 transition-colors flex items-center gap-1"
                title="Commutar Mode Clar / Fosc"
              >
                {isDark ? (
                  <>
                    <Sun className="w-3.5 h-3.5 text-amber-400" />
                    <span className="text-[10px]">Clar</span>
                  </>
                ) : (
                  <>
                    <Moon className="w-3.5 h-3.5 text-blue-300" />
                    <span className="text-[10px]">Fosc</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Contingut de la Pàgina */}
        <div className="flex-1 flex flex-col">{children}</div>

        {/* Barra de navegació inferior persistent (Bottom Bar) per a mobilitat rústica */}
        {!isLoginPage && (
          <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-md bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 py-1.5 px-2 flex items-center justify-around z-40 shadow-lg backdrop-blur-md">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex flex-col items-center justify-center py-1 px-2 rounded-xl transition-all ${
                    item.isSos
                      ? isActive
                        ? "text-rose-600 font-extrabold"
                        : "text-rose-500 hover:text-rose-600"
                      : isActive
                      ? "text-emerald-600 dark:text-emerald-400 font-bold scale-105"
                      : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  <Icon
                    className={`w-5 h-5 ${
                      item.isSos && "animate-pulse"
                    } ${isActive ? "stroke-[2.5]" : "stroke-[1.75]"}`}
                  />
                  <span className="text-[10px] mt-0.5 tracking-tight">
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
