from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods
from datetime import datetime
from pathlib import Path
import pandas as pd
import os
import re,uuid
import json
import humanize
import base64

from io import BytesIO, StringIO
from .forms import SubirArchivoForm, CarpetaCompartidaForm
from .models import *
from .utils import detectar_archivos_en_carpeta, leer_hojas_excel, procesar_archivo
from django.views.decorators.csrf import csrf_exempt 
from django import forms
from sqlalchemy import create_engine, text
from .forms import SQLUploadForm
from django import template
from sqlalchemy import text
from django.conf import settings
from django.views.decorators.http import require_GET
import traceback
from django.utils import timezone
import traceback



register = template.Library()
# ...existing code... (mantener todas las importaciones y otras funciones)

@register.filter
def dict_get(d, key):
    return d.get(key, [])

def seleccionar_archivos_para_subir(request, carpeta_id):
    """Permite seleccionar archivos locales y decidir cuáles subir"""
    carpeta = get_object_or_404(CarpetaCompartida, id=carpeta_id)
    
    if request.method == 'POST':
        form = SubirArchivoForm(request.POST, request.FILES)
        
        if form.is_valid():
            archivos_subidos = form.cleaned_data['archivo']
            
            # Asegurarse de que sea una lista
            if not isinstance(archivos_subidos, list):
                archivos_subidos = [archivos_subidos]
            
            archivos_procesados = []
            
            for archivo in archivos_subidos:
                try:
                    # Procesar según tipo
                    archivo.seek(0)  
                    
                    if archivo.name.lower().endswith(('.xlsx', '.xls')):
                        # Para Excel, obtener las hojas
                        try:
                            xl_file = pd.ExcelFile(archivo)
                            hojas = xl_file.sheet_names
                            
                            # Leer primera hoja para preview
                            df = pd.read_excel(archivo, sheet_name=0)
                            tipo = 'excel'
                        except Exception as e:
                            messages.warning(request, f'Error leyendo Excel {archivo.name}: {str(e)}')
                            continue
                            
                    elif archivo.name.lower().endswith('.csv'):
                        try:
                            # Leer como CSV
                            content = archivo.read().decode('utf-8')
                            archivo.seek(0)
                            
                            # Intentar detectar separador
                            separadores = [',', ';', '\t', '|']
                            df = None
                            
                            for sep in separadores:
                                try:
                                    df = pd.read_csv(StringIO(content), sep=sep)
                                    if len(df.columns) > 1:
                                        break
                                except:
                                    continue
                            
                            if df is None:
                                df = pd.read_csv(StringIO(content))
                            
                            hojas = []
                            tipo = 'csv'
                        except Exception as e:
                            messages.warning(request, f'Error leyendo CSV {archivo.name}: {str(e)}')
                            continue
                            
                    elif archivo.name.lower().endswith('.txt'):
                        try:
                            content = archivo.read().decode('utf-8')
                            archivo.seek(0)
                            
                            # Intentar como CSV estructurado
                            separadores = ['\t', ';', '|', ',']
                            df = None
                            
                            for sep in separadores:
                                try:
                                    df = pd.read_csv(StringIO(content), sep=sep)
                                    if len(df.columns) > 1:
                                        break
                                except:
                                    continue
                            
                            if df is None:
                                # Como texto plano
                                lines = content.split('\n')[:100]  # Máximo 100 líneas para preview
                                df = pd.DataFrame({'contenido': [line.strip() for line in lines if line.strip()]})
                            
                            hojas = []
                            tipo = 'txt'
                        except Exception as e:
                            messages.warning(request, f'Error leyendo TXT {archivo.name}: {str(e)}')
                            continue
                    
                    # Limpiar datos
                    if df is not None:
                        df = df.dropna(how='all').reset_index(drop=True)
                        df = df.fillna('No Existe')
                        # Convertir archivo a base64 para sesión
                        archivo.seek(0)
                        archivo_bytes = archivo.read()
                        archivo_b64 = base64.b64encode(archivo_bytes).decode('utf-8')
                        
                        info_archivo = {
                            'nombre': archivo.name,
                            'tipo': tipo,
                            'tamaño': archivo.size,
                            'filas': len(df),
                            'columnas': len(df.columns),
                            'columnas_nombres': list(df.columns.astype(str)),
                            'hojas': hojas,
                            'preview_html': df.head(10).to_html(classes='table table-sm table-striped', table_id=f'preview-{len(archivos_procesados)}'),
                            'archivo_b64': archivo_b64
                        }
                        
                        archivos_procesados.append(info_archivo)
                    
                except Exception as e:
                    messages.error(request, f'Error procesando {archivo.name}: {str(e)}')
            
            if not archivos_procesados:
                messages.error(request, 'No se pudo procesar ningún archivo')
                return render(request, 'archivos/seleccionar_archivos.html', {
                    'form': SubirArchivoForm(),
                    'carpeta': carpeta
                })
            
            # Guardar en sesión
            request.session['archivos_para_subir'] = archivos_procesados
            request.session['carpeta_destino_id'] = carpeta_id
            
            messages.success(request, f'✅ {len(archivos_procesados)} archivo(s) procesado(s) correctamente')
            return redirect('confirmar_archivos_subir')
        
        else:
            # Mostrar errores del formulario
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    
    else:
        form = SubirArchivoForm()
    
    return render(request, 'archivos/seleccionar_archivos.html', {
        'form': form,
        'carpeta': carpeta
    })





@csrf_exempt
def subir_publico(request):
    """Vista pública para subir archivos sin autenticación"""
    # Obtener primera carpeta activa
    carpeta = CarpetaCompartida.objects.filter(activa=True).first()
    
    if not carpeta:
        return render(request, 'archivos/error_carpeta.html')
    
    if request.method == 'POST':
        form = SubirArchivoForm(request.POST, request.FILES)
        
        if form.is_valid():
            archivos_subidos = form.cleaned_data['archivo']
            
            # Asegurarse de que sea una lista
            if not isinstance(archivos_subidos, list):
                archivos_subidos = [archivos_subidos]
            
            archivos_subidos_exitosos = []
            
            for archivo in archivos_subidos:
                try:
                    # Crear nombre único con timestamp
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nombre_base, ext = os.path.splitext(archivo.name)
                    nombre_final = f"{nombre_base}_{timestamp}{ext}"
                    
                    ruta_destino = os.path.join(carpeta.ruta, nombre_final)
                    
                    # Guardar archivo
                    with open(ruta_destino, 'wb+') as destino:
                        for chunk in archivo.chunks():
                            destino.write(chunk)
                    
                    archivos_subidos_exitosos.append(nombre_final)
                    
                except Exception as e:
                    messages.error(request, f'Error con {archivo.name}: {str(e)}')
            
            if archivos_subidos_exitosos:
                return render(request, 'archivos/subida_exitosa.html', {
                    'archivos': archivos_subidos_exitosos,
                    'carpeta': carpeta.nombre
                })
    
    else:
        form = SubirArchivoForm()
    
    return render(request, 'archivos/subir_publico.html', {
        'form': form,
        'carpeta': carpeta
    })









def confirmar_archivos_subir(request):
    """Muestra preview de archivos y permite seleccionar cuáles subir y qué hojas"""
    archivos_info = request.session.get('archivos_para_subir', [])
    carpeta_id = request.session.get('carpeta_destino_id')
    
    if not archivos_info or not carpeta_id:
        messages.error(request, 'No hay archivos para procesar')
        return redirect('listar_carpetas_compartidas')
    
    carpeta = get_object_or_404(CarpetaCompartida, id=carpeta_id)
    
    if request.method == 'POST':
        archivos_seleccionados = request.POST.getlist('archivo_seleccionado')
        archivos_subidos_exitosamente = []
        
        for i, archivo_info in enumerate(archivos_info):
            archivo_key = f"archivo_{i}"
            
            if archivo_key in archivos_seleccionados:
                # Este archivo fue seleccionado para subir
                try:
                    # Decodificar archivo
                    import base64
                    archivo_bytes = base64.b64decode(archivo_info['archivo_b64'])
                    
                    # Determinar nombre final
                    nombre_base = archivo_info['nombre']
                    
                    # Si es Excel y se seleccionaron hojas específicas
                    if archivo_info['tipo'] == 'excel' and archivo_info['hojas']:
                        hojas_seleccionadas = request.POST.getlist(f'hojas_{i}')
                        
                        if hojas_seleccionadas:
                            # Crear un archivo por cada hoja seleccionada
                            for hoja in hojas_seleccionadas:
                                nombre_hoja = f"{os.path.splitext(nombre_base)[0]}_{hoja}.xlsx"
                                ruta_destino = os.path.join(carpeta.ruta, nombre_hoja)
                                
                                # Crear DataFrame de la hoja específica
                                from io import BytesIO
                                df_hoja = pd.read_excel(BytesIO(archivo_bytes), sheet_name=hoja)
                                
                                # Guardar solo esa hoja
                                df_hoja.to_excel(ruta_destino, index=False)
                                archivos_subidos_exitosamente.append(nombre_hoja)
                        else:
                            # Subir archivo completo
                            ruta_destino = os.path.join(carpeta.ruta, nombre_base)
                            with open(ruta_destino, 'wb') as f:
                                f.write(archivo_bytes)
                            archivos_subidos_exitosamente.append(nombre_base)
                    else:
                        # Subir archivo completo
                        ruta_destino = os.path.join(carpeta.ruta, nombre_base)
                        
                        # Verificar si existe y crear nombre único
                        if os.path.exists(ruta_destino):
                            nombre_base_sin_ext, ext = os.path.splitext(nombre_base)
                            contador = 1
                            while os.path.exists(ruta_destino):
                                nuevo_nombre = f"{nombre_base_sin_ext}_{contador}{ext}"
                                ruta_destino = os.path.join(carpeta.ruta, nuevo_nombre)
                                contador += 1
                            nombre_base = nuevo_nombre
                        
                        with open(ruta_destino, 'wb') as f:
                            f.write(archivo_bytes)
                        archivos_subidos_exitosamente.append(nombre_base)
                        
                except Exception as e:
                    messages.error(request, f'Error subiendo {archivo_info["nombre"]}: {str(e)}')
        
        # Limpiar sesión
        if 'archivos_para_subir' in request.session:
            del request.session['archivos_para_subir']
        if 'carpeta_destino_id' in request.session:
            del request.session['carpeta_destino_id']
        
        if archivos_subidos_exitosamente:
            messages.success(request, f'✅ {len(archivos_subidos_exitosamente)} archivo(s) subido(s) exitosamente: {", ".join(archivos_subidos_exitosamente)}')
        
        return redirect('listar_archivos', carpeta_id=carpeta_id)
    
    return render(request, 'archivos/confirmar_subida.html', {
        'archivos': archivos_info,
        'carpeta': carpeta
    })



