{% macro read_delta(schema_name, table_name, source_root='lakehouse') %}
  {% if target.name == 'local' %}
    {{ source(schema_name, table_name) }}
  {% else %}
    {% if source_root == 'mirror' %}
      {% set root = env_var('MIRROR_ROOT_PATH') %}
    {% else %}
      {% set root = env_var('ROOT_PATH') %}
    {% endif %}
    delta_scan('{{ root }}/Tables/{{ schema_name }}/{{ table_name }}')
  {% endif %}
{% endmacro %}
