'use client'

import { useState, useEffect } from 'react'

interface Vehicle {
  id: string
  matricula: string
  marca: string
  model: string
  tipus: string
  distintiu_ambiental: string | null
  estat: string
  horometre_acumulat: number
  odometre_acumulat: number
}

export default function FlotaPage() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [newMatricula, setNewMatricula] = useState('')
  const [newMarca, setNewMarca] = useState('')
  const [newModel, setNewModel] = useState('')
  const [newTipus, setNewTipus] = useState('THERMIC')
  const [newDistintiu, setNewDistintiu] = useState('B')

  const fetchFlota = async () => {
    try {
      const res = await fetch('/api/v1/gestio/flota', {
        headers: { 'X-Empresa-ID': process.env.NEXT_PUBLIC_TENANT_ID || '' }
      })
      if (!res.ok) throw new Error('Error carregant la flota de vehicles')
      const data = await res.json()
      setVehicles(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchFlota()
  }, [])

  const handleCreateVehicle = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await fetch('/api/v1/gestio/flota', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Empresa-ID': process.env.NEXT_PUBLIC_TENANT_ID || ''
        },
        body: JSON.stringify({ 
          matricula: newMatricula, 
          marca: newMarca, 
          model: newModel,
          tipus: newTipus,
          distintiu_ambiental: newDistintiu,
          estat: 'OPERATIU'
        })
      })
      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'Error al donar d\'alta el vehicle')
      }
      
      setShowModal(false)
      setNewMatricula('')
      setNewMarca('')
      setNewModel('')
      setNewTipus('THERMIC')
      fetchFlota()
    } catch (err: any) {
      alert(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-white">Flota de Vehicles</h1>
        <button 
          onClick={() => setShowModal(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          <span className="material-symbols-outlined text-sm">add</span>
          Nou Vehicle
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
              <th className="px-6 py-4">Matrícula</th>
              <th className="px-6 py-4">Vehicle</th>
              <th className="px-6 py-4">Tipus / Distintiu</th>
              <th className="px-6 py-4">Ús Acumulat</th>
              <th className="px-6 py-4">Estat</th>
              <th className="px-6 py-4 text-right">Accions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                  <span className="material-symbols-outlined animate-spin text-3xl">refresh</span>
                  <p className="mt-2">Carregant dades des de l'API...</p>
                </td>
              </tr>
            ) : vehicles.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                  No hi ha cap vehicle registrat a la flota.
                </td>
              </tr>
            ) : (
              vehicles.map(veh => (
                <tr key={veh.id} className="hover:bg-slate-700/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-bold text-white uppercase">{veh.matricula}</td>
                  <td className="px-6 py-4 font-medium">
                    {veh.marca} {veh.model}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex gap-2">
                      <span className="px-2 py-0.5 bg-slate-700 text-slate-300 text-xs rounded border border-slate-600">
                        {veh.tipus}
                      </span>
                      {veh.distintiu_ambiental && (
                        <span className="px-2 py-0.5 bg-yellow-900/40 text-yellow-500 text-xs rounded border border-yellow-700/50">
                          Etiqueta {veh.distintiu_ambiental}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 font-mono text-xs text-slate-400">
                    {veh.odometre_acumulat} km
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 bg-green-900/30 text-green-400 text-xs rounded-full border border-green-800/50 flex items-center gap-1 w-max">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-400"></span> {veh.estat}
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b border-slate-700">
              <h3 className="text-lg font-bold text-white">Alta de Nou Vehicle</h3>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <form onSubmit={handleCreateVehicle} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Matrícula</label>
                <input 
                  type="text" required
                  value={newMatricula} onChange={(e) => setNewMatricula(e.target.value.toUpperCase())}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 uppercase font-mono tracking-widest font-bold"
                  placeholder="1234 ABC"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Marca</label>
                  <input 
                    type="text" required
                    value={newMarca} onChange={(e) => setNewMarca(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Model</label>
                  <input 
                    type="text" required
                    value={newModel} onChange={(e) => setNewModel(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Tipus</label>
                  <select 
                    value={newTipus} onChange={(e) => setNewTipus(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="THERMIC">TÈRMIC (Combustió)</option>
                    <option value="EV">ELÈCTRIC (EV)</option>
                    <option value="PHEV">HÍBRID (PHEV)</option>
                    <option value="MAQUINARIA">MAQUINÀRIA</option>
                    <option value="REMOLC">REMOLC</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Etiqueta</label>
                  <select 
                    value={newDistintiu} onChange={(e) => setNewDistintiu(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="0">Zero (0)</option>
                    <option value="ECO">ECO</option>
                    <option value="C">C</option>
                    <option value="B">B</option>
                    <option value="SENSE">Sense Etiqueta</option>
                  </select>
                </div>
              </div>
              <div className="pt-4 flex justify-end gap-3">
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
                  Guardar Vehicle
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
