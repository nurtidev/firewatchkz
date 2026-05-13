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

export interface Building {
  id: string
  city: string
  district: string | null
  name: string
  address: string | null
  object_type: string | null
  floors_count: number | null
  total_area: number | null
  fire_resistance_degree: string | null
  construction_type: string | null
  nearest_fire_department: string | null
  distance_to_fire_department: number | null
  arrival_time_minutes: number | null
  route_description: string | null
  fire_rank: string | null
  owner_name: string | null
  owner_phone: string | null
  technical_manager_name: string | null
  technical_manager_phone: string | null
  security_phone: string | null
  dispatcher_phone: string | null
  power_supply_info: string | null
  heating_info: string | null
  water_supply_info: string | null
  ventilation_info: string | null
  smoke_removal_info: string | null
  fire_alarm_info: string | null
  fire_extinguishing_systems: Record<string, string> | null
  evacuation_routes_count: number | null
  potential_hazards: string | null
  complexity_features: string | null
  auxiliary_means: string | null
  estimated_forces: Record<string, unknown> | null
  lat: number | null
  lon: number | null
}

export interface Hydrant {
  id: string
  city: string
  district: string
  address: string
  lat: number
  lon: number
  status: 'working' | 'maintenance' | 'out_of_service'
  last_checked: string | null
  winter_accessible: boolean | null
  pressure_bar: number | null
  notes: string | null
}

export interface HydrantUpdate {
  status?: 'working' | 'maintenance' | 'out_of_service'
  last_checked?: string
  winter_accessible?: boolean
  pressure_bar?: number
  notes?: string
}

export interface RouteEstimate {
  normal_min: number
  emergency_min: number
  savings_min: number
  distance_km: number
  geometry: [number, number][] | null
  source: 'osrm' | 'haversine'
  route_notes: string
  city: string
  station_id?: string
}

export interface RoutingStation {
  id: string
  name: string
  district: string
  lat: number
  lon: number
}
