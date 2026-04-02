select distinct
    film_id,
    city,
    country,
    shoot_date
from {{ read_delta('raw', 'raw_shoot_log') }}
