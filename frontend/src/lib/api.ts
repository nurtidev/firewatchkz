import type {
  City,
  CitySummary,
  DistrictRisk,
  ForecastResponse,
  KPI,
  Recommendation,
  ChatMessage,
  Incident,
  InspectorAlert,
  Building,
  Hydrant,
  HydrantUpdate,
  RouteEstimate,
  RoutingStation,
} from './types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  cities: {
    list: () => get<CitySummary[]>('/api/v1/cities'),
    get: (cityId: string) => get<City>(`/api/v1/cities/${cityId}`),
  },

  kpi: {
    get: (city: string) => get<KPI>(`/api/v1/kpi?city=${city}`),
  },

  riskMap: {
    get: (city: string) => get<DistrictRisk[]>(`/api/v1/risk-map?city=${city}`),
  },

  incidents: {
    list: (city: string, district?: string, limit = 50) => {
      const params = new URLSearchParams({ city, limit: String(limit) })
      if (district) params.set('district', district)
      return get<{ total: number; items: Incident[] }>(`/api/v1/incidents?${params}`)
    },
  },

  forecast: {
    get: (city: string, months: 3 | 6 | 12) =>
      get<ForecastResponse>(`/api/v1/forecast?city=${city}&months=${months}`),
  },

  recommendations: {
    get: (city: string) => get<Recommendation[]>(`/api/v1/recommendations?city=${city}`),
  },

  chat: {
    send: (city: string, message: string, history: ChatMessage[]) =>
      post<{ reply: string }>('/api/v1/chat', { city, message, history }),
  },

  inspector: {
    get: (city: string) => get<InspectorAlert[]>(`/api/v1/inspector?city=${city}`),
  },

  telegram: {
    config: () => get<{ status: string; chat_id?: string | null; bot_token_masked?: string }>('/api/v1/telegram/config'),
    test: (city: string) => post<{ status: string }>(`/api/v1/telegram/test?city=${city}`, {}),
  },

  buildings: {
    list: (city: string) => get<Building[]>(`/api/v1/buildings?city=${city}`),
    get: (id: string) => get<Building>(`/api/v1/buildings/${id}`),
  },

  hydrants: {
    list: (city: string, status?: string) => {
      const params = new URLSearchParams({ city })
      if (status) params.set('status', status)
      return get<Hydrant[]>(`/api/v1/hydrants?${params}`)
    },
    update: (city: string, id: string, body: HydrantUpdate) =>
      patch<Hydrant>(`/api/v1/hydrants/${id}?city=${city}`, body),
  },

  routing: {
    estimate: (body: {
      from_lat: number
      from_lon: number
      to_lat: number
      to_lon: number
      city: string
      station_id?: string
    }) => post<RouteEstimate>('/api/v1/routing/estimate', body),
    stations: (city: string) => get<RoutingStation[]>(`/api/v1/routing/stations?city=${city}`),
  },
}
