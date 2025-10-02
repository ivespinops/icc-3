# Documentación del Módulo de Pagos

## Visión General

El módulo de Pagos es un sistema integral diseñado para gestionar y procesar pagos de facturas en una constructora. El sistema integra datos de múltiples fuentes, procesa certificados SII, gestiona cesiones de facturas y genera planillas de pagos compatibles con sistemas bancarios.

## Arquitectura del Sistema

### Estructura de Archivos
```
/pagos/
├── pagos.py                     # Lógica principal del módulo
├── templates/
│   ├── pagos_menu.html         # Menú principal del módulo
│   └── planilla_pagos.html     # Interfaz de planilla de pagos
└── main.py                     # Endpoints FastAPI
```

### Directorio Persistente
El sistema utiliza un directorio persistente (`/opt/render/project/data`) para almacenar:
- `resultado.xlsx` - Planilla principal
- `cesiones.xlsx` - Datos de cesiones procesados
- `resultados_cesiones.xlsx` - Cruce de resultados
- `pagos_mostrar.xlsx` - Datos para visualización
- `planilla_pagos_santander.xlsx` - Planilla final para Santander

## Componentes del Sistema

### 1. Búsqueda y Obtención de Facturas

#### `buscar_facturas()`
**Ubicación:** `pagos.py:18-99`

Función principal para obtener facturas desde la API de iConstruye.

**Parámetros principales:**
- `IdOrgc`: ID de la organización (-1 para todas)
- `FechaEmisDesde/FechaEmisHasta`: Rango de fechas de emisión
- Filtros opcionales: RazonSocialC, EstadoPago, EstadoDocumento, etc.

**Funcionalidad:**
- Consulta la API REST de iConstruye (`https://api.iconstruye.com/cvbf/api/Factura/Buscar`)
- Utiliza autenticación por clave API (`ICONSTRUYE_API_KEY`)
- Maneja timeouts y errores de conexión
- Retorna DataFrame de pandas con los resultados

**Flujo:**
1. Valida parámetros y construye query
2. Realiza petición HTTP GET a la API
3. Procesa respuesta JSON
4. Convierte a DataFrame y retorna datos

#### `buscar_nc()`
**Ubicación:** `pagos.py:101-182`

Similar a `buscar_facturas()` pero para Notas de Crédito.
- Endpoint: `https://api.iconstruye.com/cvbf/api/NotasCorreccion/Buscar`
- Misma estructura y lógica que búsqueda de facturas

### 2. Procesamiento de Planilla Principal

#### `preparar_planilla()`
**Ubicación:** `pagos.py:184-339`

Función principal que integra facturas y notas de crédito en una planilla unificada.

**Proceso de Transformación:**
1. **Obtención de datos:**
   - Busca facturas y NC por rango de fechas
   - Filtra columnas relevantes según mapeo predefinido

2. **Unificación de datos:**
   - Merge entre facturas y NC por `folioUnico` y `rutProveedor`
   - Renombra columnas para interfaz de usuario

3. **Cálculos financieros:**
   ```python
   # Cálculo de IVA
   IVA = Neto * 0.19 (si Tipo Factura == 'Factura Electrónica')
   
   # Monto Total
   Monto = Neto + IVA
   
   # Lógica de pagos
   Pagado = Monto (si Estado Pago == 'Pagada' OR Monto NC > 0)
   
   # Saldo pendiente
   Saldo = Monto - Pagado
   ```

4. **Determinación de pagos:**
   - Calcula fecha de pago (emisión + 30 días)
   - Determina si debe pagarse el viernes actual
   - Valida estado de aprobación (VB == "Aprobada")

5. **Persistencia:**
   - Guarda resultado en `resultado.xlsx`

### 3. Procesamiento de Certificados SII

#### `extraer_datos_sii()`
**Ubicación:** `pagos.py:341-444`

Extrae información de certificados de cesión desde PDFs del SII.

**Proceso de Extracción:**
1. **Análisis de texto:**
   - Utiliza `pdfplumber` para extraer texto del PDF
   - Divide el documento por folios usando regex

