# MediaMTX Recording Manager - Guía de Instalación

## Descripción General

**MediaMTX Recording Manager** es una interfaz web para gestionar grabaciones de MediaMTX. Permite:
- Ver todas las grabaciones organizadas por cámaras/rutas
- Reproducir segmentos de vídeo
- Eliminar segmentos individuales o por lotes
- Consultar y modificar la configuración de grabación automática
- Gestionar archivos .mp4 directamente en el disco

## Requisitos Previos

- **Docker y Docker Compose** instalados en el servidor Linux
- **MediaMTX** ejecutándose en el mismo servidor (en un contenedor Docker)
- Acceso SSH al servidor o permiso para ejecutar comandos Docker
- Puerto **8080** disponible (o cualquier puerto que elijas)

## Instalación Manual en Linux

### Paso 1: Conectarse al servidor

```bash
ssh usuario@192.168.1.147
# (O la IP/dirección de tu servidor)
```

### Paso 2: Copiar los archivos

Copia la carpeta `mediamtx-manager` a tu servidor Linux:

```bash
scp -r /ruta/local/mediamtx-manager usuario@192.168.1.147:/home/usuario/
```

Alternativa: Si ya tienes los archivos, verifica que estén en una carpeta accesible.

### Paso 3: Verificar la configuración de MediaMTX

Antes de iniciar, comprueba que tu contenedor MediaMTX está ejecutándose:

```bash
docker ps | grep mediamtx
```

**Importante:** Anota el nombre exacto del contenedor. Por defecto suele ser:
- `mediamtx-mediamtx-1` (si lo levantaste con `docker-compose`)
- `mediamtx` (si tiene un nombre personalizado)

También verifica el nombre de la red:
```bash
docker network ls | grep mediamtx
```

Normalmente es `mediamtx_default` o similar.

### Paso 4: Ajustar docker-compose.yml

Abre el archivo `docker-compose.yml` y verifica/ajusta estas líneas:

```yaml
services:
  mediamtx-manager:
    # ...
    environment:
      MEDIAMTX_API: "http://NOMBRE_CONTENEDOR_MEDIAMTX:9997"
    # ...
    networks:
      - NOMBRE_RED_MEDIAMTX

networks:
  NOMBRE_RED_MEDIAMTX:
    external: true

volumes:
  mediamtx_data:
    external: true
```

Reemplaza:
- `NOMBRE_CONTENEDOR_MEDIAMTX` con el nombre real (ej: `mediamtx-mediamtx-1`)
- `NOMBRE_RED_MEDIAMTX` con la red correcta (ej: `mediamtx_default`)

### Paso 5: Levantar el contenedor

```bash
cd mediamtx-manager
docker compose up -d --build
```

Espera unos segundos a que el contenedor inicie.

### Paso 6: Acceder a la interfaz

Abre tu navegador y ve a:
```
http://192.168.1.147:8080
```

(Cambia `192.168.1.147` por la IP real de tu servidor)

## Verificar que funciona

### 1. Comprobar conectividad con MediaMTX

En la interfaz web, deberías ver el estado de conexión en la esquina superior izquierda (punto verde = conectado, rojo = error).

### 2. Si hay problemas, consulta los logs

```bash
docker logs mediamtx-manager -f --timestamps
```

Busca errores como:
- `Connection refused` → MediaMTX no es accesible con ese nombre/puerto
- `Could not resolve hostname` → El nombre del contenedor es incorrecto
- `Data directory not mounted` → El volumen no está montado correctamente

### 3. Probar endpoints desde terminal

```bash
# Verificar conectividad con MediaMTX
curl http://127.0.0.1:9997/v3/config/global/get | jq .

# Ver grabaciones
curl http://127.0.0.1:9997/v3/recordings/list | jq .

# Verificar archivos en el volumen
docker exec mediamtx-manager ls -lah /data/
```

## Uso de la Interfaz

### Pestaña "Segmentos"
- Muestra todos los segmentos de grabación organizados por ruta/cámara
- Cada segmento tiene información: inicio, duración, tamaño del archivo
- Botones:
  - **Ver** (▶): Reproduce el vídeo en una ventana modal
  - **Eliminar**: Elimina el segmento y su archivo asociado
  - Checkbox: Selecciona múltiples segmentos para eliminación por lotes

### Pestaña "Archivos en disco"
- Muestra todos los archivos .mp4 en `/data` (el volumen de grabación)
- Permite eliminar archivos directamente sin pasar por MediaMTX
- Útil si quieres eliminar archivos huérfanos o corruptos

### Configuración de Grabación
- **Grabar**: Activa/desactiva grabación por ruta
- **Borrado automático**: Configura cuánto tiempo mantener grabaciones antes de borrar automáticamente
  - Usa formato Go: `24h`, `30m`, `3600s`
  - Ejemplo: `24h` = borra grabaciones más antiguas de 24 horas
  - **Nota**: El período de borrado debe ser >= que la duración de cada segmento

