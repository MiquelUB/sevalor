'use client';

import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { AlertCircle, CheckCircle2, Download, UploadCloud, X, FileJson } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

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
  const { toast } = useToast();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const token = localStorage.getItem('sevalor_token');
      const response = await fetch(endpoint, {
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
        toast({
          title: 'Importació finalitzada',
          description: `S'han inserit ${data.inserits} registres correctament.`,
        });
      }
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Error de servidor',
        description: 'Hi ha hagut un error processant el fitxer CSV.',
      });
    } finally {
      setLoading(false);
    }
  };

  const resetState = () => {
    setFile(null);
    setResult(null);
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Importació massiva de {resourceName}</DialogTitle>
        </DialogHeader>

        {!result ? (
          <div className="flex flex-col space-y-4 py-4">
            <p className="text-sm text-gray-500">
              Puja un fitxer CSV amb les dades que vulguis importar. Les dades seran validades línia a línia.
            </p>
            
            <div className="border-2 border-dashed border-gray-200 rounded-lg p-8 flex flex-col items-center justify-center bg-gray-50 hover:bg-gray-100 transition-colors cursor-pointer relative">
              <input
                type="file"
                accept=".csv"
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={handleFileChange}
              />
              <UploadCloud className="h-10 w-10 text-gray-400 mb-2" />
              <p className="text-sm font-medium text-gray-700">
                {file ? file.name : "Fes clic o arrossega un fitxer .csv"}
              </p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-green-50 p-4 rounded-lg flex items-center space-x-3 border border-green-200">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
                <div>
                  <p className="text-sm font-medium text-green-900">Registres inserits</p>
                  <p className="text-2xl font-bold text-green-700">{result.inserits}</p>
                </div>
              </div>
              <div className={`p-4 rounded-lg flex items-center space-x-3 border ${result.errors_detectats.length > 0 ? 'bg-orange-50 border-orange-200' : 'bg-gray-50 border-gray-200'}`}>
                <AlertCircle className={`h-8 w-8 ${result.errors_detectats.length > 0 ? 'text-orange-600' : 'text-gray-400'}`} />
                <div>
                  <p className={`text-sm font-medium ${result.errors_detectats.length > 0 ? 'text-orange-900' : 'text-gray-500'}`}>Errors detectats</p>
                  <p className={`text-2xl font-bold ${result.errors_detectats.length > 0 ? 'text-orange-700' : 'text-gray-700'}`}>{result.errors_detectats.length}</p>
                </div>
              </div>
            </div>

            {result.errors_detectats.length > 0 && (
              <div className="mt-6 border rounded-md">
                <div className="bg-gray-50 px-4 py-2 border-b rounded-t-md font-medium flex items-center">
                  <FileJson className="w-4 h-4 mr-2" />
                  Taula d'Errors i Dades Faltants
                </div>
                <div className="max-h-60 overflow-y-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="text-xs text-gray-700 uppercase bg-gray-100 sticky top-0">
                      <tr>
                        <th className="px-4 py-2">Fila</th>
                        <th className="px-4 py-2">Columna</th>
                        <th className="px-4 py-2">Valor enviat</th>
                        <th className="px-4 py-2">Motiu / Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.errors_detectats.map((err, idx) => (
                        <tr key={idx} className="border-b hover:bg-gray-50">
                          <td className="px-4 py-2 font-medium">#{err.fila}</td>
                          <td className="px-4 py-2 font-mono text-xs bg-gray-100">{err.columna}</td>
                          <td className="px-4 py-2 text-red-600 italic">
                            {err.valor === "" ? "(Buit)" : err.valor}
                          </td>
                          <td className="px-4 py-2 text-gray-600">{err.motiu}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          {!result ? (
            <>
              <Button variant="outline" onClick={handleClose}>Cancel·lar</Button>
              <Button onClick={handleUpload} disabled={!file || loading}>
                {loading ? 'Processant...' : 'Importar CSV'}
              </Button>
            </>
          ) : (
            <Button onClick={handleClose}>Tancar</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
