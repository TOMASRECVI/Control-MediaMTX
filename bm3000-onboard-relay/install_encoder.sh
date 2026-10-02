#!/bin/sh
# install_encoder.sh -- instala el relay SRT y el panel web en un BM3000.
# Se ejecuta DENTRO del encoder (por telnet). Es idempotente: se puede
# repetir para actualizar scripts sin perder la configuracion existente.
#
# Uso:
#   wget http://<IP_PC>:8000/install_encoder.sh -O /tmp/install.sh
#   sh /tmp/install.sh <IP_PC>:8000 <streamid> [servidor] [puerto] [pass_panel]
#
#   IP_PC:8000   donde se sirven los ficheros (node serve_dir.js ... 8000)
#   streamid     nombre del stream, p.ej. bm3000_5  (se guarda "publish:<nombre>")
#   servidor     servidor SRT/MediaMTX (por defecto 192.168.1.147)
#   puerto       puerto SRT del servidor (por defecto 8890)
#   pass_panel   contrasena del panel web, usuario "admin" (por defecto admin);
#                solo letras, numeros y . _ -   (el telnet descarta la ñ)
#
# Que hace:
#   1. comprueba que es un Hi3520D y que hay espacio libre
#   2. descarga ffmpeg_armv7 (si falta), srt_relay.sh y el panel (config.cgi)
#   3. crea srt_relay.conf y httpd.conf SOLO si no existen (no pisa nada)
#   4. engancha el arranque en /box/load (copia en load.orig), de modo que el
#      relay y el panel sobreviven a los cambios de firmware (obj.rar)
#   5. arranca el relay ahora, sin reiniciar
#
# Variables opcionales: BOX_DIR (por defecto /box), FORCE_FFMPEG=1 para
# volver a descargar el binario, SKIP_CHECKS=1 (solo pruebas fuera del equipo).

BOX_DIR="${BOX_DIR:-/box}"
BASE="$1"; SID_NAME="$2"
SRV="${3:-192.168.1.147}"; PORT="${4:-8890}"; PPASS="${5:-admin}"

die() { echo "ERROR: $*" >&2; exit 1; }
ok()  { echo "  OK  $*"; }

[ -n "$BASE" ] && [ -n "$SID_NAME" ] || {
    echo "Uso: sh install.sh <IP_PC>:8000 <streamid> [servidor] [puerto] [pass_panel]"
    echo "Ej.: sh install.sh 192.168.1.16:8000 bm3000_5 192.168.1.147 8890 admin"
    exit 1
}
case "$BASE$SID_NAME$SRV$PORT$PPASS" in
    *[!A-Za-z0-9._:/-]*) die "caracteres no permitidos (solo letras, numeros y . _ : / -)";;
