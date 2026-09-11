'use client'

import { useState, useEffect } from 'react'

interface Client {
  id: string
  codi: string
  rao_social: string
  nif: string
  email: string | null
  telefon: string | null
}

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [newCodi, setNewCodi] = useState('')
  const [newRaoSocial, setNewRaoSocial] = useState('')
  const [newNif, setNewNif] = useState('')

  const fetchClients = async () => {
    try {
      const res = await fetch('/api/v1/gestio/clients', {
        headers: { 'X-Empresa-ID': process.env.NEXT_PUBLIC_TENANT_ID || '' }
      })
      if (!res.ok) throw new Error('Error carregant clients')
      const data = await res.json()
      setClients(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchClients()
  }, [])

  const handleCreateClient = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await fetch('/api/v1/gestio/clients', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Empresa-ID': process.env.NEXT_PUBLIC_TENANT_ID || ''
        },
        body: JSON.stringify({ 
          codi: newCodi, 
          rao_social: newRaoSocial, 
          nif: newNif 
        })
      })
      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'Error al crear el client')
      }
      
      setShowModal(false)
      setNewCodi('')
      setNewRaoSocial('')
      setNewNif('')
      fetchClients()
    } catch (err: any) {
      alert(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-white">Directori de Clients</h1>
        <button 
          onClick={() => setShowModal(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          <span className="material-symbols-outlined text-sm">add</span>
          Nou Client
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
              <th className="px-6 py-4">Email</th>
              <th className="px-6 py-4">Telèfon</th>
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
            ) : clients.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                  No s'ha trobat cap client a la base de dades.
                </td>
              </tr>
            ) : (
              clients.map(client => (
                <tr key={client.id} className="hover:bg-slate-700/30 transition-colors">
                  <td className="px-6 py-4 font-mono text-xs">{client.codi}</td>
                  <td className="px-6 py-4 font-medium text-white">{client.rao_social}</td>
                  <td className="px-6 py-4 font-mono text-xs">{client.nif}</td>
                  <td className="px-6 py-4">{client.email || '-'}</td>
                  <td className="px-6 py-4">{client.telefon || '-'}</td>
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
              <h3 className="text-lg font-bold text-white">Alta de Nou Client</h3>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <form onSubmit={handleCreateClient} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Codi</label>
                <input 
                  type="text" required
                  value={newCodi} onChange={(e) => setNewCodi(e.target.value.toUpperCase())}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 uppercase font-mono"
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
                  Guardar Client
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
