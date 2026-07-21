select
    forecast_id,
    spot_id,
    forecast_time,
    forecast_time::date as forecast_date,
    temperature_c,
    wind_speed_kmh,
    wind_direction_deg,
    precipitation_mm,
    source,
    loaded_at
from {{ source('app', 'raw_weather_forecasts') }}

