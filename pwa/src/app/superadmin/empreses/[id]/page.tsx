"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Save, AlertTriangle, ShieldCheck, PowerOff, Zap } from "lucide-react";
import { getAuthHeader } from "@/lib/auth";
import { getApiBaseUrl } from "@/lib/api";

export default function EmpresaDetailPage({ params }: { params: { id: string } }) {
  const [tenant, setTenant] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  const [estat, setEstat] = useState("");
  const [pla, setPla] = useState("");
  const [features, setFeatures] = useState({
    feature_copilot_ia: false,
    feature_flota: false,
    feature_planols: false,
    feature_telegram: false,
  });

  useEffect(() => {
    fetchTenant();
  }, []);

  const fetchTenant = async () => {
    try {
      const res = await fetch(getApiBaseUrl() + "/api/v1/superadmin/tenants", {
        headers: getAuthHeader(),
      });
      const data = await res.json();
      const t = data.find((x: any) => x.id === params.id);
      if (t) {
        setTenant(t);
        setEstat(t.estat_pagament);
        setPla(t.pla_subscripcio);
        setFeatures({
          feature_copilot_ia: t.feature_copilot_ia,
          feature_flota: t.feature_flota,
          feature_planols: t.feature_planols,
          feature_telegram: t.feature_telegram,
        });
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const saveEstat = async () => {
    try {
      await fetch(`http://localhost:8000/api/v1/superadmin/tenants/${params.id}/estat`, {
        method: "PUT",
        headers: { ...getAuthHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({ estat })
      });
    } catch(e) { console.error(e) }
  };

  const saveQuota = async () => {
    try {
      const r = await fetch(`http://localhost:8000/api/v1/superadmin/tenants/${params.id}/quota`, {
        method: "PUT",
        headers: { ...getAuthHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({ pla_subscripcio: pla })
      });
      if(!r.ok) {
        const err = await r.json();
        alert(err.detail || "Error");
      }
    } catch(e) { console.error(e) }
  };

  const saveFeatures = async () => {
    try {
      await fetch(`http://localhost:8000/api/v1/superadmin/tenants/${params.id}/feature-flags`, {
        method: "PUT",
        headers: { ...getAuthHeader(), "Content-Type": "application/json" },
        body: JSON.stringify(features)
      });
    } catch(e) { console.error(e) }
  };

  const handleSave = async () => {
    setSaving(true);
    await Promise.all([saveEstat(), saveQuota(), saveFeatures()]);
    setSaving(false);
    alert("Canvis desats correctament.");
  };
  
  const handleDestroy = async () => {
    if(confirm("ATENCIÓ: Aquesta acció marcarà el tenant com ELIMINAT i programarà la purga de dades. N'estàs segur?")) {
      await fetch(`http://localhost:8000/api/v1/superadmin/tenants/${params.id}/destruccio`, {
        method: "POST",
        headers: getAuthHeader()
      });
      fetchTenant();
    }
  }

  if (loading) return <div className="p-8 text-slate-500">Carregant...</div>;
  if (!tenant) return <div className="p-8 text-red-500">Tenant no trobat.</div>;

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-8">
      <Link href="/superadmin/empreses" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Tornar al llistat
      </Link>

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            {tenant.nom || tenant.rao_social}
            <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-100 dark:bg-slate-800 text-slate-500">
              {tenant.subdomini}.campopro.cat
            </span>
          </h1>
          <p className="text-sm font-mono text-slate-500 mt-1">ID: {tenant.id}</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2 rounded-lg font-bold flex items-center gap-2 transition-colors disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {saving ? "Desant..." : "Desar Canvis"}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* ESTAT */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-xl shadow-sm">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Cicle de Vida
          </h2>
          <select 
            value={estat} 
            onChange={e => setEstat(e.target.value)}
            className="w-full bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-emerald-500 focus:border-emerald-500 block p-2.5 dark:bg-slate-800 dark:border-slate-600 dark:placeholder-slate-400 dark:text-white"
          >
            <option value="TRIAL">TRIAL (14 dies)</option>
            <option value="ACTIU">ACTIU</option>
            <option value="SUSPES">SUSPÈS (Impagament)</option>
            <option value="ELIMINAT">ELIMINAT</option>
          </select>
          <p className="text-xs text-slate-500 mt-2">Canviar a suspès revoca els tokens de tots els operaris immediatament.</p>
        </div>

        {/* Llicència */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-xl shadow-sm">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4" />
            Pla de Llicència
          </h2>
          <select 
            value={pla} 
            onChange={e => setPla(e.target.value)}
            className="w-full bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-emerald-500 focus:border-emerald-500 block p-2.5 dark:bg-slate-800 dark:border-slate-600 dark:placeholder-slate-400 dark:text-white"
          >
            <option value="STARTER">STARTER (Max 5)</option>
            <option value="PRO">PRO (Max 15)</option>
            <option value="ENTERPRISE">ENTERPRISE (Sense límit)</option>
          </select>
          <p className="text-xs text-amber-600 mt-2">Els downgrades fallaran si superen el límit d'operaris actius.</p>
        </div>

        {/* Modules */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-xl shadow-sm md:col-span-2">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4" />
            Interruptors de Mòduls (Feature Flags)
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            {Object.keys(features).map((key) => (
              <label key={key} className="flex items-center gap-3 p-3 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                <input 
                  type="checkbox"
                  className="w-4 h-4 text-emerald-600 rounded focus:ring-emerald-500 dark:focus:ring-emerald-600 dark:ring-offset-slate-800 focus:ring-2 dark:bg-slate-700 dark:border-slate-600"
                  checked={(features as any)[key]}
                  onChange={e => setFeatures({...features, [key]: e.target.checked})}
                />
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  {key.replace('feature_', '').toUpperCase()}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* DANGER ZONE */}
        <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/50 p-6 rounded-xl shadow-sm md:col-span-2 mt-4">
          <h2 className="text-sm font-bold uppercase tracking-wider text-red-600 dark:text-red-400 mb-2 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Zona de Perill
          </h2>
          <p className="text-sm text-red-700 dark:text-red-300 mb-4">
            L'eliminació d'un tenant generarà un certificat de destrucció de dades (RGPD) i n'esborrarà els arxius transcorreguts 30 dies.
          </p>
          <button
            onClick={handleDestroy}
            className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded text-sm font-bold flex items-center gap-2 transition-colors"
          >
            <PowerOff className="w-4 h-4" />
            Forçar Destrucció (Offboarding)
          </button>
        </div>
      </div>
    </div>
  );
}
