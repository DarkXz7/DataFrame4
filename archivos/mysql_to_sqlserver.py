"""
Utilidad para convertir scripts SQL de MySQL a SQL Server

Este módulo proporciona funciones para transformar sentencias SQL escritas para MySQL
para que sean compatibles con SQL Server, facilitando la migración entre sistemas.
"""
import re
import logging

logger = logging.getLogger(__name__)

def convert_mysql_to_sqlserver(mysql_script):
    """
    Convierte un script SQL de MySQL a SQL Server.
    
    Parámetros:
    - mysql_script: String con el script SQL de MySQL
    
    Retorna:
    - String con el script convertido para SQL Server
    """
    script = mysql_script
    
    # Eliminar/comentar configuraciones específicas de MySQL
    script = re.sub(r'SET\s+SQL_MODE\s*=.*?;', '-- SQL_MODE no es compatible con SQL Server\n', script)
    script = re.sub(r'SET\s+time_zone\s*=.*?;', '-- time_zone se maneja diferente en SQL Server\n', script)
    
    # Transformar START TRANSACTION a BEGIN TRANSACTION
    script = re.sub(r'START\s+TRANSACTION', 'BEGIN TRANSACTION', script)
    
    # Reemplazar backticks (`) por corchetes ([])
    script = re.sub(r'`([^`]+)`', r'[\1]', script)
    
    # Eliminar ENGINE, CHARSET y COLLATE en CREATE TABLE
    script = re.sub(r'ENGINE\s*=\s*\w+', '', script)
    script = re.sub(r'DEFAULT\s+CHARSET\s*=\s*\w+', '', script)
    script = re.sub(r'COLLATE\s*=\s*[\w_]+', '', script)
    
    # Arreglar tipos de datos
    script = re.sub(r'int\(\d+\)', 'int', script)
    script = re.sub(r'varchar\((\d+)\)', r'nvarchar(\1)', script)
    script = re.sub(r'text', 'nvarchar(max)', script)
    
    # AUTO_INCREMENT a IDENTITY
    script = re.sub(r'AUTO_INCREMENT', 'IDENTITY(1,1)', script)
    
    # Arreglar UNIQUE KEY y PRIMARY KEY en CREATE TABLE
    def fix_keys(match):
        key_def = match.group(1)
        if 'PRIMARY KEY' in key_def:
            return key_def  # Mantener PRIMARY KEY como está
        return key_def.replace('KEY', 'INDEX')
    
    script = re.sub(r'((?:UNIQUE|PRIMARY)\s+KEY\s+[^,\)]+)', fix_keys, script)
    
    # Arreglar sintaxis de INSERT INTO con varios valores
    def fix_insert(match):
        into_part = match.group(1)
        values_part = match.group(2)
        values_list = values_part.split('),(')
        
        if len(values_list) <= 1:
            return f"{into_part} VALUES ({values_part})"
        
        result = []
        for i, values in enumerate(values_list):
            # Limpiar los paréntesis extras del primer y último elemento
            if i == 0:
                values = values.rstrip(')')
            elif i == len(values_list) - 1:
                values = values.lstrip('(')
            else:
                values = values
                
            if i == 0:
                result.append(f"{into_part} VALUES ({values})")
            else:
                columns = re.search(r'INSERT\s+INTO\s+\[\w+\]\s*\(([^\)]+)\)', into_part)
                if columns:
                    result.append(f"INSERT INTO {into_part.split('(')[0]}({columns.group(1)}) VALUES ({values})")
                else:
                    result.append(f"{into_part} VALUES ({values})")
        
        return ";\n".join(result)
    
    script = re.sub(r'(INSERT\s+INTO\s+\[\w+\](?:\s*\([^\)]+\))?\s*VALUES\s*)\(([^\;]+)\)', fix_insert, script)
    
    # Eliminar ; dentro de CREATE PROCEDURE o FUNCTION (SQL Server no lo permite)
    def fix_stored_procedure(match):
        proc_content = match.group(2)
        proc_content = proc_content.replace(';', '')
        return f"{match.group(1)}\n{proc_content}\nEND"
    
    script = re.sub(r'(CREATE\s+(?:PROCEDURE|FUNCTION)\s+[\w\.\[\]]+\s*\([^\)]*\)\s*.*?BEGIN)(.*?)(END)', 
                   fix_stored_procedure, script, flags=re.DOTALL)
    
    # Eliminar DELIMITER (SQL Server no usa este concepto)
    script = re.sub(r'DELIMITER\s+.*?;', '', script)
    
    # Limpiar cierres de procedimientos múltiples
    script = script.replace('END$$', 'END')
    script = script.replace('END ;', 'END;')
    
    # Dividir el script en sentencias individuales
    statements = []
    lines = script.split('\n')
    current_statement = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('--'):  # Línea vacía o comentario
            if current_statement:
                current_statement.append(line)
            continue
        
        current_statement.append(line)
        if line.endswith(';'):
            statements.append('\n'.join(current_statement))
            current_statement = []
    
    # Agregar la última declaración si existe
    if current_statement:
        statements.append('\n'.join(current_statement))
    
    # Volver a unir las sentencias
    clean_script = '\n\n'.join(statements)
    
    return clean_script

