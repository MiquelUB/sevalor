'use client'

import { useEffect, useState } from 'react'

interface Pressupost {
  id: string
  empresa_id: string
  client_id: string
  numero: string
  total: number
  estat: string
  token_signatura: string | null
  created_at: string
}

interface ClientItem {
  id: string
  rao_social: string
  nif: string
  telegram_chat_id?: number | null
  estat_canal_telegram?: string
}

export default function PressupostosPage() {
  const [pressupostos, setPressupostos] = useState<Pressupost[]>([])
  const [clients, setClients] = useState<ClientItem[]>([])
  const [loading, setLoading] = useState(true)
  const [modalObert, setModalObert] = useState(false)
  const [notificacio, setNotificacio] = useState<{ tipus: 'exit' | 'error'; missatge: string } | null>(null)

  // Formulari nou pressupost
  const [nouClientId, setNouClientId] = useState('')
  const [nouNumero, setNouNumero] = useState('')
  const [nouTotal, setNouTotal] = useState('')
  const [enviant, setEnviant] = useState(false)

  const carregarDades = async () => {
    try {
      setLoading(true)
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : ''
      const empresaId = typeof window !== 'undefined' ? localStorage.getItem('empresa_id') : ''
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (empresaId) headers['X-Empresa-ID'] = empresaId

      const [resPress, resClients] = await Promise.all([
        fetch('/api/v1/gestio/pressupostos', { headers }),
        fetch('/api/v1/gestio/clients', { headers }),
      ])

      if (resPress.ok) {
        const dataPress = await resPress.json()
        setPressupostos(Array.isArray(dataPress) ? dataPress : [])
      }
      if (resClients.ok) {
        const dataCli = await resClients.json()
        setClients(Array.isArray(dataCli) ? dataCli : [])
      }
    } catch (err) {
      console.error('Error carregant pressupostos:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    carregarDades()
  }, [])

  const handleCrearPressupost = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!nouClientId || !nouNumero || !nouTotal) return

    try {
      setEnviant(true)
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : ''
      const empresaId = typeof window !== 'undefined' ? localStorage.getItem('empresa_id') : ''
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (empresaId) headers['X-Empresa-ID'] = empresaId

      const res = await fetch('/api/v1/gestio/pressupostos', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          client_id: nouClientId,
          numero: nouNumero,
          total: parseFloat(nouTotal),
        }),
      })

      if (res.ok) {
        setNotificacio({ tipus: 'exit', missatge: `Pressupost ${nouNumero} creat correctament.` })
        setModalObert(false)
        setNouNumero('')
        setNouTotal('')
        setNouClientId('')
        carregarDades()
      } else {
        const err = await res.json()
        setNotificacio({ tipus: 'error', missatge: err.detail || 'Error en crear el pressupost.' })
      }
    } catch {
      setNotificacio({ tipus: 'error', missatge: 'Error de comunicació amb el servidor.' })
    } finally {
      setEnviant(false)
    }
  }

  const handleEnviarTelegram = async (id: string, numero: string) => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : ''
      const empresaId = typeof window !== 'undefined' ? localStorage.getItem('empresa_id') : ''
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (empresaId) headers['X-Empresa-ID'] = empresaId

      const res = await fetch(`/api/v1/gestio/pressupostos/${id}/enviar-telegram`, {
        method: 'POST',
        headers,
      })

      if (res.ok) {
        setNotificacio({
          tipus: 'exit',
          missatge: `Pressupost ${numero} enviat correctament al Telegram del client amb botons d'aprovació.`,
        })
        carregarDades()
      } else {
        const err = await res.json()
        setNotificacio({ tipus: 'error', missatge: err.detail || 'No s\'ha pogut enviar per Telegram.' })
      }
    } catch {
      setNotificacio({ tipus: 'error', missatge: 'Error en la petició a Telegram.' })
    }
  }

  return (
    <div className="space-y-6">
      {/* Capçalera */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Pressupostos Transaccionals</h1>
          <p className="text-sm text-slate-400">
            Circuits de signatura d'aprovació i rebuig via bot interactiu de Telegram (Spec 009).
          </p>
        </div>
        <button
          onClick={() => setModalObert(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition"
        >
          <span className="material-symbols-outlined text-lg">add_circle</span>
          Nou Pressupost
        </button>
      </div>

      {/* Alerta de Notificació */}
      {notificacio && (
        <div
          className={`p-4 rounded-xl text-sm flex items-center justify-between ${
            notificacio.tipus === 'exit'
              ? 'bg-emerald-950/60 border border-emerald-500/40 text-emerald-300'
              : 'bg-rose-950/60 border border-rose-500/40 text-rose-300'
          }`}
        >
          <span>{notificacio.missatge}</span>
          <button onClick={() => setNotificacio(null)} className="text-slate-400 hover:text-white">
            <span className="material-symbols-outlined text-sm">close</span>
          </button>
        </div>
      )}

      {/* Taula de Pressupostos */}
      <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-800/80 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-700">
              <tr>
                <th className="px-6 py-4">Número</th>
                <th className="px-6 py-4">Client</th>
                <th className="px-6 py-4 text-right">Import Total</th>
                <th className="px-6 py-4 text-center">Estat</th>
                <th className="px-6 py-4">Signatura / Token</th>
                <th className="px-6 py-4 text-center">Accions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-slate-400">
                    Carregant pressupostos...
                  </td>
                </tr>
              ) : pressupostos.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                    <span className="material-symbols-outlined text-4xl mb-2 text-slate-600 block">request_quote</span>
                    No hi ha cap pressupost registrat. Crea el primer per iniciar el circuit.
                  </td>
                </tr>
              ) : (
                pressupostos.map((p) => {
                  const client = clients.find((c) => c.id === p.client_id)
                  const teTelegram = client?.telegram_chat_id && client?.estat_canal_telegram === 'ACTIU'

                  return (
                    <tr key={p.id} className="hover:bg-slate-750/50 transition">
                      <td className="px-6 py-4 font-mono font-medium text-white">{p.numero}</td>
                      <td className="px-6 py-4">
                        <div className="font-medium text-slate-200">{client?.rao_social || 'Client desvinculat'}</div>
                        <div className="text-xs text-slate-400">
                          {teTelegram ? (
                            <span className="text-emerald-400 flex items-center gap-1 mt-0.5">
                              <span className="material-symbols-outlined text-xs">send</span> Telegram Actiu
                            </span>
                          ) : (
                            <span className="text-amber-400/80 flex items-center gap-1 mt-0.5">
                              <span className="material-symbols-outlined text-xs">link_off</span> Telegram Pendent
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right font-mono font-semibold text-slate-100">
                        {Number(p.total).toFixed(2)} €
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span
                          className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
                            p.estat === 'APROVAT'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : p.estat === 'REBUTJAT'
                              ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          }`}
                        >
                          {p.estat}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono text-xs text-slate-400">
                        {p.token_signatura ? (
                          <span className="text-blue-400 truncate max-w-[200px] block" title={p.token_signatura}>
                            {p.token_signatura}
                          </span>
                        ) : (
                          <span className="text-slate-500 italic">Pendent de signatura</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-center">
                        {p.estat === 'PENDENT' ? (
                          <button
                            onClick={() => handleEnviarTelegram(p.id, p.numero)}
                            title={teTelegram ? 'Enviar via bot Telegram' : 'El client no té el bot enllaçat'}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-500/30 rounded-lg text-xs font-medium transition"
                          >
                            <span className="material-symbols-outlined text-sm">send</span>
                            Enviar Telegram
                          </button>
                        ) : (
                          <span className="text-xs text-slate-500">Tancat</span>
                        )}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal Crear Pressupost */}
      {modalObert && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-700 pb-3">
              <h3 className="text-lg font-bold text-white">Crear Nou Pressupost</h3>
              <button onClick={() => setModalObert(false)} className="text-slate-400 hover:text-white">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <form onSubmit={handleCrearPressupost} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Client Assignat
                </label>
                <select
                  value={nouClientId}
                  onChange={(e) => setNouClientId(e.target.value)}
                  required
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="">Selecciona un client...</option>
                  {clients.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.rao_social} ({c.nif})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Número de Pressupost
                </label>
                <input
                  type="text"
                  placeholder="ex: PRES-2026-0042"
                  value={nouNumero}
                  onChange={(e) => setNouNumero(e.target.value)}
                  required
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Import Total (€)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="0.00"
                  value={nouTotal}
                  onChange={(e) => setNouTotal(e.target.value)}
                  required
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-700">
                <button
                  type="button"
                  onClick={() => setModalObert(false)}
                  className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-xl text-sm font-medium transition"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={enviant}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition disabled:opacity-50"
                >
                  {enviant ? 'Guardant...' : 'Crear Pressupost'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
