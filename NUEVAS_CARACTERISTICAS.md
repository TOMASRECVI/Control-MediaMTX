# ✨ Nuevas Características v1.2.0

## 🎥 Visor de Emisión en Vivo

### Descripción
Se agregó una nueva sección en la parte superior de la interfaz que permite ver streams en vivo de todas las cámaras/rutas activas en MediaMTX.

### Características
- **Listado de cámaras**: Muestra todas las rutas disponibles organizadas en una grilla
- **Indicadores de estado**: 
  - 🟢 Verde = Stream activo/en vivo
  - ⚫ Gris = Inactivo
- **Reproductor integrado**: 
  - Soporte para HLS (protocolo de streaming)
  - Controles de reproducción (play, pausa, volumen, pantalla completa)
  - Resolución adaptable
- **Selección intuitiva**: Click en cámara para reproducir, click nuevamente para cerrar

### Cómo usar
1. Accede a http://127.0.0.1:8080
2. Verás la sección "📹 Emisión en Vivo" en la parte superior
3. Click en cualquier cámara para ver su stream
4. Usa los controles de vídeo para pausa, volumen, etc.

### Requisitos técnicos
- MediaMTX debe estar configurado para servir HLS
- Las rutas deben estar activas y transmitiendo
- Conexión de red suficiente al servidor

---

## ⏱️ Campos de Fin y Duración en la Tabla de Grabaciones

### Descripción
La tabla de segmentos ahora muestra automáticamente la hora de finalización y la duración de cada grabación.

### Nuevos Campos
| Campo | Descripción | Ejemplo |
|-------|------------|---------|
| **Fin** | Hora exacta de finalización del segmento | 06/09/2026 16:45:32 |
| **Duración** | Duración total del segmento | 00:15:32 |

### Cálculo Automático
- **Fin**: Se calcula a partir de `start + duration`
- **Duración**: Formato HH:MM:SS para fácil lectura
- **Actualización**: Se recalcula cada vez que se refresca la lista

### Ejemplos
- Segmento de 30 segundos: 00:00:30
- Segmento de 2 minutos: 00:02:00
- Segmento de 1 hora: 01:00:00

---

## 🔧 Cambios Técnicos

### Backend (app.py)

#### Mejora en `/api/recordings`
```python
# Ahora retorna información extendida de cada segmento:
{
    "start": "2026-09-06T16:30:16Z",
    "end": "2026-09-06T16:45:48Z",           # ✨ NUEVO
    "durationSeconds": 932,                    # ✨ NUEVO
    "durationFormatted": "00:15:32"            # ✨ NUEVO
}
```

#### Nuevos Endpoints
```
GET /api/paths/list
  - Retorna lista de rutas activas
  - Incluye estado y protocolos disponibles

GET /api/stream/<name>
  - Sirve stream en vivo de una ruta
  - Soporta redirección a HLS
  - Fallback a alternativas si HLS no disponible
```

#### Nueva Función Utilitaria
```python
def format_duration(seconds):
    """
    Convierte segundos a formato legible
    
    Entrada: 932
    Salida: "00:15:32"
    """
```

### Frontend (index.html)

#### Nueva Sección de UI
```html
<div class="card">
  <h2>📹 Emisión en Vivo</h2>
  <div id="liveStreamContent">
    <!-- Selector de cámaras -->
    <!-- Reproductor de vídeo -->
  </div>
</div>
```

#### Nuevos Estilos CSS
```css
.stream-selector         /* Grid de selección de cámaras */
.stream-item            /* Botón/tarjeta de cámara */
.stream-indicator       /* Indicador de estado visual */
.stream-player          /* Contenedor del reproductor */
.stream-controls        /* Botones de control */
```

#### Nuevas Funciones JavaScript
```javascript
loadLiveStreams()
  - Carga lista de streams disponibles
  - Renderiza interfaz de selección
  - Autodetecta estado de cada stream

selectStream(streamName)
  - Selecciona/deselecciona un stream
  - Actualiza reproductor
  - Recarga interfaz
```

#### Actualización de Tabla
```javascript
// Antes:
const duration = formatDuration(seg.start, seg.end);

// Ahora:
const duration = seg.durationFormatted || formatDuration(seg.start, seg.end);
// Usa valor precalculado del backend con fallback
```

---

## 📊 Tabla de Grabaciones Actualizada

### Estructura Nueva
```
┌─────┬──────────────────┬──────────────────┬──────────────┬─────────┬──────────┐
│ Sel │ Inicio           │ Fin              │ Duración     │ Tamaño  │ Acciones │
├─────┼──────────────────┼──────────────────┼──────────────┼─────────┼──────────┤
│ ☐   │ 06/09/2026 16:30 │ 06/09/2026 16:45 │ 00:15:32     │ 234 MB  │ Ver 🎬   │
│     │                  │                  │              │         │ Eliminar │
└─────┴──────────────────┴──────────────────┴──────────────┴─────────┴──────────┘
```

