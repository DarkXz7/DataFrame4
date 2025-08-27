import socket

def obtener_mi_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "No encontrada"

ip = obtener_mi_ip()
print(f"Tu IP es: {ip}")
print(f"URL para compartir: http://{ip}:8000/subir-publico/")