# Configuración de Persistencia en Render.com con Disk

## Archivos que requieren persistencia

Tu aplicación maneja los siguientes archivos que necesitan persistencia:

### Base de datos:
- `constructora_icc.db` - Base de datos SQLite principal

### Archivos de configuración (Excel):
- `cuentas.xlsx` - Configuración de cuentas contables
- `UN.xlsx` - Configuración de centros de costos/unidades de negocio

### Archivos de datos (CSV):
- `facturas.csv` - Datos principales de facturas
- `facturas - copia.csv` - Respaldo de facturas
- `subidas.csv` - Registro de facturas subidas a KAME

## Problema con Render.com

Render.com utiliza un **sistema de archivos efímero**, lo que significa que:
- Los archivos se eliminan cada vez que se reinicia la aplicación
- Los cambios en archivos locales NO se mantienen entre despliegues
- La base de datos SQLite se pierde en cada reinicio

## Solución: Add Disk de Render (RECOMENDADO)

### ¿Qué es Add Disk?

**Add Disk** es una funcionalidad de Render que:
- Monta un SSD persistente en tu servicio
- Mantiene todos los archivos entre despliegues y reinicios
- Funciona como un disco duro tradicional
- **Costo:** $0.25/GB por mes

### Ventajas:
- ✅ **Solución simple:** No requiere cambios en tu código
- ✅ **Todo persiste:** Base de datos, Excel, CSV automáticamente
- ✅ **Económico:** Para tu proyecto (~10MB) = menos de $1/mes
- ✅ **Sin servicios externos:** Todo queda en Render

### Desventaja:
- ❌ **Zero-downtime deploys:** La app se reinicia al actualizar (pero es aceptable para la mayoría de casos)

## Configuración paso a paso

### 1. Añadir el disco en Render

1. **Ve a tu servicio** en el dashboard de Render
2. **Haz clic en "Settings"** en la barra lateral
3. **Busca la sección "Disks"**
4. **Haz clic en "Add Disk"**
5. **Configura el disco:**
   - **Name:** `app-data` (o cualquier nombre)
   - **Mount Path:** `/opt/render/project/data`
   - **Size:** `1 GB` (suficiente para tu proyecto)
6. **Haz clic en "Save"**

### 2. Modificar tu código para usar el disco

Edita `main.py` para usar el directorio persistente:

```python
import os

# Directorio persistente
PERSISTENT_DIR = "/opt/render/project/data"

# Asegurar que el directorio existe
if not os.path.exists(PERSISTENT_DIR):
    os.makedirs(PERSISTENT_DIR)

# Rutas de archivos persistentes
DATABASE = os.path.join(PERSISTENT_DIR, "constructora_icc.db")
FACTURAS_CSV = os.path.join(PERSISTENT_DIR, "facturas.csv")
SUBIDAS_CSV = os.path.join(PERSISTENT_DIR, "subidas.csv")
CUENTAS_XLSX = os.path.join(PERSISTENT_DIR, "cuentas.xlsx")
UN_XLSX = os.path.join(PERSISTENT_DIR, "UN.xlsx")
FACTURAS_COPIA_CSV = os.path.join(PERSISTENT_DIR, "facturas - copia.csv")
```

### 3. Actualizar funciones que usan archivos

```python
# Cambiar todas las referencias de archivos locales por las rutas persistentes

# En get_facturas()
def get_facturas(request: Request):
    # Cambiar:
    # df = pd.read_csv("facturas.csv")
    # Por:
    df = pd.read_csv(FACTURAS_CSV)

# En get_cuentas()
def get_cuentas(request: Request):
    # Cambiar:
    # df = pd.read_excel("cuentas.xlsx")
    # Por:
    df = pd.read_excel(CUENTAS_XLSX)

# En guardar_cuentas()
def guardar_cuentas(request: Request, data: dict):
    # Cambiar:
    # df.to_excel("cuentas.xlsx", index=False)
    # Por:
    df.to_excel(CUENTAS_XLSX, index=False)

# Y así para todos los archivos...
```

### 4. Función para migrar archivos existentes

Agrega esta función para migrar archivos existentes al disco persistente:

```python
def migrate_files_to_persistent_disk():
    """Migra archivos existentes al disco persistente"""
    archivos_locales = {
        "constructora_icc.db": DATABASE,
        "facturas.csv": FACTURAS_CSV,
        "subidas.csv": SUBIDAS_CSV,
        "cuentas.xlsx": CUENTAS_XLSX,
        "UN.xlsx": UN_XLSX,
        "facturas - copia.csv": FACTURAS_COPIA_CSV
    }
    
    for archivo_local, archivo_persistente in archivos_locales.items():
        if os.path.exists(archivo_local) and not os.path.exists(archivo_persistente):
            print(f"Migrando {archivo_local} a {archivo_persistente}")
            import shutil
            shutil.copy2(archivo_local, archivo_persistente)

@app.on_event("startup")
async def startup_event():
    # Migrar archivos existentes si es necesario
    migrate_files_to_persistent_disk()
    
    # Inicializar base de datos
    init_db()
```

### 5. Crear archivos por defecto si no existen

```python
def ensure_default_files():
    """Crea archivos por defecto si no existen"""
    
    # CSV de subidas
    if not os.path.exists(SUBIDAS_CSV):
        pd.DataFrame(columns=['idDocumento']).to_csv(SUBIDAS_CSV, index=False)
    
    # Excel de cuentas
    if not os.path.exists(CUENTAS_XLSX):
        pd.DataFrame(columns=['Orden', 'Cuenta', 'Centro de Costo Previred']).to_excel(CUENTAS_XLSX, index=False)
    
    # Excel de UN
    if not os.path.exists(UN_XLSX):
        pd.DataFrame(columns=['Orden', 'Unidad de Negocio', 'Centro de Costo Previred']).to_excel(UN_XLSX, index=False)
    
    # CSV de facturas (si no tienes el archivo inicial)
    if not os.path.exists(FACTURAS_CSV):
        # Crear estructura básica o copiar desde facturas - copia.csv
        if os.path.exists(FACTURAS_COPIA_CSV):
            import shutil
            shutil.copy2(FACTURAS_COPIA_CSV, FACTURAS_CSV)
        else:
            pd.DataFrame().to_csv(FACTURAS_CSV, index=False)

# Agregar a startup_event
@app.on_event("startup")
async def startup_event():
    migrate_files_to_persistent_disk()
    ensure_default_files()
    init_db()
```

## Resumen de cambios necesarios

### Archivos a modificar:
1. **main.py** - Cambiar todas las rutas de archivos
2. **funciones.py** - Actualizar rutas en funciones auxiliares (si las hay)

### Cambios específicos:
- Reemplazar `"constructora_icc.db"` por `DATABASE`
- Reemplazar `"facturas.csv"` por `FACTURAS_CSV`
- Reemplazar `"subidas.csv"` por `SUBIDAS_CSV`
- Reemplazar `"cuentas.xlsx"` por `CUENTAS_XLSX`
- Reemplazar `"UN.xlsx"` por `UN_XLSX`

## Costo total

Para tu proyecto con ~10MB de archivos:
- **1 GB de disco:** $0.25/mes
- **Total:** Menos de $1/mes

## Ventajas de esta solución

- **Simplicidad:** Solo cambias rutas en tu código
- **Compatibilidad:** Mantiene SQLite y todos tus archivos actuales
- **Economía:** Muy barato comparado con PostgreSQL + S3
- **Inmediato:** No requiere configuración de servicios externos

Esta es la solución más sencilla y económica para tu caso de uso.