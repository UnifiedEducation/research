-- Extract distinct studios from denormalized film catalog
-- Generate StudioID and derive founded year from earliest film

with distinct_studios as (
    select
        studio_name,
        min(release_year) - 10 as founded_approx
    from {{ ref('stg_film_catalog') }}
    where studio_name is not null
    group by studio_name
)

select
    'ST' || lpad(cast(row_number() over (order by studio_name) as varchar), 3, '0') as StudioID,
    studio_name as name,
    founded_approx as founded,
    cast(null as VARCHAR) as country
from distinct_studios
