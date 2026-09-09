# 🔧 Diagnóstico Real y Solución Aplicada (2026-09-08)

Diagnóstico hecho conectando directamente al servidor (192.168.1.147) por SSH e
inspeccionando ambos contenedores en vivo. Resumen de lo encontrado y lo arreglado.

## ❌ Causa raíz #1: mediamtx-manager y mediamtx-mediamtx-1 no se veían

**No era un problema de red Docker.** Ambos contenedores ya estaban correctamente
unidos a la misma red `mediamtx_default` (172.19.0.2 y 172.19.0.3). El `docker-compose.yml`
estaba bien.

**La causa real** estaba en `/var/lib/docker/volumes/mediamtx_data/_data/mediamtx.yml`:

```yaml
api: false   # ← La API de control de MediaMTX estaba DESHABILITADA
```

Con `api: false`, MediaMTX ni siquiera abre el puerto 9997, así que cualquier intento
de conexión (desde el manager o desde cualquier otro sitio) recibía **"Connection refused"**.
Esto explica el 100% de los errores 502 en la interfaz web (`/api/health`, `/api/paths/list`,
`/api/recordings`, etc.), independientemente de si el stream real era RTMP o SRT.

**Fix aplicado**: `api: false` → `api: true`.

## ❌ Causa raíz #2: tras habilitar la API, devolvía 401 "authentication error"

En la misma configuración, el usuario administrador de la API estaba restringido así:

```yaml
- user: any
  pass:
  ips: ["127.0.0.1", "::1"]      # ← solo localhost
  permissions:
    - action: api
    - action: metrics
    - action: pprof
```

mediamtx-manager llega desde la IP del contenedor (172.19.0.2), que no es `127.0.0.1`
ni `::1`, así que la API rechazaba la petición con 401.

**Fix aplicado**: se amplió la lista de IPs permitidas para incluir el rango de redes
Docker por defecto:

```yaml
ips: ["127.0.0.1", "::1", "172.16.0.0/12"]
```

## ✅ Resultado tras aplicar ambos fixes

```
GET /api/health      -> 200 {"mediamtx": true, "status": "ok"}
GET /api/paths/list  -> 200 con los streams activos (incluyendo los de SRT)
```

Se hizo backup del archivo original antes de tocarlo:
`/var/lib/docker/volumes/mediamtx_data/_data/mediamtx.yml.bak`

---

## ❌ Sobre "SRT no publica pero RTMP sí"

**Revisando los logs de MediaMTX, esto no era cierto: SRT sí estaba publicando
correctamente.** Se encontraron múltiples eventos:

```
INF [SRT] [conn 104.28.161.253:56881] is publishing to path 'fest'
INF [SRT] [conn 192.168.1.15:58810] is publishing to path 'prueba'
INF [SRT] [conn 88.28.165.220:31291] is publishing to path 'camara'
```

Lo que realmente se veía (y generaba la impresión de que "no funcionaba") eran
mensajes de **lectores**, no de publicadores, fallando con:

```
INF [SRT] [conn ...] closed: no stream is available on path 'camara'
INF [SRT] [conn ...] closed: no stream is available on path 'prueba1'
```

Dos causas distintas mezcladas ahí:

1. **`camara`**: el publisher de ese path se conecta y desconecta de forma intermitente
   (stream inestable en origen). Cuando no hay publisher conectado en ese instante,
   cualquier intento de lectura falla con "no stream is available" — esto es el
   comportamiento normal de MediaMTX, no un bug.
2. **`prueba1`**: nunca hubo ningún publisher a un path llamado `prueba1`. El publisher
   real está enviando a `prueba` (sin el "1"). Quien intenta **leer** `prueba1` está
   usando un nombre de path equivocado — hay que corregirlo en el lado del reproductor/cliente.

Como además la API estaba caída (causa raíz #1), la interfaz web de mediamtx-manager
no podía mostrar nada de esto — ni paths SRT ni RTMP — reforzando la sensación de que
"SRT no funciona". Ahora que la API responde, en `/api/paths/list` ya se ven los streams
SRT activos (`fest`, `prueba`) con `bytesReceived` creciendo.

**Acción recomendada para el usuario**: verificar en el software/dispositivo que
publica hacia el path `camara` por qué se desconecta de forma intermitente (ej. red
inestable, timeout del encoder), y corregir el nombre de path en quien intenta leer
`prueba1` para que apunte a `prueba`.

---

## 📋 Verificación rápida (para el futuro)

```bash
# Health del manager
curl http://192.168.1.147:8080/api/health

# Paths activos (deben aparecer los streams SRT y RTMP en vivo)
curl http://192.168.1.147:8080/api/paths/list

# Ver si la API de MediaMTX está habilitada
grep '^api:' /var/lib/docker/volumes/mediamtx_data/_data/mediamtx.yml

# Ver las IPs permitidas para la API
grep -A3 'action: api' /var/lib/docker/volumes/mediamtx_data/_data/mediamtx.yml
```

Si en el futuro se vuelve a editar `mediamtx.yml` (por ejemplo regenerándolo desde cero
o restaurando un backup viejo), revisar que **`api: true`** y que el bloque de IPs de la
acción `api` incluya la red Docker (`172.16.0.0/12` cubre el rango por defecto de Docker),
o el manager volverá a fallar con 401/Connection refused.
