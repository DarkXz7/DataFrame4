"""
Script simplificado para probar conexión SQL Server
Este script prueba específicamente la conexión a la instancia SQL Express
"""
import pyodbc
import socket
import platform
import sys
import os

# Configure Django environment
sys.path.append('c:\\Users\\migue\\OneDrive\\Escritorio\\proyecto empresa\\DataFrame4')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cargador.settings')

# Print system information
print(f"Sistema: {platform.system()} {platform.version()}")
print(f"Nombre del equipo: {platform.node()}")
print(f"Python: {sys.version.split()[0]}")

# Test SQL Server connection
print("\n=== PRUEBA DE CONEXIÓN A SQL SERVER ===\n")

try:
    # List available drivers
    print("Drivers ODBC disponibles:")
    for driver in pyodbc.drivers():
        print(f"  - {driver}")
    
    # Connection parameters - trying both authentication methods
    server = 'localhost\\SQLEXPRESS'
    database = 'pruebamiguel'
    username = 'sa'  # Intento con usuario sa (administrador)
    password = 'admin123'  # Contraseña por defecto o la que hayas configurado
    
    # Try SQL authentication first
    print(f"\nConexión 1: SQL Server Authentication")
    print(f"Servidor: {server}")
    print(f"Base de datos: {database}")
    print(f"Usuario: {username}")
    
    conn_string = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
    
    try:
        print("\nIntentando conexión con autenticación SQL...")
        conn = pyodbc.connect(conn_string, timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        print(f"\n✅ CONEXIÓN EXITOSA CON SQL AUTH")
        print(f"Versión: {version[:50]}...")
        
        # Test if the user has database access
        try:
            cursor.execute("SELECT COUNT(*) FROM sys.tables")
            table_count = cursor.fetchone()[0]
            print(f"Tablas en la base de datos: {table_count}")
        except Exception as db_err:
            print(f"⚠️ El usuario puede conectarse pero no tiene permisos: {str(db_err)}")
        
        conn.close()
    except Exception as e:
        print(f"❌ Error con autenticación SQL: {str(e)}")
        
        # Try Windows Authentication
        print("\nConexión 2: Windows Authentication")
        try:
            conn_string_win = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes"
            print("\nIntentando conexión con autenticación Windows...")
            conn = pyodbc.connect(conn_string_win, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()[0]
            print(f"\n✅ CONEXIÓN EXITOSA CON WINDOWS AUTH")
            print(f"Versión: {version[:50]}...")
            conn.close()
        except Exception as win_err:
            print(f"❌ Error con autenticación Windows: {str(win_err)}")
    
except Exception as e:
    print(f"❌ ERROR GENERAL: {str(e)}")

# Check if SQL Server port is open
print("\n=== VERIFICACIÓN DE RED ===\n")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex(('127.0.0.1', 1433))
    if result == 0:
        print("✅ Puerto 1433 está abierto")
    else:
        print(f"❌ Puerto 1433 no accesible (error {result})")
        print("   Esto puede indicar que SQL Server no está escuchando en este puerto")
    sock.close()
except Exception as e:
    print(f"Error verificando puerto: {str(e)}")

print("\n=== RECOMENDACIONES ===\n")
print("1. Si no funciona la conexión, verifica:")
print("   - Que SQL Server esté ejecutándose")
print("   - Que exista la base de datos 'pruebamiguel'")
print("   - Que exista el usuario y tenga permisos")
print("2. Para crear usuario y base de datos, ejecuta en SQL Server Management Studio:")
print("   CREATE DATABASE pruebamiguel;")
print("   USE pruebamiguel;")
print("   CREATE LOGIN djangomiguel WITH PASSWORD='admin123';")
print("   CREATE USER djangomiguel FOR LOGIN djangomiguel;")
print("   ALTER ROLE db_owner ADD MEMBER djangomiguel;")
