import os
import django
import sys

# Configurar Django
sys.path.append(r'C:\Users\migue\OneDrive\Escritorio\propuesta proyecto')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cargador.settings')
django.setup()

from archivos.models import CarpetaCompartida

def corregir_rutas():
    print("=== CORRIGIENDO RUTAS DE CARPETAS ===")
    
    carpetas = CarpetaCompartida.objects.all()
    
    for carpeta in carpetas:
        print(f"Carpeta: {carpeta.nombre}")
        print(f"Ruta actual: {carpeta.ruta}")
        
        # Si la ruta es incorrecta, corregirla
        if carpeta.ruta != r"C:\CarpetaCompartida":
            carpeta.ruta = r"C:\CarpetaCompartida"
            carpeta.save()
            print(f"✅ Corregida a: C:\\CarpetaCompartida")
        else:
            print(f"✅ Ruta ya es correcta")
        
        # Verificar que la carpeta existe
        if os.path.exists(carpeta.ruta):
            print(f"✅ La carpeta existe")
        else:
            print(f"❌ La carpeta NO existe - créala con: mkdir {carpeta.ruta}")
        
        print("-" * 50)
    
    if not carpetas.exists():
        print("❌ No hay carpetas configuradas")
        print("Creando carpeta por defecto...")
        
        CarpetaCompartida.objects.create(
            nombre="Archivos Compartidos",
            ruta=r"C:\CarpetaCompartida",
            descripcion="Carpeta principal para archivos compartidos",
            activa=True
        )
        print("✅ Carpeta creada en la base de datos")

if __name__ == "__main__":
    corregir_rutas()