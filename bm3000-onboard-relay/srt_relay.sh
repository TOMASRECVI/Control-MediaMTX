#!/bin/sh
# srt_relay.sh -- corre DENTRO del BM3000.
# Coge el RTSP que ya publica "box" en localhost y lo reempaqueta en SRT,
# en uno de dos modos (variable SRT_MODE):
#
#   listener (por defecto) -- el BM3000 abre su propio puerto SRT y
#       espera. Cualquier cliente se conecta a "srt://<IP_BM3000>:<SRT_PORT>".
#       Igual que la opcion "SRT Switch" del BM3380H. Requiere que el
#       BM3000 tenga puerto accesible (sin NAT/CGNAT de por medio).
#
#   caller -- el BM3000 marca hacia un servidor SRT remoto (streamid
#       publish). Para cuando el equipo esta detras de NAT sin forwarding,
#       o el destino es un servidor con IP publica (igual que tus URLs
#       tipo srt://184.174.32.56:44560?streamid=publish/festaro).
#
# Requiere el binario estatico ffmpeg_armv7 (ver Dockerfile de este
# mismo directorio) en la misma carpeta.
#
# Variables (editar aqui o exportarlas antes de llamar al script):
RTSP_LOCAL="${RTSP_LOCAL:-rtsp://127.0.0.1:8554/0}"
FFMPEG_BIN="${FFMPEG_BIN:-/tmp/ffmpeg_armv7}"

SRT_MODE="${SRT_MODE:-listener}"          # listener | caller
SRT_PORT="${SRT_PORT:-9000}"              # usado solo en modo listener

# --- solo para SRT_MODE=caller ---
SRT_REMOTE_HOST="${SRT_REMOTE_HOST:-}"    # ej: 184.174.32.56
SRT_REMOTE_PORT="${SRT_REMOTE_PORT:-}"    # ej: 44560
SRT_STREAMID="${SRT_STREAMID:-publish/bm3000}"
SRT_PASSPHRASE="${SRT_PASSPHRASE:-}"      # vacio = sin cifrado

# --- Guarda de identidad: aborta si esto no es ESTE BM3000 concreto ---
# Evita que el script haga algo si se copia/ejecuta por error en otro
# equipo (otro modelo, otro BM3000, o un PC durante pruebas).

# 1) Familia de hardware: el modulo de kernel del Hi3520D debe estar cargado.
if ! lsmod 2>/dev/null | grep -q '^hi3520D_h264e'; then
    echo "ABORTO: modulo hi3520D_h264e no cargado -- esto no es un Hi3520D." >&2
    exit 1
fi

# 2) Firmware exacto: el "box" en ejecucion debe coincidir con el de la
#    version 2.89 / 3.37W5 (la que corre realmente en 192.168.1.93,
#    confirmada via /get_version). Cambia este hash si flasheas otra.
BOX_MD5_ESPERADO="08480eb6df66ec40ba1f9142a548f64b"
BOX_MD5_REAL="$(md5sum /tmp/box 2>/dev/null | cut -d' ' -f1)"
if [ "$BOX_MD5_REAL" != "$BOX_MD5_ESPERADO" ]; then
    echo "ABORTO: /tmp/box no coincide con el firmware BM3000 esperado (md5=$BOX_MD5_REAL)." >&2
    exit 1
fi

# 3) (Opcional, mas fuerte) Unidad fisica exacta: descomenta y rellena la
#    MAC real de TU BM3000 (cat /sys/class/net/eth0/address en el equipo)
#    para atar el script a ese aparato en concreto y no solo al modelo.
# MAC_ESPERADA="aa:bb:cc:dd:ee:ff"
# MAC_REAL="$(cat /sys/class/net/eth0/address 2>/dev/null)"
# if [ "$MAC_REAL" != "$MAC_ESPERADA" ]; then
#     echo "ABORTO: MAC $MAC_REAL no es la unidad esperada ($MAC_ESPERADA)." >&2
#     exit 1
# fi

# Espera a que "box" tenga su servidor RTSP arriba antes de conectar.
i=0
while [ $i -lt 30 ]; do
    "$FFMPEG_BIN" -v quiet -rtsp_transport tcp -i "$RTSP_LOCAL" -t 1 -f null - 2>/dev/null
    if [ $? -eq 0 ]; then
        break
    fi
    i=$((i+1))
    sleep 1
done

# Construye la URL SRT segun el modo elegido.
if [ "$SRT_MODE" = "caller" ]; then
    if [ -z "$SRT_REMOTE_HOST" ] || [ -z "$SRT_REMOTE_PORT" ]; then
        echo "ABORTO: SRT_MODE=caller necesita SRT_REMOTE_HOST y SRT_REMOTE_PORT." >&2
        exit 1
    fi
    SRT_URL="srt://${SRT_REMOTE_HOST}:${SRT_REMOTE_PORT}?mode=caller&streamid=${SRT_STREAMID}&pkt_size=1316"
    if [ -n "$SRT_PASSPHRASE" ]; then
        SRT_URL="${SRT_URL}&passphrase=${SRT_PASSPHRASE}"
    fi
else
    SRT_URL="srt://0.0.0.0:${SRT_PORT}?mode=listener&pkt_size=1316"
fi

# Bucle de reintento infinito: si el proceso muere, la conexion cae, o
# (en modo caller) el servidor remoto no esta disponible, se relanza
# solo. Esto sustituye al "restart: unless-stopped" que tendria un
# contenedor Docker, pero corriendo dentro del propio encoder.
while true; do
    "$FFMPEG_BIN" -nostdin -loglevel warning \
        -rtsp_transport tcp -i "$RTSP_LOCAL" \
        -c copy -f mpegts \
        "$SRT_URL"
    sleep 3
done
