'use client'

import { useState, useEffect } from 'react'

interface Client { id: string; rao_social: string }
interface Operari { id: string; nom: string; cognoms: string }
interface Vehicle { id: string; matricula: string; model: string }

interface Feina {
  id: string
  codi: string
  titol: string
  adreca: string
  data_planificacio: string
  estat: string
}

export default function FeinesPage() {
  const [feines, setFeines] = useState<Feina[]>([])
  
  // Dades relacionals per al Select
  const [clients, setClients] = useState<Client[]>([])
  const [operaris, setOperaris] = useState<Operari[]>([])
  const [vehicles, setVehicles] = useState<Vehicle[]>([])

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [newCodi, setNewCodi] = useState('')
  const [newTitol, setNewTitol] = useState('')
  const [newAdreca, setNewAdreca] = useState('')
  const [newData, setNewData] = useState('')
  const [newClient, setNewClient] = useState('')
  const [newOperari, setNewOperari] = useState('')
  const [newVehicle, setNewVehicle] = useState('')

  const tenant = process.env.NEXT_PUBLIC_TENANT_ID || ''

  const fetchData = async () => {
    try {
      // Carregar paral·lelament les entitats
      const [resFeines, resClients, resOperaris, resVehicles] = await Promise.all([
        fetch('/api/v1/gestio/feines', { headers: { 'X-Empresa-ID': tenant } }),
        fetch('/api/v1/gestio/clients', { headers: { 'X-Empresa-ID': tenant } }),
        fetch('/api/v1/gestio/operaris', { headers: { 'X-Empresa-ID': tenant } }),
        fetch('/api/v1/gestio/flota', { headers: { 'X-Empresa-ID': tenant } })
      ])

      if (!resFeines.ok) throw new Error('Error carregant feines')
      
      const feinesData = await resFeines.json()
      setFeines(feinesData)
      
      if (resClients.ok) setClients(await resClients.json())
      if (resOperaris.ok) setOperaris(await resOperaris.json())
      if (resVehicles.ok) setVehicles(await resVehicles.json())

    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleCreateFeina = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!newClient) return alert('Selecciona un Client obligatoriament.')
    if (!newOperari) return alert('Selecciona un Cap de Colla obligatoriament.')

    try {
      const payload: any = {
        codi: newCodi,
        titol: newTitol,
        adreca: newAdreca,
        data_planificacio: newData,
        client_id: newClient,
        cap_de_colla_id: newOperari,
        estat: 'PENDENT'
      }
      
      if (newVehicle) payload.vehicle_id = newVehicle

      const res = await fetch('/api/v1/gestio/feines', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Empresa-ID': tenant
        },
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'Error al donar d\'alta la feina')
      }
      
      setShowModal(false)
      setNewCodi('')
      setNewTitol('')
      setNewAdreca('')
      setNewData('')
      setNewClient('')
      setNewOperari('')
      setNewVehicle('')
      fetchData()
    } catch (err: any) {
      alert(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-white">Ordres de Treball (Feines)</h1>
        <button 
          onClick={() => setShowModal(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          <span className="material-symbols-outlined text-sm">add</span>
          Nova Feina
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded-xl">
          {error}
        </div>
      )}

      <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden shadow-sm">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider text-xs">
            <tr>
              <th className="px-6 py-4">Codi</th>
              <th className="px-6 py-4">Títol i Destí</th>
              <th className="px-6 py-4">Data Planificada</th>
              <th className="px-6 py-4">Estat</th>
              <th className="px-6 py-4 text-right">Accions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                  <span className="material-symbols-outlined animate-spin text-3xl">refresh</span>
                  <p className="mt-2">Carregant dades...</p>
                </td>
              </tr>
            ) : feines.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                  No hi ha cap ordre de treball (feina) registrada.
                </td>
              </tr>
            ) : (
              feines.map(feina => (
                <tr key={feina.id} className="hover:bg-slate-700/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-bold text-white uppercase">{feina.codi}</td>
                  <td className="px-6 py-4">
                    <p className="font-medium text-white">{feina.titol}</p>
                    <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                      <span className="material-symbols-outlined text-[14px]">location_on</span>
                      {feina.adreca}
                    </p>
                  </td>
                  <td className="px-6 py-4">{feina.data_planificacio}</td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 bg-yellow-900/30 text-yellow-500 text-xs rounded-full border border-yellow-800/50 flex items-center gap-1 w-max">
                      <span className="w-1.5 h-1.5 rounded-full bg-yellow-500"></span> {feina.estat}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-blue-400 hover:text-blue-300 p-1">
                      <span className="material-symbols-outlined text-lg">edit</span>
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl shadow-xl w-full max-w-2xl my-8">
            <div className="flex justify-between items-center p-6 border-b border-slate-700 sticky top-0 bg-slate-800 rounded-t-2xl z-10">
              <h3 className="text-lg font-bold text-white">Alta de Nova Ordre de Treball</h3>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <form onSubmit={handleCreateFeina} className="p-6 space-y-4">
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Codi Feina</label>
                  <input 
                    type="text" required
                    value={newCodi} onChange={(e) => setNewCodi(e.target.value.toUpperCase())}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 font-mono"
                    placeholder="OT-001"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Data Planificada</label>
                  <input 
                    type="date" required
                    value={newData} onChange={(e) => setNewData(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Títol / Breu Descripció</label>
                <input 
                  type="text" required
                  value={newTitol} onChange={(e) => setNewTitol(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Adreça de Destí (Obligatòria)</label>
                <input 
                  type="text" required
                  value={newAdreca} onChange={(e) => setNewAdreca(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                  placeholder="Carrer, Número, Població..."
                />
              </div>

              <div className="pt-2 border-t border-slate-700">
                <h4 className="text-sm font-medium text-slate-300 mb-4 mt-2">Assignacions</h4>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Client (Obligatori)</label>
                    <select 
                      required value={newClient} onChange={(e) => setNewClient(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                    >
                      <option value="">Selecciona Client...</option>
                      {clients.map(c => <option key={c.id} value={c.id}>{c.rao_social}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Cap de Colla / Operari (Obligatori)</label>
                    <select 
                      required value={newOperari} onChange={(e) => setNewOperari(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                    >
                      <option value="">Selecciona Operari...</option>
                      {operaris.map(o => <option key={o.id} value={o.id}>{o.nom} {o.cognoms}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Vehicle (Optatiu)</label>
                    <select 
                      value={newVehicle} onChange={(e) => setNewVehicle(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                    >
                      <option value="">Sense vehicle assignat</option>
                      {vehicles.map(v => <option key={v.id} value={v.id}>{v.matricula} ({v.model})</option>)}
                    </select>
                  </div>
                </div>
              </div>

              <div className="pt-6 flex justify-end gap-3 sticky bottom-0 bg-slate-800 pb-2">
                <button 
                  type="button" 
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 rounded-lg font-medium text-slate-300 hover:bg-slate-700 transition"
                >
                  Cancel·lar
                </button>
                <button 
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-lg font-medium text-white transition"
                >
                  Guardar Ordre de Treball
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
