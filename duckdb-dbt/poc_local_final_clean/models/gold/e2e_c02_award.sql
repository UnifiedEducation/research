-- Awards with generated AwardID

select
    'AW' || lpad(cast(row_number() over (order by film_id, award_name) as varchar), 3, '0') as AwardID,
    award_name as name,
    category,
    year,
    film_id as FilmID
from {{ ref('stg_awards') }}
