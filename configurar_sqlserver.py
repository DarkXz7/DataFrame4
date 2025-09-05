"""
Script para configurar SQL Server permitiendo conexiones remotas
NOTA: Debe ejecutarse como Administrador
"""
import subprocess
import sys
import os
from pathlib import Path
import time

def print_header(title):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def main():
    print_header("CONFIGURACIÓN DE SQL SERVER PARA CONEXIONES REMOTAS")
    
    # 1. Verificar si SQL Server está ejecutándose
    print("Verificando servicios de SQL Server...")
    subprocess.run(["powershell", "-Command", "Get-Service -Name 'MSSQL*' | Select-Object Name, DisplayName, Status"], check=False)
    
    print("\n¿Qué deseas hacer?")
    print("1. Abrir SQL Server Configuration Manager")
    print("2. Activar el servicio SQL Browser")
    print("3. Configurar el firewall para permitir conexiones SQL Server")
    print("4. Volver a probar la conexión")
    print("5. Salir")
    
    choice = input("\nSelecciona una opción (1-5): ")
    
    if choice == "1":
        # Abrir SQL Server Configuration Manager
        print("Abriendo SQL Server Configuration Manager...")
        try:
            subprocess.Popen(["mmc", "/a", "SQLServerManager15.msc"], shell=True)
            print("\nEn SQL Server Configuration Manager:")
            print("1. Expande 'Configuración de red de SQL Server'")
            print("2. Selecciona 'Protocolos para MSSQLSERVER'")
            print("3. Habilita 'TCP/IP' (haz doble clic y cambia a 'Sí')")
            print("4. Haz clic derecho en 'TCP/IP' y selecciona 'Propiedades'")
            print("5. En la pestaña 'Direcciones IP', asegúrate que IPAll tenga puerto TCP = 1433")
            print("6. Reinicia el servicio 'SQL Server (MSSQLSERVER)' después")
        except Exception as e:
            print(f"Error: {e}")
            print("\nAlternativa: Busca 'SQL Server Configuration Manager' en el menú de inicio")
    
    elif choice == "2":
        # Activar el servicio SQL Browser
        print("Intentando activar SQL Browser...")
        try:
            subprocess.run(["powershell", "-Command", "Start-Service -Name SQLBrowser; Set-Service -Name SQLBrowser -StartupType Automatic"], shell=True)
            print("Verificando estado...")
            subprocess.run(["powershell", "-Command", "Get-Service -Name SQLBrowser | Select-Object Name, DisplayName, Status, StartType"], check=False)
        except Exception as e:
            print(f"Error: {e}")
            print("NOTA: Debes ejecutar este script como administrador")
    
    elif choice == "3":
        # Configurar el firewall
        print("Configurando reglas de firewall para SQL Server...")
        try:
            # Agregar regla para SQL Server (puerto 1433)
            subprocess.run([
                "powershell", "-Command",
                "New-NetFirewallRule -DisplayName 'SQL Server' -Direction Inbound -Protocol TCP -LocalPort 1433 -Action Allow"
            ], shell=True)
            
            # Agregar regla para SQL Browser (puerto 1434 UDP)
            subprocess.run([
                "powershell", "-Command",
                "New-NetFirewallRule -DisplayName 'SQL Browser' -Direction Inbound -Protocol UDP -LocalPort 1434 -Action Allow"
            ], shell=True)
            
            print("Reglas de firewall agregadas. Verificando...")
            subprocess.run([
                "powershell", "-Command",
                "Get-NetFirewallRule | Where-Object { $_.DisplayName -like '*SQL*' } | Select-Object DisplayName, Enabled, Direction, Action"
            ], check=False)
        except Exception as e:
            print(f"Error: {e}")
            print("NOTA: Debes ejecutar este script como administrador")
    
    elif choice == "4":
        # Volver a probar la conexión
        print("Ejecutando diagnóstico de conexión...")
        script_path = str(Path(__file__).parent / "diagnostico_sqlserver.py")
        subprocess.run([sys.executable, script_path], check=False)
    
    else:
        print("Saliendo...")
        return
    
    # Pausa para que el usuario pueda leer
    input("\nPresiona Enter para continuar...")
    main()  # Mostrar el menú nuevamente

if __name__ == "__main__":
    main()
