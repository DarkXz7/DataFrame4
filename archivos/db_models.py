"""
Modelos que representan tablas existentes en SQL Server
Estas clases permiten interactuar con tablas ya creadas en la base de datos SQL Server
No se deben crear nuevas tablas, solo reflejar la estructura existente
"""

from django.db import models


class ProcessAutomation(models.Model):
    """
    Modelo que representa la tabla ProcessAutomation existente en SQL Server
    Almacena información sobre procesos automatizados ejecutados
    """
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=255)
    tipo_proceso = models.CharField(max_length=50)
    fecha_ejecucion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20)
    tiempo_ejecucion = models.IntegerField()
    usuario = models.CharField(max_length=100)
    parametros = models.TextField(blank=True, null=True)
    resultado = models.TextField(blank=True, null=True)
    filas_afectadas = models.IntegerField(default=0)
    error_mensaje = models.TextField(blank=True, null=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ProcessAutomation'
        managed = False  # Importante: indica que Django no debe gestionar la tabla

    def __str__(self):
        return f"{self.nombre} ({self.fecha_ejecucion})"


class SqlFileUpload(models.Model):
    """
    Modelo que representa la tabla SqlFileUpload existente en SQL Server
    Almacena información sobre los archivos SQL subidos y procesados
    """
    id = models.AutoField(primary_key=True)
    nombre_archivo = models.CharField(max_length=255)
    tamanio_bytes = models.BigIntegerField()
    fecha_subida = models.DateTimeField(auto_now_add=True)
    usuario = models.CharField(max_length=100)
    tablas_creadas = models.TextField(blank=True, null=True)
    sentencias_total = models.IntegerField(default=0)
    sentencias_exito = models.IntegerField(default=0)
    conversion_mysql = models.BooleanField(default=False)
    errores = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20)
    ruta_temporal = models.CharField(max_length=255, blank=True, null=True)
    version_convertida = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'SqlFileUpload'
        managed = False  # Importante: indica que Django no debe gestionar la tabla

    def __str__(self):
        return f"{self.nombre_archivo} ({self.fecha_subida})"
