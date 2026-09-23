"use client";
import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Building2, Users, LayoutDashboard, Truck, 
  Map, Bell, Settings, LogOut, Menu, X, FileText 
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";

export default function GestioLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();
  const { usuari, logout } = useAuth();

  // Si és la pàgina de login, no mostrem el sidebar
  if (pathname === "/gestio/login") {
    return <>{children}</>;
  }

  const menuItems = [
    { name: "Dashboard", href: "/gestio/mapa", icon: LayoutDashboard },
    { name: "Clients", href: "/gestio/clients", icon: Building2 },
    { name: "Operaris", href: "/gestio/operaris", icon: Users },
    { name: "Flota", href: "/gestio/flota", icon: Truck },
    { name: "Plànols", href: "/gestio/planols", icon: Map },
    { name: "Comptabilitat", href: "/gestio/comptabilitat", icon: FileText },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      {/* Mobile sidebar toggle */}
      <div className="md:hidden absolute top-4 left-4 z-50">
        <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 bg-white dark:bg-slate-900 rounded-md shadow-md text-slate-800 dark:text-white border border-slate-200 dark:border-slate-800">
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Sidebar */}
      <aside className={`
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        transition-transform duration-300 ease-in-out
        absolute md:relative z-40 w-64 h-full bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col md:translate-x-0
      `}>
        <div className="p-6 flex items-center gap-3">
          <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
            <Building2 className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-lg text-slate-900 dark:text-white">Sevalor</span>
        </div>

        <nav className="flex-1 px-4 space-y-1 overflow-y-auto">
          {menuItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link key={item.name} href={item.href} onClick={() => setSidebarOpen(false)}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                  ${isActive 
                    ? "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400" 
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white"}
                `}
              >
                <item.icon className={`w-5 h-5 ${isActive ? "text-emerald-600 dark:text-emerald-400" : ""}`} />
                {item.name}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3 px-3 py-2 mb-2">
            <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-300 font-bold uppercase">
              {usuari?.nom?.[0] || "?"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{usuari?.nom || "Usuari"}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{usuari?.rol}</p>
            </div>
          </div>
          <button onClick={logout} className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors">
            <LogOut className="w-4 h-4" />
            Tancar Sessió
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4 md:p-8">
          {children}
        </div>
      </main>
      
      {/* Backdrop for mobile sidebar */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-30 bg-black/50 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}
    </div>
  );
}