### Funciones por Columna
- **Sel**: Checkbox para selección múltiple
- **Inicio**: Hora de inicio (formateada en zona horaria local)
- **Fin**: ✨ NUEVO - Hora de finalización exacta
- **Duración**: ✨ NUEVO - Formato HH:MM:SS legible
- **Tamaño**: Tamaño del archivo de vídeo
- **Acciones**: Botones para ver o eliminar

---

## 🎨 Cambios Visuales

### Antes (v1.1.0)
```
📹 Emisión en Vivo
├─ No había sección de stream en vivo
└─ Interfaz solo mostraba grabaciones

📋 Grabaciones
├─ Tabla: Inicio | Tamaño | Acciones
└─ Sin información de fin/duración
```

### Ahora (v1.2.0)
```
📹 Emisión en Vivo
├─ Selector de cámaras con estado
├─ Reproductor de vídeo integrado
└─ Actualización en tiempo real

📋 Grabaciones
├─ Tabla: Inicio | Fin ✨ | Duración ✨ | Tamaño | Acciones
└─ Información completa de cada segmento
```

---

## ⚙️ Configuración

### Requisitos de MediaMTX
Para que funcione el visor de stream, MediaMTX debe tener:

```yaml
# mediamtx.yml
paths:
  camara:
    source: rtsp://...
    record: yes
    # HLS debe estar habilitado
    hls: yes
```

### Protocolo HLS
- **Formato**: HTTP Live Streaming
- **Compatibilidad**: Todos los navegadores modernos
- **Ventajas**: 
  - No requiere plugins
  - Compatible con IPv6
  - Streaming adaptable
- **Desventajas**:
  - Latencia ~10 segundos
  - Requiere servidor HTTP

---

## 🔄 Integración con Funcionalidades Existentes

### Flujo de Trabajo Típico
1. **Ver stream en vivo** → Sección superior
2. **Revisar grabaciones** → Tabla con duración exacta
3. **Reproducir segmento** → Botón "Ver"
4. **Eliminar segmento** → Botón "Eliminar"

### Independencia de Módulos
- Visor de stream: Totalmente independiente
- Tabla de duración: No afecta otras funciones
- Compatibilidad: 100% backward-compatible

---

## 📈 Mejoras Futuras (Roadmap)

Posibles extensiones en versiones futuras:

- [ ] Grabación de snapshots del stream
- [ ] Múltiples visualizadores simultáneos
- [ ] Análisis de duración de segmentos
- [ ] Alertas cuando stream se desconecta
- [ ] Estadísticas de uptime por cámara
- [ ] Zoom y pan en el reproductor
- [ ] Grabación de clips desde stream vivo
- [ ] Sincronización de múltiples cámaras

---

## 🐛 Notas de Compatibilidad

### Navegadores Soportados
- Chrome/Chromium 60+
- Firefox 60+
- Safari 11+
- Edge 79+

### Sistemas Operativos
- Linux (servidor)
- Windows/Mac/Linux (cliente)

### Versiones de MediaMTX
- 1.0+
- Testeado en versión 1.3+

---

## 📝 Notas de Actualización

### De v1.1.0 a v1.2.0
```bash
# Actualizar a la nueva versión
cd /home/user/mediamtx-manager
docker compose down
docker compose up -d --build

# Ya estará disponible el visor de stream
# y los campos de fin/duración
```

### Cambios que NO requieren acción
- Los datos anteriores se mantienen
- No se elimina ningún segmento
- La tabla sigue funcionando igual

### Cambios que SÍ afectan
- Columna "Duración" ahora usa datos del backend (más precisión)
- Aparece nueva columna "Fin"
- Nueva sección de stream en vivo

---

## ✅ Verificación

Para verificar que todo funciona:

1. **Stream en vivo**:
   - Abre http://127.0.0.1:8080
   - Verifica que aparezca "📹 Emisión en Vivo"
   - Click en una cámara
   - Debe mostrar reproductor

2. **Duración en tabla**:
   - Abre pestaña "Segmentos"
   - Verifica que todas las columnas tengan datos
   - Duración debe estar en formato HH:MM:SS

3. **Logs**:
   ```bash
   docker logs mediamtx-manager --tail=50
   ```
   - No debe haber errores de Python
   - Debe haber logs de `/api/paths/list`

---

**Versión**: 1.2.0  
**Fecha**: 2026-09-06  
**Estado**: ✅ En producción
