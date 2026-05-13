# FireWatch — Task Board

> Each task is designed to be **self-contained** so a separate AI agent can pick it up independently.  
> Before starting any task, read **CONTEXT.md** for full project context.  
> Tasks are grouped by track. Tracks can run in parallel. Within a track, follow the order.

---

## How to Pick Up a Task (for AI Agents)

1. Read `CONTEXT.md` — understand the product, stack, and data model.
2. Find a task with status `[ ]` (not started) that has no unmet dependencies.
3. Implement it exactly as described. Do not add features beyond the acceptance criteria.
4. Mark the task `[x]` when done and note any decisions made in the **Notes** field.

---

## Track A — Backend Foundation
> No dependencies between A-1 and A-2. Start both in parallel.

---

### [A-1] Backend project scaffold
**Status:** `[x]`  
**Priority:** High  
**Depends on:** nothing

**What to build:**  
Set up the FastAPI project under `backend/`.

**File structure to create:**
```
backend/
├── main.py                  # FastAPI app, CORS, router registration
├── requirements.txt
├── .env.example
├── routers/
│   ├── __init__.py
│   ├── cities.py
│   ├── incidents.py
│   ├── forecast.py
│   ├── recommendations.py
│   ├── chat.py
│   ├── kpi.py
│   └── telegram.py
├── services/
│   ├── __init__.py
│   ├── data_loader.py       # loads CSV into DataFrame, cached
│   ├── forecaster.py        # Holt-Winters ETS wrapper
│   ├── claude_client.py     # Anthropic SDK wrapper + 1h cache
│   └── telegram_service.py  # Telegram Bot API wrapper
└── scripts/
    └── generate_data.py     # synthetic data generator (see A-2)
```

**`requirements.txt` must include:**
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
pandas==2.2.0
numpy==1.26.0
statsmodels==0.14.0
anthropic==0.40.0
python-telegram-bot==21.0
apscheduler==3.10.4
python-dotenv==1.0.0
httpx==0.27.0
```

**`main.py` responsibilities:**
- Create FastAPI app with title "FireWatch API"
- Add CORS middleware (allow all origins for MVP)
- Include all routers with `/api/v1` prefix
- Add health check: `GET /health → { status: "ok", version: "0.1.0" }`

**Acceptance criteria:**
- `uvicorn main:app --reload` starts without errors
- `GET /health` returns 200
- Swagger docs available at `/docs`
- All router files exist (can have placeholder `pass` endpoints)

---

### [A-2] Synthetic data generator
**Status:** `[x]`  
**Priority:** High  
**Depends on:** nothing (pure Python script, no FastAPI needed)

**What to build:**  
`backend/scripts/generate_data.py` — generates realistic fire incident CSV data.

**CLI usage:**
```bash
python generate_data.py --city astana --years 3 --output ../data/sample/astana_incidents.csv
```

**Output CSV schema:**
```
id, date, city, district, building_type, cause, severity, casualties, damage_tenge, lat, lon
```

**Field values:**

| Field | Values |
|---|---|
| `city` | `astana` (for now) |
| `district` | Есіл, Алматы, Байқоңыр, Сарыарқа, Нұра (5 districts of Astana) |
| `building_type` | residential, commercial, industrial, construction, other |
| `cause` | electrical, open_flame, arson, children, other |
| `severity` | low, medium, high, critical |
| `casualties` | int 0–10, weighted toward 0 |
| `damage_tenge` | int, varies by severity: low=50k–500k, medium=500k–5M, high=5M–50M, critical=50M–500M |
| `lat`, `lon` | random within district bounding box (Astana coords) |

**Realism rules:**
- Total ~800–1200 incidents over 3 years
- Seasonal pattern: Jan–Feb and May–Jun have 2x average incidents (heating failures + dry season)
- `Есіл` district: more commercial/high-rise → more electrical causes
- `Байқоңыр` district: more industrial → more critical severity
- Weekends: slightly more residential incidents

**Acceptance criteria:**
- Script runs and produces a valid CSV
- CSV has 800–1200 rows for `--years 3`
- Seasonal peaks visible when aggregated by month
- No null values

---

### [A-3] Data loader service
**Status:** `[x]`  
**Priority:** High  
**Depends on:** A-1, A-2

**What to build:**  
`backend/services/data_loader.py` — loads incident CSV(s) into Pandas, exposes clean query API.

**Interface:**
```python
class DataLoader:
    def get_incidents(self, city: str, district: str | None = None,
                      date_from: str | None = None, date_to: str | None = None) -> pd.DataFrame

    def get_monthly_counts(self, city: str) -> pd.DataFrame
    # returns: columns = [year_month (Period), count]

    def get_district_stats(self, city: str) -> pd.DataFrame
    # returns: columns = [district, total_incidents, avg_damage_tenge, risk_score (0-100)]

    def get_cities(self) -> list[dict]
    # returns: [{ id, name, incident_count }]
```

**City config** (hardcoded for MVP, in `services/data_loader.py`):
```python
CITY_CONFIG = {
    "astana": {
        "id": "astana",
        "name": "Астана",
        "center": [51.1801, 71.4460],
        "zoom": 12,
        "data_path": "data/sample/astana_incidents.csv",
        "geojson_path": "data/geojson/astana_districts.geojson",
    }
}
```

**Risk score formula:**
```
risk_score = min(100, (incidents_last_12m / max_district_incidents) * 70
                     + (avg_damage / max_avg_damage) * 30)
```

**Acceptance criteria:**
- DataLoader loads CSV on first call, caches in memory
- All methods return correct DataFrames
- Invalid city raises `HTTPException(404)`

---

### [A-4] Forecasting router
**Status:** `[x]`  
**Priority:** High  
**Depends on:** A-3

**What to build:**  
`backend/routers/forecast.py` + `backend/services/forecaster.py`

**Endpoint:**
```
GET /api/v1/forecast?city=astana&months=6
```

**Response:**
```json
{
  "city": "astana",
  "months": 6,
  "model": "Holt-Winters ETS",
  "r_squared": 0.81,
  "historical": [
    { "period": "2024-01", "actual": 32 }
  ],
  "forecast": [
    { "period": "2026-05", "predicted": 38, "lower_80": 28, "upper_80": 48 }
  ]
}
```

**Implementation notes:**
- Use `statsmodels.tsa.holtwinters.ExponentialSmoothing`
- `trend="add"`, `seasonal="add"`, `seasonal_periods=12`
- Fit on monthly aggregated incident counts
- Cache forecast result for 24h (simple dict cache keyed by `city+months`)
- Calculate R² on train data

**Acceptance criteria:**
- Endpoint returns valid JSON with both `historical` and `forecast` arrays
- `months` param accepts 3, 6, or 12
- Works with Astana sample data

---

### [A-5] Risk map router
**Status:** `[x]`  
**Priority:** High  
**Depends on:** A-3

**What to build:**  
`backend/routers/incidents.py` — two endpoints.

**Endpoints:**

```
GET /api/v1/risk-map?city=astana
```
Response: array of district risk objects
```json
[
  {
    "district": "Есіл",
    "risk_score": 78,
    "total_incidents": 312,
    "top_cause": "electrical",
    "top_building_type": "commercial",
    "avg_damage_tenge": 2400000
  }
]
```

```
GET /api/v1/incidents?city=astana&district=Есіл&limit=50
```
Response: paginated incident list (raw rows as JSON).

**Acceptance criteria:**
- Both endpoints return 200 with correct structure
- `risk_score` is 0–100

---

### [A-6] AI recommendations router
**Status:** `[x]`  
**Priority:** Medium  
**Depends on:** A-3, A-5

**What to build:**  
`backend/routers/recommendations.py` + extend `backend/services/claude_client.py`

**Endpoint:**
```
GET /api/v1/recommendations?city=astana
```

**Claude prompt template** (inject live data):
```
You are a fire safety expert advising the fire department.
City: {city_name}
Current risk data by district:
{district_stats_table}
Top incident causes this year: {top_causes}
Seasonal trend: {seasonal_note}

Generate exactly 5 concrete fire prevention recommendations.
For each recommendation output JSON:
{ "priority": "high|medium|low", "title": "...", "description": "...", "expected_impact": "..." }
Return a JSON array only, no other text.
```

**Caching:** Cache response for 1 hour per city (dict cache).

**Acceptance criteria:**
- Endpoint returns array of 5 recommendations
- Each has `priority`, `title`, `description`, `expected_impact`
- Returns cached response within 1h window

---

### [A-7] AI chat router
**Status:** `[x]`  
**Priority:** Medium  
**Depends on:** A-3, A-6

**What to build:**  
`backend/routers/chat.py`

**Endpoint:**
```
POST /api/v1/chat
Body: { "message": "string", "city": "astana", "history": [...] }
Response: { "reply": "string" }
```

**System prompt:**
```
You are FireWatch AI Analyst — an expert in fire safety data analysis.
You have access to fire incident data for {city_name}.

Summary statistics:
{kpi_summary}

District risk scores:
{district_stats}

