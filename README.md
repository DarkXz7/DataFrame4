# 📂 Módulo de Subida y Procesamiento de Archivos a la Base de Datos

Este módulo implementado en **Django** permite subir archivos locales (`Excel`, `CSV`, `TXT`) o archivos de base de datos (`.sql`), procesarlos y almacenarlos en **MySQL/MariaDB** de forma automatizada.  
Además, soporta **carpetas compartidas** para que varios usuarios puedan ver y cargar archivos en una ruta común.

---

## 🚀 Funcionalidades principales

- Subida de archivos locales (`Excel`, `CSV`, `TXT`).
- Conexión directa a bases de datos **MySQL/MariaDB**.
- Subida de archivos **`.sql`** con ejecución automática en la base conectada.
- Exploración de carpetas compartidas con archivos disponibles.
- Selección de **tablas y columnas** en tiempo real antes de importarlas.
- Normalización de columnas (nombres sin espacios, valores como `"15 días" → 15`).
- Guardado automático en la base destino (`replace` si ya existe la tabla).
- Limpieza de sesión al volver al **index**, evitando archivos huérfanos.

---

## 📂 Estructura del módulo


archivos/
├── models.py # Modelos: Carpetas, archivos detectados, procesados y cargados
├── views.py # Lógica principal: subir, procesar, conectar a MySQL, importar SQL
├── urls.py # Rutas del módulo
├── custom_filters.py # Filtros personalizados para plantillas
├── dict_extras.py # Filtros para diccionarios
├── templates/archivos/ # Vistas HTML
│ ├── subir_desde_mysql.html
│ ├── subir_sql.html
│ ├── seleccionar_tablas.html
│ └── (otras plantillas de archivos locales y carpetas)
└── uploads/ # Carpeta donde se guardan los archivos procesados

## ⚙️ Flujo de trabajo

### 1. **Inicio (`index`)**
- Muestra carpetas activas y archivos recientes.
- Limpia la sesión (para no arrastrar archivos anteriores).

### 2. **Conexión a MySQL/MariaDB**
- Formulario (`subir_desde_mysql.html`) para ingresar:
  - Host, puerto, usuario, contraseña y base de datos.
- Se guarda la conexión en la sesión (`engine_url`).
- Redirige a la vista de **subida de SQL**.

### 3. **Subir archivo SQL**
- En `subir_sql.html`, el usuario carga un archivo `.sql`.
- El sistema:
  - Lo procesa temporalmente.
  - Ejecuta comandos `DROP TABLE IF EXISTS` + `CREATE TABLE`.
  - Importa el contenido en la base conectada.
- Obtiene la lista de tablas creadas y redirige a **selección de tablas**.

### 4. **Seleccionar Tablas y Columnas**
- En `seleccionar_tablas.html` se muestran todas las tablas detectadas.
- El usuario puede:
  - Marcar qué tablas quiere importar.
  - Seleccionar columnas específicas de cada tabla.
- Se normalizan nombres y valores.
- Los datos se guardan en la base con `replace`.

### 5. **Confirmación y regreso al Index**
- Se muestra mensaje de éxito.
- Al volver al `index`, se limpia la sesión y queda listo para una nueva subida.

---

## 🖥️ Ejemplo de uso

1. **Subir archivo SQL (`prueba1.sql`)**  
   - Se conecta a la base `prueba2`.  
   - Se ejecuta el script `.sql`.  

2. **Seleccionar tablas**  
   ```text
   [✔] personas
   [✔] facturas
   [ ] clientes


## 🖥️ Requisitos Tecnicos
   Django>=4.0
pandas
sqlalchemy
pymysql
openpyxl
humanize