def execute_sqlserver_script(engine, script):
    """
    Ejecuta un script SQL en SQL Server, dividiendo las sentencias y manejando errores.
    
    Parámetros:
    - engine: Objeto engine de SQLAlchemy
    - script: String con el script SQL
    
    Retorna:
    - Diccionario con resultados de la ejecución
    """
    from sqlalchemy import text
    from .sql_error_utils import get_sql_error_details
    
    # Dividir el script en sentencias individuales
    statements = []
    current_statement = []
    
    for line in script.split('\n'):
        line_stripped = line.strip()
        
        # Ignorar líneas vacías y comentarios como sentencias independientes
        if not line_stripped or line_stripped.startswith('--'):
            continue
        
        current_statement.append(line)
        
        if line_stripped.endswith(';'):
            statements.append('\n'.join(current_statement))
            current_statement = []
    
    # Agregar última sentencia si existe
    if current_statement:
        statements.append('\n'.join(current_statement))
    
    # Ejecutar cada sentencia
    results = {
        'total': len(statements),
        'success': 0,
        'errors': [],
        'tables_created': [],
        'warnings': []
    }
    
    with engine.begin() as conn:
        for i, stmt in enumerate(statements):
            stmt = stmt.strip()
            if not stmt:
                continue
                
            try:
                # Detectar tipo de sentencia para procesamiento especializado
                stmt_type = 'unknown'
                affected_object = None
                
                # Detectar CREATE TABLE
                table_match = re.search(r'CREATE\s+TABLE\s+\[([^\]]+)\]', stmt, re.IGNORECASE)
                if table_match:
                    stmt_type = 'create_table'
                    affected_object = table_match.group(1)
                
                # Detectar INSERT INTO
                insert_match = re.search(r'INSERT\s+INTO\s+\[([^\]]+)\]', stmt, re.IGNORECASE)
                if insert_match:
                    stmt_type = 'insert'
                    affected_object = insert_match.group(1)
                
                # Ejecutar la sentencia
                conn.execute(text(stmt))
                results['success'] += 1
                
                # Registrar tablas creadas
                if stmt_type == 'create_table':
                    results['tables_created'].append(affected_object)
                
            except Exception as e:
                # Analizar el error para dar información más detallada
                error_message = str(e)
                error_details = get_sql_error_details(error_message)
                
                error_info = {
                    'statement': stmt[:100] + '...' if len(stmt) > 100 else stmt,
                    'error': error_message,
                    'index': i,
                    'tipo': error_details['tipo'],
                    'sugerencia': error_details['sugerencia']
                }
                results['errors'].append(error_info)
                
                logger.error(f"Error ejecutando sentencia SQL #{i}: {error_message}")
                logger.debug(f"Sentencia con error: {stmt}")
                
                # Agregar advertencias relevantes basadas en el tipo de error
                if error_details['tipo'] == 'syntax_error':
                    results['warnings'].append(
                        "Se detectaron errores de sintaxis. Revise si hay construcciones específicas de MySQL no soportadas en SQL Server."
                    )
                elif error_details['tipo'] == 'conversion_tipos':
                    results['warnings'].append(
                        "Error de conversión de tipos. SQL Server maneja tipos de datos de forma más estricta que MySQL."
                    )
    
    # Eliminar advertencias duplicadas
    if 'warnings' in results:
        results['warnings'] = list(set(results['warnings']))
    
    return results
