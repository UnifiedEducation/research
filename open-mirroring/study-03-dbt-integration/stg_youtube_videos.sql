{{ config(materialized='view') }}

select
    video_id,
    title,
    channel_id,
    cast(published_at as timestamp) as published_at,
    view_count,
    like_count
from {{ read_delta('youtube', 'videos', source_root='mirror') }}
