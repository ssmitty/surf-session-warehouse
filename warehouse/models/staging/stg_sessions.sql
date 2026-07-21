select
    session_id,
    spot_id,
    session_date,
    start_time,
    duration_minutes,
    rating,
    crowd_level,
    board,
    actual_wave_quality,
    notes,
    created_at
from {{ source('app', 'surf_sessions') }}

