import React from 'react';

interface FincaMapProps {
  coords?: [number, number];
  nom_finca?: string;
}

export function FincaMap({ coords, nom_finca }: FincaMapProps) {
  if (!coords) {
    return (
      <div className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-[hsl(var(--color-border))] rounded-lg bg-[hsl(var(--color-surface))]">
        <span className="text-gray-500 text-sm font-medium">Ubicació no disponible</span>
      </div>
    );
  }

  const [lat, lng] = coords;
  const geoUrl = `geo:${lat},${lng}`;
  const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${lng - 0.005},${lat - 0.005},${lng + 0.005},${lat + 0.005}&layer=mapnik&marker=${lat},${lng}`;

  return (
    <div className="flex flex-col gap-3 p-4 border border-[hsl(var(--color-border))] rounded-lg bg-[hsl(var(--color-surface))] shadow-sm overflow-hidden">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-[hsl(var(--color-foreground))] tracking-tight">
          {nom_finca || "Mapa de la Finca"}
        </h3>
        <a 
          href={geoUrl} 
          target="_blank" 
          rel="noopener noreferrer"
          className="text-xs uppercase font-bold tracking-wider text-[hsl(var(--color-primary))] hover:underline"
        >
          Obrir al Navegador GPS
        </a>
      </div>

      <div className="text-xs font-mono text-gray-500 mb-2">
        Lat: {lat.toFixed(6)} | Lng: {lng.toFixed(6)}
      </div>

      <div className="w-full h-48 bg-gray-100 rounded-md relative overflow-hidden">
        {/* Usant iframe per a una visualització lleugera */}
        <iframe 
          width="100%" 
          height="100%" 
          frameBorder="0" 
          scrolling="no" 
          marginHeight={0} 
          marginWidth={0} 
          src={mapUrl}
          className="absolute inset-0"
        ></iframe>
      </div>
    </div>
  );
}
