# 🔄 Actualización: Sincronización de Comportamiento - Archivos en Disco

## 📝 Resumen

Se ha actualizado la pantalla de "Archivos en disco" para que el comportamiento de borrado sea **completamente idéntico** al de la pantalla "Segmentos".

## 🔧 Cambios Realizados

### Funciones Actualizadas en `templates/index.html`

#### 1. `confirmDeleteFile()` (Borrado Individual)
**Antes:**
- Usaba `showModal()` con callback
- Delay: 300ms
- Refresco solo de la pestaña actual

**Ahora:**
- ✅ Usa `confirm()` nativo (como Segmentos)
- ✅ Delay: 500ms (consistente con Segmentos)
- ✅ Refresca AMBAS pestañas: `loadFilesTab()` + `loadRecordings()`
- ✅ En caso de error: espera 1000ms antes de refrescar
- ✅ Logs consistentes en consola

#### 2. `deleteSelectedFiles()` (Borrado Múltiple)
**Antes:**
- Usaba `showModal()` con callback
- Delay: 300ms  
- Refresco solo de la pestaña actual

**Ahora:**
- ✅ Usa `confirm()` nativo (como Segmentos)
- ✅ Delay: 500ms (consistente)
- ✅ Refresca AMBAS pestañas: `loadFilesTab()` + `loadRecordings()`
- ✅ En caso de error: espera 1000ms antes de refrescar
- ✅ Logs consistentes en consola

#### 3. `confirmDeleteAllFiles()` (Borrado de Ruta Completa)
**Antes:**
- Usaba `showModal()` con callback
- Delay: ninguno (inmediato)
- Refresco sin delay especificado

**Ahora:**
- ✅ Usa `confirm()` nativo (como Segmentos)
- ✅ Delay: 500ms (consistente)
- ✅ Refresca AMBAS pestañas: `loadFilesTab()` + `loadRecordings()`
- ✅ En caso de error: espera 1000ms antes de refrescar
- ✅ Logs consistentes en consola

---

## ✨ Comportamiento Resultante

### Flujo de Eliminación (Todos los casos idénticos)

```
1. Usuario hace click en "Eliminar"
   ↓
2. Aparece confirm() nativo
   ↓
3. Usuario confirma ✓
   ↓
4. Se ejecuta API call: DELETE /api/recordings/files/delete
   ↓
5. Toast de éxito o error aparece
   ↓
6. ESPERA 500ms (si éxito) o 1000ms (si error)
   ↓
7. Recarga AMBAS pestañas:
   - loadFilesTab() - Actualiza "Archivos en disco"
   - loadRecordings() - Actualiza "Segmentos"
   ↓
8. Interfaz refleja cambios en tiempo real
```

### Comparativa: Antes vs Ahora

| Aspecto | v1.1.0 | v1.2.0+ |
|---------|--------|---------|
| **Dialogo** | showModal() | confirm() |
| **Delay éxito** | 300ms | 500ms |
| **Delay error** | 1000ms | 1000ms |
| **Refresco** | 1 pestaña | 2 pestañas |
| **Sincronización** | ❌ Parcial | ✅ Completa |
| **Logs** | Mínimos | ✅ Detallados |
| **Consistencia** | ❌ Variable | ✅ Uniforme |

---

## 🧪 Casos de Prueba

### Prueba 1: Borrar archivo individual
```
1. Ir a pestaña "Archivos en disco"
2. Hacer click en botón "Eliminar" de cualquier archivo
3. Confirmar en el dialogo
   ✓ Archivo desaparece
   ✓ Tabla de "Segmentos" también se actualiza
   ✓ Si el segmento solo tenia este archivo, aparece como "<No grabado>"
```

### Prueba 2: Borrar múltiples archivos
```
1. Ir a pestaña "Archivos en disco"
2. Seleccionar varios archivos (checkboxes)
3. Click en "Eliminar X seleccionado(s)"
4. Confirmar
   ✓ Todos desaparecen del listado
   ✓ Tabla "Segmentos" se recarga inmediatamente
   ✓ Segmentos sin archivos se muestran con "<No grabado>"
```

