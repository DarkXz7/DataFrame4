-- Script para verificar datos en SQL Server
-- Ejecutar en SQL Server Management Studio

USE pruebamiguel;
GO

-- 1. Verificar si la tabla personas1 existe
IF OBJECT_ID('personas1', 'U') IS NULL
BEGIN
    PRINT '❌ La tabla personas1 NO existe en la base de datos.';
END
ELSE
BEGIN
    PRINT '✅ La tabla personas1 existe en la base de datos.';
    
    -- 2. Verificar cuántos registros tiene
    DECLARE @TotalRows INT;
    SELECT @TotalRows = COUNT(*) FROM personas1;
    PRINT '📊 Total de registros en la tabla personas1: ' + CAST(@TotalRows AS VARCHAR);
    
    -- 3. Mostrar algunos registros
    PRINT '';
    PRINT '--- Primeros 5 registros de la tabla personas1 ---';
    SELECT TOP 5 * FROM personas1;
    
    -- 4. Verificar distribución por género
    PRINT '';
    PRINT '--- Distribución por género ---';
    SELECT gender, COUNT(*) AS cantidad 
    FROM personas1 
    GROUP BY gender 
    ORDER BY COUNT(*) DESC;
END

-- 5. Consultar registros en la tabla ProcessAutomation
PRINT '';
PRINT '--- Últimos registros en ProcessAutomation ---';
SELECT TOP 5 id, nombre, tipo_proceso, estado, fecha_ejecucion, tiempo_ejecucion, filas_afectadas
FROM ProcessAutomation
WHERE nombre LIKE '%personas1%'
ORDER BY fecha_ejecucion DESC;

-- 6. Consultar registros en la tabla SqlFileUpload
PRINT '';
PRINT '--- Últimos registros en SqlFileUpload ---';
SELECT TOP 5 id, nombre_archivo, tamanio_bytes, estado, sentencias_total, sentencias_exito
FROM SqlFileUpload
WHERE nombre_archivo LIKE '%personas1%'
ORDER BY fecha_subida DESC;
