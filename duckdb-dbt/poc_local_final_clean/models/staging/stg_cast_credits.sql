select distinct
    film_id,
    actor_name,
    birth_year,
    role_name
from {{ read_delta('raw', 'raw_cast_credits') }}
