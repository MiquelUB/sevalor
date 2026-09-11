'use client'

import { useState } from 'react'

export default function PwaLogin() {
  const [nif, setNif] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

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
      alert('Login Correcte! Benvingut ' + data.usuari.nom)
      
    } catch (err: any) {
      setError(err.message)
      setPin('') // Reset PIN on error
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="fixed inset-0 z-0 pointer-events-none opacity-5" style={{ backgroundImage: 'url(https://lh3.googleusercontent.com/aida-public/AB6AXuDhTi5zkGgq31cC-nkuI-iBk82imE_Mt4rHtU7pSPSd6h52epzLq-z2O_fnkdLUzMUAiQtND3dWFNpaoqPEDd9193rd1wW8HQUo7LIT37pQxlZpIondF7eqcbDFBXSiFvW98WQETyukYVh-haSuAZ-j7sO1WQmr20-6MfPpFQyKeGfb7KI64w6_ob96lBfmUM4GsNUvBqiBZRQSG3ILpQ34dn7exvxquDAHyyQC5ysdywyiHqwLIu3Htyujyx4GXbT6_3eqCg-D_a4I)' }}></div>
      <div className="relative z-10 flex flex-col min-h-[100dvh] max-w-[480px] mx-auto overflow-x-hidden">
        
        {/* TopAppBar */}
        <div className="flex items-center bg-background-dark p-4 pb-2 justify-between">
          <span className="material-symbols-outlined text-primary">menu</span>
          <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex-1 text-center italic">CampoPro</h2>
          <span className="material-symbols-outlined text-primary">account_balance</span>
        </div>

        {/* HeaderImage */}
        <div className="w-full bg-center bg-no-repeat bg-cover flex flex-col justify-end overflow-hidden bg-forest-deep min-h-[180px] border-b-2 border-primary/30" style={{ backgroundImage: 'linear-gradient(to bottom, transparent, rgba(16,34,16,0.9)), url("https://lh3.googleusercontent.com/aida-public/AB6AXuDX4Zcud1ZfLGaHoslPb_nvEbFfI2OcOe2uWbEhSAdr37mOm_KDmaIeqBH2uIRb_cnETW1fEvhh_zcREnqsh8hBD1Yvo7CX21rDKPwof3oiJ5nzlAu3Gv9jGIMNgESTyP-1Fj4SzBeRVYM0PHeWTNm0MVK8g9xOJR1ruLAotSagFIYbTMrol9NE18FXSf-uOFjSl82FQCgpQsNo9D0K2SVL7gY2cRPm_Nkwa8uG5-SHPRbCIBeIQfQ4zYLfIa-NPTt0gHLwBtIORYhx")' }}>
          <div className="p-4">
            <div className="flex items-center gap-2 text-primary">
              <span className="material-symbols-outlined text-sm">location_on</span>
              <p className="text-xs uppercase tracking-widest font-bold">Portal Operatiu</p>
            </div>
          </div>
        </div>

        {/* HeadlineText */}
        <div className="relative px-6 py-4 mt-2">
          <div className="absolute inset-x-6 top-0 border-t border-primary/20"></div>
          <h1 className="text-white tracking-tight text-[32px] font-bold leading-tight text-center pt-4">Inici de Jornada</h1>
          <div className="flex justify-center items-center gap-4 py-2">
            <div className="h-[1px] w-12 bg-primary/40"></div>
            <span className="material-symbols-outlined text-primary/60 text-lg">history_edu</span>
            <div className="h-[1px] w-12 bg-primary/40"></div>
          </div>
        </div>

        {/* BodyText */}
        <p className="text-primary/80 text-sm font-normal leading-normal pb-4 pt-1 px-8 text-center italic">
          Registre oficial per a l'assignació tàctica.
        </p>

        {error && (
          <div className="mx-6 bg-red-500/10 border border-red-500/50 text-red-400 text-sm p-3 rounded-lg mb-2 text-center font-sans">
            {error}
          </div>
        )}

        {/* Form Section */}
        <div className="px-6 space-y-4 flex-1">
          {/* TextField: Username */}
          <div className="flex flex-col gap-1 py-2 group">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary/60 text-sm">person_edit</span>
              <p className="text-primary/90 text-xs font-bold uppercase tracking-widest">Identificador (NIF/NIE)</p>
            </div>
            <div className="relative">
              <input 
                type="text"
                value={nif}
                onChange={(e) => setNif(e.target.value.toUpperCase())}
                disabled={loading}
                className="w-full border-0 border-b-2 border-slate-accent bg-transparent focus:ring-0 focus:border-primary h-12 text-white placeholder:text-white/20 p-0 text-lg font-normal italic uppercase outline-none"
                placeholder="Ex: 12345678A"
              />
            </div>
          </div>

          {/* PIN Input Visualization */}
          <div className="flex flex-col gap-2 py-2">
            <div className="flex items-center gap-2 justify-center">
              <span className="material-symbols-outlined text-primary/60 text-sm">lock</span>
              <p className="text-primary/90 text-xs font-bold uppercase tracking-widest">PIN de Seguretat</p>
            </div>
            <div className="flex justify-center gap-4 mt-2">
              {[0,1,2,3].map(i => (
                <div 
                  key={i} 
                  className={`w-12 h-14 rounded flex items-center justify-center text-2xl font-bold border-b-2 transition-colors ${
                    pin[i] 
                      ? 'border-primary text-primary bg-primary/10' 
                      : 'border-slate-accent text-transparent bg-slate-accent/20'
                  }`}
                >
                  {pin[i] ? '•' : ''}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Custom Numpad */}
        <div className="px-6 pb-8 pt-4 bg-background-dark/80 backdrop-blur-sm border-t border-slate-accent">
          <div className="grid grid-cols-3 gap-3 font-sans">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(num => (
              <button
                key={num}
                onClick={() => handleNumpad(num.toString())}
                disabled={loading || pin.length >= 4}
                className="bg-slate-accent/30 hover:bg-slate-accent/50 active:bg-primary/20 text-white text-xl py-4 rounded transition-colors disabled:opacity-50 border border-slate-accent/50"
              >
                {num}
              </button>
            ))}
            <button
              onClick={handleDelete}
              disabled={loading || pin.length === 0}
              className="bg-slate-accent/30 hover:bg-slate-accent/50 text-primary/60 py-4 rounded transition-colors disabled:opacity-50 flex items-center justify-center border border-slate-accent/50"
            >
              <span className="material-symbols-outlined">backspace</span>
            </button>
            <button
              onClick={() => handleNumpad('0')}
              disabled={loading || pin.length >= 4}
              className="bg-slate-accent/30 hover:bg-slate-accent/50 active:bg-primary/20 text-white text-xl py-4 rounded transition-colors disabled:opacity-50 border border-slate-accent/50"
            >
              0
            </button>
            <button
              onClick={handleLogin}
              disabled={loading || pin.length !== 4 || !nif}
              className="bg-primary hover:bg-primary/90 text-background-dark font-bold py-4 rounded transition-colors disabled:opacity-50 disabled:bg-slate-accent/50 flex items-center justify-center border border-primary/50"
            >
              {loading ? (
                 <span className="material-symbols-outlined animate-spin">refresh</span>
              ) : 'ENTRAR'}
            </button>
          </div>
        </div>

      </div>
    </>
  )
}