Answer questions in the same language the user writes in (Russian or Kazakh preferred).
Be concise and data-driven. Reference specific numbers from the data.
```

**Acceptance criteria:**
- Returns non-empty reply
- Maintains conversation history (pass `history` array to Claude)
- Works in Russian

---

### [A-8] KPI router
**Status:** `[x]`  
**Priority:** Medium  
**Depends on:** A-3

**What to build:**  
`backend/routers/kpi.py`

**Endpoint:**
```
GET /api/v1/kpi?city=astana
```

**Response:**
```json
{
  "city": "astana",
  "total_incidents_ytd": 187,
  "vs_last_year_pct": -12,
  "total_damage_tenge": 1840000000,
  "highest_risk_district": "Байқоңыр",
  "top_cause": "electrical",
  "prevention_potential_tenge": 552000000,
  "prevention_potential_incidents": 56,
  "roi_note": "Estimated 30% reduction in incidents with AI-driven prevention program"
}
```

**Prevention potential formula:**
- Assume 30% of incidents are preventable
- `prevention_potential_tenge = total_damage_ytd * 0.30`
- `prevention_potential_incidents = total_incidents_ytd * 0.30`

**Acceptance criteria:**
- Returns valid JSON
- `vs_last_year_pct` is correctly calculated from actual data

---

### [A-9] Telegram router
**Status:** `[x]`  
**Priority:** Low  
**Depends on:** A-3

**What to build:**  
`backend/routers/telegram.py` + `backend/services/telegram_service.py`

**Endpoints:**
```
POST /api/v1/telegram/test?city=astana   — send test alert to configured chat
GET  /api/v1/telegram/config             — return current config (token masked)
```

**Alert format:**
```
🔥 FireWatch Alert — {city_name}
Severity: {HIGH}
District: Байқоңыр
Incidents this week: 14 (+40% vs avg)
Top cause: electrical
Recommended action: Deploy preventive patrol
```

**Scheduler:** On startup, schedule daily digest at 08:00 (city local time) if `TELEGRAM_BOT_TOKEN` is set.

**Acceptance criteria:**
- `/test` sends a real message if env vars are set, returns mock success if not
- App starts without error when `TELEGRAM_BOT_TOKEN` is missing

---

### [A-10] Cities router
**Status:** `[x]`  
**Priority:** Low  
**Depends on:** A-3

**What to build:**  
`backend/routers/cities.py`

**Endpoints:**
```
GET /api/v1/cities                 — list all available cities
GET /api/v1/cities/{city_id}       — city config (center, zoom, geojson_url)
```

**Acceptance criteria:**
- Returns Astana in the list
- Config includes `center`, `zoom`, `id`, `name`

---

### [A-Inspector] Inspector — backend router
**Status:** `[x]`  
**Priority:** High  
**Depends on:** A-3, A-5

**What was built:**  
`backend/routers/inspector.py` — анализирует 5 факторов риска для каждого района и возвращает приоритизированный список для превентивных проверок.

**Endpoint:**
```http
GET /api/v1/inspector?city=astana
```

**5 факторов риска:**
1. Высокий индекс риска района (≥70/100)
2. Последний пожар менее 14 дней назад
3. Сезонный пик (январь, февраль, май, июнь)
4. Доля промышленных объектов и стройплощадок ≥25%
5. Опасная причина в последние 30 дней (electrical / arson)

**Приоритет:** critical (4-5 факторов) → high (3) → medium (2) → low (1)

**Response includes:** `district`, `priority`, `matched_factors`, `factors[]`, `recommendation`, `days_since_last_incident`, `avg_damage_tenge`

---

### [B-Inspector] Inspector — frontend page
**Status:** `[x]`  
**Priority:** High  
**Depends on:** B-1, A-Inspector

**What was built:**  
`frontend/src/app/dashboard/inspector/page.tsx` — страница Инспектора с раскрывающимися карточками по районам.

**UI features:**
- Карточки отсортированы по приоритету (critical первыми)
- Каждая карточка раскрывается: показывает все 5 факторов с ✅/⬜, статистику, рекомендацию
- Summary-бейджи вверху: «1 критических», «1 высоких»
- Выделен в сайдбаре оранжевым как главная фича

---

### [A-11] Fire stations data + router
**Status:** `[x]`  
**Priority:** High  
**Depends on:** A-3, C-1

**What to build:**  
`backend/data/sample/astana_stations.json` + `backend/routers/stations.py` + extend `backend/services/data_loader.py`

**What to include:**  
Создать seed-данные по пожарным частям Астаны:
```json
[
  {
    "id": "station-1",
    "city": "astana",
    "name": "ПЧ-1",
    "district": "Есіл",
    "lat": 51.17,
    "lon": 71.44,
    "units": 6,
    "staff_count": 48
  }
]
```

**Endpoints:**
```http
GET /api/v1/stations?city=astana
GET /api/v1/stations/coverage?city=astana
```

**Coverage response:**
```json
[
  {
    "district": "Есіл",
    "nearest_station": "ПЧ-1",
    "distance_km": 2.8,
    "estimated_response_min": 7.4
  }
]
```

**Implementation notes:**
- Hardcode/load stations from JSON
- Add `get_stations(city)` to `DataLoader`
- For coverage:
  - use district centroids from GeoJSON properties
  - compute straight-line distance
  - estimate response time with simple formula:
    `estimated_response_min = max(3, distance_km * 2.5)`

**Acceptance criteria:**
- Returns list of Astana fire stations
- Coverage endpoint returns one row per district
- Invalid city returns 404

**Notes:** Added `backend/data/sample/astana_stations.json`, `backend/routers/stations.py`, `DataLoader.get_stations(city)` and GeoJSON centroid-based coverage calculation.

---

### [A-12] Hydrants data + router
**Status:** `[x]`  
**Priority:** High  
**Depends on:** A-3, C-1

**What to build:**  
`backend/data/sample/astana_hydrants.json` + `backend/routers/hydrants.py` + extend `backend/services/data_loader.py`

**Hydrant schema:**
```json
[
  {
    "id": "hydrant-1",
    "city": "astana",
    "district": "Алматы",
    "address": "ул. Тәуелсіздік 10",
    "lat": 51.21,
    "lon": 71.35,
    "status": "working"
  }
]
```

**Allowed statuses:**
- `working`
- `maintenance`
- `out_of_service`

**Endpoints:**
```http
GET /api/v1/hydrants?city=astana
GET /api/v1/hydrants?city=astana&status=working
```

**Acceptance criteria:**
- Returns hydrants for Astana
- Status filter works
- No null coordinates
- Invalid city returns 404

**Notes:** Added `backend/data/sample/astana_hydrants.json`, `backend/routers/hydrants.py`, and `DataLoader.get_hydrants(city, status)` backed by cached JSON seed data.

---

### [A-13] Minimal auth + role model
**Status:** `[x]`  
**Priority:** Medium  
**Depends on:** A-1

**What to build:**  
`backend/routers/auth.py` + `backend/services/auth_service.py`

**Roles:**
- `viewer`
- `dispatcher`
- `analyst`
- `admin`

**MVP approach:**
- No database yet
- Hardcoded users in memory / JSON file:
```json
[
  { "email": "admin@firewatch.kz", "password": "admin123", "role": "admin" },
  { "email": "analyst@firewatch.kz", "password": "analyst123", "role": "analyst" }
]
```

**Endpoints:**
```http
POST /api/v1/auth/login
GET /api/v1/auth/me
```

**Response shape:**
```json
{
  "token": "mock-jwt-or-signed-token",
  "user": {
    "email": "admin@firewatch.kz",
    "role": "admin"
  }
}
```

**Acceptance criteria:**
- Login works for test users
- `/me` returns current user
- Invalid credentials return 401

**Notes:** Added `backend/services/auth_service.py` and `backend/routers/auth.py` with hardcoded MVP users, signed bearer token, `/auth/login`, and `/auth/me`.

---

### [A-14] Inspection plan generator
**Status:** `[x]`  
**Priority:** High  
**Depends on:** A-3, A-5, A-8

**What to build:**  
`backend/routers/inspection_plan.py` + `backend/services/inspection_planner.py`

**Endpoint:**
```http
GET /api/v1/inspection-plan?city=astana
```

**Response:**
```json
{
  "city": "astana",
  "generated_at": "2026-04-05T10:00:00Z",
  "items": [
    {
      "district": "Байқоңыр",
      "priority": "high",
      "reason": "High risk score and severe incident pattern",
      "recommended_actions": [
        "Inspect industrial facilities",
        "Check electrical systems",
        "Review hydrant availability"
      ]
    }
  ]
}
```

**Planning rules:**
- High priority if `risk_score >= 70`
- Medium if `40 <= risk_score < 70`
- Add cause-driven action text based on top cause
- Use KPI/risk-map data only, no LLM required for MVP

**Acceptance criteria:**
- Returns at least 3 prioritized items
- Output is deterministic
- Highest-risk district appears first

**Notes:** Added `backend/services/inspection_planner.py` and `backend/routers/inspection_plan.py` with deterministic priority rules based on `risk_score` and district top cause.

---

### [A-15] Operations log router
**Status:** `[x]`  
**Priority:** Medium  
**Depends on:** A-3, A-11

**What to build:**  
`backend/data/sample/astana_operations.csv` + `backend/routers/operations.py`

**CSV fields:**
```csv
id,date,city,district,station_id,incident_id,response_time_min,outcome,notes
```

**Endpoint:**
```http
GET /api/v1/operations?city=astana
GET /api/v1/operations/kpi?city=astana
```

**KPI response:**
```json
{
  "city": "astana",
  "avg_response_time_min": 8.4,
  "operations_count": 214,
  "fastest_station": "ПЧ-1",
  "slowest_district": "Нұра"
}
```

**Acceptance criteria:**
- Operations list loads from sample CSV
- KPI endpoint aggregates correctly
- Response time is numeric and usable in charts

**Notes:** Added `backend/data/sample/astana_operations.csv`, `backend/routers/operations.py`, and `DataLoader.get_operations(city)` for operations listing and KPI aggregation.

---

## Track B — Frontend
> B-1 can start immediately. B-2 through B-6 depend on B-1.  
> Frontend can use mock/static data until backend Track A is ready.

---

### [B-1] Frontend project scaffold
**Status:** `[ ]`  
**Priority:** High  
**Depends on:** nothing

**What to build:**  
Initialize Next.js 15 app under `frontend/`.

```bash
npx create-next-app@latest frontend \
  --typescript --tailwind --eslint \
  --app --src-dir --import-alias "@/*" --no-git
