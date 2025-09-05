#!/usr/bin/env python
"""
Prueba rápida de la conexión a SQL Server
"""

import os
import sys
import django
from django.conf import settings

# Configurar Django
sys.path.append('c:\\Users\\migue\\OneDrive\\Escritorio\\proyecto empresa\\DataFrame4')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cargador.settings')
django.setup()

from sqlalchemy import create_engine, text

def test_sqlserver_connection():
    """Probar la conexión a SQL Server usando las credenciales de Django"""
    
    try:
        # Obtener credenciales desde settings.py
        db_config = settings.DATABASES['default']
        
        host = db_config.get('HOST', 'localhost')
        port = db_config.get('PORT', '') or '1433'
        user = db_config.get('USER', '')
        password = db_config.get('PASSWORD', '')
        database = db_config.get('NAME', '')
        
        print(f"Probando conexión a SQL Server:")
        print(f"Host: {host}")
        print(f"Puerto: {port}")
        print(f"Base de datos: {database}")
        print(f"Usuario: {user}")
        
        # Crear engine_url para SQL Server
        engine_url = f"mssql+pyodbc://{user}:{password}@{host},{port}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
        print(f"Engine URL: {engine_url}")
        
        # Probar la conexión
        engine = create_engine(engine_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            print(f"✅ Conexión exitosa! Resultado de prueba: {test_value}")
            
            # Probar listar tablas
            query = """
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE' 
            AND TABLE_CATALOG = DB_NAME()
            """
            result = conn.execute(text(query))
            tables = [row[0] for row in result.fetchall()]
            print(f"📊 Tablas encontradas ({len(tables)}): {tables[:5]}...")  # Mostrar solo las primeras 5
            
        return True, engine_url
        
    except Exception as e:
        print(f"❌ Error de conexión: {str(e)}")
        return False, None

if __name__ == "__main__":
    success, engine_url = test_sqlserver_connection()
    if success:
        print("\n🎉 La migración de MySQL a SQL Server está lista!")
        print(f"Engine URL para usar: {engine_url}")
    else:
        print("\n💥 Hay problemas con la conexión a SQL Server")
