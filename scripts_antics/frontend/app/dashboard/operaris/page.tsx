'use client'

import { useState, useEffect } from 'react'

interface Operari {
  id: string
  nom: string
  cognoms: string
  nif: string
  rol: string
  estat: string
  telefon: string
  pin_bloquejat: boolean
  intents_pin_fallits: number
}

export default function OperarisPage() {
  const [operaris, setOperaris] = useState<Operari[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [newNom, setNewNom] = useState('')
  const [newCognoms, setNewCognoms] = useState('')
  const [newNif, setNewNif] = useState('')
  const [newTelefon, setNewTelefon] = useState('')
  const [newEspecialitat, setNewEspecialitat] = useState('GENERAL')
  const [newCostHora, setNewCostHora] = useState(20.0)

  const fetchOperaris = async () => {
    try {
      const res = await fetch('/api/v1/gestio/operaris', {
        headers: { 'X-Empresa-ID': process.env.NEXT_PUBLIC_TENANT_ID || '' }
      })
      if (!res.ok) throw new Error('Error carregant operaris')
      const data = await res.json()
      setOperaris(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchOperaris()
  }, [])

  const handleCreateOperari = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await fetch('/api/v1/gestio/operaris', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Empresa-ID': process.env.NEXT_PUBLIC_TENANT_ID || ''
        },
        body: JSON.stringify({ 
          nif: newNif,
          nom: newNom, 
          cognoms: newCognoms,
          telefon: newTelefon,
          especialitat: newEspecialitat,
          cost_hora_eur: Number(newCostHora)
        })
      })
      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'Error al crear l\'operari')
      }
      
      setShowModal(false)
      setNewNom('')
      setNewCognoms('')
      setNewNif('')
      setNewTelefon('')
      fetchOperaris()
    } catch (err: any) {
      alert(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-white">Directori d'Operaris</h1>
        <button 
          onClick={() => setShowModal(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          <span className="material-symbols-outlined text-sm">person_add</span>
          Nou Operari
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
              <th className="px-6 py-4">Nom de l'Empleat</th>
              <th className="px-6 py-4">NIF / NIE</th>
              <th className="px-6 py-4">Rol</th>
              <th className="px-6 py-4">Telèfon</th>
              <th className="px-6 py-4">Estat Seguretat</th>
              <th className="px-6 py-4 text-right">Accions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {loading ? (
              <tr><td colSpan={6} className="px-6 py-8 text-center">Carregant dades...</td></tr>
            ) : operaris.length === 0 ? (
              <tr><td colSpan={6} className="px-6 py-8 text-center">No s'ha trobat cap operari.</td></tr>
            ) : (
              operaris.map(op => (
                <tr key={op.id} className="hover:bg-slate-700/30">
                  <td className="px-6 py-4 font-medium text-white">{op.nom} {op.cognoms}</td>
                  <td className="px-6 py-4 font-mono text-xs">{op.nif}</td>
                  <td className="px-6 py-4"><span className="bg-slate-700 px-2 py-1 rounded text-xs text-slate-300">{op.rol}</span></td>
                  <td className="px-6 py-4 font-mono text-xs">{op.telefon}</td>
                  <td className="px-6 py-4">
                    {op.pin_bloquejat ? (
                      <span className="text-red-400 flex items-center gap-1 text-xs">Bloquejat</span>
                    ) : (
                      <span className="text-green-400 flex items-center gap-1 text-xs">Actiu</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-slate-400 hover:text-white p-1" title="Restablir PIN"><span className="material-symbols-outlined text-lg">key</span></button>
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
              <h3 className="text-lg font-bold text-white">Alta Nou Operari</h3>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white"><span className="material-symbols-outlined">close</span></button>
            </div>
            <form onSubmit={handleCreateOperari} className="p-6 space-y-4">
              <div>
                <label className="block text-xs text-slate-400 mb-2">NIF / NIE</label>
                <input type="text" required value={newNif} onChange={(e) => setNewNif(e.target.value.toUpperCase())} className="w-full bg-slate-900 border rounded-lg px-4 py-2.5 text-white" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-slate-400 mb-2">Nom</label>
                  <input type="text" required value={newNom} onChange={(e) => setNewNom(e.target.value)} className="w-full bg-slate-900 border rounded-lg px-4 py-2.5 text-white" />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-2">Cognoms</label>
                  <input type="text" value={newCognoms} onChange={(e) => setNewCognoms(e.target.value)} className="w-full bg-slate-900 border rounded-lg px-4 py-2.5 text-white" />
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-2">Telèfon (Rep PIN per SMS)</label>
                <input type="text" required value={newTelefon} onChange={(e) => setNewTelefon(e.target.value)} className="w-full bg-slate-900 border rounded-lg px-4 py-2.5 text-white" />
              </div>
              <div className="pt-4 flex justify-end gap-3">
                <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 text-slate-300">Cancel·lar</button>
                <button type="submit" className="bg-blue-600 px-4 py-2 rounded-lg text-white">Registrar Operari</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
