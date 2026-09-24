export default function DashboardIndex() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
        <h3 className="text-slate-400 text-sm font-medium uppercase tracking-wider mb-2">Total Clients</h3>
        <p className="text-4xl font-bold text-white">--</p>
      </div>
      <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
        <h3 className="text-slate-400 text-sm font-medium uppercase tracking-wider mb-2">Ordres de Treball Actives</h3>
        <p className="text-4xl font-bold text-blue-400">--</p>
      </div>
      <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
        <h3 className="text-slate-400 text-sm font-medium uppercase tracking-wider mb-2">Operaris al Camp</h3>
        <p className="text-4xl font-bold text-green-400">--</p>
      </div>
    </div>
  )
}
