# FireWatch — Архитектура v2.0

> Предиктивная аналитика пожарной безопасности на уровне отдельных зданий
> с AI-powered ingestion оперативных карточек.

**Версия:** 2.0
**Статус:** Proposed
**Автор:** Nurtilek Asankhan
**Дата:** Май 2026

---

## 1. Цели версии

Версия 1.0 (текущая) делает прогноз пожаров на уровне районов через Holt-Winters
по агрегированной статистике. Это полезно для отчётов, но не actionable для
пожарных частей — они не могут "проверить район".

Версия 2.0 решает три задачи:

1. **Per-building risk scoring** — risk score на каждый объект города,
   а не на район. Инспектор выдаёт top-N конкретных адресов на проверку.
2. **AI-powered onboarding** — оперативные карточки и планы загружаются
   как файлы (PDF, .vsd, скан, .docx), Claude извлекает структуру, человек
   только ревьюит. Снимает главный барьер B2G-внедрения.
3. **Реальные данные** — переход с синтетики на data.egov.kz + 2GIS + клиентские документы.

---

## 2. Эволюция продукта

| Аспект            | v1.0 (текущая)                       | v2.0 (целевая)                                   |
|-------------------|--------------------------------------|--------------------------------------------------|
| Гранулярность     | район                                | конкретное здание                                |
| Модель            | Holt-Winters ETS                     | XGBoost Poisson + Dynamic Modifier + Holt-Winters |
| Данные            | 834 синтетических инцидентов CSV     | data.egov.kz + 2GIS + загруженные документы      |
| Onboarding        | вручную, нет                         | загрузка карточки → AI extract → review          |
| БД                | CSV in-memory                        | PostgreSQL 16 + PostGIS + TimescaleDB            |
| Auth              | нет                                  | JWT + RBAC + audit log                           |
| Карта             | районы (полигоны)                    | здания + гидранты + ПЧ слоями                    |
| Инспектор         | районы с факторами                   | top-N адресов с SHAP-объяснением + маршрут       |

---

## 3. Архитектурная диаграмма

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          ИСТОЧНИКИ ДАННЫХ                                 │
├──────────────────────────────────────────────────────────────────────────┤
│  External APIs                          Внутренние данные                 │
│  ─────────────                          ──────────────────                │
│  • data.egov.kz   (инциденты ДЧС)       • Загруженные карточки (PDF/img) │
│  • 2GIS Places    (здания, адреса)      • Реестр гидрантов клиента        │
│  • OpenWeatherMap (погода 7d forecast)  • Реестр пожарных частей          │
│  • Holiday API    (праздники РК)        • История инспекций               │
│  • OSM (fallback / hybrid)                                                │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                  INGESTION LAYER (Celery workers + APScheduler)           │
├──────────────────────────────────────────────────────────────────────────┤
│  • IncidentIngest      daily   — новые инциденты из data.egov.kz          │
│  • BuildingsSync       weekly  — обновление зданий из 2GIS                │
│  • WeatherIngest       hourly  — текущая погода + 7-day forecast          │
│  • DocumentIngest      on-demand — обработка загруженных оперкарточек     │
│  • FeatureBuilder      daily   — пересчёт фичей на каждое здание          │
│  • ModelRetrain        weekly  — переобучение baseline на новых данных    │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                  STORAGE  (PostgreSQL 16 + PostGIS + TimescaleDB)         │
├──────────────────────────────────────────────────────────────────────────┤
│  Core entities       │  Time-series (TimescaleDB hypertables)             │
│  ─────────────       │  ─────────────────────────────────────             │
│  buildings           │  weather_history                                   │
│  building_features   │  risk_scores                                       │
│  incidents           │  predictions                                       │
│  hydrants            │                                                    │
│  fire_stations       │  Files (S3-compatible: MinIO / Cloudflare R2)      │
│  operational_cards   │  ────────────────────────────────────              │
│  card_extractions    │  • raw uploads (.pdf, .vsd, .docx, .jpg)          │
│  inspections         │  • converted PDFs (normalized)                     │
│  users + audit_log   │  • generated thumbnails                            │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       ML / PREDICTION LAYER                                │
├──────────────────────────────────────────────────────────────────────────┤
│  Model 1: BaselineRisk        XGBoost (Poisson objective)                  │
│           Output: expected_incidents_per_year per building                 │
│           Refresh: weekly                                                  │
│           Explain: SHAP top-5 features                                     │
│                                                                            │
│  Model 2: DynamicModifier     rules + small MLP                            │
│           Input: weather, season, day-of-week, holiday                     │
│           Output: multiplier 0.3 – 3.0                                     │
│           Refresh: daily                                                   │
│                                                                            │
│  Model 3: HoltWintersDistrict (carry-over from v1)                         │
│           Output: monthly aggregate forecast per district                  │
│           Use: trend visualization, executive reports                      │
│                                                                            │
│  Final risk = baseline × dynamic × holt_winters_seasonality_factor         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       AI LAYER (Anthropic Claude)                          │
├──────────────────────────────────────────────────────────────────────────┤
│  Sonnet 4   — document extraction (vision, tool use, JSON schema)          │
│  Sonnet 4   — vulnerability analysis (post-extraction)                     │
│  Haiku 4.5  — risk score explanations (SHAP → natural language)            │
│  Haiku 4.5  — chat assistant for analysts                                  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          API (FastAPI v2)                                  │
├──────────────────────────────────────────────────────────────────────────┤
│  Auth:        JWT, RBAC (admin / analyst / inspector / viewer)             │
│  Endpoints:   /api/v2/buildings, /risk, /inspector, /documents, /chat      │
│  Audit:       все mutations логируются в audit_log                         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       FRONTEND (Next.js 15)                                │
├──────────────────────────────────────────────────────────────────────────┤
│  • Карта зданий с heatmap по risk score                                    │
│  • Drill-down: здание → факторы + рекомендации + история + карточка        │
│  • Инспектор: top-N с TSP-маршрутом обхода                                 │
│  • Document Upload UI с side-by-side AI extract review                     │
│  • Mobile-first view для инспекторов в поле                                │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Слой данных

