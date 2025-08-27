from django.db import models
import os

class CarpetaCompartida(models.Model):
    nombre = models.CharField(max_length=255, verbose_name="Nombre de la carpeta")
    ruta = models.CharField(max_length=500, verbose_name="Ruta de la carpeta compartida")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Carpeta Compartida"
        verbose_name_plural = "Carpetas Compartidas"
    
    def __str__(self):
        return f"{self.nombre} ({self.ruta})"
    
    def existe(self):
        """Verifica si la ruta existe y es accesible"""
        return os.path.exists(self.ruta) and os.path.isdir(self.ruta)

class ArchivoDetectado(models.Model):
    TIPOS_ARCHIVO = [
        ('excel', 'Excel (.xlsx, .xls)'),
        ('csv', 'CSV (.csv)'),
        ('txt', 'Texto (.txt)'),
    ]
    
    carpeta = models.ForeignKey(CarpetaCompartida, on_delete=models.CASCADE, related_name='archivos')
    nombre = models.CharField(max_length=255, verbose_name="Nombre del archivo")
    ruta_completa = models.CharField(max_length=1000, verbose_name="Ruta completa")
    tipo = models.CharField(max_length=10, choices=TIPOS_ARCHIVO, verbose_name="Tipo de archivo")
    tamaño = models.BigIntegerField(verbose_name="Tamaño en bytes")
    fecha_modificacion = models.DateTimeField(verbose_name="Fecha de modificación")
    fecha_deteccion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de detección")
    
    # Para archivos Excel - información de hojas
    hojas = models.TextField(blank=True, null=True, verbose_name="Hojas disponibles (JSON)")
    
    class Meta:
        verbose_name = "Archivo Detectado"
        verbose_name_plural = "Archivos Detectados"
        unique_together = ['carpeta', 'ruta_completa']
    
    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"

class ArchivoProcesado(models.Model):
    archivo_original = models.ForeignKey(ArchivoDetectado, on_delete=models.CASCADE, related_name='procesados')
    hoja_seleccionada = models.CharField(max_length=255, blank=True, null=True, verbose_name="Hoja seleccionada")
    filas_totales = models.IntegerField(verbose_name="Total de filas")
    columnas_totales = models.IntegerField(verbose_name="Total de columnas")
    columnas_nombres = models.TextField(verbose_name="Nombres de columnas")
    fecha_procesamiento = models.DateTimeField(auto_now_add=True)
    
    # Datos del preview (primeras filas)
    datos_preview = models.TextField(verbose_name="Preview de datos (JSON)")
    
    class Meta:
        verbose_name = "Archivo Procesado"
        verbose_name_plural = "Archivos Procesados"
    
    def __str__(self):
        hoja = f" - {self.hoja_seleccionada}" if self.hoja_seleccionada else ""
        return f"{self.archivo_original.nombre}{hoja}"

# Mantener el modelo original por compatibilidad
class ArchivoCargado(models.Model):
    nombre = models.CharField(max_length=255)
    tipo = models.CharField(max_length=10)  # Excel/CSV
    fecha_carga = models.DateTimeField(auto_now_add=True)
    columnas = models.TextField()  # lista de columnas como string
    filas = models.IntegerField()

    def __str__(self):
        return self.nombre