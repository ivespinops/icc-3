import os
import requests
import pandas as pd
import json
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
import csv
import pdfplumber
import pandas as pd
import numpy as np
import re
from calendar import monthrange
from dateutil.relativedelta import relativedelta

load_dotenv()
API_KEY = os.getenv("ICONSTRUYE_API_KEY")
if not API_KEY:
    print("⚠️ ADVERTENCIA: La clave API no está definida en el archivo .env")
    API_KEY = None

def buscar_facturas(IdOrgc,
                    recep_desde,
                    recep_hasta,
                    api_version="1.0",
                    RazonSocialC=None,
                    FolioCompIngreso=None,
                    NroDocumento=None,
                    OrigenFactura=None,
                    TipoFactura=None,
                    TipoDocAsociado=None,
                    Proveedor=None,
                    EstadoAsociacion=None,
                    EstadoDocumento=None,
                    EstadoPago=None,
                    Foliounico=None,
                    FechaSistDesde=None,
                    FechaSistHasta=None,
                    TipoReferencia=None,
                    FechaEmisDesde= None,
                    FechaEmisHasta= None,
                    info=None):
    
    print(f"📅 Consultando facturas por fecha de emisión desde {FechaEmisDesde} hasta {FechaEmisHasta}")
    
    if not API_KEY:
        print("❌ Error: No se puede consultar facturas sin la clave API")
        return pd.DataFrame()
    
    url_base = "https://api.iconstruye.com/cvbf/api/Factura/Buscar"
    headers = {
        "Ocp-Apim-Subscription-Key": API_KEY
    }

    recep_desde = recep_desde
    recep_hasta = recep_hasta

    params = {
        "IdOrgc": IdOrgc,
        "FechaRecepDesde": recep_desde,
        "FechaRecepHasta": recep_hasta,
        "api-version": api_version
    }

    opcionales = {
        "RazonSocialC": RazonSocialC,
        "FolioCompIngreso": FolioCompIngreso,
        "NroDocumento": NroDocumento,
        "OrigenFactura": OrigenFactura,
        "TipoFactura": TipoFactura,
        "TipoDocAsociado": TipoDocAsociado,
        "Proveedor": Proveedor,
        "EstadoAsociacion": EstadoAsociacion,
        "EstadoDocumento": EstadoDocumento,
        "EstadoPago": EstadoPago,
        "Foliounico": Foliounico,
        "FechaSistDesde": FechaSistDesde,
        "FechaSistHasta": FechaSistHasta,
        "TipoReferencia": TipoReferencia,
        "info": info
    }

    for key, value in opcionales.items():
        if value is not None:
            params[key] = value

    try:
        response = requests.get(url_base, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and data:
            df = pd.DataFrame(data)
            print(f"📊 Total de facturas encontradas: {len(df)}")
            return df
        else:
            print("⚠️ No se encontraron facturas para ese rango de emisión.")
            return pd.DataFrame()

    except requests.exceptions.HTTPError as http_err:
        print(f"❌ Error HTTP: {http_err}")
    except requests.exceptions.Timeout:
        print("⏱️ Error: tiempo de espera agotado al consultar la API.")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error de conexión o de API: {e}")

    return pd.DataFrame()

def buscar_nc(IdOrgc,
              recep_desde,
              recep_hasta,
              FechaEmisDesde=None,
              FechaEmisHasta=None,
              api_version="1.0",
              RazonSocialC=None,
              FolioCompIngreso=None,
              NroDocumento=None,
              OrigenFactura=None,
              TipoFactura=None,
              TipoDocAsociado=None,
              Proveedor=None,
              EstadoAsociacion=None,
              EstadoDocumento=None,
              EstadoPago=None,
              Foliounico=None,
              FechaSistDesde=None,
              FechaSistHasta=None,
              TipoReferencia=None,
              info=None):
    
    print(f"📅 Consultando NC por fecha de recepción desde {recep_desde} hasta {recep_hasta}")
    
    if not API_KEY:
        print("❌ Error: No se puede consultar notas de crédito sin la clave API")
        return pd.DataFrame()
    
    url_base = "https://api.iconstruye.com/cvbf/api/NotasCorreccion/Buscar"
    headers = {
        "Ocp-Apim-Subscription-Key": API_KEY
    }


    params = {
        "IdOrgc": IdOrgc,
        "FechaRecepDesde": recep_desde,
        "FechaRecepHasta": recep_hasta,
        "api-version": api_version
    }

    opcionales = {
        "RazonSocialC": RazonSocialC,
        "FolioCompIngreso": FolioCompIngreso,
        "NroDocumento": NroDocumento,
        "OrigenFactura": OrigenFactura,
        "TipoFactura": TipoFactura,
        "TipoDocAsociado": TipoDocAsociado,
        "Proveedor": Proveedor,
        "EstadoAsociacion": EstadoAsociacion,
        "EstadoDocumento": EstadoDocumento,
        "EstadoPago": EstadoPago,
        "Foliounico": Foliounico,
        "FechaSistDesde": FechaSistDesde,
        "FechaSistHasta": FechaSistHasta,
        "TipoReferencia": TipoReferencia,
        "info": info,
        "FechaEmisDesde":FechaEmisDesde,
        "FechaEmisHasta":FechaEmisHasta
    }

    for key, value in opcionales.items():
        if value is not None:
            params[key] = value

    try:
        response = requests.get(url_base, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and data:
            df = pd.DataFrame(data)
            print(f"📊 Total de Notas de Crédito encontradas: {len(df)}")
            return df
        else:
            print("⚠️ No se encontraron Notas de Crédito para ese rango de emisión.")
            return pd.DataFrame()

    except requests.exceptions.HTTPError as http_err:
        print(f"❌ Error HTTP: {http_err}")
    except requests.exceptions.Timeout:
        print("⏱️ Error: tiempo de espera agotado al consultar la API.")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error de conexión o de API: {e}")

    return pd.DataFrame()


def preparar_planilla(fecha_inicio, fecha_fin):
    facturas = buscar_facturas(-1, fecha_inicio,fecha_fin)
    nc = buscar_nc(-1, fecha_inicio, fecha_fin)

    print(facturas.columns)
    # Diccionario de mapeo: columna de la foto -> columna real del DataFrame
    columnas_facturas = {
        'N° Factura': 'folioUnico',
        'Fecha de Emisión': 'fechaEmision',
        'RUT Facturador': 'rutProveedor',
        'Proveedor Facturador': 'nomProveedor',  
        'Estado Documento': 'estadoDoc',
        'Centro Gestión': 'centroGestion',   
        'Tipo Factura': 'tipoFactura',
        'Monto Total': 'montoTotal',        
        'Estado Asociación': 'estadoAsociacion',
        'Estado Pago': 'estadoPago'
    }
    
    # Filtrar el DataFrame 'facturas' para que solo tenga las columnas de la foto
    facturas_filtradas = facturas[list(columnas_facturas.values())]

    # Diccionario de mapeo: columna de la foto -> columna real del DataFrame
    columnas_nc = {
        'N° OC': 'numDoc',
        'Factura Asocida': 'factAsociada',
        'Proveedor Facturador': 'nombreProveedor',
        'RUT Facturador': 'rutProveedor',
        'Centro Gestión': 'centroGestion',
        'Fecha de Emisión': 'fechaEmision',
        'Monto Total': 'montoTotal',
        'Estado Documento': 'estadoDoc',
        'Estado Asociación': 'estadoAsociacion',
    }
    
    # Filtrar el DataFrame 'facturas' para que solo tenga las columnas de la foto
    nc_filtradas = nc[list(columnas_nc.values())]

    # Cruce entre facturas_filtradas y nc_filtradas
    resultado = facturas_filtradas.merge(
        nc_filtradas[['factAsociada', 'rutProveedor', 'numDoc', 'montoTotal']],
        left_on=['folioUnico', 'rutProveedor'],
        right_on=['factAsociada', 'rutProveedor'],
        how='left'
    )
    
    # Renombrar columnas
    resultado = resultado.rename(columns={
        'numDoc_y': 'Numero NC',
        'montoTotal_y': 'Monto NC'
    })
    
    # Eliminar columnas extra
    resultado = resultado.drop(columns=['factAsociada'])
    
    # Ajustar nombres si hay columnas duplicadas por el merge
    resultado = resultado.rename(columns={
        'numDoc_x': 'numDoc',
        'montoTotal_x': 'montoTotal'
    })

    resultado = resultado.rename(columns={
        'folioUnico': 'Factura',
        'fechaEmision': 'Fecha Emisión',
        'rutProveedor': 'Rut',
        'nomProveedor': 'Razón Social',
        'estadoDoc': 'VB',
        'centroGestion': 'Centro de Gestión',
        'tipoFactura': 'Tipo Factura',
        'montoTotal': 'Monto Total',
        'estadoAsociacion': 'Asociación',
        'estadoPago': 'Estado de Pago',
        'numDoc': 'Número NC',
        'Monto NC': 'Monto NC'
    })

    # Asegurarnos que "Fecha Emisión" sea de tipo datetime
    resultado['Fecha Emisión'] = pd.to_datetime(resultado['Fecha Emisión'], errors='coerce')
    
    # Crear la nueva columna "Fecha de Pago"
    resultado['Fecha de Pago'] = resultado['Fecha Emisión'] + pd.Timedelta(days=30)
    
    # Reordenar columnas para que "Fecha de Pago" quede después de "Fecha Emisión"
    cols = list(resultado.columns)
    pos = cols.index('Fecha Emisión') + 1  # posición después de Fecha Emisión
    cols = cols[:pos] + ['Fecha de Pago'] + cols[pos:-1] + [cols[-1]]
    
    resultado = resultado[cols]

    # Eliminar espacios al inicio y final en la columna Tipo Factura
    resultado['Tipo Factura'] = resultado['Tipo Factura'].str.strip()

    # Ahora sí: por fila
    resultado["Neto"] = resultado.apply(
        lambda row: row["Monto Total"] * 100 / 119
                    if row['Tipo Factura'] == 'Factura Electrónica'
                    else row["Monto Total"],
        axis=1
    )

    # Crear columna IVA con condición
    resultado['IVA'] = resultado.apply(
        lambda row: row['Neto'] * 0.19 if row['Tipo Factura'] == 'Factura Electrónica' else 0,
        axis=1
    )
    
    # Crear columna Monto (Monto Total + IVA)
    resultado['Monto'] = resultado['Neto'] + resultado['IVA']
    
    # Reordenar columnas para que IVA quede después de Monto Total y Monto después de IVA
    cols = list(resultado.columns)
    pos_monto_total = cols.index('Neto') + 1
    cols = cols[:pos_monto_total] + ['IVA', 'Monto'] + [c for c in cols if c not in ['IVA', 'Monto']]
    
    resultado = resultado[cols]

    
    # Eliminar columnas duplicadas conservando solo la primera aparición
    resultado = resultado.loc[:, ~resultado.columns.duplicated()]
    # Eliminar espacios en la columna Estado de Pago
    resultado["Estado de Pago"] = resultado["Estado de Pago"].astype(str).str.strip()
    
    def calcular_pagado(row):
        if row['Estado de Pago'] == 'Pagada':
            return row['Monto']
        elif row['Monto NC'] > 0:
            return (row['Monto NC'])
        else:
            return 0
    
    resultado['Pagado'] = resultado.apply(calcular_pagado, axis=1)
    
    # Reordenar para que "Pagado" quede después de "Monto"
    cols = list(resultado.columns)
    pos_monto = cols.index('Monto') + 1
    cols = cols[:pos_monto] + ['Pagado'] + [c for c in cols if c != 'Pagado']
    
    resultado = resultado[cols]

    # Eliminar columnas repetidas conservando la primera aparición
    resultado = resultado.loc[:, ~resultado.columns.duplicated()]

    # Crear la columna "Saldo" = Monto - Pagado
    resultado['Saldo'] = resultado['Monto'] - resultado['Pagado']
    
    # Reordenar para que "Saldo" quede después de "Pagado"
    cols = list(resultado.columns)
    pos_pagado = cols.index('Pagado') + 1
    cols = cols[:pos_pagado] + ['Saldo'] + [c for c in cols if c != 'Saldo']
    
    resultado = resultado[cols]
   

    # Eliminar columnas repetidas conservando la primera aparición
    resultado = resultado.loc[:, ~resultado.columns.duplicated()]

    # Asegurarnos que la columna "Fecha de Pago" sea datetime
    resultado['Fecha de Pago'] = pd.to_datetime(resultado['Fecha de Pago'], errors='coerce')
    
    # Calcular el viernes de la semana actual
    hoy = datetime.now()
    dias_hasta_viernes = (4 - hoy.weekday()) % 7  # lunes=0, viernes=4
    viernes_actual = hoy + timedelta(days=dias_hasta_viernes)
    viernes_actual = viernes_actual.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Crear columna "A pagar" con condición extra de Saldo > 0
    resultado['A pagar'] = resultado.apply(
        lambda row: "Sí" if pd.notnull(row['Fecha de Pago']) 
                               and row['Fecha de Pago'] <= viernes_actual 
                               and row['Saldo'] > 0
                               and row['VB'] == "Aprobada"
                    else "No",
        axis=1
    )

    resultado["Monto Pago"] = np.where(resultado["A pagar"] == "Sí", resultado["Saldo"], np.nan)
    
    print(f"Viernes de esta semana: {viernes_actual.date()}")
    print(resultado[['Fecha de Pago', 'Saldo', 'A pagar']].head())



    return resultado      

def extraer_datos_sii(pdf_path: str) -> pd.DataFrame:
    """
    Extrae los datos específicos de los certificados SII.
    """
    
    datos = []
    
    with pdfplumber.open(pdf_path) as pdf:
        texto_completo = ""
        
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
    
    certificados = re.split(r'Folio N°\s*:\s*\d+', texto_completo)
    
    for i, certificado in enumerate(certificados[1:], 1):
        
        cesionario_match = re.search(r'cesionario\s+([^,]+),\s*RUT\s*N°\s*(\d{7,9}-[0-9Kk])', certificado, re.IGNORECASE)
        cesionario_nombre = cesionario_match.group(1).strip() if cesionario_match else None
        cesionario_rut = cesionario_match.group(2) if cesionario_match else None
        
        if cesionario_rut:
            domicilio_cesionario_match = re.search(rf'RUT N° {re.escape(cesionario_rut)},\s*domiciliado en\s+([^,]+)', certificado)
            cesionario_domicilio = domicilio_cesionario_match.group(1).strip() if domicilio_cesionario_match else None
        else:
            cesionario_domicilio = None
        
        cedente_match = re.search(r'por el cedente\s+([^,]+),\s*RUT\s*N°\s*(\d{7,9}-[0-9Kk])', certificado, re.IGNORECASE)
        cedente_nombre = cedente_match.group(1).strip() if cedente_match else None
        cedente_rut = cedente_match.group(2) if cedente_match else None
        
        if cedente_rut:
            domicilio_cedente_match = re.search(rf'RUT N° {re.escape(cedente_rut)},\s*domiciliado en\s+([^,]+)', certificado)
            cedente_domicilio = domicilio_cedente_match.group(1).strip() if domicilio_cedente_match else None
        else:
            cedente_domicilio = None
        
        deudor_match = re.search(r'como deudor a\s+([^,]+),\s*RUT\s*N°\s*(\d{7,9}-[0-9Kk])', certificado, re.IGNORECASE)
        deudor_nombre = deudor_match.group(1).strip() if deudor_match else None
        deudor_rut = deudor_match.group(2) if deudor_match else None
        
        if deudor_rut:
            domicilio_deudor_match = re.search(rf'RUT N° {re.escape(deudor_rut)},\s*domiciliado en\s+([^.]+)', certificado)
            deudor_domicilio = domicilio_deudor_match.group(1).strip() if domicilio_deudor_match else None
        else:
            deudor_domicilio = None
        
        tabla_pattern = r'(\d{7,9}-[0-9Kk])\s+(\d+)'
        facturas = re.findall(tabla_pattern, certificado)
        
        if not facturas:
            tabla_pattern2 = r'FACTURA\s+ELECTRONICA\s+(\d{7,9}-[0-9Kk])\s+(\d+)'
            facturas = re.findall(tabla_pattern2, certificado)
            facturas = [(f[0], f[1]) for f in facturas]
        
        if not facturas:
            lineas = certificado.split('\n')
            for linea in lineas:
                if 'FACTURA' in linea and 'ELECTRONICA' in linea:
                    rut_match = re.search(r'(\d{8,9}-[\dK])', linea)
                    folio_match = re.search(r'\b(\d{2,4})\b', linea)
                    if rut_match and folio_match:
                        facturas.append((rut_match.group(1), folio_match.group(1)))
        
        print(f"Certificado {i}:")
        print(f"  Cesionario: {cesionario_nombre} - {cesionario_rut}")
        print(f"  Cedente: {cedente_nombre} - {cedente_rut}")
        print(f"  Deudor: {deudor_nombre} - {deudor_rut}")
        print(f"  Facturas: {facturas}")
        print("-" * 40)
        
        if facturas:
            for rut_emisor, folio in facturas:
                datos.append({
                    'cesionario_nombre': cesionario_nombre,
                    'cesionario_rut': cesionario_rut,
                    'cesionario_domicilio': cesionario_domicilio,
                    'cedente_nombre': cedente_nombre,
                    'cedente_rut': cedente_rut,
                    'cedente_domicilio': cedente_domicilio,
                    'deudor_nombre': deudor_nombre,
                    'deudor_rut': deudor_rut,
                    'deudor_domicilio': deudor_domicilio,
                    'rut_emisor': rut_emisor,
                    'tipo_documento': 'FACTURA ELECTRONICA',
                    'num_folio_documento': folio
                })
        else:
            datos.append({
                'cesionario_nombre': cesionario_nombre,
                'cesionario_rut': cesionario_rut,
                'cesionario_domicilio': cesionario_domicilio,
                'cedente_nombre': cedente_nombre,
                'cedente_rut': cedente_rut,
                'cedente_domicilio': cedente_domicilio,
                'deudor_nombre': deudor_nombre,
                'deudor_rut': deudor_rut,
                'deudor_domicilio': deudor_domicilio,
                'rut_emisor': None,
                'tipo_documento': None,
                'num_folio_documento': None
            })
    
    return pd.DataFrame(datos)

def procesar_certificados(pdf_path: str):
    """
    Procesa el PDF y extrae los datos.
    """
    print(f"Procesando archivo: {pdf_path}")
    
    df = extraer_datos_sii(pdf_path)
    
    if df.empty:
        print("No se encontraron datos")
        return df
    
    print(f"\nTotal de registros: {len(df)}")
    print(f"Cesionarios únicos: {df['cesionario_nombre'].nunique()}")
    
    # Definir directorio persistente
    PERSISTENT_DIR = "/opt/render/project/data"
    
    # Asegurar que el directorio existe
    if not os.path.exists(PERSISTENT_DIR):
        os.makedirs(PERSISTENT_DIR)
    
    return df

def cruzar_resultados_cesiones(resultados: pd.DataFrame, cesiones: pd.DataFrame):
    """
    Cruza dos DataFrames:
    - resultados: columnas 'Rut' y 'Factura'
    - cesiones: columnas 'rut_emisor' y 'num_folio_documento'
    
    Agrega a 'resultados':
      - 'Cesionario' (desde 'cesionario_nombre')
      - 'Rut Cesionario' (desde 'cesionario_rut')
      - 'Cesión' (Sí/No según cruce)

    Retorna:
      - df_merged: resultados con cesiones cruzadas
      - cesiones_no_cruzadas: cesiones que no se encontraron en resultados
    """
    # Renombrar columnas de cesiones para un merge claro
    cesiones_ren = cesiones.rename(columns={
        "rut_emisor": "Rut",
        "num_folio_documento": "Factura",
        "cesionario_nombre": "Cesionario",
        "cesionario_rut": "Rut Cesionario"
    })
    
    # Cruce con left join
    df_merged = resultados.merge(
        cesiones_ren[["Rut", "Factura", "Cesionario", "Rut Cesionario"]],
        on=["Rut", "Factura"],
        how="left"
    )
    
    # Crear columna Cesión
    df_merged["Cesión"] = df_merged["Cesionario"].notna().map({True: "Sí", False: "No"})

    # Identificar cesiones no cruzadas (facturas de cesiones que no están en resultados)
    cesiones_no_cruzadas = cesiones_ren.merge(
        resultados[["Rut", "Factura"]],
        on=["Rut", "Factura"],
        how="left",
        indicator=True
    ).query("_merge == 'left_only'").drop(columns="_merge")

    return df_merged, cesiones_no_cruzadas

def actualizar_fecha_pago(df: pd.DataFrame) -> pd.DataFrame:
    """
    Actualiza las columnas 'Fecha de Pago' y 'A pagar':
    
    1. Si 'Cesión' == "Sí" → 'Fecha de Pago' = 'Fecha Emisión' + 60 días
    2. Si el viernes de la semana actual > 'Fecha de Pago' → 'A pagar' = 'No'
       En otros casos, 'A pagar' se mantiene igual
    
    Parámetros:
        df (pd.DataFrame): DataFrame con columnas 'Cesión', 'Fecha Emisión', 'Fecha de Pago', 'A pagar'
    
    Retorna:
        pd.DataFrame con las columnas actualizadas
    """
    # Copia para no modificar el original
    df = df.copy()

    # Asegurar fechas en formato datetime
    df["Fecha Emisión"] = pd.to_datetime(df["Fecha Emisión"], errors="coerce")
    df["Fecha de Pago"] = pd.to_datetime(df["Fecha de Pago"], errors="coerce")

    # 1. Actualizar Fecha de Pago si hay Cesión y Monto >= 10.000.000
    mask_cesion = (df["Cesión"] == "Sí") & (df["Monto"] >= 10_000_000)
    df.loc[mask_cesion, "Fecha de Pago"] = df.loc[mask_cesion, "Fecha Emisión"] + pd.Timedelta(days=60)


    # 2. Calcular viernes de la semana actual
    hoy = pd.Timestamp.today().normalize()
    viernes = hoy + pd.offsets.Week(weekday=4)  # 4 = viernes
    print(viernes)
    # 3. Actualizar columna "A pagar"
    mask_fecha_vencida = df["Fecha de Pago"].notna() & (viernes < df["Fecha de Pago"])
    df.loc[mask_fecha_vencida, "A pagar"] = "No"
    df.loc[mask_fecha_vencida, "Monto Pago"] = 0

    return df

def filtrar_a_pagar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Devuelve las filas donde 'A pagar' == 'Sí'.
    Tolera mayúsculas/minúsculas, espacios y falta de acento (Si/SÍ/sí).
    """
    if "A pagar" not in df.columns:
        raise KeyError(f"No existe la columna 'A pagar'. Columnas disponibles: {list(df.columns)}")

    col = df["A pagar"].astype(str).str.strip()
    # Normaliza: quita acentos y pasa a minúsculas
    col_norm = (col.str.normalize("NFKD")
                   .str.encode("ascii", errors="ignore")
                   .str.decode("utf-8")
                   .str.lower())

    mask = col_norm.eq("si")
    return df.loc[mask].copy()


def cruzar_resultados_con_santander(
    resultados: pd.DataFrame,
    santander: pd.DataFrame,
    col_santander_key: str = "RUT beneficiario\n(obligatorio solo si banco destino no es Santander)"
) -> pd.DataFrame:
    import numpy as np
    import pandas as pd
    import re

    # --- helpers ---
    def limpiar_rut_series(s: pd.Series) -> pd.Series:
        # Usa dtype "string" para preservar <NA> y no convertir NaN->"nan"
        s = s.astype("string")
        s = s.str.replace("-", "", regex=False)
        s = s.str.replace(".", "", regex=False)
        s = s.str.replace(r"\s+", "", regex=True)
        s = s.str.upper()
        return s

    def pick_col(df: pd.DataFrame, opciones) -> str | None:
        for op in opciones:
            if op in df.columns:
                return op
        # fallback tolerante a espacios/nuevas líneas/paréntesis
        norm = {re.sub(r"\s+", " ", c).strip().casefold(): c for c in df.columns}
        for op in opciones:
            key = re.sub(r"\s+", " ", op).strip().casefold()
            if key in norm:
                return norm[key]
        return None

    # --- validaciones básicas ---
    if col_santander_key not in santander.columns:
        raise KeyError(
            f"No se encontró la columna clave en 'santander': {col_santander_key}\n"
            f"Columnas disponibles: {list(santander.columns)}"
        )

    res = resultados.copy()
    san = santander.copy()

    # --- 0) Filtrar A pagar == "Sí" ---
    if "A pagar" not in res.columns:
        raise KeyError("No se encontró la columna 'A pagar' en 'resultados'.")
    res = res[res["A pagar"].astype(str).str.strip() == "Sí"].copy()
    if res.empty:
        razon_col = "Razón Social" if "Razón Social" in resultados.columns else (
            "Razon Social" if "Razon Social" in resultados.columns else None
        )
        base_cols = ["RUT"] + ([razon_col] if razon_col else [])
        return pd.DataFrame(columns=base_cols + list(san.columns))

    # --- 1) LIMPIAR SANTANDER: exigir "Cuenta destino (obligatorio)" no vacía ---
    cta_col = pick_col(san, ["Cuenta destino\n(obligatorio)", "Cuenta destino (obligatorio)", "Cuenta destino"])
    if cta_col:
        cta = san[cta_col].astype("string")
        san = san[cta.notna() & (cta.str.strip() != "")]
    # Si no existe la columna, no filtramos y seguimos (puede ser otra versión del layout)

    # --- 2) Determinar RUT a usar según Cesión ---
    rut_base = limpiar_rut_series(res.get("Rut", pd.Series(index=res.index, dtype="string")))
    rut_ces  = limpiar_rut_series(res.get("Rut Cesionario", pd.Series(index=res.index, dtype="string")))
    cesion   = res.get("Cesión", pd.Series(index=res.index, dtype="string")).fillna("No")
    res["__rut_merge__"] = np.where(cesion.astype(str).str.strip() == "Sí", rut_ces, rut_base)

    # --- 3) Preparar clave derecha y deduplicar por RUT ---
    san["__rut_merge__"] = limpiar_rut_series(san[col_santander_key])
    san_no_na = san.dropna(subset=["__rut_merge__"]).copy()

    # Si hay múltiples filas por el mismo RUT, quédate con la primera (ajusta la regla si quieres)
    san_no_na = san_no_na.drop_duplicates(subset="__rut_merge__", keep="first")

    # --- 4) Merge many-to-one (nos avisa si vuelve a haber duplicados a la derecha) ---
    merged = res.merge(
        san_no_na,
        on="__rut_merge__",
        how="left",
        suffixes=("_res", ""),
        validate="many_to_one"
    )

    # --- 5) Salida: RUT usado + Razón Social + columnas Santander ---
    merged["RUT"] = merged["__rut_merge__"]

    razon_col_src = "Razón Social" if "Razón Social" in res.columns else (
        "Razon Social" if "Razon Social" in res.columns else None
    )
    front_cols = ["RUT"]
    if razon_col_src:
        merged["Razón Social"] = merged[razon_col_src]
        front_cols.append("Razón Social")

    santander_cols = [c for c in san.columns if c not in {"__rut_merge__"}]
    final_cols = [c for c in (front_cols + santander_cols) if c in merged.columns]

    out = merged[final_cols].copy().reset_index(drop=True)
    return merged

def crear_planilla_pagos(resultados):
    import os
    
    # Definir directorio persistente
    PERSISTENT_DIR = "/opt/render/project/data"
    
    # Asegurar que el directorio existe
    if not os.path.exists(PERSISTENT_DIR):
        os.makedirs(PERSISTENT_DIR)
    
    # Buscar archivo Santander
    santander_path = None
    possible_paths = [
        os.path.join(PERSISTENT_DIR, "Santander.xlsx"),
        "Santander.xlsx"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            santander_path = path
            break
    
    if not santander_path:
        raise FileNotFoundError("No se encontró el archivo Santander.xlsx")
    
    print(f"📁 Usando archivo Santander desde: {santander_path}")
    df_santander = pd.read_excel(santander_path)
    print(f"📊 Archivo Santander cargado: {len(df_santander)} registros")
    pagos = cruzar_resultados_con_santander(resultados, df_santander)
    pagos["Monto transferencia\n(obligatorio)"] = pagos["Monto Pago"].fillna(0).astype(int)
    
    hoy = datetime.today()
    dias_hasta_viernes = (4 - hoy.weekday()) % 7
    viernes = hoy + timedelta(days=dias_hasta_viernes)
    fecha_viernes = viernes.strftime("%d %m %Y")
    
    # Dividir pagos mayores a 7,000,000 en múltiples filas
    pagos_divididos = []
    
    for _, row in pagos.iterrows():
        monto_total = row["Monto transferencia\n(obligatorio)"]
        
        if monto_total > 7000000:
            # Calcular cuántas filas de 7 millones necesitamos
            num_filas_7m = int(monto_total // 7000000)
            monto_restante = monto_total % 7000000
            
            # Crear filas de 7 millones
            for i in range(num_filas_7m):
                fila_dividida = row.copy()
                fila_dividida["Monto transferencia\n(obligatorio)"] = 7000000
                fila_dividida["Glosa personalizada transferencia\n(opcional)"] = f"PAGO FACTURA {row['Factura']} PARTE {i+1}"
                fila_dividida["Mensaje correo beneficiario\n(opcional)"] = f"PAGO PROVEEDORES {fecha_viernes}"
                pagos_divididos.append(fila_dividida)
            
            # Si hay resto, crear fila adicional con el monto restante
            if monto_restante > 0:
                fila_restante = row.copy()
                fila_restante["Monto transferencia\n(obligatorio)"] = monto_restante
                fila_restante["Glosa personalizada transferencia\n(opcional)"] = f"PAGO FACTURA {row['Factura']} PARTE {num_filas_7m + 1}"
                fila_restante["Mensaje correo beneficiario\n(opcional)"] = f"PAGO PROVEEDORES {fecha_viernes}"
                pagos_divididos.append(fila_restante)
        else:
            # Mantener el pago sin dividir
            row["Glosa personalizada transferencia\n(opcional)"] = "PAGO FACTURA " + str(row["Factura"])
            row["Mensaje correo beneficiario\n(opcional)"] = f"PAGO PROVEEDORES {fecha_viernes}"
            pagos_divididos.append(row)
    
    # Convertir la lista de filas en DataFrame
    pagos = pd.DataFrame(pagos_divididos)
    pagos = pagos[pagos["Monto transferencia\n(obligatorio)"] > 0]

    cols_santander = df_santander.columns.tolist()
    
    cols_finales = ["Rut", "Razón Social"] + cols_santander
    
    pagos = pagos[cols_finales]
    
    # Guardar en directorio persistente
    link_mostrar = os.path.join(PERSISTENT_DIR, "pagos_mostrar.xlsx")
    pagos.to_excel(link_mostrar, index=False)

    return pagos

def planilla_pago_mostrar(resultado, santander):
    resultado = filtrar_a_pagar(resultado)
    resultado_cruzado = cruzar_resultados_con_santander(resultado, santander)
    resultado_cruzado = crear_planilla_pagos(resultado_cruzado)
    return resultado_cruzado    

def generar_planilla_meses(months_back: int) -> pd.DataFrame:
    """
    Ejecuta preparar_planilla(fecha_inicio, fecha_fin) para cada mes desde
    `months_back` meses atrás hasta el mes actual y concatena todos los resultados.

    - Si hoy es 26/08/2025 y months_back=3 -> mayo, junio, julio y agosto (hasta el 26).
    - Se asegura de incluir el rango completo de cada día (00:00:00 a 23:59:59).
    - Devuelve un único DataFrame sin duplicados.
    """
    hoy = date.today()
    start_month = hoy.replace(day=1) - relativedelta(months=months_back)

    dfs = []

    for i in range(months_back + 1):
        # Fecha base de cada mes
        ym = start_month + relativedelta(months=i)
        year, month = ym.year, ym.month

        # Primer y último día del mes
        first_day = date(year, month, 1)
        last_day_num = monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)

        # Si es mes actual, fin es hoy
        end_day = min(last_day, hoy)

        # Strings con hora completa
        fecha_inicio = f"{first_day:%Y-%m-%d} 00:00:00"
        fecha_fin = f"{end_day:%Y-%m-%d} 23:59:59"

        # Llamada a tu función
        df_mes = preparar_planilla(fecha_inicio, fecha_fin)

        if isinstance(df_mes, pd.DataFrame) and not df_mes.empty:
            dfs.append(df_mes)

    # Concatenar y limpiar duplicados
    if dfs:
        df_total = pd.concat(dfs, ignore_index=True).drop_duplicates()
        return df_total
    else:
        return pd.DataFrame()

def flujo_pagos(meses, pdf_file):
    resultado = generar_planilla_meses(meses)
    cesiones= procesar_certificados(pdf_file)
    resultados, cesiones_no_cruzadas = cruzar_resultados_cesiones(resultado, cesiones)
    resultados = actualizar_fecha_pago(resultados)   
    return resultados, cesiones_no_cruzadas

