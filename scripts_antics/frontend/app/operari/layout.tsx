'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { useSyncQueue } from '@/hooks/useSyncQueue'

export default function OperariLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isLoginPage = pathname === '/operari/login'
  const [showSosModal, setShowSosModal] = useState(false)

  // Activa la cua de sincronització asíncrona per a tota l'App d'Operari
  useSyncQueue()

  return (
    <div className="bg-black min-h-screen flex justify-center text-slate-100 font-sans">
      <div className="w-full max-w-md bg-slate-900 min-h-screen relative shadow-2xl flex flex-col overflow-hidden">
        
        {/* Top Header persistent (Spec 016 RF-01, RF-06) */}
        {!isLoginPage && (
          <header className="bg-slate-900 border-b border-slate-800 px-4 py-3 flex items-center justify-between z-40 sticky top-0">
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-blue-400 tracking-wider text-sm">SEVALOR</span>
              <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded font-mono">PWA</span>
            </div>

            <div className="flex items-center gap-3">
              {/* Botó SOS Emergència Parpellejant (Spec 016 RF-06, RF-08) */}
              <button 
                onClick={() => setShowSosModal(true)}
                className="bg-red-600 hover:bg-red-500 text-white text-xs font-black px-2.5 py-1.5 rounded-lg flex items-center gap-1 animate-pulse shadow-lg shadow-red-900/40"
              >
                <span className="material-symbols-outlined text-[16px]">emergency</span>
                SOS 112
              </button>

              {/* Campana d'Incidències (Spec 016 RF-01, RF-02) */}
              <Link 
                href="/operari/incidencies" 
                className="relative p-1.5 text-slate-300 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
                title="Bústia d'Incidències"
              >
                <span className="material-symbols-outlined text-2xl">notifications</span>
              </Link>
            </div>
          </header>
        )}

        {/* Main Content Area (Scrollable) */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden pb-16">
          {children}
        </main>

        {/* Modal Protocol SOS 112 (Spec 016 RF-07, RF-08) */}
        {showSosModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="bg-slate-900 rounded-2xl w-full max-w-sm overflow-hidden border-2 border-red-500 shadow-2xl p-6 text-center">
              <div className="w-16 h-16 bg-red-600/20 text-red-500 rounded-full flex items-center justify-center mx-auto mb-4 border border-red-500/50">
                <span className="material-symbols-outlined text-4xl">sos</span>
              </div>
              <h3 className="text-xl font-black text-white uppercase tracking-wider mb-2">Protocol d'Emergència</h3>
              <p className="text-slate-300 text-xs mb-6 leading-relaxed">
                Per normativa de seguretat laboral (Spec 016 RF-08), el sistema no realitza trucades desateses. Prem el botó inferior per obrir el marcador telefònic oficial del 112.
              </p>
              
              <div className="flex flex-col gap-3">
                <a 
                  href="tel:112"
                  className="w-full py-4 bg-red-600 hover:bg-red-500 text-white font-extrabold rounded-xl text-base flex items-center justify-center gap-2 shadow-lg shadow-red-900/50"
                  onClick={() => setShowSosModal(false)}
                >
                  <span className="material-symbols-outlined">call</span>
                  Trucar al 112 Ara
                </a>
                <button 
                  onClick={() => setShowSosModal(false)}
                  className="w-full py-3 bg-slate-800 text-slate-400 font-semibold rounded-xl text-xs hover:text-white"
                >
                  Cancel·lar (Falsa Alarma)
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Bottom Navigation PWA */}
        {!isLoginPage && (
          <nav className="absolute bottom-0 w-full h-16 bg-slate-800 border-t border-slate-700 flex justify-around items-center px-2 z-40">
            <Link href="/operari" className={`flex flex-col items-center justify-center w-1/4 h-full ${pathname === '/operari' ? 'text-blue-500' : 'text-slate-400 hover:text-slate-200'}`}>
              <span className="material-symbols-outlined text-2xl">home</span>
              <span className="text-[10px] font-medium mt-0.5">Inici</span>
            </Link>
            <Link href="/operari/feines" className={`flex flex-col items-center justify-center w-1/4 h-full ${pathname.startsWith('/operari/feines') ? 'text-blue-500' : 'text-slate-400 hover:text-slate-200'}`}>
              <span className="material-symbols-outlined text-2xl">work</span>
              <span className="text-[10px] font-medium mt-0.5">Feines</span>
            </Link>
            <Link href="/operari/incidencies" className={`flex flex-col items-center justify-center w-1/4 h-full ${pathname.startsWith('/operari/incidencies') ? 'text-blue-500' : 'text-slate-400 hover:text-slate-200'}`}>
              <span className="material-symbols-outlined text-2xl">warning</span>
              <span className="text-[10px] font-medium mt-0.5">Incidències</span>
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
