-- Override dbt-duckdb's table materialization to use CREATE OR REPLACE TABLE
-- directly, avoiding the __dbt_tmp 
--
-- Why: DuckLake renames tables in its SQLite catalog but physical Parquet
-- files stay at the __dbt_tmp path. delta_export() then writes _delta_log/
-- at that path, so Fabric sees __dbt_tmp tables. This override writes
-- directly to the final table name.


{% materialization table, adapter="duckdb", supported_languages=['sql'] %}

  {%-
set existing_relation
= load_cached_relation
(this) -%}
  {%-
set target_relation
= this.incorporate
(type='table') %}
  {%
set grant_config
= config.get
('grants') %}

  {{ run_hooks
(pre_hooks, inside_transaction=False) }}
  {{ run_hooks
(pre_hooks, inside_transaction=True) }}

  {% call statement
('main') -%}
create or replace table {{ target_relation }} as
(
      {{ compiled_code }}
    )
  {%- endcall %}

  {% do create_indexes
(target_relation) %}

  {{ run_hooks
(post_hooks, inside_transaction=True) }}

  {%
set should_revoke
= should_revoke
(existing_relation, full_refresh_mode=True) %}
  {% do apply_grants
(target_relation, grant_config, should_revoke=should_revoke) %}
  {% do persist_docs
(target_relation, model) %}

  {{ adapter.
commit
() }}

  {{ run_hooks
(post_hooks, inside_transaction=False) }}

  {{
return({'relations': [target_relation]})
}}

{% endmaterialization %}
