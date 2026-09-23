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

  // Estat Fitxa 360°
  const [selectedFitxaClient, setSelectedFitxaClient] = useState<Client | null>(null)
  const [fitxaData, setFitxaData] = useState<any>(null)
  const [fitxaLoading, setFitxaLoading] = useState(false)

  const handleOpenFitxa360 = async (client: Client) => {
    setSelectedFitxaClient(client)
    setFitxaLoading(true)
    setFitxaData(null)
    try {
      const token = localStorage.getItem('sevalor_token') || localStorage.getItem('token') || ''
      const tenant = process.env.NEXT_PUBLIC_TENANT_ID || localStorage.getItem('empresa_id') || ''
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (tenant) headers['X-Empresa-ID'] = tenant

      const res = await fetch(`/api/v1/gestio/clients/${client.id}/fitxa360`, { headers })
      if (!res.ok) throw new Error('Error al carregar la Fitxa 360°')
      const data = await res.json()
      setFitxaData(data)
    } catch (err: any) {
      alert(err.message)
    } finally {
      setFitxaLoading(false)
    }
  }

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
                  <td className="px-6 py-4 text-right flex items-center justify-end gap-2">
                    <button
                      onClick={() => handleOpenFitxa360(client)}
                      className="inline-flex items-center gap-1 text-xs bg-blue-600/20 text-blue-400 hover:bg-blue-600 hover:text-white px-2.5 py-1.5 rounded-lg border border-blue-500/30 transition-colors"
                      title="Fitxa 360° del Client"
                    >
                      <span className="material-symbols-outlined text-sm">visibility</span>
                      Fitxa 360°
                    </button>
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

      {/* Modal Fitxa 360° */}
      {selectedFitxaClient && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b border-slate-700 bg-slate-850">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <span className="material-symbols-outlined text-blue-400">visibility</span>
                  Fitxa 360° — {selectedFitxaClient.rao_social}
                </h3>
                <p className="text-xs text-slate-400 mt-1 font-mono">
                  Codi: {selectedFitxaClient.codi} | NIF: {selectedFitxaClient.nif} | Anàlisi d'últims 365 dies
                </p>
              </div>
              <button
                onClick={() => setSelectedFitxaClient(null)}
                className="text-slate-400 hover:text-white p-2 rounded-lg hover:bg-slate-700"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {fitxaLoading ? (
                <div className="py-16 text-center text-slate-400 flex flex-col items-center justify-center">
                  <span className="material-symbols-outlined animate-spin text-4xl text-blue-500 mb-2">refresh</span>
                  <p>Recopilant dades històriques de la finca i intervencions...</p>
                </div>
              ) : !fitxaData ? (
                <div className="text-center py-12 text-slate-400">
                  No s'han pogut carregar les dades de la Fitxa 360°.
                </div>
              ) : (
                <>
                  {/* Resum Kpi */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-700/60">
                      <div className="text-xs font-semibold text-slate-400 uppercase">Intervencions (365d)</div>
                      <div className="text-2xl font-bold text-blue-400 mt-1">{fitxaData.resum?.total_intervencions || 0}</div>
                    </div>
                    <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-700/60">
                      <div className="text-xs font-semibold text-slate-400 uppercase">Peces Instal·lades</div>
                      <div className="text-2xl font-bold text-emerald-400 mt-1">{fitxaData.resum?.total_peces_instalades || 0}</div>
                    </div>
                    <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-700/60">
                      <div className="text-xs font-semibold text-slate-400 uppercase">Incidències</div>
                      <div className="text-2xl font-bold text-amber-400 mt-1">{fitxaData.resum?.total_incidencies || 0}</div>
                    </div>
                  </div>

                  {/* Intervencions Recents */}
                  <div>
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-sm text-blue-400">build</span>
                      Intervencions Tècniques
                    </h4>
                    {fitxaData.intervencions?.length === 0 ? (
                      <p className="text-xs text-slate-500 italic bg-slate-900/30 p-3 rounded-lg border border-slate-700/30">
                        Cap intervenció registrada en els darrers 365 dies.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {fitxaData.intervencions.map((it: any) => (
                          <div key={it.id} className="bg-slate-900/50 p-3 rounded-lg border border-slate-700/50 flex justify-between items-center text-xs">
                            <div>
                              <div className="font-semibold text-white">{it.titol}</div>
                              <div className="text-slate-400 text-[11px] font-mono">{it.codi} • {it.adreca}</div>
                            </div>
                            <span className="px-2 py-0.5 rounded text-[10px] bg-slate-700 text-slate-300 font-bold">
                              {it.estat}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Peces Instal·lades */}
                  <div>
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-sm text-emerald-400">inventory</span>
                      Peces i Components Instal·lats
                    </h4>
                    {fitxaData.peces_instalades?.length === 0 ? (
                      <p className="text-xs text-slate-500 italic bg-slate-900/30 p-3 rounded-lg border border-slate-700/30">
                        Cap peça registrada en els darrers 365 dies.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {fitxaData.peces_instalades.map((p: any, idx: number) => (
                          <div key={idx} className="bg-slate-900/50 p-3 rounded-lg border border-slate-700/50 flex justify-between items-center text-xs">
                            <div>
                              <div className="font-medium text-white">{p.nom_article}</div>
                              <div className="text-slate-400 text-[11px] font-mono">Ref: {p.codi_article} | OT: {p.ordre_treball_codi}</div>
                            </div>
                            <div className="text-emerald-400 font-bold font-mono">
                              {p.quantitat_instalada} {p.unitat_mesura}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Incidències */}
                  <div>
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-sm text-amber-400">report_problem</span>
                      Històric d'Incidències
                    </h4>
                    {fitxaData.incidencies?.length === 0 ? (
                      <p className="text-xs text-slate-500 italic bg-slate-900/30 p-3 rounded-lg border border-slate-700/30">
                        Sense incidències registrades en els darrers 365 dies.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {fitxaData.incidencies.map((inc: any) => (
                          <div key={inc.id} className="bg-slate-900/50 p-3 rounded-lg border border-slate-700/50 flex justify-between items-center text-xs">
                            <div>
                              <div className="font-medium text-white">{inc.text_observacions || 'Incidència sense descripció'}</div>
                              <div className="text-slate-400 text-[11px] font-mono">{inc.ambit} • {new Date(inc.created_at).toLocaleDateString()}</div>
                            </div>
                            <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 font-bold">
                              {inc.estat}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>

            <div className="p-4 border-t border-slate-700 bg-slate-850 flex justify-end">
              <button
                onClick={() => setSelectedFitxaClient(null)}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm font-medium transition"
              >
                Tancar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
