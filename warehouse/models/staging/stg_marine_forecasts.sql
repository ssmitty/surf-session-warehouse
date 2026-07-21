select
    forecast_id,
    spot_id,
    forecast_time,
    forecast_time::date as forecast_date,
    wave_height_m,
    wave_period_s,
    wind_wave_height_m,
    swell_wave_height_m,
    swell_wave_period_s,
    swell_wave_direction_deg,
    source,
    loaded_at
from {{ source('app', 'raw_marine_forecasts') }}

