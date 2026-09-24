'use client';

import React, { useState } from 'react';
import { AlertCircle, CheckCircle2, UploadCloud, X, FileJson } from 'lucide-react';

interface CsvImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  resourceName: string; // Ex: 'clients', 'proveidors'
  endpoint: string;     // Ex: '/api/v1/gestio/clients/import'
  onSuccess: () => void;
}

interface ImportResult {
  total_processats: number;
  inserits: number;
  errors_detectats: Array<{
    fila: number | string;
    columna: string;
    valor: string;
    motiu: string;
  }>;
}

export function CsvImportModal({ isOpen, onClose, resourceName, endpoint, onSuccess }: CsvImportModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [errorToast, setErrorToast] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setResult(null);
      setErrorToast(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setLoading(true);
    setErrorToast(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const token = localStorage.getItem('sevalor_token');
      const apiEndpoint = endpoint.startsWith('http') 
        ? endpoint 
        : `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${endpoint}`;
        
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Error al pujar el fitxer');
      }

      const data: ImportResult = await response.json();
      setResult(data);

      if (data.inserits > 0) {
        onSuccess();
      }
    } catch (error) {
      setErrorToast('Hi ha hagut un error processant el fitxer CSV. Comprova la connexió o el format.');
    } finally {
      setLoading(false);
    }
  };

  const resetState = () => {
    setFile(null);
    setResult(null);
    setErrorToast(null);
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto overflow-x-hidden bg-black/50 p-4">
      <div className="relative w-full max-w-3xl rounded-xl bg-white shadow-xl dark:bg-slate-900">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 p-4 dark:border-slate-800">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
            Importació massiva de {resourceName}
          </h3>
          <button
            onClick={handleClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {errorToast && (
            <div className="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-800 dark:bg-red-900/30 dark:text-red-400">
              {errorToast}
            </div>
          )}

          {!result ? (
            <div className="flex flex-col space-y-4">
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Puja un fitxer CSV amb les dades que vulguis importar. Les dades seran validades línia a línia.
              </p>
              
              <div className="relative flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-8 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800/50 dark:hover:bg-slate-800">
                <input
                  type="file"
                  accept=".csv"
                  className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                  onChange={handleFileChange}
                />
                <UploadCloud className="mb-2 h-10 w-10 text-slate-400" />
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  {file ? file.name : "Fes clic o arrossega un fitxer .csv"}
                </p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center space-x-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-900/50 dark:bg-emerald-900/20">
                  <CheckCircle2 className="h-8 w-8 text-emerald-600 dark:text-emerald-500" />
                  <div>
                    <p className="text-sm font-medium text-emerald-900 dark:text-emerald-400">Registres inserits</p>
                    <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-500">{result.inserits}</p>
                  </div>
                </div>
                <div className={`flex items-center space-x-3 rounded-lg border p-4 ${result.errors_detectats.length > 0 ? 'border-orange-200 bg-orange-50 dark:border-orange-900/50 dark:bg-orange-900/20' : 'border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/50'}`}>
                  <AlertCircle className={`h-8 w-8 ${result.errors_detectats.length > 0 ? 'text-orange-600 dark:text-orange-500' : 'text-slate-400'}`} />
                  <div>
                    <p className={`text-sm font-medium ${result.errors_detectats.length > 0 ? 'text-orange-900 dark:text-orange-400' : 'text-slate-500'}`}>Errors detectats</p>
                    <p className={`text-2xl font-bold ${result.errors_detectats.length > 0 ? 'text-orange-700 dark:text-orange-500' : 'text-slate-700 dark:text-slate-300'}`}>{result.errors_detectats.length}</p>
                  </div>
                </div>
              </div>

              {result.errors_detectats.length > 0 && (
                <div className="mt-6 overflow-hidden rounded-md border border-slate-200 dark:border-slate-700">
                  <div className="flex items-center border-b border-slate-200 bg-slate-50 px-4 py-2 font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                    <FileJson className="mr-2 h-4 w-4" />
                    Taula d'Errors i Dades Faltants
                  </div>
                  <div className="max-h-60 overflow-y-auto">
                    <table className="w-full text-left text-sm text-slate-600 dark:text-slate-400">
                      <thead className="sticky top-0 bg-slate-100 text-xs uppercase text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                        <tr>
                          <th className="px-4 py-2">Fila</th>
                          <th className="px-4 py-2">Columna</th>
                          <th className="px-4 py-2">Valor enviat</th>
                          <th className="px-4 py-2">Motiu / Error</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 dark:divide-slate-700 bg-white dark:bg-slate-900">
                        {result.errors_detectats.map((err, idx) => (
                          <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                            <td className="px-4 py-2 font-medium">#{err.fila}</td>
                            <td className="px-4 py-2 font-mono text-xs bg-slate-50 dark:bg-slate-800">{err.columna}</td>
                            <td className="px-4 py-2 text-rose-600 italic dark:text-rose-400">
                              {err.valor === "" ? "(Buit)" : err.valor}
                            </td>
                            <td className="px-4 py-2">{err.motiu}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-slate-100 p-4 dark:border-slate-800">
          {!result ? (
            <>
              <button
                onClick={handleClose}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Cancel·lar
              </button>
              <button
                onClick={handleUpload}
                disabled={!file || loading}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {loading ? 'Processant...' : 'Importar CSV'}
              </button>
            </>
          ) : (
            <button
              onClick={handleClose}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 dark:bg-slate-700 dark:hover:bg-slate-600"
            >
              Tancar
            </button>
          )}
        </div>

      </div>
    </div>
  );
}
