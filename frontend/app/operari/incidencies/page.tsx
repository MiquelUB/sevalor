'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import SensoryInputForm from '@/components/operari/SensoryInputForm'

interface IncidenciaItem {
  id: string
  ambit: string
  estat: string
  text_observacions?: string
  audio_path?: string
  foto_path?: string
  created_at?: string
}

export default function IncidenciesPage() {
  const router = useRouter()
  const [incidencies, setIncidencies] = useState<IncidenciaItem[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'ACTIVES' | 'RESOLTES'>('ACTIVES')
  const [showForm, setShowForm] = useState(false)

  useEffect(() => {
    fetchIncidencies()
  }, [])

  const fetchIncidencies = async () => {
    try {
      const token = localStorage.getItem('operari_token')
      if (!token) {
        router.push('/operari/login')
        return
      }

      const res = await fetch('/api/v1/operari/incidencies', {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setIncidencies(data)
      }
    } catch (e) {
      console.error('Error carregant incidències', e)
    } finally {
      setLoading(false)
    }
  }

  const incidenciesFiltrades = incidencies.filter(i => {
    if (tab === 'ACTIVES') return i.estat !== 'VERD' && i.estat !== 'RESOLTA'
    return i.estat === 'VERD' || i.estat === 'RESOLTA'
  })

  return (
    <div className="p-4 space-y-4 pb-20">
      <div className="flex justify-between items-center pt-2">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <span className="material-symbols-outlined text-amber-500">warning</span>
            Bústia d'Incidències
          </h1>
          <p className="text-xs text-slate-400">Canal de comunicació sensorial amb oficina</p>
        </div>

        <button 
          onClick={() => setShowForm(!showForm)}
          className="bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold px-3 py-2 rounded-xl flex items-center gap-1 shadow-lg"
        >
          <span className="material-symbols-outlined text-[18px]">
            {showForm ? 'close' : 'add'}
          </span>
          {showForm ? 'Tancar' : '+ Nova'}
        </button>
      </div>

      {/* Formulari Sensorial desplegable (Àudio 30s + Foto) */}
      {showForm && (
        <div className="bg-slate-900 border border-amber-500/40 rounded-2xl p-4 shadow-xl">
          <SensoryInputForm onSubmitted={() => {
            setShowForm(false)
            fetchIncidencies()
          }} />
        </div>
      )}

      {/* Pestanyes Actives / Resoltes (Spec 016 RF-18) */}
      <div className="flex bg-slate-800 rounded-xl p-1 gap-1">
        <button 
          onClick={() => setTab('ACTIVES')}
          className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${
            tab === 'ACTIVES' ? 'bg-amber-600 text-white shadow' : 'text-slate-400 hover:text-white'
          }`}
        >
          Actives / Obertes
        </button>
        <button 
          onClick={() => setTab('RESOLTES')}
          className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${
            tab === 'RESOLTES' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-white'
          }`}
        >
          Historial Resoltes
        </button>
      </div>

      {/* Llistat d'Incidències */}
      {loading ? (
        <div className="text-center py-10 text-slate-500 text-sm">Carregant incidències...</div>
      ) : incidenciesFiltrades.length === 0 ? (
        /* Empty State Real (Spec 016 RF-04) */
        <div className="text-center py-12 bg-slate-800/40 border border-slate-800 rounded-2xl p-6">
          <span className="material-symbols-outlined text-4xl text-slate-600 mb-2">check_circle</span>
          <p className="text-sm font-semibold text-slate-300">No hi ha incidències registrades avui</p>
          <p className="text-xs text-slate-500 mt-1">Tot el servei opera amb normalitat tècnica.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {incidenciesFiltrades.map(inci => (
            <div key={inci.id} className="bg-slate-800 border border-slate-700/60 rounded-xl p-4 flex flex-col gap-2">
              <div className="flex justify-between items-start">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase bg-slate-900 text-amber-400">
                  {inci.ambit}
                </span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                  inci.estat === 'VERMELL' ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'
                }`}>
                  {inci.estat}
                </span>
              </div>

              {inci.text_observacions && (
                <p className="text-xs text-slate-200 mt-1">{inci.text_observacions}</p>
              )}

              <div className="flex items-center gap-3 mt-2 pt-2 border-t border-slate-700/50 text-[11px] text-slate-400">
                {inci.audio_path && (
                  <span className="flex items-center gap-1 text-blue-400">
                    <span className="material-symbols-outlined text-[14px]">mic</span> Àudio gravat
                  </span>
                )}
                {inci.foto_path && (
                  <span className="flex items-center gap-1 text-emerald-400">
                    <span className="material-symbols-outlined text-[14px]">photo_camera</span> Foto pericial
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
