def preview_sql_conversion(request):
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
