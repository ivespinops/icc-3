from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
import os
import pandas as pd
import numpy as np
import json
from funciones import subir_facturas_kame, cargar_csv_a_dataframe, preparar_facturas, agregar_campo_subidas_a_facturas
from pagos import flujo_pagos
from pydantic import BaseModel
from typing import List
import io
import shutil
import email_sender

app = FastAPI(title="Constructora ICC")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Directorio persistente
PERSISTENT_DIR = "/opt/render/project/data"

# Asegurar que el directorio existe
if not os.path.exists(PERSISTENT_DIR):
    os.makedirs(PERSISTENT_DIR)

# Rutas de archivos persistentes
DATABASE = os.path.join(PERSISTENT_DIR, "constructora_icc.db")
FACTURAS_CSV = os.path.join(PERSISTENT_DIR, "facturas.csv")
SUBIDAS_CSV = os.path.join(PERSISTENT_DIR, "subidas.csv")
FACTURAS_SUBIDAS_CSV = os.path.join(PERSISTENT_DIR, "facturas_subidas_datos.csv")
CUENTAS_XLSX = os.path.join(PERSISTENT_DIR, "cuentas.xlsx")
UN_XLSX = os.path.join(PERSISTENT_DIR, "UN.xlsx")
FACTURAS_COPIA_CSV = os.path.join(PERSISTENT_DIR, "facturas - copia.csv")
CERTIFICADOS_SII_PDF = os.path.join(PERSISTENT_DIR, "certificados_sii.pdf")
PLANILLA_FLUJO_PAGOS_XLSX = os.path.join(PERSISTENT_DIR, "planilla_flujo_pagos.xlsx")
PLANILLA_FLUJO_PAGOS_CSV = os.path.join(PERSISTENT_DIR, "planilla_flujo_pagos.csv")
CESIONES_NO_CRUZADAS_XLSX = os.path.join(PERSISTENT_DIR, "cesiones_no_cruzadas.xlsx")
CESIONES_NO_CRUZADAS_CSV = os.path.join(PERSISTENT_DIR, "cesiones_no_cruzadas.csv")
SANTANDER_XLSX = os.path.join(PERSISTENT_DIR, "Santander.xlsx")
TRANSFERENCIAS_XLSX = os.path.join(PERSISTENT_DIR, "transferencias.xlsx")

# Pydantic models
class FacturaKame(BaseModel):
    idDocumento: int
    folioUnico: str
    nomProveedor: str
    
    class Config:
        str_strip_whitespace = True

class SubirKameRequest(BaseModel):
    facturas: List[FacturaKame]

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_files_to_persistent_disk():
    """Migra archivos existentes al disco persistente"""
    archivos_locales = {
        "constructora_icc.db": DATABASE,
        "facturas.csv": FACTURAS_CSV,
        "subidas.csv": SUBIDAS_CSV,
        "cuentas.xlsx": CUENTAS_XLSX,
        "UN.xlsx": UN_XLSX,
        "facturas - copia.csv": FACTURAS_COPIA_CSV,
        "certificados_sii.pdf": CERTIFICADOS_SII_PDF,
        "Santander.xlsx": SANTANDER_XLSX
    }
    
    for archivo_local, archivo_persistente in archivos_locales.items():
        if os.path.exists(archivo_local) and not os.path.exists(archivo_persistente):
            print(f"Migrando {archivo_local} a {archivo_persistente}")
            shutil.copy2(archivo_local, archivo_persistente)

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
    
    # Excel de Santander (Cuentas Bancarias)
    if not os.path.exists(SANTANDER_XLSX):
        # Crear estructura básica para Santander
        columnas_santander = [
            'Nombre beneficiario\n(obligatorio)',
            'RUT beneficiario\n(obligatorio solo si banco destino no es Santander)',
            'Banco destino\n(obligatorio)',
            'Tipo de cuenta destino\n(obligatorio)',
            'Número de cuenta destino\n(obligatorio)',
            'Correo beneficiario\n(obligatorio)',
            'Monto transferencia\n(obligatorio)',
            'Glosa personalizada transferencia\n(opcional)',
            'Mensaje correo beneficiario\n(opcional)'
        ]
        pd.DataFrame(columns=columnas_santander).to_excel(SANTANDER_XLSX, index=False)
    
    # CSV de facturas (si no tienes el archivo inicial)
    if not os.path.exists(FACTURAS_CSV):
        # Crear estructura básica o copiar desde facturas - copia.csv
        if os.path.exists(FACTURAS_COPIA_CSV):
            shutil.copy2(FACTURAS_COPIA_CSV, FACTURAS_CSV)
        else:
            pd.DataFrame().to_csv(FACTURAS_CSV, index=False)

def init_db():
    conn = get_db_connection()
    
    # Users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add is_manager column if it doesn't exist
    try:
        conn.execute('ALTER TABLE users ADD COLUMN is_manager BOOLEAN NOT NULL DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass

    # Add is_admin_obra column if it doesn't exist
    try:
        conn.execute('ALTER TABLE users ADD COLUMN is_admin_obra BOOLEAN NOT NULL DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    # Sessions table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Obras table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS obras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_obra TEXT NOT NULL,
            centro_costo TEXT NOT NULL,
            administrador_obra_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (administrador_obra_id) REFERENCES users (id)
        )
    ''')

    # Flujo cajas configuration table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS obra_flujo_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            obra_id INTEGER NOT NULL,
            fecha_inicio DATE NOT NULL,
            fecha_fin DATE NOT NULL,
            FOREIGN KEY (obra_id) REFERENCES obras (id) ON DELETE CASCADE,
            UNIQUE(obra_id)
        )
    ''')

    # Items catalog table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Flujo cajas items table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS flujo_cajas_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            obra_id INTEGER NOT NULL,
            codigo TEXT NOT NULL,
            nombre TEXT NOT NULL,
            presupuesto_inicial REAL NOT NULL DEFAULT 0,
            modificaciones REAL NOT NULL DEFAULT 0,
            gasto_real REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (obra_id) REFERENCES obras (id) ON DELETE CASCADE
        )
    ''')

    # Flujo cajas weekly data table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS flujo_cajas_semanal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            semana DATE NOT NULL,
            valor REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (item_id) REFERENCES flujo_cajas_items (id) ON DELETE CASCADE,
            UNIQUE(item_id, semana)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS saldos_previos_bancos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            banco TEXT NOT NULL,
            semana DATE NOT NULL,
            valor REAL DEFAULT 0,
            UNIQUE(banco, semana)
        )
    ''')

    # Flujo cajas editable ingresos table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS flujo_cajas_editable_ingresos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_ingreso TEXT NOT NULL,
            semana DATE NOT NULL,
            valor REAL DEFAULT 0,
            UNIQUE(tipo_ingreso, semana)
        )
    ''')

    # Credits table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS creditos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_credito TEXT NOT NULL,
            banco TEXT NOT NULL,
            cuotas_restantes INTEGER NOT NULL,
            valor_cuota REAL NOT NULL,
            fecha_pago DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create default admin user
    password_hash = hash_password("password123")
    conn.execute('''
        INSERT OR IGNORE INTO users (name, email, password_hash, is_admin, is_manager, is_admin_obra)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ("Constanza Carreño", "ccarreno@constructoraicc.cl", password_hash, 1, 0, 0))

    # Create default manager user
    manager_password_hash = hash_password("manager123")
    conn.execute('''
        INSERT OR IGNORE INTO users (name, email, password_hash, is_admin, is_manager, is_admin_obra)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ("Gerente Test", "gerente@constructoraicc.cl", manager_password_hash, 0, 1, 0))

    # Create default admin_obra user
    admin_obra_password_hash = hash_password("obra123")
    conn.execute('''
        INSERT OR IGNORE INTO users (name, email, password_hash, is_admin, is_manager, is_admin_obra)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ("Admin Obra", "adminobra@constructoraicc.cl", admin_obra_password_hash, 0, 0, 1))

    # Insert predefined items
    predefined_items = [
        ("101", "Facturación", "INGRESOS"),
        ("102", "Facturación Adicional", "INGRESOS"),
        ("103", "Otros Ingresos", "INGRESOS"),
        ("1010", "Trazados Y Emplazamiento", "Obras Preliminares"),
        ("1020", "Áridos", "Obras Preliminares"),
        ("1030", "Pernos, Tornillos, Clavos y Fijaciones", "Obras Preliminares"),
        ("1050", "Cemento", "Obras Preliminares"),
        ("1060", "Hormigón", "Obras Preliminares"),
        ("1070", "OSB e Internit", "Obras Preliminares"),
        ("1080", "Aditivos", "Obras Preliminares"),
        ("1090", "Fierro y Mallas", "Obras Preliminares"),
        ("1100", "Moldaje", "Obras Preliminares"),
        ("1110", "Estructura Metálica", "Obras Preliminares"),
        ("1130", "Impermeabilización", "Obras Preliminares"),
        ("1135", "Obras Preliminares", "Obras Preliminares"),
        ("1140", "Maderas", "Obras Preliminares"),
        ("1150", "Yeso", "Obras Preliminares"),
        ("1180", "Adhesivos", "Obras Preliminares"),
        ("1190", "Cerámicos", "Obras Preliminares"),
        ("1200", "Pinturas", "Obras Preliminares"),
        ("1220", "Porcelanato", "Obras Preliminares"),
        ("1230", "Perfiles Metalcon", "Obras Preliminares"),
        ("1240", "Volcanita", "Obras Preliminares"),
        ("1250", "Aislación Térmica - Acústica", "Obras Preliminares"),
        ("1320", "Quincallería", "Obras Preliminares"),
        ("1330", "Puertas y marcos", "Obras Preliminares"),
        ("1350", "Molduras y guardapolvo", "Obras Preliminares"),
        ("1400", "Tuberias PVC", "Obras Preliminares"),
        ("1510", "Ferretería (Disco Corte, Broca)", "Obras Preliminares"),
        ("1620", "Cubiertas y Revestimientos", "Obras Preliminares"),
        ("1600", "Señalética", "Obras Preliminares"),
        ("1630", "Materiales sanitarios", "Obras Preliminares"),
        ("1640", "Materiales Aguas Lluvias", "Obras Preliminares"),
        ("2010", "Subcontrato Movimiento de tierra", "SUBCONTRATO"),
        ("2030", "Subcontrato Tabiquería Metalcon", "SUBCONTRATO"),
        ("2040", "Subcontrato Carpinterías Metálicas", "SUBCONTRATO"),
        ("2050", "Subcontrato Estructura Metálica", "SUBCONTRATO"),
        ("2060", "Subcontrato Enfierradura", "SUBCONTRATO"),
        ("2080", "Subcontrato Colocación Hormigón", "SUBCONTRATO"),
        ("2090", "Subcontrato Impermeabilizaciones", "SUBCONTRATO"),
        ("2120", "Subcontrato Cubiertas y Hojalaterías", "SUBCONTRATO"),
        ("2140", "Subcontrato Revestimientos Porcelanato y Cerámico", "SUBCONTRATO"),
        ("2160", "Subcontrato Ventanas, Vidrios y Espejos", "SUBCONTRATO"),
        ("2180", "Subcontrato Pavimentos exteriores", "SUBCONTRATO"),
        ("2280", "Subcontrato Electricidad y C. Debiles", "SUBCONTRATO"),
        ("2240", "Subcontrato Muebles", "SUBCONTRATO"),
        ("2260", "Subcontratos Instalaciones Sanitarias", "SUBCONTRATO"),
        ("2270", "Subcontrato Climatización y Ventilación", "SUBCONTRATO"),
        ("2450", "Subcontrato Cielos", "SUBCONTRATO"),
        ("2470", "Subcontrato Acero Inox", "SUBCONTRATO"),
        ("2310", "Subcontrato Demolición", "SUBCONTRATO"),
        ("2290", "Subcontrato Pintura", "SUBCONTRATO"),
        ("2370", "Subcontrato aceros inox", "SUBCONTRATO"),
        ("2440", "Especialidades", "SUBCONTRATO"),
        ("3050", "Equipos Menores y Herramientas", "EQUIPOS"),
        ("3060", "Arriendo Maquinaria", "EQUIPOS"),
        ("3070", "Arriendo Camioneta", "EQUIPOS"),
        ("3090", "Camiones Pluma", "EQUIPOS"),
        ("3110", "Arriendo Andamio", "EQUIPOS"),
        ("3140", "Taquímetros y niveles", "EQUIPOS"),
        ("3000", "Instalación de Faena", "INSTALACION FAENA"),
        ("3030", "Instalaciones sanitarias provisorias", "INSTALACION FAENA"),
        ("3040", "Instalaciones eléctricas provisorias", "INSTALACION FAENA"),
        ("4010", "Consumo Electricidad", "GASTOS GENERALES"),
        ("4020", "Consumo Teléfono e Internet", "GASTOS GENERALES"),
        ("4030", "Consumo Agua", "GASTOS GENERALES"),
        ("4040", "Consumo Gas", "GASTOS GENERALES"),
        ("4050", "Combustibles (petróleo y bencina)", "GASTOS GENERALES"),
        ("4070", "Librería", "GASTOS GENERALES"),
        ("4080", "Materiales Aseo", "GASTOS GENERALES"),
        ("4090", "Fotocopias y Ploteos", "GASTOS GENERALES"),
        ("4100", "Equipos Informáticos (PC FACTORY PC MB)", "GASTOS GENERALES"),
        ("4110", "Permisos y Derechos (BODEGA)", "GASTOS GENERALES"),
        ("4120", "Caja Chica", "GASTOS GENERALES"),
        ("4130", "Elementos de Seguridad", "GASTOS GENERALES"),
        ("4140", "Ensayos de laboratorio", "GASTOS GENERALES"),
        ("4150", "Fletes", "GASTOS GENERALES"),
        ("4160", "Gastos Financieros", "GASTOS GENERALES"),
        ("4170", "Seguros", "GASTOS GENERALES"),
        ("5100", "MDO DIRECTA", "MANO DE OBRA"),
        ("5200", "MDO INDIRECTA", "MANO DE OBRA"),
        ("5300", "MDO SUPERVISORES", "MANO DE OBRA"),
        ("5400", "MDO PROFESIONALES", "MANO DE OBRA"),
        ("5600", "Asesorías Profesionales", "MANO DE OBRA")
    ]

    for codigo, nombre, tipo in predefined_items:
        conn.execute('''
            INSERT OR IGNORE INTO items (codigo, nombre, tipo)
            VALUES (?, ?, ?)
        ''', (codigo, nombre, tipo))

    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_session(user_id: int) -> str:
    conn = get_db_connection()
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=7)
    
    conn.execute('''
        INSERT INTO sessions (user_id, session_token, expires_at)
        VALUES (?, ?, ?)
    ''', (user_id, session_token, expires_at))
    conn.commit()
    conn.close()
    
    return session_token

def clean_for_json(obj):
    """Limpia un objeto para que sea serializable en JSON"""
    if isinstance(obj, pd.DataFrame):
        # Reemplazar valores problemáticos
        obj = obj.replace([np.nan, np.inf, -np.inf], None)
        return obj
    elif isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj.item()
    elif pd.isna(obj):
        return None
    else:
        return obj

def get_current_user(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    
    conn = get_db_connection()
    result = conn.execute('''
        SELECT u.* FROM users u
        JOIN sessions s ON u.id = s.user_id
        WHERE s.session_token = ? AND s.expires_at > ?
    ''', (session_token, datetime.now())).fetchone()
    conn.close()
    
    return dict(result) if result else None

@app.on_event("startup")
async def startup_event():
    # Migrar archivos existentes si es necesario
    migrate_files_to_persistent_disk()
    
    # Crear archivos por defecto si no existen
    ensure_default_files()
    
    # Inicializar base de datos
    init_db()

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    password_hash = hash_password(password)
    
    user = conn.execute('''
        SELECT * FROM users WHERE email = ? AND password_hash = ?
    ''', (email, password_hash)).fetchone()
    conn.close()
    
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Email o contraseña incorrectos"
        })
    
    session_token = create_session(user['id'])
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="session_token", value=session_token, httponly=True, max_age=7*24*3600)
    
    return response

