-- Films with FK lookups to director, studio, genre dimension tables
-- Incremental: only inserts new film_ids. Use dbt run --full-refresh for schema changes.
{{ config(materialized='incremental', unique_key='FilmID') }}

select
    f.film_id as FilmID,
    f.title,
    f.release_year as releaseYear,
    f.rating,
    d.DirectorID,
    s.StudioID,
    g.GenreID,
    f.budget,
    cast(null as bigint) as runtime,
    cast(null as varchar) as language,
    cast(floor(f.release_year / 10) * 10 as int) || 's' as releaseDecade,
    f.title || ' (' || f.release_year || ')' as titleYear
from {{ ref('stg_film_catalog') }} f
left join {{ ref('e2e_c02_director') }} d on f.director_name = d.name
left join {{ ref('e2e_c02_studio') }} s on f.studio_name = s.name
left join {{ ref('e2e_c02_genre') }} g on f.genre = g.name

{% if is_incremental() %}
where f.film_id not in (select FilmID from {{ this }})
{% endif %}
