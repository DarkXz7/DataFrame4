"""
Script para crear la base de datos y usuario necesarios en SQL Server
Este script utiliza autenticación de Windows para crear la base de datos
y un usuario SQL Server con los permisos necesarios.
"""
import pyodbc
import sys

def print_header(titulo):
    print("\n" + "=" * 60)
    print(f" {titulo}")
    print("=" * 60)

def ejecutar_script():
    print_header("CONFIGURACIÓN DE BASE DE DATOS SQL SERVER")
    
    try:
        # Conectar con autenticación Windows
        server = "localhost\\SQLEXPRESS"  # Instancia SQL Express
        conn_string = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};Trusted_Connection=yes"
        
        print("Conectando a SQL Server con autenticación de Windows...")
        conn = pyodbc.connect(conn_string)
        cursor = conn.cursor()
        
        # Verificar conexión
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        print(f"Versión de SQL Server: {version[:50]}...\n")
        
        # Verificar si existe la base de datos
        cursor.execute("SELECT name FROM sys.databases WHERE name = 'pruebamiguel'")
        if cursor.fetchone():
            print("✅ Base de datos 'pruebamiguel' ya existe")
            
            # Usar la base de datos
            conn.autocommit = True
            cursor.execute("USE pruebamiguel")
        else:
            # Crear la base de datos
            print("Creando base de datos 'pruebamiguel'...")
            conn.autocommit = True
            cursor.execute("CREATE DATABASE pruebamiguel")
            cursor.execute("USE pruebamiguel")
            print("✅ Base de datos 'pruebamiguel' creada")
        
        # Verificar si existe el usuario/login
        cursor.execute("SELECT name FROM sys.sql_logins WHERE name = 'djangomiguel'")
        if cursor.fetchone():
            print("✅ Login 'djangomiguel' ya existe")
            
            # Actualizar la contraseña
            print("Actualizando contraseña del usuario...")
            cursor.execute("ALTER LOGIN djangomiguel WITH PASSWORD = 'admin123'")
        else:
            # Crear login SQL Server
            print("Creando login 'djangomiguel'...")
            cursor.execute("CREATE LOGIN djangomiguel WITH PASSWORD = 'admin123'")
            print("✅ Login 'djangomiguel' creado")
        
        # Verificar si existe el usuario en la base de datos
        cursor.execute("SELECT name FROM sys.database_principals WHERE name = 'djangomiguel'")
        if cursor.fetchone():
            print("✅ Usuario de base de datos 'djangomiguel' ya existe")
        else:
            # Crear usuario de base de datos
            print("Creando usuario de base de datos...")
            cursor.execute("CREATE USER djangomiguel FOR LOGIN djangomiguel")
            print("✅ Usuario de base de datos 'djangomiguel' creado")
        
        # Asignar permisos
        print("Asignando permisos db_owner...")
        cursor.execute("ALTER ROLE db_owner ADD MEMBER djangomiguel")
        
        # Verificar las tablas en la base de datos
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        tables = [row.TABLE_NAME for row in cursor.fetchall()]
        
        if tables:
            print(f"\nTablas existentes en la base de datos ({len(tables)}):")
            for i, table in enumerate(tables, 1):
                print(f"  {i}. {table}")
        else:
            print("\nLa base de datos está vacía (no hay tablas)")
            print("Deberás ejecutar las migraciones de Django:")
            print("  python manage.py migrate")
        
        # Cerrar conexión
        cursor.close()
        conn.close()
        
        print_header("CONFIGURACIÓN COMPLETA")
        print("La base de datos 'pruebamiguel' y el usuario 'djangomiguel' están listos.")
        print("Para usar SQL Auth en Django, actualiza settings.py con:")
        print("""
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': 'pruebamiguel',
        'USER': 'djangomiguel',
        'PASSWORD': 'admin123',
        'HOST': 'localhost\\SQLEXPRESS',
        'PORT': '1433',
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            'TrustServerCertificate': 'yes',
        },
    }
}""")
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        print("\nPosibles soluciones:")
        print("1. Verifica que SQL Server esté ejecutándose")
        print("2. Asegúrate que estás ejecutando este script con permisos administrativos")
        print("3. Comprueba que la instancia SQL Express es correcta")
        print("4. Intenta ejecutar las consultas manualmente en SQL Server Management Studio")

if __name__ == "__main__":
    ejecutar_script()
