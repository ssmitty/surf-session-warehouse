CREATE TABLE IF NOT EXISTS surf_spots (
    spot_id SERIAL PRIMARY KEY,
    spot_slug TEXT NOT NULL UNIQUE,
    spot_name TEXT NOT NULL,
    region TEXT NOT NULL,
    latitude NUMERIC(9, 6) NOT NULL,
    longitude NUMERIC(9, 6) NOT NULL,
    preferred_wind_direction TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS surf_sessions (
    session_id SERIAL PRIMARY KEY,
    spot_id INTEGER NOT NULL REFERENCES surf_spots(spot_id),
    session_date DATE NOT NULL,
    start_time TIME,
    duration_minutes INTEGER CHECK (duration_minutes IS NULL OR duration_minutes > 0),
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    crowd_level TEXT CHECK (crowd_level IN ('Low', 'Medium', 'High')),
    board TEXT,
    actual_wave_quality TEXT CHECK (actual_wave_quality IN ('Poor', 'Fair', 'Good', 'Great', 'Excellent')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_marine_forecasts (
    forecast_id SERIAL PRIMARY KEY,
    spot_id INTEGER NOT NULL REFERENCES surf_spots(spot_id),
    forecast_time TIMESTAMPTZ NOT NULL,
    wave_height_m NUMERIC(7, 3),
    wave_period_s NUMERIC(7, 3),
    wind_wave_height_m NUMERIC(7, 3),
    swell_wave_height_m NUMERIC(7, 3),
    swell_wave_period_s NUMERIC(7, 3),
    swell_wave_direction_deg NUMERIC(7, 3),
    source TEXT NOT NULL DEFAULT 'open-meteo-marine',
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (spot_id, forecast_time, source)
);

CREATE TABLE IF NOT EXISTS raw_weather_forecasts (
    forecast_id SERIAL PRIMARY KEY,
    spot_id INTEGER NOT NULL REFERENCES surf_spots(spot_id),
    forecast_time TIMESTAMPTZ NOT NULL,
    temperature_c NUMERIC(7, 3),
    wind_speed_kmh NUMERIC(7, 3),
    wind_direction_deg NUMERIC(7, 3),
    precipitation_mm NUMERIC(7, 3),
    source TEXT NOT NULL DEFAULT 'open-meteo-weather',
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (spot_id, forecast_time, source)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id SERIAL PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('started', 'success', 'failed')),
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_surf_sessions_spot_date ON surf_sessions (spot_id, session_date);
CREATE INDEX IF NOT EXISTS idx_raw_marine_spot_time ON raw_marine_forecasts (spot_id, forecast_time);
CREATE INDEX IF NOT EXISTS idx_raw_weather_spot_time ON raw_weather_forecasts (spot_id, forecast_time);