2. **Extracción de entidades:**
   ```regex
   # Patrones principales
   cesionario: r'cesionario\s+([^,]+),\s*RUT\s*N°\s*(\d{7,9}-[0-9Kk])'
   cedente: r'por el cedente\s+([^,]+),\s*RUT\s*N°\s*(\d{7,9}-[0-9Kk])'
   deudor: r'como deudor a\s+([^,]+),\s*RUT\s*N°\s*(\d{7,9}-[0-9Kk])'
   ```

3. **Identificación de facturas:**
   - Busca patrones de RUT y número de folio
   - Múltiples patrones de fallback para diferentes formatos

4. **Estructura de salida:**
   - DataFrame con información completa de cesiones
   - Incluye datos de todas las partes involucradas

#### `procesar_certificados()`
**Ubicación:** `pagos.py:446-479`

Wrapper principal para el procesamiento de certificados:
- Orquesta la extracción
- Maneja persistencia en directorio
- Guarda en `cesiones.xlsx`

### 4. Integración y Cruce de Datos

#### `cruzar_resultados_cesiones()`
**Ubicación:** `pagos.py:481-507`

Integra planilla principal con datos de cesiones.

**Lógica de cruce:**
- Join por `Rut` (emisor) y `Factura` (número)
- Agrega campos: Cesionario, Rut Cesionario, Cesión (Sí/No)
- Left join - mantiene todas las facturas originales

#### `cruzar_resultados_con_santander()`
**Ubicación:** `pagos.py:509-556`

Integra datos con información bancaria de Santander.

**Lógica condicional:**
```python
# Determina RUT a usar según cesión
rut_merge = rut_cesionario if cesion == "Sí" else rut_emisor_original

# Join con datos bancarios
merge(santander, left_on=rut_merge, right_on=rut_santander)
```

### 5. Generación de Planilla de Pagos

#### `crear_planilla_pagos()`
**Ubicación:** `pagos.py:558-621`

Genera la planilla final de pagos integrando todos los componentes.

**Proceso:**
1. **Carga de datos bancarios:**
   - Lee archivo `Santander.xlsx`
   - Valida existencia de archivo

2. **Integración de datos:**
   - Cruza resultados con datos bancarios
   - Calcula montos de transferencia

3. **Generación de metadatos:**
   ```python
   # Glosa personalizada
   "PAGO FACTURA " + numero_factura
   
   # Fecha de proceso
   viernes_actual = calculo_proximo_viernes()
   
   # Mensaje estándar
   f"PAGO PROVEEDORES {fecha_viernes}"
   ```

4. **Filtrado y limpieza:**
   - Elimina registros con monto 0
   - Valida RUTs completos
   - Genera dos archivos:
     - `pagos_mostrar.xlsx` (visualización)
     - `planilla_pagos_santander.xlsx` (procesamiento bancario)

## Flujo de Trabajo Completo

### 1. Preparación de Planilla Principal
```mermaid
graph TD
    A[Definir rango fechas] --> B[buscar_facturas()]
    A --> C[buscar_nc()]
    B --> D[Filtrar columnas]
    C --> D
    D --> E[Merge facturas + NC]
    E --> F[Calcular IVA, Monto, Saldo]
    F --> G[Determinar pagos por fecha]
    G --> H[Guardar resultado.xlsx]
```

### 2. Procesamiento de Cesiones
```mermaid
graph TD
    A[Subir PDF SII] --> B[extraer_datos_sii()]
    B --> C[Dividir por certificados]
    C --> D[Extraer entidades regex]
    D --> E[Identificar facturas]
    E --> F[Guardar cesiones.xlsx]
```

### 3. Integración Final
```mermaid
graph TD
    A[resultado.xlsx] --> C[cruzar_resultados_cesiones()]
    B[cesiones.xlsx] --> C
    C --> D[resultados_cesiones.xlsx]
    D --> E[cruzar_resultados_con_santander()]
    F[Santander.xlsx] --> E
    E --> G[crear_planilla_pagos()]
    G --> H[pagos_mostrar.xlsx]
    G --> I[planilla_pagos_santander.xlsx]
```

## API Endpoints

### Endpoints del Módulo (main.py)

#### Navegación
- `GET /pagos` - Menú principal del módulo
- `GET /pagos/planilla-pagos` - Interfaz de planilla de pagos

#### API de Planilla de Pagos
- `POST /api/pagos/planilla-pagos` - Genera planilla usando datos existentes
- `GET /api/pagos/planilla-pagos/cargar` - Carga planilla existente
- `POST /api/pagos/planilla-pagos/guardar` - Guarda cambios en planilla
- `GET /api/pagos/planilla-pagos/descargar-santander` - Descarga archivo Santander

