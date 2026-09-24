'use client'

import { useState, useEffect } from 'react'

interface Proveidor {
  id: string
  codi: string
  rao_social: string
  nif: string
  email: string | null
  telefon: string | null
  especialitat: string
  actiu: boolean
}

export default function ProveidorsPage() {
  const [proveidors, setProveidors] = useState<Proveidor[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [newCodi, setNewCodi] = useState('')
  const [newRaoSocial, setNewRaoSocial] = useState('')
  const [newNif, setNewNif] = useState('')
  const [newEspecialitat, setNewEspecialitat] = useState('MATERIALS')

  const fetchProveidors = async () => {
    try {
      const res = await fetch('/api/v1/gestio/proveidors', {
        headers: { 'X-Empresa-ID': process.env.NEXT_PUBLIC_TENANT_ID || '' }
      })
      if (!res.ok) throw new Error('Error carregant proveïdors')
      const data = await res.json()
      setProveidors(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProveidors()
  }, [])

  const handleCreateProveidor = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await fetch('/api/v1/gestio/proveidors', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Empresa-ID': process.env.NEXT_PUBLIC_TENANT_ID || ''
        },
        body: JSON.stringify({ 
          codi: newCodi, 
          rao_social: newRaoSocial, 
          nif: newNif,
          especialitat: newEspecialitat
        })
      })
      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'Error al crear el proveïdor')
      }
      
      setShowModal(false)
      setNewCodi('')
      setNewRaoSocial('')
      setNewNif('')
      setNewEspecialitat('MATERIALS')
      fetchProveidors()
    } catch (err: any) {
      alert(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-white">Directori de Proveïdors</h1>
        <button 
          onClick={() => setShowModal(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          <span className="material-symbols-outlined text-sm">add</span>
          Nou Proveïdor
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
              <th className="px-6 py-4">Raó Social</th>
              <th className="px-6 py-4">NIF / CIF</th>
              <th className="px-6 py-4">Especialitat</th>
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
            ) : proveidors.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                  No hi ha proveïdors registrats per a aquesta empresa.
                </td>
              </tr>
            ) : (
              proveidors.map(prov => (
                <tr key={prov.id} className="hover:bg-slate-700/30 transition-colors">
                  <td className="px-6 py-4 font-mono text-xs">{prov.codi}</td>
                  <td className="px-6 py-4 font-medium text-white">{prov.rao_social}</td>
                  <td className="px-6 py-4 font-mono text-xs">{prov.nif}</td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 bg-slate-700 text-slate-300 text-xs rounded-full">
                      {prov.especialitat}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {prov.actiu ? (
                      <span className="text-green-400 flex items-center gap-1 text-xs"><span className="w-2 h-2 rounded-full bg-green-400"></span> Actiu</span>
                    ) : (
                      <span className="text-red-400 flex items-center gap-1 text-xs"><span className="w-2 h-2 rounded-full bg-red-400"></span> Inactiu</span>
                    )}
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
              <h3 className="text-lg font-bold text-white">Alta de Nou Proveïdor</h3>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <form onSubmit={handleCreateProveidor} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Codi de Proveïdor</label>
                <input 
                  type="text" required
                  value={newCodi} onChange={(e) => setNewCodi(e.target.value.toUpperCase())}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 uppercase font-mono"
                  placeholder="EX: PROV-001"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Raó Social</label>
                <input 
                  type="text" required
                  value={newRaoSocial} onChange={(e) => setNewRaoSocial(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">NIF / CIF</label>
                <input 
                  type="text" required
                  value={newNif} onChange={(e) => setNewNif(e.target.value.toUpperCase())}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 uppercase font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Especialitat</label>
                <select 
                  value={newEspecialitat} onChange={(e) => setNewEspecialitat(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="MATERIALS">MATERIALS</option>
                  <option value="MAQUINARIA">MAQUINARIA</option>
                  <option value="SUBCONTRACTA">SUBCONTRACTA</option>
                </select>
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
                  Guardar Proveïdor
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
