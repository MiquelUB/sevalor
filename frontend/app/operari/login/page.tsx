'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function OperariLogin() {
  const router = useRouter()
  
  const [step, setStep] = useState(1)
  const [nif, setNif] = useState('')
  const [pin, setPin] = useState('')
  
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleNifSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!nif.trim()) return
    setStep(2)
    setError('')
  }

  const handleKeypad = (num: string) => {
    if (pin.length < 4) {
      const newPin = pin + num
      setPin(newPin)
      if (newPin.length === 4) {
        // Auto-submit when 4 digits are reached
        executeLogin(newPin)
      }
    }
  }

  const handleBackspace = () => {
    setPin(prev => prev.slice(0, -1))
  }

  const executeLogin = async (currentPin: string) => {
    setLoading(true)
    setError('')
    try {
      const tenant = process.env.NEXT_PUBLIC_TENANT_ID || ''
      const res = await fetch('/api/v1/operari_auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Empresa-ID': tenant
        },
        body: JSON.stringify({ nif: nif.toUpperCase(), pin: currentPin })
      })

      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'Error d\'accés')
      }

      const data = await res.json()
      // Guardar token al localStorage per les posteriors peticions PWA
      localStorage.setItem('operari_token', data.access_token)
      localStorage.setItem('operari_data', JSON.stringify(data.usuari))
      
      router.push('/operari')
    } catch (err: any) {
      setError(err.message)
      setPin('') // Reset pin on error
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6 py-12">
      <div className="text-center mb-12">
        <h1 className="text-3xl font-black text-blue-500 tracking-tight">Sevalor <span className="text-white">PWA</span></h1>
        <p className="text-slate-400 text-sm mt-2 font-medium uppercase tracking-widest">Portal de l'Operari</p>
      </div>

      <div className="w-full max-w-sm">
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded-xl text-center mb-6 text-sm font-medium animate-pulse">
            {error}
          </div>
        )}

        {step === 1 && (
          <form onSubmit={handleNifSubmit} className="space-y-6">
            <div>
              <label className="block text-center text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
                Introdueix el teu NIF/NIE
              </label>
              <input 
                type="text" 
                value={nif} 
                onChange={(e) => setNif(e.target.value.toUpperCase())}
                placeholder="Ex: 12345678A"
                className="w-full bg-slate-800 border-2 border-slate-700 rounded-2xl px-6 py-4 text-center text-2xl font-bold text-white focus:outline-none focus:border-blue-500 transition-colors uppercase"
                autoFocus
                required
              />
            </div>
            <button 
              type="submit"
              disabled={!nif.trim()}
              className="w-full bg-blue-600 disabled:bg-slate-800 disabled:text-slate-500 hover:bg-blue-500 text-white font-bold py-4 rounded-2xl text-lg transition-colors"
            >
              Continuar
            </button>
          </form>
        )}

        {step === 2 && (
          <div className="space-y-8 animate-in fade-in slide-in-from-right-4 duration-300">
            <div className="text-center">
              <p className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">NIF: <span className="text-white">{nif}</span></p>
              <button onClick={() => { setStep(1); setPin(''); setError(''); }} className="text-blue-400 text-xs hover:underline">Canviar usuari</button>
            </div>

            <div>
              <label className="block text-center text-sm font-semibold text-slate-400 uppercase tracking-wider mb-6">
                Codi PIN
              </label>
              
              {/* Display PIN dots */}
              <div className="flex justify-center gap-4 mb-10">
                {[...Array(4)].map((_, i) => (
                  <div 
                    key={i} 
                    className={`w-5 h-5 rounded-full transition-all duration-200 ${i < pin.length ? 'bg-blue-500 scale-110 shadow-[0_0_15px_rgba(59,130,246,0.5)]' : 'bg-slate-700'}`}
                  ></div>
                ))}
              </div>

              {/* Numeric Keypad */}
              <div className="grid grid-cols-3 gap-4 max-w-[280px] mx-auto">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(num => (
                  <button 
                    key={num}
                    onClick={() => handleKeypad(num.toString())}
                    className="h-16 bg-slate-800 hover:bg-slate-700 active:bg-slate-600 rounded-2xl text-2xl font-bold text-white shadow-sm border border-slate-700/50 flex items-center justify-center transition-colors"
                    disabled={loading}
                  >
                    {num}
                  </button>
                ))}
                <div className="h-16"></div> {/* Empty space */}
                <button 
                  onClick={() => handleKeypad('0')}
                  className="h-16 bg-slate-800 hover:bg-slate-700 active:bg-slate-600 rounded-2xl text-2xl font-bold text-white shadow-sm border border-slate-700/50 flex items-center justify-center transition-colors"
                  disabled={loading}
                >
                  0
                </button>
                <button 
                  onClick={handleBackspace}
                  className="h-16 bg-slate-800/50 hover:bg-slate-700 active:bg-red-900/40 rounded-2xl text-slate-400 shadow-sm border border-slate-700/30 flex items-center justify-center transition-colors"
                  disabled={loading || pin.length === 0}
                >
                  <span className="material-symbols-outlined text-3xl">backspace</span>
                </button>
              </div>
            </div>

            {loading && (
              <div className="text-center text-blue-400 flex items-center justify-center gap-2">
                <span className="material-symbols-outlined animate-spin">refresh</span>
                Validant accés...
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
