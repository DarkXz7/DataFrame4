"""
Script de prueba para verificar la conexión de Django a SQL Server
y listar las tablas creadas
"""
import os
import sys
import django
from django.db import connection

# Configurar Django
sys.path.append('c:\\Users\\migue\\OneDrive\\Escritorio\\proyecto empresa\\DataFrame4')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cargador.settings')
django.setup()

def print_header(titulo):
    print("\n" + "=" * 60)
    print(f" {titulo}")
    print("=" * 60)

def verificar_conexion():
    print_header("VERIFICACIÓN DE CONEXIÓN DJANGO A SQL SERVER")
    
    try:
        # Obtener cursor
        with connection.cursor() as cursor:
            # Verificar conexión con una consulta simple
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()[0]
            print(f"✅ Conexión exitosa a SQL Server")
            print(f"Versión: {version[:100]}...\n")
            
            # Obtener lista de tablas
            cursor.execute("""
                SELECT 
                    t.TABLE_SCHEMA + '.' + t.TABLE_NAME AS tabla,
                    COUNT(c.COLUMN_NAME) AS columnas
                FROM 
                    INFORMATION_SCHEMA.TABLES t
                JOIN 
                    INFORMATION_SCHEMA.COLUMNS c 
                    ON t.TABLE_NAME = c.TABLE_NAME AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
                WHERE 
                    t.TABLE_TYPE = 'BASE TABLE'
                GROUP BY 
                    t.TABLE_SCHEMA, t.TABLE_NAME
                ORDER BY 
                    t.TABLE_SCHEMA, t.TABLE_NAME
            """)
            
            tables = cursor.fetchall()
            
            print(f"Tablas en la base de datos ({len(tables)}):")
            for i, (table, cols) in enumerate(tables, 1):
                print(f"  {i}. {table} ({cols} columnas)")
        
        # Verificar modelos de Django
        from django.apps import apps
        
        print("\nModelos de Django configurados:")
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                print(f"  - {model._meta.app_label}.{model._meta.object_name}")
        
        print("\n✅ ¡La conexión a SQL Server desde Django funciona correctamente!")
        print("Puedes seguir trabajando con tu aplicación normalmente.")
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        
if __name__ == "__main__":
    verificar_conexion()
