from django.urls import path
from . import views

urlpatterns = [
    # Página principal
    path('', views.index, name='index'),
    path('elegir-metodo/', views.elegir_metodo, name='elegir_metodo'),
    
    
    #administrador de carpetas compartidas
     path('carpetas/eliminar/<int:carpeta_id>/', views.eliminar_carpeta, name='eliminar_carpeta'),
     
    # Archivos locales
    path('subir-local/', views.subir_archivo_local, name='subir_archivo_local'),
    path('guardar-local/', views.guardar_archivo_local, name='guardar_archivo_local'),
    path('archivos-guardados/', views.ver_archivos_guardados, name='archivos_guardados'),
    path('seleccionar-archivos/<int:carpeta_id>/', views.seleccionar_archivos_para_subir, name='seleccionar_archivos_para_subir'),
    # Carpetas compartidas
    path('carpetas/', views.listar_carpetas_compartidas, name='listar_carpetas_compartidas'),
    path('carpetas/gestionar/', views.gestionar_carpetas, name='gestionar_carpetas'),
    path('carpetas/<int:carpeta_id>/archivos/', views.listar_archivos, name='listar_archivos'),
    path('subir-publico/', views.subir_publico, name='subir_publico'),
    # Archivos de carpetas compartidas
    path('archivo/<int:archivo_id>/', views.detalle_archivo, name='detalle_archivo'),
    path('archivo/<int:archivo_id>/procesar/', views.procesar_archivo_vista, name='procesar_archivo'),
    path('carpetas/<int:carpeta_id>/subir/', views.subir_archivo_a_carpeta, name='subir_archivo'),
    # API
    path('api/archivo-procesado/<int:procesado_id>/datos/', views.obtener_datos_archivo, name='obtener_datos_archivo'),
    path('carpetas/<int:carpeta_id>/seleccionar/', views.seleccionar_archivos_para_subir, name='seleccionar_archivos'),
    path('confirmar-subida/', views.confirmar_archivos_subir, name='confirmar_archivos_subir'),
    
    # Elegir para subir desde archivos de Bases de datos
    path('subir-sql/', views.subir_sql, name='subir_sql'),
    path('subir-desde-postgres/', views.subir_desde_postgres, name='subir_desde_postgres'),
    path('subir-desde-mysql/', views.subir_desde_mysql, name='subir_desde_mysql'),
    path("seleccionar_tablas/", views.seleccionar_tablas, name="seleccionar_tablas"),
    path('subir-desde-postgres/', views.subir_desde_postgres, name='subir_desde_postgres'),
    path('subir-desde-sqlserver/', views.subir_desde_sqlserver, name='subir_desde_sqlserver'),
    # URLs de compatibilidad
    path('subir/', views.subir_archivo, name='subir_archivo'),
    path('guardar/', views.guardar_archivo, name='guardar_archivo'),
]