## Submódulos del Sistema

### 1. Planilla Principal
**Función:** Generación de planilla base con facturas y cálculos financieros
**Archivos:** `planilla_principal.xlsx`, `resultado.xlsx`

### 2. Cesiones
**Función:** Procesamiento de certificados SII y gestión de cesiones
**Archivos:** PDF de entrada, `cesiones.xlsx`

### 3. Planilla Preliminar
**Función:** Cruce de planilla principal con cesiones
**Archivos:** `planilla_preliminar.xlsx`

### 4. Cuentas Bancarias
**Función:** Gestión de información bancaria
**Archivos:** `Santander.xlsx`, `cuentas_bancarias.xlsx`

### 5. Planilla de Pagos
**Función:** Generación final de archivos para procesamiento bancario
**Archivos:** `pagos_mostrar.xlsx`, `planilla_pagos_santander.xlsx`

## Configuración y Dependencias

### Variables de Entorno
```bash
ICONSTRUYE_API_KEY=clave_api_iconstruye
```

### Dependencias Python
```python
# Core
import pandas as pd
import numpy as np
import requests

# PDF Processing
import pdfplumber

# Utilities
import os
import re
import json
from datetime import datetime, timedelta
```

### Estructura de Datos

#### Campos de Facturas
```python
campos_facturas = {
    'folioUnico': 'Número único de factura',
    'fechaEmision': 'Fecha de emisión',
    'rutProveedor': 'RUT del proveedor',
    'nomProveedor': 'Nombre del proveedor',
    'estadoDoc': 'Estado del documento',
    'estadoPago': 'Estado de pago',
    'montoTotal': 'Monto total',
    'tipoFactura': 'Tipo de factura'
}
```

#### Campos de Cesiones
```python
campos_cesiones = {
    'cesionario_nombre': 'Nombre del cesionario',
    'cesionario_rut': 'RUT del cesionario',
    'cedente_nombre': 'Nombre del cedente',
    'cedente_rut': 'RUT del cedente',
    'deudor_nombre': 'Nombre del deudor',
    'rut_emisor': 'RUT emisor de la factura',
    'num_folio_documento': 'Número de folio'
}
```

## Manejo de Errores y Logging

### Estrategias de Error
1. **API Timeouts:** 30 segundos por defecto
2. **Archivos faltantes:** Creación de estructuras vacías
3. **Datos malformados:** Validación y limpieza automática
4. **Errores de parsing PDF:** Múltiples patrones de fallback

### Logging
```python
# Ejemplos de mensajes de log
print(f"📅 Consultando facturas por fecha de emisión desde {fecha_desde} hasta {fecha_hasta}")
print(f"📊 Total de facturas encontradas: {len(df)}")
print(f"✅ Planilla principal generada con {len(resultado)} registros")
```

## Casos de Uso Principales

### 1. Procesamiento Semanal de Pagos
1. Ejecutar preparación de planilla con fechas de la semana
2. Procesar certificados SII si existen cesiones
3. Generar planilla preliminar integrando datos
4. Cargar información bancaria actualizada
5. Generar planilla final para Santander

### 2. Gestión de Cesiones
1. Recibir PDF de certificados SII
2. Extraer información de cesiones automáticamente
3. Actualizar base de datos de cesiones
4. Regenerar planillas afectadas

### 3. Consulta y Filtrado
1. Buscar facturas por múltiples criterios
2. Filtrar por estado, proveedor, monto
3. Exportar subconjuntos específicos
4. Generar reportes personalizados

## Consideraciones Técnicas

### Performance
- Procesamiento en lotes para grandes volúmenes
- Caching de consultas API frecuentes
- Optimización de operaciones pandas para DataFrames grandes

### Seguridad
- Autenticación API mediante variables de entorno
- Validación de entrada para prevenir inyecciones
- Manejo seguro de archivos temporales

### Escalabilidad
- Diseño modular para fácil extensión
- Separación de lógica de negocio y presentación
- API REST para integración con otros sistemas

---

*Esta documentación describe la versión actual del módulo de Pagos. Para actualizaciones o modificaciones, consultar el código fuente y los comentarios inline.*