@app.get("/logout")
async def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        conn = get_db_connection()
        conn.execute('DELETE FROM sessions WHERE session_token = ?', (session_token,))
        conn.commit()
        conn.close()
    
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

@app.post("/profile")
async def update_profile(request: Request, email: str = Form(...), password: str = Form(None)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    conn = get_db_connection()
    
    if password:
        password_hash = hash_password(password)
        conn.execute('''
            UPDATE users SET email = ?, password_hash = ? WHERE id = ?
        ''', (email, password_hash, user['id']))
    else:
        conn.execute('''
            UPDATE users SET email = ? WHERE id = ?
        ''', (email, user['id']))
    
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/profile?success=1", status_code=302)

@app.get("/flujo-caja", response_class=HTMLResponse)
async def flujo_caja(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)

    # Solo Administrador y Gerente pueden acceder
    if not (user['is_admin'] or user['is_manager']):
        raise HTTPException(status_code=403, detail="Acceso denegado")

    conn = get_db_connection()

    # Obtener todas las obras
    obras = conn.execute('''
        SELECT o.*, u.name as administrador_nombre
        FROM obras o
        JOIN users u ON o.administrador_obra_id = u.id
        ORDER BY o.nombre_obra
    ''').fetchall()

    # Agregado general por familia y obras separadas para ingresos
    familias_agregadas = {}
    ingresos_por_obra = {}
    todas_semanas = set()

    for obra in obras:
        obra_id = obra['id']
        obra_nombre = obra['nombre_obra']

        # Get or create flujo config for this obra
        config = conn.execute('''
            SELECT * FROM obra_flujo_config WHERE obra_id = ?
        ''', (obra_id,)).fetchone()

        if not config:
            # Create default config if it doesn't exist
            obra_start = obra['created_at'][:10]
            start_date = datetime.strptime(obra_start, '%Y-%m-%d')
            end_date = start_date + timedelta(days=180)

            conn.execute('''
                INSERT INTO obra_flujo_config (obra_id, fecha_inicio, fecha_fin)
                VALUES (?, ?, ?)
            ''', (obra_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            conn.commit()

            config = {
                'fecha_inicio': start_date.strftime('%Y-%m-%d'),
                'fecha_fin': end_date.strftime('%Y-%m-%d')
            }

        # Generate weekly dates for this obra
        semanas = get_weeks_between_dates(config['fecha_inicio'], config['fecha_fin'])
        todas_semanas.update(semanas)

        # Get flujo items with familia for this obra
        items = conn.execute('''
            SELECT fc.*, i.tipo as familia
            FROM flujo_cajas_items fc
            LEFT JOIN items i ON fc.codigo = i.codigo
            WHERE fc.obra_id = ?
        ''', (obra_id,)).fetchall()

        # Process items for this obra
        for item in items:
            item_dict = dict(item)
            familia = item_dict.get('familia', 'Sin Familia')
            if not familia:
                familia = 'Sin Familia'

            # Si es INGRESOS, agregar por obra
            if familia == "INGRESOS":
                obra_key = f"INGRESOS - {obra_nombre}"
                if obra_key not in ingresos_por_obra:
                    ingresos_por_obra[obra_key] = {
                        "familia": obra_key,
                        "tipo_flujo": "Ingresos por Obra",
                        "presupuesto_inicial": 0,
                        "modificaciones": 0,
                        "gasto_real": 0,
                        "flujo_semanal": {}
                    }

                # Sum values for this obra's income
                ingresos_por_obra[obra_key]["presupuesto_inicial"] += item_dict.get('presupuesto_inicial', 0)
                ingresos_por_obra[obra_key]["modificaciones"] += item_dict.get('modificaciones', 0)
                ingresos_por_obra[obra_key]["gasto_real"] += item_dict.get('gasto_real', 0)

                # Get weekly data for this item
                flujo_data = conn.execute('''
                    SELECT semana, valor FROM flujo_cajas_semanal WHERE item_id = ?
                ''', (item_dict['id'],)).fetchall()

                for row in flujo_data:
                    semana = row['semana']
                    valor = row['valor']
                    if semana not in ingresos_por_obra[obra_key]["flujo_semanal"]:
                        ingresos_por_obra[obra_key]["flujo_semanal"][semana] = 0
                    ingresos_por_obra[obra_key]["flujo_semanal"][semana] += valor

            else:
                # Para otras familias, agregar normalmente
                if familia not in familias_agregadas:
                    familias_agregadas[familia] = {
                        "familia": familia,
                        "tipo_flujo": "Pagos",
                        "presupuesto_inicial": 0,
                        "modificaciones": 0,
                        "gasto_real": 0,
                        "flujo_semanal": {}
                    }

                # Sum values
                familias_agregadas[familia]["presupuesto_inicial"] += item_dict.get('presupuesto_inicial', 0)
                familias_agregadas[familia]["modificaciones"] += item_dict.get('modificaciones', 0)
                familias_agregadas[familia]["gasto_real"] += item_dict.get('gasto_real', 0)

                # Get weekly data for this item
                flujo_data = conn.execute('''
                    SELECT semana, valor FROM flujo_cajas_semanal WHERE item_id = ?
                ''', (item_dict['id'],)).fetchall()

                for row in flujo_data:
                    semana = row['semana']
                    valor = row['valor']
                    if semana not in familias_agregadas[familia]["flujo_semanal"]:
                        familias_agregadas[familia]["flujo_semanal"][semana] = 0
                    familias_agregadas[familia]["flujo_semanal"][semana] += valor

    # Convert all semanas to sorted list
    semanas_ordenadas = sorted(list(todas_semanas))

    # Ensure all families have all weeks initialized
    for familia_data in familias_agregadas.values():
        for semana in semanas_ordenadas:
            if semana not in familia_data["flujo_semanal"]:
                familia_data["flujo_semanal"][semana] = 0

    # Ensure all obra ingresos have all weeks initialized
    for obra_data in ingresos_por_obra.values():
        for semana in semanas_ordenadas:
            if semana not in obra_data["flujo_semanal"]:
                obra_data["flujo_semanal"][semana] = 0

    # Convert to list - start with saldos previos
    familias_lista = []

    # Get saldos previos from database
    bancos = ["Banco Santander", "Banco Chile", "Banco BCI", "Banco Consorcio", "Banco ITAU"]
    saldos_previos = []

    # Get all bank values first
    all_banks_data = {}
    for banco in bancos:
        saldos_db = conn.execute('''
            SELECT semana, valor FROM saldos_previos_bancos WHERE banco = ?
        ''', (banco,)).fetchall()
        all_banks_data[banco] = {row['semana']: row['valor'] for row in saldos_db}

    # Create placeholder for Saldo Total Previo (will be calculated later)
    saldo_total = {
        "familia": "Saldo Total Previo",
        "tipo_flujo": "Saldo Previo",
        "presupuesto_inicial": 0,
        "modificaciones": 0,
        "gasto_real": 0,
        "flujo_semanal": {semana: 0 for semana in semanas_ordenadas}
    }

    saldos_previos.append(saldo_total)

    # Add bank rows (editable)
    for banco in bancos:
        banco_data = {
            "familia": banco,
            "tipo_flujo": "Saldo Previo",
            "presupuesto_inicial": 0,
            "modificaciones": 0,
            "gasto_real": 0,
            "flujo_semanal": {},
            "editable": True
        }

        for semana in semanas_ordenadas:
            banco_data["flujo_semanal"][semana] = all_banks_data[banco].get(semana, 0)

        saldos_previos.append(banco_data)
    familias_lista.extend(saldos_previos)

    # Add editable ingresos rows before the ingresos por obra
    tipos_ingresos_editables = ["Facturación Emitida", "Préstamos", "Otros"]

    # Get editable ingresos data from database
    editable_ingresos_data = {}
    for tipo in tipos_ingresos_editables:
        editable_db = conn.execute('''
            SELECT semana, valor FROM flujo_cajas_editable_ingresos WHERE tipo_ingreso = ?
        ''', (tipo,)).fetchall()
        editable_ingresos_data[tipo] = {row['semana']: row['valor'] for row in editable_db}

    # Add "Facturación Emitida" first
    facturacion_data = {
        "familia": "Facturación Emitida",
        "tipo_flujo": "Ingresos por Obra",
        "presupuesto_inicial": 0,
        "modificaciones": 0,
        "gasto_real": 0,
        "flujo_semanal": {},
        "editable": True
    }
    for semana in semanas_ordenadas:
        facturacion_data["flujo_semanal"][semana] = editable_ingresos_data["Facturación Emitida"].get(semana, 0)
    familias_lista.append(facturacion_data)

    # Add "Préstamos" second
    prestamos_data = {
        "familia": "Préstamos",
        "tipo_flujo": "Ingresos por Obra",
        "presupuesto_inicial": 0,
        "modificaciones": 0,
        "gasto_real": 0,
        "flujo_semanal": {},
        "editable": True
    }
    for semana in semanas_ordenadas:
        prestamos_data["flujo_semanal"][semana] = editable_ingresos_data["Préstamos"].get(semana, 0)
    familias_lista.append(prestamos_data)

    # Add ingresos por obra next (sorted alphabetically)
    ingresos_ordenados = sorted(ingresos_por_obra.values(), key=lambda x: x["familia"])
    familias_lista.extend(ingresos_ordenados)

    # Add "Otros" at the end of Ingresos por Obra
    otros_data = {
        "familia": "Otros",
        "tipo_flujo": "Ingresos por Obra",
        "presupuesto_inicial": 0,
        "modificaciones": 0,
        "gasto_real": 0,
        "flujo_semanal": {},
        "editable": True
    }
    for semana in semanas_ordenadas:
        otros_data["flujo_semanal"][semana] = editable_ingresos_data["Otros"].get(semana, 0)
    familias_lista.append(otros_data)

    # Add credits as a payment category
    creditos = conn.execute('''
        SELECT * FROM creditos WHERE cuotas_restantes > 0
        ORDER BY fecha_pago ASC
    ''').fetchall()

    # Calculate weekly credit payments (monthly payments distributed to corresponding weeks)
    creditos_flujo_semanal = {}
    for semana in semanas_ordenadas:
        creditos_flujo_semanal[semana] = 0

    # Get the start and end dates of the cash flow period for optimization
    if semanas_ordenadas:
        flujo_start = datetime.strptime(semanas_ordenadas[0], '%Y-%m-%d')
        flujo_end = datetime.strptime(semanas_ordenadas[-1], '%Y-%m-%d') + timedelta(days=6)

        for credito in creditos:
            fecha_pago_inicial = datetime.strptime(credito['fecha_pago'], '%Y-%m-%d')
            cuotas_restantes = credito['cuotas_restantes']
            valor_cuota = credito['valor_cuota']

            # Calculate all future monthly payments that fall within the cash flow period
            for cuota_num in range(cuotas_restantes):
                # Calculate the payment date for this installment (monthly)
                # Use more accurate month calculation
                year = fecha_pago_inicial.year
                month = fecha_pago_inicial.month + cuota_num
                day = fecha_pago_inicial.day

                # Handle month overflow
                while month > 12:
                    month -= 12
                    year += 1

                try:
                    fecha_pago_actual = datetime(year, month, day)
                except ValueError:
                    # Handle end-of-month cases (e.g., Feb 31 -> Feb 28)
                    import calendar
                    max_day = calendar.monthrange(year, month)[1]
                    fecha_pago_actual = datetime(year, month, min(day, max_day))

                # Only process payments within the cash flow period
                if flujo_start <= fecha_pago_actual <= flujo_end:
                    # Find which week this payment falls into
                    for semana in semanas_ordenadas:
                        semana_datetime = datetime.strptime(semana, '%Y-%m-%d')
                        week_start = semana_datetime
                        week_end = semana_datetime + timedelta(days=6)

                        if week_start <= fecha_pago_actual <= week_end:
                            creditos_flujo_semanal[semana] += valor_cuota
                            break

    # Add credits family to the aggregated families (only if there are any credits or payments)
    total_creditos_valor = sum(creditos_flujo_semanal.values())
    print(f"DEBUG - Créditos encontrados: {len(creditos)}")
    print(f"DEBUG - Total valor créditos: {total_creditos_valor}")
    print(f"DEBUG - Flujo semanal créditos: {creditos_flujo_semanal}")

    if creditos or total_creditos_valor > 0:
        familias_agregadas["Créditos"] = {
            "familia": "Créditos",
            "tipo_flujo": "Pagos",
            "presupuesto_inicial": sum(credito['valor_cuota'] * credito['cuotas_restantes'] for credito in creditos),
            "modificaciones": 0,
            "gasto_real": 0,
            "flujo_semanal": creditos_flujo_semanal
        }
        print(f"DEBUG - Familia Créditos agregada a familias_agregadas")
    else:
        print(f"DEBUG - NO se agregó familia Créditos - sin créditos o pagos")

    # Add other families alphabetically
    otras_familias = [familias_agregadas[k] for k in sorted(familias_agregadas.keys())]
    print(f"DEBUG - Familias agregadas keys: {list(familias_agregadas.keys())}")
    print(f"DEBUG - Otras familias a agregar: {[f['familia'] for f in otras_familias]}")
    familias_lista.extend(otras_familias)
    print(f"DEBUG - Familias en lista final: {[f['familia'] for f in familias_lista]}")

    # Calculate total ingresos row (sum of all ingresos por obra)
    total_ingresos = {
        "familia": "TOTAL INGRESOS",
        "tipo_flujo": "Ingresos por Obra",
        "presupuesto_inicial": 0,
        "modificaciones": 0,
        "gasto_real": 0,
        "flujo_semanal": {semana: 0 for semana in semanas_ordenadas}
    }

    # Sum all ingresos por obra
    for obra_data in ingresos_por_obra.values():
        total_ingresos["presupuesto_inicial"] += obra_data["presupuesto_inicial"]
        total_ingresos["modificaciones"] += obra_data["modificaciones"]
        total_ingresos["gasto_real"] += obra_data["gasto_real"]

        for semana in semanas_ordenadas:
            total_ingresos["flujo_semanal"][semana] += obra_data["flujo_semanal"].get(semana, 0)

    # Sum all editable ingresos values
    for tipo in tipos_ingresos_editables:
        for semana in semanas_ordenadas:
            total_ingresos["flujo_semanal"][semana] += editable_ingresos_data[tipo].get(semana, 0)

    # Calculate total pagos row (sum of all other families)
    total_pagos = {
        "familia": "TOTAL PAGOS",
        "tipo_flujo": "Pagos",
        "presupuesto_inicial": 0,
        "modificaciones": 0,
        "gasto_real": 0,
        "flujo_semanal": {semana: 0 for semana in semanas_ordenadas}
    }

    # Sum all pagos (other families)
    for familia_data in familias_agregadas.values():
        total_pagos["presupuesto_inicial"] += familia_data["presupuesto_inicial"]
        total_pagos["modificaciones"] += familia_data["modificaciones"]
        total_pagos["gasto_real"] += familia_data["gasto_real"]

        for semana in semanas_ordenadas:
            total_pagos["flujo_semanal"][semana] += familia_data["flujo_semanal"].get(semana, 0)

    # Calculate total row (ingresos - pagos)
    total_resumen = {
        "familia": "TOTAL",
        "tipo_flujo": "Total",
        "presupuesto_inicial": total_ingresos["presupuesto_inicial"] - total_pagos["presupuesto_inicial"],
        "modificaciones": total_ingresos["modificaciones"] - total_pagos["modificaciones"],
        "gasto_real": total_ingresos["gasto_real"] - total_pagos["gasto_real"],
        "flujo_semanal": {}
    }

    for semana in semanas_ordenadas:
        total_resumen["flujo_semanal"][semana] = total_ingresos["flujo_semanal"][semana] - total_pagos["flujo_semanal"][semana]

    # Calculate Saldo Total Previo with the new logic
    saldo_total_previo_semana = {}

    for i, semana in enumerate(semanas_ordenadas):
        # Sum all other Saldo Previo rows (banks) for this week
        suma_bancos = sum(all_banks_data[banco].get(semana, 0) for banco in bancos)

        if suma_bancos > 0:
            # If there are values in bank rows, use the sum
            saldo_total_previo_semana[semana] = suma_bancos
        else:
            # If sum is zero, calculate as: previous week's Saldo Total Previo + previous week's TOTAL
            if i == 0:
                # For the first week, if no bank values, start with 0
                saldo_total_previo_semana[semana] = 0
            else:
                semana_anterior = semanas_ordenadas[i - 1]
                saldo_anterior = saldo_total_previo_semana.get(semana_anterior, 0)
                total_anterior = total_resumen["flujo_semanal"].get(semana_anterior, 0)
                saldo_total_previo_semana[semana] = saldo_anterior + total_anterior

    # Update the Saldo Total Previo in familias_lista
    for familia in familias_lista:
        if familia["familia"] == "Saldo Total Previo" and familia["tipo_flujo"] == "Saldo Previo":
            familia["flujo_semanal"] = saldo_total_previo_semana
            break

    # Get credits for the credits management section
    creditos_db = conn.execute('''
        SELECT * FROM creditos ORDER BY fecha_pago ASC
    ''').fetchall()

    conn.close()

    return templates.TemplateResponse("flujo_caja.html", {
        "request": request,
        "user": user,
        "familias_resumen": familias_lista,
        "total_ingresos": total_ingresos,
        "total_pagos": total_pagos,
        "total_resumen": total_resumen,
        "semanas": semanas_ordenadas,
        "obras": obras,
        "creditos": creditos_db
    })

@app.post("/flujo-caja/saldos-previos")
async def update_saldo_previo(request: Request, banco: str = Form(...), semana: str = Form(...), valor: float = Form(...)):
    user = get_current_user(request)
    if not user:
        return {"success": False, "message": "No autorizado"}

    if not (user['is_admin'] or user['is_manager']):
        return {"success": False, "message": "Acceso denegado"}

    conn = get_db_connection()

    try:
        conn.execute('''
            INSERT OR REPLACE INTO saldos_previos_bancos (banco, semana, valor)
            VALUES (?, ?, ?)
        ''', (banco, semana, valor))
        conn.commit()
        conn.close()

        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "message": str(e)}

@app.post("/flujo-caja/ingresos-editables")
async def update_ingreso_editable(request: Request, tipo_ingreso: str = Form(...), semana: str = Form(...), valor: float = Form(...)):
    user = get_current_user(request)
    if not user:
        return {"success": False, "message": "No autorizado"}

    if not (user['is_admin'] or user['is_manager']):
        return {"success": False, "message": "Acceso denegado"}

    conn = get_db_connection()

    try:
        conn.execute('''
            INSERT OR REPLACE INTO flujo_cajas_editable_ingresos (tipo_ingreso, semana, valor)
            VALUES (?, ?, ?)
        ''', (tipo_ingreso, semana, valor))
        conn.commit()
        conn.close()

        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "message": str(e)}

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    user = get_current_user(request)
    if not user or not user['is_admin']:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY name').fetchall()
    conn.close()
    
    return templates.TemplateResponse("admin_users.html", {
        "request": request, 
        "user": user, 
        "users": [dict(u) for u in users]
    })

@app.post("/admin/users")
async def create_user(request: Request, name: str = Form(...), email: str = Form(...),
                     password: str = Form(...), is_admin: str = Form(None), is_manager: str = Form(None), is_admin_obra: str = Form(None)):
    user = get_current_user(request)
    if not user or not user['is_admin']:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    conn = get_db_connection()
    password_hash = hash_password(password)

    # Convertir valores de checkbox
    is_admin_bool = is_admin == "true"
    is_manager_bool = is_manager == "true"
    is_admin_obra_bool = is_admin_obra == "true"

    try:
        conn.execute('''
            INSERT INTO users (name, email, password_hash, is_admin, is_manager, is_admin_obra)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, email, password_hash, is_admin_bool, is_manager_bool, is_admin_obra_bool))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return RedirectResponse(url="/admin/users?error=email_exists", status_code=302)
    
    conn.close()
    return RedirectResponse(url="/admin/users?success=1", status_code=302)

@app.post("/admin/users/{user_id}/delete")
async def delete_user(request: Request, user_id: int):
    user = get_current_user(request)
    if not user or not user['is_admin']:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    if user_id == user['id']:
        return RedirectResponse(url="/admin/users?error=cannot_delete_self", status_code=302)
    
    conn = get_db_connection()
    conn.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/admin/users?success=deleted", status_code=302)

@app.get("/aprobaciones", response_class=HTMLResponse)
async def aprobaciones(request: Request):
    user = get_current_user(request)
    if not user or not user['is_manager']:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    return templates.TemplateResponse("aprobaciones.html", {"request": request, "user": user})

@app.get("/aprobaciones/transferencias", response_class=HTMLResponse)
async def aprobaciones_transferencias(request: Request):
    user = get_current_user(request)
    if not user or not user['is_manager']:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    return templates.TemplateResponse("aprobaciones_transferencias.html", {"request": request, "user": user})

@app.get("/api/aprobaciones/transferencias")
async def get_transferencias_data(request: Request):
    user = get_current_user(request)
    if not user or not user['is_manager']:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    try:
        # Verificar si ya existe el archivo de transferencias guardado
        if os.path.exists(TRANSFERENCIAS_XLSX):
            df = pd.read_excel(TRANSFERENCIAS_XLSX)
        else:
            # Si no existe, cargar desde pagos_mostrar.xlsx
            pagos_mostrar_path = os.path.join(PERSISTENT_DIR, "pagos_mostrar.xlsx")
            
            if not os.path.exists(pagos_mostrar_path):
                return {"data": [], "message": "No hay datos de planilla de pagos disponibles"}
            
            # Cargar los datos existentes
            df = pd.read_excel(pagos_mostrar_path)
            
            if df.empty:
                return {"data": [], "message": "Planilla de pagos está vacía"}
            
            # Seleccionar las columnas específicas requeridas con variaciones
            column_mapping = {
                "Rut": ["Rut", "RUT"],
                "Razón Social": ["Razón Social", "Razon Social"],
                "Cuenta destino": ["Cuenta destino", "Cuenta destino (obligatorio)", "Cuenta destino\n(obligatorio)", "Número de cuenta destino\n(obligatorio)"],
                "Monto transferencia": ["Monto transferencia\n(obligatorio)", "Monto transferencia (obligatorio)", "Monto transferencia"],
                "Glosa personalizada transferencia": ["Glosa personalizada transferencia", "Glosa personalizada transferencia\n(opcional)"]
            }
            
            # Encontrar columnas disponibles y crear mapeo
            available_columns = []
            column_rename_map = {}
            
            for target_col, variations in column_mapping.items():
                found = False
                for variation in variations:
                    if variation in df.columns:
                        available_columns.append(variation)
                        column_rename_map[variation] = target_col
                        found = True
                        break
                
                if not found:
                    # Si no se encuentra ninguna variación, mantener el nombre objetivo
                    available_columns.append(target_col)
            
            # Filtrar DataFrame con las columnas disponibles
            df_filtered = df[available_columns] if available_columns else df
            
            # Renombrar columnas para estandarizar nombres
            df_filtered = df_filtered.rename(columns=column_rename_map)
            
            # Agregar nuevas columnas si no existen
            if 'Transferido' not in df_filtered.columns:
                df_filtered['Transferido'] = False
            if 'Fecha Transferencia' not in df_filtered.columns:
                df_filtered['Fecha Transferencia'] = None
                
            df = df_filtered
        
        # Limpiar datos para JSON serialization
        df_clean = df.replace([np.nan, np.inf, -np.inf], None)
        
        # Convertir valores booleanos para el frontend
        if 'Transferido' in df_clean.columns:
            df_clean['Transferido'] = df_clean['Transferido'].astype(bool)
        
        # Convertir a lista de diccionarios
        data = df_clean.to_dict('records')
        
        return {
            "data": data,
            "total_records": len(data),
            "columns": list(df_clean.columns)
        }
        
    except Exception as e:
        print(f"❌ Error al obtener datos de transferencias: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener datos: {str(e)}")

@app.post("/api/aprobaciones/transferencias/guardar")
async def guardar_transferencias(request: Request):
    user = get_current_user(request)
    if not user or not user['is_manager']:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    try:
        body = await request.json()
        data = body.get('data', [])
        saldo_cc = body.get('saldo_cc', 0)
        
        if not data:
            raise HTTPException(status_code=400, detail="No hay datos para guardar")
        
        # Crear DataFrame desde los datos
        df = pd.DataFrame(data)
        
        # Agregar metadatos
        df.attrs['saldo_cc'] = saldo_cc
        df.attrs['fecha_guardado'] = datetime.now().isoformat()
        
        # Guardar en archivo Excel con metadatos
        with pd.ExcelWriter(TRANSFERENCIAS_XLSX, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Transferencias', index=False)
            
            # Crear hoja de metadatos
            metadata_df = pd.DataFrame([{
                'saldo_cuenta_corriente': saldo_cc,
                'fecha_guardado': datetime.now().isoformat()
            }])
            metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
        
        return {"success": True, "message": "Datos guardados correctamente"}
        
    except Exception as e:
        print(f"❌ Error al guardar transferencias: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al guardar datos: {str(e)}")

@app.get("/api/aprobaciones/transferencias/metadata")
async def get_transferencias_metadata(request: Request):
    user = get_current_user(request)
    if not user or not user['is_manager']:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    try:
        if not os.path.exists(TRANSFERENCIAS_XLSX):
            return {"saldo_cuenta_corriente": 0, "fecha_guardado": None}
        
        # Leer metadatos
        metadata_df = pd.read_excel(TRANSFERENCIAS_XLSX, sheet_name='Metadata')
        
        if metadata_df.empty:
            return {"saldo_cuenta_corriente": 0, "fecha_guardado": None}
        
        metadata = metadata_df.iloc[0].to_dict()
        return {
            "saldo_cuenta_corriente": metadata.get('saldo_cuenta_corriente', 0),
            "fecha_guardado": metadata.get('fecha_guardado', None)
        }
        
    except Exception as e:
        print(f"❌ Error al obtener metadatos: {str(e)}")
        return {"saldo_cuenta_corriente": 0, "fecha_guardado": None}

@app.get("/facturas", response_class=HTMLResponse)
async def facturas(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("facturas.html", {"request": request, "user": user})

@app.get("/api/facturas")
async def get_facturas(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        df = pd.read_csv(FACTURAS_CSV)
        
        # Agregar campo Subidas
        df = agregar_campo_subidas_a_facturas(df)
        
        column_config = {
            'idDocumento': {'web_name': 'ID', 'filterable': False},
            'numDoc': {'web_name': 'No', 'filterable': False},
            'folioDoc': {'web_name': 'No', 'filterable': False},
            'folioUnico': {'web_name': 'Folio', 'filterable': False},
            'origenFactura': {'web_name': 'Origen', 'filterable': False},
            'tipoFactura': {'web_name': 'Tipo', 'filterable': True},
            'tipoDocAsociado': {'web_name': 'Doc. Asociado', 'filterable': False},
            'nomProveedor': {'web_name': 'Razón Social', 'filterable': False},
            'rutProveedor': {'web_name': 'Rut', 'filterable': False},
            'centroGestion': {'web_name': 'Centro de Costo', 'filterable': False},
            'fechaSistema': {'web_name': 'No', 'filterable': False},
            'fechaEmision': {'web_name': 'Fecha Emisión', 'filterable': True},
            'fechaEstimadaPago': {'web_name': 'Fecha Pago', 'filterable': False},
            'fechaRecepSII': {'web_name': 'Fecha Recepción SII', 'filterable': False},
            'fechaRecepcion': {'web_name': 'Fecha Recepción', 'filterable': False},
            'moneda': {'web_name': 'Moneda', 'filterable': False},
            'montoTotal': {'web_name': 'Total ($)', 'filterable': False},
            'montoNeto': {'web_name': 'Neto Afecto ($)', 'filterable': False},
            'montoNoAfectoOExento': {'web_name': 'No Afecto ($)', 'filterable': False},
            'estadoDoc': {'web_name': 'Estado', 'filterable': True},
            'estadoAsociacion': {'web_name': 'Asociada', 'filterable': False},
            'estadoPago': {'web_name': 'Pago', 'filterable': False},
            'estadoPagoSii': {'web_name': 'Pago SII', 'filterable': False},
            'FechaIngreso': {'web_name': 'No', 'filterable': False},
            'ConceptoCompras': {'web_name': 'Concepto Compras', 'filterable': True},
            'Cliente': {'web_name': 'No', 'filterable': False},
            'Proveedor': {'web_name': 'No', 'filterable': False},
            'Honorario': {'web_name': 'No', 'filterable': False},
            'Empleado': {'web_name': 'No', 'filterable': False},
            'Cuenta': {'web_name': 'No', 'filterable': False},
            'Cuenta 2': {'web_name': 'Cuenta', 'filterable': True},
            'Centro': {'web_name': 'ID Centro de Costo', 'filterable': True},
            'Unidad de Negocio': {'web_name': 'Centro Costo KAME', 'filterable': True},
            'Estado': {'web_name': 'No', 'filterable': False},
            'Subidas': {'web_name': 'Subidas', 'filterable': True}
        }
        
        visible_columns = []
        filterable_columns = []
        
        for col in df.columns:
            if col in column_config and column_config[col]['web_name'] != 'No':
                visible_columns.append({
                    'original': col,
                    'display': column_config[col]['web_name'],
                    'filterable': column_config[col]['filterable']
                })
                if column_config[col]['filterable']:
                    filterable_columns.append(col)
        
        df_visible = df[[col['original'] for col in visible_columns]]
        
        df_visible = df_visible.fillna('')
        
        return {
            "data": df_visible.to_dict('records'),
            "columns": visible_columns,
            "filterable_columns": filterable_columns
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading CSV: {str(e)}")

@app.post("/api/subir-kame")
async def subir_kame(request: Request, data: SubirKameRequest):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        print(f"📥 Recibida solicitud para procesar {len(data.facturas)} facturas")
        
        # Cargar el DataFrame completo desde facturas.csv
        df = cargar_csv_a_dataframe(FACTURAS_CSV)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No se pudo cargar el archivo facturas.csv")
        
        # Agregar campo Subidas
        df = agregar_campo_subidas_a_facturas(df)
        
        results = []
        
        # Procesar cada factura seleccionada
        for factura in data.facturas:
            try:
                print(f"🔄 Procesando factura ID: {factura.idDocumento}")
                
                # Llamar a la función subir_facturas_kame con el ID y el DataFrame completo
                result = subir_facturas_kame(factura.idDocumento, df)
                
                if result == True:
                    print(f"✅ Factura {factura.idDocumento} enviada exitosamente")
                    results.append({
                        "idDocumento": factura.idDocumento,
                        "success": True,
                        "error": None
                    })
                elif result == "ALREADY_UPLOADED":
                    print(f"❌ Factura {factura.idDocumento} ya está subida a Kame")
                    results.append({
                        "idDocumento": factura.idDocumento,
                        "success": False,
                        "error": "La factura ya está subida a Kame"
                    })
                elif result == "CANCELLED":
                    print(f"❌ Factura {factura.idDocumento} está cancelada")
                    results.append({
                        "idDocumento": factura.idDocumento,
                        "success": False,
                        "error": "No se puede subir una factura cancelada"
                    })
                else:
                    print(f"❌ Error en factura {factura.idDocumento}: función retornó False")
                    results.append({
                        "idDocumento": factura.idDocumento,
                        "success": False,
                        "error": "Posiblemente falta la cuenta contable"
                    })
                    
            except Exception as e:
                print(f"❌ Excepción en factura {factura.idDocumento}: {str(e)}")
                results.append({
                    "idDocumento": factura.idDocumento,
                    "success": False,
                    "error": str(e)
                })
        
        print(f"📊 Procesamiento completado: {len([r for r in results if r['success']])} exitosas, {len([r for r in results if not r['success']])} fallidas")
        return {"results": results}
        
    except Exception as e:
        print(f"❌ Error general al procesar facturas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar las facturas: {str(e)}")

@app.post("/api/facturas/borrar")
async def borrar_facturas(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    try:
        body = await request.json()
        ids_borrar = body.get("idsBorrar", [])
        if not ids_borrar or not isinstance(ids_borrar, list):
            raise HTTPException(status_code=400, detail="No se especificaron IDs válidos para borrar")
        # Convertir a enteros
        ids_borrar = [int(x) for x in ids_borrar]
        from funciones import borrar_facturas_por_ids
        eliminadas_facturas, eliminadas_subidas = borrar_facturas_por_ids(ids_borrar, borrar_de_subidas=False)
        return {
            "success": True,
            "eliminadas_facturas": eliminadas_facturas,
            "eliminadas_subidas": eliminadas_subidas,
            "message": f"Se eliminaron {eliminadas_facturas} facturas y {eliminadas_subidas} registros de subidas."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al borrar facturas: {str(e)}")

@app.post("/api/exportar-excel")
async def exportar_excel(request: Request, filters: dict = None):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Cargar datos
        df = pd.read_csv(FACTURAS_CSV)
        df = agregar_campo_subidas_a_facturas(df)
        
        # Aplicar filtros si se proporcionan
        if filters:
            # Aplicar filtros usando la misma lógica que el frontend
            filtered_df = df.copy()
            
            # Filtros generales
            for key, value in filters.items():
                if not value or key in ['fechaInicio', 'fechaFin']:
                    continue
                    
                column_name = key
                if key == 'Cuenta2':
                    column_name = 'Cuenta 2'
                elif key == 'UnidadNegocio':
                    column_name = 'Unidad de Negocio'
                
                # Filtro especial para cuentas vacías
                if key == 'Cuenta2' and value == '__EMPTY__':
                    filtered_df = filtered_df[filtered_df[column_name].fillna('').astype(str).str.strip() == '']
                else:
                    filtered_df = filtered_df[filtered_df[column_name].fillna('').astype(str).str.lower().str.contains(value.lower(), na=False)]
            
            # Filtro de fechas
            if 'fechaInicio' in filters and filters['fechaInicio']:
                fecha_inicio = filters['fechaInicio']
                filtered_df = filtered_df[pd.to_datetime(filtered_df['fechaEmision'], errors='coerce') >= pd.to_datetime(fecha_inicio)]
            
            if 'fechaFin' in filters and filters['fechaFin']:
                fecha_fin = filters['fechaFin']
                filtered_df = filtered_df[pd.to_datetime(filtered_df['fechaEmision'], errors='coerce') <= pd.to_datetime(fecha_fin)]
            
            df = filtered_df
        
        # Configurar columnas visibles
        column_config = {
            'idDocumento': {'web_name': 'ID', 'filterable': False},
            'numDoc': {'web_name': 'No', 'filterable': False},
            'folioDoc': {'web_name': 'No', 'filterable': False},
            'folioUnico': {'web_name': 'Folio', 'filterable': False},
            'origenFactura': {'web_name': 'Origen', 'filterable': False},
            'tipoFactura': {'web_name': 'Tipo', 'filterable': True},
            'tipoDocAsociado': {'web_name': 'Doc. Asociado', 'filterable': False},
            'nomProveedor': {'web_name': 'Razón Social', 'filterable': False},
            'rutProveedor': {'web_name': 'Rut', 'filterable': False},
            'centroGestion': {'web_name': 'Centro de Costo', 'filterable': False},
            'fechaSistema': {'web_name': 'No', 'filterable': False},
            'fechaEmision': {'web_name': 'Fecha Emisión', 'filterable': True},
            'fechaEstimadaPago': {'web_name': 'Fecha Pago', 'filterable': False},
            'fechaRecepSII': {'web_name': 'Fecha Recepción SII', 'filterable': False},
            'fechaRecepcion': {'web_name': 'Fecha Recepción', 'filterable': False},
            'moneda': {'web_name': 'Moneda', 'filterable': False},
            'montoTotal': {'web_name': 'Total ($)', 'filterable': False},
            'montoNeto': {'web_name': 'Neto Afecto ($)', 'filterable': False},
            'montoNoAfectoOExento': {'web_name': 'No Afecto ($)', 'filterable': False},
            'estadoDoc': {'web_name': 'Estado', 'filterable': True},
            'estadoAsociacion': {'web_name': 'Asociada', 'filterable': False},
            'estadoPago': {'web_name': 'Pago', 'filterable': False},
            'estadoPagoSii': {'web_name': 'Pago SII', 'filterable': False},
            'FechaIngreso': {'web_name': 'No', 'filterable': False},
            'ConceptoCompras': {'web_name': 'Concepto Compras', 'filterable': True},
            'Cliente': {'web_name': 'No', 'filterable': False},
            'Proveedor': {'web_name': 'No', 'filterable': False},
            'Honorario': {'web_name': 'No', 'filterable': False},
            'Empleado': {'web_name': 'No', 'filterable': False},
            'Cuenta': {'web_name': 'No', 'filterable': False},
            'Cuenta 2': {'web_name': 'Cuenta', 'filterable': True},
            'Centro': {'web_name': 'ID Centro de Costo', 'filterable': True},
            'Unidad de Negocio': {'web_name': 'Centro Costo KAME', 'filterable': True},
            'Estado': {'web_name': 'No', 'filterable': False},
            'Subidas': {'web_name': 'Subidas', 'filterable': True}
        }
        
        # Filtrar y renombrar columnas
        visible_columns = []
        for col in df.columns:
            if col in column_config and column_config[col]['web_name'] != 'No':
                visible_columns.append(col)
        
        df_export = df[visible_columns].copy()
        
        # Renombrar columnas para Excel
        rename_dict = {}
        for col in visible_columns:
            if col in column_config:
                rename_dict[col] = column_config[col]['web_name']
        
        df_export = df_export.rename(columns=rename_dict)
        df_export = df_export.fillna('')
        
        # Crear archivo Excel en memoria usando el engine por defecto
        buffer = io.BytesIO()
        
        # Intentar usar openpyxl primero, luego xlsxwriter, finalmente fallback a CSV
        try:
            # Intentar con openpyxl
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_export.to_excel(writer, sheet_name='Facturas', index=False)
            
            media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f"facturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
        except ImportError:
            try:
                # Intentar con xlsxwriter
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_export.to_excel(writer, sheet_name='Facturas', index=False)
                
                media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                filename = f"facturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                
            except ImportError:
                # Fallback a CSV
                buffer = io.StringIO()
                df_export.to_csv(buffer, index=False, encoding='utf-8')
                buffer = io.BytesIO(buffer.getvalue().encode('utf-8'))
                
                media_type = 'text/csv'
                filename = f"facturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        buffer.seek(0)
        
        return StreamingResponse(
            io.BytesIO(buffer.read()),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        print(f"❌ Error al exportar Excel: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al exportar Excel: {str(e)}")

@app.get("/preparar-facturas", response_class=HTMLResponse)
async def preparar_facturas_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("preparar_facturas.html", {"request": request, "user": user})

@app.post("/api/preparar-facturas")
async def api_preparar_facturas(request: Request, fecha_inicio: str = Form(...), fecha_final: str = Form(...)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        print(f"📅 Preparando facturas desde {fecha_inicio} hasta {fecha_final}")
        preparar_facturas(fecha_inicio, fecha_final)
        return {"success": True, "message": "Facturas preparadas exitosamente"}
    except Exception as e:
        print(f"❌ Error al preparar facturas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al preparar facturas: {str(e)}")

# Módulo Facturas Subidas
@app.get("/facturas-subidas", response_class=HTMLResponse)
async def facturas_subidas_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("facturas_subidas.html", {"request": request, "user": user})

@app.get("/api/facturas-subidas")
async def get_facturas_subidas(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Cargar datos completos desde facturas_subidas_datos.csv
        facturas_info = []
        
        if os.path.exists(FACTURAS_SUBIDAS_CSV):
            df = pd.read_csv(FACTURAS_SUBIDAS_CSV, encoding='utf-8-sig')
            
            for _, fila_data in df.iterrows():
                facturas_info.append({
                    'idDocumento': int(fila_data['idDocumento']),
                    'folioUnico': str(fila_data['folioUnico']),
                    'rutProveedor': str(fila_data['rutProveedor']),
                    'nomProveedor': str(fila_data['nomProveedor']),
                    'fechaEmision': str(fila_data['fechaEmision'])[:10] if pd.notna(fila_data['fechaEmision']) else '',
                    'montoNeto': float(fila_data['montoNeto']) if pd.notna(fila_data['montoNeto']) else 0
                })
        
        return {"facturas": facturas_info}
        
    except Exception as e:
        print(f"❌ Error al cargar facturas subidas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al cargar facturas subidas: {str(e)}")

@app.post("/api/facturas-subidas/eliminar")
async def eliminar_facturas_subidas(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Leer el cuerpo de la petición
        body = await request.json()
        ids_eliminar = body.get('idsEliminar', [])
        
        if not ids_eliminar:
            raise HTTPException(status_code=400, detail="No se especificaron IDs para eliminar")
        
        # Eliminar de subidas.csv
        archivo_subidas = SUBIDAS_CSV
        ids_actuales = []
        if os.path.exists(archivo_subidas):
            import csv
            with open(archivo_subidas, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader, None)  # Saltar cabecera
                for row in reader:
                    if row and int(row[0]) not in ids_eliminar:
                        ids_actuales.append(row[0])
        
        # Reescribir subidas.csv sin los IDs eliminados
        with open(archivo_subidas, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['idDocumento'])
            for id_doc in ids_actuales:
                writer.writerow([id_doc])
        
        # Eliminar también de facturas_subidas_datos.csv
        if os.path.exists(FACTURAS_SUBIDAS_CSV):
            df = pd.read_csv(FACTURAS_SUBIDAS_CSV, encoding='utf-8-sig')
            df_filtrado = df[~df['idDocumento'].isin(ids_eliminar)]
            df_filtrado.to_csv(FACTURAS_SUBIDAS_CSV, index=False, encoding='utf-8-sig')
            print(f"✅ También eliminados de facturas_subidas_datos.csv")
        
        print(f"✅ Eliminados {len(ids_eliminar)} registros de facturas subidas")
        return {"success": True, "eliminadas": len(ids_eliminar)}
        
    except Exception as e:
        print(f"❌ Error al eliminar facturas subidas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar facturas subidas: {str(e)}")

# Módulo Cuentas
@app.get("/cuentas", response_class=HTMLResponse)
async def cuentas_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("cuentas.html", {"request": request, "user": user})

@app.get("/api/cuentas")
async def get_cuentas(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        df = pd.read_excel(CUENTAS_XLSX)
        df = df.fillna('')
        return {
            "data": df.to_dict('records'),
            "columns": df.columns.tolist()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cargar cuentas.xlsx: {str(e)}")

@app.post("/api/cuentas/guardar")
async def guardar_cuentas(request: Request, data: dict):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        if not data.get('data'):
            raise HTTPException(status_code=400, detail="No hay datos para guardar")
        
        df = pd.DataFrame(data['data'])
        
        if df.empty:
            raise HTTPException(status_code=400, detail="No se puede guardar un archivo vacío")
        
        # Convertir campos específicos a enteros
        integer_fields = ['Orden', 'Centro de Costo Previred']
        for field in integer_fields:
            if field in df.columns:
                # Convertir a numérico, valores no válidos se convierten a NaN
                df[field] = pd.to_numeric(df[field], errors='coerce')
                # Llenar NaN con 0 y convertir a entero
                df[field] = df[field].fillna(0).astype(int)
        
        df.to_excel(CUENTAS_XLSX, index=False)
        return {"success": True, "message": "Archivo cuentas.xlsx guardado exitosamente"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar cuentas.xlsx: {str(e)}")

# Módulo Centros de Costos
@app.get("/centros-costos", response_class=HTMLResponse)
async def centros_costos_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("centros_costos.html", {"request": request, "user": user})

@app.get("/api/centros-costos")
async def get_centros_costos(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        df = pd.read_excel(UN_XLSX)
        df = df.fillna('')
        return {
            "data": df.to_dict('records'),
            "columns": df.columns.tolist()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cargar UN.xlsx: {str(e)}")

@app.post("/api/centros-costos/guardar")
async def guardar_centros_costos(request: Request, data: dict):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        if not data.get('data'):
            raise HTTPException(status_code=400, detail="No hay datos para guardar")
        
        df = pd.DataFrame(data['data'])
        
        if df.empty:
            raise HTTPException(status_code=400, detail="No se puede guardar un archivo vacío")
        
        # Convertir campos específicos a enteros
        integer_fields = ['Orden', 'Centro de Costo Previred']
        for field in integer_fields:
            if field in df.columns:
                # Convertir a numérico, valores no válidos se convierten a NaN
                df[field] = pd.to_numeric(df[field], errors='coerce')
                # Llenar NaN con 0 y convertir a entero
                df[field] = df[field].fillna(0).astype(int)
        
        df.to_excel(UN_XLSX, index=False)
        return {"success": True, "message": "Archivo UN.xlsx guardado exitosamente"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar UN.xlsx: {str(e)}")

# Módulo Pagos
@app.get("/pagos", response_class=HTMLResponse)
async def pagos_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return RedirectResponse(url="/pagos/preparar-plantilla", status_code=302)

@app.get("/pagos/preparar-plantilla", response_class=HTMLResponse)
async def pagos_preparar_plantilla_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("pagos_preparar_plantilla.html", {"request": request, "user": user})

@app.get("/pagos/plantilla-preliminar", response_class=HTMLResponse)
async def pagos_plantilla_preliminar_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("pagos_plantilla_preliminar.html", {"request": request, "user": user})

@app.get("/pagos/cesiones", response_class=HTMLResponse)
async def pagos_cesiones_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("pagos_cesiones.html", {"request": request, "user": user})

@app.get("/pagos/planilla-pagos", response_class=HTMLResponse)
async def pagos_planilla_pagos_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("pagos_planilla_pagos.html", {"request": request, "user": user})

@app.post("/api/pagos/certificados")
async def subir_certificados(request: Request, certificadosFile: UploadFile = File(None)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        if certificadosFile:
            # Verificar que sea un PDF
            if not certificadosFile.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")
            
            # Leer el contenido del archivo
            content = await certificadosFile.read()
            
            # Guardar el archivo en el directorio persistente
            with open(CERTIFICADOS_SII_PDF, 'wb') as f:
                f.write(content)
            
            message = f"Archivo {certificadosFile.filename} subido y guardado como certificados_sii.pdf"
        else:
            # Si no se subió archivo, usar el certificados_sii.pdf por defecto
            archivo_local = "certificados_sii.pdf"
            
            if os.path.exists(archivo_local) and not os.path.exists(CERTIFICADOS_SII_PDF):
                # Copiar desde la ruta principal del proyecto al directorio persistente
                shutil.copy2(archivo_local, CERTIFICADOS_SII_PDF)
                message = "Se ha copiado el archivo certificados_sii.pdf por defecto al directorio persistente"
            elif os.path.exists(CERTIFICADOS_SII_PDF):
                message = "Se está utilizando el archivo certificados_sii.pdf existente en el directorio persistente"
            else:
                raise HTTPException(status_code=400, detail="No se encontró certificados_sii.pdf ni en la ruta principal ni fue subido un archivo")
        
        return {"success": True, "message": message}
        
    except Exception as e:
        print(f"❌ Error al procesar certificados: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar certificados: {str(e)}")

@app.post("/api/pagos/flujo-pagos")
async def ejecutar_flujo_pagos(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        print("📝 Iniciando procesamiento de flujo de pagos...")
        
        # Validar request body
        try:
            body = await request.json()
        except Exception as e:
            print(f"❌ Error al parsear JSON: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error al parsear JSON: {str(e)}")
        
        meses = body.get('meses', 3)
        print(f"📊 Meses solicitados: {meses}")
        
        if not isinstance(meses, int) or meses < 1 or meses > 12:
            raise HTTPException(status_code=400, detail="El número de meses debe ser entre 1 y 12")
        
        # Verificar que exista el archivo de certificados
        print(f"📁 Verificando archivo: {CERTIFICADOS_SII_PDF}")
        if not os.path.exists(CERTIFICADOS_SII_PDF):
            raise HTTPException(status_code=400, detail="No se encontró el archivo certificados_sii.pdf. Por favor suba un archivo primero.")
        
        print(f"🚀 Ejecutando flujo de pagos con {meses} meses hacia atrás")
        
        # Verificar importaciones
        try:
            from pagos import flujo_pagos
            print("✅ Importación de flujo_pagos exitosa")
        except ImportError as e:
            print(f"❌ Error de importación: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error de importación: {str(e)}")
        
        # Ejecutar la función flujo_pagos
        try:
            print("⚙️ Ejecutando función flujo_pagos...")
            resultados, cesiones_no_cruzadas = flujo_pagos(meses, CERTIFICADOS_SII_PDF)
            print("✅ Función flujo_pagos ejecutada correctamente")
        except Exception as e:
            print(f"❌ Error en flujo_pagos: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error en flujo_pagos: {str(e)}")
        
        # Verificar que los resultados no sean None
        if resultados is None:
            resultados = pd.DataFrame()
        if cesiones_no_cruzadas is None:
            cesiones_no_cruzadas = pd.DataFrame()
            
        print(f"📊 Resultados obtenidos - Tipo: {type(resultados)}, Shape: {getattr(resultados, 'shape', 'N/A')}")
        
        # Preparar estadísticas
        try:
            total_registros = len(resultados) if not resultados.empty else 0
            con_cesiones = len(resultados[resultados['Cesión'] == 'Sí']) if not resultados.empty and 'Cesión' in resultados.columns else 0
            sin_cesiones = len(resultados[resultados['Cesión'] == 'No']) if not resultados.empty and 'Cesión' in resultados.columns else 0
            cesiones_no_cruzadas_count = len(cesiones_no_cruzadas) if not cesiones_no_cruzadas.empty else 0
            
            estadisticas = {
                'total_registros': total_registros,
                'con_cesiones': con_cesiones,
                'sin_cesiones': sin_cesiones,
                'cesiones_no_cruzadas': cesiones_no_cruzadas_count
            }
            print(f"📈 Estadísticas calculadas: {estadisticas}")
        except Exception as e:
            print(f"❌ Error calculando estadísticas: {str(e)}")
            estadisticas = {'total_registros': 0, 'con_cesiones': 0, 'sin_cesiones': 0, 'cesiones_no_cruzadas': 0}
        
        print(f"✅ Flujo de pagos completado: {estadisticas['total_registros']} registros procesados")
        
        # Guardar la planilla en el directorio persistente
        archivo_guardado = None
        if not resultados.empty:
            try:
                # Guardar como Excel
                resultados.to_excel(PLANILLA_FLUJO_PAGOS_XLSX, index=False)
                archivo_guardado = PLANILLA_FLUJO_PAGOS_XLSX
                print(f"💾 Planilla guardada en: {PLANILLA_FLUJO_PAGOS_XLSX}")
                
                # También guardar como CSV para mayor compatibilidad
                resultados.to_csv(PLANILLA_FLUJO_PAGOS_CSV, index=False, encoding='utf-8-sig')
                print(f"💾 Planilla CSV guardada en: {PLANILLA_FLUJO_PAGOS_CSV}")
                
            except Exception as e:
                print(f"⚠️ Error al guardar planilla: {str(e)}")
        
        # Guardar cesiones no cruzadas
        if not cesiones_no_cruzadas.empty:
            try:
                cesiones_no_cruzadas.to_excel(CESIONES_NO_CRUZADAS_XLSX, index=False)
                cesiones_no_cruzadas.to_csv(CESIONES_NO_CRUZADAS_CSV, index=False, encoding='utf-8-sig')
                print(f"💾 Cesiones no cruzadas guardadas en: {CESIONES_NO_CRUZADAS_XLSX}")
                
            except Exception as e:
                print(f"⚠️ Error al guardar cesiones no cruzadas: {str(e)}")
        
        # Convertir DataFrame a lista de diccionarios para la respuesta
        data = []
        try:
            if not resultados.empty:
                # Convertir fechas a strings para serialización JSON
                resultados_copy = resultados.copy()
                
                # Limpiar valores NaN, inf y -inf para JSON serialización
                resultados_copy = resultados_copy.replace([np.nan, np.inf, -np.inf], None)
                
                for col in resultados_copy.columns:
                    if resultados_copy[col].dtype == 'datetime64[ns]':
                        resultados_copy[col] = resultados_copy[col].dt.strftime('%Y-%m-%d')
                    elif resultados_copy[col].dtype in ['float64', 'float32']:
                        # Convertir floats a números válidos o None
                        resultados_copy[col] = resultados_copy[col].apply(
                            lambda x: None if pd.isna(x) or np.isinf(x) else float(x)
                        )
                
                data = resultados_copy.to_dict('records')
                
                # Limpiar cada registro individualmente para asegurar compatibilidad JSON
                data = [clean_for_json(record) for record in data]
                
            print(f"📄 Data preparada: {len(data)} registros")
        except Exception as e:
            print(f"❌ Error preparando data: {str(e)}")
            import traceback
            traceback.print_exc()
            data = []
        
        # Limpiar estadísticas también
        estadisticas = clean_for_json(estadisticas)
        
        response_data = {
            "success": True, 
            "message": f"Flujo de pagos ejecutado exitosamente para {meses} meses",
            "data": data,
            "estadisticas": estadisticas,
            "archivo_guardado": os.path.basename(archivo_guardado) if archivo_guardado else None
        }
        
        return clean_for_json(response_data)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"❌ Error general al ejecutar flujo de pagos: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al ejecutar flujo de pagos: {str(e)}")

@app.get("/api/pagos/plantilla-preliminar")
async def get_plantilla_preliminar(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Verificar si existe el archivo
        if not os.path.exists(PLANILLA_FLUJO_PAGOS_CSV):
            return {"success": False, "message": "No hay datos disponibles. Execute el flujo de pagos primero."}
        
        # Cargar datos desde CSV
        df = pd.read_csv(PLANILLA_FLUJO_PAGOS_CSV, encoding='utf-8-sig')
        
        if df.empty:
            return {"success": False, "message": "No hay datos en la planilla."}
        
        # Preparar estadísticas
        total_registros = len(df)
        con_cesiones = len(df[df['Cesión'] == 'Sí']) if 'Cesión' in df.columns else 0
        sin_cesiones = len(df[df['Cesión'] == 'No']) if 'Cesión' in df.columns else 0
        
        estadisticas = {
            'total_registros': total_registros,
            'con_cesiones': con_cesiones,
            'sin_cesiones': sin_cesiones
        }
        
        # Limpiar datos para JSON
        df_clean = df.replace([np.nan, np.inf, -np.inf], None)
        
        # Convertir fechas a strings
        for col in df_clean.columns:
            if df_clean[col].dtype == 'datetime64[ns]':
                df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d')
        
        data = df_clean.to_dict('records')
        data = [clean_for_json(record) for record in data]
        
        return {
            "success": True,
            "data": data,
            "estadisticas": estadisticas
        }
        
    except Exception as e:
        print(f"❌ Error al cargar plantilla preliminar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al cargar datos: {str(e)}")

@app.post("/api/pagos/plantilla-preliminar")
async def save_plantilla_preliminar(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Obtener datos del request
        body = await request.json()
        data = body.get('data', [])
        
        if not data:
            raise HTTPException(status_code=400, detail="No hay datos para guardar")
        
        # Convertir a DataFrame
        df = pd.DataFrame(data)
        
        # Guardar en CSV
        df.to_csv(PLANILLA_FLUJO_PAGOS_CSV, index=False, encoding='utf-8-sig')
        
        # Guardar en Excel también
        df.to_excel(PLANILLA_FLUJO_PAGOS_XLSX, index=False, engine='openpyxl')
        
        print(f"✅ Datos guardados exitosamente: {len(data)} registros")
        
        return {
            "success": True,
            "message": f"Datos guardados exitosamente: {len(data)} registros"
        }
        
    except Exception as e:
        print(f"❌ Error al guardar plantilla preliminar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al guardar datos: {str(e)}")

def apply_filters_to_dataframe(df, filters):
    """Apply the same filtering logic used in frontend to the dataframe"""
    filtered_df = df.copy()
    
    print(f"🔍 Columnas disponibles: {list(df.columns)}")
    
    # Apply search filter
    if filters.get('searchTerm'):
        search_term = filters['searchTerm'].lower()
        search_mask = df.astype(str).apply(lambda x: x.str.lower().str.contains(search_term, na=False)).any(axis=1)
        filtered_df = filtered_df[search_mask]
        print(f"📊 Después de filtro de búsqueda '{search_term}': {len(filtered_df)} registros")
    
    # Apply VB filter
    if filters.get('vbFilter') and 'VB' in filtered_df.columns:
        vb_filter_value = filters['vbFilter']
        # Handle multiple VB values (comma separated from frontend)
        if ',' in vb_filter_value:
            vb_values = [v.strip() for v in vb_filter_value.split(',') if v.strip()]
            if vb_values and '' not in vb_values:  # Don't filter if "Todos los VB" is selected
                filtered_df = filtered_df[filtered_df['VB'].isin(vb_values)]
                print(f"📊 Después de filtro VB múltiple {vb_values}: {len(filtered_df)} registros")
        else:
            # Single value filter (backward compatibility)
            if vb_filter_value:
                filtered_df = filtered_df[filtered_df['VB'] == vb_filter_value]
                print(f"📊 Después de filtro VB '{vb_filter_value}': {len(filtered_df)} registros")
    
    # Apply Estado de Pago filter
    if filters.get('estadoPagoFilter') and 'Estado de Pago' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Estado de Pago'] == filters['estadoPagoFilter']]
        print(f"📊 Después de filtro Estado de Pago '{filters['estadoPagoFilter']}': {len(filtered_df)} registros")
    
    # Apply A pagar filter - handle frontend true/false values
    if filters.get('aPagarFilter') and 'A pagar' in filtered_df.columns:
        if filters['aPagarFilter'] == 'true':
            filtered_df = filtered_df[filtered_df['A pagar'] == 'Sí']
        elif filters['aPagarFilter'] == 'false':
            filtered_df = filtered_df[filtered_df['A pagar'] == 'No']
        print(f"📊 Después de filtro A pagar '{filters['aPagarFilter']}': {len(filtered_df)} registros")
    
    # Apply Cesión filter - handle frontend Si/No to backend Sí/No
    if filters.get('cesionFilter') and 'Cesión' in filtered_df.columns:
        if filters['cesionFilter'] == 'Sí':
            filtered_df = filtered_df[filtered_df['Cesión'] == 'Sí']
        elif filters['cesionFilter'] == 'No':
            filtered_df = filtered_df[filtered_df['Cesión'] == 'No']
        print(f"📊 Después de filtro Cesión '{filters['cesionFilter']}': {len(filtered_df)} registros")
    
    # Apply date filters - map frontend date type to actual column name
    if filters.get('fechaDesde') or filters.get('fechaHasta'):
        tipo_fecha = filters.get('tipoFecha', 'Fecha Venc. Factura')
        
        # Map frontend date type to actual column name
        date_column_mapping = {
            'Fecha Venc. Factura': 'Fecha de Pago',
            'Fecha Emisión': 'Fecha Emisión',
            'Fecha de Pago': 'Fecha de Pago'
        }
        
        actual_date_column = date_column_mapping.get(tipo_fecha, tipo_fecha)
        print(f"🗓️ Filtro de fecha usando columna: {actual_date_column}")
        
        if actual_date_column in filtered_df.columns:
            try:
                # Convert date column to datetime
                filtered_df[actual_date_column] = pd.to_datetime(filtered_df[actual_date_column], errors='coerce')
                
                if filters.get('fechaDesde'):
                    fecha_desde = pd.to_datetime(filters['fechaDesde'])
                    filtered_df = filtered_df[filtered_df[actual_date_column] >= fecha_desde]
                    print(f"📊 Después de filtro fecha desde '{filters['fechaDesde']}': {len(filtered_df)} registros")
                
                if filters.get('fechaHasta'):
                    fecha_hasta = pd.to_datetime(filters['fechaHasta'])
                    filtered_df = filtered_df[filtered_df[actual_date_column] <= fecha_hasta]
                    print(f"📊 Después de filtro fecha hasta '{filters['fechaHasta']}': {len(filtered_df)} registros")
            except Exception as e:
                print(f"⚠️ Error en filtro de fechas: {e}")
    
    return filtered_df

@app.get("/api/pagos/plantilla-preliminar/download")
async def download_plantilla_preliminar(
    request: Request,
    searchTerm: str = "",
    vbFilter: str = "",
    estadoPagoFilter: str = "",
    aPagarFilter: str = "",
    cesionFilter: str = "",
    fechaDesde: str = "",
    fechaHasta: str = "",
    tipoFecha: str = "Fecha Venc. Factura"
):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Load data from CSV or Excel - check both configured and current directory
        df = None
        
        # Try configured paths first
        if os.path.exists(PLANILLA_FLUJO_PAGOS_CSV):
            df = pd.read_csv(PLANILLA_FLUJO_PAGOS_CSV, encoding='utf-8-sig')
            print(f"✅ Cargando datos desde: {PLANILLA_FLUJO_PAGOS_CSV}")
        elif os.path.exists(PLANILLA_FLUJO_PAGOS_XLSX):
            df = pd.read_excel(PLANILLA_FLUJO_PAGOS_XLSX, engine='openpyxl')
            print(f"✅ Cargando datos desde: {PLANILLA_FLUJO_PAGOS_XLSX}")
        else:
            # Try current directory as fallback
            current_dir_csv = "planilla_flujo_pagos.csv"
            current_dir_xlsx = "planilla_flujo_pagos.xlsx"
            if os.path.exists(current_dir_csv):
                df = pd.read_csv(current_dir_csv, encoding='utf-8-sig')
                print(f"✅ Cargando datos desde directorio actual: {current_dir_csv}")
            elif os.path.exists(current_dir_xlsx):
                df = pd.read_excel(current_dir_xlsx, engine='openpyxl')
                print(f"✅ Cargando datos desde directorio actual: {current_dir_xlsx}")
            else:
                print(f"❌ No se encontraron archivos en:")
                print(f"  - {PLANILLA_FLUJO_PAGOS_CSV}")
                print(f"  - {PLANILLA_FLUJO_PAGOS_XLSX}")
                print(f"  - {current_dir_csv}")
                print(f"  - {current_dir_xlsx}")
                raise HTTPException(status_code=404, detail="No hay datos disponibles para descargar")
        
        original_count = len(df)
        print(f"📊 Registros originales: {original_count}")
        
        # Apply filters
        filters = {
            'searchTerm': searchTerm,
            'vbFilter': vbFilter,
            'estadoPagoFilter': estadoPagoFilter,
            'aPagarFilter': aPagarFilter,
            'cesionFilter': cesionFilter,
            'fechaDesde': fechaDesde,
            'fechaHasta': fechaHasta,
            'tipoFecha': tipoFecha
        }
        
        # Filter out empty values
        filters = {k: v for k, v in filters.items() if v}
        
        if filters:
            print(f"🔍 Aplicando filtros: {filters}")
            df = apply_filters_to_dataframe(df, filters)
            filtered_count = len(df)
            print(f"📊 Registros después de filtrar: {filtered_count}")
        else:
            print("⚠️ No se aplicaron filtros, descargando todos los registros")
        
        # Create Excel file in memory
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)
        
        # Determine filename based on whether filters are applied
        filename = "plantilla_preliminar_filtrada.xlsx" if filters else "plantilla_preliminar.xlsx"
        
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        
        return StreamingResponse(
            io.BytesIO(excel_buffer.read()),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers=headers
        )
        
    except Exception as e:
        print(f"❌ Error al descargar plantilla preliminar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar descarga: {str(e)}")

# Email models
class EmailRequest(BaseModel):
    recipients: List[str]
    subject: str
    content: str
    filterParams: dict

@app.post("/api/pagos/plantilla-preliminar/email")
async def send_plantilla_preliminar_email(email_request: EmailRequest, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Load and filter data using same logic as download function
        df = None
        
        # Try configured paths first
        if os.path.exists(PLANILLA_FLUJO_PAGOS_CSV):
            df = pd.read_csv(PLANILLA_FLUJO_PAGOS_CSV, encoding='utf-8-sig')
            print(f"✅ Cargando datos desde: {PLANILLA_FLUJO_PAGOS_CSV}")
        elif os.path.exists(PLANILLA_FLUJO_PAGOS_XLSX):
            df = pd.read_excel(PLANILLA_FLUJO_PAGOS_XLSX, engine='openpyxl')
            print(f"✅ Cargando datos desde: {PLANILLA_FLUJO_PAGOS_XLSX}")
        else:
            # Try current directory as fallback
            current_dir_csv = "planilla_flujo_pagos.csv"
            current_dir_xlsx = "planilla_flujo_pagos.xlsx"
            if os.path.exists(current_dir_csv):
                df = pd.read_csv(current_dir_csv, encoding='utf-8-sig')
                print(f"✅ Cargando datos desde directorio actual: {current_dir_csv}")
            elif os.path.exists(current_dir_xlsx):
                df = pd.read_excel(current_dir_xlsx, engine='openpyxl')
                print(f"✅ Cargando datos desde directorio actual: {current_dir_xlsx}")
            else:
                raise HTTPException(status_code=404, detail="No hay datos disponibles para enviar")
        
        # Apply filters
        filter_params = email_request.filterParams
        filters = {k: v for k, v in filter_params.items() if v}
        
        if filters:
            print(f"🔍 Aplicando filtros para email: {filters}")
            df = apply_filters_to_dataframe(df, filters)
        
        # Create temporary Excel file
        temp_filename = f"plantilla_preliminar_filtrada_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        temp_path = os.path.join("/tmp", temp_filename)
        
        # Ensure temp directory exists
        os.makedirs("/tmp", exist_ok=True)
        df.to_excel(temp_path, index=False, engine='openpyxl')
        
        # Format table data for email content
        def format_table_for_email(df, max_rows=20):
            # Select key columns for the email summary
            key_columns = []
            available_columns = df.columns.tolist()
            
            # Priority columns to include in email
            priority_cols = ['Número de Factura', 'Fecha de Emisión', 'Fecha de Pago', 'Rut', 'Razón Social', 'VB', 'Centro de Gestión', 'Monto Total']
            
            # Add priority columns if they exist
            for col in priority_cols:
                if col in available_columns:
                    key_columns.append(col)
            
            # If we don't have enough key columns, add others
            if len(key_columns) < 6:
                for col in available_columns:
                    if col not in key_columns and len(key_columns) < 6:
                        key_columns.append(col)
            
            # Create summary dataframe
            summary_df = df[key_columns].head(max_rows)
            
            # Format numeric columns
            for col in summary_df.columns:
                if col in ['Monto', 'Monto Total', 'Neto', 'IVA', 'Monto Pago', 'Pagado', 'Saldo']:
                    try:
                        summary_df[col] = summary_df[col].apply(lambda x: f"${int(float(x)):,}" if pd.notnull(x) and str(x).replace('.','').replace(',','').replace('-','').isdigit() else str(x))
                    except:
                        pass
            
            # Convert to HTML with styling
            table_html = summary_df.to_html(
                index=False, 
                classes="email-table",
                table_id="data-table",
                escape=False,
                border=1
            )
            
            # Add inline CSS styling
            styled_html = f"""
            <div style="overflow-x: auto;">
                <style>
                    .email-table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin: 20px 0;
                        font-family: Arial, sans-serif;
                        font-size: 12px;
                    }}
                    .email-table th {{
                        background-color: #4472C4;
                        color: white;
                        padding: 8px;
                        text-align: left;
                        border: 1px solid #ddd;
                    }}
                    .email-table td {{
                        padding: 6px 8px;
                        border: 1px solid #ddd;
                        text-align: left;
                    }}
                    .email-table tr:nth-child(even) {{
                        background-color: #f2f2f2;
                    }}
                    .email-table tr:hover {{
                        background-color: #e8f4fd;
                    }}
                </style>
                {table_html}
            </div>
            """
            
            return styled_html
        
        # Format table for email
        table_html = format_table_for_email(df, 20)
        
        # Replace {TABLA_DATOS} placeholder with formatted table
        email_content = email_request.content.replace("{TABLA_DATOS}", table_html)
        
        # Add summary information
        if len(df) > 20:
            email_content += f"\n\n(Tabla muestra los primeros 20 registros de {len(df)} total. Ver archivo Excel adjunto para todos los datos.)"
        else:
            email_content += f"\n\n(Mostrando {len(df)} registros total.)"
        
        # Send email with Excel attachment
        email_sender.enviar_excel_gmail(
            archivo_xlsx=temp_path,
            para=email_request.recipients,
            asunto=email_request.subject,
            cuerpo=email_content
        )
        
        # Clean up temporary file
        try:
            os.remove(temp_path)
        except:
            pass
        
        print(f"📧 Email enviado exitosamente a: {', '.join(email_request.recipients)}")
        return {"success": True, "message": "Email enviado exitosamente"}
        
    except Exception as e:
        print(f"❌ Error al enviar email: {str(e)}")
        # Clean up temporary file if it exists
        try:
            if 'temp_path' in locals():
                os.remove(temp_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Error al enviar email: {str(e)}")

@app.get("/api/pagos/cesiones")
async def get_cesiones(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Verificar si existe el archivo
        if not os.path.exists(CESIONES_NO_CRUZADAS_CSV):
            return {"success": False, "message": "No hay cesiones no cruzadas disponibles. Execute el flujo de pagos primero."}
        
        # Cargar datos desde CSV
        df = pd.read_csv(CESIONES_NO_CRUZADAS_CSV, encoding='utf-8-sig')
        
        if df.empty:
            return {"success": False, "message": "No hay cesiones no cruzadas."}
        
        # Preparar estadísticas
        total_cesiones = len(df)
        cesionarios_unicos = df['cesionario_nombre'].nunique() if 'cesionario_nombre' in df.columns else 0
        
        estadisticas = {
            'total_cesiones': total_cesiones,
            'cesionarios_unicos': cesionarios_unicos
        }
        
        # Limpiar datos para JSON
        df_clean = df.replace([np.nan, np.inf, -np.inf], None)
        
        # Convertir fechas a strings si las hay
        for col in df_clean.columns:
            if df_clean[col].dtype == 'datetime64[ns]':
                df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d')
        
        data = df_clean.to_dict('records')
        data = [clean_for_json(record) for record in data]
        
        return {
            "success": True,
            "data": data,
            "estadisticas": estadisticas
        }
        
    except Exception as e:
        print(f"❌ Error al cargar cesiones: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al cargar datos: {str(e)}")

@app.delete("/api/pagos/cesiones/all")
async def eliminar_todas_cesiones_endpoint(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Verificar si existe el archivo
        if not os.path.exists(CESIONES_NO_CRUZADAS_CSV):
            raise HTTPException(status_code=404, detail="No hay cesiones no cruzadas disponibles.")
        
        # Eliminar el archivo CSV
        os.remove(CESIONES_NO_CRUZADAS_CSV)
        
        # También eliminar el archivo Excel si existe
        if os.path.exists(CESIONES_NO_CRUZADAS_XLSX):
            os.remove(CESIONES_NO_CRUZADAS_XLSX)
        
        print(f"✅ Todas las cesiones eliminadas exitosamente")
        
        return {
            "success": True,
            "message": "Todas las cesiones han sido eliminadas exitosamente"
        }
        
    except Exception as e:
        print(f"❌ Error al eliminar todas las cesiones: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar todas las cesiones: {str(e)}")

@app.delete("/api/pagos/cesiones/{index}")
async def eliminar_cesion(request: Request, index: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Verificar si existe el archivo
        if not os.path.exists(CESIONES_NO_CRUZADAS_CSV):
            raise HTTPException(status_code=404, detail="No hay cesiones no cruzadas disponibles.")
        
        # Cargar datos desde CSV
        df = pd.read_csv(CESIONES_NO_CRUZADAS_CSV, encoding='utf-8-sig')
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No hay cesiones no cruzadas.")
        
        # Verificar que el índice sea válido
        if index < 0 or index >= len(df):
            raise HTTPException(status_code=400, detail="Índice de cesión inválido.")
        
        # Eliminar la fila
        df_new = df.drop(index).reset_index(drop=True)
        
        # Guardar el archivo actualizado
        df_new.to_csv(CESIONES_NO_CRUZADAS_CSV, index=False, encoding='utf-8-sig')
        
        # También actualizar el archivo Excel si existe
        if os.path.exists(CESIONES_NO_CRUZADAS_XLSX):
            df_new.to_excel(CESIONES_NO_CRUZADAS_XLSX, index=False)
        
        print(f"✅ Cesión eliminada exitosamente. Registros restantes: {len(df_new)}")
        
        return {
            "success": True,
            "message": "Cesión eliminada exitosamente",
            "total_restantes": len(df_new)
        }
        
    except Exception as e:
        print(f"❌ Error al eliminar cesión: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar cesión: {str(e)}")

@app.get("/api/pagos/planilla-pagos/status")
async def get_planilla_status(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        pagos_mostrar_path = os.path.join(PERSISTENT_DIR, "pagos_mostrar.xlsx")
        
        if os.path.exists(pagos_mostrar_path):
            # Cargar los datos existentes
            df = pd.read_excel(pagos_mostrar_path)
            
            if not df.empty:
                # Limpiar datos para JSON serialization
                df_clean = df.replace([np.nan, np.inf, -np.inf], None)
                
                # Calcular estadísticas
                total_registros = len(df_clean)
                monto_col = None
                
                # Buscar columna de monto
                for col in df_clean.columns:
                    col_lower = col.lower()
                    if any(keyword in col_lower for keyword in ['monto', 'valor', 'importe', 'amount']):
                        monto_col = col
                        break
                
                total_monto = 0
                if monto_col:
                    total_monto = df_clean[monto_col].fillna(0).sum()
                
                # Calcular registros sin cuenta
                cuenta_col = None
                for col in df_clean.columns:
                    col_lower = col.lower()
                    if 'cuenta' in col_lower and ('corriente' in col_lower or 'bancaria' in col_lower):
                        cuenta_col = col
                        break
                
                sin_cuenta_corriente = 0
                if cuenta_col:
                    sin_cuenta_corriente = df_clean[cuenta_col].isna().sum() + (df_clean[cuenta_col].astype(str).str.strip() == '').sum()
                
                # Marcar registros sin cuenta
                if cuenta_col:
                    df_clean['_sin_cuenta'] = df_clean[cuenta_col].isna() | (df_clean[cuenta_col].astype(str).str.strip() == '')
                
                return {
                    "exists": True,
                    "success": True,
                    "message": f"Planilla cargada: {total_registros} registros",
                    "data": df_clean.to_dict('records'),
                    "estadisticas": {
                        "total_registros": total_registros,
                        "total_monto": float(total_monto) if pd.notna(total_monto) else 0,
                        "sin_cuenta_corriente": int(sin_cuenta_corriente)
                    }
                }
        
        return {"exists": False}
        
    except Exception as e:
        print(f"❌ Error al verificar estado de planilla: {str(e)}")
        return {"exists": False, "error": str(e)}

@app.post("/api/pagos/planilla-pagos")
async def crear_planilla_pagos_api(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        print("📝 Iniciando creación de planilla de pagos...")
        
        # Verificar que exista la plantilla preliminar
        if not os.path.exists(PLANILLA_FLUJO_PAGOS_CSV):
            raise HTTPException(status_code=400, detail="No hay plantilla preliminar disponible. Execute el flujo de pagos primero.")
        
        # Cargar la planilla preliminar (resultados)
        print(f"📁 Cargando plantilla preliminar desde: {PLANILLA_FLUJO_PAGOS_CSV}")
        resultados = pd.read_csv(PLANILLA_FLUJO_PAGOS_CSV, encoding='utf-8-sig')
        
        if resultados.empty:
            raise HTTPException(status_code=400, detail="La plantilla preliminar está vacía.")
        
        print(f"📊 Plantilla preliminar cargada: {len(resultados)} registros")
        
        # Cargar las cuentas bancarias (santander)
        print(f"📁 Cargando cuentas bancarias desde: {SANTANDER_XLSX}")
        if not os.path.exists(SANTANDER_XLSX):
            raise HTTPException(status_code=400, detail="No hay archivo de cuentas bancarias disponible.")
        
        santander = pd.read_excel(SANTANDER_XLSX)
        print(f"📊 Cuentas bancarias cargadas: {len(santander)} registros")
        
        # Importar y ejecutar la función planilla_pago_mostrar
        from pagos import planilla_pago_mostrar
        print("✅ Función planilla_pago_mostrar importada")
        
        # Ejecutar la función
        print("⚙️ Ejecutando planilla_pago_mostrar...")
        planilla_pagos = planilla_pago_mostrar(resultados, santander)
        print("✅ Función planilla_pago_mostrar ejecutada correctamente")
        
        # Verificar que los resultados no sean None
        if planilla_pagos is None:
            planilla_pagos = pd.DataFrame()
        
        print(f"📊 Planilla de pagos generada - Shape: {getattr(planilla_pagos, 'shape', 'N/A')}")
        
        # Preparar estadísticas
        try:
            total_registros = len(planilla_pagos) if not planilla_pagos.empty else 0
            
            # Buscar columnas de monto (puede tener diferentes nombres)
            monto_col = None
            for col in planilla_pagos.columns:
                if 'monto' in col.lower() and ('transfer' in col.lower() or 'pago' in col.lower()):
                    monto_col = col
                    break
            
            total_monto = 0
            if not planilla_pagos.empty and monto_col:
                total_monto = planilla_pagos[monto_col].fillna(0).sum()
            
            # Contar registros sin cuenta corriente
            # Buscar la columna correcta (puede tener diferentes formatos)
            cuenta_col = None
            posibles_columnas = [
                'Cuenta destino (obligatorio)',
                'Cuenta destino\n(obligatorio)', 
                'Número de cuenta destino\n(obligatorio)',
                'Cuenta destino'
            ]
            
            for col in posibles_columnas:
                if col in planilla_pagos.columns:
                    cuenta_col = col
                    break
            
            sin_cuenta = 0
            if cuenta_col:
                sin_cuenta = planilla_pagos[cuenta_col].isna().sum() + (planilla_pagos[cuenta_col].astype(str).str.strip() == '').sum()
            
            estadisticas = {
                'total_registros': total_registros,
                'total_monto': int(total_monto) if not pd.isna(total_monto) else 0,
                'sin_cuenta_corriente': int(sin_cuenta)
            }
            print(f"📈 Estadísticas calculadas: {estadisticas}")
        except Exception as e:
            print(f"❌ Error calculando estadísticas: {str(e)}")
            estadisticas = {'total_registros': 0, 'total_monto': 0, 'sin_cuenta_corriente': 0}
        
        print(f"✅ Planilla de pagos completada: {estadisticas['total_registros']} registros")
        
        # Preparar datos para JSON
        data = []
        try:
            if not planilla_pagos.empty:
                # Limpiar valores NaN, inf y -inf para JSON serialización
                planilla_clean = planilla_pagos.replace([np.nan, np.inf, -np.inf], None)
                
                # Agregar campo para identificar registros sin cuenta corriente
                # Buscar la columna correcta (puede tener diferentes formatos)
                cuenta_col = None
                posibles_columnas = [
                    'Cuenta destino (obligatorio)',
                    'Cuenta destino\n(obligatorio)', 
                    'Número de cuenta destino\n(obligatorio)',
                    'Cuenta destino'
                ]
                
                for col in posibles_columnas:
                    if col in planilla_clean.columns:
                        cuenta_col = col
                        break
                
                if cuenta_col:
                    planilla_clean['_sin_cuenta'] = (
                        planilla_clean[cuenta_col].isna() | 
                        (planilla_clean[cuenta_col].astype(str).str.strip() == '')
                    )
                else:
                    planilla_clean['_sin_cuenta'] = True
                
                for col in planilla_clean.columns:
                    if planilla_clean[col].dtype == 'datetime64[ns]':
                        planilla_clean[col] = planilla_clean[col].dt.strftime('%Y-%m-%d')
                    elif planilla_clean[col].dtype in ['float64', 'float32']:
                        planilla_clean[col] = planilla_clean[col].apply(
                            lambda x: None if pd.isna(x) or np.isinf(x) else float(x)
                        )
                
                data = planilla_clean.to_dict('records')
                data = [clean_for_json(record) for record in data]
                
                print(f"📄 Data preparada: {len(data)} registros")
                    
        except Exception as e:
            print(f"❌ Error preparando data: {str(e)}")
            import traceback
            traceback.print_exc()
            data = []
        
        # Limpiar estadísticas también
        estadisticas = clean_for_json(estadisticas)
        
        response_data = {
            "success": True, 
            "message": f"Planilla de pagos creada exitosamente con {estadisticas['total_registros']} registros",
            "data": data,
            "estadisticas": estadisticas
        }
        
        return clean_for_json(response_data)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"❌ Error general al crear planilla de pagos: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al crear planilla de pagos: {str(e)}")

@app.get("/api/pagos/planilla-pagos/download-mostrar")
async def download_planilla_mostrar(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Verificar si existe el archivo pagos_mostrar.xlsx
        pagos_mostrar_path = os.path.join(PERSISTENT_DIR, "pagos_mostrar.xlsx")
        
        if not os.path.exists(pagos_mostrar_path):
            raise HTTPException(status_code=404, detail="No hay planilla disponible para descargar. Genere la planilla primero.")
        
        # Crear response para descarga
        def iterfile():
            with open(pagos_mostrar_path, 'rb') as file:
                yield from file
        
        headers = {
            'Content-Disposition': 'attachment; filename="pagos_mostrar.xlsx"'
        }
        
        return StreamingResponse(
            iterfile(),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers=headers
        )
        
    except Exception as e:
        print(f"❌ Error al descargar planilla mostrar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar descarga: {str(e)}")

@app.get("/api/pagos/planilla-pagos/download-santander")
async def download_planilla_santander(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        print("📝 Generando planilla Santander actualizada...")
        
        # Verificar que exista la plantilla preliminar
        if not os.path.exists(PLANILLA_FLUJO_PAGOS_CSV):
            raise HTTPException(status_code=400, detail="No hay plantilla preliminar disponible. Execute el flujo de pagos primero.")
        
        # Cargar la planilla preliminar (resultados)
        print(f"📁 Cargando plantilla preliminar desde: {PLANILLA_FLUJO_PAGOS_CSV}")
        resultados = pd.read_csv(PLANILLA_FLUJO_PAGOS_CSV, encoding='utf-8-sig')
        
        if resultados.empty:
            raise HTTPException(status_code=400, detail="La plantilla preliminar está vacía.")
        
        print(f"📊 Plantilla preliminar cargada: {len(resultados)} registros")
        
        # Cargar las cuentas bancarias (santander)
        print(f"📁 Cargando cuentas bancarias desde: {SANTANDER_XLSX}")
        if not os.path.exists(SANTANDER_XLSX):
            raise HTTPException(status_code=400, detail="No hay archivo de cuentas bancarias disponible.")
        
        santander = pd.read_excel(SANTANDER_XLSX)
        print(f"📊 Cuentas bancarias cargadas: {len(santander)} registros")
        
        # Importar y ejecutar la función planilla_pago_mostrar
        from pagos import planilla_pago_mostrar
        print("✅ Función planilla_pago_mostrar importada")
        
        # Ejecutar la función para generar planilla Santander
        print("⚙️ Ejecutando planilla_pago_mostrar...")
        planilla_pagos = planilla_pago_mostrar(resultados, santander)
        print("✅ Función planilla_pago_mostrar ejecutada correctamente")
        
        # Verificar que los resultados no sean None
        if planilla_pagos is None or planilla_pagos.empty:
            raise HTTPException(status_code=400, detail="No se generaron registros para la planilla de pagos.")
        
        print(f"📊 Planilla de pagos generada: {len(planilla_pagos)} registros")
        
        # Contar registros sin cuenta corriente antes de eliminar columnas
        # Buscar la columna correcta (puede tener diferentes formatos)
        cuenta_col = None
        posibles_columnas = [
            'Cuenta destino (obligatorio)',
            'Cuenta destino\n(obligatorio)', 
            'Número de cuenta destino\n(obligatorio)',
            'Cuenta destino'
        ]
        
        for col in posibles_columnas:
            if col in planilla_pagos.columns:
                cuenta_col = col
                break
        
        sin_cuenta_corriente = 0
        if cuenta_col:
            sin_cuenta_corriente = planilla_pagos[cuenta_col].isna().sum() + (planilla_pagos[cuenta_col].astype(str).str.strip() == '').sum()
        
        # Eliminar las primeras dos columnas para la descarga
        if len(planilla_pagos.columns) > 2:
            planilla_santander = planilla_pagos.iloc[:, 2:]  # Excluir las primeras 2 columnas
            print(f"✂️ Eliminadas las primeras 2 columnas. Columnas restantes: {len(planilla_santander.columns)}")
        else:
            planilla_santander = planilla_pagos.copy()
        
        # Guardar la planilla Santander
        planilla_santander_path = os.path.join(PERSISTENT_DIR, "planilla_pagos_santander.xlsx")
        planilla_santander.to_excel(planilla_santander_path, index=False, engine='openpyxl')
        print(f"💾 Planilla Santander guardada en: {planilla_santander_path}")
        
        if sin_cuenta_corriente > 0:
            print(f"⚠️ ADVERTENCIA: {sin_cuenta_corriente} registros sin cuenta corriente")
        
        # Crear response para descarga
        def iterfile():
            with open(planilla_santander_path, 'rb') as file:
                yield from file
        
        headers = {
            'Content-Disposition': 'attachment; filename="planilla_pagos_santander.xlsx"'
        }
        
        return StreamingResponse(
            iterfile(),
            media_type='application/vnd.openxmlformats-oficedocument.spreadsheetml.sheet',
            headers=headers
        )
        
    except Exception as e:
        print(f"❌ Error al descargar planilla Santander: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar descarga: {str(e)}")

@app.post("/api/pagos/planilla-pagos/guardar")
async def guardar_planilla_editada(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Obtener datos del request
        body = await request.json()
        data = body.get('data', [])
        
        if not data:
            raise HTTPException(status_code=400, detail="No hay datos para guardar")
        
        # Convertir a DataFrame
        df = pd.DataFrame(data)
        
        # Guardar en pagos_mostrar.xlsx
        pagos_mostrar_path = os.path.join(PERSISTENT_DIR, "pagos_mostrar.xlsx")
        df.to_excel(pagos_mostrar_path, index=False)
        
        print(f"✅ Planilla editada guardada exitosamente: {len(data)} registros en {pagos_mostrar_path}")
        
        return {
            "success": True,
            "message": f"Planilla guardada exitosamente: {len(data)} registros"
        }
        
    except Exception as e:
        print(f"❌ Error al guardar planilla editada: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al guardar datos: {str(e)}")

# Módulo Cuentas Bancarias (submódulo de Pagos)
@app.get("/pagos/cuentas-bancarias", response_class=HTMLResponse)
async def cuentas_bancarias_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("cuentas_bancarias.html", {"request": request, "user": user})

@app.get("/api/pagos/cuentas-bancarias")
async def get_cuentas_bancarias(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        df = pd.read_excel(SANTANDER_XLSX)
        df = df.fillna('')
        return {
            "data": df.to_dict('records'),
            "columns": df.columns.tolist()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cargar Santander.xlsx: {str(e)}")

@app.post("/api/pagos/cuentas-bancarias/guardar")
async def guardar_cuentas_bancarias(request: Request, data: dict):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        if not data.get('data'):
            raise HTTPException(status_code=400, detail="No hay datos para guardar")
        
        df = pd.DataFrame(data['data'])
        
        if df.empty:
            raise HTTPException(status_code=400, detail="No se puede guardar un archivo vacío")
        
        df.to_excel(SANTANDER_XLSX, index=False)
        return {"success": True, "message": "Archivo Santander.xlsx guardado exitosamente"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar Santander.xlsx: {str(e)}")

@app.post("/api/pagos/cuentas-bancarias/subir")
async def subir_cuentas_bancarias(request: Request, santanderFile: UploadFile = File(...)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        # Verificar que sea un archivo Excel
        if not santanderFile.filename.lower().endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Solo se permiten archivos Excel (.xlsx, .xls)")
        
        # Leer el contenido del archivo
        content = await santanderFile.read()
        
        # Guardar el archivo en el directorio persistente
        with open(SANTANDER_XLSX, 'wb') as f:
            f.write(content)
        
        message = f"Archivo {santanderFile.filename} subido y guardado como Santander.xlsx"
        return {"success": True, "message": message}
        
    except Exception as e:
        print(f"❌ Error al procesar archivo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar archivo: {str(e)}")

@app.get("/obras", response_class=HTMLResponse)
async def obras(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Verificar que el usuario tenga acceso al módulo Obras
    if not (user['is_admin'] or user['is_manager'] or user['is_admin_obra']):
        raise HTTPException(status_code=403, detail="No tienes permisos para acceder a este módulo")

    return templates.TemplateResponse("obras.html", {"request": request, "user": user})

@app.get("/obras/crear", response_class=HTMLResponse)
async def crear_obra_form(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Solo Administrador y Gerente pueden crear obras
    if not (user['is_admin'] or user['is_manager']):
        raise HTTPException(status_code=403, detail="No tienes permisos para crear obras")

    # Obtener lista de usuarios con rol Admin Obra
    conn = get_db_connection()
    admin_obra_users = conn.execute('''
        SELECT id, name, email FROM users
        WHERE is_admin_obra = 1
        ORDER BY name
    ''').fetchall()
    conn.close()

    return templates.TemplateResponse("crear_obra.html", {
        "request": request,
        "user": user,
        "admin_obra_users": admin_obra_users
    })

@app.post("/obras/crear")
async def crear_obra(request: Request,
                    nombre_obra: str = Form(...),
                    centro_costo: str = Form(...),
                    administrador_obra_id: int = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Solo Administrador y Gerente pueden crear obras
    if not (user['is_admin'] or user['is_manager']):
        raise HTTPException(status_code=403, detail="No tienes permisos para crear obras")

    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO obras (nombre_obra, centro_costo, administrador_obra_id)
            VALUES (?, ?, ?)
        ''', (nombre_obra, centro_costo, administrador_obra_id))
        conn.commit()
        conn.close()

        return {"success": True, "message": "Obra creada exitosamente"}
    except Exception as e:
        print(f"❌ Error al crear obra: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al crear obra: {str(e)}")

@app.get("/obras/lista")
async def listar_obras(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Verificar que el usuario tenga acceso al módulo Obras
    if not (user['is_admin'] or user['is_manager'] or user['is_admin_obra']):
        raise HTTPException(status_code=403, detail="No tienes permisos para acceder a este módulo")

    conn = get_db_connection()

    # Si es Admin o Gerente, ver todas las obras
    if user['is_admin'] or user['is_manager']:
        obras = conn.execute('''
            SELECT o.id, o.nombre_obra, o.centro_costo, o.created_at, u.name as administrador_nombre
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            ORDER BY o.created_at DESC
        ''').fetchall()
    # Si es Admin Obra, solo ver sus obras asignadas
    elif user['is_admin_obra']:
        obras = conn.execute('''
            SELECT o.id, o.nombre_obra, o.centro_costo, o.created_at, u.name as administrador_nombre
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            WHERE o.administrador_obra_id = ?
            ORDER BY o.created_at DESC
        ''', (user['id'],)).fetchall()
    else:
        obras = []

    conn.close()

    return {"obras": [dict(obra) for obra in obras]}

@app.get("/obras/{obra_id}", response_class=HTMLResponse)
async def obra_detalle(request: Request, obra_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Verificar que el usuario tenga acceso al módulo Obras
    if not (user['is_admin'] or user['is_manager'] or user['is_admin_obra']):
        raise HTTPException(status_code=403, detail="No tienes permisos para acceder a este módulo")

    conn = get_db_connection()

    # Verificar permisos: Admin/Gerente ven todas, Admin Obra solo la suya
    if user['is_admin'] or user['is_manager']:
        obra = conn.execute('''
            SELECT o.*, u.name as administrador_nombre, u.email as administrador_email
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            WHERE o.id = ?
        ''', (obra_id,)).fetchone()
    elif user['is_admin_obra']:
        obra = conn.execute('''
            SELECT o.*, u.name as administrador_nombre, u.email as administrador_email
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            WHERE o.id = ? AND o.administrador_obra_id = ?
        ''', (obra_id, user['id'])).fetchone()
    else:
        obra = None

    conn.close()

    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada o sin permisos")

    return templates.TemplateResponse("obra_detalle.html", {
        "request": request,
        "user": user,
        "obra": dict(obra)
    })

@app.get("/obras/{obra_id}/dashboard", response_class=HTMLResponse)
async def obra_dashboard(request: Request, obra_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Verificar permisos y obtener obra
    conn = get_db_connection()

    if user['is_admin'] or user['is_manager']:
        obra = conn.execute('''
            SELECT o.*, u.name as administrador_nombre
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            WHERE o.id = ?
        ''', (obra_id,)).fetchone()
    elif user['is_admin_obra']:
        obra = conn.execute('''
            SELECT o.*, u.name as administrador_nombre
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            WHERE o.id = ? AND o.administrador_obra_id = ?
        ''', (obra_id, user['id'])).fetchone()
    else:
        obra = None

    conn.close()

    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada o sin permisos")

    return templates.TemplateResponse("obra_dashboard.html", {
        "request": request,
        "user": user,
        "obra": dict(obra)
    })

@app.get("/obras/{obra_id}/facturas", response_class=HTMLResponse)
async def obra_facturas(request: Request, obra_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Verificar permisos y obtener obra
    conn = get_db_connection()

    if user['is_admin'] or user['is_manager']:
        obra = conn.execute('''
            SELECT o.*, u.name as administrador_nombre
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            WHERE o.id = ?
        ''', (obra_id,)).fetchone()
    elif user['is_admin_obra']:
        obra = conn.execute('''
            SELECT o.*, u.name as administrador_nombre
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            WHERE o.id = ? AND o.administrador_obra_id = ?
        ''', (obra_id, user['id'])).fetchone()
    else:
        obra = None

    conn.close()

    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada o sin permisos")

    return templates.TemplateResponse("obra_facturas.html", {
        "request": request,
        "user": user,
        "obra": dict(obra)
    })

@app.get("/obras/{obra_id}/reportes", response_class=HTMLResponse)
async def obra_reportes(request: Request, obra_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Verificar permisos y obtener obra
    conn = get_db_connection()

    if user['is_admin'] or user['is_manager']:
        obra = conn.execute('''
            SELECT o.*, u.name as administrador_nombre
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            WHERE o.id = ?
        ''', (obra_id,)).fetchone()
    elif user['is_admin_obra']:
        obra = conn.execute('''
            SELECT o.*, u.name as administrador_nombre
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            WHERE o.id = ? AND o.administrador_obra_id = ?
        ''', (obra_id, user['id'])).fetchone()
    else:
        obra = None

    conn.close()

    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada o sin permisos")

    return templates.TemplateResponse("obra_reportes.html", {
        "request": request,
        "user": user,
        "obra": dict(obra)
    })


# FLUJO DE CAJAS ROUTES

def get_weeks_between_dates(start_date, end_date):
    """Generate list of Monday dates between start and end date"""
    from datetime import datetime, timedelta

    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()

    # Find the Monday of the week containing start_date
    days_since_monday = start.weekday()
    first_monday = start - timedelta(days=days_since_monday)

    weeks = []
    current = first_monday
    while current <= end:
        weeks.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=7)

    return weeks

@app.get("/obras/{obra_id}/flujo-cajas", response_class=HTMLResponse)
async def obra_flujo_cajas(request: Request, obra_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db_connection()

    # Verificar permisos y obtener obra
    if user['is_admin'] or user['is_manager']:
        obra = conn.execute('''
            SELECT o.*, u.name as administrador_nombre
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            WHERE o.id = ?
        ''', (obra_id,)).fetchone()
    elif user['is_admin_obra']:
        obra = conn.execute('''
            SELECT o.*, u.name as administrador_nombre
            FROM obras o
            JOIN users u ON o.administrador_obra_id = u.id
            WHERE o.id = ? AND o.administrador_obra_id = ?
        ''', (obra_id, user['id'])).fetchone()
    else:
        conn.close()
        raise HTTPException(status_code=403, detail="Sin permisos para acceder")

    if not obra:
        conn.close()
        raise HTTPException(status_code=404, detail="Obra no encontrada o sin permisos")

    # Get or create flujo config
    config = conn.execute('''
        SELECT * FROM obra_flujo_config WHERE obra_id = ?
    ''', (obra_id,)).fetchone()

    if not config:
        # Create default config: start date = obra creation, end date = start + 6 months
        obra_start = obra['created_at'][:10]  # Get date part only
        start_date = datetime.strptime(obra_start, '%Y-%m-%d')
        end_date = start_date + timedelta(days=180)  # 6 months

        conn.execute('''
            INSERT INTO obra_flujo_config (obra_id, fecha_inicio, fecha_fin)
            VALUES (?, ?, ?)
        ''', (obra_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        conn.commit()

        config = {
            'fecha_inicio': start_date.strftime('%Y-%m-%d'),
            'fecha_fin': end_date.strftime('%Y-%m-%d')
        }

    # Generate weekly dates
    semanas = get_weeks_between_dates(config['fecha_inicio'], config['fecha_fin'])

    # Get flujo items with familia (tipo) from items table
    items = conn.execute('''
        SELECT fc.*, i.tipo as familia
        FROM flujo_cajas_items fc
        LEFT JOIN items i ON fc.codigo = i.codigo
        WHERE fc.obra_id = ?
        ORDER BY fc.codigo
    ''', (obra_id,)).fetchall()

    # Get weekly data for each item
    items_with_flujo = []
    for item in items:
        flujo_data = conn.execute('''
            SELECT semana, valor FROM flujo_cajas_semanal WHERE item_id = ?
        ''', (item['id'],)).fetchall()

        flujo_dict = {row['semana']: row['valor'] for row in flujo_data}

        item_dict = dict(item)
        item_dict['flujo_semanal'] = flujo_dict
        items_with_flujo.append(item_dict)

    # Calcular resumen por familia
    familias_resumen = {}

    # Inicializar familia "INGRESOS" aunque no tenga items
    familias_resumen["INGRESOS"] = {
        "familia": "INGRESOS",
        "presupuesto_inicial": 0,
        "modificaciones": 0,
        "gasto_real": 0,
        "flujo_semanal": {semana: 0 for semana in semanas}
    }

    # Agregar datos de cada item agrupado por familia
    for item in items_with_flujo:
        familia = item.get('familia', 'Sin Familia')
        if not familia:
            familia = 'Sin Familia'

        if familia not in familias_resumen:
            familias_resumen[familia] = {
                "familia": familia,
                "presupuesto_inicial": 0,
                "modificaciones": 0,
                "gasto_real": 0,
                "flujo_semanal": {semana: 0 for semana in semanas}
            }

        # Sumar valores
        familias_resumen[familia]["presupuesto_inicial"] += item.get('presupuesto_inicial', 0)
        familias_resumen[familia]["modificaciones"] += item.get('modificaciones', 0)
        familias_resumen[familia]["gasto_real"] += item.get('gasto_real', 0)

        # Sumar flujos semanales
        for semana in semanas:
            familias_resumen[familia]["flujo_semanal"][semana] += item['flujo_semanal'].get(semana, 0)

    # Convertir a lista y ordenar (INGRESOS primero)
    familias_lista = []
    if "INGRESOS" in familias_resumen:
        familias_lista.append(familias_resumen["INGRESOS"])

    # Agregar otras familias ordenadas alfabéticamente
    otras_familias = [familias_resumen[k] for k in sorted(familias_resumen.keys()) if k != "INGRESOS"]
    familias_lista.extend(otras_familias)

    # Calcular fila de total (INGRESOS - todas las demás)
    total_resumen = {
        "familia": "TOTAL",
        "presupuesto_inicial": 0,
        "modificaciones": 0,
        "gasto_real": 0,
        "flujo_semanal": {semana: 0 for semana in semanas}
    }

    ingresos = familias_resumen.get("INGRESOS", {"presupuesto_inicial": 0, "modificaciones": 0, "gasto_real": 0, "flujo_semanal": {}})

    # Total = Ingresos - suma de todas las demás familias
    total_resumen["presupuesto_inicial"] = ingresos["presupuesto_inicial"]
    total_resumen["modificaciones"] = ingresos["modificaciones"]
    total_resumen["gasto_real"] = ingresos["gasto_real"]

    for semana in semanas:
        total_resumen["flujo_semanal"][semana] = ingresos["flujo_semanal"].get(semana, 0)

    # Restar todas las demás familias
    for familia_key, familia_data in familias_resumen.items():
        if familia_key != "INGRESOS":
            total_resumen["presupuesto_inicial"] -= familia_data["presupuesto_inicial"]
            total_resumen["modificaciones"] -= familia_data["modificaciones"]
            total_resumen["gasto_real"] -= familia_data["gasto_real"]

            for semana in semanas:
                total_resumen["flujo_semanal"][semana] -= familia_data["flujo_semanal"].get(semana, 0)

    conn.close()

    return templates.TemplateResponse("obra_flujo_cajas.html", {
        "request": request,
        "user": user,
        "obra": dict(obra),
        "fecha_inicio": config['fecha_inicio'],
        "fecha_fin": config['fecha_fin'],
        "semanas": semanas,
        "items": items_with_flujo,
        "familias_resumen": familias_lista,
        "total_resumen": total_resumen
    })

@app.post("/obras/{obra_id}/flujo-cajas/fechas")
async def update_flujo_dates(request: Request, obra_id: int, fecha_inicio: str = Form(...), fecha_fin: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db_connection()

    # Update or insert config
    conn.execute('''
        INSERT OR REPLACE INTO obra_flujo_config (obra_id, fecha_inicio, fecha_fin)
        VALUES (?, ?, ?)
    ''', (obra_id, fecha_inicio, fecha_fin))
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/obras/{obra_id}/flujo-cajas", status_code=302)

@app.post("/obras/{obra_id}/flujo-cajas/items")
async def add_flujo_item(request: Request, obra_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    data = await request.json()

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO flujo_cajas_items (obra_id, codigo, nombre, presupuesto_inicial, modificaciones, gasto_real)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (obra_id, data['codigo'], data['nombre'], data['presupuesto_inicial'], data['modificaciones'], data['gasto_real']))
    conn.commit()
    conn.close()

    return {"status": "success"}

@app.post("/obras/{obra_id}/flujo-cajas/items/{item_id}/semana")
async def update_week_value(request: Request, obra_id: int, item_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    data = await request.json()

    conn = get_db_connection()
    conn.execute('''
        INSERT OR REPLACE INTO flujo_cajas_semanal (item_id, semana, valor)
        VALUES (?, ?, ?)
    ''', (item_id, data['semana'], data['valor']))
    conn.commit()
    conn.close()

    return {"status": "success"}

@app.put("/obras/{obra_id}/flujo-cajas/items/{item_id}/modificaciones")
async def update_modificaciones(request: Request, obra_id: int, item_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    data = await request.json()
    modificaciones = float(data.get('modificaciones', 0))

    conn = get_db_connection()
    conn.execute('''
        UPDATE flujo_cajas_items
        SET modificaciones = ?
        WHERE id = ? AND obra_id = ?
    ''', (modificaciones, item_id, obra_id))
    conn.commit()
    conn.close()

    return {"status": "success"}

@app.delete("/obras/{obra_id}/flujo-cajas/items/{item_id}")
async def delete_flujo_item(request: Request, obra_id: int, item_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    conn = get_db_connection()
    # Delete item (cascade will remove weekly data)
    conn.execute('DELETE FROM flujo_cajas_items WHERE id = ? AND obra_id = ?', (item_id, obra_id))
    conn.commit()
    conn.close()

    return {"status": "success"}

# Routes for items management
@app.get("/obras/{obra_id}/flujo-cajas/available-items")
async def get_available_items(request: Request, obra_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    conn = get_db_connection()
    items = conn.execute('''
        SELECT * FROM items ORDER BY tipo, codigo
    ''').fetchall()
    conn.close()

    return {"items": [dict(item) for item in items]}

@app.post("/obras/items")
async def create_item(request: Request, codigo: str = Form(...), nombre: str = Form(...), tipo: str = Form(...)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    # Check if user has permission (Admin or Manager)
    if not (user['is_admin'] or user['is_manager']):
        raise HTTPException(status_code=403, detail="Sin permisos para crear items")

    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO items (codigo, nombre, tipo)
            VALUES (?, ?, ?)
        ''', (codigo, nombre, tipo))
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Item creado exitosamente"}
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="El código ya existe")

@app.get("/obras/items", response_class=HTMLResponse)
async def items_management(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Check if user has permission (Admin or Manager)
    if not (user['is_admin'] or user['is_manager']):
        raise HTTPException(status_code=403, detail="Sin permisos para acceder")

    conn = get_db_connection()
    items = conn.execute('''
        SELECT * FROM items ORDER BY tipo, codigo
    ''').fetchall()
    conn.close()

    return templates.TemplateResponse("items_management.html", {
        "request": request,
        "user": user,
        "items": [dict(item) for item in items]
    })

@app.post("/obras/{obra_id}/flujo-cajas/items/from-catalog")
async def add_item_from_catalog(request: Request, obra_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    data = await request.json()
    item_id = data.get('item_id')
    presupuesto_inicial = float(data.get('presupuesto_inicial', 0))
    modificaciones = float(data.get('modificaciones', 0))
    gasto_real = float(data.get('gasto_real', 0))

    conn = get_db_connection()

    # Get item from catalog
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Item no encontrado")

    # Add item to flujo cajas
    conn.execute('''
        INSERT INTO flujo_cajas_items (obra_id, codigo, nombre, presupuesto_inicial, modificaciones, gasto_real)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (obra_id, item['codigo'], item['nombre'], presupuesto_inicial, modificaciones, gasto_real))

    conn.commit()
    conn.close()

    return {"status": "success"}


# RUTAS PARA CRÉDITOS DENTRO DEL FLUJO DE CAJA

@app.get("/flujo-caja/creditos", response_class=HTMLResponse)
async def ver_creditos(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)

    # Solo Administrador y Gerente pueden acceder
    if not (user['is_admin'] or user['is_manager']):
        raise HTTPException(status_code=403, detail="Acceso denegado")

    conn = get_db_connection()
    creditos = conn.execute('''
        SELECT * FROM creditos ORDER BY fecha_pago ASC
    ''').fetchall()
    conn.close()

    # Redirect to main flujo-caja page since credits are integrated there
    return RedirectResponse(url="/flujo-caja", status_code=302)

@app.post("/flujo-caja/creditos")
async def crear_credito(
    request: Request,
    nombre_credito: str = Form(...),
    banco: str = Form(...),
    cuotas_restantes: int = Form(...),
    valor_cuota: float = Form(...),
    fecha_pago: str = Form(...)
):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    # Solo Administrador y Gerente pueden crear créditos
    if not (user['is_admin'] or user['is_manager']):
        raise HTTPException(status_code=403, detail="Acceso denegado")

    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO creditos (nombre_credito, banco, cuotas_restantes, valor_cuota, fecha_pago)
            VALUES (?, ?, ?, ?, ?)
        ''', (nombre_credito, banco, cuotas_restantes, valor_cuota, fecha_pago))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear crédito: {str(e)}")
    finally:
        conn.close()

    return RedirectResponse(url="/flujo-caja", status_code=302)

@app.put("/flujo-caja/creditos/{credito_id}")
async def actualizar_credito(
    request: Request,
    credito_id: int
):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    # Get JSON data instead of Form data for PUT request
    data = await request.json()
    nombre_credito = data.get('nombre_credito')
    banco = data.get('banco')
    cuotas_restantes = int(data.get('cuotas_restantes', 0))
    valor_cuota = float(data.get('valor_cuota', 0))
    fecha_pago = data.get('fecha_pago')

    # Solo Administrador y Gerente pueden actualizar créditos
    if not (user['is_admin'] or user['is_manager']):
        raise HTTPException(status_code=403, detail="Acceso denegado")

    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE creditos
            SET nombre_credito = ?, banco = ?, cuotas_restantes = ?,
                valor_cuota = ?, fecha_pago = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (nombre_credito, banco, cuotas_restantes, valor_cuota, fecha_pago, credito_id))

        if conn.rowcount == 0:
            raise HTTPException(status_code=404, detail="Crédito no encontrado")

        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar crédito: {str(e)}")
    finally:
        conn.close()

    return {"status": "success", "message": "Crédito actualizado correctamente"}

@app.delete("/flujo-caja/creditos/{credito_id}")
async def eliminar_credito(credito_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    # Solo Administrador y Gerente pueden eliminar créditos
    if not (user['is_admin'] or user['is_manager']):
        raise HTTPException(status_code=403, detail="Acceso denegado")

    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM creditos WHERE id = ?', (credito_id,))

        if conn.rowcount == 0:
            raise HTTPException(status_code=404, detail="Crédito no encontrado")

        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar crédito: {str(e)}")
    finally:
        conn.close()

    return {"status": "success", "message": "Crédito eliminado correctamente"}

@app.get("/flujo-caja/creditos/{credito_id}")
async def obtener_credito(credito_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    # Solo Administrador y Gerente pueden ver detalles de créditos
    if not (user['is_admin'] or user['is_manager']):
        raise HTTPException(status_code=403, detail="Acceso denegado")

    conn = get_db_connection()
    credito = conn.execute('SELECT * FROM creditos WHERE id = ?', (credito_id,)).fetchone()
    conn.close()

    if not credito:
        raise HTTPException(status_code=404, detail="Crédito no encontrado")

    return dict(credito)

@app.post("/flujo-caja/creditos/{credito_id}/pagar-cuota")
async def pagar_cuota_credito(credito_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    # Solo Administrador y Gerente pueden procesar pagos
    if not (user['is_admin'] or user['is_manager']):
        raise HTTPException(status_code=403, detail="Acceso denegado")

    conn = get_db_connection()
    try:
        # Verificar que el crédito existe y tiene cuotas pendientes
        credito = conn.execute('SELECT * FROM creditos WHERE id = ?', (credito_id,)).fetchone()
        if not credito:
            raise HTTPException(status_code=404, detail="Crédito no encontrado")

        if credito['cuotas_restantes'] <= 0:
            raise HTTPException(status_code=400, detail="Este crédito ya está pagado completamente")

        # Reducir una cuota
        nueva_cuotas_restantes = credito['cuotas_restantes'] - 1

        conn.execute('''
            UPDATE creditos
            SET cuotas_restantes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (nueva_cuotas_restantes, credito_id))

        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al procesar el pago: {str(e)}")
    finally:
        conn.close()

    return {"status": "success", "message": "Cuota pagada correctamente", "cuotas_restantes": nueva_cuotas_restantes}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
