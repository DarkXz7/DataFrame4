"""
Manejador de errores para las conexiones de SQL Server
Proporciona funciones para manejar, registrar y presentar errores de SQL Server
de manera consistente en toda la aplicación.
"""
import logging
import traceback
import sys
import re
import pyodbc
import sqlalchemy.exc
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect

# Configurar logger
logger = logging.getLogger(__name__)

# Códigos de error comunes de SQL Server y sus soluciones
ERROR_SOLUTIONS = {
    # Errores de autenticación
    18456: "Error de autenticación. Verifique el usuario y la contraseña. Si usa Windows Authentication, verifique que 'Trusted_Connection' esté configurado como 'yes'.",
    18452: "El inicio de sesión no tiene permisos para conectarse a la base de datos. Revise los permisos del usuario.",
    4060: "No se puede abrir la base de datos. Verifique que la base de datos exista y que el usuario tenga permisos.",
    4064: "No se puede abrir la sesión de usuario predeterminada. Verifique la configuración de usuario.",
    
    # Errores de conexión
    53: "No se puede conectar a la instancia de SQL Server. Verifique que el servicio esté en ejecución, el nombre de instancia sea correcto y que el firewall no esté bloqueando la conexión.",
    40: "No se puede abrir una conexión con SQL Server. Tiempo de espera agotado o servidor no accesible.",
    10061: "El servidor rechazó activamente la conexión. Verifique que SQL Server esté ejecutándose y acepte conexiones.",
    17: "SQL Server no está disponible o rechazó la conexión. Compruebe la instancia SQL Server y los permisos de red.",
    
    # Errores de permisos
    229: "El usuario no tiene permisos para ejecutar esta acción. Revise los permisos de la base de datos.",
    262: "Permisos insuficientes para modificar la base de datos o tabla.",
    297: "Usuario sin permiso para usar la instrucción CREATE.",
    
    # Otros errores
    2714: "El objeto ya existe en la base de datos.",
    208: "Objeto no encontrado. Verifique el nombre de la tabla o vista.",
    156: "Error de sintaxis SQL. Verifique la consulta.",
    547: "La instrucción viola una restricción de integridad referencial."
}

def extract_error_code(error_message):
    """Extrae el código de error de SQL Server del mensaje de error."""
    # Patrones comunes de códigos de error SQL Server
    patterns = [
        r'Error (\d+)',           # Error XXXXX
        r'Error:? (\d+),',        # Error: XXXXX,
        r'\[(\d+)\]',             # [XXXXX]
        r'error code (\d+)',      # error code XXXXX
        r'code (\d+)',            # code XXXXX
        r'error state (\d+)'      # error state XXXXX
    ]
    
    for pattern in patterns:
        match = re.search(pattern, str(error_message))
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
    return None

def get_friendly_error_message(exception):
    """
    Convierte excepciones de SQL Server en mensajes amigables con
    posibles soluciones.
    """
    error_message = str(exception)
    error_code = extract_error_code(error_message)
    
    # Registro detallado del error para debug
    logger.error(f"Error SQL Server: {error_code} - {error_message}")
    
    if error_code in ERROR_SOLUTIONS:
        solution = ERROR_SOLUTIONS[error_code]
        return f"Error de base de datos ({error_code}): {solution}"
    
    # Manejo de errores específicos sin código numérico
    if "login timeout expired" in error_message.lower():
        return "Tiempo de espera agotado al conectar con SQL Server. Verifique que el servidor esté en ejecución y accesible."
    
    if "network-related" in error_message.lower():
        return "Error de red al conectar con SQL Server. Verifique que el servidor esté en ejecución, el nombre sea correcto y sea accesible desde este equipo."
    
    if "incorrect syntax" in error_message.lower():
        return "Error de sintaxis SQL en la consulta."
    
    # Mensaje genérico para otros errores
    return f"Error de base de datos: {error_message}"

def handle_sql_exception(exception, request=None, redirect_url=None):
    """
    Maneja excepciones de SQL de manera centralizada.
    Registra el error, muestra mensajes al usuario y redirige si es necesario.
    
    Parámetros:
    - exception: La excepción capturada
    - request: Objeto request de Django para mostrar mensajes (opcional)
    - redirect_url: URL a la que redirigir tras el error (opcional)
    
    Retorno:
    - Si hay request y redirect_url: objeto HttpResponseRedirect
    - Si hay request sin redirect_url: None (solo muestra mensaje)
    - Si no hay request: texto con mensaje de error
    """
    # Registrar error con detalles para depuración
    logger.error("Error SQL Server:")
    logger.error(f"Tipo: {type(exception).__name__}")
    logger.error(f"Mensaje: {str(exception)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Obtener mensaje amigable
    friendly_message = get_friendly_error_message(exception)
    
    if request:
        # Mostrar mensaje al usuario en la interfaz
        messages.error(request, friendly_message)
        
        # Redirigir si se especificó una URL
        if redirect_url:
            return redirect(redirect_url)
    
    # Si no hay request, devolver el mensaje para uso programático
    return friendly_message

def handle_sql_exception_json(exception):
    """
    Versión para APIs que devuelve un JsonResponse con el error.
    """
    friendly_message = get_friendly_error_message(exception)
    
    # Determinar código HTTP según el error
    error_code = extract_error_code(str(exception))
    http_status = 500  # Por defecto error interno
    
    if error_code in [18456, 18452, 4064]:  # Errores de autenticación
        http_status = 401
    elif error_code in [229, 262, 297]:  # Errores de permisos
        http_status = 403
    elif error_code in [208, 4060]:  # Recursos no encontrados
        http_status = 404
    
    return JsonResponse({
        'ok': False,
        'error': friendly_message,
        'error_code': error_code
    }, status=http_status)

def is_sql_server_error(exception):
    """Comprueba si la excepción está relacionada con SQL Server."""
    return (
        isinstance(exception, pyodbc.Error) or
        isinstance(exception, sqlalchemy.exc.SQLAlchemyError) or
        "sql" in str(type(exception)).lower()
    )

# Ejemplo de uso:
"""
from .error_handler import handle_sql_exception, handle_sql_exception_json, is_sql_server_error

def vista_ejemplo(request):
    try:
        # Código que puede causar error de SQL Server
        with sqlalchemy_connection() as conn:
            result = conn.execute(text("SELECT * FROM tabla_inexistente"))
    except Exception as e:
        if is_sql_server_error(e):
            return handle_sql_exception(e, request, redirect_url='inicio')
        else:
            # Manejar otro tipo de errores
            messages.error(request, f"Error inesperado: {str(e)}")
            return redirect('inicio')
"""
