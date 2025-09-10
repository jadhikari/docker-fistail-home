from django import template

register = template.Library()

@register.filter
def subtract(value, arg):
    """Subtract the arg from the value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def lookup(dictionary, key):
    """Look up a key in a dictionary."""
    try:
        return dictionary.get(key, 0)
    except (AttributeError, TypeError):
        return 0
