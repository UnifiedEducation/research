-- Extract distinct genres from denormalized film catalog

with distinct_genres as (
    select distinct genre
    from {{ ref('stg_film_catalog') }}
    where genre is not null
),

genre_film_counts as (
    select genre, count(*) as film_count
    from {{ ref('stg_film_catalog') }}
    where genre is not null
    group by genre
)

select
    'G' || lpad(cast(row_number() over (order by dg.genre) as varchar), 3, '0') as GenreID,
    dg.genre as name,
    'Films in the ' || dg.genre || ' genre' as description,
    coalesce(gfc.film_count, 0) as popularity
from distinct_genres dg
left join genre_film_counts gfc on dg.genre = gfc.genre
