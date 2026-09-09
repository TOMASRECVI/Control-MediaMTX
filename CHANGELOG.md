# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

## [1.1.0] - 2026-09-06

### ✨ Añadido
- **Script de instalación automática** (`install.sh`)
  - Detecta contenedor MediaMTX automáticamente
  - Configura red y volúmenes correctamente
  - Prueba conectividad después de iniciar
  
- **Endpoint de diagnóstico** (`/api/debug/segment/<path>/<start>`)
  - Verifica estado actual de un segmento
  - Útil para debugging de problemas de eliminación

- **Script de diagnóstico** (`debug_api.sh`)
  - Inspecciona configuración de MediaMTX
  - Lista rutas activas y grabaciones
  - Prueba conectividad de la API

- **Documentación completa en español**
  - Guía de instalación paso a paso
  - Solución de problemas
  - Referencia de comandos
  
- **Mejor manejo de errores 400 de MediaMTX**
  - Si se elimina el archivo pero MediaMTX devuelve error, se considera éxito parcial
  - Mensaje informativo diferenciado
  - Logs mejorados para debugging

### 🐛 Corregido
- Error al eliminar último archivo de una ruta
- Mejor manejo de timestamps con microsegundos
- Ruta API correcta en peticiones DELETE
- Validación mejorada de rutas (path traversal)

### 📚 Documentación
- Nuevo archivo `README.md` con descripción general
- Nuevo archivo `INSTRUCCIONES.md` con guía completa
- Nuevo archivo `CHANGELOG.md` (este archivo)

### 🔧 Técnico
- Mejores logs con información de contexto
- Manejo diferenciado de errores HTTP (400, 502, etc.)
- Resiliencia mejorada en operaciones de archivo

---

## [1.0.0] - 2026-09-05

### ✨ Añadido
- **Interfaz web completa**
  - Visualización de grabaciones por ruta
  - Pestaña de segmentos y archivos en disco
  - Selector de rutas con indicador de grabación

- **Reproductor de vídeo**
  - Reproducción HTML5 integrada
  - Soporte para seek con Range requests
  - Modal para visualización

- **Eliminación de segmentos**
  - Eliminar individual con confirmación
  - Selección múltiple para borrado por lotes
  - Eliminar todos los segmentos de una ruta

- **Gestión de archivos**
  - Listar archivos .mp4 en el volumen
  - Eliminar archivos específicos del disco
  - Información de tamaño de archivo

- **Configuración de grabación**
  - Activar/desactivar grabación por ruta
  - Configurar borrado automático (recordDeleteAfter)
  - Validación de duraciones

- **API REST completa**
  - Endpoints para listar, crear, modificar y eliminar
  - Soporte CORS habilitado
  - Timeout configurable

- **Frontend responsivo**
  - Diseño adaptable (desktop, tablet, móvil)
  - Tema oscuro
  - Animaciones suave
  - Notificaciones toast

- **Docker ready**
  - Dockerfile optimizado
  - docker-compose para despliegue fácil
  - Volúmenes persistentes

---

## Notas de Versión

### Cómo instalar cambios

Después de cualquier cambio, reinicia el contenedor:

```bash
cd mediamtx-manager
docker compose down
docker compose up -d --build
```

### Historial de problemas solucionados

- **Problema**: Archivos no se borraban del disco
  - **Causa**: La ruta del volumen no estaba correctamente montada
  - **Solución**: Actualización de docker-compose.yml con ruta correcta

- **Problema**: Error 400 al eliminar segmentos
  - **Causa**: Segmento siendo grabado o ya eliminado en MediaMTX
  - **Solución**: Manejo resiliente, se accepta eliminación parcial del archivo

- **Problema**: Interfaz no conectaba con MediaMTX
  - **Causa**: Nombre del contenedor incorrecto en MEDIAMTX_API
  - **Solución**: Script de instalación detecta automáticamente

- **Problema**: Archivos con microsegundos no se encontraban
  - **Causa**: Patrón regex solo buscaba segundos
  - **Solución**: Actualización de regex para soportar microsegundos

---

## Por hacer (Roadmap)

- [ ] Autenticación (login básico)
- [ ] Exportación de informes
- [ ] Webhooks para eventos
- [ ] Backup automático
- [ ] Panel de estadísticas
- [ ] API de línea de comandos (CLI)
- [ ] Almacenamiento en caché de listados
- [ ] Compresión de vídeos antiguos
- [ ] Integración con S3/almacenamiento en nube

---

**Última actualización**: 2026-09-06
