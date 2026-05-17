'use client'

import { useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { InspectorRouteWaypoint } from '@/lib/types'

// Fix default Leaflet icon paths
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

function makeNumberedIcon(index: number, riskLevel: string) {
  const color =
    riskLevel === 'high' ? '#ef4444' :
    riskLevel === 'medium' ? '#f59e0b' :
    '#22c55e'

  return new L.DivIcon({
    html: `<div style="
      background:${color};
      border:2px solid #fff;
      border-radius:50%;
      width:22px;
      height:22px;
      display:flex;
      align-items:center;
      justify-content:center;
      font-size:10px;
      font-weight:700;
      color:#fff;
      box-shadow:0 1px 4px rgba(0,0,0,.5);
      line-height:1;
    ">${index}</div>`,
    className: '',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  })
}

function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (positions.length === 0) return
    if (positions.length === 1) {
      map.setView(positions[0], 14)
      return
    }
    const bounds = L.latLngBounds(positions)
    map.fitBounds(bounds, { padding: [40, 40] })
  }, [map, positions])
  return null
}

interface Props {
  waypoints: InspectorRouteWaypoint[]
  defaultCenter?: [number, number]
}

export default function InspectorRouteMap({ waypoints, defaultCenter }: Props) {
  const validWaypoints = waypoints.filter(
    (w) => typeof w.lat === 'number' && typeof w.lon === 'number'
  )

  const polylinePositions: [number, number][] = validWaypoints.map((w) => [w.lat, w.lon])

  const center: [number, number] =
    validWaypoints.length > 0
      ? [validWaypoints[0].lat, validWaypoints[0].lon]
      : defaultCenter ?? [51.1282, 71.43]

  return (
    <MapContainer
      center={center}
      zoom={12}
      style={{ height: '100%', width: '100%' }}
      zoomControl={false}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />

      {validWaypoints.map((w, i) => {
        const riskLevel =
          w.final_score >= 2.0 ? 'high' :
          w.final_score >= 1.0 ? 'medium' :
          'low'
        return (
          <Marker
            key={w.building_id}
            position={[w.lat, w.lon]}
            icon={makeNumberedIcon(i + 1, riskLevel)}
          >
            <Popup>
              <div style={{ minWidth: 160 }}>
                <div style={{ fontWeight: 700, marginBottom: 2 }}>#{i + 1} {w.address}</div>
                <div style={{ color: '#888', fontSize: 12 }}>
                  Риск: {w.final_score.toFixed(2)}
                </div>
              </div>
            </Popup>
          </Marker>
        )
      })}

      {polylinePositions.length >= 2 && (
        <Polyline
          positions={polylinePositions}
          pathOptions={{ color: '#f97316', weight: 3, opacity: 0.8, dashArray: '6 4' }}
        />
      )}

      <FitBounds positions={polylinePositions} />
    </MapContainer>
  )
}
