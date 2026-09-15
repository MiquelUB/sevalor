'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function PwaLogin() {
  const [nif, setNif] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const handleNumpad = (digit: string) => {
    if (pin.length < 4) {
      setPin(prev => prev + digit)
    }
  }

  const handleDelete = () => {
    setPin(prev => prev.slice(0, -1))
  }

  const handleLogin = async () => {
    if (!nif || pin.length !== 4) {
      setError('Introdueix NIF i un PIN de 4 dígits')
      return
    }
    setLoading(true)
    setError('')
    
    try {
      // In Phase 1 real implementation, this connects to the FastAPI backend
      const res = await fetch('/api/v1/operari_auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Empresa-ID': process.env.NEXT_PUBLIC_TENANT_ID || '' // Placeholder for tenant resolution
        },
        body: JSON.stringify({ nif, pin })
      })

      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'Credencials invàlides')
      }
      
      const data = await res.json()
      localStorage.setItem('sevalor_token', data.access_token)
      router.push('/dashboard')
      
    } catch (err: any) {
      setError(err.message)
      setPin('') // Reset PIN on error
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-slate-800 rounded-3xl p-8 shadow-2xl border border-slate-700">
        
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-500 rounded-2xl mx-auto flex items-center justify-center shadow-lg shadow-blue-500/30 mb-4">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Accés Sevalor</h1>
          <p className="text-slate-400 mt-2 text-sm">Panell de Control</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/50 rounded-xl text-red-500 text-sm text-center font-medium">
            {error}
          </div>
        )}

        <div className="space-y-6">
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider ml-1">NIF</label>
            <input
              type="text"
              value={nif}
              onChange={(e) => setNif(e.target.value.toUpperCase())}
              placeholder="Ex: 12345678A"
              className="w-full bg-slate-900 border-2 border-slate-700 text-white rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors uppercase placeholder:normal-case placeholder:text-slate-600 font-medium"
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider ml-1">PIN (4 dígits)</label>
            <div className="flex justify-center gap-4 py-2">
              {[0, 1, 2, 3].map((i) => (
                <div 
                  key={i} 
                  className={`w-4 h-4 rounded-full transition-all duration-200 ${
                    pin.length > i 
                      ? 'bg-blue-500 shadow-[0_0_12px_rgba(59,130,246,0.6)]' 
                      : 'bg-slate-700'
                  }`}
                />
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 pt-2">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((num) => (
              <button
                key={num}
                onClick={() => handleNumpad(num.toString())}
                className="h-14 bg-slate-700/50 hover:bg-slate-700 rounded-xl text-white font-semibold text-xl transition-all active:scale-95"
              >
                {num}
              </button>
            ))}
            <button
              onClick={handleDelete}
              className="h-14 bg-slate-700/30 hover:bg-slate-700/50 rounded-xl text-slate-400 font-semibold text-xl flex items-center justify-center transition-all active:scale-95"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z" />
              </svg>
            </button>
            <button
              onClick={() => handleNumpad('0')}
              className="h-14 bg-slate-700/50 hover:bg-slate-700 rounded-xl text-white font-semibold text-xl transition-all active:scale-95"
            >
              0
            </button>
            <button
              onClick={handleLogin}
              disabled={loading}
              className="h-14 bg-blue-600 hover:bg-blue-500 rounded-xl text-white font-bold text-sm transition-all active:scale-95 disabled:opacity-50 disabled:active:scale-100 flex items-center justify-center"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                'ENTRAR'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}