## Problemas Comunes

### Error 400 al intentar eliminar

**Síntoma**: "400 Client Error" al hacer clic en "Eliminar"

**Causa**: El segmento puede estar siendo grabado actualmente o ya no existe en MediaMTX

**Solución**: 
1. Espera a que termine de grabarse ese segmento
2. Recarga la página
3. Intenta nuevamente

Si el archivo se eliminó del disco pero MediaMTX devuelve error, la app mostrará un mensaje informativo.

### No aparecen grabaciones

**Síntoma**: La interfaz dice "No hay grabaciones"

**Causa**: MediaMTX no está grabando o no hay segmentos completados

**Solución**:
1. Verifica que el stream esté activo en MediaMTX
2. Comprueba que `record: true` esté habilitado en la config
3. Espera a que se complete el primer segmento (puede tardar minutos)

### Archivos no se eliminan del disco

**Síntoma**: Los archivos siguen existiendo después de eliminar desde la web

**Causa**: Problemas de permisos en el volumen Docker

**Solución**:
1. Verifica que el volumen tiene permisos de lectura/escritura:
```bash
docker exec mediamtx-manager ls -la /data/
```
2. Consulta los logs para más detalles
3. Asegúrate de que el volumen no está montado como read-only (`:ro`)

### Problemas de conectividad

**Síntoma**: "Punto rojo" en la esquina superior izquierda, o error "MediaMTX no disponible"

**Causa**: El contenedor mediamtx-manager no puede alcanzar a MediaMTX

**Soluciones**:
1. Verifica el nombre del contenedor:
```bash
docker ps | grep mediamtx
```

2. Verifica que ambos contenedores están en la misma red:
```bash
docker network inspect mediamtx_default
```

3. Edita `docker-compose.yml` con los valores correctos y reinicia:
```bash
docker compose down
docker compose up -d --build
```

## Parar y reiniciar

```bash
# Parar
docker compose down

# Reiniciar
docker compose up -d

# Ver logs en tiempo real
docker logs mediamtx-manager -f --timestamps
```

## Puertos y Acceso

- **Puerto 8080**: Interfaz web (http://servidor:8080)
- Asegúrate de que el puerto 8080 no esté bloqueado por firewall:
```bash
sudo ufw allow 8080/tcp
# O en iptables:
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
```

## Configuración Avanzada

### Variables de entorno

En `docker-compose.yml` puedes ajustar:

```yaml
environment:
  MEDIAMTX_API: "http://mediamtx-mediamtx-1:9997"  # URL de la API de MediaMTX
  REQUEST_TIMEOUT: "10"  # Timeout en segundos para peticiones HTTP
  DATA_PATH: "/data"  # Ruta del volumen dentro del contenedor
  FLASK_ENV: "production"  # Cambiar a "development" para más logs
```

### Puerto personalizado

Para usar un puerto diferente a 8080, modifica en `docker-compose.yml`:

```yaml
ports:
  - "9000:8080"  # Expone el puerto 9000 en lugar de 8080
```

Luego accede a `http://servidor:9000`

## Soporte y Diagnóstico

Si tienes problemas:

1. **Consulta los logs**:
```bash
docker logs mediamtx-manager --tail=100 --timestamps
```

2. **Ejecuta el script de diagnóstico** (dentro del contenedor):
```bash
docker exec mediamtx-manager bash /app/debug_api.sh
```

3. **Verifica manualmente los endpoints**:
```bash
# Desde el servidor Linux:
curl -s http://127.0.0.1:9997/v3/recordings/list | jq .
curl -s http://127.0.0.1:8080/api/recordings | jq .
```

4. **Incluye esta información en cualquier reporte de error**:
   - Salida de `docker ps`
   - Salida de `docker logs mediamtx-manager` (últimas 50 líneas)
   - Tu archivo `docker-compose.yml` (sin datos sensibles)
   - URL exacta que usas para acceder

## Estructura de archivos

```
mediamtx-manager/
├── Dockerfile           # Configuración del contenedor
├── docker-compose.yml   # Orquestación de contenedores
├── app.py              # API Flask (backend)
├── requirements.txt    # Dependencias de Python
├── templates/
│   └── index.html      # Interfaz web (frontend)
├── debug_api.sh        # Script de diagnóstico
└── INSTRUCCIONES.md    # Este archivo
```

## Licencia y Créditos

Desarrollado como herramienta complementaria para MediaMTX.
MediaMTX es un software de código abierto: https://github.com/bluenviron/mediamtx

## Contacto y Reportar Errores

Si encuentras bugs o tienes sugerencias:
1. Revisa los logs con `docker logs mediamtx-manager`
2. Prueba la reproducción del problema
3. Documenta los pasos exactos para reproducirlo
