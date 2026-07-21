select
    sessions.session_id,
    sessions.spot_id,
    spots.spot_slug,
    spots.spot_name,
    spots.region,
    sessions.session_date,
    sessions.start_time,
    sessions.duration_minutes,
    sessions.rating,
    sessions.crowd_level,
    sessions.board,
    sessions.actual_wave_quality,
    sessions.notes,
    sessions.created_at
from {{ ref('stg_sessions') }} sessions
join {{ ref('stg_spots') }} spots
    on sessions.spot_id = spots.spot_id

