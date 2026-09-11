'use client'

import { useState, useEffect } from 'react'

interface Article {
  id: string
  codi_barres: string
  nom: string
  quantitat: number
  stock_minim: number
  unitat_mesura: string
  referencia_inventari: string
}

export default function MagatzemPage() {
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [newCodi, setNewCodi] = useState('')
  const [newRef, setNewRef] = useState('')
  const [newNom, setNewNom] = useState('')
  const [newQuantitat, setNewQuantitat] = useState(0)
  const [newMinim, setNewMinim] = useState(0)
  const [newUnitat, setNewUnitat] = useState('UNITAT')

  const fetchArticles = async () => {
    try {
      const res = await fetch('/api/v1/gestio/magatzem/articles', {
        headers: {
          'X-Empresa-ID': process.env.NEXT_PUBLIC_TENANT_ID || ''
        }
      })
      if (!res.ok) throw new Error('Error carregant articles del magatzem')
      const data = await res.json()
      setArticles(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchArticles()
  }, [])

  const handleCreateArticle = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await fetch('/api/v1/gestio/magatzem/articles', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Empresa-ID': process.env.NEXT_PUBLIC_TENANT_ID || ''
        },
        body: JSON.stringify({ 
          codi_barres: newCodi,
          referencia_inventari: newRef,
          nom: newNom,
          quantitat: Number(newQuantitat),
          stock_minim: Number(newMinim),
          unitat_mesura: newUnitat
        })
      })
      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'Error al donar d\'alta l\'article')
      }
      
      setShowModal(false)
      setNewCodi('')
      setNewRef('')
      setNewNom('')
      setNewQuantitat(0)
      setNewMinim(0)
      setNewUnitat('UNITATS')
      fetchArticles()
    } catch (err: any) {
      alert(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-white">Inventari del Magatzem</h1>
        <button 
          onClick={() => setShowModal(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          <span className="material-symbols-outlined text-sm">inventory_2</span>
          Alta Article
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
              <th className="px-6 py-4">Ref. / EAN</th>
              <th className="px-6 py-4">Article</th>
              <th className="px-6 py-4 text-right">Stock Actual</th>
              <th className="px-6 py-4 text-right">Límit Seguretat</th>
              <th className="px-6 py-4 text-right">Estat</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                  <span className="material-symbols-outlined animate-spin text-3xl">refresh</span>
                  <p className="mt-2">Sincronitzant inventari...</p>
                </td>
              </tr>
            ) : articles.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                  L'inventari està buit. No hi ha articles registrats.
                </td>
              </tr>
            ) : (
              articles.map(art => {
                const isLowStock = art.quantitat <= art.stock_minim;
                return (
                  <tr key={art.id} className="hover:bg-slate-700/30 transition-colors">
                    <td className="px-6 py-4 font-mono text-xs">{art.referencia_inventari}<br/>{art.codi_barres}</td>
                    <td className="px-6 py-4 font-medium text-white">{art.nom}</td>
                    <td className={`px-6 py-4 text-right font-bold ${isLowStock ? 'text-red-400' : 'text-slate-200'}`}>
                      {art.quantitat} <span className="text-slate-500 text-xs font-normal">{art.unitat_mesura}</span>
                    </td>
                    <td className="px-6 py-4 text-right text-slate-400">{art.stock_minim}</td>
                    <td className="px-6 py-4 text-right">
                      {isLowStock ? (
                        <span className="bg-red-500/20 text-red-400 border border-red-500/50 px-2 py-1 rounded text-xs">REPOSAR</span>
                      ) : (
                        <span className="bg-green-500/20 text-green-400 border border-green-500/50 px-2 py-1 rounded text-xs">OK</span>
                      )}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl shadow-xl w-full max-w-lg overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b border-slate-700">
              <h3 className="text-lg font-bold text-white">Registre de Nou Article</h3>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <form onSubmit={handleCreateArticle} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Nom de l'article</label>
                  <input 
                    type="text" required
                    value={newNom} onChange={(e) => setNewNom(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                    placeholder="Ex: Tub de coure 15mm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Referència (Interna)</label>
                  <input 
                    type="text" required
                    value={newRef} onChange={(e) => setNewRef(e.target.value.toUpperCase())}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 font-mono uppercase"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Codi de Barres / SKU</label>
                  <input 
                    type="text"
                    value={newCodi} onChange={(e) => setNewCodi(e.target.value.toUpperCase())}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 font-mono uppercase"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Unitat de Mesura</label>
                  <select 
                    value={newUnitat} onChange={(e) => setNewUnitat(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="UNITAT">Unitats</option>
                    <option value="KG">Quilograms (Kg)</option>
                    <option value="LITRES">Litres (L)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Stock Inicial</label>
                  <input 
                    type="number" required min="0" step="0.01"
                    value={newQuantitat} onChange={(e) => setNewQuantitat(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Alerta de Reposició (Mínim)</label>
                  <input 
                    type="number" required min="0" step="0.01"
                    value={newMinim} onChange={(e) => setNewMinim(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
              <div className="pt-4 flex justify-end gap-3">
                <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 rounded-lg font-medium text-slate-300 hover:bg-slate-700 transition">
                  Cancel·lar
                </button>
                <button type="submit" className="bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-lg font-medium text-white transition">
                  Registrar al Magatzem
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