def subir_archivo_a_carpeta(request, carpeta_id):
    """Subir archivo a carpeta compartida específica"""
    carpeta = get_object_or_404(CarpetaCompartida, id=carpeta_id)
    
    if request.method == 'POST':
        form = SubirArchivoForm(request.POST, request.FILES)
        if form.is_valid():
            archivo_subido = request.FILES['archivo']
            
            try:
                # Verificar que la carpeta es accesible y se puede escribir
                if not os.path.exists(carpeta.ruta):
                    messages.error(request, f'La carpeta {carpeta.ruta} no existe')
                    return redirect('listar_archivos', carpeta_id=carpeta_id)
                
                # Crear ruta destino
                ruta_destino = os.path.join(carpeta.ruta, archivo_subido.name)
                
                # Verificar si el archivo ya existe
                if os.path.exists(ruta_destino):
                    # Crear nombre único agregando número
                    nombre_base, extension = os.path.splitext(archivo_subido.name)
                    contador = 1
                    while os.path.exists(ruta_destino):
                        nuevo_nombre = f"{nombre_base}_{contador}{extension}"
                        ruta_destino = os.path.join(carpeta.ruta, nuevo_nombre)
                        contador += 1
                
                # Guardar archivo
                with open(ruta_destino, 'wb+') as destino:
                    for chunk in archivo_subido.chunks():
                        destino.write(chunk)
                
                messages.success(request, f'✅ Archivo "{os.path.basename(ruta_destino)}" subido exitosamente a {carpeta.nombre}')
                return redirect('listar_archivos', carpeta_id=carpeta_id)
                
            except PermissionError:
                messages.error(request, 'Sin permisos para escribir en la carpeta. Contacta al administrador.')
                return redirect('listar_archivos', carpeta_id=carpeta_id)
            except Exception as e:
                messages.error(request, f'Error al subir archivo: {str(e)}')
                return redirect('listar_archivos', carpeta_id=carpeta_id)
    else:
        form = SubirArchivoForm()
    
    context = {
        'form': form,
        'carpeta': carpeta,
    }
    return render(request, 'archivos/subir_archivo.html', context)






# Vista principal - Página de inicio con opciones
def index(request):
    """
    Vista principal que permite elegir entre subir archivo local o acceder a carpetas compartidas.
    Además, limpia la sesión para evitar que queden datos o archivos previos cargados.
    """

    # Limpiar claves de sesión relacionadas con la conexión y archivos
    for key in [
        'engine_url',
        'tablas',
        'tablas_seleccionadas',
        'columnas',
        'columnas_elegidas',
        'archivo_temporal',
        'archivo_datos',
        'archivos_para_subir',
        'carpeta_destino_id',
    ]:
        if key in request.session:
            del request.session[key]

    # Obtener carpetas activas
    carpetas_activas = CarpetaCompartida.objects.filter(activa=True)

    # Contar carpetas compartidas disponibles
    carpetas_disponibles = CarpetaCompartida.objects.filter(activa=True).count()

    # Contar archivos recientes subidos
    archivos_recientes = ArchivoCargado.objects.all().order_by('-fecha_carga')[:5]

    context = {
        'carpetas_disponibles': carpetas_disponibles,
        'archivos_recientes': archivos_recientes,
        'carpetas_activas': carpetas_activas
    }

    return render(request, 'archivos/index.html', context)



# Vista para elegir método de trabajo
def elegir_metodo(request):
    """Vista para que el usuario elija entre archivo local o carpeta compartida"""
    return render(request, 'archivos/elegir_metodo.html')

# ========== SECCIÓN: ARCHIVOS LOCALES ==========

def subir_archivo_local(request):
    """Vista para subir archivos locales"""
    if request.method == 'POST':
        form = SubirArchivoForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            nombre = archivo.name

            # Detectar tipo y procesar
            try:
                if nombre.lower().endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(archivo)
                    tipo = "Excel"
                elif nombre.lower().endswith('.csv'):
                    df = pd.read_csv(archivo)
                    tipo = "CSV"
                elif nombre.lower().endswith('.txt'):
                    # Intentar leer como CSV con diferentes separadores
                    archivo.seek(0)  # Volver al inicio del archivo
                    content = archivo.read().decode('utf-8')
                    
                    # Detectar separador
                    separadores = ['\t', ';', '|', ',']
                    df = None
                    
                    for sep in separadores:
                        try:
                            from io import StringIO
                            df = pd.read_csv(StringIO(content), sep=sep)
                            if len(df.columns) > 1:
                                break
                        except:
                            continue
                    
                    if df is None or len(df.columns) == 1:
                        # Leer como texto plano
                        lines = content.split('\n')[:100]
                        df = pd.DataFrame({'contenido': lines})
                    
                    tipo = "TXT"
                else:
                    messages.error(request, "Formato no soportado. Solo se permiten archivos .xlsx, .xls, .csv y .txt")
                    return render(request, "archivos/subir_local.html", {"form": form})

                # Limpiar datos
                if df is not None and not df.empty:
                    df = df.dropna(how='all')  # Eliminar filas vacías
                    df = df.reset_index(drop=True)
                    df = df.fillna('No Existe')
                    
                    if df.empty:
                        messages.error(request, "El archivo no contiene datos válidos")
                        return render(request, "archivos/subir_local.html", {"form": form})

                # Guardar en sesión para preview
                request.session['archivo_temporal'] = {
                    'nombre': nombre,
                    'tipo': tipo,
                    'df_html': df.to_html(classes='table table-striped table-hover'),
                    'columnas': list(df.columns),
                    'filas': len(df)
                }
                
                request.session['archivo_datos'] = df.to_dict('records')

                return render(request, "archivos/preview_local.html", {
                    "nombre": nombre,
                    "tipo": tipo,
                    "df_html": df.to_html(classes='table table-striped table-hover'),
                    "filas": len(df),
                    "columnas": len(df.columns),
                    "columnas_nombres": list(df.columns)
                })

            except Exception as e:
                messages.error(request, f"Error al procesar el archivo: {str(e)}")
                return render(request, "archivos/subir_local.html", {"form": form})
        else:
            messages.error(request, "Por favor, selecciona un archivo válido")
    else:
        form = SubirArchivoForm()

    return render(request, "archivos/subir_local.html", {"form": form})

def guardar_archivo_local(request):
    """Guarda el archivo local procesado"""
    if request.method == 'POST':
        archivo_temp = request.session.get('archivo_temporal')
        archivo_datos = request.session.get('archivo_datos')
        
        if not archivo_temp or not archivo_datos:
            messages.error(request, "No hay archivo para guardar. Por favor, sube un archivo primero.")
            return redirect('subir_archivo_local')
        
        try:
            # Guardar en base de datos
            archivo_guardado = ArchivoCargado.objects.create(
                nombre=archivo_temp['nombre'],
                tipo=archivo_temp['tipo'],
                columnas=', '.join(archivo_temp['columnas']),
                filas=archivo_temp['filas']
            )
            
            
            # === Guardar archivo físico en carpeta compartida ===
            import pandas as pd
            from io import StringIO
            import os

            # Obtener carpeta compartida activa
            carpeta = CarpetaCompartida.objects.filter(ruta=r'C:\CarpetaCompartida').first()
            if not carpeta:
                messages.error(request, "No se encontró la carpeta compartida C:\\CarpetaCompartida.")
                return redirect('subir_archivo_local')

            if not os.path.exists(carpeta.ruta):
                os.makedirs(carpeta.ruta, exist_ok=True)

            ruta_destino = os.path.join(carpeta.ruta, archivo_temp['nombre'])

            # Reconstruir DataFrame y guardar según tipo de archivo
            df = pd.DataFrame(archivo_datos)
            df = df.fillna('')
            if archivo_temp['tipo'].lower() == 'excel':
                df.to_excel(ruta_destino, index=False)
            elif archivo_temp['tipo'].lower() == 'csv':
                df.to_csv(ruta_destino, index=False)
            elif archivo_temp['tipo'].lower() == 'txt':
                # Guardar como texto plano (tabulado)
                df.to_csv(ruta_destino, index=False, sep='\t')
            else:
                # Por defecto, guardar como CSV
                df.to_csv(ruta_destino, index=False)
            
            # Limpiar sesión
            del request.session['archivo_temporal']
            del request.session['archivo_datos']
            
            
            messages.success(request, f"¡Archivo '{archivo_temp['nombre']}' guardado exitosamente!")
            return render(request, "archivos/exito.html", {
                "archivo": archivo_guardado,
                "mensaje": "Archivo guardado exitosamente"
            })
            
        except Exception as e:
            messages.error(request, f"Error al guardar el archivo: {str(e)}")
            return redirect('subir_archivo_local')
    
    return redirect('subir_archivo_local')

# ========== SECCIÓN: CARPETAS COMPARTIDAS ==========

def listar_carpetas_compartidas(request):
    """Lista todas las carpetas compartidas disponibles"""
    carpetas = CarpetaCompartida.objects.filter(activa=True)
    
    # Verificar accesibilidad de cada carpeta
    for carpeta in carpetas:
        carpeta.accesible = carpeta.existe()
    
    return render(request, 'archivos/listar_carpetas.html', {
        'carpetas': carpetas
    })
    
#Gestionar carpetas compartidas 
def gestionar_carpetas(request):
    """Vista para gestionar carpetas compartidas"""
    if request.method == 'POST':
        form = CarpetaCompartidaForm(request.POST)
        if form.is_valid():
            carpeta = form.save()
            messages.success(request, f'Carpeta "{carpeta.nombre}" agregada exitosamente')
            return redirect('gestionar_carpetas')
    else:
        form = CarpetaCompartidaForm()
    
    carpetas = CarpetaCompartida.objects.all().order_by('-fecha_creacion')
    return render(request, 'archivos/gestionar_carpetas.html', {
        'form': form,
        'carpetas': carpetas
    })
    
    