```

**Additional packages to install:**
```bash
npm install recharts react-leaflet leaflet @types/leaflet
npm install lucide-react clsx
```

**File structure after scaffold:**
```
frontend/src/
├── app/
│   ├── layout.tsx          # root layout, city context provider
│   ├── page.tsx            # redirect to /dashboard
│   └── dashboard/
│       └── page.tsx        # main dashboard page
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   ├── TopBar.tsx      # city selector lives here
│   │   └── StatCard.tsx
│   ├── map/
│   │   └── RiskMap.tsx     # Leaflet map placeholder
│   ├── charts/
│   │   ├── ForecastChart.tsx
│   │   └── IncidentsByDistrict.tsx
│   ├── ai/
│   │   ├── ChatPanel.tsx
│   │   └── RecommendationCard.tsx
│   └── telegram/
│       └── TelegramConfig.tsx
├── lib/
│   ├── api.ts              # typed fetch wrappers for all backend endpoints
│   └── types.ts            # shared TypeScript interfaces
└── context/
    └── CityContext.tsx     # React context for selected city
```

**`lib/types.ts`** must define:
```typescript
export interface City { id: string; name: string; center: [number, number]; zoom: number }
export interface DistrictRisk { district: string; risk_score: number; total_incidents: number; top_cause: string; avg_damage_tenge: number }
export interface ForecastPoint { period: string; predicted?: number; actual?: number; lower_80?: number; upper_80?: number }
export interface Recommendation { priority: 'high' | 'medium' | 'low'; title: string; description: string; expected_impact: string }
export interface KPI { total_incidents_ytd: number; vs_last_year_pct: number; total_damage_tenge: number; highest_risk_district: string; prevention_potential_tenge: number }
export interface ChatMessage { role: 'user' | 'assistant'; content: string }
```

**`lib/api.ts`** — create typed fetch functions for every backend endpoint (can point to `localhost:8000` via env var).

**Acceptance criteria:**
- `npm run dev` starts without errors
- Dashboard page renders (even if empty)
- All component files exist

---

### [B-2] TopBar with city selector
**Status:** `[ ]`  
**Priority:** High  
**Depends on:** B-1

**What to build:**  
`frontend/src/components/layout/TopBar.tsx` + `frontend/src/context/CityContext.tsx`

**TopBar UI:**
- Left: FireWatch logo + flame icon
- Center: City selector dropdown — fetches from `GET /api/v1/cities`, defaults to `astana`
- Right: "Last updated" timestamp

**CityContext:**
```typescript
const CityContext = createContext<{
  city: City | null
  setCity: (c: City) => void
}>()
```

Wrap `layout.tsx` in `CityContext.Provider`. All other components read city from context.

**Acceptance criteria:**
- Dropdown shows available cities
- Selecting a city updates context and re-fetches data in all panels
- Falls back to mock city list if API is unavailable

---

### [B-3] KPI stat cards
**Status:** `[ ]`  
**Priority:** High  
**Depends on:** B-1

**What to build:**  
`frontend/src/components/layout/StatCard.tsx` + integrate into `dashboard/page.tsx`

**Four stat cards (top of dashboard):**
| Card | Value | Subtext |
|---|---|---|
| Total incidents YTD | `187` | `vs last year: -12%` (green if negative) |
| Total damage | `₸1.84B` | formatted in billions/millions |
| Prevention potential | `₸552M` | "Preventable with AI program" |
| Highest risk district | `Байқоңыр` | risk score badge |

**Acceptance criteria:**
- Cards render with mock data
- Fetches real data from `GET /api/v1/kpi?city={city}`
- Positive `vs_last_year_pct` shown in red, negative in green

---

### [B-4] Interactive risk map
**Status:** `[ ]`  
**Priority:** High  
**Depends on:** B-1

**What to build:**  
`frontend/src/components/map/RiskMap.tsx`

**Map features:**
- Leaflet map centred on selected city
- Choropleth: district polygons coloured by `risk_score` (green → yellow → red)
- Click on district → tooltip showing: district name, risk score, total incidents, top cause
- Legend in bottom-right corner

**Color scale:**
```
0–33  → green  (#22c55e)
34–66 → yellow (#eab308)
67–100→ red    (#ef4444)
```

**Data source:** `GET /api/v1/risk-map?city={city}` for scores + city GeoJSON for boundaries.

**Note:** GeoJSON for Astana districts needs to be created or sourced. If not available, render circle markers at district centroids instead.

**Acceptance criteria:**
- Map renders without SSR errors (use `dynamic import` with `ssr: false`)
- Districts are coloured by risk score
- Tooltip shows on click

---

### [B-5] Forecast chart
**Status:** `[ ]`  
**Priority:** High  
**Depends on:** B-1

**What to build:**  
`frontend/src/components/charts/ForecastChart.tsx`

**Chart type:** Recharts `ComposedChart`
- Area for historical data (solid blue)
- Line for forecast (dashed orange)
- Shaded area between `lower_80` and `upper_80` (light orange, 20% opacity)
- X-axis: month labels
- Toggle buttons: 3M / 6M / 12M forecast horizon

**Data source:** `GET /api/v1/forecast?city={city}&months={months}`

**Acceptance criteria:**
- Chart renders with mock data
- Switching 3M/6M/12M refetches and re-renders
- Confidence interval band is visible

---

### [B-6] Recommendations panel
**Status:** `[ ]`  
**Priority:** Medium  
**Depends on:** B-1

**What to build:**  
`frontend/src/components/ai/RecommendationCard.tsx` + panel in dashboard

**UI:**
- Section title: "AI Recommendations"
- Refresh button (re-fetches, ignores cache)
- 5 cards, each showing: priority badge (red/yellow/green), title, description, expected impact

**Data source:** `GET /api/v1/recommendations?city={city}`

**Acceptance criteria:**
- 5 recommendation cards render
- Priority badge colour matches severity
- Loading spinner while fetching

---

### [B-7] AI chat panel
**Status:** `[ ]`  
**Priority:** Medium  
**Depends on:** B-1

**What to build:**  
`frontend/src/components/ai/ChatPanel.tsx`

**UI:**
- Collapsible side panel (right side)
- Message thread (user = right-aligned blue bubble, assistant = left-aligned grey bubble)
- Text input + send button
- Suggested questions shown when chat is empty:
  - "Какой район наиболее опасен?"
  - "Когда ожидается пик пожаров?"
  - "Какие меры снизят риск в Байқоңыр?"

**Data source:** `POST /api/v1/chat` with `{ message, city, history }`

**Acceptance criteria:**
- Messages send and receive
- History is maintained during session
- Suggested questions auto-fill input on click

---

### [B-8] Telegram config panel
**Status:** `[ ]`  
**Priority:** Low  
**Depends on:** B-1

**What to build:**  
`frontend/src/components/telegram/TelegramConfig.tsx`

**UI:**
- Simple form: Bot Token (masked), Chat ID
- "Send Test Alert" button → calls `POST /api/v1/telegram/test?city={city}`
- Status badge: Connected / Not configured

**Acceptance criteria:**
- Form renders
- Test button triggers API call and shows success/error toast

---

### [B-9] Fire stations layer on map
**Status:** `[x]`  
**Priority:** High  
**Depends on:** B-4, A-11

**What to build:**  
Extend `frontend/src/components/map/RiskMap.tsx`

**UI features:**
- Add station markers to map
- Marker popup shows:
  - station name
  - district
  - units
  - staff count
- Add toggle:
  - `Районы`
  - `Пожарные части`
  - `Гидранты` (future-ready placeholder allowed)

**Data source:**  
`GET /api/v1/stations?city={city}`

**Acceptance criteria:**
- Stations render on the map
- Popups open on click
- Layer toggle works without page reload

**Notes:** Extended `frontend/src/components/map/RiskMap.tsx` with fire-station markers, popups, and a shared layer toggle.

---

### [B-10] Hydrants map layer
**Status:** `[x]`  
**Priority:** Medium  
**Depends on:** B-9, A-12

**What to build:**  
Extend `frontend/src/components/map/RiskMap.tsx`

**UI behavior:**
- Hydrant markers on map
- Color by status:
  - working → blue
  - maintenance → yellow
  - out_of_service → red
- Popup:
  - address
  - district
  - status

**Acceptance criteria:**
- Hydrants render correctly
- Status color is visible
- Layer toggle can hide/show hydrants

**Notes:** Extended `frontend/src/components/map/RiskMap.tsx` with hydrant markers, status-based colors, and popup details.

---

### [B-11] Frontend auth shell + role guards
**Status:** `[x]`  
**Priority:** Medium  
**Depends on:** B-1, A-13

**What to build:**  
`frontend/src/app/login/page.tsx` + `frontend/src/context/AuthContext.tsx`

**Features:**
- Login form
- Persist token in `localStorage`
- Protect dashboard routes
- Display current role in top bar
- Hide admin-only controls for non-admin users

**Acceptance criteria:**
- Unauthenticated user is redirected to `/login`
- Successful login opens dashboard
- Role-based UI hiding works

**Notes:** Added `frontend/src/context/AuthContext.tsx`, `frontend/src/lib/auth.ts`, and `frontend/src/app/login/page.tsx` with token persistence, session restore, and reusable `RequireAuth` / `useAuth` helpers.

---

### [B-12] Inspection plan panel
**Status:** `[x]`  
**Priority:** Medium  
**Depends on:** B-6, A-14

**What to build:**  
`frontend/src/components/ai/InspectionPlanPanel.tsx`

**UI:**
- Section title: "План проверок"
- Cards grouped by priority
- Each item shows:
  - district
  - reason
  - recommended actions

**Acceptance criteria:**
- Pulls real data from `/inspection-plan`
- Priority is color-coded
- Empty/loading states are handled

**Notes:** Added `frontend/src/components/ai/InspectionPlanPanel.tsx` and integrated the panel into the main dashboard.

---

### [B-13] Operations analytics panel
**Status:** `[x]`  
**Priority:** Medium  
**Depends on:** B-3, B-5, A-15

**What to build:**  
`frontend/src/components/charts/ResponseTimeChart.tsx`

**UI:**
- Line/bar chart for response times
- Small KPI summary:
  - average response time
  - fastest station
  - slowest district

**Acceptance criteria:**
- Uses `/operations/kpi`
- Renders without SSR issues
- Updates on city change

**Notes:** Added `frontend/src/components/charts/ResponseTimeChart.tsx` and integrated operations analytics into the main dashboard.

---

## Track C — Data & GeoJSON
> Fully independent, can run in parallel with A and B.

---

### [C-1] Astana districts GeoJSON
**Status:** `[x]`  
**Priority:** High  
**Depends on:** nothing

**What to build:**  
`backend/data/geojson/astana_districts.geojson`

Create or source a GeoJSON FeatureCollection of Astana's 5 administrative districts:
- Есіл (Yesil)
- Алматы (Almaty)
- Байқоңыр (Baikonur)
- Сарыарқа (Saryarka)
- Нұра (Nura)

Each Feature must have:
```json
{ "properties": { "district": "Есіл", "district_en": "Yesil" } }
```

If exact boundaries are not findable, create approximate polygon coordinates based on the known geography of Astana (the city sits at ~51.18°N, 71.45°E).

**Acceptance criteria:**
- Valid GeoJSON FeatureCollection
- All 5 districts present
- Polygons roughly cover Astana's area

---

## Track D — Deployment
> Start after Track A and B are both functional locally.

---

### [D-1] Railway deployment config
**Status:** `[ ]`  
**Priority:** Medium  
**Depends on:** A-1, B-1

**What to build:**  
Config files for Railway deployment.

**`backend/Procfile`:**
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

**`backend/runtime.txt`:**
```
python-3.11
```

**`frontend/Dockerfile`** (or let Railway use Nixpacks — add a `railway.json`):
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "NIXPACKS" },
  "deploy": { "startCommand": "npm run start", "restartPolicyType": "ON_FAILURE" }
}
```

**`frontend/.env.local.example`:**
```
NEXT_PUBLIC_API_URL=https://your-api.up.railway.app
```

**Acceptance criteria:**
- Both services deploy on Railway without manual config
- Frontend can reach backend via `NEXT_PUBLIC_API_URL` env var

---

## Status Summary

| Task | Track | Status | Parallel with |
|---|---|---|---|
| A-1 Backend scaffold | A | `[x]` | A-2, B-1, C-1 |
| A-2 Synthetic data | A | `[x]` | A-1, B-1, C-1 |
| A-3 Data loader | A | `[x]` | — |
| A-4 Forecast router | A | `[x]` | A-5, A-8, A-9 |
| A-5 Risk map router | A | `[x]` | A-4, A-8, A-9 |
| A-6 Recommendations | A | `[x]` | A-7 |
| A-7 AI chat | A | `[x]` | A-6 |
| A-8 KPI router | A | `[x]` | A-4, A-5 |
| A-9 Telegram router | A | `[x]` | A-4, A-5 |
| A-10 Cities router | A | `[x]` | — |
| A-Inspector Inspector backend | A | `[x]` | B-Inspector |
| B-Inspector Inspector frontend | B | `[x]` | — |
| A-11 Fire stations | A | `[x]` | A-12, B-9 |
| A-12 Hydrants router | A | `[x]` | A-11, B-10 |
| A-13 Minimal auth | A | `[x]` | B-11 |
| A-14 Inspection plan | A | `[x]` | B-12 |
| A-15 Operations log | A | `[x]` | B-13 |
| B-1 Frontend scaffold | B | `[x]` | A-1, A-2, C-1 |
| B-2 City selector | B | `[x]` | B-3, B-4, B-5 |
| B-3 KPI cards | B | `[x]` | B-2, B-4, B-5 |
| B-4 Risk map | B | `[x]` | B-2, B-3, B-5 |
| B-5 Forecast chart | B | `[x]` | B-2, B-3, B-4 |
| B-6 Recommendations | B | `[x]` | B-7, B-8 |
| B-7 AI chat panel | B | `[x]` | B-6, B-8 |
| B-8 Telegram panel | B | `[x]` | B-6, B-7 |
| B-9 Fire stations map | B | `[x]` | B-10 |
| B-10 Hydrants layer | B | `[x]` | — |
| B-11 Frontend auth | B | `[x]` | — |
| B-12 Inspection panel | B | `[x]` | B-13 |
| B-13 Operations analytics | B | `[x]` | — |
| C-1 Astana GeoJSON | C | `[x]` | Everything |
| D-1 Railway config | D | `[x]` | — |
| A-16 Buildings GET/{id} endpoint | A | `[x]` | A-1 |
| A-17 Hydrants PATCH/{id} endpoint + new fields | A | `[x]` | A-12 |
| A-18 Emergency routing service + router | A | `[x]` | A-11 |
| B-14 Buildings page + QR modal | B | `[x]` | A-16 |
| B-15 Public plan viewer /plan/[id] | B | `[x]` | A-16 |
| B-16 Hydrants page with mobile update form | B | `[x]` | A-17 |
| B-17 Emergency routing page with map | B | `[x]` | A-18 |

---

# v2.0 — Per-building Risk + Document Ingestion

> См. `ARCHITECTURE_v2.md` для полного контекста.
> Решения по реализации зафиксированы 2026-05-13:
> - Hosting: Railway (без TimescaleDB пока)
> - Storage: Cloudflare R2 (не MinIO)
> - Buildings source: OSM-first, но через `BuildingsProvider` абстракцию для свапа на 2GIS
> - v1 API (`/api/v1/*`) работает параллельно с v2 до конца Фазы 2
> - Реальные оперкарточки недоступны → генерируем синтетику для тестов

**Фазы:**
- **Фаза 1 (E + F + G)** — DB foundation + Document Ingestion (5 недель)
- **Фаза 2 (H + I)** — Per-building risk model + UI (5 недель)
- **Фаза 3 (J)** — Polish, RBAC, observability, v1 cleanup (3-4 недели)

---

## Track E — Database Foundation (Фаза 1)

> Без этого трека ничего из v2 не поедет. E-1 → E-2 → остальные параллельно.

---

### [E-1] Railway Postgres + PostGIS setup
**Status:** `[ ]`
**Priority:** Critical
**Depends on:** nothing

**What to build:**
Поднять managed PostgreSQL 16 на Railway, активировать PostGIS 3.4, подключить `backend` сервис.

**Steps:**
- Railway → Add Service → PostgreSQL
- Connect to backend via `DATABASE_URL` env var (Railway auto-injects)
- Через Railway Web Shell или psql: `CREATE EXTENSION IF NOT EXISTS postgis;` `CREATE EXTENSION IF NOT EXISTS pgcrypto;` (для `gen_random_uuid`)
- Локально: `docker-compose.yml` с `postgis/postgis:16-3.4` для dev
- Обновить `.env.example` и `backend/README.md` с `DATABASE_URL` примером

**Acceptance criteria:**
- `SELECT PostGIS_Version();` возвращает 3.4.x на проде
- Локальный docker-compose поднимает Postgres+PostGIS одной командой
- Backend на Railway видит DATABASE_URL

---

### [E-2] SQLAlchemy + Alembic scaffold
**Status:** `[ ]`
**Priority:** Critical
**Depends on:** E-1

**What to build:**
Подключить SQLAlchemy 2.x (async) и Alembic в `backend/`.

**Add to `requirements.txt`:**
```
sqlalchemy[asyncio]==2.0.30
alembic==1.13.2
asyncpg==0.29.0
geoalchemy2==0.15.2
```

**File structure:**
```
backend/
├── db/
│   ├── __init__.py
│   ├── session.py          # async engine + session factory
│   └── base.py             # DeclarativeBase
├── models/
│   ├── __init__.py
│   └── (per-table модели появятся в E-3, E-4)
└── alembic/
    ├── env.py
    ├── alembic.ini
    └── versions/
```

**Session config:** asyncpg pool, `pool_size=10`, `pool_pre_ping=True`.

**Acceptance criteria:**
- `alembic upgrade head` работает (пока без миграций)
- `alembic revision --autogenerate -m "..."` создаёт пустую миграцию
- Можно сделать `async with get_session() as s:` в FastAPI dependency

---

### [E-3] Migration: core entities
**Status:** `[ ]`
**Priority:** Critical
**Depends on:** E-2

**What to build:**
Первая Alembic-миграция: `cities`, `buildings`, `users`, `audit_log`.

**Tables (упрощённый набор v1-совместимых полей):**

`cities`:
- `id UUID PK`, `code TEXT UNIQUE` (e.g. 'astana'), `name TEXT`, `center GEOMETRY(POINT, 4326)`, `zoom INT`

`buildings` (см. ARCHITECTURE_v2.md §4.3, но без `building_features`):
- Все поля из schema в доке
- **Важно:** `source TEXT NOT NULL` ('osm'/'2gis'/'manual'/'document_extract'), `external_id TEXT`, UNIQUE(source, external_id)
- GIST индексы на `geom` и `centroid`

`users`:
- `id UUID PK`, `email UNIQUE`, `full_name`, `role TEXT` (admin/analyst/inspector/viewer), `password_hash`, `created_at`, `last_login_at`
- Сидим 4 тестовых юзера в миграции (см. A-13)

`audit_log`:
- Как в доке, индексы на (entity_type, entity_id) и occurred_at

**Acceptance criteria:**
- `alembic upgrade head` создаёт все 4 таблицы
- В `cities` засеян 1 город — Астана (с centroid 51.18, 71.45, zoom 12)
- Можно сделать `SELECT * FROM buildings;` (пусто, но без ошибки)

---

### [E-4] Migration: incidents, hydrants, stations, operations
**Status:** `[ ]`
**Priority:** Critical
**Depends on:** E-3

**What to build:**
Вторая миграция: `incidents`, `hydrants`, `fire_stations`, `operations`, `inspections`.

**Tables:** см. ARCHITECTURE_v2.md §4.3 + v1-совместимость:
- `incidents` — добавить `district TEXT` (для legacy v1 endpoints)
- `hydrants` — поля из A-17 (status enum: working/maintenance/out_of_service)
- `fire_stations` — поля из A-11 (units, staff_count)
- `operations` — все поля из A-15

**Acceptance criteria:**
- Миграция применяется без ошибок
- Все GIST индексы созданы (видны в `\di+`)
- Foreign keys корректны

---

### [E-5] Migration: documents (operational_cards + card_extractions)
**Status:** `[ ]`
**Priority:** High
**Depends on:** E-3

**What to build:**
Третья миграция: `operational_cards`, `card_extractions`.

См. ARCHITECTURE_v2.md §4.3, без изменений.

**Acceptance criteria:**
- Обе таблицы созданы
- FK `card_extractions.card_id → operational_cards.id` с `ON DELETE CASCADE`
- FK `operational_cards.uploaded_by → users.id`

---

### [E-6] CSV → Postgres migration script
**Status:** `[ ]`
**Priority:** High
**Depends on:** E-3, E-4

**What to build:**
`backend/scripts/migrate_csv_to_db.py` — одноразовый перенос всех существующих CSV-данных в БД.

**Migrates:**
- `astana_incidents.csv` → `incidents` (генерим `district` по lat/lon если нужно)
- `astana_stations.json` → `fire_stations`
- `astana_hydrants.json` → `hydrants`
- `astana_operations.csv` → `operations`
- Тестовые юзеры из `auth_service.py` → `users`

**Idempotent:** скрипт можно запустить много раз, дубликатов не создаст (по `external_id` или composite key).

**Acceptance criteria:**
- После запуска: `SELECT COUNT(*) FROM incidents` ≈ 834
- Все 5 районов Астаны представлены в `incidents.district`
- Гидранты и станции имеют валидные `geom`

---

### [E-7] data_loader_v2 — SQLAlchemy backend
**Status:** `[ ]`
**Priority:** High
**Depends on:** E-6

**What to build:**
`backend/services/data_loader_v2.py` — замена pandas-based `data_loader.py` для v2 эндпоинтов.

**Interface:** те же методы что в v1 (`get_incidents`, `get_district_stats`, etc.), но возвращают dict'ы а не DataFrame, читают из Postgres.

**v1 НЕ ТРОГАЕМ** — старый `data_loader.py` продолжает работать с CSV для `/api/v1/*`.

**Acceptance criteria:**
- Все методы async, используют SQLAlchemy
- Performance: `get_district_stats('astana')` < 100ms
- Покрыт unit-тестами на in-memory test DB

---

### [E-8] BuildingsProvider abstraction
**Status:** `[ ]`
**Priority:** High
**Depends on:** E-3

**What to build:**
Абстракция для пуллинга зданий из разных источников (OSM сейчас, 2GIS потом).

**File structure:**
```
backend/services/providers/
├── __init__.py
├── base.py              # abstract BuildingsProvider
├── osm_provider.py      # Overpass API impl
└── twogis_provider.py   # NotImplementedError stub
```

**Interface:**
```python
class BuildingsProvider(ABC):
    @abstractmethod
    async def fetch_buildings(self, bbox: BBox) -> list[BuildingDTO]: ...

    @abstractmethod
    def source_name(self) -> Literal['osm', '2gis']: ...
```

**`BuildingDTO`** — Pydantic модель с полями для upsert в `buildings`. `external_id` обязателен.

**Factory:** `get_provider(name: str) -> BuildingsProvider` читает `BUILDINGS_PROVIDER` env var ('osm' по умолчанию).

**Acceptance criteria:**
- OSM provider возвращает здания для bbox Астаны через Overpass
- Можно мокнуть provider в тестах
- Свап на 2GIS позже — добавить новый класс, поменять env var

---

## Track F — Document Ingestion Backend (Фаза 1)

> F-1, F-2, F-4 параллельны. F-3 → F-5 → F-6 → F-7 → F-8 последовательно.

---

### [F-1] Cloudflare R2 storage integration
**Status:** `[ ]`
**Priority:** Critical
**Depends on:** E-2

**What to build:**
`backend/services/storage.py` — обёртка над S3-совместимым API R2.

**Use `boto3`** с custom endpoint URL. Кладём в `backend/requirements.txt`: `boto3==1.34.0`.

**Interface:**
```python
class StorageService:
    async def upload(self, key: str, content: bytes, mime: str) -> str  # returns URL
    async def download(self, key: str) -> bytes
    async def presigned_get(self, key: str, ttl_seconds: int = 3600) -> str
    async def delete(self, key: str): ...
```

**Env vars:**
```
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=firewatch-documents
R2_PUBLIC_URL=https://...
```

**Key structure:** `documents/{user_id}/{card_uuid}/original.{ext}` + `documents/{user_id}/{card_uuid}/converted.pdf` + `documents/{user_id}/{card_uuid}/thumb.jpg`

**Acceptance criteria:**
- Upload + download + delete работают на боевом R2
- Presigned URLs валидны и истекают
- Локальная альтернатива: `LOCAL_STORAGE_PATH` env var переключает на disk (для разработки без R2)

---

### [F-2] Celery + Redis async workers
**Status:** `[ ]`
**Priority:** Critical
**Depends on:** E-2

**What to build:**
Celery worker для async-обработки документов.

**Add to requirements:** `celery[redis]==5.4.0`, `redis==5.0.4`

**File structure:**
```
backend/
├── celery_app.py           # Celery instance
├── workers/
│   ├── __init__.py
│   └── documents.py        # task definitions (заполнятся в F-3, F-5)
```

**Railway:** добавить второй сервис `backend-worker` с командой `celery -A celery_app worker -l info`. Redis — Railway add-on.

**Broker URL** через env `REDIS_URL`.

**Acceptance criteria:**
- Worker стартует на Railway без ошибок
- Тестовая задача `celery_app.send_task('ping')` возвращает результат
- API endpoint может зашедулить задачу и не блокироваться

---

### [F-3] Document upload + normalization
**Status:** `[ ]`
**Priority:** High
**Depends on:** E-5, F-1, F-2

**What to build:**
- `POST /api/v2/documents/upload` (multipart) — приём файла, запись в R2, создание `operational_cards` record со статусом `uploaded`, запуск Celery task
- Celery task `normalize_document(card_id)`:
  - DOCX/DOC/VSD → PDF через `libreoffice --headless --convert-to pdf` (LibreOffice ставим в worker Docker image)
  - JPG/PNG/PDF — без конвертации
  - Генерация thumbnail (first page → JPG 400px)
  - Update status → `ready_for_extraction`

**Dockerfile для worker:**
```
FROM python:3.11
RUN apt-get update && apt-get install -y libreoffice
...
```

**Acceptance criteria:**
- Можно загрузить PDF/DOCX/VSD/JPG через curl
- Файл появляется в R2
- После ~30 сек статус карточки = `ready_for_extraction`
- Thumbnail доступен через presigned URL

---

### [F-4] Synthetic operational cards generator
**Status:** `[x]`
**Priority:** High
**Depends on:** nothing (не зависит от БД)

**What to build:**
`backend/scripts/generate_synthetic_cards.py` — генератор фейковых оперкарточек в стиле формы МЧС РК.

**Output:** 30-50 файлов в `backend/data/sample/synthetic_cards/`:
- 15 PDF (с реальным текстом, через `reportlab`)
- 10 scan-like JPG (рендер PDF → noise + skew, через `pdf2image` + `Pillow`)
- 5 DOCX (через `python-docx`)
- 5 битых/неполных карточек (для теста edge cases)

**Поля карточки** (берём из Pydantic schema в ARCHITECTURE_v2.md §6.3):
- Номер карточки, дата утверждения
- Объект: название, адрес (реальные адреса Астаны), категория Ф1-Ф5
- Здание: этажи, площадь, материалы, год постройки
- Системы ПБ: сигнализация, спринклеры, эвакуационные выходы
- Гидранты рядом, водоисточники
- Особенности: газовые системы, опасные материалы

**Variation:** случайные значения, иногда специально пропущенные поля, иногда устаревшие даты revision.

**Acceptance criteria:**
- 30+ файлов сгенерированы
- PDF/JPG/DOCX все валидны (открываются)
- Покрывают разные типы зданий (ТРЦ, школа, жилой, склад)

---

### [F-5] Pydantic extraction schema + Claude tool
**Status:** `[ ]`
**Priority:** High
**Depends on:** F-3

**What to build:**
- `backend/services/extraction/schema.py` — Pydantic-модель `OperationalCardExtraction` из ARCHITECTURE_v2.md §6.3
- `backend/services/extraction/extractor.py` — wrapper Claude Sonnet 4 с tool use
- Конвертация PDF → image blocks для Claude (vision API; разбиваем на pages, до 100 страниц за раз)

**System prompt:** см. ARCHITECTURE_v2.md §5.4

**Costs tracking:** возврашать tokens used + computed cost USD из API response, писать в `card_extractions.extraction_cost_usd`.

**Acceptance criteria:**
- Прогон на синтетических карточках из F-4 даёт валидный JSON по schema
- Confidence score для каждого поля от 0 до 1
- Cost per card < $0.20

---

### [F-6] Extraction Celery task
**Status:** `[ ]`
**Priority:** High
**Depends on:** F-5

**What to build:**
Celery task `extract_document(card_id)`:
- Читает PDF из R2
- Зовёт extractor из F-5
- Пишет результат в `card_extractions`
- Обновляет `operational_cards.status` → `extracted`, `extraction_id`

Триггерится автоматически после F-3 (normalization → extraction в chain).

**Acceptance criteria:**
- Загруженный документ через 60 сек имеет статус `extracted`
- В `card_extractions` есть JSON с полями и confidences
- Если Claude API падает — retry с exponential backoff (3 попытки)

---

### [F-7] Vulnerability analysis task
**Status:** `[ ]`
**Priority:** Medium
**Depends on:** F-6

**What to build:**
Celery task `analyze_vulnerabilities(extraction_id)`:
- Берёт extracted_data + raw_text
- Зовёт Claude Sonnet 4 с промптом из ARCHITECTURE_v2.md §6.4
- Пишет `vulnerabilities[]` в `card_extractions.vulnerabilities`
- Status → `review` (готово к проверке человеком)

**Acceptance criteria:**
- На синтетической карточке с заведомо отсутствующим дымоудалением — vulnerability с severity ≥ high
- Каждая vulnerability имеет `regulation_violated` и `recommended_action`

---

### [F-8] Document approval → buildings upsert
**Status:** `[ ]`
**Priority:** High
**Depends on:** F-7, E-8

**What to build:**
- `POST /api/v2/documents/{id}/approve` — финализация
- На approve: парсим `extracted_data`, делаем UPSERT в `buildings` (source='document_extract', external_id=card_id), обновляем связанные `hydrants` если упомянуты
- Триггер пересчёта features (placeholder — реальный pipeline в H-4)
- Audit log

**Acceptance criteria:**
- После approve: новое здание в `buildings` с правильными полями
- Если здание уже было (matched по адресу) — обновляется, source меняется на document_extract если confidence выше
- Запись в `audit_log`

---

### [F-9] Documents list + status endpoints
**Status:** `[ ]`
**Priority:** Medium
**Depends on:** F-3

**What to build:**
```
GET    /api/v2/documents?status=&uploaded_by=&limit=
GET    /api/v2/documents/{id}
GET    /api/v2/documents/{id}/status       # для polling из UI
GET    /api/v2/documents/{id}/extraction
PATCH  /api/v2/documents/{id}/extraction   # human corrections
DELETE /api/v2/documents/{id}
```

**Acceptance criteria:**
- Все эндпоинты возвращают валидный JSON
- PATCH сохраняет changes в audit_log

---

## Track G — Document Ingestion Frontend (Фаза 1)

> G-1 → G-2 → G-3 → G-4. G-5, G-6 параллельны с G-4.

---

### [G-1] Documents list page
**Status:** `[ ]`
**Priority:** High
**Depends on:** F-9

**What to build:**
`frontend/src/app/dashboard/documents/page.tsx`

**UI:**
- Таблица: имя файла, дата загрузки, статус (chip), кто загрузил, building (если matched)
- Фильтр по статусу (uploaded / extracting / review / approved / rejected)
- Кнопка "Загрузить документ" → открывает upload modal (G-2)
- Click на row → переход на `/dashboard/documents/[id]`

**Data:** `GET /api/v2/documents`

**Acceptance criteria:**
- Таблица рендерится с моковыми данными если API недоступен
- Polling каждые 5 сек для документов в статусах `extracting`/`converting`
- Мобильная адаптивность (карточки на 375px, таблица на ≥768px)

---

### [G-2] Upload modal with drag-drop
**Status:** `[ ]`
**Priority:** High
**Depends on:** G-1

**What to build:**
`frontend/src/components/documents/UploadModal.tsx`

**UI:**
- Dropzone (react-dropzone): "Перетащите карточку сюда или нажмите для выбора"
- Поддержка multiple files
- Прогресс-бар per file
- Подсказка форматов: PDF, DOCX, DOC, VSD, JPG, PNG, ZIP
- После upload → редирект на /dashboard/documents/[id]

**API:** `POST /api/v2/documents/upload`

**Acceptance criteria:**
- Drag-drop работает
- Прогресс обновляется
- Ошибки upload (413, 415) показываются юзеру по-русски

---

### [G-3] PDF preview component
**Status:** `[ ]`
**Priority:** High
**Depends on:** G-1

**What to build:**
`frontend/src/components/documents/PdfPreview.tsx`

**Stack:** `pdfjs-dist` через `react-pdf` wrapper.

**Features:**
- Загрузка PDF через presigned URL из API
- Пагинация (◀ ▶ + jump to page)
- Zoom in/out
- Highlight bbox при click на поле extraction (placeholder — реальная подсветка в G-6)

**SSR:** dynamic import с ssr: false (как Leaflet, см. feedback memory).

**Acceptance criteria:**
- PDF отображается
- Навигация между страницами работает
- Для не-PDF (JPG) — fallback на `<img>`

---

### [G-4] Side-by-side review UI
**Status:** `[ ]`
**Priority:** High
**Depends on:** G-3, F-7

**What to build:**
`frontend/src/app/dashboard/documents/[id]/page.tsx`

**UI:** см. mock в ARCHITECTURE_v2.md §6.5:
- Left panel (50%): PdfPreview из G-3
- Right panel (50%): scrollable форма с extracted полями
- Color-coding per field:
  - 🟢 confidence > 0.9 — read-only highlight
  - 🟡 0.6-0.9 — editable, фокус автоматически
  - 🔴 < 0.6 — required to confirm, save disabled
- Vulnerabilities секция снизу с severity badges
- Кнопки: "Отклонить" / "Сохранить и далее"

**Mobile:** tabs вместо split (PDF / Поля)

**Data:** `GET /api/v2/documents/{id}/extraction`

**Acceptance criteria:**
- Все поля редактируемы
- Save button disabled пока есть red fields без подтверждения
- Approve → `POST /api/v2/documents/{id}/approve` → редирект на список

---

### [G-5] Vulnerability cards UI
**Status:** `[ ]`
**Priority:** Medium
**Depends on:** G-4

**What to build:**
Компонент `VulnerabilityCard.tsx` внутри G-4.

**UI per card:**
- Severity badge (critical=red, high=orange, medium=yellow, low=gray)
- Description
- Ссылка на regulation_violated
- Recommended action как actionable bullet

**Acceptance criteria:**
- Карточки отсортированы по severity
- Раскрываются по клику

---

### [G-6] Bbox highlight on field click (stretch)
**Status:** `[ ]`
**Priority:** Low
**Depends on:** G-4, F-5

**What to build:**
При click на поле в правой панели — подсветить место в PDF где Claude нашёл значение.

**Approach:** просим Claude в F-5 возвращать `bbox` (page, x, y, width, height) для каждого поля. Рендерим overlay поверх PDF canvas.

**Note:** stretch goal — если Claude bbox не очень надёжен, можно отложить в v2.1.

**Acceptance criteria:**
- Click → подсветка появляется
- Работает на 80%+ полях (где confidence ≥ 0.7)

---

## Track H — Per-building Risk Backend (Фаза 2)

> H-1 → H-2 → H-3, H-4 параллельны. H-5 → H-6, H-7 параллельны. H-8 → H-9.

---

### [H-1] OSM buildings import
**Status:** `[ ]`
**Priority:** Critical
**Depends on:** E-8

**What to build:**
`backend/scripts/import_osm_buildings.py` — массовый импорт зданий Астаны через Overpass API.

**Steps:**
- Bbox Астаны: примерно 51.05..51.30, 71.30..71.60
- Overpass query: `way["building"](bbox); out geom;`
- Для каждого OSM way: парсим теги → BuildingDTO (через провайдер из E-8)
- UPSERT в `buildings` с source='osm', external_id=osm_id

**Idempotent:** повторный запуск обновляет уже существующие.

**Acceptance criteria:**
- 10K+ зданий импортировано (примерно ожидаем для Астаны)
- GIST индексы используются (EXPLAIN на bbox query)
- Скрипт можно запускать через `python -m scripts.import_osm_buildings --city astana`

---

### [H-2] Incident-to-building matching
**Status:** `[ ]`
**Priority:** High
**Depends on:** H-1

**What to build:**
`backend/scripts/match_incidents_to_buildings.py` — заполняет `incidents.building_id`.

**Approach:**
```sql
UPDATE incidents i
SET building_id = (
    SELECT b.id FROM buildings b
    WHERE ST_DWithin(b.geom::geography, i.geom::geography, 30)
    ORDER BY ST_Distance(b.geom, i.geom)
    LIMIT 1
)
WHERE building_id IS NULL;
```

**Acceptance criteria:**
- ≥70% инцидентов получили `building_id`
- Остальные — это inцидент в нежилых местах (улицы, поля) — это ok

---

### [H-3] Weather integration (без TimescaleDB)
**Status:** `[ ]`
**Priority:** Medium
**Depends on:** E-3

**What to build:**
- Таблица `weather_history` (обычная, не hypertable пока):
  ```sql
  CREATE TABLE weather_history (
      ts TIMESTAMPTZ NOT NULL,
      h3_cell TEXT NOT NULL,
      temp_c NUMERIC, wind_ms NUMERIC, humidity_pct NUMERIC, precipitation_mm NUMERIC,
      PRIMARY KEY (ts, h3_cell)
  );
  CREATE INDEX idx_weather_ts ON weather_history(ts DESC);
  ```
  Партиционируем по месяцу через PARTITION BY RANGE если объёмы вырастут.
- Celery beat: hourly task `fetch_weather` для Астаны
- Использует OpenWeatherMap (env `OPENWEATHERMAP_API_KEY`)

**H3 library:** `h3==4.1.0` (используется и в feature builder)

**Acceptance criteria:**
- Каждый час появляется запись в `weather_history` для центра Астаны (h3 res 8)
- За сутки набралось 24 точки

---

### [H-4] FeatureBuilder service
**Status:** `[ ]`
**Priority:** Critical
**Depends on:** H-2

**What to build:**
- Таблица `building_features` (см. ARCHITECTURE_v2.md §4.3)
- Celery task `rebuild_features(city_id)` — пересчёт для всех зданий города
- Запуск daily в 03:00

**Минимальный набор фичей (для MVP, не 50):**
1. `nearest_hydrant_m` — `ST_DWithin` query
2. `nearest_station_m`
3. `incidents_500m_3y` — count
4. `incidents_on_this_building_3y` — count
5. `building_density_500m`
6. `age_years` — `extract(year from now()) - year_built`
7. `population_estimate` — rough estimate по floors * area
8. `days_since_last_incident`
9. `days_since_last_inspection`
10. `building_type` (one-hot будет в препроцессинге модели)

**Performance:** для 10K зданий должно занимать < 5 минут (batch processing).

**Acceptance criteria:**
- Запуск таска заполняет `building_features` для всех зданий
- Idempotent (повторный запуск перезаписывает)

---

### [H-5] XGBoost Poisson baseline training
**Status:** `[ ]`
**Priority:** Critical
**Depends on:** H-4

**What to build:**
`backend/ml/baseline_trainer.py` — обучение модели baseline.

**Add to requirements:** `xgboost==2.0.3`, `scikit-learn==1.4.0`, `shap==0.45.0`

**Pipeline:**
- Загрузка `building_features` + target (`incidents_3y / 3` для rate в год)
- Time-based split: train на зданиях с feature_date < 2025-01, valid >= 2025-01
- Config из ARCHITECTURE_v2.md §5.1
- Метрики: Poisson deviance, lift в top-decile
- Сохранение модели через `joblib.dump` в `backend/ml/models/baseline_{date}.pkl`

**CLI:** `python -m ml.baseline_trainer --city astana --save`

**Acceptance criteria:**
- Модель обучается на синтетических данных (834 инцидента)
- Top-decile lift > 1.5 (зданий с predicted high risk действительно горят чаще среднего)
- Сохранённая модель загружается обратно

---

### [H-6] SHAP explanations + risk endpoint
**Status:** `[ ]`
**Priority:** High
**Depends on:** H-5

**What to build:**
- `backend/services/risk_predictor.py` — обёртка над загруженной моделью + SHAP TreeExplainer
- Таблица `risk_scores` (без TimescaleDB, обычная)
- Daily Celery task `compute_risk_scores` — заполняет `risk_scores` для всех зданий
- Эндпоинты:
  ```
  GET /api/v2/buildings?bbox=&min_risk=&limit=
  GET /api/v2/buildings/{id}
  GET /api/v2/buildings/{id}/risk?horizon=7|30|90
  GET /api/v2/buildings/{id}/factors  # SHAP top-5 + Haiku-explanation
  ```

**Haiku-explanation:** SHAP top-5 → Claude Haiku 4.5 → natural language объяснение на русском (как в v1 recommendations).

**Acceptance criteria:**
- Endpoint возвращает baseline + final score + top-5 факторов с весами
- Объяснение читаемое на русском
- Кешируется на 24ч

---

### [H-7] Dynamic modifier (rules)
**Status:** `[ ]`
**Priority:** High
**Depends on:** H-3, H-5

**What to build:**
`backend/services/dynamic_modifier.py` — реализация правил из ARCHITECTURE_v2.md §5.2.

Входит в `compute_risk_scores` task (H-6) как множитель к baseline.

**Inputs:** building, current_time, latest_weather для h3-cell здания.

**Output:** multiplier [0.3, 3.0] + breakdown по факторам (для UI).

**Acceptance criteria:**
- На день с tempC=-25 + wind=12 + holiday: multiplier ≈ 2.0+
- На обычный летний понедельник: ≈ 1.0
- Breakdown полей доступен через API для UI

---

### [H-8] Inspector v2 endpoint
**Status:** `[ ]`
**Priority:** High
**Depends on:** H-6

**What to build:**
`backend/routers/v2/inspector.py`

**Endpoints:**
```
GET /api/v2/inspector?city=&top_n=50&filter=
GET /api/v2/inspector/route?building_ids=[...]   # TSP-optimized
```

**TSP:** используем библиотеку или OR-tools если простой nearest-neighbour не достаточно. Для top-50 — OR-tools решает за <1s.

**Acceptance criteria:**
- Возвращает top-N зданий по final_score
- Route endpoint возвращает упорядоченный список + total_distance_km + estimated_time

---

### [H-9] v2 hydrants + stations endpoints
**Status:** `[ ]`
**Priority:** Medium
**Depends on:** E-4

**What to build:**
`/api/v2/hydrants` и `/api/v2/fire-stations` — те же что v1, но из Postgres + bbox фильтр.

**Acceptance criteria:**
- Bbox фильтрация работает через GIST индексы
- Совместимы с frontend контрактом v1 (можно мигрировать страницу постепенно)

---

## Track I — Per-building Risk Frontend (Фаза 2)

---

### [I-1] Buildings heatmap layer on map
**Status:** `[ ]`
**Priority:** Critical
**Depends on:** H-6, B-4

**What to build:**
Новый слой в `RiskMap.tsx` — здания с цветом по `final_score`.

**Performance:** 10K+ зданий — рендерить через Leaflet vector tiles или canvas renderer (`L.canvas()` режим), а не SVG markers.

**Color scale:** градиент green → yellow → red от 0 до max_risk в видимой области.

**Layer toggle:** добавить "Здания (риск)" в toggle из B-9.

**Acceptance criteria:**
- 10K зданий рендерятся плавно (60 fps на zoom/pan)
- Click на здание → переход на drill-down (I-2)
- Mobile: lazy load только в видимом bbox

---

### [I-2] Building drill-down page
**Status:** `[ ]`
**Priority:** High
**Depends on:** H-6, H-7

**What to build:**
`frontend/src/app/dashboard/buildings/[id]/page.tsx` — расширение существующей страницы из B-14.

**Sections:**
- Header: адрес, тип, основные параметры
- Risk score: final / baseline / dynamic с breakdown
- SHAP top-5 факторов (bar chart + Claude explanation)
- Recommendations (5 штук от Haiku, как в v1)
- История инцидентов
- Связанные операционные карточки (если есть в `operational_cards`)

**Acceptance criteria:**
- Все секции данных из реальных API
- Mobile friendly
- Print-friendly view (для распечатки инспектором)

---

### [I-3] Inspector v2 page
**Status:** `[ ]`
**Priority:** High
**Depends on:** H-8

**What to build:**
Расширение существующей `/dashboard/inspector/page.tsx` (B-Inspector) — переключатель v1 (районы) / v2 (здания).

**v2 mode:**
- Список top-N зданий с risk score
- TSP-route на карте
- Estimated route time
- Экспорт маршрута в PDF/Telegram для инспектора в поле

**Acceptance criteria:**
- Switcher работает
- Маршрут визуализируется на карте
- Mobile-first для использования в поле

---

## Track J — Polish (Фаза 3)

---

### [J-1] JWT RBAC middleware
**Status:** `[ ]`
**Priority:** High
**Depends on:** A-13 (уже есть)

**What to build:**
Расширение существующего `auth_service.py` под 4 роли с реальным JWT (не mock).

**Add:** `python-jose==3.3.0`, `passlib[bcrypt]==1.7.4`.

**FastAPI dependency:** `require_role('admin', 'analyst')` — декоратор для эндпоинтов.

**Routes coverage:**
- `admin` — `/api/v2/admin/*`, user management
- `analyst` — read all, run predictions
- `inspector` — read assigned + log inspections
- `viewer` — read-only

**Acceptance criteria:**
- Все mutation эндпоинты v2 требуют auth
- 403 при недостаточной роли
- Frontend hides admin controls для non-admin

---

### [J-2] Audit log middleware
**Status:** `[ ]`
**Priority:** Medium
**Depends on:** J-1

**What to build:**
FastAPI middleware который логирует все mutations (POST/PATCH/PUT/DELETE) в `audit_log`.

**Captures:** user_id, action (route+method), entity_type, entity_id, changes (diff before/after где возможно), ip_address.

**Endpoint:** `GET /api/v2/admin/audit-log?entity_type=&user_id=&from=&to=` (admin only).

**Acceptance criteria:**
- Каждый mutation попадает в audit_log
- Performance overhead < 5ms
- Логи видны в admin UI

---

### [J-3] pytest test suite
**Status:** `[ ]`
**Priority:** High
**Depends on:** все v2 backend tasks

**What to build:**
`backend/tests/` — coverage ≥60% для:
- Все v2 routers
- DataLoader_v2
- Extractor (mock Claude API)
- FeatureBuilder
- Risk predictor

**Stack:** pytest + pytest-asyncio + httpx async client + pytest-postgresql для in-memory test DB.

**CI:** GitHub Actions workflow `pytest.yml` на каждый PR.

**Acceptance criteria:**
- `pytest backend/tests` зелёный
- Coverage отчёт ≥60% по core путям
- CI gate включён на main branch

---

### [J-4] Observability stack (lite)
**Status:** `[ ]`
**Priority:** Medium
**Depends on:** E-1

**What to build:**
- `/metrics` endpoint через `prometheus-fastapi-instrumentator`
- Структурированное логирование (JSON) через `structlog`
- Railway → Grafana Cloud free tier integration (Loki + Prom)
- Дашборды:
  - Request rate / latency / error rate per endpoint
  - Celery task throughput + failure rate
  - Claude API cost per day

**Acceptance criteria:**
- Метрики видны в Grafana
- Алерт на error rate > 5% за 5 мин (Telegram)

---

### [J-5] Backups
**Status:** `[ ]`
**Priority:** High
**Depends on:** E-1

**What to build:**
- Daily `pg_dump` через Railway cron job → R2 bucket (`backups/postgres/{date}.dump`)
- Retention 30 дней (R2 lifecycle rule)
- R2 bucket уже имеет versioning для документов
- Runbook: `docs/RECOVERY.md` с шагами восстановления

**Acceptance criteria:**
- За неделю в R2 7 свежих бэкапов
- Тест восстановления на staging (или локально) — проходит

---

### [J-6] v1 → v2 cutover
**Status:** `[ ]`
**Priority:** Medium
**Depends on:** I-1, I-2, I-3, J-1

**What to build:**
Финальный PR — удаление v1:
- Удалить `backend/routers/` v1 файлы
- Удалить старый `data_loader.py`
- Удалить CSV-загрузку из `main.py`
- Frontend: удалить старые страницы которые мигрировали в v2
- Обновить `CONTEXT.md` и `CLAUDE.md` (CSV → Postgres, новые соглашения)

**Acceptance criteria:**
- Нет упоминаний `/api/v1/` в frontend
- `grep -r "pandas" backend/` пусто (или только в ML)
- Smoke test всех страниц проходит

---

## v2 Status Summary

| Task | Track | Status | Phase | Depends on |
|---|---|---|---|---|
| E-1 Postgres+PostGIS Railway | E | `[ ]` | 1 | — |
| E-2 SQLAlchemy + Alembic | E | `[ ]` | 1 | E-1 |
| E-3 Migration: core entities | E | `[ ]` | 1 | E-2 |
| E-4 Migration: incidents+hydrants | E | `[ ]` | 1 | E-3 |
| E-5 Migration: documents | E | `[ ]` | 1 | E-3 |
| E-6 CSV → Postgres script | E | `[ ]` | 1 | E-4 |
| E-7 data_loader_v2 | E | `[ ]` | 1 | E-6 |
| E-8 BuildingsProvider abstraction | E | `[ ]` | 1 | E-3 |
| F-1 R2 storage | F | `[ ]` | 1 | E-2 |
| F-2 Celery+Redis | F | `[ ]` | 1 | E-2 |
| F-3 Upload + normalization | F | `[ ]` | 1 | E-5, F-1, F-2 |
| F-4 Synthetic cards generator | F | `[x]` | 1 | — |
| F-5 Pydantic + Claude tool | F | `[ ]` | 1 | F-3 |
| F-6 Extraction task | F | `[ ]` | 1 | F-5 |
| F-7 Vulnerability analysis | F | `[ ]` | 1 | F-6 |
| F-8 Approval → buildings upsert | F | `[ ]` | 1 | F-7, E-8 |
| F-9 Documents endpoints | F | `[ ]` | 1 | F-3 |
| G-1 Documents list page | G | `[ ]` | 1 | F-9 |
| G-2 Upload modal | G | `[ ]` | 1 | G-1 |
| G-3 PDF preview | G | `[ ]` | 1 | G-1 |
| G-4 Side-by-side review | G | `[ ]` | 1 | G-3, F-7 |
| G-5 Vulnerability cards | G | `[ ]` | 1 | G-4 |
| G-6 Bbox highlight (stretch) | G | `[ ]` | 1 | G-4, F-5 |
| H-1 OSM buildings import | H | `[ ]` | 2 | E-8 |
| H-2 Incident matching | H | `[ ]` | 2 | H-1 |
| H-3 Weather integration | H | `[ ]` | 2 | E-3 |
| H-4 FeatureBuilder | H | `[ ]` | 2 | H-2 |
| H-5 XGBoost training | H | `[ ]` | 2 | H-4 |
| H-6 SHAP + risk endpoint | H | `[ ]` | 2 | H-5 |
| H-7 Dynamic modifier | H | `[ ]` | 2 | H-3, H-5 |
| H-8 Inspector v2 backend | H | `[ ]` | 2 | H-6 |
| H-9 v2 hydrants+stations | H | `[ ]` | 2 | E-4 |
| I-1 Buildings heatmap layer | I | `[ ]` | 2 | H-6, B-4 |
| I-2 Building drill-down | I | `[ ]` | 2 | H-6, H-7 |
| I-3 Inspector v2 frontend | I | `[ ]` | 2 | H-8 |
| J-1 JWT RBAC | J | `[ ]` | 3 | A-13 |
| J-2 Audit log middleware | J | `[ ]` | 3 | J-1 |
| J-3 pytest suite | J | `[ ]` | 3 | all backend |
| J-4 Observability | J | `[ ]` | 3 | E-1 |
| J-5 Backups | J | `[ ]` | 3 | E-1 |
| J-6 v1 cutover | J | `[ ]` | 3 | I-1, I-2, I-3, J-1 |
