select
    spot_id,
    spot_slug,
    spot_name,
    region,
    latitude::numeric as latitude,
    longitude::numeric as longitude,
    preferred_wind_direction,
    notes,
    created_at
from {{ source('app', 'surf_spots') }}

