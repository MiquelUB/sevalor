'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  const navItems = [
    { name: 'Dashboard', href: '/dashboard', icon: 'dashboard' },
    { name: 'Mapa GIS', href: '/dashboard/mapa', icon: 'public' },
    { name: 'Feines', href: '/dashboard/feines', icon: 'work' },
    { name: 'Agenda', href: '/dashboard/agenda', icon: 'calendar_month' },
    { name: 'Pressupostos', href: '/dashboard/pressupostos', icon: 'request_quote' },
    { name: 'Clients', href: '/dashboard/clients', icon: 'group' },
    { name: 'Operaris', href: '/dashboard/operaris', icon: 'engineering' },
    { name: 'Proveïdors', href: '/dashboard/proveidors', icon: 'local_shipping' },
    { name: 'Flota', href: '/dashboard/flota', icon: 'directions_car' },
    { name: 'Magatzem', href: '/dashboard/magatzem', icon: 'inventory_2' },
    { name: 'Plànols', href: '/dashboard/planols', icon: 'map' },
  ]

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100 font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col">
        <div className="p-6">
          <h1 className="text-2xl font-bold text-blue-500 tracking-tight">CampoPro</h1>
          <p className="text-xs text-slate-400 uppercase tracking-widest mt-1">Portal d'Oficina</p>
        </div>
        <nav className="flex-1 px-4 space-y-2 mt-4">
          {navItems.map((item) => {
            const active = pathname === item.href
            return (
              <Link 
                key={item.name} 
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${
                  active 
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30' 
                    : 'text-slate-400 hover:bg-slate-700/50 hover:text-slate-200'
                }`}
              >
                <span className="material-symbols-outlined text-lg">{item.icon}</span>
                <span className="font-medium text-sm">{item.name}</span>
              </Link>
            )
          })}
        </nav>
        <div className="p-4 border-t border-slate-700">
          <button className="flex items-center gap-2 text-slate-400 hover:text-red-400 transition-colors w-full px-4 py-2 text-sm font-medium">
            <span className="material-symbols-outlined text-lg">logout</span>
            Tancar Sessió
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Top Header */}
        <header className="h-16 bg-slate-800 border-b border-slate-700 flex items-center justify-between px-8">
          <h2 className="text-lg font-semibold text-slate-200">
            {navItems.find(i => i.href === pathname)?.name || 'Panell de Control'}
          </h2>
          <div className="flex items-center gap-4">
            <span className="material-symbols-outlined text-slate-400 cursor-pointer hover:text-white transition">notifications</span>
            <div className="h-8 w-8 bg-blue-600 rounded-full flex items-center justify-center text-sm font-bold border border-blue-400">
              AD
            </div>
          </div>
        </header>
        
        {/* Scrollable Content */}
        <div className="flex-1 overflow-auto p-8 bg-slate-900">
          {children}
        </div>
      </main>
    </div>
  )
}
