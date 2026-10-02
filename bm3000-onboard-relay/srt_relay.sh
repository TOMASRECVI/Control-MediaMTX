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
# mismo directorio). Vive en /box/ (particion persistente JFFS2), NO
# dentro del paquete obj.rar -- el flash del BM3000 solo tiene ~28MB y
# no hay sitio para duplicar el archivo entero durante una actualizacion
# si ffmpeg_armv7 (4+MB) va empaquetado dentro. Este propio script
# tambien vive en /box/srt_relay.sh por el mismo motivo.
#
# CONFIGURACION: si existe /box/srt_relay.conf (particion persistente
# JFFS2, no /tmp) se carga aqui. Cambiar servidor/puerto/streamid en el
# futuro es solo editar ese fichero de texto y reiniciar -- NO hace
# falta volver a montar/reflashear obj.rar para nada. Ejemplo de
# contenido de /box/srt_relay.conf:
#   SRT_MODE=caller
#   SRT_REMOTE_HOST=192.168.1.147
#   SRT_REMOTE_PORT=8890
#   SRT_STREAMID=publish:bm3000
[ -f /box/srt_relay.conf ] && . /box/srt_relay.conf

# Variables (si no las puso /box/srt_relay.conf, o para pruebas manuales
# exportandolas antes de llamar al script):
RTSP_LOCAL="${RTSP_LOCAL:-rtsp://127.0.0.1:8554/0}"
FFMPEG_BIN="${FFMPEG_BIN:-/box/ffmpeg_armv7}"

SRT_MODE="${SRT_MODE:-listener}"          # listener | caller
SRT_PORT="${SRT_PORT:-9000}"              # usado solo en modo listener

# --- solo para SRT_MODE=caller ---
SRT_REMOTE_HOST="${SRT_REMOTE_HOST:-}"    # ej: 184.174.32.56
SRT_REMOTE_PORT="${SRT_REMOTE_PORT:-}"    # ej: 44560
SRT_STREAMID="${SRT_STREAMID:-publish:bm3000}"          # MediaMTX usa ":" (confirmado funcionando)
SRT_PASSPHRASE="${SRT_PASSPHRASE:-}"      # vacio = sin cifrado

# --- Guarda de identidad: aborta si esto no es ESTE BM3000 concreto ---
# Evita que el script haga algo si se copia/ejecuta por error en otro
# equipo (otro modelo, otro BM3000, o un PC durante pruebas).

# 1) Familia de hardware: el modulo de kernel del Hi3520D debe estar cargado.
if ! lsmod 2>/dev/null | grep -q '^hi3520D_h264e'; then
    echo "ABORTO: modulo hi3520D_h264e no cargado -- esto no es un Hi3520D." >&2
    exit 1
fi

# 2) Firmware conocido: el "box" en ejecucion debe coincidir con alguno
#    de los equipos BM3000 ya verificados manualmente por telnet. Anade
#    aqui el md5sum de /tmp/box de cada unidad nueva que se despliegue.
BOX_MD5_CONOCIDOS="08480eb6df66ec40ba1f9142a548f64b 09d9e4e225758d746ef4c24982cc745d 6e020576f6039e0f3c83046d07c99642"
BOX_MD5_REAL="$(md5sum /tmp/box 2>/dev/null | cut -d' ' -f1)"
case " $BOX_MD5_CONOCIDOS " in
    *" $BOX_MD5_REAL "*) ;;
    *)
        echo "ABORTO: /tmp/box no coincide con ningun firmware BM3000 conocido (md5=$BOX_MD5_REAL)." >&2
        exit 1
        ;;
esac

# 3) (Opcional, mas fuerte) Unidad fisica exacta: descomenta y rellena la
#    MAC real de TU BM3000 (cat /sys/class/net/eth0/address en el equipo)
#    para atar el script a ese aparato en concreto y no solo al modelo.
# MAC_ESPERADA="aa:bb:cc:dd:ee:ff"
# MAC_REAL="$(cat /sys/class/net/eth0/address 2>/dev/null)"
# if [ "$MAC_REAL" != "$MAC_ESPERADA" ]; then
#     echo "ABORTO: MAC $MAC_REAL no es la unidad esperada ($MAC_ESPERADA)." >&2
#     exit 1
# fi

# Panel web de configuracion (puerto PANEL_PORT, 8090 por defecto, ver config.cgi). Solo arranca
# si existe /box/httpd.conf (con la linea "/:usuario:contrasena" para
# autenticacion basica) -- sin ese fichero no se expone nada, para no
# dejar un panel de escritura abierto por defecto.
if [ -f /box/httpd.conf ] && [ -x /box/www/cgi-bin/config.cgi ]; then
    PANEL_PORT="${PANEL_PORT:-8090}"
    ps | grep -q "[h]ttpd -p $PANEL_PORT" || busybox httpd -p "$PANEL_PORT" -h /box/www -c /box/httpd.conf
fi

# Timeout (en microsegundos) para operaciones de socket RTSP/IO. Sin
# esto, si "box" corta el RTSP interno (p.ej. al desactivar el switch
# RTSP en la web) ffmpeg se queda colgado esperando datos de una
# conexion muerta en vez de fallar -- y el bucle de reintento de mas
# abajo nunca llega a relanzarlo, ni siquiera cuando el RTSP vuelve.
# Con 5s se vio en pruebas reales que a veces corta la propia fase de
# deteccion de codec al reconectar ("Could not find codec parameters")
# justo antes de estabilizarse, entrando en un bucle de reconexion
# fallida. 10s da mas margen a esa fase sin perder la proteccion contra
# el cuelgue original.
IO_TIMEOUT_US="${IO_TIMEOUT_US:-10000000}"

# Espera a que "box" tenga su servidor RTSP arriba antes de conectar.
# (usa "-f mpegts" a /dev/null en vez de "-f null": este build no incluye
# el muxer "null", solo mpegts/rtsp -- confirmado en pruebas reales).
i=0
while [ $i -lt 30 ]; do
    "$FFMPEG_BIN" -nostdin -v quiet -rtsp_transport tcp -timeout "$IO_TIMEOUT_US" -i "$RTSP_LOCAL" -t 1 -c copy -f mpegts /dev/null 2>/dev/null
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
# contenedor Docker, pero corriendo dentro del propio encoder. Los
# timeouts de arriba son los que garantizan que "muere" pase de verdad
# cuando el RTSP se corta, en vez de quedarse colgado para siempre.
while true; do
    "$FFMPEG_BIN" -nostdin -loglevel warning \
        -rtsp_transport tcp -timeout "$IO_TIMEOUT_US" -i "$RTSP_LOCAL" \
        -c copy -f mpegts \
        "$SRT_URL"
    sleep 3
done
