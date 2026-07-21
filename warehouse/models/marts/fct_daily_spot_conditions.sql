with marine as (
    select
        spot_id,
        forecast_date,
        avg(wave_height_m) as avg_wave_height_m,
        max(wave_height_m) as max_wave_height_m,
        avg(wave_period_s) as avg_wave_period_s,
        avg(swell_wave_height_m) as avg_swell_wave_height_m,
        avg(swell_wave_period_s) as avg_swell_wave_period_s,
        avg(swell_wave_direction_deg) as avg_swell_wave_direction_deg
    from {{ ref('stg_marine_forecasts') }}
    group by 1, 2
),

weather as (
    select
        spot_id,
        forecast_date,
        avg(temperature_c) as avg_temperature_c,
        avg(wind_speed_kmh) as avg_wind_speed_kmh,
        avg(wind_direction_deg) as avg_wind_direction_deg,
        sum(precipitation_mm) as total_precipitation_mm
    from {{ ref('stg_weather_forecasts') }}
    group by 1, 2
)

select
    md5(concat(marine.spot_id::text, '-', marine.forecast_date::text)) as daily_condition_id,
    marine.spot_id,
    marine.forecast_date,
    marine.avg_wave_height_m,
    marine.max_wave_height_m,
    marine.avg_wave_period_s,
    marine.avg_swell_wave_height_m,
    marine.avg_swell_wave_period_s,
    marine.avg_swell_wave_direction_deg,
    weather.avg_temperature_c,
    weather.avg_wind_speed_kmh,
    weather.avg_wind_direction_deg,
    weather.total_precipitation_mm,
    case
        when marine.avg_wave_height_m between 0.6 and 2.0
         and marine.avg_wave_period_s >= 7
         and coalesce(weather.avg_wind_speed_kmh, 0) <= 20
            then 1
        else 0
    end as modeled_surfable_day
from marine
left join weather
    on marine.spot_id = weather.spot_id
   and marine.forecast_date = weather.forecast_date
