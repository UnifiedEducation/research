-- Extract distinct actors from denormalized cast credits

with distinct_actors as (
    select distinct
        actor_name,
        birth_year
    from {{ ref('stg_cast_credits') }}
    where actor_name is not null
)

select
    'A' || lpad(cast(row_number() over (order by actor_name) as varchar), 3, '0') as ActorID,
    actor_name as name,
    birth_year as birthYear
from distinct_actors
