# 🚀 Guía Rápida de Despliegue v1.2.0

## ⚡ Despliegue en 30 segundos

```bash
cd /home/user/mediamtx-manager
docker compose down
docker compose up -d --build
```

Espera 10 segundos y accede a:
```
http://127.0.0.1:8080
```

---

## ✅ Verificación Rápida

### 1. ¿Está el contenedor ejecutándose?
```bash
docker ps | grep mediamtx-manager
```

Debe mostrar algo como:
```
abc123... mediamtx-manager "gunicorn --bind 0..." 5 seconds ago Up 5 seconds 0.0.0.0:8080->8080/tcp
```

### 2. ¿Hay errores en los logs?
```bash
docker logs mediamtx-manager --tail=20
```

No debe haber líneas con `ERROR` o `Exception`

### 3. ¿La interfaz está accesible?
```bash
curl http://127.0.0.1:8080 -s | head -5
```

Debe retornar HTML

---

## 🎬 Primeras Pruebas

### Prueba 1: Ver Streams en Vivo
1. Abre http://127.0.0.1:8080
2. Busca "📹 Emisión en Vivo" en la parte superior
3. Debería listar todas tus cámaras
4. Haz click en una cámara
5. Debería aparecer un reproductor

**Resultado esperado**: ✅ Puedes ver el stream en vivo

### Prueba 2: Ver Duración en Tabla
1. Click en pestaña "Segmentos"
2. Busca las columnas: `Inicio` | `Fin` | `Duración`
3. Cada fila debe tener valores en estas 3 columnas

**Resultado esperado**: ✅ Ves duración en formato HH:MM:SS (ej: 00:15:32)

### Prueba 3: Eliminar Archivo
1. Selecciona cualquier segmento con checkbox
2. Click en "Eliminar"
3. Confirma en el diálogo
4. La tabla debería refrescarse automáticamente

**Resultado esperado**: ✅ El archivo desaparece sin error 400

### Prueba 4: Eliminar Último Archivo (La Prueba Crítica)
1. Busca una ruta que solo tenga 1 segmento
2. Selecciona ese único segmento
3. Click en "Eliminar"
4. Confirma

**Resultado esperado**: 
- ✅ Se elimina correctamente
- ✅ NO muestra "Error 400"
- ✅ La tabla se recarga vacía
- ✅ Mensaje de éxito aparece

Si esto funciona, **la v1.2.0 está correcta** ✅

---

## 🔧 Si Algo Falla

### Error: "Connection refused"
```bash
# El contenedor no está corriendo. Verifica:
docker compose up -d --build

# Espera 10 segundos y luego:
docker logs mediamtx-manager --tail=30
```

### Error: "Error: 400 Client Error" al eliminar
```bash
# Esto no debería ocurrir en v1.2.0. Si ocurre:
# 1. Verifica que estés usando la última versión
docker logs mediamtx-manager | grep "format_duration"

# Debería haber lineas con format_duration

# 2. Si no aparece, reconstruye:
docker compose down
docker compose up -d --build
docker logs mediamtx-manager --tail=20
```

### Error: Streams no aparecen en visor
```bash
# Verifica que la API de MediaMTX responde:
curl http://mediamtx:9997/v3/paths/list | jq .

# Si da error, puede ser que:
# 1. MediaMTX no esté corriendo
# 2. La red Docker no es la correcta (edita docker-compose.yml)
# 3. El nombre del contenedor no coincide
```

### Error: Tabla vacía sin grabaciones
```bash
# Verifica que hay archivos en el volumen:
docker exec mediamtx-manager ls -la /data/recordings/

# Si está vacío, necesitas que MediaMTX esté grabando primero
```

---

## 📊 Comandos Útiles

### Ver logs en tiempo real
```bash
docker logs mediamtx-manager -f --timestamps
```
Presiona `Ctrl+C` para salir

### Ejecutar diagnóstico completo
```bash
docker exec mediamtx-manager bash /app/debug_api.sh
```

### Reiniciar solo la aplicación (sin perder datos)
```bash
docker restart mediamtx-manager
```

### Ver estado del contenedor
```bash
docker stats mediamtx-manager
```

### Limpiar todo y empezar de nuevo
```bash
docker compose down -v  # ⚠️ Elimina volúmenes (datos)
cd /home/user/mediamtx-manager
bash install.sh
```

---

## 🆕 Novedades de v1.2.0

### ✨ 1. Visor de Emisión en Vivo
- Selector visual de cámaras
- Indicadores de estado (🟢 activo / ⚫ inactivo)
- Reproductor HLS integrado
- Soporte para múltiples cámaras

### ✨ 2. Campos de Duración
- Columna "Fin" - hora exacta de finalización
- Columna "Duración" - formato HH:MM:SS
- Precisión de microsegundos en cálculos
- Fallback si backend no proporciona valores

### ✨ 3. Refresco Automático
- Cada eliminación refresca la tabla automáticamente
- Manejo gracioso de errores MediaMTX
- Acepta "éxito parcial" en eliminaciones
- Delays ajustados (300-1000ms según operación)

---

## 📋 Checklist Pre-Despliegue

- [ ] Tengo acceso a `/home/user/mediamtx-manager`
- [ ] Docker está instalado y corriendo
- [ ] MediaMTX está corriendo en su contenedor
- [ ] La red Docker es la correcta (o `install.sh` la configura)
- [ ] Tengo al menos 1 cámara configurada en MediaMTX
- [ ] He leído `NUEVAS_CARACTERISTICAS.md` (opcional pero recomendado)

---

## 🎯 Próximos Pasos Después de Desplegar

1. **Prueba todas las 4 pruebas** listadas arriba
2. **Reporta cualquier problema** 
3. **Lee la documentación completa** en `NUEVAS_CARACTERISTICAS.md`
4. **Consulta `INSTRUCCIONES.md`** para configuraciones avanzadas

---

## 📞 Soporte Rápido

| Problema | Solución |
|----------|----------|
| No veo streams | Verifica MediaMTX está corriendo con grabaciones activas |
| Error 400 | Reconstruye: `docker compose up -d --build` |
| Tabla vacía | Asegúrate que hay archivos grabados en `/data/recordings/` |
| Refresco no funciona | Verifica la consola del navegador (F12) por errores JavaScript |
| Duración no aparece | Limpia caché: Ctrl+Shift+R (o Cmd+Shift+R en Mac) |

---

**Versión**: 1.2.0  
**Estado**: ✅ Listo para producción  
**Tiempo de despliegue**: ~30 segundos  

¿Necesitas ayuda? Consulta:
- `NUEVAS_CARACTERISTICAS.md` - Detalles técnicos
- `INSTRUCCIONES.md` - Guía completa
- `README.md` - Overview del proyecto