def eliminar_carpeta(request, carpeta_id):
    carpeta = get_object_or_404(CarpetaCompartida, id=carpeta_id)
    if request.method == 'POST':
        carpeta.delete()
        messages.success(request, f'Carpeta "{carpeta.nombre}" eliminada correctamente.')
        return redirect('index')
    return render(request, 'archivos/confirmar_eliminar_carpeta.html', {'carpeta': carpeta})

def listar_archivos(request, carpeta_id):
    """Lista archivos en una carpeta compartida - VERSIÓN SIMPLE"""
    carpeta = get_object_or_404(CarpetaCompartida, id=carpeta_id)
    
    # Verificar si la carpeta es accesible
    carpeta_accesible = os.path.exists(carpeta.ruta) and os.path.isdir(carpeta.ruta)
    
    archivos_detectados = []
    total_archivos = 0
    tipos_archivo = {}
    
    if carpeta_accesible:
        try:
            # Buscar archivos en la carpeta
            for archivo_nombre in os.listdir(carpeta.ruta):
                archivo_path = os.path.join(carpeta.ruta, archivo_nombre)
                
                if os.path.isfile(archivo_path):
                    # Solo archivos Excel, CSV y TXT
                    if archivo_nombre.lower().endswith(('.xlsx', '.xls', '.csv', '.txt')):
                        
                        # Determinar tipo
                        if archivo_nombre.lower().endswith(('.xlsx', '.xls')):
                            tipo = 'excel'
                        elif archivo_nombre.lower().endswith('.csv'):
                            tipo = 'csv'
                        else:
                            tipo = 'txt'
                        
                        # Crear o obtener registro del archivo
                        archivo_obj, created = ArchivoDetectado.objects.get_or_create(
                            ruta_completa=archivo_path,
                            defaults={
                                'nombre': archivo_nombre,
                                'carpeta': carpeta,
                                'tipo': tipo,
                                'tamaño': os.path.getsize(archivo_path),
                                'fecha_modificacion': datetime.fromtimestamp(os.path.getmtime(archivo_path))
                            }
                        )
                        
                        archivos_detectados.append(archivo_obj)
                        tipos_archivo[tipo] = tipos_archivo.get(tipo, 0) + 1
            
            total_archivos = len(archivos_detectados)
            
        except Exception as e:
            messages.error(request, f'Error al leer la carpeta: {str(e)}')
            carpeta_accesible = False
    
    context = {
        'carpeta': carpeta,
        'archivos': archivos_detectados,
        'carpeta_accesible': carpeta_accesible,
        'total_archivos': total_archivos,
        'tipos_archivo': tipos_archivo,
    }
    
    return render(request, 'archivos/listar_archivos.html', context)

def detalle_archivo(request, archivo_id):
    """Muestra los detalles de un archivo específico"""
    archivo = get_object_or_404(ArchivoDetectado, id=archivo_id)
    
    # Información básica del archivo
    info_archivo = {
        'nombre': archivo.nombre,
        'tipo': archivo.get_tipo_display(),
        'tamaño': humanize.naturalsize(archivo.tamaño),
        'fecha_modificacion': archivo.fecha_modificacion,
        'ruta': archivo.ruta_completa
    }
    
    # Si es Excel, obtener las hojas disponibles
    hojas_disponibles = []
    if archivo.tipo == 'excel':
        try:
            hojas_disponibles = leer_hojas_excel(archivo.ruta_completa)
        except Exception as e:
            messages.error(request, f'Error al leer las hojas del archivo Excel: {str(e)}')
    
    return render(request, 'archivos/detalle_archivo.html', {
        'archivo': archivo,
        'info_archivo': info_archivo,
        'hojas_disponibles': hojas_disponibles
    })

def procesar_archivo_vista(request, archivo_id):
    """Procesa un archivo de carpeta compartida y muestra su contenido"""
    archivo = get_object_or_404(ArchivoDetectado, id=archivo_id)
    hoja_seleccionada = request.GET.get('hoja', None)
    
    try:
        # Procesar el archivo
        df, info_procesamiento = procesar_archivo(archivo, hoja_seleccionada)
        
        if df is not None:
            df = df.fillna('')
        
        if df is None or df.empty:
            messages.error(request, 'El archivo no contiene datos válidos o está vacío')
            return redirect('detalle_archivo', archivo_id=archivo_id)
        
        # Guardar información del procesamiento
        archivo_procesado = ArchivoProcesado.objects.create(
            archivo_original=archivo,
            hoja_seleccionada=hoja_seleccionada,
            filas_totales=len(df),
            columnas_totales=len(df.columns),
            columnas_nombres=', '.join(df.columns.astype(str)),
            datos_preview=df.head(100).to_json()
        )
        
        # Preparar datos para la vista
        df_html = df.head(50).to_html(classes='table table-striped table-hover', table_id='archivo-tabla')
        
        # Convertir columnas a lista para evitar usar filtros
        columnas_lista = [str(col) for col in df.columns]
        
        return render(request, 'archivos/procesar_archivo.html', {
            'archivo': archivo,
            'archivo_procesado': archivo_procesado,
            'df_html': df_html,
            'info_procesamiento': info_procesamiento,
            'hoja_seleccionada': hoja_seleccionada,
            'mostrando_filas': min(50, len(df)),
            'total_filas': len(df),
            'columnas_lista': columnas_lista,  
        })
        
    except Exception as e:
        messages.error(request, f'Error al procesar el archivo: {str(e)}')
        return redirect('detalle_archivo', archivo_id=archivo_id)

# ========== SECCIÓN: API Y UTILIDADES ==========

