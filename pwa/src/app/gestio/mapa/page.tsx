"use client";

import React, { useState, useEffect } from "react";
import {
  Compass,
  MapPin,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Briefcase,
  Users,
  Search,
  Check
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch } from "@/lib/api";

interface Feina {
  id: string;
  codi: string;
  titol: string;
  estat: string;
  adreca: string;
  versio: number;
  cap_de_colla_id?: string | null;
}

interface Operari {
  id: string;
  nom: string;
  cognoms: string;
  rol: string;
  estat: string;
}

export default function GestioMapaPage() {
  const { rolActiu } = useGestio();
  const [modeVisor, setModeVisor] = useState<"SAT" | "TOPO">("SAT");
  const [feines, setFeines] = useState<Feina[]>([]);
  const [operaris, setOperaris] = useState<Operari[]>([]);
  const [loading, setLoading] = useState(true);
  const [draggingId, setDraggingId] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [feinesData, operarisData] = await Promise.all([
        apiFetch<Feina[]>("/gestio/feines?limit=100"),
        apiFetch<Operari[]>("/gestio/operaris")
      ]);
      setFeines(feinesData);
      setOperaris(operarisData.filter(o => o.rol === "OPERARI" && o.estat === "ACTIU"));
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleDragStart = (e: React.DragEvent, feina: Feina) => {
    e.dataTransfer.setData("feinaId", feina.id);
    e.dataTransfer.setData("versio", feina.versio.toString());
    setDraggingId(feina.id);
  };

  const handleDragEnd = () => {
    setDraggingId(null);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = async (e: React.DragEvent, operariId: string) => {
    e.preventDefault();
    const feinaId = e.dataTransfer.getData("feinaId");
    const versioStr = e.dataTransfer.getData("versio");
    if (!feinaId || !versioStr) return;

    try {
      await apiFetch(`/gestio/feines/${feinaId}/drop-and-go`, {
        method: "PATCH",
        body: JSON.stringify({
          versio: parseInt(versioStr, 10),
          cap_de_colla_id: operariId,
          data_programada: new Date().toISOString().split("T")[0]
        })
      });
      // Update local state to reflect assignment
      setFeines(prev => prev.map(f => f.id === feinaId ? { ...f, cap_de_colla_id: operariId, estat: "ASSIGNADA" } : f));
      alert("Ordre assignada correctament!");
    } catch (err: any) {
      alert("Error en l'assignació: " + err.message);
    }
  };

  const pendingFeines = feines.filter(f => f.estat === "PENDENT" || !f.cap_de_colla_id);
  
  // Fake positions for operators to render them on the map
  const getOperariPos = (index: number, total: number) => {
    const angle = (index / total) * Math.PI * 2;
    const radius = 25; // percentage
    return {
      top: `${50 + Math.sin(angle) * radius}%`,
      left: `${50 + Math.cos(angle) * radius}%`
    };
  };

  return (
    <div className="flex-1 flex h-[calc(100vh-3.5rem)] relative overflow-hidden bg-slate-900 text-white select-none">
      {/* 1. SIDEBAR DE FEINES PENDENTS (DRAGGABLE) */}
      <aside className="w-80 bg-slate-900 border-r border-slate-800 flex flex-col z-20 shadow-xl">
        <div className="p-4 border-b border-slate-800">
          <h2 className="font-bold text-slate-100 flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-emerald-500" />
            Ordres Pendents
          </h2>
          <p className="text-xs text-slate-400 mt-1">Arrossega al mapa per assignar</p>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading && <p className="text-slate-500 text-sm">Carregant...</p>}
          {!loading && pendingFeines.length === 0 && (
            <div className="text-center p-4 bg-slate-800/50 border border-slate-700 rounded-xl">
              <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
              <p className="text-sm font-bold">Tot assignat</p>
            </div>
          )}
          {pendingFeines.map(feina => (
            <div
              key={feina.id}
              draggable
              onDragStart={(e) => handleDragStart(e, feina)}
              onDragEnd={handleDragEnd}
              className={`p-3 bg-slate-800 border ${draggingId === feina.id ? 'border-emerald-500 opacity-50' : 'border-slate-700'} rounded-xl cursor-grab active:cursor-grabbing hover:bg-slate-700 transition-colors shadow-lg`}
            >
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-mono font-bold bg-slate-900 px-2 py-0.5 rounded text-emerald-400">
                  {feina.codi}
                </span>
                <span className="text-[10px] font-bold text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded">
                  {feina.estat}
                </span>
              </div>
              <p className="text-sm font-bold mt-1 text-slate-200">{feina.titol}</p>
              <p className="text-xs text-slate-400 mt-1 truncate flex items-center gap-1">
                <MapPin className="w-3 h-3" /> {feina.adreca}
              </p>
            </div>
          ))}
        </div>
      </aside>

      {/* 2. VISOR CARTOGRÀFIC (DROPPABLE ZONES) */}
      <div className="flex-1 relative bg-slate-950">
        <div
          className="absolute inset-0 w-full h-full bg-cover bg-center transition-all duration-500 opacity-80"
          style={{
            backgroundImage:
              modeVisor === "SAT"
                ? "radial-gradient(circle at 50% 50%, rgba(2, 36, 72, 0.4), rgba(0, 14, 36, 0.95)), url('https://images.unsplash.com/photo-1524661135-423995f22d0b?auto=format&fit=crop&w=2000&q=80')"
                : "linear-gradient(rgba(15, 23, 42, 0.85), rgba(15, 23, 42, 0.95)), url('https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=2000&q=80')",
          }}
        />

        {/* CONTROLS DEL MAPA */}
        <div className="absolute top-4 right-4 z-20 flex bg-slate-900 border border-slate-700 rounded-lg overflow-hidden shadow-xl">
          <button
            onClick={() => setModeVisor("SAT")}
            className={`px-3 py-1.5 text-xs font-bold ${modeVisor === "SAT" ? 'bg-emerald-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
          >
            SAT
          </button>
          <button
            onClick={() => setModeVisor("TOPO")}
            className={`px-3 py-1.5 text-xs font-bold ${modeVisor === "TOPO" ? 'bg-emerald-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
          >
            TOPO
          </button>
        </div>

        {/* OPERARIS AL MAPA (DROPPABLE TARGETS) */}
        {!loading && operaris.map((op, i) => {
          const pos = getOperariPos(i, operaris.length);
          const assignades = feines.filter(f => f.cap_de_colla_id === op.id);

          return (
            <div
              key={op.id}
              className={`absolute transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-10`}
              style={pos}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, op.id)}
            >
              <div className="w-12 h-12 rounded-full bg-slate-900 border-2 border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.5)] flex items-center justify-center mb-1 group hover:scale-110 transition-transform">
                <Users className="w-6 h-6 text-emerald-400" />
                {/* Drop indicator overlay */}
                {draggingId && (
                  <div className="absolute inset-0 rounded-full border-2 border-dashed border-white animate-spin-slow bg-emerald-500/20" />
                )}
              </div>
              <div className="bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg p-2 shadow-xl text-center min-w-[120px]">
                <p className="text-xs font-bold text-white">{op.nom} {op.cognoms}</p>
                <p className="text-[10px] text-slate-400 mt-0.5">{assignades.length} OT assignades</p>
                {assignades.length > 0 && (
                  <div className="mt-1 flex flex-wrap justify-center gap-1">
                    {assignades.map(a => (
                      <span key={a.id} className="text-[8px] bg-slate-800 px-1 py-0.5 rounded border border-slate-700 text-slate-300">
                        {a.codi}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
