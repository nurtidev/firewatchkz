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
| B-1 Frontend scaffold | B | `[x]` | A-1, A-2, C-1 |
| B-2 City selector | B | `[x]` | B-3, B-4, B-5 |
| B-3 KPI cards | B | `[x]` | B-2, B-4, B-5 |
| B-4 Risk map | B | `[x]` | B-2, B-3, B-5 |
| B-5 Forecast chart | B | `[x]` | B-2, B-3, B-4 |
| B-6 Recommendations | B | `[x]` | B-7, B-8 |
| B-7 AI chat panel | B | `[x]` | B-6, B-8 |
| B-8 Telegram panel | B | `[x]` | B-6, B-7 |
| C-1 Astana GeoJSON | C | `[x]` | Everything |
| D-1 Railway config | D | `[x]` | — |
