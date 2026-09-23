"use client";
import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardList, PackageOpen, Truck, Settings } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

export default function OperariLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { usuari } = useAuth();

  // Si és la pàgina de login, no mostrem les tabs
  if (pathname === "/operari/login") {
    return <>{children}</>;
  }

  const tabs = [
    { name: "Feines", href: "/operari/feines", icon: ClipboardList },
    { name: "Material", href: "/operari/material", icon: PackageOpen },
    { name: "Vehicles", href: "/operari/vehicles", icon: Truck },
    { name: "Ajustos", href: "/operari/ajustos", icon: Settings },
  ];

  return (
    <div className="flex flex-col h-screen h-[100dvh] overflow-hidden bg-slate-50 dark:bg-slate-950 pb-[env(safe-area-inset-bottom)]">
      {/* Header Mobile-friendly */}
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 py-3 flex justify-between items-center z-10 shrink-0">
        <h1 className="font-bold text-lg text-slate-900 dark:text-white">Sevalor</h1>
        <div className="flex items-center gap-2">
          {/* Aquí podria anar el Sync Status de la Fase 2 */}
          <div className="text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-2 py-1 rounded-full">
            {usuari?.nom || "Operari"}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto z-0 p-4 relative">
        {children}
      </main>

      {/* Bottom Tabs Navigation */}
      <nav className="bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 shrink-0 z-10">
        <div className="flex justify-around items-center h-16">
          {tabs.map((tab) => {
            const isActive = pathname.startsWith(tab.href);
            return (
              <Link 
                key={tab.name} 
                href={tab.href}
                className="flex flex-col items-center justify-center w-full h-full space-y-1 touch-manipulation active:bg-slate-50 dark:active:bg-slate-800 transition-colors"
              >
                <tab.icon className={`w-6 h-6 ${isActive ? "text-emerald-600 dark:text-emerald-400" : "text-slate-500 dark:text-slate-400"}`} />
                <span className={`text-[10px] font-medium ${isActive ? "text-emerald-600 dark:text-emerald-400" : "text-slate-500 dark:text-slate-400"}`}>
                  {tab.name}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
