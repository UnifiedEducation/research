{% macro read_delta(schema_name, table_name) %}
  {% if target.name == 'local' %}
    {{ source(schema_name, table_name) }}
  {% else %}
    delta_scan('{{ env_var("ROOT_PATH") }}/Tables/{{ schema_name }}/{{ table_name }}')
  {% endif %}
{% endmacro %}
