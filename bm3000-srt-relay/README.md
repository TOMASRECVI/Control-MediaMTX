# BM3000 → SRT relay

El encoder BM3000 (Hi3520D, firmware `up_final.rar`) solo emite RTMP/RTSP/HLS —
no tiene SRT nativo (se verificó que el binario no enlaza `libsrt` ni tiene
ninguna cadena `srt_*`, a diferencia del BM3380H que sí lo trae de fábrica).

Este contenedor resuelve eso sin tocar el firmware del equipo: recibe el
stream RTSP/RTMP del BM3000 y lo republica en SRT (modo *caller*/publish)
hacia MediaMTX, copiando el vídeo sin recodificar (`-c copy`, coste de CPU
prácticamente nulo).

## Uso

```bash
cp .env.example .env
# edita .env con la IP del BM3000 y los datos de tu MediaMTX
docker compose up -d
docker compose logs -f
```

Deberías ver algo como `Opening 'srt://...' for writing` seguido de
`frame= ... fps= ... bitrate=...` sin errores de conexión.

## Verificación manual rápida (sin Docker)

Para probar el pull/push a mano antes de levantar el contenedor:

```bash
ffmpeg -re -rtsp_transport tcp -i rtsp://<IP_BM3000>/live \
  -c copy -f mpegts \
  "srt://<IP_MEDIAMTX>:8890?streamid=publish:bm3000&pkt_size=1316"
```

## Notas

- Si el BM3000 y este contenedor comparten la red docker `mediamtx_default`
  con el contenedor real de MediaMTX, puedes usar su nombre de contenedor
  (p. ej. `mediamtx`) en vez de la IP en `MEDIAMTX_HOST`, evitando saltos por
  el host.
- Confirma el puerto SRT real en el `mediamtx.yml` del servidor
  (`srtAddress: :8890` es el valor por defecto de MediaMTX, pero puede estar
  cambiado).
- Si prefieres RTMP como fuente en vez de RTSP, cambia `BM3000_SOURCE_URL` a
  `rtmp://<IP_BM3000>/live/stream` y deja `BM3000_EXTRA_INPUT_FLAGS` vacío.
