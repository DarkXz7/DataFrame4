"""
Utilidades para procesamiento de errores SQL Server
"""

def get_sql_error_details(error_str):
    """
    Analiza el mensaje de error de SQL Server y devuelve información más útil
    
    Parámetros:
    - error_str: String con el mensaje de error de SQL Server
    
    Retorna:
    - Dict con información procesada del error
    """
    import re
    
    error_info = {
        'tipo': 'desconocido',
        'detalle': error_str,
        'sugerencia': None
    }
    
    # Patrones comunes de errores SQL Server
    patrones = [
        {
            'regex': r"Cannot find the object \"([^\"]+)\"",
            'tipo': 'objeto_no_encontrado',
            'sugerencia': "El objeto referenciado no existe. Verifique si hay referencias a tablas o columnas que no existen."
        },
        {
            'regex': r"Incorrect syntax near '([^']+)'",
            'tipo': 'syntax_error',
            'sugerencia': "Error de sintaxis. Podría ser sintaxis específica de MySQL no compatible con SQL Server."
        },
        {
            'regex': r"Invalid column name '([^']+)'",
            'tipo': 'columna_invalida',
            'sugerencia': "La columna referenciada no existe. Verifique si usa comillas invertidas (`) en lugar de corchetes []."
        },
        {
            'regex': r"Conversion failed when converting ([^']+) value",
            'tipo': 'conversion_tipos',
            'sugerencia': "Error al convertir tipos de datos. SQL Server maneja tipos de manera diferente a MySQL."
        },
        {
            'regex': r"'([^']+)' is not a recognized built-in function name",
            'tipo': 'funcion_desconocida',
            'sugerencia': "La función usada no existe en SQL Server. Puede requerir un equivalente específico de SQL Server."
        },
        {
            'regex': r"There is already an object named '([^']+)' in the database",
            'tipo': 'objeto_duplicado',
            'sugerencia': "Objeto duplicado. Agregue DROP IF EXISTS antes de CREATE o cambie el nombre."
        }
    ]
    
    # Buscar coincidencia con patrones conocidos
    for patron in patrones:
        match = re.search(patron['regex'], error_str, re.IGNORECASE)
        if match:
            error_info['tipo'] = patron['tipo']
            error_info['sugerencia'] = patron['sugerencia']
            error_info['objeto'] = match.group(1) if match.groups() else None
            break
    
    return error_info
