'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import SensoryInputForm from '@/components/operari/SensoryInputForm'

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
  estat: string
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
  
  // Fotos de qualitat (Spec 013 RF-13)
  const [fotosStatus, setFotosStatus] = useState<{ inicial: boolean, intermedia: boolean, final: boolean }>({
    inicial: false,
    intermedia: false,
    final: false
  })

  // Modal Alerta Faltant
  const [showAlerta, setShowAlerta] = useState(false)
  const [alertaText, setAlertaText] = useState('')
  const [sendingAlerta, setSendingAlerta] = useState(false)

  // Modal Incidència Sensorial (Spec 013 RF-20)
  const [showIncidenciaModal, setShowIncidenciaModal] = useState(false)

  // Estats d'acció
  const [trajecteIniciat, setTrajecteIniciat] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    fetchFeina()
    fetchFotosStatus()
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

  const fetchFotosStatus = async () => {
    try {
      const token = localStorage.getItem('operari_token')
      if (!token) return
      const res = await fetch(`/api/v1/operari/feines/${id}/fotos`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const json = await res.json()
        if (json.fotos) {
          setFotosStatus(json.fotos)
        }
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handlePujarFoto = async (tipus: 'INICIAL' | 'INTERMEDIA' | 'FINAL') => {
    try {
      setActionLoading(true)
      const token = localStorage.getItem('operari_token')
      const form = new FormData()
      form.append('tipus', tipus)
      
      const res = await fetch(`/api/v1/operari/feines/${id}/fotos`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form
      })
      if (!res.ok) throw new Error('Error pujant evidència fotogràfica')
      await fetchFotosStatus()
      alert(`Foto ${tipus} registrada correctament`)
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleIniciarTrajecte = async () => {
    try {
      setActionLoading(true)
      const token = localStorage.getItem('operari_token')
      const res = await fetch(`/api/v1/operari/feines/${id}/iniciar-trajecte`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        setTrajecteIniciat(true)
        alert('Trajecte iniciat: vehicle en trànsit i ETA enviat al client')
      }
    } catch (e) {
      alert('Error en iniciar trajecte')
    } finally {
      setActionLoading(false)
    }
  }

  const handleComencarFeina = async () => {
    try {
      setActionLoading(true)
      const token = localStorage.getItem('operari_token')
      
      // Geolocalització real del navegador (Spec 013 RF-12.1)
      let lat: number | undefined
      let lng: number | undefined
      if (navigator.geolocation) {
        try {
          const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 4000 })
          })
          lat = pos.coords.latitude
          lng = pos.coords.longitude
        } catch {
          // Si no hi ha GPS directe, continuem
        }
      }

      const res = await fetch(`/api/v1/operari/feines/${id}/comencar`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}` 
        },
        body: JSON.stringify({ lat, lng, desviacio_justificada: false })
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Error iniciant feina')
      }

      await fetchFeina()
      alert('Feina iniciada: cronòmetre activat')
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleFinalitzarFeina = async () => {
    const totes = fotosStatus.inicial && fotosStatus.intermedia && fotosStatus.final
    if (!totes) {
      alert('Protocol de qualitat incomplet: Has de capturar les 3 fotografies obligatòries (Inicial, Intermèdia, Final) abans de finalitzar la feina.')
      return
    }

    try {
      setActionLoading(true)
      const token = localStorage.getItem('operari_token')
      const res = await fetch(`/api/v1/operari/feines/${id}/finalitzar`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Error en finalitzar')
      }
      alert('Feina finalitzada satisfactòriament!')
      router.push('/operari/feines')
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading(false)
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

  const protocolFotosComplet = fotosStatus.inicial && fotosStatus.intermedia && fotosStatus.final

  return (
    <div className="pb-28">
      {/* Header Back */}
      <div className="bg-slate-900 border-b border-slate-800 p-4 sticky top-0 z-10 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/operari/feines" className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-white">
            <span className="material-symbols-outlined">arrow_back</span>
          </Link>
          <div>
            <p className="text-xs text-blue-400 font-bold">{feina.codi}</p>
            <h1 className="text-lg font-bold text-white line-clamp-1">{feina.titol}</h1>
          </div>
        </div>

        <span className={`text-[10px] font-black px-2.5 py-1 rounded-full uppercase tracking-wider ${
          feina.estat === 'EN_CURS' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' :
          feina.estat === 'COMPLERT' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' :
          'bg-blue-500/20 text-blue-400 border border-blue-500/40'
        }`}>
          {feina.estat}
        </span>
      </div>

      <div className="p-4 space-y-4">
        {/* Panell de Controls Operatius (Spec 013 RF-11, RF-12, RF-20) */}
        <section className="bg-slate-900 rounded-2xl p-4 border border-slate-800 shadow-xl space-y-3">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800 pb-2">
            Controls Operatius de Camp
          </h2>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={handleIniciarTrajecte}
              disabled={actionLoading || trajecteIniciat}
              className={`py-3 px-2 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                trajecteIniciat 
                  ? 'bg-blue-900/40 text-blue-300 border border-blue-700/50' 
                  : 'bg-blue-600 hover:bg-blue-500 text-white'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">directions_car</span>
              {trajecteIniciat ? 'En Trajecte' : 'Iniciar Trajecte'}
            </button>

            <button
              onClick={handleComencarFeina}
              disabled={actionLoading || feina.estat === 'EN_CURS' || feina.estat === 'COMPLERT'}
              className={`py-3 px-2 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                feina.estat === 'EN_CURS'
                  ? 'bg-emerald-900/40 text-emerald-300 border border-emerald-700/50'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">play_circle</span>
              {feina.estat === 'EN_CURS' ? 'Feina En Curs' : 'Començar Feina'}
            </button>
          </div>

          {/* Botó Incidència Sensorial */}
          <button
            onClick={() => setShowIncidenciaModal(true)}
            className="w-full py-2.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[18px]">warning</span>
            🚨 Notificar Incidència (Veu / Foto)
          </button>
        </section>

        {/* Protocol Obligatori de 3 Fotos (Spec 013 RF-13, RF-14) */}
        <section className="bg-slate-900 rounded-2xl p-4 border border-slate-800 shadow-xl space-y-3">
          <div className="flex justify-between items-center border-b border-slate-800 pb-2">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              Control de Qualitat (3 Fotos)
            </h2>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
              protocolFotosComplet ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
            }`}>
              {protocolFotosComplet ? '3/3 COMPLETAT' : 'PENDENT'}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center">
            <button
              onClick={() => handlePujarFoto('INICIAL')}
              disabled={actionLoading}
              className={`p-3 rounded-xl border flex flex-col items-center gap-1 text-xs font-semibold ${
                fotosStatus.inicial 
                  ? 'bg-emerald-950/40 border-emerald-600/50 text-emerald-300' 
                  : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-500'
              }`}
            >
              <span className="material-symbols-outlined text-xl">
                {fotosStatus.inicial ? 'check_circle' : 'add_a_photo'}
              </span>
              1. Inicial
            </button>

            <button
              onClick={() => handlePujarFoto('INTERMEDIA')}
              disabled={actionLoading}
              className={`p-3 rounded-xl border flex flex-col items-center gap-1 text-xs font-semibold ${
                fotosStatus.intermedia 
                  ? 'bg-emerald-950/40 border-emerald-600/50 text-emerald-300' 
                  : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-500'
              }`}
            >
              <span className="material-symbols-outlined text-xl">
                {fotosStatus.intermedia ? 'check_circle' : 'add_a_photo'}
              </span>
              2. Intermèdia
            </button>

            <button
              onClick={() => handlePujarFoto('FINAL')}
              disabled={actionLoading}
              className={`p-3 rounded-xl border flex flex-col items-center gap-1 text-xs font-semibold ${
                fotosStatus.final 
                  ? 'bg-emerald-950/40 border-emerald-600/50 text-emerald-300' 
                  : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-500'
              }`}
            >
              <span className="material-symbols-outlined text-xl">
                {fotosStatus.final ? 'check_circle' : 'add_a_photo'}
              </span>
              3. Final
            </button>
          </div>

          {/* Botó Finalitzar Feina (Bloquejat si manquen fotos) */}
          <button
            onClick={handleFinalitzarFeina}
            disabled={actionLoading || !protocolFotosComplet || feina.estat === 'COMPLERT'}
            className={`w-full py-3.5 rounded-xl font-black text-sm flex items-center justify-center gap-2 transition-all ${
              protocolFotosComplet && feina.estat !== 'COMPLERT'
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/40'
                : 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed opacity-60'
            }`}
          >
            <span className="material-symbols-outlined">task_alt</span>
            {feina.estat === 'COMPLERT' ? 'Feina Tancada' : 'Finalitzar Feina'}
          </button>
        </section>

        {/* Informació Operativa */}
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
        </section>

        {/* Picking de Material (Spec 013 RF-18: Balanç Pick In - Pick Out) */}
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

      {/* Modal Incidència Sensorial (Spec 013 RF-20) */}
      {showIncidenciaModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 rounded-2xl w-full max-w-sm overflow-hidden border border-amber-500/50 shadow-2xl p-5">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-white text-base flex items-center gap-2">
                <span className="material-symbols-outlined text-amber-500">warning</span>
                Incidència de Tasca
              </h3>
              <button onClick={() => setShowIncidenciaModal(false)} className="text-slate-400 hover:text-white">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <SensoryInputForm onSubmitted={() => setShowIncidenciaModal(false)} />
          </div>
        </div>
      )}

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
