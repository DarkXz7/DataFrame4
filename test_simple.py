import os

carpeta = r"C:\CarpetaCompartida"

print("=== PRUEBA SIMPLE ===")
print(f"1. ¿Existe la carpeta? {os.path.exists(carpeta)}")

if os.path.exists(carpeta):
    try:
        archivos = os.listdir(carpeta)
        print(f"2. Archivos encontrados: {len(archivos)}")
        for archivo in archivos:
            print(f"   - {archivo}")
    except Exception as e:
        print(f"2. Error: {e}")
else:
    print("2. Necesitas crear la carpeta primero")