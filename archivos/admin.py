from django.contrib import admin
from .models import ArchivoCargado, CarpetaCompartida, ArchivoDetectado, ArchivoProcesado

@admin.register(CarpetaCompartida)
class CarpetaCompartidaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'ruta', 'activa', 'fecha_creacion']
    list_filter = ['activa', 'fecha_creacion']
    search_fields = ['nombre', 'ruta']

@admin.register(ArchivoDetectado)
class ArchivoDetectadoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'carpeta', 'tamaño', 'fecha_modificacion']
    list_filter = ['tipo', 'carpeta', 'fecha_deteccion']
    search_fields = ['nombre', 'ruta_completa']

@admin.register(ArchivoProcesado)
class ArchivoProcesadoAdmin(admin.ModelAdmin):
    list_display = ['archivo_original', 'hoja_seleccionada', 'filas_totales', 'fecha_procesamiento']
    list_filter = ['fecha_procesamiento']

@admin.register(ArchivoCargado)
class ArchivoCargadoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'fecha_carga', 'filas']
    list_filter = ['tipo', 'fecha_carga']
    search_fields = ['nombre']
