CREATE TABLE IF NOT EXISTS operations (
    id TEXT PRIMARY KEY,
    date DATE NOT NULL,
    city TEXT NOT NULL,
    district TEXT NOT NULL,
    station_id TEXT NOT NULL,
    incident_id TEXT NOT NULL REFERENCES incidents(id),
    response_time_min DOUBLE PRECISION NOT NULL,
    outcome TEXT NOT NULL,
    units_dispatched INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS operations_city_date_idx ON operations (city, date);
