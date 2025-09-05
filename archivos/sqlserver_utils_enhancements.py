"""
Funciones de mejora para las utilidades de SQL Server
Para ser agregadas al archivo sqlserver_utils.py
"""

def check_sqlserver_service_status():
    """
    Comprueba el estado del servicio de SQL Server en Windows.
    
    Retorno:
    - dict con información del estado del servicio
    """
    import subprocess
    import re
    
    services = {
        'MSSQLSERVER': {'name': 'SQL Server (instancia principal)', 'status': 'Desconocido'},
        'SQLSERVERAGENT': {'name': 'SQL Server Agent', 'status': 'Desconocido'},
        'SQLBrowser': {'name': 'SQL Server Browser', 'status': 'Desconocido'},
        'MSSQL$SQLEXPRESS': {'name': 'SQL Server Express', 'status': 'Desconocido'}
    }
    
    try:
        # Ejecutar comando para listar servicios
        output = subprocess.check_output(
            ["powershell", "-Command", "Get-Service | Where-Object {$_.DisplayName -like '*SQL Server*'} | Select-Object Name,Status"],
            text=True
        )
        
        # Analizar salida
        lines = output.strip().split('\n')
        for line in lines[2:]:  # Saltamos las dos primeras líneas (headers)
            parts = line.strip().split()
            if not parts:
                continue
                
            service_name = parts[0]
            status = ' '.join(parts[1:]) if len(parts) > 1 else 'Desconocido'
            
            # Actualizar el estado si conocemos el servicio
            for key in services:
                if key.lower() == service_name.lower() or service_name.lower().startswith(key.lower()):
                    services[key]['status'] = status
        
        return {
            'success': True,
            'services': services
        }
        
    except Exception as e:
        logger.error(f"Error comprobando servicios de SQL Server: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'services': services
        }

def read_sql_safe(query, engine_or_conn, params=None, chunk_size=None):
    """
    Versión segura de pd.read_sql con manejo de errores mejorado.
    
    Parámetros:
    - query: Consulta SQL (string o objeto SQLAlchemy)
    - engine_or_conn: Conexión o engine SQLAlchemy
    - params: Parámetros para la consulta (dict o None)
    - chunk_size: Tamaño de fragmento para lecturas grandes (None para leer todo)
    
    Retorno:
    - DataFrame de pandas con los resultados o DataFrame vacío en caso de error
    """
    import pandas as pd
    from sqlalchemy import text
    
    # Convertir a objeto text() si es string
    if isinstance(query, str):
        query = text(query)
    
    try:
        if chunk_size:
            # Lectura por fragmentos para conjuntos grandes
            return pd.read_sql(query, engine_or_conn, params=params, chunksize=chunk_size)
        else:
            # Lectura normal
            return pd.read_sql(query, engine_or_conn, params=params)
            
    except Exception as e:
        logger.error(f"Error en read_sql_safe: {str(e)}")
        # Crear un DataFrame vacío con mensaje de error
        return pd.DataFrame({'error': [str(e)]})

def table_exists(table_name, engine=None):
    """
    Verifica si una tabla existe en la base de datos.
    
    Parámetros:
    - table_name: Nombre de la tabla a verificar
    - engine: Engine SQLAlchemy o None (se creará uno nuevo)
    
    Retorno:
    - True si la tabla existe, False en caso contrario
    """
    close_engine = engine is None
    
    try:
        if close_engine:
            engine_url = get_sqlserver_connection_string()
            engine = create_engine(engine_url)
        
        with engine.connect() as conn:
            query = text("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = :table_name 
                AND TABLE_CATALOG = DB_NAME()
            """)
            result = conn.execute(query, {'table_name': table_name}).scalar()
            return result > 0
    except Exception as e:
        logger.error(f"Error verificando si existe la tabla {table_name}: {str(e)}")
        return False
    finally:
        if close_engine and engine:
            engine.dispose()
