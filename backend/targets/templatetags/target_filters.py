from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if isinstance(key, str) and ',' in key:
        # Handle tuple keys like "2024,12"
        year, month = key.split(',')
        key = (int(year), int(month))
    return dictionary.get(key) 