@require_http_methods(["GET"])
def obtener_datos_archivo(request, procesado_id):
    """API para obtener datos paginados del archivo procesado"""
    procesado = get_object_or_404(ArchivoProcesado, id=procesado_id)
    
    try:
        inicio = int(request.GET.get('inicio', 0))
        limite = int(request.GET.get('limite', 50))
        
        # Recrear DataFrame desde el archivo original
        df, _ = procesar_archivo(procesado.archivo_original, procesado.hoja_seleccionada)
        
        # Obtener el segmento solicitado
        df_segmento = df.iloc[inicio:inicio+limite]
        
        return JsonResponse({
            'success': True,
            'html': df_segmento.to_html(classes='table table-striped table-hover'),
            'inicio': inicio,
            'fin': min(inicio + limite, len(df)),
            'total': len(df)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def ver_archivos_guardados(request):
    """Vista para ver todos los archivos guardados"""
    archivos = ArchivoCargado.objects.all().order_by('-fecha_carga')
    
    paginator = Paginator(archivos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'archivos/archivos_guardados.html', {
        'page_obj': page_obj
    })

# Mantener vistas originales para compatibilidad
def subir_archivo(request):
    """Redirecciona a la nueva vista de subir archivo local"""
    return redirect('subir_archivo_local')

def guardar_archivo(request):
    """Redirecciona a la nueva vista de guardar archivo local"""
    return redirect('guardar_archivo_local')




# SECCION SUBIR A BASE DE DATOS
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from django.shortcuts import redirect









# Formularios simples para conexión con bd
class ConexionMySQLForm(forms.Form):
    host = forms.CharField(label="Host", initial="localhost")
    puerto = forms.IntegerField(label="Puerto", initial=3306)
    usuario = forms.CharField(label="Usuario")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    base = forms.CharField(label="Base de datos")

class ConexionPostgresForm(forms.Form):
    host = forms.CharField(label="Host", initial="localhost")
    puerto = forms.IntegerField(label="Puerto", initial=5432)
    usuario = forms.CharField(label="Usuario")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    base = forms.CharField(label="Base de datos")

class ConexionSQLServerForm(forms.Form):
    host = forms.CharField(label="Host", initial="localhost")
    puerto = forms.IntegerField(label="Puerto", initial=1433)
    usuario = forms.CharField(label="Usuario")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    base = forms.CharField(label="Base de datos")


def subir_desde_mysql(request):
    """
    Versión actualizada: conecta automáticamente con SQL Server usando las credenciales de settings.py
    y redirecciona a seleccionar_datos sin formulario de login
    """
    # Simplemente redirige a la función de SQL Server automática
    return subir_desde_sqlserver(request)

def limpiar_valor(valor):
    # Ejemplo: "15 días" -> 15, convertir valores a enteros si es posible
    if isinstance(valor, str) and valor.strip().endswith("días"):
        return int(valor.split()[0])
    return valor




def subir_desde_postgres(request):
    # Puedes implementar la lógica real después
    from django import forms
    class DummyForm(forms.Form):
        pass
    form = DummyForm()
    return render(request, 'archivos/subir_desde_postgres.html', {'form': form})

def subir_desde_sqlserver(request):
    """
    Conecta automáticamente a SQL Server usando las credenciales de settings.py
    Sin necesidad de formulario de login manual
    """
    from django.conf import settings
    from .sqlserver_utils import test_sqlserver_connection, get_sqlserver_connection_string
    
    try:
        # Probar conexión utilizando la utilidad
        success, message, engine = test_sqlserver_connection()
        
        if success:
            # Obtener cadena de conexión para SQLAlchemy
            engine_url = get_sqlserver_connection_string()
            
            # Guardar en sesión y redirigir
            request.session['engine_url'] = engine_url
            messages.success(request, f"Conectado exitosamente a SQL Server")
            messages.info(request, message)
            return redirect('seleccionar_datos')
        else:
            # Falló la conexión
            messages.error(request, f"Error conectando a SQL Server: {message}")
            
            # Sugerir soluciones basadas en el mensaje de error
            if "10061" in message:
                # Error de conexión rechazada
                solucion = """
                <p><strong>Error de conexión 10061</strong>: El servidor rechazó la conexión</p>
                <ul>
                    <li>Usa el script <code>configurar_sqlserver.py</code> como administrador para configurar SQL Server</li>
                    <li>En SQL Server Configuration Manager, activa TCP/IP en Protocolos</li>
                    <li>Reinicia el servicio SQL Server después de activar TCP/IP</li>
                    <li>Asegúrate que el firewall permita conexiones al puerto 1433</li>
                    <li>Verifica que estás usando el nombre de instancia correcto (SQLEXPRESS)</li>
                </ul>
                """
            elif "Login failed" in message or "inicio de sesión" in message.lower():
                # Error de autenticación
                solucion = """
                <p><strong>Error de autenticación</strong>: Credenciales incorrectas</p>
                <ul>
                    <li>Verifica que el usuario y contraseña sean correctos en settings.py</li>
                    <li>Ejecuta <code>verificar_sqlexpress.py</code> para probar autenticación</li>
                    <li>Prueba usar autenticación de Windows (Trusted_Connection=yes)</li>
                    <li>Ejecuta <code>configurar_base_datos.py</code> para crear el usuario</li>
                </ul>
                """
            else:
                # Error genérico
                solucion = """
                <p><strong>Error de conexión</strong></p>
                <ul>
                    <li>Asegúrate que SQL Server está instalado y ejecutándose</li>
                    <li>Verifica las credenciales en settings.py</li>
                    <li>Revisa los logs de SQL Server para más información</li>
                    <li>Ejecuta <code>diagnostico_sqlserver.py</code> para ayuda</li>
                </ul>
                """
            
            messages.warning(request, mark_safe(f"Soluciones posibles: {solucion}"))
            return redirect('index')
            
    except Exception as e:
        messages.error(request, f"Error general: {str(e)}")
        return redirect('index')

def conectar_sqlserver_automatico(request):
    """
    Alias para compatibilidad - redirige a subir_desde_sqlserver
    """
    return subir_desde_sqlserver(request)


# ...existing code...
def subir_sql(request):
    from .sqlserver_utils import get_sqlserver_connection_string, sqlalchemy_connection
    from .mysql_to_sqlserver import convert_mysql_to_sqlserver, execute_sqlserver_script
    from .models import ProcessAutomation, SqlFileUpload
    import logging
    import json
    import tempfile
    import os
    from datetime import datetime
    import time
    
    logger = logging.getLogger(__name__)
    
    # Limpiar errores SQL de sesiones anteriores
    if 'sql_errors' in request.session:
        del request.session['sql_errors']
    
    engine_url = request.session.get('engine_url')
    if not engine_url:
        engine_url = get_sqlserver_connection_string()
        request.session['engine_url'] = engine_url
        
    from sqlalchemy import create_engine
    engine = create_engine(engine_url)
    
    if request.method == 'POST':
        archivo_sql = request.FILES.get('archivo_sql')
        if archivo_sql:
            # Registrar tiempo de inicio para medir duración
            tiempo_inicio = time.time()
            
            # Limpiar sesión de datos anteriores
            for key in ['tablas', 'tablas_seleccionadas', 'columnas', 'columnas_elegidas']:
                if key in request.session:
                    del request.session[key]
            
            # Obtener información básica del archivo
            nombre_archivo = archivo_sql.name
            tamanio_bytes = archivo_sql.size
            
            # Leer contenido del archivo SQL
            archivo_sql.seek(0)
            sql_texto_original = archivo_sql.read().decode('utf-8', errors='ignore')
            
            # Crear un registro temporal del archivo
            with tempfile.NamedTemporaryFile(delete=False, suffix='.sql', mode='w', encoding='utf-8') as tmp:
                tmp.write(sql_texto_original)
                ruta_temporal = tmp.name
              # Crear registro inicial en SqlFileUpload
            sql_upload = SqlFileUpload(
                nombre_archivo=nombre_archivo,
                tamanio_bytes=tamanio_bytes,
                fecha_subida=timezone.now(),  # Usar timezone.now() en lugar de auto_now_add
                usuario=request.user.username if request.user.is_authenticated else 'usuario_anónimo',
                sentencias_total=0,
                sentencias_exito=0,
                conversion_mysql=('`' in sql_texto_original or 'ENGINE=' in sql_texto_original),
                estado='Procesando',
                ruta_temporal=ruta_temporal
            )
            sql_upload.save()
            
            # Crear registro de proceso en ProcessAutomation
            process_record = ProcessAutomation(
                nombre=f"Importación SQL: {nombre_archivo}",
                tipo_proceso="Importación SQL",
                fecha_ejecucion=timezone.now(),  # Usar timezone.now() en lugar de auto_now_add
                estado="En proceso",
                tiempo_ejecucion=0,
                usuario=request.user.username if request.user.is_authenticated else 'usuario_anónimo',
                parametros=json.dumps({
                    "nombre_archivo": nombre_archivo,
                    "tamanio_bytes": tamanio_bytes,
                    "conversion_requerida": bool('`' in sql_texto_original or 'ENGINE=' in sql_texto_original)
                }),
                filas_afectadas=0
            )
            process_record.save()
            
            try:
                # Convertir SQL de MySQL a formato compatible con SQL Server
                sql_texto_convertido = convert_mysql_to_sqlserver(sql_texto_original)
                
                # Guardar versión original y convertida para visualización (opcional)
                request.session['sql_original'] = sql_texto_original[:5000] if len(sql_texto_original) > 5000 else sql_texto_original
                request.session['sql_convertido'] = sql_texto_convertido[:5000] if len(sql_texto_convertido) > 5000 else sql_texto_convertido
                
                # Actualizar registro del archivo con la versión convertida
                sql_upload.version_convertida = sql_texto_convertido[:10000] if len(sql_texto_convertido) > 10000 else sql_texto_convertido
                sql_upload.save()
                
                # Ejecutar el script SQL convertido en SQL Server
                resultados = execute_sqlserver_script(engine, sql_texto_convertido)
                  # Calcular tiempo de ejecución en segundos
                tiempo_ejecucion = int(time.time() - tiempo_inicio)
                
                # Actualizar registros en ambas tablas con los resultados
                if resultados['errors']:
                    # Hubo errores en la ejecución
                    error_summary = f"{len(resultados['errors'])} de {resultados['total']} sentencias fallaron."
                    
                    # Mostrar mensaje principal de error
                    messages.error(request, f"Error al ejecutar SQL: {error_summary}")
                    
                    # Mostrar advertencias específicas si existen
                    if 'warnings' in resultados and resultados['warnings']:
                        for warning in resultados['warnings'][:3]:  # Limitar a 3 advertencias
                            messages.warning(request, warning)
                    
                    # Mostrar detalles del primer error con sugerencia si está disponible
                    first_error = resultados['errors'][0]
                    error_msg = first_error['error']
                    
                    # Incluir sugerencia si está disponible
                    if 'sugerencia' in first_error and first_error['sugerencia']:
                        error_msg += f" - Sugerencia: {first_error['sugerencia']}"
                    
                    messages.error(request, f"Detalle del error: {error_msg}")
                    
                    # Si hay múltiples errores, agregar una nota
                    if len(resultados['errors']) > 1:
                        messages.info(request, f"Hay {len(resultados['errors'])-1} errores adicionales. Revise los logs para más detalles.")
                    
                    # Registrar información detallada en logs
                    logger.error(f"Errores en ejecución SQL: {len(resultados['errors'])} de {resultados['total']} sentencias fallaron.")
                    for i, error in enumerate(resultados['errors'][:5]):  # Limitamos a los primeros 5 errores
                        logger.error(f"Error #{i+1}: {error['error']} en sentencia: {error['statement']}")
                        if 'sugerencia' in error:
                            logger.error(f"  Sugerencia: {error['sugerencia']}")
                    
                    # Guardar información de errores en la sesión para mostrar en la página
                    request.session['sql_errors'] = [
                        {
                            'error': e['error'],
                            'statement': e['statement'],
                            'sugerencia': e.get('sugerencia', '')
                        } for e in resultados['errors'][:10]  # Limitamos a 10 errores
                    ]
                    
                    # Actualizar registro de SqlFileUpload con los errores
                    sql_upload.estado = 'Error'
                    sql_upload.sentencias_total = resultados['total']
                    sql_upload.sentencias_exito = resultados['success']
                    sql_upload.errores = json.dumps([{
                        'error': e['error'],
                        'statement': e['statement'][:200],  # Limitamos la longitud
                        'tipo': e.get('tipo', 'desconocido')
                    } for e in resultados['errors'][:20]])  # Limitamos a 20 errores
                    
                    if resultados['tables_created']:
                        sql_upload.tablas_creadas = json.dumps(resultados['tables_created'])
                    
                    sql_upload.save()
                    
                    # Actualizar registro de proceso con el fallo
                    process_record.estado = 'Error'
                    process_record.tiempo_ejecucion = tiempo_ejecucion
                    process_record.filas_afectadas = resultados['success']
                    process_record.error_mensaje = f"Error en SQL: {error_summary}. {error_msg}"
                    process_record.resultado = json.dumps({
                        'sentencias_totales': resultados['total'],
                        'sentencias_exitosas': resultados['success'],
                        'errores_totales': len(resultados['errors']),
                        'tablas_afectadas': resultados['tables_created'] if 'tables_created' in resultados else []
                    })
                    process_record.save()
                    
                    return redirect('subir_sql')
                  # CASO DE ÉXITO - No hay errores
                
                # Actualizar registro en SqlFileUpload
                sql_upload.estado = 'Completado'
                sql_upload.sentencias_total = resultados['total']
                sql_upload.sentencias_exito = resultados['success']
                
                if 'tables_created' in resultados and resultados['tables_created']:
                    sql_upload.tablas_creadas = json.dumps(resultados['tables_created'])
                
                sql_upload.save()
                
                # Actualizar registro de proceso en ProcessAutomation
                process_record.estado = 'Completado'
                process_record.tiempo_ejecucion = tiempo_ejecucion
                process_record.filas_afectadas = resultados['success']
                process_record.resultado = json.dumps({
                    'sentencias_totales': resultados['total'],
                    'sentencias_exitosas': resultados['success'],
                    'tablas_afectadas': resultados['tables_created'] if 'tables_created' in resultados else []
                })
                process_record.save()
                
                # Guardar tablas creadas en la sesión
                if resultados['tables_created']:
                    request.session['created_tables'] = resultados['tables_created']
                else:
                    # Si no detectamos tablas creadas específicamente, obtener todas las tablas
                    tablas_query = """
                    SELECT TABLE_NAME 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_TYPE = 'BASE TABLE' 
                    AND TABLE_CATALOG = DB_NAME()
                    """
                    tablas = pd.read_sql(tablas_query, engine)['TABLE_NAME'].tolist()
                    request.session['created_tables'] = tablas
                
                request.session['source_type'] = 'sql'
                request.session['wizard_step'] = 2
                
                # Mensaje de éxito                messages.success(request, f"Archivo SQL importado correctamente. {resultados['success']} sentencias ejecutadas.")
                if resultados['tables_created']:
                    messages.info(request, f"Tablas creadas: {', '.join(resultados['tables_created'][:5])}" + 
                               ("... y más" if len(resultados['tables_created']) > 5 else ""))
                return redirect('seleccionar_datos')
                
            except Exception as e:
                # Calcular tiempo de ejecución hasta el error
                tiempo_ejecucion = int(time.time() - tiempo_inicio)
                
                # Registrar el error en logs
                logger.exception("Error en subir_sql")
                error_detalle = traceback.format_exc()
                
                # Actualizar SqlFileUpload con información del error
                sql_upload.estado = 'Error'
                sql_upload.errores = json.dumps({
                    'error': str(e),
                    'detalle': error_detalle[:1000]  # Limitamos para no guardar trazas enormes
                })
                sql_upload.save()
                
                # Actualizar ProcessAutomation con información del error
                process_record.estado = 'Error'
                process_record.tiempo_ejecucion = tiempo_ejecucion
                process_record.error_mensaje = f"Error inesperado: {str(e)}"
                process_record.resultado = json.dumps({
                    'error': str(e),
                    'tipo_error': e.__class__.__name__
                })
                process_record.save()
                
                # Mostrar mensaje de error al usuario
                messages.error(request, f"Error al procesar el archivo SQL: {str(e)}")
                
                # Guardar el error en la sesión para visualización
                request.session['sql_errors'] = [{
                    'error': str(e),
                    'statement': 'N/A',
                    'sugerencia': 'Revisa el formato del archivo SQL y asegúrate que sea compatible.'
                }]
                
                # Eliminar el archivo temporal si existe
                try:
                    if os.path.exists(ruta_temporal):
                        os.remove(ruta_temporal)
                except:
                    pass
                
                return redirect('subir_sql')
                
    return render(request, "archivos/subir_sql.html")









def tabla_existe(engine, tabla):
    try:
        with engine.connect() as conn:
            # Usar sintaxis SQL Server para verificar existencia de tabla
            query = """
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = ? 
            AND TABLE_CATALOG = DB_NAME()
            """
            result = conn.execute(text(query), (tabla,))
            return result.scalar() > 0
    except Exception:
        return False
    





from django.views.decorators.http import require_GET



@csrf_exempt
def preview_sql_estructura(request):
    """API para previsualizar la estructura y datos de un archivo SQL desde carpeta compartida"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'})
    
    try:
        data = json.loads(request.body)
        ruta = data.get('ruta', '').strip()
        archivo = data.get('archivo', '').strip()
        
        if not ruta or not archivo:
            return JsonResponse({'ok': False, 'error': 'Ruta y nombre de archivo requeridos'})
        
        ruta_completa = os.path.join(ruta, archivo)
        
        # Verificar que el archivo existe
        if not os.path.isfile(ruta_completa):
            return JsonResponse({'ok': False, 'error': f'No se encuentra el archivo: {ruta_completa}'})
        
        # Verificar que es un archivo SQL
        if not archivo.lower().endswith('.sql'):
            return JsonResponse({'ok': False, 'error': 'El archivo debe tener extensión .sql'})
        
        # Leer el contenido del archivo SQL
        with open(ruta_completa, 'r', encoding='utf-8', errors='ignore') as f:
            sql_content = f.read()
        
        # Buscar tablas en el script (CREATE TABLE)
        tabla_pattern = re.compile(r'create\s+table\s+(?:if\s+not\s+exists\s+)?`?([A-Za-z0-9_]+)`?(?:\s*\(|\s+as)', re.IGNORECASE)
        tablas_encontradas = tabla_pattern.findall(sql_content)
        tablas_encontradas = sorted(list(dict.fromkeys(tablas_encontradas)))  # Eliminar duplicados
        
        # Obtener engine desde sesión
        engine_url = request.session.get('engine_url')
        if not engine_url:
            return JsonResponse({'ok': False, 'error': 'No hay conexión a base de datos'})
        
        engine = create_engine(engine_url)
        
        # En lugar de usar un schema temporal, usaremos tablas temporales con prefijo
        prefix = f"__tmp_{uuid.uuid4().hex[:8]}_"
        
        resultado_tablas = []
        created_temp_tables = []
        
        try:
            # Modificar el script para usar tablas temporales con prefijo
            def _reemplazar_tabla(m):
                nombre_tabla = m.group(2)
                return f"{m.group(1)} `{prefix}{nombre_tabla}`"
            
            script_mod = re.sub(r'(?i)\b(CREATE\s+TABLE|INSERT\s+INTO)\s+`?([A-Za-z0-9_]+)`?',
                                _reemplazar_tabla, sql_content)
            
            # Ejecutar cada sentencia
            with engine.begin() as conn:
                for stmt in [s.strip() for s in script_mod.split(';') if s.strip()]:
                    try:
                        conn.execute(text(stmt))
                        # Capturar nombres de tablas creadas
                        if re.search(r'(?i)create\s+table', stmt):
                            tabla_match = re.search(r'(?i)create\s+table\s+(?:if\s+not\s+exists\s+)?`?(\w+)`?', stmt)
                            if tabla_match:
                                created_temp_tables.append(tabla_match.group(1))
                    except Exception as e:
                        print(f"Error ejecutando: {stmt[:100]}... | {str(e)}")
              # Procesar cada tabla original detectada
            for tabla in tablas_encontradas:
                temp_tabla = f"{prefix}{tabla}"
                tabla_info = {'nombre': tabla, 'columnas': [], 'columnas_info': [], 'preview': []}
                
                try:
                    # Obtener columnas usando sintaxis SQL Server
                    with engine.begin() as conn:
                        # Usar INFORMATION_SCHEMA en lugar de SHOW COLUMNS
                        query = """
                        SELECT COLUMN_NAME, DATA_TYPE 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_NAME = ? 
                        AND TABLE_CATALOG = DB_NAME()
                        ORDER BY ORDINAL_POSITION
                        """
                        result = conn.execute(text(query), (temp_tabla,))
                        columns_info = result.fetchall()
                        
                        for col_info in columns_info:
                            col_name = col_info[0]
                            col_type = col_info[1]
                            tabla_info['columnas'].append(col_name)
                            tabla_info['columnas_info'].append({
                                'nombre': col_name,
                                'tipo': col_type
                            })
                    
                    # Obtener datos de muestra (primeras 5 filas) - usar TOP en lugar de LIMIT
                    df = pd.read_sql(f"SELECT TOP 5 * FROM [{temp_tabla}]", engine)
                      # Convertir a lista para JSON
                    tabla_info['preview'] = df.values.tolist()
                    
                except Exception as e:
                    print(f"Error obteniendo datos de {tabla}: {str(e)}")
                
                resultado_tablas.append(tabla_info)
        
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f"Error al procesar el script: {str(e)}"})
        
        finally:
            # Limpiar tablas temporales
            try:
                with engine.begin() as conn:
                    for tabla in created_temp_tables:
                        try:
                            conn.execute(text(f"DROP TABLE IF EXISTS [{tabla}]"))
                        except:
                            pass
            except:
                pass
        
        # Si no se encontraron tablas con información, buscar tablas insertadas
        if not any(tabla.get('columnas') for tabla in resultado_tablas):
            insert_pattern = re.compile(r'insert\s+into\s+`?([A-Za-z0-9_]+)`?', re.IGNORECASE)
            tablas_insert = insert_pattern.findall(sql_content)
            tablas_insert = sorted(list(dict.fromkeys(tablas_insert)))  # Eliminar duplicados
            
            for tabla in tablas_insert:
                if not any(t['nombre'] == tabla for t in resultado_tablas):
                    tabla_info = {'nombre': tabla, 'columnas': [], 'preview': []}
                    resultado_tablas.append(tabla_info)
        
        # Guardar el script y las tablas encontradas en la sesión para usar después
        request.session['sql_script_preview'] = sql_content
        request.session['tablas_detectadas'] = [t['nombre'] for t in resultado_tablas]
        
        return JsonResponse({
            'ok': True,
            'tablas': resultado_tablas,
            'archivo': archivo,
            'ruta': ruta
        })
    
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})



@csrf_exempt
def preview_tabla(request):
    """
    Devuelve (JSON) columnas y primeras filas de una tabla/hoja seleccionada (paso 2 dinámico).
    Parámetros:
      ?tabla=nombre
    Usa la sesión (source_type, temp_file, engine_url).
    """
    from django.http import JsonResponse
    tabla = request.GET.get('tabla')
    if not tabla:
        return JsonResponse({'ok': False, 'error': 'Tabla requerida'})
    
    engine_url = request.session.get('engine_url')
    source_type = request.session.get('source_type')
    temp_file = request.session.get('temp_file')

    if not source_type:
        return JsonResponse({'ok': False, 'error': 'Fuente no inicializada'})

    import pandas as pd
    sample_rows = 25
    cols = []
    data = []

    try:
        if source_type == 'excel':
            df = pd.read_excel(temp_file, sheet_name=tabla, nrows=sample_rows, dtype=object)
        elif source_type == 'csv':
            if tabla != 'csv_table':
                return JsonResponse({'ok': False, 'error': 'Tabla CSV inválida'})
            df = pd.read_csv(temp_file, nrows=sample_rows, dtype=object)
        elif source_type == 'sql':
            if not engine_url:
                return JsonResponse({'ok': False, 'error': 'Sin conexión'})
            engine = create_engine(engine_url)
            safe = re.sub(r'[^A-Za-z0-9_]', '', tabla)
            df = pd.read_sql(f"SELECT TOP {sample_rows} * FROM [{safe}]", engine)
        elif source_type == 'sql_script':
            # Para scripts SQL, vamos a crear tablas temporales con prefijo en lugar de schema temporal
            if not engine_url:
                return JsonResponse({'ok': False, 'error': 'Sin conexión'})
            
            script = request.session.get('sql_script', '')
            if not script:
                return JsonResponse({'ok': False, 'error': 'Script SQL no disponible'})
            
            # Usamos un prefijo único para las tablas temporales
            prefix = f"__tmp_{uuid.uuid4().hex[:8]}_"
            engine = create_engine(engine_url)
            created_tables = []
            
            try:
                # Modifica el script para crear tablas con prefijo
                def _reemplazar_tabla(m):
                    nombre_tabla = m.group(2)
                    return f"{m.group(1)} `{prefix}{nombre_tabla}`"
                
                script_mod = re.sub(r'(?i)\b(CREATE\s+TABLE|INSERT\s+INTO)\s+`?([A-Za-z0-9_]+)`?',
                                    _reemplazar_tabla, script)
                
                # Ejecuta el script modificado 
                with engine.begin() as conn:
                    for stmt in [s.strip() for s in script_mod.split(';') if s.strip()]:
                        try:
                            conn.execute(text(stmt))
                            # Capturar tablas creadas para limpiarlas después
                            if re.search(r'(?i)create\s+table', stmt):
                                tabla_match = re.search(r'(?i)create\s+table\s+(?:if\s+not\s+exists\s+)?`?(\w+)`?', stmt)
                                if tabla_match:
                                    created_tables.append(tabla_match.group(1))
                        except Exception:                            pass  # Ignoramos errores individuales
                
                # Ahora lee la tabla específica con el prefijo
                temp_tabla = f"{prefix}{tabla}"
                try:
                    # Primero verifica si la tabla existe
                    with engine.begin() as conn:
                        result = conn.execute(text(
                            f"SELECT COUNT(*) FROM information_schema.tables "
                            f"WHERE table_catalog = DB_NAME() AND table_name = '{temp_tabla}'"
                        ))
                        if result.scalar() == 0:
                            return JsonResponse({
                                'ok': True, 
                                'columnas': [], 
                                'data': [],
                                'warning': 'La tabla parece no existir o está vacía'
                            })                    # Intenta leer la tabla
                    df = pd.read_sql(f"SELECT TOP {sample_rows} * FROM [{temp_tabla}]", engine)
                except Exception:
                    # Si falla, devuelve estructura vacía
                    return JsonResponse({
                        'ok': True, 
                        'columnas': [], 
                        'data': [],
                        'warning': 'La tabla parece no existir o está vacía'
                    })
                finally:
                    # Limpiar tablas temporales
                    with engine.begin() as conn:
                        for tabla_tmp in created_tables:
                            try:
                                conn.execute(text(f"DROP TABLE IF EXISTS [{tabla_tmp}]"))
                            except:
                                pass
            except Exception as e:
                return JsonResponse({'ok': False, 'error': f"Error al preparar vista previa: {str(e)}"})
        else:
            return JsonResponse({'ok': False, 'error': 'Tipo de origen desconocido'})
        
        # Procesamiento común final
        cols = [str(c) for c in df.columns]
        # Limitar longitud de valores para preview
        def _tr(v):
            s = '' if pd.isna(v) else str(v)
            return s[:120]
        data = [[_tr(v) for v in row] for row in df.itertuples(index=False, name=None)]
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

    return JsonResponse({'ok': True, 'columnas': cols, 'data': data})
    
@require_GET
def preview_tabla(request):
    """
    Devuelve (JSON) columnas y primeras filas de una tabla/hoja seleccionada (paso 2 dinámico).
    Parámetros:
      ?tabla=nombre
    Usa la sesión (source_type, temp_file, engine_url).
    """
    from django.http import JsonResponse
    tabla = request.GET.get('tabla')
    if not tabla:
        return JsonResponse({'ok': False, 'error': 'Tabla requerida'})
    engine_url = request.session.get('engine_url')
    source_type = request.session.get('source_type')
    temp_file = request.session.get('temp_file')

    if not source_type:
        return JsonResponse({'ok': False, 'error': 'Fuente no inicializada'})

    import pandas as pd
    from .sqlserver_utils import read_sql_safe, table_exists
    sample_rows = 25
    cols = []
    data = []

    try:
        if source_type == 'excel':
            df = pd.read_excel(temp_file, sheet_name=tabla, nrows=sample_rows, dtype=object)
        elif source_type == 'csv':
            if tabla != 'csv_table':
                return JsonResponse({'ok': False, 'error': 'Tabla CSV inválida'})
            df = pd.read_csv(temp_file, nrows=sample_rows, dtype=object)
        elif source_type == 'sql':
            if not engine_url:
                return JsonResponse({'ok': False, 'error': 'Sin conexión'})
            
            # Usar conexión segura para SQL Server
            engine = create_engine(engine_url)
            safe = re.sub(r'[^A-Za-z0-9_]', '', tabla)
            
            # Verificar si la tabla existe primero
            if not table_exists(safe, engine):
                return JsonResponse({'ok': False, 'error': f'La tabla [{safe}] no existe en la base de datos.'})
                
            # Usar lectura segura con manejo de errores
            df = read_sql_safe(f"SELECT TOP {sample_rows} * FROM [{safe}]", engine)
              # Verificar si hubo un error en la consulta
            if isinstance(df, pd.DataFrame) and 'error' in df.columns and len(df) == 1:
                return JsonResponse({'ok': False, 'error': f"Error en consulta: {df['error'][0]}"})

        elif source_type == 'sql_script':
            # Para scripts SQL, vamos a crear tablas temporales con prefijo en lugar de schema temporal
            if not engine_url:
                return JsonResponse({'ok': False, 'error': 'Sin conexión'})
            
            script = request.session.get('sql_script', '')
            if not script:
                return JsonResponse({'ok': False, 'error': 'Script SQL no disponible'})
              # Crea schema temporal único para preview
            import uuid
            temp_schema = f"__preview_{uuid.uuid4().hex[:8]}"
            engine = create_engine(engine_url)
            try:
                with engine.begin() as conn:
                    # SQL Server usa sintaxis diferente para crear schemas
                    conn.execute(text(f"IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = '{temp_schema}') BEGIN EXEC('CREATE SCHEMA [{temp_schema}]') END"))
                    
                    # Modifica el script para crear tablas en schema temporal
                    def _reemplazar_tabla(m):
                        nombre_tabla = m.group(2)
                        return f"{m.group(1)} [{temp_schema}].[{nombre_tabla}]"
                    
                    script_mod = re.sub(r'(?i)\b(CREATE\s+TABLE|INSERT\s+INTO)\s+`?([A-Za-z0-9_]+)`?',
                                        _reemplazar_tabla, script)
                    
                    # Ejecuta el script modificado en el schema temporal
                    for stmt in [s.strip() for s in script_mod.split(';') if s.strip()]:
                        try:
                            conn.execute(text(stmt))
                        except Exception:
                            pass  # Ignoramos errores individuales
                  # Ahora lee la tabla específica desde el schema temporal
                safe_tabla = re.sub(r'[^A-Za-z0-9_]', '', tabla)
                try:
                    # Intenta leer la tabla - SQL Server usa TOP en lugar de LIMIT
                    df = pd.read_sql(f"SELECT TOP {sample_rows} * FROM [{temp_schema}].[{safe_tabla}]", engine)
                except Exception:
                    # Si falla, devuelve estructura vacía
                    return JsonResponse({
                        'ok': True, 
                        'columnas': [], 
                        'data': [],
                        'warning': 'La tabla parece no existir o está vacía'                    })
                finally:
                    # Siempre limpia el schema temporal - SQL Server
                    with engine.begin() as conn:
                        conn.execute(text(f"DROP SCHEMA IF EXISTS [{temp_schema}]"))
            except Exception as e:
                return JsonResponse({'ok': False, 'error': f"Error al preparar vista previa: {str(e)}"})
        else:
            return JsonResponse({'ok': False, 'error': 'Tipo de origen desconocido'})
        
        # Procesamiento común final
        cols = [str(c) for c in df.columns]
        # Limitar longitud de valores para preview
        def _tr(v):
            s = '' if pd.isna(v) else str(v)
            return s[:120]
        data = [[_tr(v) for v in row] for row in df.itertuples(index=False, name=None)]
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

    return JsonResponse({'ok': True, 'columnas': cols, 'data': data})


# ===== MODIFICACIÓN FLUJO seleccionar_datos: integrar columnas en el paso 2 (sin step 3) =====



def seleccionar_datos(request):
    """
    Paso 1:
      - Subir archivo local (Excel / CSV / SQL)
      - O tomar archivo desde carpeta compartida (ruta UNC + nombre archivo)
      - (Opcional) Guardar como proceso si es .sql
    Paso 2:
      - Seleccionar tablas/hojas, columnas, rangos, renombrar y normalizar
      - Guardar directamente en la BD conectada (replace)
    """
    engine_url = request.session.get('engine_url')
    if not engine_url:
        messages.error(request, "Sesión expirada. Conecta de nuevo.")
        return redirect('subir_desde_mysql')
    engine = create_engine(engine_url)

    # Reset rápido vía ?reset=1
    if request.GET.get('reset') == '1':
        for k in ['wizard_step', 'source_type', 'temp_file', 'excel_sheets', 'created_tables']:
            request.session.pop(k, None)
        request.session['wizard_step'] = 1
        return redirect('seleccionar_datos')

    step = request.session.get('wizard_step', 1)
    source_type = request.session.get('source_type')  # 'excel','csv','sql'
    temp_file = request.session.get('temp_file')
    excel_sheets = request.session.get('excel_sheets', [])
    created_tables = request.session.get('created_tables', [])


    if request.method == 'POST' and request.POST.get('accion') == 'subir_archivo':
        modo = request.POST.get('modo_origen', 'local')

        # Limpiar estado previo
        for k in ['source_type','temp_file','excel_sheets','created_tables','sql_script','candidate_sql_tables']:
            request.session.pop(k, None)

        import tempfile, shutil
        script = ''
        archivo_path = None

        # 1. Obtener archivo (local o compartido)
        try:
            if modo == 'compartido':
                ruta = (request.POST.get('ruta_compartida') or '').strip()
                nombre_archivo = (request.POST.get('nombre_archivo') or '').strip()
                if not ruta or not nombre_archivo:
                    messages.error(request, "Ruta y nombre de archivo requeridos.")
                    return redirect('seleccionar_datos')
                full_path = os.path.join(ruta, nombre_archivo)
                if not os.path.isfile(full_path):
                    messages.error(request, f"No se encuentra el archivo: {full_path}")
                    return redirect('seleccionar_datos')
                ext = os.path.splitext(full_path.lower())[1]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                with open(full_path, 'rb') as fsrc, open(tmp.name, 'wb') as fdst:
                    shutil.copyfileobj(fsrc, fdst)
                archivo_path = tmp.name
                if ext == '.sql':
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        script = f.read()
            else:
                archivo = request.FILES.get('archivo_fuente')
                if not archivo:
                    messages.error(request, "Selecciona un archivo.")
                    return redirect('seleccionar_datos')
                nombre = archivo.name.lower()
                ext = os.path.splitext(nombre)[1]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                for chunk in archivo.chunks():
                    tmp.write(chunk)
                tmp.close()
                archivo_path = tmp.name
                if ext == '.sql':
                    archivo.seek(0)
                    script = archivo.read().decode('utf-8', errors='ignore')
        except Exception as e:
            messages.error(request, f"Error leyendo el archivo: {e}")
            return redirect('seleccionar_datos')

        # 2. Procesar según extensión
        if ext in ('.xlsx', '.xls'):
            try:
                xls = pd.ExcelFile(archivo_path)
                request.session['source_type'] = 'excel'
                request.session['temp_file'] = archivo_path
                request.session['excel_sheets'] = xls.sheet_names
                request.session['wizard_step'] = 2
                messages.success(request, f"Excel cargado ({len(xls.sheet_names)} hojas). Selecciona qué subir.")
            except Exception as e:
                messages.error(request, f"Error leyendo Excel: {e}")
                return redirect('seleccionar_datos')

        elif ext == '.csv':
            request.session['source_type'] = 'csv'
            request.session['temp_file'] = archivo_path
            request.session['excel_sheets'] = ['csv_table']
            request.session['wizard_step'] = 2
            messages.success(request, "CSV cargado. Selecciona columnas.")

        elif ext == '.sql':
            if not script.strip():
                messages.error(request, "Script SQL vacío.")
                return redirect('seleccionar_datos')

            patt = re.compile(r'create\s+table\s+`?([A-Za-z0-9_]+)`?', re.IGNORECASE)
            tablas = patt.findall(script)
            tablas = sorted(list(dict.fromkeys(tablas)))
            if not tablas:
                messages.warning(request, "No se detectaron tablas en el script. Aun así se ejecutará.")

            errores = []
            total_filas = 0
            try:
                bloques = [b.strip() for b in script.split(';') if b.strip()]
                with engine.begin() as conn:
                    for stmt in bloques:
                        try:
                            conn.execute(text(stmt))
                        except Exception as e:
                            errores.append({'stmt': stmt[:60], 'error': str(e)})
                            messages.warning(request, f"Error al ejecutar: {e}")

                # Contar filas usando una conexión explícita (SQLAlchemy 2.x)                with engine.connect() as conn:
                    for t in tablas:
                        try:
                            result = conn.execute(text(f"SELECT COUNT(*) FROM [{t}]"))
                            filas = result.scalar() or 0
                            total_filas += filas
                            messages.info(request, f"Tabla '{t}': {filas} filas")
                        except Exception as e:
                            messages.warning(request, f"Error leyendo '{t}': {e}")

                messages.success(request, f"Script ejecutado. {len(tablas)} tabla(s), {total_filas} fila(s).")
            except Exception as e:
                messages.error(request, f"Error global ejecutando script: {e}")

            if request.POST.get('guardar_proceso'):
                import time
                from sqlalchemy.engine.url import make_url
                url = make_url(engine_url)
                nombre_proc = (request.POST.get('nombre_proceso') or f"proc_sql_{int(time.time())}").strip()
                cfg = {
                    "nombre_proceso": nombre_proc,
                    "origen": {
                        "tipo": "sql_script",
                        "contenido": script,
                        "tablas_resultantes": tablas
                    },
                    "destino": {
                        "motor": "mysql",
                        "conexion": {
                            "host": url.host,
                            "puerto": url.port or 3306,
                            "usuario": url.username,
                            "password": url.password,
                            "base": url.database
                        }
                    },
                    "ejecucion": {"on_error": "continue"}
                }
                try:
                    proceso = ProcessConfig.objects.create(
                        nombre=nombre_proc,
                        descripcion="Proceso (ejecutado inmediatamente)",
                        json_config=cfg
                    )
                    run = ProcessRunLog.objects.create(
                        proceso=proceso,
                        exito=True,
                        filas_totales=total_filas,
                        mensaje=f"OK. Filas procesadas: {total_filas}",
                        fin=timezone.now()
                    )
                    if errores:
                        run.errores = errores
                        run.save()
                    messages.success(request, f"Proceso '{nombre_proc}' guardado y registrado.")
                except Exception as e:
                    messages.error(request, f"No se pudo guardar el proceso: {e}")

            return redirect('index')

        else:
            messages.error(request, "Extensión no soportada.")
            return redirect('seleccionar_datos')



    # Procesar columnas (Paso 2)
    if request.method == 'POST' and request.POST.get('accion') == 'procesar_columnas' and step == 2:
        tablas_sel = request.POST.getlist('tablas')
        if not tablas_sel:
            messages.error(request, "Selecciona al menos una tabla.")
            return redirect('seleccionar_datos')
        
        source_type = request.session.get('source_type')
        normalizar = bool(request.POST.get('aplicar_normalizacion'))
        procesadas = 0
        detalles = []

        if source_type == 'sql_script':
            script = request.session.get('sql_script', '')
            if not script:
                messages.error(request, "Script no disponible en sesión.")
                return redirect('seleccionar_datos')
            
            temp_schema = f"__tmp_{uuid.uuid4().hex[:8]}"
            try:
                with engine.begin() as conn:
                    # SQL Server usa sintaxis diferente para crear schemas
                    conn.execute(text(f"IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = '{temp_schema}') BEGIN EXEC('CREATE SCHEMA [{temp_schema}]') END"))
                    # Reescribir CREATE/INSERT apuntando al schema temporal
                    def _reemplazar_tabla(m):
                        nombre_tabla = m.group(2)
                        return f"{m.group(1)} [{temp_schema}].[{nombre_tabla}]"
                    script_mod = re.sub(r'(?i)\b(CREATE\s+TABLE|INSERT\s+INTO)\s+`?([A-Za-z0-9_]+)`?',
                                        _reemplazar_tabla, script)
                    for stmt in [s.strip() for s in script_mod.split(';') if s.strip()]:
                        conn.execute(text(stmt))
            except Exception as e:
                messages.error(request, f"Fallo ejecutando script: {e}")                # Intentar limpiar
                with engine.begin() as c:
                    try:
                        c.execute(text(f"DROP SCHEMA IF EXISTS [{temp_schema}]"))
                    except:
                        pass
                return redirect('seleccionar_datos')

        for tabla in tablas_sel:
            cols_sel = request.POST.getlist(f'columnas_{tabla}')
            if not cols_sel:
                continue            # Cargar DataFrame
            if source_type == 'excel':
                df_full = pd.read_excel(request.session['temp_file'], sheet_name=tabla, dtype=object)
            elif source_type == 'csv':
                df_full = pd.read_csv(request.session['temp_file'], dtype=object)
            elif source_type == 'sql_script':
                # Leer de schema temporal
                safe = re.sub(r'[^A-Za-z0-9_]', '', tabla)
                try:
                    select_cols = ", ".join([f"[{c}]" for c in cols_sel])
                    df_full = pd.read_sql(f"SELECT {select_cols} FROM [{temp_schema}].[{safe}]", engine)
                except Exception:
                    df_full = pd.DataFrame(columns=cols_sel)
            else:
                df_full = pd.DataFrame()

            if source_type in ('excel','csv'):
                df_full = df_full[[c for c in cols_sel if c in df_full.columns]]

            # Rango filas
            def _toi(v, d):
                try: return int(v)
                except: return d
            inicio = _toi(request.POST.get(f'fila_inicio_{tabla}', 0), 0)
            fin_raw = (request.POST.get(f'fila_fin_{tabla}', '') or '').strip()
            fin = _toi(fin_raw, len(df_full)) if fin_raw else len(df_full)
            if inicio < 0: inicio = 0
            if fin > len(df_full): fin = len(df_full)
            if fin < inicio: fin = inicio
            df = df_full.iloc[inicio:fin]

            # Renombrado
            nuevos = {}
            usados = set()
            for col in cols_sel:
                nuevo = (request.POST.get(f'rename_{tabla}_{col}', col) or col).strip()
                nuevo = re.sub(r'\W+', '_', nuevo) or col
                base = nuevo; k = 1
                while nuevo in usados:
                    k += 1
                    nuevo = f"{base}_{k}"
                usados.add(nuevo)
                nuevos[col] = nuevo
            df = df.rename(columns=nuevos)

            if normalizar and not df.empty:
                for c in df.columns:
                    df[c] = df[c].apply(_normalizar_celda)

            final_name = request.POST.get(f'nombre_tabla_final_{tabla}', tabla).strip() or tabla
            final_name = re.sub(r'\W+', '_', final_name)[:60]
            try:
                df.to_sql(final_name, engine, if_exists='replace', index=False)
                procesadas += 1
                detalles.append(f"{final_name}({len(df)})")
            except Exception as e:
                messages.error(request, f"Error guardando {final_name}: {e}")

        # Limpiar schema temporal si hubo script        if source_type == 'sql_script':
            with engine.begin() as conn:
                try:
                    conn.execute(text(f"DROP SCHEMA [{temp_schema}]"))
                except:
                    pass

        if procesadas:
            messages.success(request, f"{procesadas} tabla(s) guardada(s): " + ", ".join(detalles))
        else:
            messages.error(request, "No se guardó ninguna tabla.")
        for k in ['wizard_step','source_type','temp_file','excel_sheets','created_tables','sql_script','candidate_sql_tables']:
            request.session.pop(k, None)
        return redirect('index')

    # Render Step 2
    if step == 2:
        source_type = request.session.get('source_type')
        if source_type == 'excel':
            tablas_disponibles = request.session.get('excel_sheets', [])
        elif source_type == 'csv':
            tablas_disponibles = ['csv_table']
        elif source_type == 'sql_script':
            tablas_disponibles = request.session.get('candidate_sql_tables', [])
        else:
            tablas_disponibles = []
        return render(request, 'archivos/seleccionar_datos.html', {
            'step': 2,
            'tablas_disponibles': tablas_disponibles,
            'source_type': source_type
        })

    return render(request, 'archivos/seleccionar_datos.html', {'step': 1})


def _extraer_tablas_creadas(engine):
    try:
        # Usar sintaxis SQL Server en lugar de MySQL
        query = """
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE' 
        AND TABLE_CATALOG = DB_NAME()
        """
        return pd.read_sql(query, engine)['TABLE_NAME'].tolist()
    except Exception:
        return []

def _normalizar_celda(valor):
    """
    Normaliza una celda según reglas simples:
      - Cadenas vacías o equivalentes a nulo ('n/a', 'na', 'none', 'null') -> None
      - Si la cadena inicia con un número entero (ej: '15 días', '20kg', '  7 items') devuelve ese entero
      - En cualquier otro caso devuelve el valor original
    No altera tipos que no sean str.
    """
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto or texto.lower() in ('n/a', 'na', 'none', 'null'):
            return None

        # Captura un entero inicial (positivo o negativo) al comienzo de la cadena
        coincidencia = re.match(r'^(-?\d+)', texto)
        if coincidencia:
            numero_str = coincidencia.group(1)
            try:
                return int(numero_str)
            except Exception:
                # Si falla la conversión, se deja el valor original
                pass

    return valor








def procesos_list(request):
    procesos = ProcessConfig.objects.filter(activo=True).order_by('-actualizado')
    return render(request, 'archivos/procesos_list.html', {'procesos': procesos})



def ejecutar_proceso(request, proceso_id):
    proceso = get_object_or_404(ProcessConfig, id=proceso_id, activo=True)
    run = ProcessRunLog.objects.create(proceso=proceso)
    cfg = proceso.json_config
    errores = []
    total_filas = 0
    try:
        destino = cfg['destino']
        motor = destino['motor']
        conn = destino['conexion']
        if motor == 'mysql':
            engine_url = f"mysql+pymysql://{conn['usuario']}:{conn['password']}@{conn['host']}:{conn['puerto']}/{conn['base']}"
        elif motor == 'postgres':
            engine_url = f"postgresql://{conn['usuario']}:{conn['password']}@{conn['host']}:{conn['puerto']}/{conn['base']}"
        elif motor == 'mssql':
            engine_url = f"mssql+pyodbc://{conn['usuario']}:{conn['password']}@{conn['host']},{conn['puerto']}/{conn['base']}?driver=ODBC+Driver+17+for+SQL+Server"
        else:
            raise ValueError("Motor destino no soportado")
        engine = create_engine(engine_url)

        origen = cfg['origen']
        if origen['tipo'] in ('excel','csv'):
            # ...existing code para excel/csv...
            pass  # (deja tu implementación previa)
        elif origen['tipo'] == 'sql_script':
            # 1. Cargar script (contenido inline o archivo)
            sql_text = origen.get('contenido')
            if not sql_text:
                ruta_base = origen.get('ruta_base') or ''
                archivo = origen.get('archivo')
                if not archivo:
                    raise ValueError("Script SQL no definido.")
                script_path = os.path.join(ruta_base, archivo) if ruta_base else archivo
                with open(script_path, 'r', encoding='utf-8') as f:
                    sql_text = f.read()
            bloques = [b.strip() for b in sql_text.split(';') if b.strip()]
            with engine.begin() as conn:
                for stmt in bloques:
                    try:
                        conn.execute(text(stmt))
                    except Exception as e:
                        errores.append({'stmt': stmt[:60], 'error': str(e)})
                        if cfg.get('ejecucion', {}).get('on_error') == 'stop':
                            raise
            # 2. Opcional: post_copia tablas (si quieres mapear a otros nombres)
            for m in origen.get('tablas_resultantes', []):
                # m puede ser string (mismo nombre) o dict {'origen':'t1','destino':'t2','modo':'replace'}
                if isinstance(m, str):
                    tabla_origen = tabla_destino = m
                    modo = 'replace'
                else:
                    tabla_origen = m.get('origen')
                    tabla_destino = m.get('destino', tabla_origen)
                    modo = m.get('modo', 'replace')
                if not tabla_origen:                    continue
                df = pd.read_sql(f"SELECT * FROM [{tabla_origen}]", engine)
                df.to_sql(tabla_destino, engine, if_exists=('replace' if modo=='replace' else 'append'), index=False)
                total_filas += len(df)
        else:
            raise ValueError("Origen no implementado aún")

        run.exito = True
        run.filas_totales = total_filas
        run.mensaje = f"OK. Filas procesadas: {total_filas}"
    except Exception as e:
        run.exito = False
        run.mensaje = f"Fallo: {e}"
        errores.append({'stack': traceback.format_exc()})
    run.fin = timezone.now()
    if errores:
        run.errores = errores
    run.save()
    if run.exito:
        messages.success(request, f"Proceso '{proceso.nombre}' ejecutado. Filas: {run.filas_totales}")
    else:
        messages.error(request, f"Proceso '{proceso.nombre}' falló: {run.mensaje}")
    return redirect('procesos_list')


def _leer_origen_simple(tipo, archivo, hoja=None):
    try:
        if tipo == 'excel':
            return pd.read_excel(archivo, sheet_name=hoja, dtype=object)
        if tipo == 'csv':
            return pd.read_csv(archivo, dtype=object)
    except Exception:
        return None
    return None


def preview_sql_conversion(request):
    """
    Vista AJAX para previsualizar la conversión de SQL de MySQL a SQL Server
    sin ejecutar el script.
    """
    from django.http import JsonResponse
    from .mysql_to_sqlserver import convert_mysql_to_sqlserver
    from .sql_compatibility import analizar_compatibilidad_mysql_sqlserver
    import json
    
    if request.method == 'POST' and request.FILES.get('archivo_sql'):
        try:
            archivo_sql = request.FILES['archivo_sql']
            archivo_sql.seek(0)
            sql_original = archivo_sql.read().decode('utf-8', errors='ignore')
            
            # Realizar análisis de compatibilidad
            reporte_compatibilidad = analizar_compatibilidad_mysql_sqlserver(sql_original)
            
            # Convertir SQL de MySQL a formato SQL Server
            sql_convertido = convert_mysql_to_sqlserver(sql_original)
            
            # Limitar tamaño para respuesta AJAX
            max_length = 50000  # Caracteres máximos para evitar respuestas muy grandes
            sql_original_truncado = sql_original[:max_length] + ("..." if len(sql_original) > max_length else "")
            sql_convertido_truncado = sql_convertido[:max_length] + ("..." if len(sql_convertido) > max_length else "")
            
            # Generar resumen de cambios realizados
            cambios = []
            if '`' in sql_original:
                cambios.append("Reemplazo de comillas invertidas (`) por corchetes ([]) para identificadores")
            if 'AUTO_INCREMENT' in sql_original:
                cambios.append("Conversión de AUTO_INCREMENT a IDENTITY(1,1)")
            if 'ENGINE=' in sql_original:
                cambios.append("Eliminación de especificaciones de motor (ENGINE=InnoDB)")
            if 'int(' in sql_original:
                cambios.append("Ajuste de tipos de datos (int(N) → int)")
            if 'varchar(' in sql_original:
                cambios.append("Conversión de varchar a nvarchar para soporte Unicode")
            if 'START TRANSACTION' in sql_original:
                cambios.append("Ajuste de sintaxis de transacciones (START TRANSACTION → BEGIN TRANSACTION)")
            
            # Incluir advertencias del análisis de compatibilidad
            nivel_compatibilidad = reporte_compatibilidad['nivel_compatibilidad']
            mensajes_compatibilidad = {
                'alto': 'El script parece ser altamente compatible con SQL Server.',
                'medio': 'El script tiene algunos problemas de compatibilidad que pueden requerir ajustes manuales.',
                'bajo': 'El script tiene problemas graves de compatibilidad que requerirán intervención manual.'
            }
            
            # Crear respuesta para el cliente
            respuesta = {
                'success': True,
                'sql_original': sql_original_truncado,
                'sql_convertido': sql_convertido_truncado,
                'cambios': cambios,
                'compatibilidad': {
                    'nivel': nivel_compatibilidad,
                    'mensaje': mensajes_compatibilidad[nivel_compatibilidad],
                    'problemas': reporte_compatibilidad['total_problemas'],
                    'recomendaciones': reporte_compatibilidad['recomendaciones']
                }
            }
            
            # Si hay problemas específicos, incluirlos en la respuesta
            if reporte_compatibilidad['problemas']:
                respuesta['compatibilidad']['detalles'] = reporte_compatibilidad['problemas']
            
            return JsonResponse(respuesta)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({
        'success': False,
        'error': 'Método no permitido o archivo no proporcionado'
    }, status=400)
    """
    Vista AJAX para previsualizar la conversión de SQL de MySQL a SQL Server
    sin ejecutar el script.
    """
    from django.http import JsonResponse
    from .mysql_to_sqlserver import convert_mysql_to_sqlserver
    import json
    
    if request.method == 'POST' and request.FILES.get('archivo_sql'):
        try:
            archivo_sql = request.FILES['archivo_sql']
            archivo_sql.seek(0)
            sql_original = archivo_sql.read().decode('utf-8', errors='ignore')
            
            # Convertir SQL de MySQL a formato SQL Server
            sql_convertido = convert_mysql_to_sqlserver(sql_original)
            
            # Limitar tamaño para respuesta AJAX
            max_length = 50000  # Caracteres máximos para evitar respuestas muy grandes
            sql_original_truncado = sql_original[:max_length] + ("..." if len(sql_original) > max_length else "")
            sql_convertido_truncado = sql_convertido[:max_length] + ("..." if len(sql_convertido) > max_length else "")
            
            # Generar resumen de cambios realizados
            cambios = []
            if '`' in sql_original:
                cambios.append("Reemplazo de comillas invertidas (`) por corchetes ([]) para identificadores")
            if 'AUTO_INCREMENT' in sql_original:
                cambios.append("Conversión de AUTO_INCREMENT a IDENTITY(1,1)")
            if 'ENGINE=' in sql_original:
                cambios.append("Eliminación de especificaciones de motor (ENGINE=InnoDB)")
            if 'int(' in sql_original:
                cambios.append("Ajuste de tipos de datos (int(N) → int)")
            if 'varchar(' in sql_original:
                cambios.append("Conversión de varchar a nvarchar para soporte Unicode")
            if 'START TRANSACTION' in sql_original:
                cambios.append("Ajuste de sintaxis de transacciones (START TRANSACTION → BEGIN TRANSACTION)")
            
            return JsonResponse({
                'success': True,
                'sql_original': sql_original_truncado,
                'sql_convertido': sql_convertido_truncado,
                'cambios': cambios
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({
        'success': False,
        'error': 'Método no permitido o archivo no proporcionado'
    }, status=400)