### 4.1 Источники данных

| Источник            | Тип данных                    | Частота | Стоимость        |
|---------------------|-------------------------------|---------|------------------|
| data.egov.kz        | Инциденты ДЧС РК              | Daily   | Бесплатно        |
| 2GIS Places API     | Здания (геометрия, метаданные)| Weekly  | Commercial       |
| OSM (Overpass)      | Buildings (резерв/гибрид)     | Weekly  | Бесплатно        |
| OpenWeatherMap      | Погода current + 7d forecast  | Hourly  | $40-200/мес      |
| Yandex Geocoder     | Адрес ↔ координаты            | On-demand| Pay-per-request |
| Holiday API РК      | Праздники, выходные           | Yearly  | Бесплатно        |
| Клиентские uploads  | Оперкарточки, планы           | On-demand| —               |

### 4.2 Интеграция с 2GIS

**Что используем:**

- **Places API** — выгрузка зданий с метаданными: тип, координаты, адрес,
  тип объекта (residential / commercial / industrial / etc.), часы работы
  для коммерческих, число этажей где доступно.
- **Map Tiles API** — базовый слой карты (заменяет OSM tiles в Leaflet).
  Лучшее покрытие КЗ, узнаваемая визуализация.
- **Geocoder** — резолвинг адресов в координаты при загрузке инцидентов и карточек.

**Получение доступа:**

