# test_permisos.py
import os

def test_escritura():
    carpeta = r"C:\CarpetaCompartida"  # ← Nombre correcto
    archivo_test = os.path.join(carpeta, "test_django.txt")
    
    try:
        with open(archivo_test, 'w') as f:
            f.write("Prueba de escritura desde Django")
        
        if os.path.exists(archivo_test):
            os.remove(archivo_test)
            print("✅ Django PUEDE escribir en C:\CarpetaCompartida")
            return True
        else:
            print("❌ No se pudo crear el archivo")
            return False
            
    except PermissionError:
        print("❌ Sin permisos de escritura en C:\CarpetaCompartida")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_escritura()