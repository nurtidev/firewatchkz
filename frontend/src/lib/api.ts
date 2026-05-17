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
  InspectorBuilding,
  InspectorRoute,
  Building,
  BuildingDetail,
  BuildingRiskItem,
  RiskBreakdown,
  RiskExplanation,
  Hydrant,
  HydrantUpdate,
  RouteEstimate,
  RoutingStation,
  OperationalCard,
  CardStatus,
  ExtractionData,
} from './types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return ''
  const q = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')
  return q ? `?${q}` : ''
}

// JWT хранится в localStorage под ключом из AUTH_TOKEN_KEY (см. lib/auth.ts).
// Дублируем константу, чтобы не тянуть зависимость и не ломать SSR.
const AUTH_TOKEN_KEY = 'firewatch.auth.token'

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  if (typeof window === 'undefined') return extra
  const token = window.localStorage.getItem(AUTH_TOKEN_KEY)
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PATCH',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  cities: {
    list: () => get<CitySummary[]>('/api/v2/cities'),
    get: (cityId: string) => get<City>(`/api/v2/cities/${cityId}`),
  },

  kpi: {
    get: (city: string) => get<KPI>(`/api/v2/kpi?city=${city}`),
  },

  riskMap: {
    get: (city: string) => get<DistrictRisk[]>(`/api/v2/risk-map?city=${city}`),
  },

  incidents: {
    list: (city: string, district?: string, limit = 50) => {
      const params = new URLSearchParams({ city, limit: String(limit) })
      if (district) params.set('district', district)
      return get<{ total: number; items: Incident[] }>(`/api/v2/incidents?${params}`)
    },
  },

  forecast: {
    get: (city: string, months: 3 | 6 | 12) =>
      get<ForecastResponse>(`/api/v2/forecast?city=${city}&months=${months}`),
  },

  recommendations: {
    get: (city: string) => get<Recommendation[]>(`/api/v2/recommendations?city=${city}`),
  },

  chat: {
    send: (city: string, message: string, history: ChatMessage[]) =>
      post<{ reply: string }>('/api/v2/chat', { city, message, history }),
  },

  inspector: {
    // /alerts — агрегат по районам (бэк строит из incidents).
    // /inspector?top_n=… — top-N зданий по risk_score (нужны заполненные risk_scores).
    get: (city: string) => get<InspectorAlert[]>(`/api/v2/inspector/alerts?city=${city}`),
    list: (city: string, topN: number, minRisk: number) =>
      get<InspectorBuilding[]>(`/api/v2/inspector?city=${city}&top_n=${topN}&min_risk=${minRisk}`),
    route: (buildingIds: string[]) =>
      get<InspectorRoute>(`/api/v2/inspector/route?building_ids=${encodeURIComponent(JSON.stringify(buildingIds))}`),
  },

  telegram: {
    config: () => get<{ status: string; chat_id?: string | null; bot_token_masked?: string }>('/api/v2/telegram/config'),
    test: (city: string) => post<{ status: string }>(`/api/v2/telegram/test?city=${city}`, {}),
  },

  buildings: {
    list: (city: string) => get<Building[]>(`/api/v2/buildings?city=${city}`),
    listRisk: (city: string, bbox?: string, limit = 500) =>
      get<BuildingRiskItem[]>(`/api/v2/buildings?city=${city}${bbox ? `&bbox=${bbox}` : ''}&limit=${limit}`),
    get: (id: string) => get<Building>(`/api/v2/buildings/${id}`),
    getDetail: (id: string) => get<BuildingDetail>(`/api/v2/buildings/${id}`),
    getRisk: (id: string, horizon = 30) =>
      get<RiskBreakdown>(`/api/v2/buildings/${id}/risk?horizon=${horizon}`),
    getFactors: (id: string) => get<RiskExplanation>(`/api/v2/buildings/${id}/factors`),
    getIncidents: (city: string, buildingId: string, limit = 10) => {
      const params = new URLSearchParams({ city, building_id: buildingId, limit: String(limit) })
      return get<{ total: number; items: Incident[] }>(`/api/v2/incidents?${params}`)
    },
  },

  hydrants: {
    list: (city: string, status?: string) => {
      const params = new URLSearchParams({ city })
      if (status) params.set('status', status)
      return get<Hydrant[]>(`/api/v2/hydrants?${params}`)
    },
    update: (city: string, id: string, body: HydrantUpdate) =>
      patch<Hydrant>(`/api/v2/hydrants/${id}?city=${city}`, body),
  },

  routing: {
    estimate: (body: {
      from_lat: number
      from_lon: number
      to_lat: number
      to_lon: number
      city: string
      station_id?: string
    }) => post<RouteEstimate>('/api/v2/routing/estimate', body),
    stations: (city: string) => get<RoutingStation[]>(`/api/v2/routing/stations?city=${city}`),
  },

  documents: {
    list: (params?: { status?: string; uploaded_by?: string; limit?: number }) =>
      // Бэк смонтирован с trailing slash — без него 307, на котором браузер теряет Authorization.
      get<OperationalCard[]>(`/api/v2/documents/${buildQuery(params)}`),
    getStatus: (id: string) =>
      get<CardStatus>(`/api/v2/documents/${id}/status`),
    getDetail: (id: string) =>
      get<OperationalCard>(`/api/v2/documents/${id}`),
    getExtraction: (id: string) =>
      get<ExtractionData>(`/api/v2/documents/${id}/extraction`),
    approve: (id: string, approvedBy?: string) =>
      post<{ card_id: string; building_id: string; status: string }>(
        `/api/v2/documents/${id}/approve`,
        { approved_by: approvedBy ?? null }
      ),
    reject: (id: string) =>
      fetch(`${BASE_URL}/api/v2/documents/${id}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
        .then(r => { if (!r.ok) throw new Error('reject failed') }),
    upload: (file: File, buildingId?: string) => {
      const form = new FormData()
      form.append('file', file)
      if (buildingId) form.append('building_id', buildingId)
      // multipart/form-data — Content-Type ставит браузер сам (с boundary), не подмешиваем
      return fetch(`${BASE_URL}/api/v2/documents/upload`, {
        method: 'POST',
        headers: authHeaders(),
        body: form,
      })
        .then(r => { if (!r.ok) throw new Error(`Upload failed: ${r.status}`); return r.json() })
    },
    delete: (id: string) =>
      fetch(`${BASE_URL}/api/v2/documents/${id}`, {
        method: 'DELETE',
        headers: authHeaders(),
      }).then(r => {
        if (!r.ok) throw new Error(`Delete failed: ${r.status}`)
      }),
    patchExtraction: (id: string, fieldCorrections: Record<string, unknown>) =>
      patch<ExtractionData>(`/api/v2/documents/${id}/extraction`, { field_corrections: fieldCorrections }),
  },
}
