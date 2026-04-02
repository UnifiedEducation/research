-- Cast entries with FK lookups to film and actor
-- Generate CastID per row

select
    'CA' || lpad(cast(row_number() over (order by c.film_id, c.actor_name) as varchar), 3, '0') as CastID,
    c.film_id as FilmID,
    a.ActorID,
    c.role_name as roleName
from {{ ref('stg_cast_credits') }} c
left join {{ ref('e2e_c02_actor') }} a on c.actor_name = a.name