1. Демо-ключ на [dev.2gis.com](https://dev.2gis.com) — для разработки сразу.
2. Письмо на `api@2gis.com` с описанием use case ("B2G fire safety analytics
   platform for Kazakhstan emergency services, нужны здания КЗ городов
   с метаданными, объём X запросов/мес").
3. Коммерческий договор — обычно $200-500/мес на старте, скейл по объёму.
4. **On-premise опция** — есть, существенно для тендеров с гос. ИБ-требованиями.

**Альтернативы / гибрид:**

- **OpenStreetMap (бесплатно)** — для MVP и тестов модели. Astana покрытие
  ~70-80%, Almaty лучше, регионы слабее. Качаем через Overpass API или
  `osm2pgsql` импорт.
- **Yandex Maps API** — сопоставимое качество, политически чуть хуже для
  гос. контрактов РК.
- **Кадастр недвижимости РК** (через Правительство для граждан / data.egov.kz)
  — официальный источник, идеален как enrichment-слой при B2G продажах.
  Доступ бюрократический, обычно через партнёрство с НИТ.

**Стратегия:**
MVP — OSM. Production v2.0 — 2GIS как primary, OSM как fallback, кадастр
как enrichment где есть доступ.

### 4.3 Схема БД

```sql
-- Buildings
CREATE TABLE buildings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id         UUID NOT NULL REFERENCES cities(id),
    address         TEXT NOT NULL,
    address_norm    TEXT NOT NULL,
    geom            GEOMETRY(POLYGON, 4326) NOT NULL,
    centroid        GEOMETRY(POINT, 4326) GENERATED ALWAYS AS (ST_Centroid(geom)) STORED,
    building_type   TEXT,           -- residential / commercial / industrial / social / educational / medical
    floors_above    INTEGER,
    floors_below    INTEGER,
    height_m        NUMERIC,
    total_area_sqm  NUMERIC,
    year_built      INTEGER,
    wall_material   TEXT,
    fire_resistance INTEGER,        -- I-V степень
    fire_hazard_class TEXT,         -- Ф1-Ф5
    source          TEXT NOT NULL,  -- '2gis' | 'osm' | 'cadastre' | 'manual' | 'document_extract'
    external_id     TEXT,           -- ID в источнике
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source, external_id)
);
CREATE INDEX idx_buildings_geom ON buildings USING GIST(geom);
CREATE INDEX idx_buildings_centroid ON buildings USING GIST(centroid);
CREATE INDEX idx_buildings_city ON buildings(city_id);

-- Building features (precomputed для модели)
CREATE TABLE building_features (
    building_id     UUID PRIMARY KEY REFERENCES buildings(id) ON DELETE CASCADE,
    nearest_hydrant_m       NUMERIC,
    nearest_station_m       NUMERIC,
    incidents_500m_3y       INTEGER,
    building_density_500m   NUMERIC,
    population_estimate     INTEGER,
    last_inspection_days    INTEGER,
    last_incident_days      INTEGER,
    -- ... etc
    feature_set     JSONB,          -- расширяемые фичи
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Incidents (исторические инциденты ДЧС)
CREATE TABLE incidents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at     TIMESTAMPTZ NOT NULL,
    geom            GEOMETRY(POINT, 4326) NOT NULL,
    address_text    TEXT,
    building_id     UUID REFERENCES buildings(id),
    incident_type   TEXT,           -- fire / smoke / false_alarm / other
    damage_tenge    NUMERIC,
    cause           TEXT,
    casualties      INTEGER DEFAULT 0,
    source          TEXT NOT NULL,
    external_id     TEXT
);
CREATE INDEX idx_incidents_geom ON incidents USING GIST(geom);
CREATE INDEX idx_incidents_time ON incidents(occurred_at);
CREATE INDEX idx_incidents_building ON incidents(building_id);

-- Hydrants
CREATE TABLE hydrants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    geom            GEOMETRY(POINT, 4326) NOT NULL,
    address         TEXT,
    status          TEXT NOT NULL DEFAULT 'working',  -- working / broken / unknown / buried
    capacity_l_s    NUMERIC,
    last_check_at   TIMESTAMPTZ,
    winter_access   BOOLEAN DEFAULT true
);
CREATE INDEX idx_hydrants_geom ON hydrants USING GIST(geom);

-- Fire stations
CREATE TABLE fire_stations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    geom            GEOMETRY(POINT, 4326) NOT NULL,
    address         TEXT,
    vehicles_count  INTEGER,
    response_zone   GEOMETRY(POLYGON, 4326)
);

-- Operational cards (загруженные документы)
CREATE TABLE operational_cards (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    building_id     UUID REFERENCES buildings(id),
    uploaded_by     UUID NOT NULL REFERENCES users(id),
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    file_url        TEXT NOT NULL,     -- путь в MinIO/S3
    file_name       TEXT NOT NULL,
    file_size_bytes BIGINT,
    file_mime       TEXT,
    status          TEXT NOT NULL,     -- uploaded / extracting / extracted / review / approved / rejected
    extraction_id   UUID REFERENCES card_extractions(id),
    approved_at     TIMESTAMPTZ,
    approved_by     UUID REFERENCES users(id)
);

-- Card extractions (результаты AI обработки)
CREATE TABLE card_extractions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id             UUID NOT NULL REFERENCES operational_cards(id) ON DELETE CASCADE,
    model_version       TEXT NOT NULL,
    extracted_data      JSONB NOT NULL,     -- структурированные поля
    field_confidences   JSONB NOT NULL,     -- {field: 0.0-1.0}
    vulnerabilities     JSONB,              -- AI-найденные риски
    raw_text            TEXT,               -- сырой OCR/extract текст
    extraction_cost_usd NUMERIC,
    duration_ms         INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Risk scores (time-series, TimescaleDB hypertable)
CREATE TABLE risk_scores (
    building_id     UUID NOT NULL REFERENCES buildings(id),
    score_date      DATE NOT NULL,
    horizon_days    INTEGER NOT NULL,     -- 7 / 30 / 90
    baseline_score  NUMERIC NOT NULL,     -- expected incidents/year
    dynamic_mult    NUMERIC NOT NULL,
    seasonal_mult   NUMERIC NOT NULL,
    final_score     NUMERIC NOT NULL,
    top_features    JSONB,                -- SHAP top-5
    PRIMARY KEY (building_id, score_date, horizon_days)
);
SELECT create_hypertable('risk_scores', 'score_date');

-- Weather history (TimescaleDB)
CREATE TABLE weather_history (
    ts              TIMESTAMPTZ NOT NULL,
    h3_cell         TEXT NOT NULL,        -- Uber H3 spatial index, resolution 8
    temp_c          NUMERIC,
    wind_ms         NUMERIC,
    humidity_pct    NUMERIC,
    precipitation_mm NUMERIC,
    PRIMARY KEY (ts, h3_cell)
);
SELECT create_hypertable('weather_history', 'ts');

-- Users, roles, audit
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    full_name       TEXT,
    role            TEXT NOT NULL,        -- admin / analyst / inspector / viewer
    organization_id UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

CREATE TABLE audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id),
    action      TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id   UUID,
    changes     JSONB,
    ip_address  INET,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_time ON audit_log(occurred_at);
```

---

## 5. ML / Prediction Pipeline

### 5.1 Baseline Risk Model — XGBoost Poisson

**Задача:** predict expected_incidents_per_year per building.

**Почему Poisson, а не классификация:**
Пожары — редкое событие. На большинстве зданий 0 инцидентов за всю историю.
Бинарная классификация будет тривиально предсказывать "0" с точностью 99%.
Poisson loss моделирует rate (интенсивность) события, что естественно
для счётных данных с большим числом нулей.

**Конфиг:**

```python
import xgboost as xgb

model = xgb.XGBRegressor(
    objective='count:poisson',
    n_estimators=500,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    tree_method='hist',
    eval_metric='poisson-nloglik'
)
```

**Фичи (35-50 в production):**

*Статические — из 2GIS / кадастра:*
- `building_type` (one-hot: residential / commercial / industrial / social / mixed)
- `year_built` + `age_years`
- `floors_above`, `floors_below`, `height_m`
- `total_area_sqm`, `area_per_floor`
- `wall_material` (one-hot)
- `fire_resistance_degree` (1-5)
- `fire_hazard_class` (Ф1-Ф5)

*Пространственные:*
- `nearest_hydrant_m`
- `nearest_station_m`
- `station_response_time_avg`
- `building_density_500m`
- `incidents_500m_3y`, `incidents_500m_1y`
- `road_width_min_m` (доступность для пожарной техники)
- `dead_end_road` (boolean)

*Историко-инспекционные:*
- `incidents_on_this_building_3y`
- `days_since_last_incident`
- `days_since_last_inspection`
- `last_inspection_violations_count`

*Демографические:*
- `population_estimate`
- `vulnerable_groups_present` (boolean: дет. сад, пансионат, школа)

**Валидация:**
Time-based split — train на 2023-2024, validate на 2025, test на 2026 Q1.
Метрики: Poisson deviance, lift в top-decile (важно: сравниваем "если бы
проверили top-10% predicted risk зданий — сколько инцидентов попало бы в них").

**Explainability:**
SHAP values на каждое предсказание. Top-5 features → Claude → объяснение
на русском для инспектора.

### 5.2 Dynamic Modifier

Baseline даёт rate в год. Но риск пожара в понедельник летом и в субботу
вечером в новогодние праздники в -25° с ветром 15 м/с — разный.

**Подход:** начинаем с правил, постепенно заменяем обученным MLP.

**Правила (initial):**

```python
def dynamic_modifier(building, now, weather):
    mult = 1.0

    # Сезонность отопления
    if weather.temp_c < 0:
        mult *= 1.30  # отопительный сезон, печи, газ
    if weather.temp_c < -20:
        mult *= 1.15  # экстремальный холод

    # Ветер (распространение огня)
    if weather.wind_ms > 10:
        mult *= 1.20
    if weather.wind_ms > 15:
        mult *= 1.40

    # Сухая жаркая погода
    if weather.temp_c > 30 and weather.humidity_pct < 30:
        mult *= 1.25

    # Праздники
    if is_major_holiday(now):
        mult *= 1.35  # фейерверки, алкоголь, отсутствие персонала
    if is_friday_or_saturday_evening(now):
        mult *= 1.15

    return clamp(mult, 0.3, 3.0)
```

**Обучение MLP (после набора данных):**
Лог инцидентов с условиями на момент инцидента → MLP с фичами
(temp, wind, humidity, day_of_week, hour, is_holiday) → output multiplier
с MSE loss vs наблюдаемый rate.

### 5.3 Holt-Winters District (оставляем из v1)

Используется для:
- Сезонного множителя в final risk
- Executive dashboards (тренды по районам)
- Прогноза bюджетов и ресурсов ДЧС

### 5.4 Claude AI Layer

| Use case                    | Модель        | Tool use | Cost / call |
|-----------------------------|---------------|----------|-------------|
| Document extraction         | Sonnet 4      | Yes      | $0.05-0.20  |
| Vulnerability analysis      | Sonnet 4      | No       | $0.01-0.05  |
| Risk explanation            | Haiku 4.5     | No       | $0.001-0.003|
| Chat assistant              | Haiku 4.5     | No       | $0.002-0.01 |
| Recommendation cards        | Haiku 4.5     | No       | $0.001      |

**Промт-паттерн для extraction:**

```python
EXTRACTION_SYSTEM = """
Ты — ассистент пожарной службы Казахстана. Извлеки структурированные данные
из загруженной оперативной карточки или плана объекта согласно schema.

Правила:
1. Для каждого поля верни значение И confidence от 0 до 1.
2. Если поле не найдено в документе — null с confidence 0.
3. Если значение неоднозначно — выбери наиболее вероятное и confidence < 0.7.
4. Adресa и координаты в КЗ — если адрес есть, geocode при сохранении.
5. Используй russian/kazakh as-is, не переводи.

Документ может быть оформлен по форме МЧС РК (стандартная карточка пожаротушения),
или произвольно (тогда извлекай по смыслу).
"""
```

### 5.5 Feature Engineering Pipeline

`FeatureBuilder` запускается ежедневно как Celery task:

```python
@celery.task
def rebuild_features(city_id: UUID):
    buildings = fetch_buildings(city_id)
    incidents_idx = build_spatial_index(fetch_incidents(city_id, years=3))
    hydrants_idx = build_spatial_index(fetch_hydrants(city_id))
    stations_idx = build_spatial_index(fetch_stations(city_id))

    for building in buildings:
        features = {
            'nearest_hydrant_m': hydrants_idx.nearest_distance(building.centroid),
            'nearest_station_m': stations_idx.nearest_distance(building.centroid),
            'incidents_500m_3y': len(incidents_idx.within(building.centroid, 500)),
            'building_density_500m': count_buildings_within(building.centroid, 500),
            'age_years': current_year - building.year_built if building.year_built else None,
            # ...
        }
        upsert_features(building.id, features)
```

---

## 6. Document Ingestion Module (новая фича)

Это **главное продуктовое отличие** v2.0. Превращает онбординг с
"полгода ввода руками" в "загрузил папку с карточками → просмотрел
автоматически извлечённое → сохранил".

### 6.1 Поддерживаемые форматы

| Формат          | Метод обработки                                          |
|-----------------|----------------------------------------------------------|
| PDF (text)      | Прямо в Claude vision                                    |
| PDF (scanned)   | Прямо в Claude vision (vision хорошо OCR'ит)             |
| JPG / PNG / WEBP| Прямо в Claude vision                                    |
| DOCX            | mammoth → текст + извлечение изображений → Claude        |
| DOC (legacy)    | LibreOffice headless → DOCX → как выше                   |
| VSD / VSDX      | LibreOffice headless → PDF → Claude vision               |
| XLSX            | openpyxl → текст + таблицы → Claude                      |
| ZIP / RAR       | Распаковка → recursive processing                        |

### 6.2 Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. UPLOAD                                                          │
│     User → POST /api/v2/documents/upload (multipart)                │
│     ↓                                                               │
│     Stored in MinIO: documents/{user_id}/{uuid}/{original_name}     │
│     Record in operational_cards (status='uploaded')                 │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. NORMALIZATION  (Celery worker)                                  │
│     Detect MIME → convert to PDF if needed (LibreOffice headless)   │
│     Generate thumbnails for UI preview                              │
│     Update status='converting' → 'ready_for_extraction'             │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. EXTRACTION  (Claude Sonnet 4, tool use)                         │
│     Send PDF (up to 100 pages per call) + system prompt + schema    │
│     Receive structured JSON + confidence per field                  │
│     Store in card_extractions                                       │
│     Update status='extracted'                                       │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. VULNERABILITY ANALYSIS  (Claude Sonnet 4, separate call)        │
│     Input: extracted data + raw document text                       │
│     Prompt: "Найди несоответствия Правилам ПБ РК, устаревшие        │
│              данные, отсутствующие обязательные пункты, риски"      │
│     Output: list of vulnerabilities + recommended actions           │
│     Store in card_extractions.vulnerabilities                       │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. HUMAN REVIEW                                                    │
│     UI: side-by-side PDF preview | extracted fields                 │
│     Colour coding by confidence:                                    │
│       • green  (>0.9) — autoapprove, не показываем фокус            │
│       • yellow (0.6-0.9) — нужен взгляд                             │
│       • red    (<0.6)  — обязательная правка                        │
│     User edits + approves → status='approved'                       │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  6. PERSISTENCE                                                     │
│     Извлечённые данные → UPSERT в buildings + связанные таблицы     │
│     Триггер пересчёта features для обновлённых зданий               │
│     Audit log: кто, что, когда                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Schema извлечения (Pydantic)

Эта схема — то, что Claude получает как tool definition.

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import date

class FieldWithConfidence(BaseModel):
    value: Optional[str | int | float | bool]
    confidence: float = Field(..., ge=0.0, le=1.0)

class WaterSource(BaseModel):
    type: Literal["hydrant", "reservoir", "natural", "pond", "river"]
    distance_m: Optional[int]
    capacity_l_s: Optional[float]
    status: Optional[Literal["working", "broken", "seasonal", "unknown"]]
    notes: Optional[str]

class Vulnerability(BaseModel):
    severity: Literal["critical", "high", "medium", "low"]
    description: str
    regulation_violated: Optional[str]
    recommended_action: str

class OperationalCardExtraction(BaseModel):
    # Метаданные документа
    card_number: FieldWithConfidence
    approved_date: FieldWithConfidence
    last_revision_date: FieldWithConfidence

    # Объект
    object_name: FieldWithConfidence
    address: FieldWithConfidence
    coordinates_lat: FieldWithConfidence
    coordinates_lng: FieldWithConfidence
    object_category: FieldWithConfidence  # residential / commercial / etc
    owner: FieldWithConfidence
    responsible_name: FieldWithConfidence
    responsible_phone: FieldWithConfidence

    # Здание
    floors_above: FieldWithConfidence
    floors_below: FieldWithConfidence
    height_m: FieldWithConfidence
    total_area_sqm: FieldWithConfidence
    year_built: FieldWithConfidence
    walls_material: FieldWithConfidence
    roof_material: FieldWithConfidence
    fire_resistance_degree: FieldWithConfidence  # 1-5
    functional_class: FieldWithConfidence        # Ф1-Ф5
    structural_class: FieldWithConfidence        # С0-С3

    # Заселённость
    max_people_day: FieldWithConfidence
    max_people_night: FieldWithConfidence
    vulnerable_groups: List[str]                 # дет. сад / инвалиды / etc

    # Системы пожарной безопасности
    alarm_system_present: FieldWithConfidence
    alarm_system_type: FieldWithConfidence
    automatic_extinguishing: FieldWithConfidence
    fire_exits_count: FieldWithConfidence
    smoke_removal: FieldWithConfidence

    # Водоснабжение
    internal_hydrants_count: FieldWithConfidence
    water_sources: List[WaterSource]

    # Опасности
    hazardous_materials: List[str]
    gas_systems: List[str]
    structural_concerns: List[str]

    # Доступ
    approach_roads: List[str]
    firefighting_clearance: FieldWithConfidence
    access_obstacles: List[str]

    # AI-анализ (заполняется во втором проходе)
    identified_vulnerabilities: List[Vulnerability] = []

    # Metadata
    document_quality_notes: Optional[str]
    overall_confidence: float
```

### 6.4 Vulnerability Analysis промт

```
Ты — эксперт по пожарной безопасности РК. Проанализируй извлечённые
данные оперативной карточки + сырой текст документа.

Найди:
1. Несоответствия "Правилам пожарной безопасности РК" (Постановление
   Правительства РК № 1077 от 9 октября 2014 г.):
   - Эвакуационные выходы (количество, ширина, направление открывания)
   - Системы оповещения по классу объекта (Ф1-Ф5)
   - Соответствие категории объекта степени огнестойкости
2. Устаревшие данные:
   - Если last_revision_date > 3 лет — флаг
   - Если данные о системах ПБ не обновлялись после реконструкции
3. Отсутствующие обязательные пункты:
   - Если объект Ф1.1 (детский) — должна быть категория людей с ОВЗ
   - Если высота >28м — должны быть лифты для пожарных
4. Inferred риски:
   - Газовые системы + старая электрика + многолюдность = high
   - Деревянные конструкции + отсутствие АУПТ = high
   - И т.д.

Вывод: List[Vulnerability] с severity, описанием, ссылкой на норму,
рекомендуемым действием.
```

### 6.5 Human Review UI

```
┌──────────────────────────────────────────────────────────────────────┐
│  Operational Card: 2024-ПЧ10-053.pdf                                 │
│  Загружена: Айгерим К., 12 мая 2026, 14:23                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   ┌──────────────────────────┐  ┌─────────────────────────────────┐ │
│   │                          │  │ OBJECT                          │ │
│   │   [PDF preview]          │  │ Name:    [ТРЦ Хан Шатыр    ] 🟢│ │
│   │                          │  │ Address: [Туран 37          ] 🟢│ │
│   │   page 1 of 8            │  │                                 │ │
│   │                          │  │ BUILDING                        │ │
│   │   ◀ ▶                    │  │ Floors:    [6              ] 🟢│ │
│   │                          │  │ Year:      [2006           ] 🟢│ │
│   │                          │  │ Area sqm:  [127000         ] 🟡│ │
│   │                          │  │ Wall mat:  [метал-каркас   ] 🟡│ │
│   │                          │  │                                 │ │
│   │                          │  │ FIRE SAFETY                     │ │
│   │                          │  │ Alarm:     [Bosch FPA-5000 ] 🟢│ │
│   │                          │  │ Auto extn: [спринклер      ] 🟢│ │
│   │                          │  │ Smoke rem: [—              ] 🔴│ │
│   │                          │  │                                 │ │
│   │                          │  │ ⚠ VULNERABILITIES (3)           │ │
│   │                          │  │ • CRIT: дымоудаление не указано │ │
│   │                          │  │ • HIGH: данные не обновлялись   │ │
│   │                          │  │   с 2019 (5 лет)                │ │
│   │                          │  │ • MED:  расстояние до гидранта  │ │
│   │                          │  │   указано как «~50м» — уточнить │ │
│   └──────────────────────────┘  └─────────────────────────────────┘ │
│                                                                       │
│   [ Отклонить ]                              [ Сохранить и далее ]   │
└──────────────────────────────────────────────────────────────────────┘
```

**Поведение:**
- Поля с зелёным confidence пользователь может проигнорировать, но они подсвечены.
- Жёлтые — fokus автоматически переходит на них последовательно.
- Красные — обязательны к проверке, кнопка "Сохранить" disabled пока не подтверждено.
- Click на любое поле — подсвечивает место в PDF где это было найдено (bbox).
- Edit поля — сохраняется как correction для будущего fine-tuning.

### 6.6 Стоимость обработки одной карточки

Типичная карточка — 5-15 страниц PDF.

| Операция                          | Стоимость         |
|-----------------------------------|-------------------|
| Storage (MinIO/R2)                | ~$0.0001          |
| Conversion (LibreOffice headless) | ~$0.001 compute   |
| Claude Sonnet 4 extraction (10p)  | ~$0.10            |
| Claude Sonnet 4 vulnerabilities   | ~$0.03            |
| **Итого**                         | **~$0.13/card**   |

При тарификации клиенту 500-2000 ₸/карточка (зависит от пакета) маржа
~99%. При 1000 карточек на город — это $130 себестоимости и
500K-2M ₸ выручки.

---

## 7. API v2

### 7.1 Аутентификация

JWT с access + refresh tokens. Роли:

| Role       | Permissions                                                       |
|------------|-------------------------------------------------------------------|
| admin      | Full access, user management, system settings                     |
| analyst    | Read all, run predictions, generate reports                        |
| inspector  | Read assigned buildings, log inspection results                    |
| viewer     | Read-only dashboards                                              |

### 7.2 Endpoints

```
# Buildings & risk
GET  /api/v2/buildings?bbox=&min_risk=&limit=
GET  /api/v2/buildings/{id}
GET  /api/v2/buildings/{id}/risk?horizon=7|30|90
GET  /api/v2/buildings/{id}/factors        # SHAP explanation
GET  /api/v2/buildings/{id}/history        # incidents + inspections
PATCH /api/v2/buildings/{id}               # corrections

# Inspector
GET  /api/v2/inspector?city=&top_n=50&filter=
GET  /api/v2/inspector/route?building_ids=[...]   # TSP-optimized

# Inspections
POST /api/v2/inspections
GET  /api/v2/inspections?building_id=

# Documents (operational cards)
POST   /api/v2/documents/upload                   # multipart
GET    /api/v2/documents/{id}/status
GET    /api/v2/documents/{id}/extraction
PATCH  /api/v2/documents/{id}/extraction          # corrections
POST   /api/v2/documents/{id}/approve
DELETE /api/v2/documents/{id}

# Hydrants & stations
GET  /api/v2/hydrants?bbox=
PATCH /api/v2/hydrants/{id}                       # status update
GET  /api/v2/fire-stations?bbox=

# Cities & geo
GET  /api/v2/cities
GET  /api/v2/cities/{id}/districts                # legacy GeoJSON

# Forecasts (district-level Holt-Winters, kept)
GET  /api/v2/forecast?city=&months=

# KPI dashboards
GET  /api/v2/kpi?city=

# AI assistant
POST /api/v2/chat
POST /api/v2/recommendations/{building_id}

# Telegram
GET  /api/v2/telegram/config
POST /api/v2/telegram/test

# Admin
GET  /api/v2/admin/users
POST /api/v2/admin/users
GET  /api/v2/admin/audit-log
```

---

## 8. Безопасность и B2G соответствие

Для гос. контрактов в РК критично:

1. **On-premise deployment** — Docker Compose + Helm chart для развёртывания
   внутри периметра клиента. SaaS не пройдёт ИБ-экспертизу МЧС.
2. **Аудит всех действий** — каждая модификация в audit_log с user_id, IP, timestamp.
3. **Шифрование at-rest** — PostgreSQL TDE или disk encryption, MinIO server-side encryption.
4. **TLS 1.3 везде** — между всеми сервисами.
5. **ЭЦП интеграция (опционально для v2.1)** — авторизация через НУЦ РК.
6. **Соответствие 152-ФЗ аналогу РК** — Закон РК "О персональных данных и их защите"
   (контактные данные ответственных лиц в карточках — это персональные данные).
7. **Бэкапы** — daily PostgreSQL + объектное хранилище, 30-day retention минимум.
8. **Логирование Claude API вызовов** — для compliance и анализа стоимости.
9. **Опция self-hosted Claude** — Bedrock через AWS GovCloud или on-prem Llama
   fallback для совсем закрытых контуров (v2.2+).

---

## 9. Stack & deployment

| Layer          | Технология                                          |
|----------------|-----------------------------------------------------|
| Frontend       | Next.js 15 + React 19 + TypeScript + Tailwind       |
| Карта          | react-leaflet (можно перейти на MapLibre / 2GIS SDK) |
| Графики        | Recharts                                            |
| Backend        | Python 3.11 + FastAPI + Uvicorn (gunicorn workers)  |
| Async jobs     | Celery + Redis broker                               |
| Scheduler      | APScheduler или Celery Beat                         |
| ML             | XGBoost, scikit-learn, SHAP, statsmodels            |
| LLM            | Anthropic Claude (Sonnet 4 + Haiku 4.5)             |
| Object storage | MinIO (self-hosted) или Cloudflare R2 (cloud)       |
| Database       | PostgreSQL 16 + PostGIS 3.4 + TimescaleDB 2.x       |
| Cache          | Redis 7                                             |
| Observability  | Prometheus + Grafana + Loki + OpenTelemetry         |
| Deploy (cloud) | Railway → AWS EKS при масштабе                      |
| Deploy (on-prem) | Docker Compose / Helm chart                       |
| CI/CD          | GitHub Actions                                      |

---

## 10. Roadmap по неделям

### Фаза 1 — Foundation (недели 1-4)

**Неделя 1-2:**
- PostgreSQL + PostGIS + TimescaleDB на проде
- Миграция с CSV на БД, schema выше
- Базовая JWT-аутентификация + 4 роли
- Audit log middleware

**Неделя 3-4:**
- Импорт buildings из OSM для Астаны (osm2pgsql)
- Импорт реальных инцидентов из data.egov.kz
- Запрос демо-ключа 2GIS, начало переговоров
- OpenWeatherMap интеграция

### Фаза 2 — Per-building Model (недели 5-8)

**Неделя 5-6:**
- FeatureBuilder pipeline
- Baseline XGBoost Poisson на реальных данных
- SHAP explanations
- Endpoint `/api/v2/buildings/{id}/risk`
- Валидация на out-of-time данных

**Неделя 7-8:**
- Dynamic modifier (rules first)
- Frontend: карта зданий с heatmap по risk
- Drill-down UI на здание
- Инспектор v2: top-N зданий + TSP-маршрут

### Фаза 3 — Document Ingestion (недели 9-12)

**Неделя 9-10:**
- MinIO + загрузка файлов
- Conversion pipeline (LibreOffice headless для DOCX/VSD)
- Claude Sonnet 4 extraction с tool use
- Pydantic schema для извлечения

**Неделя 11-12:**
- Vulnerability analysis (второй проход Claude)
- Human review UI (side-by-side с confidence colors)
- Persistence pipeline (saves to buildings + features rebuild trigger)

### Фаза 4 — Production-readiness (недели 13-16)

**Неделя 13-14:**
- Тесты (pytest, ≥60% coverage core пути)
- Observability stack
- Бэкапы, восстановление, runbooks
- Docker Compose для on-prem deploy

**Неделя 15-16:**
- Презентация ДЧС Астаны
- Пилот в ПЧ №10 (расширение существующего контакта)
- Подписание 2GIS commercial agreement

---

## 11. Cost estimates (operational, mo)

| Component                | Bootstrap (1 city) | Scale (5 cities) |
|--------------------------|---------------------|-------------------|
| Cloud infra (Railway/AWS)| $80                 | $400              |
| PostgreSQL managed       | $30                 | $150              |
| MinIO storage            | $10                 | $80               |
| OpenWeatherMap           | $40                 | $100              |
| 2GIS API                 | $200                | $800              |
| Claude API (extractions) | $50                 | $400              |
| Claude API (chat/explain)| $20                 | $150              |
| Monitoring (Grafana etc) | $30                 | $80               |
| **Total/month**          | **~$460**           | **~$2,160**       |

В тенге: ~230K bootstrap → ~1.1M на 5 городов в месяц. При первом
контракте даже на 1 город уровня 15-25M ₸ — система самофинансируется
с первой сделки.

---

## 12. Открытые вопросы

- Как часто реально обновляются документы по объектам в ПЧ? (важно для UX
  потока ингеста — нужны ли batch uploads и подсказки "это здание уже есть")
- Готовы ли ДЧС регионов поставить on-prem или хотят SaaS? (определяет
  приоритет on-prem пайплайна)
- Есть ли стандартный шаблон оперативной карточки МЧС РК? (если да —
  можем тренировать extraction на нём как на golden standard)
- Доступ к кадастру через Правительство для граждан — нужна юр. форма
  партнёрства, кто инициирует?
- Какие именно интеграции хочет ПЧ №10 кроме .vsd планов?

---

## Авторство

Документ подготовлен совместно с Claude (Anthropic).
Архитектура — proposal, требует валидации на реальном пилоте.
