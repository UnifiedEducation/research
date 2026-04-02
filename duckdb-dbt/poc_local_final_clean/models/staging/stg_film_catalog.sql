select distinct
    film_id,
    title,
    release_year,
    rating,
    director_name,
    studio_name,
    genre,
    budget
from {{ read_delta('raw', 'raw_film_catalog') }}
