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

export interface BlindDistrict {
  district: string
  lat: number
  lon: number
  total_buildings: number
  blind_buildings: number
  blind_pct: number
  avg_emergency_min: number
  max_emergency_min: number
}

export interface BlindZonesSummary {
  city: string
  threshold_min: number
  total_buildings: number
  blind_buildings: number
  blind_pct: number
  districts: BlindDistrict[]
}

export interface OperationsAnalytics {
  city: string
  totals: {
    incidents: number
    damage_tenge: number
    casualties: number
    avg_response_min: number | null
  }
  by_cause: { cause: string; count: number; damage_tenge: number }[]
  by_severity: { severity: string; count: number }[]
  monthly: { month: string; count: number; damage_tenge: number }[]
}

export interface OperationalCard {
  id: string
  status: 'uploaded' | 'processing' | 'ready_for_extraction' | 'extracted' | 'approved' | 'rejected' | 'deleted'
  file_name: string
  file_mime: string | null
  uploaded_at: string
  building_id: string | null
  uploaded_by: string | null
  thumbnail_key: string | null
  converted_key: string | null
}

export interface CardStatus {
  card_id: string
  status: string
  processed_at: string | null
}

export interface FieldValue {
  value: string | number | boolean | null
  confidence: number
  source_page?: number | null
}

export interface Vulnerability {
  severity: 'critical' | 'high' | 'medium' | 'low'
  description: string
  regulation_violated?: string | null
  recommended_action: string
}

export interface BuildingDetail extends Building {
  risk_score: number | null
  shap_values: Record<string, number> | null
}

export interface RiskBreakdown {
  baseline_score: number
  dynamic_modifier: number
  final_score: number
  horizon_days: number
  expected_incidents: number
}

export interface ShapFactor {
  feature: string
  value: number | string | null
  shap_value: number
}

export interface RiskExplanation {
  shap_factors: ShapFactor[]
  explanation: string
}

export interface BuildingRiskItem {
  building_id: string
  address: string
  building_type: string | null
  lat: number | null
  lon: number | null
  final_score: number
  baseline_score: number
  dynamic_modifier: number
  risk_level: 'low' | 'medium' | 'high'
}

export interface InspectorBuilding {
  building_id: string
  address: string
  building_type: string | null
  floors_above: number | null
  lat: number | null
  lon: number | null
  final_score: number
  risk_level: 'low' | 'medium' | 'high'
}

export interface InspectorRouteWaypoint {
  building_id: string
  lat: number
  lon: number
  address: string
  final_score: number
}

export interface InspectorRoute {
  ordered_buildings: string[]
  total_distance_km: number
  estimated_time_min: number
  waypoints: InspectorRouteWaypoint[]
}

export interface ExtractionData {
  id: string
  card_id: string
  status: string
  extracted_data: {
    card_number?: FieldValue
    approved_date?: FieldValue
    building_name?: FieldValue
    address?: FieldValue
    city?: FieldValue
    hazard_class?: FieldValue
    floors_above?: FieldValue
    floors_below?: FieldValue
    total_area_sqm?: FieldValue
    height_m?: FieldValue
    year_built?: FieldValue
    wall_material?: FieldValue
    fire_resistance_degree?: FieldValue
    max_occupancy?: FieldValue
    has_gas_systems?: FieldValue
    has_hazardous_materials?: FieldValue
    overall_confidence?: number
    missing_fields?: string[]
    extraction_notes?: string | null
    fire_safety?: {
      alarm_type?: string | null
      sprinkler_present?: boolean | null
      smoke_extraction?: boolean | null
      evacuation_exits?: number | null
    }
    hydrants?: Array<{ distance_m?: number | null; address?: string | null }>
    vulnerabilities?: Vulnerability[]
  }
  human_corrections?: Record<string, unknown> | null
  extraction_cost_usd?: number | null
  created_at: string
}
