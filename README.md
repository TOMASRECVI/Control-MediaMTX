# 🎥 MediaMTX Recording Manager

Una interfaz web moderna para gestionar grabaciones de **MediaMTX** con facilidad. Visualiza, reproduce y elimina segmentos de grabación desde una dashboard intuitiva.

![Status](https://img.shields.io/badge/status-stable-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Docker](https://img.shields.io/badge/docker-required-blue)

## ✨ Características

- ✅ **Visualización de grabaciones** - Lista todos los segmentos organizados por ruta/cámara
- ✅ **Reproductor integrado** - Reproduce vídeos directamente en la interfaz con soporte para seek
- ✅ **Eliminación flexible** - Elimina segmentos individuales, por lotes o todos de una ruta
- ✅ **Gestión de archivos** - Acceso directo a archivos `.mp4` en el disco
- ✅ **Configuración de grabación** - Activa/desactiva grabación y establece borrado automático
- ✅ **Diseño responsive** - Funciona en desktop, tablet y móvil
- ✅ **Sin dependencias externas** - Todo se ejecuta en Docker

## 🚀 Instalación Rápida

### Opción 1: Script Automático (Recomendado)

```bash
cd /home/usuario/mediamtx-manager
bash install.sh
```

El script:
- ✓ Detecta tu contenedor MediaMTX automáticamente
- ✓ Configura la red y volúmenes correctamente
- ✓ Construye e inicia el contenedor
- ✓ Te muestra la URL para acceder

### Opción 2: Manual

1. **Edita `docker-compose.yml`**:
   ```yaml
   MEDIAMTX_API: "http://NOMBRE-TU-CONTENEDOR:9997"
   ```

2. **Inicia los contenedores**:
   ```bash
   docker compose up -d --build
   ```

3. **Accede a la interfaz**:
   ```
   http://<ip-de-tu-servidor>:8080
   ```

### Opción 3: Paquete de instalación genérico

Si vas a desplegar esto en un servidor nuevo (no el original del proyecto),
usa la carpeta [`install/`](install/README.md): un `docker-compose.yml`
configurable por variables de entorno (`.env`), sin nada específico de
ninguna red en concreto, con guía paso a paso incluida.

```bash
git clone https://github.com/TOMASRECVI/Control-MediaMTX.git
cd Control-MediaMTX/install
cp .env.example .env   # edita con los datos de tu servidor
docker compose up -d --build
```

## 📖 Documentación

- **[INSTRUCCIONES.md](INSTRUCCIONES.md)** - Guía completa de instalación, configuración y solución de problemas
- **[API Endpoints](API.md)** - Documentación de todos los endpoints disponibles

## 🎮 Uso

### Interfaz Principal

**Pestaña "Segmentos"**:
- Ver todos los segmentos de grabación
- Filtros por ruta/cámara
- Botones para reproducir o eliminar cada segmento
- Selección múltiple para eliminación por lotes

**Pestaña "Archivos en disco"**:
- Listar todos los `.mp4` guardados
- Eliminar archivos específicos o grupos
- Ver tamaño de archivo

**Panel de Control**:
- Cambiar estado de grabación
- Configurar borrado automático (ej: `24h`)
- Ver información de conexión

### Comandos Comunes

```bash
# Ver logs en tiempo real
docker logs mediamtx-manager -f --timestamps

# Parar la aplicación
docker compose down

# Reiniciar
docker compose up -d

# Reconstruir después de cambios
docker compose up -d --build

# Ejecutar diagnóstico
docker exec mediamtx-manager bash /app/debug_api.sh
```

## 🔧 Configuración

### Variables de entorno

En `docker-compose.yml`:

```yaml
environment:
  MEDIAMTX_API: "http://mediamtx-mediamtx-1:9997"  # URL de MediaMTX
  REQUEST_TIMEOUT: "10"                             # Timeout HTTP
  DATA_PATH: "/data"                                # Ruta del volumen
  FLASK_ENV: "production"                           # Modo debug/prod
```

### Puerto personalizado

```yaml
ports:
  - "9000:8080"  # Usa puerto 9000 en lugar de 8080
```

## 🆘 Solución de Problemas

### "Punto rojo" (No conecta con MediaMTX)

```bash
# Verifica el nombre del contenedor
docker ps | grep mediamtx

# Edita docker-compose.yml con el nombre correcto
nano docker-compose.yml

# Reinicia
docker compose down && docker compose up -d
```

### Error 400 al eliminar

- El segmento puede estar siendo grabado
- Espera a que se complete y recarga la página
- O intenta desde la pestaña "Archivos en disco"

### No aparecen grabaciones

```bash
# Verifica que MediaMTX esté grabando
docker logs mediamtx-nombre -f

# Comprueba los archivos
docker exec mediamtx-nombre ls -la /data/

# Espera a que se complete el primer segmento (puede tardar)
```

### No se eliminan archivos

```bash
# Verifica permisos del volumen
docker exec mediamtx-manager ls -la /data/

# Consulta los logs
docker logs mediamtx-manager

# Comprueba que el volumen no es read-only en docker-compose.yml
```

## 📁 Estructura

```
mediamtx-manager/
├── Dockerfile              # Imagen del contenedor
├── docker-compose.yml      # Configuración de orquestación
├── app.py                  # API Flask (backend)
├── requirements.txt        # Dependencias Python
├── templates/
│   └── index.html          # Interfaz web (frontend)
├── install.sh              # Script de instalación
├── debug_api.sh            # Diagnóstico
├── INSTRUCCIONES.md        # Guía completa (español)
└── README.md               # Este archivo
```

## 🔌 API Endpoints

### Información

- `GET /api/health` - Estado de conexión
- `GET /api/recordings` - Listar todas las grabaciones

### Control

- `DELETE /api/recordings/segment` - Eliminar un segmento
- `POST /api/recordings/batch-delete` - Eliminar múltiples segmentos
- `DELETE /api/recordings/path/<name>` - Eliminar todos los segmentos de una ruta
- `POST /api/recordings/files/delete` - Eliminar archivos del disco

### Configuración

- `GET /api/config/defaults` - Obtener config global
- `PATCH /api/config/defaults` - Modificar config global
- `PATCH /api/config/paths/<name>` - Configurar una ruta específica

### Multimedia

- `GET /video/<path>` - Reproducir vídeo (con soporte para seek)

## 🐛 Reportar Errores

Si encuentras un bug:

1. Consulta los logs:
   ```bash
   docker logs mediamtx-manager --tail=100
   ```

2. Ejecuta el diagnóstico:
   ```bash
   docker exec mediamtx-manager bash /app/debug_api.sh
   ```

3. Intenta reproducir el problema

4. Reporta con:
   - Descripción del problema
   - Pasos para reproducir
   - Logs relevantes
   - Tu versión de Docker

## 📝 Cambios Recientes

### v1.1.0
- ✨ Manejo mejorado de errores 400 de MediaMTX
- ✨ Script de instalación automática
- 📚 Documentación completa en español
- 🐛 Mejor resiliencia en eliminación de archivos

### v1.0.0
- Interfaz web inicial
- Eliminación de segmentos
- Reproductor de vídeo
- Gestión de archivos

## 📜 Licencia

MIT License - Ver LICENSE

## 🤝 Créditos

Desarrollado como herramienta complementaria para [MediaMTX](https://github.com/bluenviron/mediamtx)

---

**¿Necesitas ayuda?** Consulta [INSTRUCCIONES.md](INSTRUCCIONES.md) para una guía completa en español.
