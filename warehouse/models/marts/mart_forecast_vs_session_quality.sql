select
    sessions.session_id,
    sessions.spot_id,
    sessions.spot_name,
    sessions.region,
    sessions.session_date,
    sessions.rating,
    sessions.actual_wave_quality,
    conditions.avg_wave_height_m,
    conditions.max_wave_height_m,
    conditions.avg_wave_period_s,
    conditions.avg_swell_wave_height_m,
    conditions.avg_swell_wave_period_s,
    conditions.avg_wind_speed_kmh,
    conditions.avg_wind_direction_deg,
    conditions.modeled_surfable_day,
    case
        when sessions.rating >= 4 then 1
        else 0
    end as high_quality_session
from {{ ref('fct_surf_sessions') }} sessions
left join {{ ref('fct_daily_spot_conditions') }} conditions
    on sessions.spot_id = conditions.spot_id
   and sessions.session_date = conditions.forecast_date

