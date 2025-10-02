# Constructora ICC - Aplicación Web

Aplicación web simple para gestión de usuarios de Constructora ICC.

## Características

- **Autenticación**: Sistema de login con sesiones seguras
- **Dashboard**: Página de inicio para usuarios autenticados
- **Gestión de perfil**: Los usuarios pueden actualizar su email y contraseña
- **Administración**: Los administradores pueden gestionar usuarios
- **Tema oscuro**: Interfaz optimizada para uso en terreno

## Instalación

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Ejecutar la aplicación:
```bash
python main.py
```

La aplicación estará disponible en `http://localhost:8000`

## Usuario por defecto

- **Email**: ccarreno@constructoraicc.cl
- **Contraseña**: password123
- **Nivel**: Administrador

## Estructura del proyecto

```
aplicación/
├── main.py                 # Aplicación FastAPI principal
├── requirements.txt        # Dependencias
├── constructora_icc.db    # Base de datos SQLite (se crea automáticamente)
├── static/
│   └── style.css          # Estilos CSS
└── templates/
    ├── base.html          # Plantilla base
    ├── login.html         # Página de login
    ├── dashboard.html     # Dashboard principal
    ├── profile.html       # Configuración de perfil
    └── admin_users.html   # Gestión de usuarios (admin)
```

## Funcionalidades

### Para todos los usuarios:
- Iniciar/cerrar sesión
- Ver dashboard con información personal
- Actualizar email y contraseña

### Para administradores:
- Gestionar usuarios (crear, ver, eliminar)
- Asignar permisos de administrador

## Tecnologías utilizadas

- **Backend**: FastAPI (Python)
- **Base de datos**: SQLite
- **Frontend**: HTML, CSS, JavaScript vanilla
- **Autenticación**: Sesiones con tokens seguros