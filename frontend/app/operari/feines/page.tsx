'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

interface Feina {
  id: string
  codi: string
  titol: string
  estat: string
  adreca?: string
  data_planificacio?: string
  client?: {
    id: string
    rao_social: string
  }
}

export default function PWAFeines() {
  const router = useRouter()
  const [feines, setFeines] = useState<Feina[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const token = localStorage.getItem('operari_token')
    if (!token) {
      router.push('/operari/login')
      return
    }
    
    fetchFeines(token)
  }, [router])

  const fetchFeines = async (token: string) => {
    try {
      const res = await fetch('/api/v1/operari/feines', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      if (!res.ok) {
        if (res.status === 401) {
          localStorage.removeItem('operari_token')
          router.push('/operari/login')
          return
        }
        throw new Error('Error carregant feines')
      }
      const data = await res.json()
      setFeines(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 pb-24">
      <h1 className="text-2xl font-black text-white mb-6 tracking-tight">Les meves feines</h1>
      
      {error && (
        <div className="bg-red-900/30 text-red-400 p-4 rounded-xl mb-4 border border-red-800/50">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <span className="material-symbols-outlined animate-spin text-blue-500 text-4xl">refresh</span>
        </div>
      ) : feines.length === 0 ? (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-8 text-center text-slate-400">
          <span className="material-symbols-outlined text-5xl mb-3 opacity-50">done_all</span>
          <p className="font-medium">No tens feines pendents avui.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {feines.map(feina => (
            <Link href={`/operari/feines/${feina.id}`} key={feina.id} className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg relative overflow-hidden block active:bg-slate-800 transition-colors">
              <div className={`absolute top-0 left-0 w-1.5 h-full ${feina.estat === 'EN_CURS' ? 'bg-amber-500' : 'bg-blue-500'}`}></div>
              
              <div className="flex justify-between items-start mb-3 pl-2">
                <span className="text-blue-400 font-bold text-xs uppercase tracking-wider">{feina.codi}</span>
                <span className={`text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wider ${
                  feina.estat === 'EN_CURS' ? 'bg-amber-900/40 text-amber-500' : 'bg-blue-900/40 text-blue-400'
                }`}>
                  {feina.estat.replace('_', ' ')}
                </span>
              </div>

              <h3 className="text-lg font-bold text-white mb-2 pl-2 pr-4">{feina.titol}</h3>
              
              <div className="space-y-2 mt-4 pl-2">
                {feina.client && (
                  <div className="flex items-center gap-2 text-slate-400 text-sm">
                    <span className="material-symbols-outlined text-[18px] text-slate-500">business</span>
                    <span className="truncate">{feina.client.rao_social}</span>
                  </div>
                )}
                {feina.adreca && (
                  <div className="flex items-start gap-2 text-slate-400 text-sm">
                    <span className="material-symbols-outlined text-[18px] text-slate-500 mt-0.5">location_on</span>
                    <span>{feina.adreca}</span>
                  </div>
                )}
                {feina.data_planificacio && (
                  <div className="flex items-center gap-2 text-slate-400 text-sm">
                    <span className="material-symbols-outlined text-[18px] text-slate-500">calendar_today</span>
                    <span>{new Date(feina.data_planificacio).toLocaleDateString('ca-ES')}</span>
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
