# Script para configurar el servicio de SQL Server para que inicie automáticamente
# Ejecutar como administrador

# Definir las funciones de utilidad
function Get-SqlServerServices {
    Get-Service | Where-Object { $_.DisplayName -like "*SQL Server*" } | 
        Select-Object Name, DisplayName, Status, StartType |
        Format-Table -AutoSize
}

function Set-SqlServerServiceStartup {
    param (
        [string]$ServiceName,
        [string]$StartupType = "Automatic"
    )
    
    try {
        $service = Get-Service -Name $ServiceName -ErrorAction Stop
        Set-Service -Name $ServiceName -StartupType $StartupType
        Write-Host "Servicio $($service.DisplayName) configurado para iniciar $StartupType" -ForegroundColor Green
        
        # Iniciar el servicio si no está en ejecución
        if ($service.Status -ne "Running") {
            Write-Host "Iniciando servicio $($service.DisplayName)..." -ForegroundColor Yellow
            Start-Service -Name $ServiceName
            Write-Host "Servicio iniciado correctamente" -ForegroundColor Green
        }
        
        return $true
    }
    catch {
        Write-Host "Error configurando el servicio $ServiceName: $_" -ForegroundColor Red
        return $false
    }
}

# Mostrar la información actual de los servicios
Write-Host "Servicios de SQL Server actuales:" -ForegroundColor Cyan
Get-SqlServerServices

# Detectar automáticamente los servicios de SQL Server relevantes
$sqlServices = Get-Service | Where-Object { 
    $_.Name -like "MSSQL*" -and 
    $_.DisplayName -like "*SQL Server (*" 
}

if ($sqlServices.Count -eq 0) {
    Write-Host "No se encontraron servicios de SQL Server instalados." -ForegroundColor Red
    exit 1
}

# Mostrar los servicios encontrados y configurar
Write-Host "`nServicios de SQL Server encontrados para configurar:" -ForegroundColor Cyan
foreach ($service in $sqlServices) {
    Write-Host "- $($service.Name): $($service.DisplayName) - Estado actual: $($service.Status)" -ForegroundColor Yellow
    
    $confirm = Read-Host "¿Desea configurar este servicio para inicio automático? (S/N)"
    if ($confirm -eq "S" -or $confirm -eq "s") {
        $result = Set-SqlServerServiceStartup -ServiceName $service.Name
    }
}

# Configurar también los servicios relacionados
$relatedServices = @(
    "SQLBrowser", # SQL Server Browser
    "SQLWriter",  # SQL Server VSS Writer
    "SQLTELEMETRY" # SQL Server CEIP
)

foreach ($serviceName in $relatedServices) {
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host "`nServicio relacionado encontrado: $($service.DisplayName)" -ForegroundColor Cyan
        $confirm = Read-Host "¿Desea configurar este servicio para inicio automático? (S/N)"
        if ($confirm -eq "S" -or $confirm -eq "s") {
            $result = Set-SqlServerServiceStartup -ServiceName $serviceName
        }
    }
}

# Verificar el estado final
Write-Host "`nEstado final de los servicios:" -ForegroundColor Cyan
Get-SqlServerServices

Write-Host "`nCompruebe que los servicios necesarios están configurados como 'Automatic' e iniciados." -ForegroundColor Green
