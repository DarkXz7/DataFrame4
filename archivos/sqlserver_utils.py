"""
Utilidades para la conexión a SQL Server desde Django
Este módulo proporciona funciones para facilitar la conexión a SQL Server
y manejar errores comunes.
"""
import logging
from django.conf import settings
from django.db import connections, OperationalError, InterfaceError
from sqlalchemy import create_engine, text
from contextlib import contextmanager
from .error_handler import handle_sql_exception, get_friendly_error_message

logger = logging.getLogger(__name__)

def get_sqlserver_connection_string():
    """
    Crea una cadena de conexión para SQLAlchemy basada en la configuración
    actual de settings.py
    """
    # Obtener configuración de settings.py
    db_config = settings.DATABASES['default']
    
    # Determinar si usamos Windows Auth o SQL Auth
    if 'USER' in db_config and 'PASSWORD' in db_config:
        # SQL Auth
        user = db_config.get('USER')
        password = db_config.get('PASSWORD')
        auth_part = f"{user}:{password}@"
    else:
        # Windows Auth
        auth_part = ""
    
    # Parámetros básicos
    host = db_config.get('HOST', 'localhost')
    port = db_config.get('PORT', '1433') or '1433'
    database = db_config.get('NAME', '')
    
    # Determinar parámetros adicionales
    options = db_config.get('OPTIONS', {})
    driver = options.get('driver', 'ODBC Driver 17 for SQL Server')
    
    # Construir parámetros
    params = [f"driver={driver.replace(' ', '+')}"]
    
    # Agregar Trusted_Connection solo si no hay user/password
    if not ('USER' in db_config and 'PASSWORD' in db_config):
        params.append("trusted_connection=yes")
    
    # Agregar otros parámetros de OPTIONS
    for key, value in options.items():
        if key.lower() not in ['driver', 'trusted_connection']:
            params.append(f"{key.lower()}={value}")
    
    # Construir URL completa
    engine_url = f"mssql+pyodbc://{auth_part}{host}"
    
    # Agregar puerto si está definido
    if port:
        engine_url += f":{port}"
    
    # Agregar base de datos y parámetros
    engine_url += f"/{database}?{'&'.join(params)}"
    
    return engine_url

def test_sqlserver_connection():
    """
    Prueba la conexión a SQL Server utilizando la configuración actual.
    Devuelve (éxito, mensaje, engine)
    """
    try:
        # Comprobar conexión de Django
        with connections['default'].cursor() as cursor:
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()[0]
            
        # Crear engine de SQLAlchemy
        engine_url = get_sqlserver_connection_string()
        engine = create_engine(engine_url)
        
        # Probar conexión con SQLAlchemy
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 AS test")).scalar()
            
        return True, f"Conexión exitosa: {version[:50]}...", engine
    
    except (OperationalError, InterfaceError) as e:
        logger.error(f"Error de conexión SQL Server: {str(e)}")
        return False, f"Error de conexión: {str(e)}", None
    
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        return False, f"Error inesperado: {str(e)}", None

@contextmanager
def sqlalchemy_connection():
    """
    Context manager para manejar conexiones SQLAlchemy con manejo robusto de errores.
    Ejemplo de uso:
    
    with sqlalchemy_connection() as conn:
        result = conn.execute(text("SELECT * FROM tabla"))
        # Procesar resultados...
    """
    engine_url = get_sqlserver_connection_string()
    engine = None
    connection = None
    
    try:
        engine = create_engine(engine_url)
        connection = engine.connect()
        yield connection
    except Exception as e:
        # Convertir la excepción a un mensaje amigable (no lanzamos
        # para permitir que el caller maneje la excepción)
        friendly_message = get_friendly_error_message(e)
        logger.error(f"Error en conexión SQL Server: {friendly_message}")
        # Re-lanzar para que el caller pueda manejarla
        raise
    finally:
        # Cerrar recursos incluso si hay error
        if connection is not None:
            connection.close()
        if engine is not None:
            engine.dispose()
        
def get_tables_list():
    """
    Obtiene la lista de tablas disponibles en la base de datos.
    Devuelve una lista de nombres de tablas.
    """
    try:
        with sqlalchemy_connection() as conn:
            query = text("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_CATALOG = DB_NAME()
                ORDER BY TABLE_NAME
            """)
            result = conn.execute(query)
            tables = [row[0] for row in result]
            return tables
    except Exception as e:
        logger.error(f"Error obteniendo tablas: {str(e)}")
        return []
        
def execute_query_safe(query, params=None, fetch_all=True, connection=None):
    """
    Ejecuta una consulta SQL de forma segura con manejo de errores mejorado.
    
    Parámetros:
    - query: Consulta SQL (string o objeto text())
    - params: Parámetros para la consulta (dict o None)
    - fetch_all: Si es True, devuelve todos los resultados, si es False, solo el primero
    - connection: Conexión SQLAlchemy existente o None (se creará una nueva)
    
    Retorno:
    - Resultados de la consulta o None si hay error
    
    Ejemplo:
    results = execute_query_safe("SELECT * FROM users WHERE active=:active", {'active': True})
    """
    # Convertir a objeto text() si es string
    if isinstance(query, str):
        query = text(query)
    
    # Determinar si necesitamos crear nuestra propia conexión
    close_connection = connection is None
    
    try:
        if close_connection:
            with sqlalchemy_connection() as conn:
                result = conn.execute(query, params or {})
                if fetch_all:
                    return result.fetchall()
                else:
                    return result.fetchone()
        else:
            # Usar la conexión proporcionada
            result = connection.execute(query, params or {})
            if fetch_all:
                return result.fetchall()
            else:
                return result.fetchone()
                
    except Exception as e:
        logger.error(f"Error ejecutando consulta: {str(e)}")
        logger.debug(f"Consulta: {query}")
        logger.debug(f"Parámetros: {params}")
        # No manejamos la excepción aquí, dejamos que se propague
        # para que el caller pueda manejarla apropiadamente
        raise

def execute_query_safe(query, params=None, fetch_all=True, connection=None):
    """
    Ejecuta una consulta SQL de forma segura con manejo de errores mejorado.
    
    Parámetros:
    - query: Consulta SQL (string o objeto text())
    - params: Parámetros para la consulta (dict o None)
    - fetch_all: Si es True, devuelve todos los resultados, si es False, solo el primero
    - connection: Conexión SQLAlchemy existente o None (se creará una nueva)
    
    Retorno:
    - Resultados de la consulta o None si hay error
    
    Ejemplo:
    results = execute_query_safe("SELECT * FROM users WHERE active=:active", {'active': True})
    """
    # Convertir a objeto text() si es string
    if isinstance(query, str):
        query = text(query)
    
    # Determinar si necesitamos crear nuestra propia conexión
    close_connection = connection is None
    
    try:
        if close_connection:
            with sqlalchemy_connection() as conn:
                result = conn.execute(query, params or {})
                if fetch_all:
                    return result.fetchall()
                else:
                    return result.fetchone()
        else:
            # Usar la conexión proporcionada
            result = connection.execute(query, params or {})
            if fetch_all:
                return result.fetchall()
            else:
                return result.fetchone()
                
    except Exception as e:
        logger.error(f"Error ejecutando consulta: {str(e)}")
        logger.debug(f"Consulta: {query}")
        logger.debug(f"Parámetros: {params}")
        # No manejamos la excepción aquí, dejamos que se propague
        # para que el caller pueda manejarla apropiadamente
        raise

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
