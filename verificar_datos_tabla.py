"""
Script para verificar si los datos fueron guardados correctamente en la base de datos SQL Server.
Este script se conectará a la base de datos y consultará los datos de una tabla específica.
"""

import pyodbc
import pandas as pd
from tabulate import tabulate
import sys
import os
import json

# Función para obtener la cadena de conexión
def get_sqlserver_connection_string():
    server = "localhost\\SQLEXPRESS"
    database = "pruebamiguel"
    trusted_connection = "yes"
    
    # Construir cadena de conexión para pyodbc
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"Trusted_Connection={trusted_connection};"
        f"TrustServerCertificate=yes;"
    )
    
    return conn_str

def verificar_tabla(nombre_tabla):
    """Verifica si una tabla existe en la base de datos"""
    try:
        # Establecer conexión
        conn_str = get_sqlserver_connection_string()
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Consulta para verificar si la tabla existe
        query_exists = f"""
        SELECT COUNT(*) 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME = '{nombre_tabla}' 
        AND TABLE_CATALOG = DB_NAME()
        """
        
        cursor.execute(query_exists)
        count = cursor.fetchone()[0]
        
        if count == 0:
            print(f"❌ La tabla '{nombre_tabla}' no existe en la base de datos.")
            return False
        else:
            print(f"✅ La tabla '{nombre_tabla}' existe en la base de datos.")
            return True
            
    except Exception as e:
        print(f"❌ Error al verificar la tabla: {str(e)}")
        return False

def obtener_estructura_tabla(nombre_tabla):
    """Obtiene la estructura de una tabla"""
    try:
        conn_str = get_sqlserver_connection_string()
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Consulta para obtener la estructura de la tabla
        query_structure = f"""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{nombre_tabla}'
        ORDER BY ORDINAL_POSITION
        """
        
        cursor.execute(query_structure)
        columns = cursor.fetchall()
        
        if columns:
            print("\n📋 Estructura de la tabla:")
            column_data = []
            for col in columns:
                col_name = col[0]
                data_type = col[1]
                length = col[2] if col[2] else 'N/A'
                column_data.append([col_name, data_type, length])
            
            print(tabulate(column_data, headers=["Columna", "Tipo", "Longitud"], tablefmt="grid"))
        
    except Exception as e:
        print(f"❌ Error al obtener la estructura de la tabla: {str(e)}")

def contar_registros(nombre_tabla):
    """Cuenta los registros en la tabla"""
    try:
        conn_str = get_sqlserver_connection_string()
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Consulta para contar los registros
        query_count = f"SELECT COUNT(*) FROM {nombre_tabla}"
        
        cursor.execute(query_count)
        count = cursor.fetchone()[0]
        
        print(f"\n📊 La tabla '{nombre_tabla}' tiene {count} registros.")
        return count
        
    except Exception as e:
        print(f"❌ Error al contar registros: {str(e)}")
        return 0

def obtener_datos(nombre_tabla, limite=10):
    """Obtiene los datos de la tabla"""
    try:
        conn_str = get_sqlserver_connection_string()
        conn = pyodbc.connect(conn_str)
        
        # Usar pandas para leer los datos
        query = f"SELECT TOP {limite} * FROM {nombre_tabla}"
        df = pd.read_sql(query, conn)
        
        if not df.empty:
            print(f"\n📝 Mostrando {min(limite, len(df))} registros de '{nombre_tabla}':")
            print(tabulate(df, headers="keys", tablefmt="grid", showindex=False))
            return True
        else:
            print(f"⚠️ No hay datos en la tabla '{nombre_tabla}'")
            return False
            
    except Exception as e:
        print(f"❌ Error al obtener datos: {str(e)}")
        return False

def main():
    # Si se proporciona un nombre de tabla como argumento, usarlo
    if len(sys.argv) > 1:
        tabla = sys.argv[1]
    else:
        tabla = input("Ingrese el nombre de la tabla a verificar (por defecto 'personas1'): ").strip() or "personas1"
    
    print(f"\n🔍 Verificando la tabla '{tabla}'...")
    
    # Verificar si la tabla existe
    if verificar_tabla(tabla):
        # Obtener estructura
        obtener_estructura_tabla(tabla)
        
        # Contar registros
        num_registros = contar_registros(tabla)
        
        # Mostrar datos solo si hay registros
        if num_registros > 0:
            obtener_datos(tabla)
        
        print("\n✅ Verificación completada.")
    
if __name__ == "__main__":
    main()
