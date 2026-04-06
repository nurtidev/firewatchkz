CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    date DATE NOT NULL,
    city TEXT NOT NULL,
    district TEXT NOT NULL,
    building_type TEXT NOT NULL,
    cause TEXT NOT NULL,
    severity TEXT NOT NULL,
    casualties INTEGER NOT NULL DEFAULT 0,
    damage_tenge BIGINT NOT NULL DEFAULT 0,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS incidents_city_date_idx ON incidents (city, date);
CREATE INDEX IF NOT EXISTS incidents_district_idx ON incidents (district);
