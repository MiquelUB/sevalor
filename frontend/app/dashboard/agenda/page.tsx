'use client'

import { useState, useEffect } from 'react'

interface Feina {
  id: string
  codi: string
  titol: string
  adreca: string
  estat: string
  data_planificacio: string
  hora_inici_prevista?: string | null
  hora_fi_prevista?: string | null
  version_id?: number
}

export default function AgendaPage() {
  const [feines, setFeines] = useState<Feina[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [conflictMsg, setConflictMsg] = useState<string | null>(null)

  // Modal d'agendament
  const [selectedFeina, setSelectedFeina] = useState<Feina | null>(null)
  const [iniciTime, setIniciTime] = useState('')
  const [fiTime, setFiTime] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Setmana actual
  const [currentDate, setCurrentDate] = useState<Date>(new Date())

  const fetchFeines = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('sevalor_token') || localStorage.getItem('token') || ''
      const tenant = process.env.NEXT_PUBLIC_TENANT_ID || localStorage.getItem('empresa_id') || ''

      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (tenant) headers['X-Empresa-ID'] = tenant

      const res = await fetch('/api/v1/gestio/feines', { headers })
      if (!res.ok) throw new Error('Error en carregar les ordres de treball')
      const data = await res.json()
      setFeines(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchFeines()
  }, [])

  // Càlcul dels 7 dies de la setmana seleccionada (Dilluns a Diumenge)
  const getWeekDates = (date: Date) => {
    const start = new Date(date)
    const day = start.getDay()
    const diff = start.getDate() - day + (day === 0 ? -6 : 1) // Dilluns
    start.setDate(diff)

    const week = []
    for (let i = 0; i < 7; i++) {
      const d = new Date(start)
      d.setDate(start.getDate() + i)
      week.push(d)
    }
    return week
  }

  const weekDays = getWeekDates(currentDate)
  const dayNames = ['Dilluns', 'Dimarts', 'Dimecres', 'Dijous', 'Divendres', 'Dissabte', 'Diumenge']

  const handleOpenAgendar = (feina: Feina) => {
    setSelectedFeina(feina)
    setConflictMsg(null)
    const dataPlan = feina.data_planificacio || new Date().toISOString().split('T')[0]
    setIniciTime(feina.hora_inici_prevista ? feina.hora_inici_prevista.slice(0, 16) : `${dataPlan}T08:00`)
    setFiTime(feina.hora_fi_prevista ? feina.hora_fi_prevista.slice(0, 16) : `${dataPlan}T12:00`)
  }

  const handleSaveAgenda = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFeina) return

    setSubmitting(true)
    setConflictMsg(null)

    try {
      const token = localStorage.getItem('sevalor_token') || localStorage.getItem('token') || ''
      const tenant = process.env.NEXT_PUBLIC_TENANT_ID || localStorage.getItem('empresa_id') || ''

      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      }
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (tenant) headers['X-Empresa-ID'] = tenant

      const payload = {
        hora_inici_prevista: new Date(iniciTime).toISOString(),
        hora_fi_prevista: new Date(fiTime).toISOString(),
        version_id: selectedFeina.version_id ?? 1
      }

      const res = await fetch(`/api/v1/gestio/feines/${selectedFeina.id}/agendar`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(payload)
      })

      if (res.status === 409) {
        const errorData = await res.json()
        setConflictMsg(errorData.detail || 'Conflicte de concurrència: aquesta feina ha estat modificada per un altre usuari.')
        await fetchFeines() // Actualitzar estat
        return
      }

      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'Error en desar la planificació')
      }

      setSelectedFeina(null)
      await fetchFeines()
    } catch (err: any) {
      alert(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Capçalera */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <span className="material-symbols-outlined text-blue-500">calendar_month</span>
            Agenda i Planificació Setmanal
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Programació i assignació d'ordres de treball amb protecció de concurrència (Optimistic Locking).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const prev = new Date(currentDate)
              prev.setDate(prev.getDate() - 7)
              setCurrentDate(prev)
            }}
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700"
          >
            <span className="material-symbols-outlined">chevron_left</span>
          </button>
          <button
            onClick={() => setCurrentDate(new Date())}
            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-lg border border-slate-700"
          >
            Avui
          </button>
          <button
            onClick={() => {
              const next = new Date(currentDate)
              next.setDate(next.getDate() + 7)
              setCurrentDate(next)
            }}
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700"
          >
            <span className="material-symbols-outlined">chevron_right</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded-xl text-sm">
          {error}
        </div>
      )}

      {/* Grid Setmanal amb Tailwind Grid */}
      <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden shadow-sm">
        <div className="grid grid-cols-7 border-b border-slate-700 bg-slate-900/60 text-center">
          {weekDays.map((d, index) => {
            const isToday = d.toDateString() === new Date().toDateString()
            return (
              <div
                key={index}
                className={`py-3 px-2 border-r last:border-r-0 border-slate-700/60 ${
                  isToday ? 'bg-blue-600/10 text-blue-400 font-bold' : 'text-slate-300 font-medium'
                }`}
              >
                <div className="text-xs uppercase tracking-wider text-slate-400">{dayNames[index]}</div>
                <div className="text-lg mt-0.5">{d.getDate()}</div>
                <div className="text-[10px] text-slate-500">{d.toLocaleDateString('ca-ES', { month: 'short' })}</div>
              </div>
            )
          })}
        </div>

        {/* Columnes de feines per dia */}
        <div className="grid grid-cols-7 min-h-[500px] divide-x divide-slate-700/50 bg-slate-800/40">
          {weekDays.map((d, index) => {
            const dateStr = d.toISOString().split('T')[0]
            const dayFeines = feines.filter((f) => f.data_planificacio === dateStr)

            return (
              <div key={index} className="p-2 flex flex-col gap-2">
                {dayFeines.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-slate-600 text-xs py-8">
                    Sense tasques
                  </div>
                ) : (
                  dayFeines.map((feina) => (
                    <div
                      key={feina.id}
                      onClick={() => handleOpenAgendar(feina)}
                      className="cursor-pointer bg-slate-900/80 hover:bg-slate-750 p-3 rounded-xl border border-slate-700 hover:border-blue-500/50 transition-all text-xs flex flex-col gap-1 shadow-sm"
                    >
                      <div className="flex justify-between items-center">
                        <span className="font-mono text-[10px] text-blue-400 font-semibold">{feina.codi}</span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[9px] uppercase font-bold ${
                            feina.estat === 'EN_CURS'
                              ? 'bg-blue-500/20 text-blue-300'
                              : feina.estat === 'BLOQUEJADA'
                              ? 'bg-red-500/20 text-red-300'
                              : 'bg-slate-700 text-slate-300'
                          }`}
                        >
                          {feina.estat}
                        </span>
                      </div>
                      <div className="font-medium text-white truncate" title={feina.titol}>
                        {feina.titol}
                      </div>
                      <div className="text-slate-400 text-[10px] truncate" title={feina.adreca}>
                        📍 {feina.adreca}
                      </div>
                      {feina.hora_inici_prevista && (
                        <div className="text-blue-300 text-[10px] mt-1 flex items-center gap-1 font-mono">
                          <span className="material-symbols-outlined text-[12px]">schedule</span>
                          {new Date(feina.hora_inici_prevista).toLocaleTimeString('ca-ES', {
                            hour: '2-digit',
                            minute: '2-digit'
                          })}{' '}
                          -{' '}
                          {feina.hora_fi_prevista
                            ? new Date(feina.hora_fi_prevista).toLocaleTimeString('ca-ES', {
                                hour: '2-digit',
                                minute: '2-digit'
                              })
                            : ''}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Modal d'agendament amb versió optimista */}
      {selectedFeina && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b border-slate-700">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <span className="material-symbols-outlined text-blue-400">schedule</span>
                  Planificar Ordre de Treball
                </h3>
                <p className="text-xs text-slate-400 mt-0.5 font-mono">{selectedFeina.codi} - {selectedFeina.titol}</p>
              </div>
              <button onClick={() => setSelectedFeina(null)} className="text-slate-400 hover:text-white">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            {conflictMsg && (
              <div className="m-6 p-4 bg-amber-500/10 border border-amber-500/40 text-amber-300 rounded-xl text-xs flex items-start gap-2">
                <span className="material-symbols-outlined text-sm">warning</span>
                <div>
                  <strong>Avís de Concurrència (HTTP 409):</strong>
                  <p className="mt-0.5">{conflictMsg}</p>
                </div>
              </div>
            )}

            <form onSubmit={handleSaveAgenda} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Hora d'Inici Prevista
                </label>
                <input
                  type="datetime-local"
                  required
                  value={iniciTime}
                  onChange={(e) => setIniciTime(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Hora de Fi Prevista
                </label>
                <input
                  type="datetime-local"
                  required
                  value={fiTime}
                  onChange={(e) => setFiTime(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 text-sm"
                />
              </div>

              <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-700/50 text-[11px] text-slate-400 flex items-center justify-between">
                <span>Versió de registre:</span>
                <span className="font-mono text-blue-400 font-bold">v{selectedFeina.version_id ?? 1}</span>
              </div>

              <div className="pt-4 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setSelectedFeina(null)}
                  className="px-4 py-2 rounded-lg font-medium text-slate-300 hover:bg-slate-700 transition text-sm"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-lg font-medium text-white transition text-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {submitting && <span className="material-symbols-outlined animate-spin text-sm">refresh</span>}
                  Confirmar Planificació
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
