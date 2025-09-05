"""
Utilidad para analizar compatibilidad de scripts SQL de MySQL con SQL Server
"""
import re

def analizar_compatibilidad_mysql_sqlserver(sql_script):
    """
    Analiza un script SQL de MySQL para detectar posibles problemas de compatibilidad
    con SQL Server y ofrecer recomendaciones.
    
    Parámetros:
    - sql_script: String con el script SQL de MySQL
    
    Retorna:
    - Dict con información sobre compatibilidad y recomendaciones
    """
    resultado = {
        'total_problemas': 0,
        'nivel_compatibilidad': 'alto',
        'problemas': [],
        'recomendaciones': []
    }
    
    # Patrones a detectar que pueden causar problemas
    patrones_problematicos = [
        {
            'regex': r'LIMIT\s+\d+',
            'descripcion': 'Cláusula LIMIT no compatible con SQL Server',
            'recomendacion': 'Reemplazar LIMIT con TOP en SQL Server',
            'gravedad': 'alta'
        },
        {
            'regex': r'AUTO_INCREMENT',
            'descripcion': 'AUTO_INCREMENT no existe en SQL Server',
            'recomendacion': 'Usar IDENTITY(1,1) en lugar de AUTO_INCREMENT',
            'gravedad': 'media'
        },
        {
            'regex': r'ENGINE\s*=',
            'descripcion': 'Especificación de ENGINE no aplicable a SQL Server',
            'recomendacion': 'Eliminar ENGINE=InnoDB y configuraciones similares',
            'gravedad': 'baja'
        },
        {
            'regex': r'UNSIGNED',
            'descripcion': 'Tipos UNSIGNED no existen en SQL Server',
            'recomendacion': 'Usar tipos sin UNSIGNED y ajustar rangos si es necesario',
            'gravedad': 'media'
        },
        {
            'regex': r'NOW\(\)',
            'descripcion': 'Función NOW() no disponible en SQL Server',
            'recomendacion': 'Usar GETDATE() en lugar de NOW()',
            'gravedad': 'baja'
        },
        {
            'regex': r'CONCAT_WS\(',
            'descripcion': 'Función CONCAT_WS no disponible en SQL Server',
            'recomendacion': 'Usar combinación de CONCAT y COALESCE',
            'gravedad': 'media'
        },
        {
            'regex': r'ON\s+DUPLICATE\s+KEY\s+UPDATE',
            'descripcion': 'Sintaxis ON DUPLICATE KEY UPDATE no existe en SQL Server',
            'recomendacion': 'Usar MERGE o construcciones con EXISTS',
            'gravedad': 'alta'
        }
    ]
    
    # Detectar problemas potenciales
    for patron in patrones_problematicos:
        coincidencias = re.findall(patron['regex'], sql_script, re.IGNORECASE)
        if coincidencias:
            problema = {
                'tipo': patron['descripcion'],
                'ocurrencias': len(coincidencias),
                'gravedad': patron['gravedad'],
                'recomendacion': patron['recomendacion']
            }
            resultado['problemas'].append(problema)
            resultado['total_problemas'] += len(coincidencias)
            
            # Agregar recomendación única
            if patron['recomendacion'] not in resultado['recomendaciones']:
                resultado['recomendaciones'].append(patron['recomendacion'])
    
    # Determinar nivel de compatibilidad
    problemas_graves = sum(1 for p in resultado['problemas'] if p['gravedad'] == 'alta')
    problemas_medios = sum(1 for p in resultado['problemas'] if p['gravedad'] == 'media')
    
    if problemas_graves > 0:
        resultado['nivel_compatibilidad'] = 'bajo'
    elif problemas_medios > 2:
        resultado['nivel_compatibilidad'] = 'medio'
    elif resultado['total_problemas'] > 5:
        resultado['nivel_compatibilidad'] = 'medio'
    
    return resultado
