-- Extract distinct locations from shoot log

with distinct_locations as (
    select distinct city, country
    from {{ ref('stg_shoot_log') }}
    where city is not null
)

select
    'L' || lpad(cast(row_number() over (order by country, city) as varchar), 3, '0') as LocationID,
    city,
    country
from distinct_locations
