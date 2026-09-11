'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'

interface LiniaPicking {
  id: string
  article_id: string
  article_nom: string
  quantitat_prevista: number
  quantitat_carregada_pick_in: number
}

interface FeinaDetail {
  id: string
  codi: string
  titol: string
  descripcio?: string
  adreca?: string
  client?: { rao_social: string }
  vehicle?: { matricula: string, model: string }
  linies_picking: LiniaPicking[]
}

export default function FeinaDetailPage() {
  const { id } = useParams()
  const router = useRouter()
  const [feina, setFeina] = useState<FeinaDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [savingLinia, setSavingLinia] = useState<string | null>(null)
  
  // Modal Alerta Faltant
  const [showAlerta, setShowAlerta] = useState(false)
  const [alertaText, setAlertaText] = useState('')
  const [sendingAlerta, setSendingAlerta] = useState(false)

  useEffect(() => {
    fetchFeina()
  }, [])

  const fetchFeina = async () => {
    try {
      const token = localStorage.getItem('operari_token')
      if (!token) {
        router.push('/operari/login')
        return
      }
      const res = await fetch(`/api/v1/operari/feines/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Error carregant feina')
      const json = await res.json()
      setFeina(json)
    } catch (err) {
      console.error(err)
      alert('Error de connexió')
    } finally {
      setLoading(false)
    }
  }

  const updateLinia = async (liniaId: string, val: number) => {
    try {
      setSavingLinia(liniaId)
      const token = localStorage.getItem('operari_token')
      
      const res = await fetch(`/api/v1/operari/picking/linies/${liniaId}`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ quantitat_carregada_pick_in: val })
      })
      
      if (!res.ok) throw new Error('No guardat')
      
      setFeina(prev => {
        if (!prev) return prev
        return {
          ...prev,
          linies_picking: prev.linies_picking.map(l => l.id === liniaId ? { ...l, quantitat_carregada_pick_in: val } : l)
        }
      })
    } catch (err) {
      alert('Error al guardar línia')
    } finally {
      setSavingLinia(null)
    }
  }

  const handleSendAlerta = async () => {
    if (!alertaText.trim()) return
    setSendingAlerta(true)
    try {
      const token = localStorage.getItem('operari_token')
      
      const res = await fetch(`/api/v1/operari/incidencies`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          ordre_treball_id: id,
          ambit: 'MATERIAL',
          estat: 'VERMELL',
          text_observacions: `FALTA MATERIAL: ${alertaText}`
        })
      })
      
      if (!res.ok) throw new Error('Error al enviar alerta')
      
      alert('Alerta enviada al supervisor')
      setShowAlerta(false)
      setAlertaText('')
    } catch (err) {
      alert('Error de connexió')
    } finally {
      setSendingAlerta(false)
    }
  }

  if (loading) return <div className="p-8 text-center text-slate-400">Carregant feina...</div>
  if (!feina) return <div className="p-8 text-center text-red-400">No s'ha trobat la feina</div>

  return (
    <div className="pb-24">
      {/* Header Back */}
      <div className="bg-slate-900 border-b border-slate-800 p-4 sticky top-0 z-10 flex items-center gap-3">
        <Link href="/operari/feines" className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-white">
          <span className="material-symbols-outlined">arrow_back</span>
        </Link>
        <div>
          <p className="text-xs text-blue-400 font-bold">{feina.codi}</p>
          <h1 className="text-lg font-bold text-white line-clamp-1">{feina.titol}</h1>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Detalls de la Feina */}
        <section className="bg-slate-900 rounded-xl p-4 border border-slate-800 shadow-lg">
          <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">Informació Operativa</h2>
          
          {feina.client && (
            <div className="mb-3">
              <span className="block text-xs text-slate-500 mb-1">Client</span>
              <span className="text-white font-medium">{feina.client.rao_social}</span>
            </div>
          )}
          
          {feina.adreca && (
            <div className="mb-3">
              <span className="block text-xs text-slate-500 mb-1">Destí</span>
              <div className="flex gap-2 items-start">
                <span className="material-symbols-outlined text-[18px] text-blue-400 mt-0.5">location_on</span>
                <span className="text-white">{feina.adreca}</span>
              </div>
            </div>
          )}

          {feina.descripcio && (
            <div className="mb-3">
              <span className="block text-xs text-slate-500 mb-1">Instruccions</span>
              <p className="text-slate-300 text-sm whitespace-pre-wrap">{feina.descripcio}</p>
            </div>
          )}

          {feina.vehicle && (
            <div className="mt-4 p-3 bg-blue-900/20 rounded-lg border border-blue-900/50 flex items-center gap-3">
              <span className="material-symbols-outlined text-blue-400 text-2xl">directions_car</span>
              <div>
                <p className="text-xs text-blue-300">Vehicle assignat</p>
                <p className="text-white font-bold">{feina.vehicle.matricula} <span className="font-normal text-slate-400">({feina.vehicle.model})</span></p>
              </div>
            </div>
          )}
          
          {/* Placeholder Planol */}
          <div className="mt-4 p-3 bg-slate-800 rounded-lg flex items-center justify-between opacity-50">
             <div className="flex items-center gap-2">
               <span className="material-symbols-outlined text-slate-400">map</span>
               <span className="text-sm text-slate-300">Plànols adjunts (Pròximament)</span>
             </div>
             <span className="material-symbols-outlined text-slate-500">chevron_right</span>
          </div>
        </section>

        {/* Picking de Material */}
        <section className="bg-slate-900 rounded-xl p-4 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
            <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Picking de Material</h2>
          </div>

          {feina.linies_picking.length === 0 ? (
            <div className="text-center p-6 bg-slate-800/50 rounded-lg">
              <span className="material-symbols-outlined text-4xl text-slate-600 mb-2">inventory_2</span>
              <p className="text-slate-400 text-sm">Cap material assignat prèviament per enginyeria.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {feina.linies_picking.map(linia => (
                <div key={linia.id} className="bg-slate-800 p-3 rounded-lg flex flex-col gap-2">
                  <div className="flex justify-between items-start">
                    <span className="text-white font-medium text-sm pr-4">{linia.article_nom}</span>
                    <span className="text-xs text-slate-400 whitespace-nowrap bg-slate-900 px-2 py-1 rounded">Previst: {linia.quantitat_prevista}</span>
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-slate-400">Quantitat utilitzada:</span>
                    <div className="flex items-center gap-3">
                      <button 
                        onClick={() => updateLinia(linia.id, Math.max(0, linia.quantitat_carregada_pick_in - 1))}
                        disabled={savingLinia === linia.id}
                        className="w-8 h-8 bg-slate-700 rounded-full flex items-center justify-center text-white active:bg-slate-600 disabled:opacity-50"
                      >-</button>
                      <span className="text-white font-bold w-6 text-center">{linia.quantitat_carregada_pick_in}</span>
                      <button 
                        onClick={() => updateLinia(linia.id, linia.quantitat_carregada_pick_in + 1)}
                        disabled={savingLinia === linia.id}
                        className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white active:bg-blue-500 disabled:opacity-50"
                      >+</button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Botó Alerta de Faltant */}
          <button 
            onClick={() => setShowAlerta(true)}
            className="w-full mt-5 py-3 bg-amber-900/30 text-amber-500 border border-amber-900/50 rounded-xl font-medium flex items-center justify-center gap-2 active:bg-amber-900/50"
          >
            <span className="material-symbols-outlined text-[20px]">warning</span>
            Alerta de Material Faltant
          </button>
        </section>
      </div>

      {/* Modal Alerta Faltant */}
      {showAlerta && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 rounded-2xl w-full max-w-sm overflow-hidden border border-slate-700 shadow-2xl">
            <div className="p-5 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-amber-500">warning</span>
                Material no assignat
              </h3>
              <p className="text-slate-400 text-sm mt-1">Sol·licita al supervisor el material o eina que no tens a la llista d'aquesta feina.</p>
            </div>
            <div className="p-5">
              <textarea
                value={alertaText}
                onChange={e => setAlertaText(e.target.value)}
                placeholder="Ex: Falten 3 tubs de 25mm o Eina de tallar trencada..."
                className="w-full h-32 bg-slate-800 border border-slate-700 rounded-xl p-3 text-white focus:outline-none focus:border-amber-500 resize-none text-sm"
              ></textarea>
            </div>
            <div className="p-3 bg-slate-800/50 flex gap-3">
              <button 
                onClick={() => setShowAlerta(false)}
                className="flex-1 py-3 text-slate-300 font-medium active:bg-slate-800 rounded-xl"
              >
                Cancel·lar
              </button>
              <button 
                onClick={handleSendAlerta}
                disabled={sendingAlerta || !alertaText.trim()}
                className="flex-1 py-3 bg-amber-600 text-white font-bold rounded-xl active:bg-amber-500 disabled:opacity-50"
              >
                {sendingAlerta ? 'Enviant...' : 'Enviar Alerta'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
