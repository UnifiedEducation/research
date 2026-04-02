select distinct
    film_id,
    award_name,
    category,
    year
from {{ read_delta('raw', 'raw_awards') }}
