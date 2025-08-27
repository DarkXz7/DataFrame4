from django import template

register = template.Library()

@register.filter
def split(value, separator):
    """Divide una cadena por el separador especificado"""
    if not value:
        return []
    return str(value).split(separator)

@register.filter  
def get_item(dictionary, key):
    """Obtiene un item de un diccionario"""
    return dictionary.get(key)