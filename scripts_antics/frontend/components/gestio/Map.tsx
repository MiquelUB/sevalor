"use client";

import { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Corregir la icona per defecte de Leaflet a NextJS
const DefaultIcon = L.icon({
  iconUrl: '/leaflet/marker-icon.png',
  iconRetinaUrl: '/leaflet/marker-icon-2x.png',
  shadowUrl: '/leaflet/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  tooltipAnchor: [16, -28],
  shadowSize: [41, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

interface MapProps {
  markers?: Array<{
    id: string;
    lat: number;
    lng: number;
    title: string;
    status: string; // PENDENT, EN_CURS, FINALITZADA
    isIncidencia?: boolean;
  }>;
}

export default function GestioMap({ markers = [] }: MapProps) {
  // Coordenades centrals per defecte (ex. Barcelona)
  const defaultCenter: [number, number] = [41.3851, 2.1734];

  return (
    <MapContainer 
      center={defaultCenter} 
      zoom={13} 
      scrollWheelZoom={true} 
      className="w-full h-full rounded-xl z-0"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {markers.map(marker => (
        <Marker key={marker.id} position={[marker.lat, marker.lng]}>
          <Popup>
            <div className="text-sm font-sans">
              <strong className="block mb-1 text-slate-800">{marker.title}</strong>
              <span className={`px-2 py-1 rounded text-xs text-white ${
                marker.isIncidencia ? 'bg-red-500' :
                marker.status === 'EN_CURS' ? 'bg-blue-500' :
                marker.status === 'FINALITZADA' ? 'bg-green-500' : 'bg-slate-500'
              }`}>
                {marker.isIncidencia ? '🚨 INCIDÈNCIA' : marker.status}
              </span>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
