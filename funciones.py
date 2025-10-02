import os
import requests
import pandas as pd
import json
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
import csv

# Cargar la API key desde .env
load_dotenv()
API_KEY = os.getenv("ICONSTRUYE_API_KEY")
if not API_KEY:
    raise ValueError("La clave API no está definida en el archivo .env")


def agregar_a_subidas_csv(id_documento, datos_factura=None):
    """
    Agrega un idDocumento a subidas.csv evitando duplicados.
    También guarda los datos completos de la factura en facturas_subidas_datos.csv.
    Evita duplicados comparando por folioUnico y rutProveedor.
    Crea los archivos si no existen.
    """
    from main import SUBIDAS_CSV, FACTURAS_SUBIDAS_CSV, FACTURAS_CSV
    import pandas as pd
    archivo_subidas = SUBIDAS_CSV
    
    # Verificar si el archivo existe y leer los IDs existentes
    ids_existentes = set()
    if os.path.exists(archivo_subidas):
        try:
            with open(archivo_subidas, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                # Leer la cabecera
                next(reader, None)
                # Leer los IDs existentes
                for row in reader:
                    if row:  # Evitar filas vacías
                        ids_existentes.add(row[0])
        except Exception as e:
            print(f"⚠️ Error leyendo {archivo_subidas}: {e}")
    
    # Si el ID ya existe, no lo agregamos
    if str(id_documento) in ids_existentes:
        print(f"📋 ID {id_documento} ya existe en {archivo_subidas}")
        return
    
    # Agregar el nuevo ID
    try:
        # Si el archivo no existe, crearlo con cabecera
        if not os.path.exists(archivo_subidas):
            with open(archivo_subidas, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['idDocumento'])
        
        # Agregar el nuevo ID
        with open(archivo_subidas, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([str(id_documento)])
        
        print(f"✅ ID {id_documento} agregado a {archivo_subidas}")
        
        # Agregar datos completos a facturas_subidas_datos.csv
        try:
            # Si no se proporcionaron datos, buscarlos en facturas.csv
            if datos_factura is None:
                df_facturas = pd.read_csv(FACTURAS_CSV, encoding='utf-8-sig')
                fila = df_facturas[df_facturas['idDocumento'] == id_documento]
                if not fila.empty:
                    datos_factura = fila.iloc[0].to_dict()
            
            # Guardar en archivo de datos completos
            if datos_factura is not None:
                df_nueva = pd.DataFrame([datos_factura])
                
                # Si el archivo existe, verificar duplicados por folioUnico + rutProveedor
                if os.path.exists(FACTURAS_SUBIDAS_CSV):
                    df_existente = pd.read_csv(FACTURAS_SUBIDAS_CSV, encoding='utf-8-sig')
                    
                    # Verificar duplicados por folioUnico y rutProveedor
                    folio = str(datos_factura.get('folioUnico', ''))
                    rut = str(datos_factura.get('rutProveedor', ''))
                    
                    existe = ((df_existente['folioUnico'].astype(str) == folio) & 
                             (df_existente['rutProveedor'].astype(str) == rut)).any()
                    
                    if not existe:
                        df_final = pd.concat([df_existente, df_nueva], ignore_index=True)
                        df_final.to_csv(FACTURAS_SUBIDAS_CSV, index=False, encoding='utf-8-sig')
                        print(f"✅ Datos completos agregados a facturas_subidas_datos.csv")
                    else:
                        print(f"📋 Factura con folio {folio} y RUT {rut} ya existe en facturas_subidas_datos.csv")
                else:
                    df_nueva.to_csv(FACTURAS_SUBIDAS_CSV, index=False, encoding='utf-8-sig')
                    print(f"✅ Archivo facturas_subidas_datos.csv creado")
        except Exception as e:
            print(f"⚠️ Error guardando datos completos: {e}")
    
    except Exception as e:
        print(f"❌ Error escribiendo en {archivo_subidas}: {e}")


def buscar_facturas(IdOrgc,
                                 FechaEmisDesde,
                                 FechaEmisHasta,
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
    
    print(f"📅 Consultando facturas por fecha de emisión desde {FechaEmisDesde} hasta {FechaEmisHasta}")
    
    url_base = "https://api.iconstruye.com/cvbf/api/Factura/Buscar"
    headers = {
        "Ocp-Apim-Subscription-Key": API_KEY  # Define esta variable con tu clave antes de ejecutar
    }

    # Simulamos FechaRecepDesde y FechaRecepHasta como requeridos (por ejemplo, 1 día antes y después del período de emisión)
    recep_desde = FechaEmisDesde
    recep_hasta = FechaEmisHasta

    # Parámetros obligatorios
    params = {
        "IdOrgc": IdOrgc,
        "FechaRecepDesde": recep_desde,
        "FechaRecepHasta": recep_hasta,
        "FechaEmisDesde": FechaEmisDesde,
        "FechaEmisHasta": FechaEmisHasta,
        "api-version": api_version
    }

    # Parámetros opcionales
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


# ------------------------------------------------------------------
# 1. Obtener token desde Auth0
# ------------------------------------------------------------------
def obtener_token() -> str:
    url = "https://api.kameone.cl/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("KAME_CLIENT_ID"),
        "client_secret": os.getenv("KAME_CLIENT_SECRET"),
        "audience": "https://api.kameone.cl/api"
    }

    resp = requests.post(url, json=payload, timeout=30)
    print("📤 Status:", resp.status_code)
    print("📨 Respuesta:", resp.text)

    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"❌ Token no recibido: {data}")
    return data["access_token"]


def obtener_fichas_completas():
    try:
        token = obtener_token()
        url = "https://api.kameone.cl/api/Maestro/getListFicha"
        headers = {"Authorization": f"Bearer {token}"}
        
        page = 1
        all_items = []

        while True:
            params = {"page": page}
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            if not items:
                break  # No hay más datos
            
            all_items.extend(items)

            # Si ya descargamos todos los registros, salimos
            if page * data["per_page"] >= data["total"]:
                break

            page += 1

        df = pd.DataFrame(all_items)
        return df

    except Exception as e:
        print(f"❌ Error al obtener fichas: {e}")
        return pd.DataFrame()  # Devuelve DataFrame vacío en caso de error

def quitar_puntos(df):  
    # Quitar los puntos de la columna Rut
    df['Rut'] = df['Rut'].astype(str).str.replace('.', '', regex=False)
    
    print(df)
    return df


def cruzar_por_rut(facturas, fichas):    
    # Limpiar puntos en columna Rut de fichas (si aplica)
    fichas['Rut'] = fichas['Rut'].astype(str).str.replace('.', '', regex=False)
    
    # Asegurar que rutProveedor sea string para el merge
    facturas['rutProveedor'] = facturas['rutProveedor'].astype(str)

    # Hacer merge
    df_resultado = facturas.merge(
        fichas[['Rut', 'FechaIngreso', 'ConceptoCompras', 'Cliente', 'Proveedor', 'Honorario', 'Empleado']], 
        how='left', 
        left_on='rutProveedor', 
        right_on='Rut'
    )

    # Detectar filas sin match (Rut == NaN) y poner "Proveedor no encontrado"
    sin_match = df_resultado['Rut'].isna()
    df_resultado.loc[sin_match, 'FechaIngreso'] = 'Proveedor no encontrado'
    df_resultado.loc[sin_match, 'ConceptoCompras'] = 'Proveedor no encontrado'

    # Eliminar columna auxiliar Rut si no se necesita
    df_resultado = df_resultado.drop(columns='Rut')

    return df_resultado


def cruzar_por_concepto(facturas, cuentas):
    df_resultado = facturas.merge(
        cuentas[['Concepto', 'Cuenta', 'Cuenta 2']],
        how='left',
        left_on='ConceptoCompras',
        right_on='Concepto'
    )
    
    # Opcional: eliminar columna 'Concepto' si no se quiere duplicada
    df_resultado = df_resultado.drop(columns='Concepto')
    
    return df_resultado

def extraer_4_caracteres(df, columna_origen, columna_destino):
    """
    Extrae los primeros 4 caracteres de la columna_origen y los guarda en columna_destino.

    Parámetros:
    - df: DataFrame
    - columna_origen: str, nombre de la columna de donde extraer el texto
    - columna_destino: str, nombre de la nueva columna donde guardar los resultados
    """
    df[columna_destino] = df[columna_origen].astype(str).str.slice(0, 4)
    return df

def cruzar_por_centro_costo(facturas, un):
    # Normalizar columnas
    un.columns = un.columns.str.strip()

    # Convertir columnas clave a string
    facturas['Centro'] = facturas['Centro'].astype(str)
    un['Centro de Costo Previred'] = un['Centro de Costo Previred'].astype(str)

    # Hacer merge
    df_resultado = facturas.merge(
        un[['Unidad de Negocio', 'Estado', 'Centro de Costo Previred']],
        how='left',
        left_on='Centro',
        right_on='Centro de Costo Previred'
    )

    df_resultado = df_resultado.drop(columns='Centro de Costo Previred')

    return df_resultado

def asignar_boleta_honorarios(df):
    """
    Si 'ConceptoCompras' está vacío (NaN o cadena vacía) y 'Honorario' == 'S',
    entonces se asigna 'Boleta Honorarios' en la columna 'tipoFactura'.
    """
    # Verificamos si existe la columna tipoFactura, si no, la creamos
    if 'tipoFactura' not in df.columns:
        df['tipoFactura'] = None

    # Aplicamos la lógica condicional
    condicion = (df['ConceptoCompras'].isna() | (df['ConceptoCompras'].astype(str).str.strip() == '')) & (df['Honorario'] == 'S')
    df.loc[condicion, 'tipoFactura'] = 'Boleta Honorarios'

    return df

def obtener_detalle_factura(IdDoc, api_version="1.0"):
    url = "https://api.iconstruye.com/cvbf/api/Factura/PorId"
    headers = {
        "Ocp-Apim-Subscription-Key": API_KEY
    }
    params = {
        "IdDoc": IdDoc,
        "api-version": api_version
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        detalle = response.json()

        # 👉 Normalización de la estructura
        if isinstance(detalle, list):
            detalle = detalle[0] if len(detalle) > 0 else {}
        elif isinstance(detalle, dict) and "items" in detalle:
            detalle = detalle["items"][0] if detalle["items"] else {}

        # 👉 Extracción segura
        monto_neto = detalle.get("cabecera", {}).get("totales", {}).get("neto", {}).get("montoNeto")
        monto_no_afecto = detalle.get("cabecera", {}).get("totales", {}).get("neto", {}).get("montoNoAfectoOExento")

        print(f"📄 Factura ID {IdDoc} → Neto: {monto_neto}, No Afecto: {monto_no_afecto}")

        return {
            "montoNeto": monto_neto,
            "montoNoAfectoOExento": monto_no_afecto
        }

    except requests.exceptions.HTTPError as http_err:
        print(f"❌ Error HTTP: {http_err}")
    except requests.exceptions.Timeout:
        print("⏱️ Tiempo de espera agotado.")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error de conexión/API: {e}")

    return {
        "montoNeto": None,
        "montoNoAfectoOExento": None
    }

# Esta función envoltorio maneja posibles errores individuales
def obtener_detalle_seguro(id_doc):
    try:
        return obtener_detalle_factura(id_doc)
    except Exception as e:
        print(f"⚠️ Error al obtener detalle para ID {id_doc}: {e}")
        return None
    
def descargar_unidad_negocio():
    try:
        token = obtener_token()
        url = "https://api.kameone.cl/api/Maestro/getListUnidadNegocio"
        headers = {"Authorization": f"Bearer {token}"}
        payload={}
    
        
        response = requests.request("GET", url, headers=headers, data=payload)
        
        unidades = response.json()
        df = pd.DataFrame(unidades)
        return df
        
    except Exception as e:
        print(f"❌ Error al obtener unidades de negocio: {e}")
        return pd.DataFrame()  
    
def cargar_excel_a_dataframe(ruta_archivo):
    """
    Carga un archivo Excel (.xlsx) y lo convierte en un DataFrame.
    
    Parámetros:
        ruta_archivo (str): Ruta al archivo Excel
    
    Retorna:
        pd.DataFrame: DataFrame con el contenido del archivo
    """
    try:
        df = pd.read_excel(ruta_archivo)
        print(f"✅ Archivo cargado correctamente. Total de filas: {len(df)}")
        return df
    except Exception as e:
        print(f"❌ Error al cargar el archivo: {e}")
        return pd.DataFrame()

def cargar_csv_a_dataframe(ruta_archivo):
    """
    Carga un archivo CSV (.csv) y lo convierte en un DataFrame.
    
    Parámetros:
        ruta_archivo (str): Ruta al archivo CSV
    
    Retorna:
        pd.DataFrame: DataFrame con el contenido del archivo
    """
    try:
        df = pd.read_csv(ruta_archivo, encoding='utf-8-sig')
        print(f"✅ Archivo cargado correctamente. Total de filas: {len(df)}")
        return df
    except Exception as e:
        print(f"❌ Error al cargar el archivo: {e}")
        return pd.DataFrame()

def borrar_facturas_por_ids(ids_borrar, borrar_de_subidas=True):
    """
    Elimina facturas con los IDs dados de facturas.csv y opcionalmente de subidas.csv.
    Parámetros:
        ids_borrar: Lista de IDs a eliminar
        borrar_de_subidas: Si True, también elimina de subidas.csv (por defecto True para mantener compatibilidad)
    Retorna el número de facturas eliminadas de cada archivo.
    """
    from main import FACTURAS_CSV, SUBIDAS_CSV
    import pandas as pd
    import os
    import csv

    # Borrar de facturas.csv
    if os.path.exists(FACTURAS_CSV):
        df = pd.read_csv(FACTURAS_CSV, encoding='utf-8-sig')
        antes = len(df)
        df = df[~df['idDocumento'].isin(ids_borrar)]
        despues = len(df)
        df.to_csv(FACTURAS_CSV, index=False, encoding='utf-8-sig')
        eliminadas_facturas = antes - despues
    else:
        eliminadas_facturas = 0

    # Borrar de subidas.csv solo si se especifica
    eliminadas_subidas = 0
    if borrar_de_subidas and os.path.exists(SUBIDAS_CSV):
        with open(SUBIDAS_CSV, 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            rows = list(reader)
        header = rows[0] if rows else ['idDocumento']
        ids_actuales = [row for row in rows[1:] if row and int(row[0]) not in ids_borrar]
        eliminadas_subidas = (len(rows) - 1) - len(ids_actuales)
        with open(SUBIDAS_CSV, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(header)
            writer.writerows(ids_actuales)

    return eliminadas_facturas, eliminadas_subidas

def agregar_campo_subidas_a_facturas(df_facturas):
    """
    Agrega el campo 'Subidas' al DataFrame de facturas.
    Determina si cada factura está en el archivo facturas_subidas_datos.csv
    comparando por folioUnico y rutProveedor
    
    Parámetros:
        df_facturas: DataFrame con las facturas
    
    Retorna:
        DataFrame con el campo Subidas agregado
    """
    try:
        # Leer facturas subidas desde facturas_subidas_datos.csv
        from main import FACTURAS_SUBIDAS_CSV
        facturas_subidas = set()
        
        if os.path.exists(FACTURAS_SUBIDAS_CSV):
            df_subidas = pd.read_csv(FACTURAS_SUBIDAS_CSV, encoding='utf-8-sig')
            
            # Crear set de tuplas (folioUnico, rutProveedor) para comparación rápida
            for _, row in df_subidas.iterrows():
                folio = str(row['folioUnico']) if pd.notna(row['folioUnico']) else ''
                rut = str(row['rutProveedor']) if pd.notna(row['rutProveedor']) else ''
                facturas_subidas.add((folio, rut))
        
        # Agregar columna Subidas comparando folioUnico y rutProveedor
        def verificar_subida(row):
            folio = str(row['folioUnico']) if pd.notna(row['folioUnico']) else ''
            rut = str(row['rutProveedor']) if pd.notna(row['rutProveedor']) else ''
            return 'Sí' if (folio, rut) in facturas_subidas else 'No'
        
        df_facturas['Subidas'] = df_facturas.apply(verificar_subida, axis=1)
        
        print(f"✅ Campo 'Subidas' agregado. {len(facturas_subidas)} facturas marcadas como subidas")
        return df_facturas
        
    except Exception as e:
        print(f"❌ Error al agregar campo Subidas: {e}")
        # Agregar columna con valor por defecto
        df_facturas['Subidas'] = 'No'
        return df_facturas
    
def cruzar_dataframes(df1, df2, id_column='idDocumento'):
    """
    Cruza dos DataFrames por una columna ID, manteniendo la lógica:
    - Agrega nuevos registros del df2 que no existen en df1
    - Reemplaza valores existentes en df1 con los valores del df2 cuando coinciden
    - Mantiene valores de df1 que no están en df2
    """

    import pandas as pd

    # Verificar que la columna ID existe en ambos DataFrames
    if id_column not in df1.columns:
        raise ValueError(f"La columna '{id_column}' no existe en df1")
    if id_column not in df2.columns:
        raise ValueError(f"La columna '{id_column}' no existe en df2")

    # Copia para no modificar los originales
    resultado = df1.copy()
    
    # Asegurarse de que los tipos coincidan entre ambos DataFrames
    df2_casted = df2.copy()
    for col in df2_casted.columns:
        if col in resultado.columns:
            try:
                df2_casted[col] = df2_casted[col].astype(resultado[col].dtype)
            except Exception as e:
                print(f"⚠️ No se pudo convertir la columna '{col}': {e}")

    # Establecer índice para actualización
    resultado = resultado.set_index(id_column)
    df2_casted = df2_casted.set_index(id_column)

    # Actualizar valores existentes
    resultado.update(df2_casted)

    # Agregar filas nuevas
    resultado = resultado.combine_first(df2_casted)

    # Restaurar índice
    resultado = resultado.reset_index()

    # Reordenar columnas para que id_column esté primero
    cols = [id_column] + [col for col in resultado.columns if col != id_column]
    resultado = resultado[cols]

    return resultado

def preparar_facturas(fechainicio, fechafinal):
    fichas = obtener_fichas_completas()
    # fechas en formato YYYY-MM-DD
    facturas = buscar_facturas(
        IdOrgc=-1,
        FechaEmisDesde=fechainicio,
        FechaEmisHasta=fechafinal
    )    
    facturas_cruzadas = cruzar_por_rut(facturas, fichas)
    from main import CUENTAS_XLSX, UN_XLSX, FACTURAS_CSV
    df_cuentas = cargar_excel_a_dataframe(CUENTAS_XLSX)
    facturas_con_cuenta = cruzar_por_concepto(facturas_cruzadas, df_cuentas)
    df_facturas_honorarios = asignar_boleta_honorarios(facturas_con_cuenta)
    df_un = cargar_excel_a_dataframe(UN_XLSX)
    df_facturas_cc = extraer_4_caracteres(df_facturas_honorarios, "centroGestion", "Centro")
    df_facturas_con_cc = cruzar_por_centro_costo(df_facturas_cc, df_un)
    detalles = df_facturas_con_cc['idDocumento'].apply(obtener_detalle_factura)
    df_facturas_con_cc[['montoNeto', 'montoNoAfectoOExento']] = pd.DataFrame(detalles.tolist(), index=df_facturas_con_cc.index)
    df1= cargar_csv_a_dataframe(FACTURAS_CSV)
    dfcruzado = cruzar_dataframes(df1, df_facturas_con_cc, id_column='idDocumento')
    dfcruzado.to_csv(FACTURAS_CSV, index=False, encoding='utf-8-sig')
    
def subir_facturas_kame(id, df):
    id_documento = id
    fila = df[df['idDocumento'] == id_documento].reset_index(drop=True)
    
    # Verificar si la factura ya está subida comparando folioUnico y rutProveedor
    try:
        from main import FACTURAS_SUBIDAS_CSV
        folio_actual = str(fila.loc[0, 'folioUnico']) if pd.notna(fila.loc[0, 'folioUnico']) else ''
        rut_actual = str(fila.loc[0, 'rutProveedor']) if pd.notna(fila.loc[0, 'rutProveedor']) else ''
        
        if os.path.exists(FACTURAS_SUBIDAS_CSV):
            df_subidas = pd.read_csv(FACTURAS_SUBIDAS_CSV, encoding='utf-8-sig')
            
            # Verificar si existe la combinación folioUnico + rutProveedor
            existe = ((df_subidas['folioUnico'].astype(str) == folio_actual) & 
                     (df_subidas['rutProveedor'].astype(str) == rut_actual)).any()
            
            if existe:
                print(f"❌ La factura con folio {folio_actual} y RUT {rut_actual} ya está subida a Kame")
                return "ALREADY_UPLOADED"
    except Exception as e:
        print(f"⚠️ Error verificando facturas subidas: {e}")
        # Continuar con el proceso si hay error en la verificación
    
    # Verificar si la factura está cancelada
    estado_doc = str(fila.loc[0, 'estadoDoc']).strip() if pd.notna(fila.loc[0, 'estadoDoc']) else ''
    if estado_doc.lower() == 'cancelada':
        print(f"❌ No se puede subir la factura {id_documento} porque su estado es 'Cancelada'")
        return "CANCELLED"
    
    if pd.isna(fila.loc[0, 'Cuenta']):
        print("No hay cuenta")
        return False
    else:
        usuario = "jgutierrez@constructoraicc.cl"
        tipoComprobante = "TRASPASO"
        folio = ""
        fecha = str(fila.loc[0, 'fechaEmision'])[:10]    
        cuenta = str(fila.loc[0, 'Cuenta'])
        montoNeto = int(float(fila.loc[0, 'montoNeto']))
        montoNoAfecto = int(float(fila.loc[0, 'montoNoAfectoOExento']))
        rutFicha = str(fila.loc[0, 'rutProveedor'])
        razon = str(fila.loc[0, 'nomProveedor'])
        documento = str(fila.loc[0, 'tipoFactura'])
        folioDocumento = str(fila.loc[0, 'folioUnico'])
        unidadNegocio = str(fila.loc[0, 'Unidad de Negocio'])
        comentario = f"{documento} #{folioDocumento}, ficha {rutFicha} {razon}"
        fechaVencimiento = ""
        tipoMovimiento = ""
        numeroMovimiento = ""
        detalle = []
        
        if montoNeto > 0:
            detalle.append({
                "cuenta": cuenta,
                "debe": montoNeto,
                "haber": 0,
                "comentario": comentario+" afecto",
                "rutFicha": rutFicha,
                "documento": razon,
                "folioDocumento": folioDocumento,
                "unidadNegocio": unidadNegocio,
                "fechaVencimiento": fechaVencimiento,
                "tipoMovimiento": tipoMovimiento,
                "numeroMovimiento": numeroMovimiento
            })
            detalle.append({
                "cuenta": cuenta,
                "debe": 0,
                "haber": montoNeto,
                "comentario": comentario,
                "rutFicha": rutFicha,
                "documento": razon,
                "folioDocumento": folioDocumento,
                "unidadNegocio": "Oficina Central",
                "fechaVencimiento": fechaVencimiento,
                "tipoMovimiento": tipoMovimiento,
                "numeroMovimiento": numeroMovimiento
            })
        if montoNoAfecto > 0:
            detalle.append({
                "cuenta": cuenta,
                "debe": montoNoAfecto,
                "haber": 0,
                "comentario": comentario+" no afecto",
                "rutFicha": rutFicha,
                "documento": razon,
                "folioDocumento": folioDocumento,
                "unidadNegocio": unidadNegocio,
                "fechaVencimiento": fechaVencimiento,
                "tipoMovimiento": tipoMovimiento,
                "numeroMovimiento": numeroMovimiento
            })
            detalle.append({
                "cuenta": cuenta,
                "debe": 0,
                "haber": montoNoAfecto,
                "comentario": comentario,
                "rutFicha": rutFicha,
                "documento": razon,
                "folioDocumento": folioDocumento,
                "unidadNegocio": "Oficina Central",
                "fechaVencimiento": fechaVencimiento,
                "tipoMovimiento": tipoMovimiento,
                "numeroMovimiento": numeroMovimiento
            })    
        payload = {
            "usuario": "jgutierrez@constructoraicc.cl",
            "tipoComprobante": "TRASPASO",
            "folio": "",
            "fecha": fecha,
            "comentario": comentario, 
            "detalle": detalle          
         }
    token = obtener_token()

    url = "https://api.kameone.cl/api/Contabilidad/addComprobante"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print("\n📤 Enviando comprobante contable...")
    print(f"📄 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    print("📤 Status:", response.status_code)
    print("📨 Respuesta:", response.text)
    
    if response.status_code != 200:
        response.raise_for_status()
    else:
        print("✅ Comprobante enviado correctamente.")
        # Agregar el ID a subidas.csv
        agregar_a_subidas_csv(id_documento)
        
    return True
