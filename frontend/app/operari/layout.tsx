'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'

export default function OperariLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isLoginPage = pathname === '/operari/login'

  // Si és la pàgina de login, amaguem la Bottom Navigation
  return (
    <div className="bg-black min-h-screen flex justify-center text-slate-100 font-sans">
      <div className="w-full max-w-md bg-slate-900 min-h-screen relative shadow-2xl flex flex-col overflow-hidden">
        
        {/* Main Content Area (Scrollable) */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden pb-16">
          {children}
        </main>

        {/* Bottom Navigation PWA */}
        {!isLoginPage && (
          <nav className="absolute bottom-0 w-full h-16 bg-slate-800 border-t border-slate-700 flex justify-around items-center px-2 z-50">
            <Link href="/operari" className={`flex flex-col items-center justify-center w-1/4 h-full ${pathname === '/operari' ? 'text-blue-500' : 'text-slate-400 hover:text-slate-200'}`}>
              <span className="material-symbols-outlined text-2xl">home</span>
              <span className="text-[10px] font-medium mt-0.5">Inici</span>
            </Link>
            <Link href="/operari/feines" className={`flex flex-col items-center justify-center w-1/4 h-full ${pathname.startsWith('/operari/feines') ? 'text-blue-500' : 'text-slate-400 hover:text-slate-200'}`}>
              <span className="material-symbols-outlined text-2xl">work</span>
              <span className="text-[10px] font-medium mt-0.5">Feines</span>
            </Link>
            <Link href="/operari/material" className={`flex flex-col items-center justify-center w-1/4 h-full ${pathname.startsWith('/operari/material') ? 'text-blue-500' : 'text-slate-400 hover:text-slate-200'}`}>
              <span className="material-symbols-outlined text-2xl">inventory_2</span>
              <span className="text-[10px] font-medium mt-0.5">Material</span>
            </Link>
            <Link href="/operari/perfil" className={`flex flex-col items-center justify-center w-1/4 h-full ${pathname.startsWith('/operari/perfil') ? 'text-blue-500' : 'text-slate-400 hover:text-slate-200'}`}>
              <span className="material-symbols-outlined text-2xl">person</span>
              <span className="text-[10px] font-medium mt-0.5">Perfil</span>
            </Link>
          </nav>
        )}
      </div>
    </div>
  )
}
