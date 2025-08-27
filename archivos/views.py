from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from datetime import datetime
from pathlib import Path
import pandas as pd
import os
import json
import humanize
import base64
from io import BytesIO, StringIO
from .forms import SubirArchivoForm, CarpetaCompartidaForm
from .models import ArchivoCargado, CarpetaCompartida, ArchivoDetectado, ArchivoProcesado
from .utils import detectar_archivos_en_carpeta, leer_hojas_excel, procesar_archivo
from django.views.decorators.csrf import csrf_exempt 




# ...existing code... (mantener todas las importaciones y otras funciones)

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
                    archivo.seek(0)  # Asegurar que estamos al inicio
                    
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
    """Vista principal que permite elegir entre subir archivo local o acceder a carpetas compartidas"""
    
    # Contar carpetas compartidas disponibles
    carpetas_disponibles = CarpetaCompartida.objects.filter(activa=True).count()
    
    # Contar archivos recientes subidos
    archivos_recientes = ArchivoCargado.objects.all().order_by('-fecha_carga')[:5]
    
    context = {
        'carpetas_disponibles': carpetas_disponibles,
        'archivos_recientes': archivos_recientes
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
            'columnas_lista': columnas_lista,  # ← Nueva variable
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