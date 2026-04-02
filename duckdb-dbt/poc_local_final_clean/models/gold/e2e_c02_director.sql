-- Extract distinct directors from denormalized film catalog
-- Generate DirectorID using 'D' + zero-padded row number

with distinct_directors as (
    select distinct director_name
    from {{ ref('stg_film_catalog') }}
    where director_name is not null
)

select
    'D' || lpad(cast(row_number() over (order by director_name) as varchar), 3, '0') as DirectorID,
    director_name as name
from distinct_directors
