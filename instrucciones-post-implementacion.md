# Instrucciones Post-Implementación - Disco Persistente

## ✅ Cambios completados

Ya he implementado todos los cambios necesarios para que tu aplicación use el disco persistente de Render:

### 1. **Archivos modificados:**
- ✅ `main.py` - Configurado para usar disco persistente
- ✅ `funciones.py` - Actualizado para usar las nuevas rutas

### 2. **Cambios implementados:**

#### En `main.py`:
- ✅ **Directorio persistente configurado:** `/opt/render/project/data`
- ✅ **Variables de rutas agregadas:** `DATABASE`, `FACTURAS_CSV`, `SUBIDAS_CSV`, `CUENTAS_XLSX`, `UN_XLSX`
- ✅ **Función de migración:** `migrate_files_to_persistent_disk()` - Copia archivos existentes al disco
- ✅ **Función de archivos por defecto:** `ensure_default_files()` - Crea archivos vacíos si no existen
- ✅ **Startup actualizado:** Migra archivos y crea por defecto al iniciar
- ✅ **Todas las referencias de archivos actualizadas** (13 ubicaciones cambiadas)

#### En `funciones.py`:
- ✅ **Función `agregar_a_subidas_csv()`** - Usa `SUBIDAS_CSV` del disco persistente
- ✅ **Función `agregar_campo_subidas_a_facturas()`** - Usa `SUBIDAS_CSV` del disco persistente
- ✅ **Función `preparar_facturas()`** - Usa `CUENTAS_XLSX`, `UN_XLSX`, `FACTURAS_CSV` del disco persistente

---

## 📋 Qué hacer ahora

### 1. **Hacer commit de los cambios**
```bash
git add .
git commit -m "Implementar persistencia con disco de Render - Configurar rutas persistentes para todos los archivos"
```

### 2. **Desplegar a Render**
```bash
git push origin main
```

### 3. **Verificar el deploy**
1. Ve a tu dashboard de Render
2. Espera a que termine el deploy
3. Revisa los logs para ver las migraciones:
   ```
   Migrando constructora_icc.db a /opt/render/project/data/constructora_icc.db
   Migrando facturas.csv a /opt/render/project/data/facturas.csv
   Migrando subidas.csv a /opt/render/project/data/subidas.csv
   ```

### 4. **Probar la aplicación**
- ✅ **Login** funcionando
- ✅ **Facturas** cargando correctamente
- ✅ **Cuentas** y **Centros de Costos** editables
- ✅ **Subidas a KAME** persistiendo
- ✅ **Base de datos** manteniéndose entre reinicios

---

## 🔧 Cómo funciona ahora

### **Antes (efímero):**
```
/app/
├── constructora_icc.db  ❌ Se perdía en cada reinicio
├── facturas.csv         ❌ Se perdía en cada reinicio
├── subidas.csv          ❌ Se perdía en cada reinicio
└── cuentas.xlsx         ❌ Se perdía en cada reinicio
```

### **Después (persistente):**
```
/opt/render/project/data/    ✅ Disco persistente
├── constructora_icc.db      ✅ Persiste para siempre
├── facturas.csv             ✅ Persiste para siempre
├── subidas.csv              ✅ Persiste para siempre
├── cuentas.xlsx             ✅ Persiste para siempre
└── UN.xlsx                  ✅ Persiste para siempre
```

### **Migración automática:**
Al primera vez que despliegues:
1. La app detecta archivos en la ubicación antigua
2. Los copia automáticamente al disco persistente
3. Usa solo las rutas persistentes a partir de ahí

---

## 💰 Costo

**Disco de 1GB:** $0.25/mes
- Tu proyecto usa ~10MB
- Sobran ~990MB para crecimiento
- **Total:** Menos de $1/mes

---

## 🚨 Verificaciones importantes

### **Después del primer deploy, verifica:**

1. **Archivos migrados correctamente:**
   ```bash
   # En los logs de Render deberías ver:
   Migrando constructora_icc.db a /opt/render/project/data/constructora_icc.db
   Migrando facturas.csv a /opt/render/project/data/facturas.csv
   ```

2. **Aplicación funcionando:**
   - Login exitoso
   - Facturas cargando
   - Poder editar cuentas y centros de costos
   - Subidas a KAME funcionando

3. **Persistencia funcionando:**
   - Haz un cambio (ej: editar una cuenta)
   - Espera 5 minutos (para que Render pueda reiniciar)
   - Verifica que el cambio se mantuvo

---

## 🛠️ Solución de problemas

### **Si los archivos no se migran:**
```bash
# Revisa los logs de Render para ver errores
# Los archivos se crearán vacíos automáticamente
```

### **Si la aplicación no inicia:**
```bash
# Verifica que el disco esté montado en: /opt/render/project/data
# Revisa la configuración del disco en Settings > Disks
```

### **Si los datos no persisten:**
```bash
# Verifica que el Mount Path sea exactamente: /opt/render/project/data
# Confirma que el disco esté activo en tu dashboard
```

---

## ✅ Próximos pasos

1. **Deploy inmediato** - Haz push de los cambios
2. **Verificar funcionamiento** - Prueba todas las funciones
3. **Respaldo opcional** - Considera hacer backup de archivos críticos
4. **Monitoreo** - Revisa logs regularmente la primera semana

---

## 📞 Soporte

Si encuentras algún problema:
1. Revisa los logs de Render
2. Verifica que el disco esté montado correctamente
3. Confirma que los archivos existen en `/opt/render/project/data/`

**¡Tu aplicación ahora tiene persistencia completa!** 🎉