### Prueba 3: Borrar todos los archivos de una ruta
```
1. Ir a pestaña "Archivos en disco"
2. Buscar botón "Eliminar 12 archivos" (ejemplo)
3. Click en ese botón
4. Confirmar
   ✓ Desaparecen todos los archivos de la ruta
   ✓ Pestaña "Segmentos" muestra esa ruta como sin grabaciones
   ✓ La ruta permanece pero sin archivos
```

### Prueba 4: Confirmar sincronización
```
1. Tener ambas pestañas visibles (abrir en dos ventanas o usar split-screen)
2. Borrar un archivo desde "Archivos en disco"
3. Confirmar eliminación
   ✓ Archivo desaparece de "Archivos en disco"
   ✓ Segmento desaparece de "Segmentos" (o muestra "<No grabado>")
   ✓ Ambas actualizaciones ocurren al mismo tiempo (~500ms)
```

---

## 📊 Impacto Técnico

### Cambios en el Código

**Patrones Mejorados:**
```javascript
// ANTES (showModal con callback)
showModal('Titulo', 'Mensaje', async () => {
  try { await api(...); } 
  catch (e) { toast(e.message); }
});

// AHORA (confirm + IIFE async)
if (!confirm('Mensaje')) return;
(async () => {
  try { await api(...); } 
  catch (e) { toast(e.message); }
})();
```

**Ventajas:**
- ✅ Ejecución más predecible
- ✅ Mejor manejo de errores
- ✅ Logs consistentes
- ✅ Delays uniformes
- ✅ Sintaxis más clara y menos anidada

### Funciones Afectadas

1. `confirmDeleteFile()` - Línea 627
2. `confirmDeleteAllFiles()` - Línea 654  
3. `deleteSelectedFiles()` - Línea 671

**Total de cambios:** ~50 líneas de código mejorado

---

## 🔄 Sincronización Entre Pestañas

### Antes (v1.1.0)
```
Usuario borra en "Archivos en disco"
         ↓
     [500ms delay]
         ↓
Recarga solo "Archivos en disco"
         ↓
Usuario tiene que cambiar a "Segmentos" manualmente
para ver los cambios (¡Inconsistencia!)
```

### Ahora (v1.2.0+)
```
Usuario borra en "Archivos en disco"
         ↓
     [500ms delay]
         ↓
Recarga automáticamente AMBAS:
- "Archivos en disco"
- "Segmentos"
         ↓
Ambas pestañas en sincronización perfecta (✓)
```

---

## 🚀 Despliegue

### Para activar estos cambios:
```bash
cd /home/user/mediamtx-manager
docker compose down
docker compose up -d --build
```

### Verificación:
```bash
# 1. Accede a http://127.0.0.1:8080
# 2. Ve a pestaña "Archivos en disco"
# 3. Prueba borrar un archivo
# 4. Abre consola (F12) y verifica logs:
#    - "Waiting for MediaMTX to refresh..."
#    - "Refreshing files tab after error..."
# 5. Ambas pestañas se actualizan automáticamente
```

---

## ⚠️ Nota Importante

Los cambios en esta actualización **NO afectan a:**
- ✅ Los datos guardados
- ✅ La configuración de MediaMTX
- ✅ Los archivos de grabación (solo cómo se muestran)
- ✅ La API backend

Solo mejoran la **experiencia del usuario** haciendo que:
1. El comportamiento sea predecible
2. Las pestañas se sincronicen automáticamente
3. Los errores se manejen graciosamente
4. Los delays sean uniformes y calculados

---

## 🎯 Resultado Final

✅ **Comportamiento unificado:** Todas las operaciones de borrado funcionan idénticamente
✅ **Sincronización perfecta:** Las dos pestañas siempre muestran datos consistentes
✅ **Mejor UX:** El usuario no tiene que actualizar manualmente
✅ **Manejo robusto de errores:** Los retrasos dan tiempo a MediaMTX para procesar

---

**Versión**: 1.2.0+  
**Fecha**: 2026-09-07  
**Estado**: ✅ Implementado y probado
