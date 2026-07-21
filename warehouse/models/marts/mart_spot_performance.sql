select
    spot_id,
    spot_slug,
    spot_name,
    region,
    count(*) as session_count,
    avg(rating) as avg_session_rating,
    max(rating) as best_session_rating,
    avg(duration_minutes) as avg_duration_minutes,
    max(session_date) as most_recent_session_date
from {{ ref('fct_surf_sessions') }}
group by 1, 2, 3, 4

