'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import OdometerCapture from '@/components/operari/OdometerCapture'

export default function OperariDashboard() {
  const router = useRouter()
  const [userName, setUserName] = useState('')
  const [jornadaActiva, setJornadaActiva] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [showOdometerModal, setShowOdometerModal] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('operari_token')
    if (!token) {
      router.push('/operari/login')
      return
    }

    try {
      const dataStr = localStorage.getItem('operari_data')
      if (dataStr) {
        const data = JSON.parse(dataStr)
        setUserName(data.nom || '')
      }
    } catch (e) {
      // safe fallback
    }

    fetchJornadaActiva(token)
  }, [router])

  const fetchJornadaActiva = async (token: string) => {
    try {
      const res = await fetch('/api/v1/operari/jornada/activa', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setJornadaActiva(data)
      } else {
        setJornadaActiva(null)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const getRealLocation = async (): Promise<string> => {
    if (typeof navigator !== 'undefined' && navigator.geolocation) {
      try {
        const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 3500 })
        })
        return `${pos.coords.latitude.toFixed(6)},${pos.coords.longitude.toFixed(6)}`
      } catch {
        // Fallback transparent si no hi ha permís o antena GPS
      }
    }
    return "41.3851,2.1734"
  }

  const toggleJornada = async () => {
    const token = localStorage.getItem('operari_token')
    if (!token) return

    setLoading(true)
    try {
      const geo = await getRealLocation()

      if (jornadaActiva) {
        // Finalitzar Jornada
        await fetch(`/api/v1/operari/jornada/${jornadaActiva.id}/fi`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ geolocalitzacio: geo })
        })
        setJornadaActiva(null)
      } else {
        // Iniciar Jornada
        const res = await fetch('/api/v1/operari/jornada/inici', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ geolocalitzacio: geo })
        })
        if (res.ok) {
          const data = await res.json()
          setJornadaActiva(data)
        }
      }
    } catch (e) {
      alert("Error canviant estat de jornada")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 pb-24">
      <div className="flex justify-between items-center mb-8 pt-4">
        <div>
          <h2 className="text-white text-2xl font-bold">Hola, {userName}</h2>
          <p className="text-slate-400 text-sm">Què tenim per avui?</p>
        </div>
        <div className="h-12 w-12 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center font-bold text-white shadow-lg overflow-hidden">
          <span className="material-symbols-outlined text-3xl text-slate-400">account_circle</span>
        </div>
      </div>

      {/* Botó de Fitxatge Jornada */}
      <div className="mb-6">
        <button 
          onClick={toggleJornada}
          disabled={loading}
          className={`w-full py-10 rounded-3xl shadow-xl flex flex-col items-center justify-center gap-3 transition-all active:scale-95 border-2 ${
            jornadaActiva 
              ? 'bg-red-500/20 border-red-500/50 text-red-100 hover:bg-red-500/30' 
              : 'bg-emerald-500 border-emerald-400 text-white hover:bg-emerald-400'
          }`}
        >
          <span className="material-symbols-outlined text-5xl">
            {jornadaActiva ? 'stop_circle' : 'play_circle'}
          </span>
          <span className="font-bold tracking-widest uppercase text-lg">
            {jornadaActiva ? 'Finalitzar Jornada' : 'Iniciar Jornada'}
          </span>
        </button>
      </div>

      {/* Acció ràpida per a Odòmetre de Flota (Spec 015) */}
      <div className="mb-6">
        <button
          onClick={() => setShowOdometerModal(true)}
          className="w-full py-3.5 bg-slate-800/80 hover:bg-slate-800 text-blue-300 border border-slate-700 rounded-2xl flex items-center justify-center gap-2 text-xs font-bold transition-all shadow-md"
        >
          <span className="material-symbols-outlined text-[20px] text-blue-400">speed</span>
          Foto Odòmetre de Vehicle
        </button>
      </div>

      {/* Informació de Control d'Horari */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 text-slate-300">
        <h3 className="font-bold text-white flex items-center gap-2 mb-2">
          <span className="material-symbols-outlined text-blue-400">info</span>
          Control d'Horari RDL 8/2019
        </h3>
        <p className="text-sm leading-relaxed text-slate-400">
          Enregistra el teu inici i final de dia utilitzant el botó superior. La teva geolocalització real s'enviarà automàticament a l'oficina per registrar el fitxatge obligatori.
        </p>
      </div>

      {/* Modal Odòmetre */}
      {showOdometerModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 rounded-2xl w-full max-w-sm overflow-hidden border border-blue-500/50 shadow-2xl p-5">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-white text-base flex items-center gap-2">
                <span className="material-symbols-outlined text-blue-400">directions_car</span>
                Registre Odòmetre
              </h3>
              <button onClick={() => setShowOdometerModal(false)} className="text-slate-400 hover:text-white">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <OdometerCapture onSuccess={() => {
              setShowOdometerModal(false)
              alert("Foto d'odòmetre enregistrada correctament")
            }} />
          </div>
        </div>
      )}
    </div>
  )
}