esac
case "$PORT" in *[!0-9]*) die "el puerto debe ser numerico";; esac
[ ${#PPASS} -ge 5 ] || die "la contrasena del panel necesita al menos 5 caracteres"

echo "== 1/5 Comprobaciones =="
if [ "${SKIP_CHECKS:-0}" != "1" ]; then
    lsmod 2>/dev/null | grep -q '^hi3520D_h264e' || die "no es un Hi3520D (modulo hi3520D_h264e no cargado): ffmpeg_armv7 solo vale para ese chip"
    ok "chip Hi3520D"
    [ -d "$BOX_DIR" ] || die "no existe $BOX_DIR"
    [ -f "$BOX_DIR/load" ] || die "no existe $BOX_DIR/load (no parece un BM3000)"
    FREE_KB="$(df -k "$BOX_DIR" | tail -1 | awk '{print $4}')"
    NEED_KB=900
    [ -f "$BOX_DIR/ffmpeg_armv7" ] && [ "${FORCE_FFMPEG:-0}" != "1" ] || NEED_KB=5200
    [ "$FREE_KB" -ge "$NEED_KB" ] 2>/dev/null || die "poco espacio libre en $BOX_DIR: ${FREE_KB}K (hacen falta ${NEED_KB}K). Borra backups viejos (obj_new.rar, *.orig)"
    ok "espacio libre: ${FREE_KB}K"
fi

fetch() {  # fetch <fichero_remoto> <destino> <tamano_minimo>
    wget "http://$BASE/$1" -O "$2.tmp" >/dev/null 2>&1 || { rm -f "$2.tmp"; die "no se pudo descargar $1 de http://$BASE (comprueba que el servidor de ficheros esta activo)"; }
    SZ="$(wc -c < "$2.tmp")"
    [ "$SZ" -ge "$3" ] || { rm -f "$2.tmp"; die "$1 descargado incompleto ($SZ bytes)"; }
    mv -f "$2.tmp" "$2" || die "no se pudo escribir $2"
    chmod 777 "$2"
    ok "$1 ($SZ bytes)"
}

echo "== 2/5 Descarga de ficheros =="
if [ ! -f "$BOX_DIR/ffmpeg_armv7" ] || [ "${FORCE_FFMPEG:-0}" = "1" ]; then
    fetch ffmpeg_armv7 "$BOX_DIR/ffmpeg_armv7" 1000000
else
    ok "ffmpeg_armv7 ya instalado (FORCE_FFMPEG=1 para sustituirlo)"
fi
fetch srt_relay.sh "$BOX_DIR/srt_relay.sh" 3000
mkdir -p "$BOX_DIR/www/cgi-bin" || die "no se pudo crear $BOX_DIR/www/cgi-bin"
fetch config.cgi "$BOX_DIR/www/cgi-bin/config.cgi" 3000
echo '<meta http-equiv="refresh" content="0;url=/cgi-bin/config.cgi">' > "$BOX_DIR/www/index.html"

echo "== 3/5 Configuracion (sin pisar la existente) =="
if [ -f "$BOX_DIR/srt_relay.conf" ]; then
    ok "srt_relay.conf ya existe, se conserva:"; sed 's/^/        /' "$BOX_DIR/srt_relay.conf"
else
    {
        echo "SRT_MODE='caller'"
        echo "SRT_REMOTE_HOST='$SRV'"
        echo "SRT_REMOTE_PORT='$PORT'"
        echo "SRT_STREAMID='publish:$SID_NAME'"
    } > "$BOX_DIR/srt_relay.conf" || die "no se pudo escribir srt_relay.conf"
    ok "srt_relay.conf creado: $SRV:$PORT  publish:$SID_NAME"
fi
if [ -f "$BOX_DIR/httpd.conf" ]; then
    ok "httpd.conf ya existe, se conserva la contrasena actual del panel"
else
    echo "/:admin:$PPASS" > "$BOX_DIR/httpd.conf" || die "no se pudo escribir httpd.conf"
    ok "panel: usuario admin, contrasena la indicada (cambiala desde el propio panel)"
fi

echo "== 4/5 Arranque en $BOX_DIR/load (sobrevive a cambios de firmware) =="
LOAD="$BOX_DIR/load"
if grep -q 'srt_relay.sh' "$LOAD"; then
    ok "load ya lanza el relay, no se toca"
else
    [ "$(tail -n 1 "$LOAD")" = "./run" ] || die "la ultima linea de $LOAD no es './run': no lo modifico. Pegame 'cat $LOAD'"
    [ -f "$LOAD.orig" ] || cp "$LOAD" "$LOAD.orig" || die "no se pudo hacer la copia $LOAD.orig"
    sed '$d' "$LOAD.orig" > "$LOAD.new"
    {
        echo '# relay SRT + panel: arranque independiente de obj.rar (sobrevive a cambios de firmware)'
        echo "if [ -x $BOX_DIR/srt_relay.sh ]; then"
        echo "        $BOX_DIR/srt_relay.sh > /dev/null 2>&1 < /dev/null &"
        echo 'fi'
        echo './run'
    } >> "$LOAD.new"
    sh -n "$LOAD.new" || { rm -f "$LOAD.new"; die "el load nuevo tiene errores de sintaxis; no se aplica"; }
    cat "$LOAD.new" > "$LOAD" || die "no se pudo escribir $LOAD (restaura con: cat $LOAD.orig > $LOAD)"
    rm -f "$LOAD.new"
    ok "load modificado (copia de seguridad en $LOAD.orig; deshacer: cat $LOAD.orig > $LOAD)"
fi

echo "== 5/5 Arranque del relay =="
if [ "${SKIP_CHECKS:-0}" = "1" ]; then
    echo "  (SKIP_CHECKS: no se arranca nada)"
else
    kill $(ps | grep '[s]rt_relay.sh' | awk '{print $1}') $(ps | grep '[f]fmpeg_armv7' | awk '{print $1}') 2>/dev/null
    kill $(ps | grep '[h]ttpd -p' | awk '{print $1}') 2>/dev/null
    rm -f /tmp/srt_relay.pid
    "$BOX_DIR/srt_relay.sh" > /dev/null 2>&1 < /dev/null &
    IP="$(ifconfig eth0 2>/dev/null | grep 'inet addr' | sed 's/.*inet addr:\([0-9.]*\).*/\1/')"
    echo
    echo "Hecho. El relay tarda unos 20 s en arrancar (calcula antes el md5 de box)."
    echo "  Panel:   http://${IP:-<IP_del_encoder>}:8090   (usuario admin)"
    echo "  Estado:  cat /tmp/srt_state      (connected / connecting)"
    echo "  Log:     cat /tmp/srt_last.log"
    echo "  Procesos: ps | grep -E 'httpd|ffmpeg|srt_relay'"
fi
