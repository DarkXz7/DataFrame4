"""
Script para verificar si los datos de personas1.sql fueron cargados correctamente
y si se registró la operación en ProcessAutomation y SqlFileUpload
"""
import os
import sys
import django
import pandas as pd
import json
from sqlalchemy import create_engine, text
from datetime import datetime

# Configurar el entorno de Django
sys.path.append('c:/Users/migue/OneDrive/Escritorio/proyecto empresa/DataFrame4')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cargador.settings')
django.setup()

# Importar modelos
from archivos.db_models import ProcessAutomation, SqlFileUpload

def verificar_datos():
    # Obtener conexión desde settings de Django
    from django.conf import settings
    
    db_settings = settings.DATABASES['default']
    engine_url = f"mssql+pyodbc://{db_settings['HOST']}:{db_settings['PORT']}/{db_settings['NAME']}?driver={db_settings['OPTIONS']['driver'].replace(' ', '+')}&TrustServerCertificate=yes&Trusted_Connection=yes"
    
    engine = create_engine(engine_url)
    
    print("=== VERIFICACIÓN DE DATOS ===\n")
      # 1. Verificar si la tabla personas1 existiría (según análisis del script)
    print("NOTA: Ya no se crea físicamente la tabla personas1, solo se registra el archivo.")
    print("Analizando información registrada en SqlFileUpload...")
    
    try:
        # Verificar si existen registros que mencionan la tabla personas1
        uploads_with_tabla = SqlFileUpload.objects.filter(tablas_creadas__contains='personas1').order_by('-fecha_subida')
        
        if not uploads_with_tabla:
            print("❌ No se encontraron registros que mencionen la tabla 'personas1'.")
        else:
            print(f"✅ Se encontraron {uploads_with_tabla.count()} registros que mencionan la tabla 'personas1'.")
            
            ultimo = uploads_with_tabla.first()
            print(f"📊 Última subida: {ultimo.nombre_archivo} ({ultimo.fecha_subida})")
            
            # Mostrar información sobre las sentencias SQL
            print(f"📝 Sentencias totales: {ultimo.sentencias_total}")
            
            # Mostrar tabla de análisis
            if ultimo.tablas_creadas:
                try:
                    tablas = json.loads(ultimo.tablas_creadas)
                    print("\n--- Tablas mencionadas en el script SQL ---")
                    for i, tabla in enumerate(tablas, 1):
                        print(f"{i}. {tabla}")
                    print("----------------------------------------")
                except:
                    print("❌ Error al procesar la información de tablas creadas")
    
    except Exception as e:
        print(f"❌ Error al verificar la información sobre personas1: {str(e)}")
      # 2. Verificar registros en SqlFileUpload
    try:
        uploads = SqlFileUpload.objects.filter(nombre_archivo__contains='personas1').order_by('-fecha_subida')
        
        if not uploads:
            print("\n❌ No se encontraron registros en SqlFileUpload para el archivo personas1.sql")
        else:
            print(f"\n✅ Se encontraron {uploads.count()} registros en SqlFileUpload para personas1.sql")
            
            ultimo = uploads.first()
            print("\n--- Último registro en SqlFileUpload ---")
            print(f"ID: {ultimo.id}")
            print(f"Nombre archivo: {ultimo.nombre_archivo}")
            print(f"Tamaño: {ultimo.tamanio_bytes:,} bytes")
            print(f"Fecha subida: {ultimo.fecha_subida}")
            print(f"Estado: {ultimo.estado}")
            print(f"Sentencias totales: {ultimo.sentencias_total}")
            print(f"Tipo de registro: {'Solo análisis - No ejecutado' if ultimo.estado == 'Registrado' else 'Ejecución SQL'}")
            
            # Mostrar tablas que se analizaron (sin crearlas)
            if ultimo.tablas_creadas:
                try:
                    tablas = json.loads(ultimo.tablas_creadas)
                    print(f"Tablas analizadas: {', '.join(tablas)}")
                except:
                    print("Error al procesar información de tablas")
                    
            # Mostrar errores si existen
            if ultimo.errores:
                try:
                    errores_data = json.loads(ultimo.errores)
                    print(f"⚠️ Errores: {errores_data.get('error', 'Error desconocido')}")
                except:
                    print("⚠️ Se registraron errores, pero no se pueden analizar")
            
            print("----------------------------------------")
    
    except Exception as e:
        print(f"❌ Error al verificar SqlFileUpload: {str(e)}")
      # 3. Verificar registros en ProcessAutomation
    try:
        procesos = ProcessAutomation.objects.filter(nombre__contains='personas1').order_by('-fecha_ejecucion')
        
        if not procesos:
            print("\n❌ No se encontraron registros en ProcessAutomation para el archivo personas1.sql")
        else:
            print(f"\n✅ Se encontraron {procesos.count()} registros en ProcessAutomation para personas1.sql")
            
            ultimo = procesos.first()
            print("\n--- Último registro en ProcessAutomation ---")
            print(f"ID: {ultimo.id}")
            print(f"Nombre: {ultimo.nombre}")
            print(f"Tipo proceso: {ultimo.tipo_proceso}")
            print(f"Fecha ejecución: {ultimo.fecha_ejecucion}")
            print(f"Estado: {ultimo.estado}")
            print(f"Tiempo ejecución: {ultimo.tiempo_ejecucion} segundos")
            
            # Mostrar parámetros
            if ultimo.parametros:
                try:
                    parametros = json.loads(ultimo.parametros)
                    print("\nParámetros:")
                    for key, value in parametros.items():
                        print(f"  - {key}: {value}")
                except:
                    print("Error al procesar parámetros")
            
            # Mostrar resultado
            if ultimo.resultado:
                try:
                    resultado = json.loads(ultimo.resultado)
                    print("\nResultado:")
                    for key, value in resultado.items():
                        if isinstance(value, list) and len(value) > 5:
                            print(f"  - {key}: {', '.join(value[:5])}... (y {len(value)-5} más)")
                        else:
                            print(f"  - {key}: {value}")
                except:
                    print("Error al procesar resultado")
            
            # Mostrar error si existe
            if ultimo.error_mensaje:
                print(f"\n⚠️ Error: {ultimo.error_mensaje}")
            
            print("----------------------------------------")
    
    except Exception as e:
        print(f"❌ Error al verificar ProcessAutomation: {str(e)}")

if __name__ == "__main__":
    verificar_datos()
