"use client";

import React from "react";
import { useAssignacions } from "@/lib/hooks/useAssignacions";
import { OrdreTreballLocal } from "@/lib/types/operari";

function AssignacioCard({ ordre }: { ordre: OrdreTreballLocal }) {
  return (
    <div className="bg-white rounded-lg shadow p-4 mb-4 border-l-4" style={{ borderColor: 'var(--color-primary, #0f172a)' }}>
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-semibold text-lg" style={{ color: 'var(--color-foreground, #000)' }}>
          {ordre.titol}
        </h3>
        <span className="text-xs px-2 py-1 rounded font-medium" style={{ backgroundColor: 'var(--color-muted, #e2e8f0)', color: 'var(--color-foreground, #000)' }}>
          {ordre.codi}
        </span>
      </div>
      <p className="text-sm mb-3" style={{ color: 'var(--color-muted-foreground, #64748b)' }}>
        {ordre.client_nom || "Client no especificat"}
      </p>
      {ordre.descripcio && (
        <p className="text-sm mb-3 line-clamp-2" style={{ color: 'var(--color-foreground, #000)' }}>
          {ordre.descripcio}
        </p>
      )}
      <div className="flex justify-between items-center text-xs" style={{ color: 'var(--color-muted-foreground, #64748b)' }}>
        <span>🗓 {new Date(ordre.data_programada).toLocaleDateString()}</span>
        <button 
          className="px-3 py-1.5 rounded font-medium transition-opacity hover:opacity-90 active:opacity-80"
          style={{ backgroundColor: 'var(--color-primary, #0f172a)', color: 'var(--color-primary-foreground, #fff)' }}
        >
          Obrir Feina
        </button>
      </div>
    </div>
  );
}

export default function FeinesKanbanPage() {
  const { ordres, loading, error, refetch } = useAssignacions();

  const pendents = ordres.filter(o => ["PENDENT", "PAUSADA"].includes(o.estat_local));
  const enCurs = ordres.filter(o => ["EN_TRANSIT", "EN_CURS"].includes(o.estat_local));

  return (
    <div className="min-h-screen pb-20" style={{ backgroundColor: 'var(--color-background, #f8fafc)' }}>
      {/* Header */}
      <header className="px-4 py-6 shadow-sm sticky top-0 z-10" style={{ backgroundColor: 'var(--color-surface, #fff)' }}>
        <h1 className="text-2xl font-bold" style={{ color: 'var(--color-primary, #0f172a)' }}>
          Tauler de Feines
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--color-muted-foreground, #64748b)' }}>
          Gestiona les teves assignacions diàries
        </p>
      </header>

      {/* Main Content */}
      <main className="p-4 max-w-md mx-auto">
        {loading && ordres.length === 0 ? (
          <div className="flex justify-center items-center h-48">
            <p className="animate-pulse" style={{ color: 'var(--color-muted-foreground, #64748b)' }}>
              Carregant assignacions...
            </p>
          </div>
        ) : error ? (
          <div className="p-4 rounded-lg mb-6 border" style={{ backgroundColor: 'var(--color-destructive-muted, #fee2e2)', borderColor: 'var(--color-destructive, #ef4444)', color: 'var(--color-destructive, #ef4444)' }}>
            <h2 className="font-semibold mb-1">Error de connexió</h2>
            <p className="text-sm mb-3">{error}</p>
            <button 
              onClick={refetch}
              className="px-4 py-2 rounded text-sm font-medium"
              style={{ backgroundColor: 'var(--color-background, #fff)', color: 'var(--color-destructive, #ef4444)', border: '1px solid var(--color-destructive, #ef4444)' }}
            >
              Tornar a provar
            </button>
          </div>
        ) : ordres.length === 0 ? (
          // ZERO MOCK DATA - Empty State
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center rounded-xl border-2 border-dashed" style={{ borderColor: 'var(--color-border, #cbd5e1)', backgroundColor: 'var(--color-surface, #fff)' }}>
            <div className="text-4xl mb-4" role="img" aria-label="Buit">📋</div>
            <h2 className="text-lg font-semibold mb-2" style={{ color: 'var(--color-foreground, #000)' }}>Cap tasca assignada avui</h2>
            <p className="text-sm mb-6" style={{ color: 'var(--color-muted-foreground, #64748b)' }}>
              No tens cap ordre de treball programada. Pots revisar de nou més tard.
            </p>
            <button 
              onClick={refetch}
              className="px-5 py-2.5 rounded-lg font-medium transition-opacity"
              style={{ backgroundColor: 'var(--color-secondary, #334155)', color: 'var(--color-secondary-foreground, #fff)' }}
            >
              Refrescar
            </button>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Column: En Curs */}
            <section>
              <h2 className="text-sm font-bold uppercase tracking-wider mb-4 flex items-center gap-2" style={{ color: 'var(--color-primary, #0f172a)' }}>
                <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: 'var(--color-accent, #10b981)' }}></span>
                En Curs ({enCurs.length})
              </h2>
              {enCurs.length > 0 ? (
                enCurs.map(ordre => <AssignacioCard key={ordre.id} ordre={ordre} />)
              ) : (
                <div className="p-4 rounded-lg text-sm text-center border border-dashed" style={{ borderColor: 'var(--color-border, #cbd5e1)', color: 'var(--color-muted-foreground, #64748b)' }}>
                  Cap feina activa en aquest moment.
                </div>
              )}
            </section>

            {/* Column: Pendents */}
            <section>
              <h2 className="text-sm font-bold uppercase tracking-wider mb-4" style={{ color: 'var(--color-muted-foreground, #64748b)' }}>
                Pendents ({pendents.length})
              </h2>
              {pendents.length > 0 ? (
                pendents.map(ordre => <AssignacioCard key={ordre.id} ordre={ordre} />)
              ) : (
                <div className="p-4 rounded-lg text-sm text-center border border-dashed" style={{ borderColor: 'var(--color-border, #cbd5e1)', color: 'var(--color-muted-foreground, #64748b)' }}>
                  No queden tasques pendents.
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}