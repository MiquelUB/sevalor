'use client'

import { useState } from 'react'

interface PressupostClient {
  id: string
  numero: string
  titol: string
  total: number
  estat: 'PENDENT' | 'APROVAT' | 'REBUTJAT'
  data: string
}

interface IntervencioClient {
  id: string
  codi: string
  titol: string
  estat: 'PLANIFICADA' | 'EN_CURS' | 'FINALITZADA'
  data: string
  adreca: string
}

export default function ClientPortalPage() {
  const [autenticat, setAutenticat] = useState(false)
  const [codiAcces, setCodiAcces] = useState('')
  const [errorLogin, setErrorLogin] = useState('')

  // Dades de demostració del client autenticat al portal d'autoservei
  const [clientInfo] = useState({
    raoSocial: 'Comunitat de Propietaris Mallorca 234',
    nif: 'H-65498712',
    adreca: 'Carrer de Mallorca, 234, Barcelona',
    telegramVinculat: true,
  })

  const [pressupostos, setPressupostos] = useState<PressupostClient[]>([
    {
      id: 'pres-001',
      numero: 'PRES-2026-018',
      titol: 'Substitució de columnes generals d\'aigua comunitària',
      total: 3840.50,
      estat: 'PENDENT',
      data: '2026-09-20',
    },
    {
      id: 'pres-002',
      numero: 'PRES-2026-009',
      titol: 'Reparació d\'escomesa elèctrica i quadre de comptadors',
      total: 1250.00,
      estat: 'APROVAT',
      data: '2026-09-02',
    },
  ])

  const [intervencions] = useState<IntervencioClient[]>([
    {
      id: 'ot-001',
      codi: 'OT-2026-089',
      titol: 'Revisió preventiva de la xarxa d\'evacuació',
      estat: 'FINALITZADA',
      data: '2026-09-15',
      adreca: 'Carrer de Mallorca, 234, Barcelona',
    },
    {
      id: 'ot-002',
      codi: 'OT-2026-104',
      titol: 'Instal·lació de vàlvules de retenció i antiretorn',
      estat: 'PLANIFICADA',
      data: '2026-09-28',
      adreca: 'Carrer de Mallorca, 234, Barcelona',
    },
  ])

  const [pestanyaActiva, setPestanyaActiva] = useState<'pressupostos' | 'obres' | 'canal'>('pressupostos')
  const [missatgeAccio, setMissatgeAccio] = useState<string | null>(null)

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault()
    if (codiAcces.trim().length >= 4) {
      setAutenticat(true)
      setErrorLogin('')
    } else {
      setErrorLogin('Introdueix un codi d\'accés o NIF vàlid (mínim 4 caràcters).')
    }
  }

  const handleAccioPressupost = (id: string, novaAccio: 'APROVAT' | 'REBUTJAT') => {
    setPressupostos((prev) =>
      prev.map((p) => (p.id === id ? { ...p, estat: novaAccio } : p))
    )
    setMissatgeAccio(
      novaAccio === 'APROVAT'
        ? '✅ Pressupost aprovat digitalment. El gestor d\'obra ha rebut la conformitat.'
        : '❌ Has rebutjat el pressupost. Ens posarem en contacte per revisar la proposta.'
    )
  }

  if (!autenticat) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4">
        <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex p-3 bg-blue-600/10 rounded-2xl border border-blue-500/20 text-blue-400 mb-2">
              <span className="material-symbols-outlined text-3xl">domain</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Portal d'Autoservei del Client</h1>
            <p className="text-sm text-slate-400">
              Accedeix als teus pressupostos, estat d'obres i canal transaccional privat.
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                NIF o Codi de Client
              </label>
              <input
                type="text"
                placeholder="ex: H-65498712 o CLI-001"
                value={codiAcces}
                onChange={(e) => setCodiAcces(e.target.value)}
                required
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm font-mono"
              />
              {errorLogin && <p className="text-xs text-rose-400 mt-1.5">{errorLogin}</p>}
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition shadow-lg shadow-blue-600/20"
            >
              Accedir al Portal
            </button>
          </form>

          <div className="text-center pt-2">
            <span className="text-xs text-slate-500">
              Canal Sobirà Xifrat d'Extrem a Extrem (RGPD / Hetzner UE)
            </span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Capçalera del Portal */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600/20 rounded-xl border border-blue-500/30 text-blue-400">
              <span className="material-symbols-outlined text-xl">domain</span>
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">{clientInfo.raoSocial}</h2>
              <p className="text-xs text-slate-400 font-mono">NIF: {clientInfo.nif} • {clientInfo.adreca}</p>
            </div>
          </div>
          <button
            onClick={() => setAutenticat(false)}
            className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
          >
            Tancar Sessió
          </button>
        </div>
      </header>

      {/* Contingut Principal */}
      <main className="max-w-6xl mx-auto p-6 space-y-6">
        {/* Banner Informatiu / Notificació */}
        {missatgeAccio && (
          <div className="p-4 rounded-2xl bg-blue-950/60 border border-blue-500/40 text-blue-200 text-sm flex items-center justify-between">
            <span>{missatgeAccio}</span>
            <button onClick={() => setMissatgeAccio(null)} className="text-blue-400 hover:text-white">
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          </div>
        )}

        {/* Pestanyes de Navegació */}
        <div className="flex border-b border-slate-800 gap-6">
          <button
            onClick={() => setPestanyaActiva('pressupostos')}
            className={`pb-3 text-sm font-semibold transition border-b-2 flex items-center gap-2 ${
              pestanyaActiva === 'pressupostos'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <span className="material-symbols-outlined text-base">request_quote</span>
            Pressupostos Pendents i Aprovats
          </button>
          <button
            onClick={() => setPestanyaActiva('obres')}
            className={`pb-3 text-sm font-semibold transition border-b-2 flex items-center gap-2 ${
              pestanyaActiva === 'obres'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <span className="material-symbols-outlined text-base">construction</span>
            Estat d'Intervencions i Obres
          </button>
          <button
            onClick={() => setPestanyaActiva('canal')}
            className={`pb-3 text-sm font-semibold transition border-b-2 flex items-center gap-2 ${
              pestanyaActiva === 'canal'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <span className="material-symbols-outlined text-base">send</span>
            Canal Telegram Transaccional
          </button>
        </div>

        {/* Pestanya: Pressupostos */}
        {pestanyaActiva === 'pressupostos' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
              Propostes Econòmiques
            </h3>
            <div className="grid gap-4 md:grid-cols-2">
              {pressupostos.map((p) => (
                <div
                  key={p.id}
                  className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-lg hover:border-slate-700 transition"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="font-mono text-xs text-blue-400 block mb-1">{p.numero}</span>
                      <h4 className="font-semibold text-white text-base">{p.titol}</h4>
                      <span className="text-xs text-slate-400 mt-1 block">Emès el {p.data}</span>
                    </div>
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                        p.estat === 'APROVAT'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : p.estat === 'REBUTJAT'
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}
                    >
                      {p.estat}
                    </span>
                  </div>

                  <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80 flex items-center justify-between">
                    <span className="text-xs text-slate-400">Total amb IVA:</span>
                    <span className="text-lg font-mono font-bold text-white">
                      {p.total.toFixed(2)} €
                    </span>
                  </div>

                  {p.estat === 'PENDENT' ? (
                    <div className="flex gap-2 pt-2">
                      <button
                        onClick={() => handleAccioPressupost(p.id, 'APROVAT')}
                        className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition"
                      >
                        Aprovar Digitalment
                      </button>
                      <button
                        onClick={() => handleAccioPressupost(p.id, 'REBUTJAT')}
                        className="flex-1 py-2 bg-slate-800 hover:bg-rose-950/60 hover:text-rose-400 text-slate-300 rounded-xl text-xs font-semibold transition border border-slate-700"
                      >
                        Rebutjar
                      </button>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 text-center italic pt-1">
                      {p.estat === 'APROVAT'
                        ? 'Aprovat i programat per a l\'execució.'
                        : 'Aquesta proposta s\'ha descartat.'}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Pestanya: Obres */}
        {pestanyaActiva === 'obres' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
              Seguiment de Treballs i Intervencions
            </h3>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-850 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="px-6 py-4">Codi OT</th>
                    <th className="px-6 py-4">Descripció</th>
                    <th className="px-6 py-4">Data Planificada</th>
                    <th className="px-6 py-4 text-center">Estat</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {intervencions.map((ot) => (
                    <tr key={ot.id} className="hover:bg-slate-850/50">
                      <td className="px-6 py-4 font-mono font-medium text-white">{ot.codi}</td>
                      <td className="px-6 py-4">
                        <div className="font-medium text-slate-200">{ot.titol}</div>
                        <div className="text-xs text-slate-400">{ot.adreca}</div>
                      </td>
                      <td className="px-6 py-4 font-mono text-xs">{ot.data}</td>
                      <td className="px-6 py-4 text-center">
                        <span
                          className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold ${
                            ot.estat === 'FINALITZADA'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                          }`}
                        >
                          {ot.estat}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Pestanya: Canal Telegram */}
        {pestanyaActiva === 'canal' && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-500/10 rounded-2xl border border-blue-500/20 text-blue-400">
                <span className="material-symbols-outlined text-3xl">send</span>
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Bot Transaccional de Telegram</h3>
                <p className="text-sm text-slate-400">
                  Aprova pressupostos amb un sol clic i rep avisos d'intervencions tècniques en temps real.
                </p>
              </div>
            </div>

            <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">Estat de vinculació:</span>
                <span className="text-emerald-400 font-semibold flex items-center gap-1">
                  <span className="material-symbols-outlined text-sm">check_circle</span> Actiu i Xifrat
                </span>
              </div>
              <p className="text-xs text-slate-500">
                El teu usuari de Telegram està autoritzat per rebre missatges d'Inline Keyboard i aprovar propostes econòmiques de forma vinculant.
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
