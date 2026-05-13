'use client'

import { useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Fix default Leaflet icon paths
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const fireIcon = new L.DivIcon({
  html: `<div style="
    background:#f97316;border:2px solid #fff;
    border-radius:50%;width:16px;height:16px;
    box-shadow:0 1px 4px rgba(0,0,0,.5)
  "></div>`,
  className: '',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
})

const destIcon = new L.DivIcon({
  html: `<div style="
    background:#ef4444;border:2px solid #fff;
    border-radius:50%;width:16px;height:16px;
    box-shadow:0 1px 4px rgba(0,0,0,.5)
  "></div>`,
  className: '',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
})

function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (positions.length < 2) return
    const bounds = L.latLngBounds(positions)
    map.fitBounds(bounds, { padding: [32, 32] })
  }, [map, positions])
  return null
}

interface Props {
  from: { lat: number; lon: number; label: string }
  to: { lat: number; lon: number; label: string }
  geometry: [number, number][] | null // [[lon, lat], ...]
}

export default function RouteMap({ from, to, geometry }: Props) {
  // Convert geometry from [lon, lat] to Leaflet [lat, lon]
  const polylinePoints: [number, number][] = geometry
    ? geometry.map(([lon, lat]) => [lat, lon])
    : [
        [from.lat, from.lon],
        [to.lat, to.lon],
      ]

  const fitPositions: [number, number][] = [[from.lat, from.lon], [to.lat, to.lon]]

  return (
    <MapContainer
      center={[from.lat, from.lon]}
      zoom={12}
      style={{ height: '100%', width: '100%' }}
      zoomControl={false}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />

      <Marker position={[from.lat, from.lon]} icon={fireIcon}>
        <Popup>{from.label}</Popup>
      </Marker>

      <Marker position={[to.lat, to.lon]} icon={destIcon}>
        <Popup>{to.label}</Popup>
      </Marker>

      <Polyline
        positions={polylinePoints}
        pathOptions={{ color: '#f97316', weight: 4, opacity: 0.85, dashArray: geometry ? undefined : '8 6' }}
      />

      <FitBounds positions={fitPositions} />
    </MapContainer>
  )
}
