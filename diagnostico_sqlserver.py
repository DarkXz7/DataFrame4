"""
Script de diagnóstico para conexiones SQL Server
Este script verifica varios aspectos de la configuración para ayudar a identificar
problemas de conexión con SQL Server.
"""
import os
import sys
import socket
import subprocess
import platform
from sqlalchemy import create_engine, text
from django.conf import settings
import django

# Inicializar Django para acceder a settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cargador.settings')
django.setup()

def print_header(titulo):
    """Imprime un encabezado formateado"""
    print("\n" + "=" * 60)
    print(f" {titulo}")
    print("=" * 60)

def verificar_sistema():
    """Verificar información del sistema operativo"""
    print_header("INFORMACIÓN DEL SISTEMA")
    print(f"Sistema Operativo: {platform.system()} {platform.release()} {platform.version()}")
    print(f"Arquitectura: {platform.architecture()[0]}")
    print(f"Python versión: {platform.python_version()}")

def verificar_red():
    """Verificar conexión de red básica"""
    print_header("PRUEBAS DE RED")
    
    # Obtener host de settings.py
    host = settings.DATABASES['default'].get('HOST', 'localhost')
    if host == 'localhost' or host == '127.0.0.1':
        host_real = 'localhost'
    else:
        host_real = host
        
    # Probar ping al servidor
    print(f"Haciendo ping a {host_real}...")
    try:
        if platform.system().lower() == 'windows':
            param = '-n'
        else:
            param = '-c'
        resultado = subprocess.run(['ping', param, '2', host_real], 
                                capture_output=True, text=True, check=False)
        if resultado.returncode == 0:
            print(f"✅ Ping exitoso a {host_real}")
        else:
            print(f"❌ Error en ping a {host_real}")
            print(f"Detalles: {resultado.stdout}")
    except Exception as e:
        print(f"❌ Error ejecutando ping: {e}")
    
    # Probar conexión directa al puerto
    puerto = settings.DATABASES['default'].get('PORT', '1433') 
    puerto = puerto or '1433'  # Si está vacío, usar puerto por defecto
    
    print(f"\nProbando conexión al puerto {puerto} en {host_real}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    try:
        resultado = sock.connect_ex((host_real if host_real != 'localhost' else '127.0.0.1', int(puerto)))
        if resultado == 0:
            print(f"✅ El puerto {puerto} está abierto y accesible")
        else:
            print(f"❌ No se puede conectar al puerto {puerto}")
            print(f"   Código de error: {resultado}")
    except Exception as e:
        print(f"❌ Error probando el puerto: {e}")
    finally:
        sock.close()

def verificar_configuracion_django():
    """Verificar la configuración de Django para SQL Server"""
    print_header("CONFIGURACIÓN DE DJANGO")
    
    db_config = settings.DATABASES.get('default', {})
    print(f"ENGINE: {db_config.get('ENGINE', '-- no configurado --')}")
    print(f"NAME: {db_config.get('NAME', '-- no configurado --')}")
    print(f"USER: {db_config.get('USER', '-- no configurado --')}")
    print(f"PASSWORD: {'*' * len(db_config.get('PASSWORD', ''))} (oculta)")
    print(f"HOST: {db_config.get('HOST', '-- no configurado --')}")
    print(f"PORT: {db_config.get('PORT', '-- no configurado --') or '1433 (por defecto)'}")
    
    opciones = db_config.get('OPTIONS', {})
    print("\nOPCIONES:")
    for clave, valor in opciones.items():
        print(f"  - {clave}: {valor}")

def verificar_driver_odbc():
    """Verificar si el driver ODBC para SQL Server está instalado"""
    print_header("DRIVER ODBC")
    
    try:
        if platform.system().lower() == 'windows':
            import pyodbc
            drivers = pyodbc.drivers()
            print("Drivers ODBC instalados:")
            for idx, driver in enumerate(drivers, 1):
                print(f"{idx}. {driver}")
            
            driver_requerido = settings.DATABASES['default'].get('OPTIONS', {}).get('driver', '')
            if driver_requerido and driver_requerido in drivers:
                print(f"\n✅ El driver requerido '{driver_requerido}' está instalado")
            elif driver_requerido:
                print(f"\n❌ El driver requerido '{driver_requerido}' NO está instalado")
            else:
                print("\n⚠️ No se ha especificado ningún driver en la configuración")
        else:
            print("La verificación de drivers ODBC solo está disponible en Windows")
    except ImportError:
        print("❌ No se pudo importar pyodbc. Asegúrate de tenerlo instalado (pip install pyodbc)")
    except Exception as e:
        print(f"❌ Error al verificar drivers ODBC: {e}")

def probar_conexion():
    """Probar la conexión a SQL Server"""
    print_header("PRUEBA DE CONEXIÓN")
    
    db_config = settings.DATABASES.get('default', {})
    
    # Extraer datos de conexión
    host = db_config.get('HOST', 'localhost')
    port = db_config.get('PORT', '') or '1433'  # Puerto por defecto de SQL Server
    user = db_config.get('USER', '')
    password = db_config.get('PASSWORD', '')
    database = db_config.get('NAME', '')
    driver = db_config.get('OPTIONS', {}).get('driver', 'ODBC Driver 17 for SQL Server')
    
    if not all([user, password, database]):
        print("❌ Faltan datos de configuración (usuario, contraseña o base de datos)")
        return
    
    # Crear string de conexión
    engine_url = f"mssql+pyodbc://{user}:{password}@{host},{port}/{database}?driver={driver.replace(' ', '+')}"
    
    # No mostrar la contraseña en la URL
    masked_url = engine_url.replace(password, '*' * len(password))
    print(f"URL de conexión: {masked_url}")
    
    # Probar la conexión
    try:
        engine = create_engine(engine_url)
        print("Intentando conectar...")
        with engine.connect() as conn:
            # Usar una consulta simple para probar la conexión
            result = conn.execute(text("SELECT @@VERSION")).scalar()
            print("\n✅ CONEXIÓN EXITOSA")
            print(f"\nVersión de SQL Server: {result}")
    except Exception as e:
        print("\n❌ ERROR DE CONEXIÓN")
        print(f"\nDetalles del error: {str(e)}")
        
        # Sugerir soluciones
        print("\nPOSIBLES SOLUCIONES:")
        print("1. Verifica que SQL Server esté instalado y ejecutándose")
        print("2. Comprueba que las credenciales sean correctas")
        print("3. Asegúrate que el servidor acepte conexiones remotas")
        print("4. Revisa si hay un firewall bloqueando la conexión")
        print("5. Instala el driver ODBC mencionado en el error (si aplica)")
        print("6. En SQL Server Configuration Manager, activa 'TCP/IP' en protocolos del servidor")

def main():
    """Función principal"""
    print("\n" + "=" * 60)
    print(" HERRAMIENTA DE DIAGNÓSTICO DE CONEXIÓN A SQL SERVER")
    print("=" * 60)
    print("\nEjecutando pruebas de diagnóstico...")
    
    verificar_sistema()
    verificar_configuracion_django()
    verificar_driver_odbc()
    verificar_red()
    probar_conexion()
    
    print("\n" + "=" * 60)
    print(" DIAGNÓSTICO COMPLETADO")
    print("=" * 60)

if __name__ == "__main__":
    main()
