import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from .models import ArchivoDetectado, CarpetaCompartida

def detectar_archivos_en_carpeta(carpeta):
    """Detecta automáticamente todos los archivos soportados en una carpeta"""
    archivos_encontrados = []
    
    try:
        ruta_carpeta = Path(carpeta.ruta)
        if not ruta_carpeta.exists():
            return []
        
        # Extensiones soportadas
        extensiones_soportadas = ['.xlsx', '.xls', '.csv', '.txt']
        
        # Buscar todos los archivos en la carpeta
        for archivo in ruta_carpeta.iterdir():
            if archivo.is_file() and archivo.suffix.lower() in extensiones_soportadas:
                
                # Crear o actualizar registro del archivo
                archivo_obj, created = ArchivoDetectado.objects.get_or_create(
                    ruta_completa=str(archivo),
                    defaults={
                        'nombre': archivo.name,
                        'carpeta': carpeta,
                        'tamaño': archivo.stat().st_size,
                        'fecha_modificacion': datetime.fromtimestamp(archivo.stat().st_mtime),
                        'tipo': detectar_tipo_archivo(archivo.suffix)
                    }
                )
                
                # Si el archivo ya existía, actualizar fecha de modificación
                if not created:
                    nueva_fecha_mod = datetime.fromtimestamp(archivo.stat().st_mtime)
                    if archivo_obj.fecha_modificacion != nueva_fecha_mod:
                        archivo_obj.fecha_modificacion = nueva_fecha_mod
                        archivo_obj.tamaño = archivo.stat().st_size
                        archivo_obj.save()
                
                archivos_encontrados.append(archivo_obj)
        
        return archivos_encontrados
        
    except Exception as e:
        print(f"Error detectando archivos: {e}")
        return []

def detectar_tipo_archivo(extension):
    """Detecta el tipo de archivo basado en la extensión"""
    extension = extension.lower()
    if extension in ['.xlsx', '.xls']:
        return 'excel'
    elif extension == '.csv':
        return 'csv'
    elif extension == '.txt':
        return 'txt'
    return 'otro'

def leer_hojas_excel(ruta_archivo):
    """Lee las hojas disponibles en un archivo Excel"""
    try:
        xl_file = pd.ExcelFile(ruta_archivo)
        return xl_file.sheet_names
    except Exception as e:
        print(f"Error leyendo hojas Excel: {e}")
        return []

def procesar_archivo(archivo_detectado, hoja_seleccionada=None):
    """Procesa cualquier archivo soportado y devuelve DataFrame e información"""
    try:
        ruta = archivo_detectado.ruta_completa
        
        if not os.path.exists(ruta):
            raise FileNotFoundError(f"Archivo no encontrado: {ruta}")
        
        # Procesar según el tipo
        if archivo_detectado.tipo == 'excel':
            if hoja_seleccionada:
                df = pd.read_excel(ruta, sheet_name=hoja_seleccionada)
            else:
                # Leer la primera hoja por defecto
                df = pd.read_excel(ruta, sheet_name=0)
                
        elif archivo_detectado.tipo == 'csv':
            # Detectar separador automáticamente
            separadores = [',', ';', '\t', '|']
            df = None
            
            for sep in separadores:
                try:
                    df_temp = pd.read_csv(ruta, sep=sep, nrows=5)
                    if len(df_temp.columns) > 1:
                        df = pd.read_csv(ruta, sep=sep)
                        break
                except:
                    continue
                    
            if df is None:
                df = pd.read_csv(ruta)
                
        elif archivo_detectado.tipo == 'txt':
            # Intentar como CSV primero, luego como texto plano
            try:
                df = pd.read_csv(ruta, sep='\t')
            except:
                try:
                    df = pd.read_csv(ruta)
                except:
                    # Leer como texto plano
                    with open(ruta, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[:1000]
                    df = pd.DataFrame({'contenido': [line.strip() for line in lines]})
        else:
            raise ValueError(f"Tipo de archivo no soportado: {archivo_detectado.tipo}")
        
        # Limpiar datos
        df = df.dropna(how='all')  # Eliminar filas completamente vacías
        df = df.reset_index(drop=True)
        
        # Información del procesamiento
        info_procesamiento = {
            'archivo': archivo_detectado.nombre,
            'tipo': archivo_detectado.tipo,
            'procesado_en': datetime.now(),
            'filas_procesadas': len(df),
            'columnas_detectadas': len(df.columns),
            'hojas_disponibles': leer_hojas_excel(ruta) if archivo_detectado.tipo == 'excel' else []
        }
        
        return df, info_procesamiento
        
    except Exception as e:
        print(f"Error procesando archivo: {e}")
        raise e