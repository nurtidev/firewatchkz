export interface City {
  id: string
  name: string
  center: [number, number]
  zoom: number
}

export interface CitySummary {
  id: string
  name: string
  incident_count: number
}

export interface DistrictRisk {
  district: string
  risk_score: number
  total_incidents: number
  top_cause: string
  top_building_type: string
  avg_damage_tenge: number
}

export interface ForecastPoint {
  period: string
  predicted?: number
  actual?: number
  lower_80?: number
  upper_80?: number
}

export interface ForecastResponse {
  city: string
  months: number
  model: string
  r_squared: number
  historical: ForecastPoint[]
  forecast: ForecastPoint[]
}

export interface Recommendation {
  priority: 'high' | 'medium' | 'low'
  title: string
  description: string
  expected_impact: string
}

export interface KPI {
  city: string
  total_incidents_ytd: number
  vs_last_year_pct: number
  total_damage_tenge: number
  highest_risk_district: string
  top_cause: string
  prevention_potential_tenge: number
  prevention_potential_incidents: number
  roi_note: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface InspectorFactor {
  matched: boolean
  label: string
}

export interface InspectorAlert {
  district: string
  priority: 'critical' | 'high' | 'medium' | 'low'
  matched_factors: number
  total_factors: number
  risk_score: number
  days_since_last_incident: number | null
  avg_damage_tenge: number
  recommendation: string
  factors: InspectorFactor[]
}

export interface Incident {
  id: string
  date: string
  city: string
  district: string
  building_type: string
  cause: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  casualties: number
  damage_tenge: number
  lat: number
  lon: number
}
