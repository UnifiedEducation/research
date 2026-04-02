-- Shoot location entries with FK lookups to film and location

select
    'SL' || lpad(cast(row_number() over (order by s.film_id, s.shoot_date) as varchar), 3, '0') as ShootLocationID,
    s.film_id as FilmID,
    l.LocationID,
    s.shoot_date as shootDate
from {{ ref('stg_shoot_log') }} s
left join {{ ref('e2e_c02_location') }} l on s.city = l.city and s.country = l.country
