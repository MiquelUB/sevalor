import re

with open("pwa/src/app/gestio/page.tsx", "r") as f:
    content = f.read()

# 1. Update the 'Crear Ordre de Treball' button to use an onClick alert instead of a broken Link
content = content.replace(
'''        <Link 
          href="/gestio/feines/crear" 
          className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold shadow-sm flex items-center gap-2 transition-all"
        >
          <Wrench className="w-4 h-4" />
          Crear Ordre de Treball
        </Link>''',
'''        <button 
          onClick={() => alert('Mòdul de Creació d\\'OT en desenvolupament (Proper Sprint)')}
          className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold shadow-sm flex items-center gap-2 transition-all cursor-pointer"
        >
          <Wrench className="w-4 h-4" />
          Crear Ordre de Treball
        </button>'''
)

# 2. Update KPI wrappers to Link components
content = content.replace(
'''        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider mb-1">Cuadrilles Actives</p>''',
'''        <Link href="/gestio/operaris" className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between hover:border-emerald-500 transition-colors cursor-pointer block">
          <div>
            <p className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider mb-1">Cuadrilles Actives</p>'''
)
content = content.replace(
'''          <div className="w-10 h-10 rounded-full bg-emerald-50 dark:bg-emerald-900/20 flex items-center justify-center">
            <Users className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          </div>
        </div>

        {/* Órdenes de Trabajo */}''',
'''          <div className="w-10 h-10 rounded-full bg-emerald-50 dark:bg-emerald-900/20 flex items-center justify-center">
            <Users className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          </div>
        </Link>

        {/* Órdenes de Trabajo */}'''
)

content = content.replace(
'''        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider mb-1">Feines d'Avui</p>''',
'''        <Link href="/gestio/mapa" className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between hover:border-blue-500 transition-colors cursor-pointer block">
          <div>
            <p className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider mb-1">Feines d'Avui</p>'''
)
content = content.replace(
'''          <div className="w-10 h-10 rounded-full bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          </div>
        </div>

        {/* Incidencias Urgentes */}''',
'''          <div className="w-10 h-10 rounded-full bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          </div>
        </Link>

        {/* Incidencias Urgentes */}'''
)

content = content.replace(
'''        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-red-200 dark:border-red-900/50 shadow-sm flex items-center justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 w-16 h-16 bg-red-500/10 rounded-bl-full -mr-4 -mt-4 animate-pulse"></div>
          <div>
            <p className="text-[10px] font-mono font-bold text-red-500 uppercase tracking-wider mb-1">Incidències Obra</p>''',
'''        <Link href="/gestio/notificacions" className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-red-200 dark:border-red-900/50 shadow-sm flex items-center justify-between relative overflow-hidden hover:border-red-500 transition-colors cursor-pointer block">
          <div className="absolute top-0 right-0 w-16 h-16 bg-red-500/10 rounded-bl-full -mr-4 -mt-4 animate-pulse"></div>
          <div>
            <p className="text-[10px] font-mono font-bold text-red-500 uppercase tracking-wider mb-1">Incidències Obra</p>'''
)
content = content.replace(
'''          <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" />
          </div>
        </div>

        {/* Estado Flota */}''',
'''          <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" />
          </div>
        </Link>

        {/* Estado Flota */}'''
)

content = content.replace(
'''        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider mb-1">Estat Flota</p>''',
'''        <Link href="/gestio/flota" className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between hover:border-slate-500 transition-colors cursor-pointer block">
          <div>
            <p className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider mb-1">Estat Flota</p>'''
)
content = content.replace(
'''          <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
            <Truck className="w-5 h-5 text-slate-600 dark:text-slate-300" />
          </div>
        </div>

        {/* Alertas Preventivas */}''',
'''          <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
            <Truck className="w-5 h-5 text-slate-600 dark:text-slate-300" />
          </div>
        </Link>

        {/* Alertas Preventivas */}'''
)

content = content.replace(
'''        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/50 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono font-bold text-amber-600 uppercase tracking-wider mb-1">Alertes Tècniques</p>''',
'''        <Link href="/gestio/magatzem" className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/50 shadow-sm flex items-center justify-between hover:border-amber-500 transition-colors cursor-pointer block">
          <div>
            <p className="text-[10px] font-mono font-bold text-amber-600 uppercase tracking-wider mb-1">Alertes Tècniques</p>'''
)
content = content.replace(
'''          <div className="w-10 h-10 rounded-full bg-amber-50 dark:bg-amber-900/20 flex items-center justify-center">
            <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400" />
          </div>
        </div>
      </div>''',
'''          <div className="w-10 h-10 rounded-full bg-amber-50 dark:bg-amber-900/20 flex items-center justify-center">
            <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400" />
          </div>
        </Link>
      </div>'''
)

with open("pwa/src/app/gestio/page.tsx", "w") as f:
    f.write(content)

print("Patch applied to pwa/src/app/gestio/page.tsx")
