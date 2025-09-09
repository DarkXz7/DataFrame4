"""
Script para simular la subida del archivo personas1.sql
Este script replica el comportamiento de la vista 'subir_sql' en views.py
cuando se sube un archivo desde http://127.0.0.1:8000/seleccionar-datos/
"""
import os
import sys
import django
import time
import json
import tempfile
import traceback
from datetime import datetime

# Configurar el entorno de Django
sys.path.append('c:/Users/migue/OneDrive/Escritorio/proyecto empresa/DataFrame4')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cargador.settings')
django.setup()

# Importar modelos y utilidades
from django.utils import timezone
from sqlalchemy import create_engine, text
from archivos.db_models import ProcessAutomation, SqlFileUpload

# Ruta al archivo SQL de prueba
SQL_FILE_PATH = 'C:\\Users\\migue\\Downloads\\personas1.sql'

def simular_subida_sql():
    print("=== SIMULANDO SUBIDA DE ARCHIVO SQL ===\n")
    
    # Verificar que el archivo existe
    if not os.path.exists(SQL_FILE_PATH):
        print(f"❌ El archivo {SQL_FILE_PATH} no existe.")
        return
    
    # Obtener información del archivo
    nombre_archivo = os.path.basename(SQL_FILE_PATH)
    tamanio_bytes = os.path.getsize(SQL_FILE_PATH)
    
    # Validar el archivo
    if not nombre_archivo.lower().endswith('.sql'):
        print(f"❌ El archivo {nombre_archivo} no es un archivo SQL válido.")
        return
    
    # Leer contenido del archivo
    with open(SQL_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        sql_texto_original = f.read()
    
    # Validar contenido del archivo
    if not sql_texto_original.strip():
        print(f"❌ El archivo {nombre_archivo} está vacío.")
        return
    
    print(f"📄 Archivo: {nombre_archivo}")
    print(f"📏 Tamaño: {tamanio_bytes} bytes")
    print(f"🔄 Procesando...")
    
    # Registrar tiempo de inicio
    tiempo_inicio = time.time()
    
    # Crear un archivo temporal (como lo hace la vista)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.sql', mode='w', encoding='utf-8') as tmp:
        tmp.write(sql_texto_original)
        ruta_temporal = tmp.name
    
    # Obtener conexión a SQL Server desde settings de Django
    from archivos.sqlserver_utils import get_sqlserver_connection_string
    
    engine_url = get_sqlserver_connection_string()
    
    try:
        # Analizar el script SQL para extraer información sin ejecutarlo
        # Dividir el script en sentencias individuales
        sentencias = [s.strip() for s in sql_texto_original.split(';') if s.strip()]
        total_sentencias = len(sentencias)
        
        # Analizar las sentencias para encontrar tablas que se crearían (sin ejecutarlas)
        import re
        tabla_pattern = re.compile(r'create\s+table\s+(?:if\s+not\s+exists\s+)?[`\[]?(\w+)[`\]]?', re.IGNORECASE)
        posibles_tablas = []
        
        for stmt in sentencias:
            match = tabla_pattern.search(stmt)
            if match:
                posibles_tablas.append(match.group(1))
        
        # Eliminar duplicados
        posibles_tablas = list(dict.fromkeys(posibles_tablas))
        
        # 1. Crear registro en SqlFileUpload
        sql_upload = SqlFileUpload(
            nombre_archivo=nombre_archivo,
            tamanio_bytes=tamanio_bytes,
            fecha_subida=timezone.now(),
            usuario='script_automatico',
            sentencias_total=total_sentencias,
            sentencias_exito=0,  # Se actualizará después si se ejecutan las sentencias
            conversion_mysql=('`' in sql_texto_original or 'ENGINE=' in sql_texto_original),
            estado='Registrado',  # Nuevo estado: solo registrado, no ejecutado
            ruta_temporal=ruta_temporal
        )
        
        # Si se detectaron posibles tablas, registrarlas
        if posibles_tablas:
            sql_upload.tablas_creadas = json.dumps(posibles_tablas)
        
        sql_upload.save()
        
        print(f"✅ Creado registro en SqlFileUpload (ID: {sql_upload.id})")
        
        # 2. Crear registro en ProcessAutomation
        process_record = ProcessAutomation(
            nombre=f"Registro SQL: {nombre_archivo}",
            tipo_proceso="Registro SQL",
            fecha_ejecucion=timezone.now(),
            estado="Completado",
            tiempo_ejecucion=int(time.time() - tiempo_inicio),
            usuario='script_automatico',
            parametros=json.dumps({
                "nombre_archivo": nombre_archivo,
                "tamanio_bytes": tamanio_bytes,
                "conversion_requerida": bool('`' in sql_texto_original or 'ENGINE=' in sql_texto_original),
                "sentencias_detectadas": total_sentencias,
                "posibles_tablas": posibles_tablas
            }),
            filas_afectadas=0,  # No hay filas afectadas ya que no ejecutamos el script
            resultado=json.dumps({
                "sentencias_detectadas": total_sentencias,
                "posibles_tablas": posibles_tablas,
                "estado": "Archivo SQL registrado correctamente"
            })
        )
        process_record.save()
        print(f"✅ Creado registro en ProcessAutomation (ID: {process_record.id})")
        print(f"\n✅ Archivo SQL registrado exitosamente")
        
        # Información detallada del análisis
        print(f"\n--- Análisis del archivo SQL ---")
        print(f"Sentencias detectadas: {total_sentencias}")
        print(f"Posibles tablas a crear: {', '.join(posibles_tablas) if posibles_tablas else 'Ninguna detectada'}")
        print(f"Conversión MySQL necesaria: {'Sí' if ('`' in sql_texto_original or 'ENGINE=' in sql_texto_original) else 'No'}")
        print("--------------------------------")
    
    except Exception as e:
        error_detalle = traceback.format_exc()
        
        # Actualizar registros con información del error
        sql_upload = SqlFileUpload(
            nombre_archivo=nombre_archivo,
            tamanio_bytes=tamanio_bytes,
            fecha_subida=timezone.now(),
            usuario='script_automatico',
            sentencias_total=0,
            sentencias_exito=0,
            conversion_mysql=False,
            estado='Error',
            ruta_temporal=ruta_temporal,            errores=json.dumps({
                'error': str(e),
                'detalle': error_detalle[:1000]  # Limitamos para no guardar trazas enormes
            })
        )
        sql_upload.save()
        
        process_record = ProcessAutomation(
            nombre=f"Registro SQL (Error): {nombre_archivo}",
            tipo_proceso="Registro SQL",
            fecha_ejecucion=timezone.now(),
            estado="Error",
            tiempo_ejecucion=int(time.time() - tiempo_inicio),
            usuario='script_automatico',
            parametros=json.dumps({
                "nombre_archivo": nombre_archivo,
                "tamanio_bytes": tamanio_bytes
            }),
            error_mensaje=f"Error inesperado: {str(e)}",            resultado=json.dumps({
                'error': str(e),
                'tipo_error': e.__class__.__name__
            })
        )
        process_record.save()
        print(f"\n❌ Error inesperado durante el proceso: {str(e)}")
    
    finally:
        # Eliminar archivo temporal
        try:
            if os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)
                print(f"🗑️  Archivo temporal eliminado: {ruta_temporal}")
        except Exception as e:
            print(f"⚠️  No se pudo eliminar el archivo temporal: {str(e)}")
    
    tiempo_ejecucion = int(time.time() - tiempo_inicio)
    print("\n=== PROCESO COMPLETADO ===")
    print(f"⏱️  Tiempo total: {tiempo_ejecucion} segundos")
    print("Ejecuta verificar_personas1.py para ver los detalles completos")

if __name__ == "__main__":
    simular_subida_sql()
