{% for section, _ in sections.items() %}
{% if section %}## {{section}}
{% endif %}

{% if sections[section] %}
{% for category, val in definitions.items() if category in sections[section]%}
### {{ definitions[category]['name'] }}

{% if definitions[category]['showcontent'] %}
{% for text, values in sections[section][category].items() %}
{% for line in text.splitlines() %}
{% if line.strip() %}- {{ line.strip() }} ({{ values|join(', ') }})
{% endif %}
{% endfor %}
{% endfor %}

{% else %}
- {{ sections[section][category]['']|join(', ') }}

{% endif %}
{% if sections[section][category]|length == 0 %}
No significant changes.

{% else %}
{% endif %}
{% endfor %}
{% else %}
No significant changes.

{% endif %}
{% endfor %}
