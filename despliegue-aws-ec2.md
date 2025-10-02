# Guía de Despliegue en AWS EC2 - Aplicación Constructora ICC

Esta guía te ayudará a desplegar tu aplicación FastAPI en una instancia EC2 de AWS paso a paso.

## Prerrequisitos

- Cuenta de AWS activa
- Acceso a la consola de AWS
- Conocimientos básicos de terminal/SSH
- Tu aplicación FastAPI funcionando localmente

## Paso 1: Crear una Instancia EC2

1. **Inicia sesión en la Consola de AWS**
   - Ve a [https://aws.amazon.com/console/](https://aws.amazon.com/console/)
   - Inicia sesión con tus credenciales

2. **Navega al servicio EC2**
   - En el panel de servicios, busca "EC2" o navega a "Compute" > "EC2"

3. **Lanza una nueva instancia**
   - Haz clic en "Launch Instance"
   - **Nombre**: Constructora-ICC-App
   - **AMI**: Ubuntu Server 22.04 LTS (Free tier eligible)
   - **Tipo de instancia**: t2.micro (Free tier eligible)
   - **Key pair**: Crea o selecciona un key pair existente (necesario para SSH)
   - **Grupo de seguridad**: Crear uno nuevo con las siguientes reglas:
     - SSH (puerto 22) desde tu IP
     - HTTP (puerto 80) desde cualquier lugar (0.0.0.0/0)
     - HTTPS (puerto 443) desde cualquier lugar (0.0.0.0/0)
     - Custom TCP (puerto 8000) desde cualquier lugar (0.0.0.0/0)

4. **Configura almacenamiento**
   - 8 GB GP2 (incluido en free tier)

5. **Lanza la instancia**
   - Revisa la configuración y haz clic en "Launch Instance"

## Paso 2: Conectar a la Instancia EC2

1. **Obtén la IP pública**
   - Ve a la sección "Instances" en EC2
   - Selecciona tu instancia y copia la "Public IPv4 address"

2. **Conecta vía SSH**
   ```bash
   ssh -i tu-key-pair.pem ubuntu@TU-IP-PUBLICA
   ```

## Paso 3: Preparar el Servidor

1. **Actualizar el sistema**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Instalar Python 3.11 y pip**
   ```bash
   sudo apt install python3.11 python3.11-pip python3.11-venv -y
   sudo ln -sf /usr/bin/python3.11 /usr/bin/python3
   sudo ln -sf /usr/bin/python3.11 /usr/bin/python
   ```

3. **Instalar dependencias del sistema**
   ```bash
   sudo apt install git nginx supervisor -y
   ```

## Paso 4: Subir la Aplicación

1. **Crear directorio para la aplicación**
   ```bash
   sudo mkdir -p /var/www/constructora-icc
   sudo chown -R ubuntu:ubuntu /var/www/constructora-icc
   cd /var/www/constructora-icc
   ```

2. **Subir archivos de la aplicación**
   Opción A - Usando Git (recomendado):
   ```bash
   # Si tienes un repositorio Git
   git clone TU-REPOSITORIO .
   ```

   Opción B - Usando SCP desde tu máquina local:
   ```bash
   # Desde tu máquina local (no en el servidor)
   scp -i tu-key-pair.pem -r ./aplicación/* ubuntu@TU-IP-PUBLICA:/var/www/constructora-icc/
   ```

3. **Crear entorno virtual e instalar dependencias**
   ```bash
   cd /var/www/constructora-icc
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Paso 5: Configurar Base de Datos

1. **Verificar que la base de datos se inicialice correctamente**
   ```bash
   cd /var/www/constructora-icc
   source venv/bin/activate
   python -c "
   import sqlite3
   from main import init_db
   init_db()
   print('Base de datos inicializada correctamente')
   "
   ```

2. **Dar permisos correctos a la base de datos**
   ```bash
   sudo chown ubuntu:ubuntu constructora_icc.db
   chmod 664 constructora_icc.db
   ```

## Paso 6: Configurar Supervisor (Proceso Manager)

1. **Crear archivo de configuración de Supervisor**
   ```bash
   sudo nano /etc/supervisor/conf.d/constructora-icc.conf
   ```

2. **Agregar la siguiente configuración**:
   ```ini
   [program:constructora-icc]
   command=/var/www/constructora-icc/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
   directory=/var/www/constructora-icc
   user=ubuntu
   autostart=true
   autorestart=true
   redirect_stderr=true
   stdout_logfile=/var/log/constructora-icc.log
   ```

3. **Recargar y iniciar Supervisor**
   ```bash
   sudo supervisorctl reread
   sudo supervisorctl update
   sudo supervisorctl start constructora-icc
   ```

4. **Verificar que la aplicación esté corriendo**
   ```bash
   sudo supervisorctl status
   curl http://localhost:8000
   ```

## Paso 7: Configurar Nginx como Proxy Reverso

1. **Crear archivo de configuración de Nginx**
   ```bash
   sudo nano /etc/nginx/sites-available/constructora-icc
   ```

2. **Agregar la siguiente configuración**:
   ```nginx
   server {
       listen 80;
       server_name TU-IP-PUBLICA;

       client_max_body_size 50M;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location /static/ {
           alias /var/www/constructora-icc/static/;
           expires 30d;
           add_header Cache-Control "public, no-transform";
       }
   }
   ```

3. **Habilitar el sitio**
   ```bash
   sudo ln -s /etc/nginx/sites-available/constructora-icc /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo nginx -t
   sudo systemctl restart nginx
   ```

## Paso 8: Configurar el Firewall

```bash
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw status
```

## Paso 9: Verificar el Despliegue

1. **Verificar que todos los servicios estén corriendo**
   ```bash
   sudo systemctl status nginx
   sudo supervisorctl status
   ```

2. **Probar la aplicación**
   - Abre tu navegador web
   - Ve a `http://TU-IP-PUBLICA`
   - Deberías ver la página de login de la aplicación

3. **Verificar logs si hay problemas**
   ```bash
   # Logs de la aplicación
   sudo tail -f /var/log/constructora-icc.log
   
   # Logs de Nginx
   sudo tail -f /var/log/nginx/error.log
   ```

## Paso 10: Configurar SSL (Opcional pero Recomendado)

1. **Instalar Certbot**
   ```bash
   sudo apt install certbot python3-certbot-nginx -y
   ```

2. **Obtener certificado SSL**
   ```bash
   sudo certbot --nginx -d tu-dominio.com
   ```

## Credenciales de Acceso por Defecto

- **Email**: ccarreno@constructoraicc.cl
- **Contraseña**: password123

**¡IMPORTANTE!** Cambia estas credenciales inmediatamente después del primer login.

## Comandos Útiles para Administración

```bash
# Reiniciar la aplicación
sudo supervisorctl restart constructora-icc

# Ver logs de la aplicación
sudo tail -f /var/log/constructora-icc.log

# Reiniciar Nginx
sudo systemctl restart nginx

# Actualizar la aplicación (si usas Git)
cd /var/www/constructora-icc
git pull
sudo supervisorctl restart constructora-icc

# Backup de la base de datos
cp constructora_icc.db backup_$(date +%Y%m%d_%H%M%S).db
```

## Estructura de Archivos en el Servidor

```
/var/www/constructora-icc/
├── main.py                 # Aplicación principal
├── funciones.py           # Funciones auxiliares
├── requirements.txt       # Dependencias
├── constructora_icc.db   # Base de datos SQLite
├── venv/                 # Entorno virtual
├── static/               # Archivos estáticos
├── templates/            # Plantillas HTML
├── facturas.csv         # Datos de facturas
├── cuentas.xlsx         # Configuración de cuentas
├── UN.xlsx              # Centros de costos
└── subidas.csv          # Log de facturas subidas
```

## Troubleshooting

### La aplicación no carga
1. Verificar que Supervisor esté corriendo: `sudo supervisorctl status`
2. Revisar logs: `sudo tail -f /var/log/constructora-icc.log`
3. Verificar que el puerto 8000 esté libre: `sudo netstat -tlnp | grep 8000`

### Error 502 Bad Gateway
1. Verificar que la aplicación esté corriendo en el puerto 8000
2. Revisar configuración de Nginx
3. Verificar logs de Nginx: `sudo tail -f /var/log/nginx/error.log`

### Problemas con la base de datos
1. Verificar permisos: `ls -la constructora_icc.db`
2. Recrear la base de datos: `rm constructora_icc.db && python -c "from main import init_db; init_db()"`

### No se pueden subir archivos
1. Verificar permisos del directorio: `sudo chown -R ubuntu:ubuntu /var/www/constructora-icc`
2. Verificar configuración de Nginx para `client_max_body_size`

## Costos Estimados en AWS

- **Instancia t2.micro**: Gratis por 12 meses (Free Tier), luego ~$8.50/mes
- **Almacenamiento EBS**: Gratis 30GB por mes (Free Tier)
- **Transferencia de datos**: 15GB gratis por mes

## Mantenimiento Recomendado

1. **Backups regulares** de la base de datos y archivos
2. **Actualizaciones de seguridad** del sistema operativo
3. **Monitoreo de logs** para detectar errores
4. **Certificados SSL** renovar cada 90 días (automático con Certbot)

¡Tu aplicación ya debería estar funcionando en AWS EC2!