"use client";

import dynamic from 'next/dynamic';
import { useState, useEffect } from 'react';

// Càrrega asíncrona per evitar errors SSR amb l'objecte window (necessari per Leaflet)
const MapWithNoSSR = dynamic(() => import('@/components/gestio/Map'), {
  ssr: false,
  loading: () => <div className="w-full h-full flex items-center justify-center bg-slate-800 text-slate-400">Carregant mapa cartogràfic...</div>
});

export default function MapaGISPage() {
  const [markers, setMarkers] = useState<any[]>([]);
  const [incidenciesDrawerOpen, setIncidenciesDrawerOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Càrrega de dades reals d'Ordres de Treball i Incidències des de la Torre de Control GIS
  useEffect(() => {
    const fetchMarkers = async () => {
      try {
        setLoading(true);
        const token = localStorage.getItem('sevalor_token') || localStorage.getItem('token') || '';
        const tenant = process.env.NEXT_PUBLIC_TENANT_ID || localStorage.getItem('empresa_id') || '';

        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        if (tenant) headers['X-Empresa-ID'] = tenant;

        const res = await fetch('/api/v1/gestio/feines/mapa', { headers });
        if (res.ok) {
          const data = await res.json();
          const mapped = data.map((item: any) => ({
            id: item.id,
            lat: item.lat,
            lng: item.lng,
            title: `${item.codi} - ${item.titol}${item.client_rao_social ? ` (${item.client_rao_social})` : ''}`,
            status: item.estat,
            isIncidencia: item.is_incidencia,
            adreca: item.adreca,
            client_rao_social: item.client_rao_social,
          }));
          setMarkers(mapped);
        } else {
          // Si no hi ha resposta positiva, mantenir estat buit
          setMarkers([]);
        }
      } catch (err: any) {
        console.error("Error carregant marcadors del mapa:", err);
        setError(err.message);
        setMarkers([]);
      } finally {
        setLoading(false);
      }
    };

    fetchMarkers();
  }, []);

  return (
    <div className="flex h-[calc(100vh-8rem)] relative">
      {/* Zona principal del Mapa */}
      <div className="flex-1 bg-slate-800 rounded-2xl overflow-hidden border border-slate-700 relative">
        <MapWithNoSSR markers={markers} />
        
        {/* Controls Overlay */}
        <div className="absolute top-4 right-4 z-[400] flex flex-col gap-2">
          <button 
            onClick={() => setIncidenciesDrawerOpen(!incidenciesDrawerOpen)}
            className="bg-slate-900/90 text-white p-3 rounded-lg shadow-lg border border-slate-700 hover:bg-slate-800 flex items-center transition-all"
          >
            <span className="material-symbols-outlined mr-2 text-blue-400">memory</span>
            Alertes Copilot
            {markers.filter(m => m.isIncidencia).length > 0 && (
              <span className="ml-2 bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                {markers.filter(m => m.isIncidencia).length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Drawer Lateral del Copilot (Memoràndums Pericials) */}
      {incidenciesDrawerOpen && (
        <div className="w-96 bg-slate-900 border-l border-slate-700 p-6 flex flex-col ml-4 rounded-2xl overflow-y-auto">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold text-white flex items-center">
              <span className="material-symbols-outlined mr-2 text-blue-400">memory</span>
              Copilot Drawer
            </h2>
            <button onClick={() => setIncidenciesDrawerOpen(false)} className="text-slate-400 hover:text-white">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>

          {/* Estat buit real (Zero Mock Data) */}
          <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700 text-center">
            <span className="material-symbols-outlined text-3xl text-slate-500 mb-2">inbox</span>
            <p className="text-sm text-slate-400">Sense alertes d'incidència pendents de revisió.</p>
          </div>
        </div>
      )}
    </div>
  );
}
