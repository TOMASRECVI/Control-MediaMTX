#!/bin/sh
# config.cgi -- panel web del propio BM3000 para editar /box/srt_relay.conf
# y las credenciales de acceso al propio panel (/box/httpd.conf).
# Lo sirve "httpd" de BusyBox (ver srt_relay.sh), puerto PANEL_PORT (8090 por defecto), con
# autenticacion basica. Solo escribe valores validados con lista blanca:
# srt_relay.conf se carga con "." (shell), asi que cualquier caracter raro
# seria ejecucion de comandos como root.

CONF=/box/srt_relay.conf
AUTH=/box/httpd.conf

esc() { echo "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g'; }
bad_chars() { case "$1" in *[!A-Za-z0-9._:/@-]*) return 0;; esac; return 1; }
bad_cred() { case "$1" in *[!A-Za-z0-9._-]*) return 0;; esac; return 1; }

# Estado del relay: stopped (sin ffmpeg), connecting o connected (ver el
# bucle de srt_relay.sh, que escribe /tmp/srt_state).
relay_code() {
    if ! ps | grep -q '[f]fmpeg_armv7'; then echo stopped
    elif [ "$(cat /tmp/srt_state 2>/dev/null)" = "connected" ]; then echo connected
    else echo connecting; fi
}

# Consulta de estado para el JS de la pagina: primera linea = codigo, y si
# no esta conectado, las ultimas lineas de ffmpeg (para ver el motivo).
if [ "$QUERY_STRING" = "status=1" ]; then
    CODE="$(relay_code)"
    printf 'Content-type: text/plain\r\nCache-Control: no-store\r\n\r\n%s\n' "$CODE"
    [ "$CODE" != "connected" ] && tail -n 4 /tmp/srt_last.log 2>/dev/null
    exit 0
fi

[ -f "$CONF" ] && . "$CONF"
MODE="${SRT_MODE:-caller}"
HOST="$SRT_REMOTE_HOST"; RPORT="$SRT_REMOTE_PORT"; LPORT="${SRT_PORT:-9000}"
SID="$SRT_STREAMID"; PASS="$SRT_PASSPHRASE"

AUTH_LINE="$(grep '^/:' "$AUTH" 2>/dev/null | head -1)"
AUTH_REST="${AUTH_LINE#/:}"
CUR_USER="${AUTH_REST%%:*}"
CUR_PASS="${AUTH_REST#*:}"

MSG=""
if [ -n "$QUERY_STRING" ]; then
    ACTION=""; N_MODE=""; N_HOST=""; N_RPORT=""; N_LPORT=""; N_SID=""; N_PASS=""
    C_OLD=""; C_USER=""; C_NEW=""; C_NEW2=""
    OLDIFS="$IFS"; IFS='&'; set -f
    for kv in $QUERY_STRING; do
        k="${kv%%=*}"; v="${kv#*=}"
        v="$(echo "$v" | tr '+' ' ')"
        v="$(busybox httpd -d "$v")"
        case "$k" in
            action) ACTION="$v";;
            mode) N_MODE="$v";; host) N_HOST="$v";; rport) N_RPORT="$v";;
            lport) N_LPORT="$v";; sid) N_SID="$v";; pass) N_PASS="$v";;
            cold) C_OLD="$v";; cuser) C_USER="$v";; cnew) C_NEW="$v";; cnew2) C_NEW2="$v";;
        esac
    done
    IFS="$OLDIFS"; set +f

    if [ "$ACTION" = "cred" ]; then
        ERR=""
        if [ "$C_OLD" != "$CUR_PASS" ]; then ERR="La contrasena actual no coincide"
        elif [ -z "$C_USER" ] || bad_cred "$C_USER"; then ERR="Usuario no valido (solo letras, numeros y . _ -)"
        elif bad_cred "$C_NEW"; then ERR="Contrasena no valida (solo letras, numeros y . _ -)"
        elif [ ${#C_NEW} -lt 6 ]; then ERR="La contrasena nueva necesita al menos 6 caracteres"
        elif [ "$C_NEW" != "$C_NEW2" ]; then ERR="Las dos contrasenas nuevas no coinciden"
        fi
        if [ -n "$ERR" ]; then
            MSG="ERROR: $ERR"
        else
            echo "/:$C_USER:$C_NEW" > "$AUTH.tmp" && cat "$AUTH.tmp" > "$AUTH" && rm -f "$AUTH.tmp" || WFAIL=1
            if [ -n "$WFAIL" ]; then
                MSG="ERROR: no se pudo escribir $AUTH"
            else
                ( sleep 2
                  PP="${PANEL_PORT:-8090}"
                  for p in $(ps | grep "[h]ttpd -p $PP" | awk '{print $1}'); do kill "$p" 2>/dev/null; done
                  busybox httpd -p "$PP" -h /box/www -c /box/httpd.conf
                ) >/dev/null 2>&1 </dev/null &
                MSG="Acceso cambiado. El panel se reinicia: en unos segundos el navegador pedira el usuario y la contrasena nuevos."
            fi
        fi
    elif [ "$ACTION" = "conf" ]; then
        ERR=""
        case "$N_MODE" in caller|listener) ;; *) ERR="Modo no valido";; esac
        for f in "$N_HOST" "$N_SID" "$N_PASS"; do
            bad_chars "$f" && ERR="Caracteres no permitidos (solo letras, numeros y . _ : / @ -)"
        done
        case "$N_RPORT$N_LPORT" in *[!0-9]*) ERR="Los puertos deben ser numericos";; esac
        if [ "$N_MODE" = "caller" ] && { [ -z "$N_HOST" ] || [ -z "$N_RPORT" ]; }; then
            ERR="Modo caller necesita servidor y puerto remoto"
        fi

        if [ -n "$ERR" ]; then
            MSG="ERROR: $ERR"
        else
            {
                echo "SRT_MODE='$N_MODE'"
                if [ "$N_MODE" = "caller" ]; then
                    echo "SRT_REMOTE_HOST='$N_HOST'"
                    echo "SRT_REMOTE_PORT='$N_RPORT'"
                else
                    echo "SRT_PORT='${N_LPORT:-9000}'"
                fi
                [ -n "$N_SID" ] && echo "SRT_STREAMID='$N_SID'"
                [ -n "$N_PASS" ] && echo "SRT_PASSPHRASE='$N_PASS'"
                [ -n "$PANEL_PORT" ] && echo "PANEL_PORT='$PANEL_PORT'"
                true
            } > "$CONF.tmp" && cat "$CONF.tmp" > "$CONF" && rm -f "$CONF.tmp" || WFAIL=1
            if [ -n "$WFAIL" ]; then
                MSG="ERROR: no se pudo escribir $CONF"
            else
                for p in $(ps | grep -E '[s]rt_relay.sh|[f]fmpeg_armv7' | awk '{print $1}'); do kill "$p" 2>/dev/null; done
                rm -f /tmp/srt_relay.pid
                ( /box/srt_relay.sh >/dev/null 2>&1 </dev/null & )
                MODE="$N_MODE"; HOST="$N_HOST"; RPORT="$N_RPORT"; LPORT="${N_LPORT:-9000}"; SID="$N_SID"; PASS="$N_PASS"
                MSG="Guardado. Relay reiniciado con la nueva configuracion."
            fi
        fi
    fi
fi

SEL_C=""; SEL_L=""
[ "$MODE" = "caller" ] && SEL_C=" selected"
[ "$MODE" = "listener" ] && SEL_L=" selected"

printf 'Content-type: text/html; charset=utf-8\r\n\r\n'
cat << EOF
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BM3000 SRT</title>
<style>body{font-family:sans-serif;background:#0d1117;color:#e6edf3;max-width:480px;margin:2rem auto;padding:0 1rem}
label{display:block;margin-top:.8rem;font-size:.8rem;color:#8b949e}
input,select{width:100%;padding:8px;background:#161b22;color:#e6edf3;border:1px solid #30363d;border-radius:6px;box-sizing:border-box}
button{margin-top:1.2rem;padding:10px 18px;background:#238636;color:#fff;border:0;border-radius:6px;cursor:pointer}
h3{margin-top:2.2rem;border-top:1px solid #30363d;padding-top:1.2rem}
.srt{display:flex;align-items:center;gap:.6rem;padding:10px 12px;border-radius:6px;background:#161b22;border:1px solid #30363d;font-size:.9rem}
.dot{width:12px;height:12px;border-radius:50%;background:#8b949e;flex-shrink:0}
.srt.ok .dot{background:#3fb950}.srt.wait .dot{background:#d29922}.srt.off .dot{background:#f85149}
.log{font-size:.72rem;color:#8b949e;white-space:pre-wrap;word-break:break-all;margin:.4rem 0 0}
.msg{margin-top:1rem;padding:8px;border-radius:6px;background:#1c2333}.st{color:#8b949e;font-size:.85rem}</style></head><body>
<h2>BM3000 &mdash; relay SRT</h2>
<div id="srtst" class="srt wait"><span class="dot"></span><span id="srttxt">Comprobando estado...</span></div>
<pre id="srtlog" class="log"></pre>
$( [ -n "$MSG" ] && echo "<div class=\"msg\">$(esc "$MSG")</div>" )
<form method="get" action="/cgi-bin/config.cgi"><input type="hidden" name="action" value="conf">
<label>Modo</label><select name="mode"><option value="caller"$SEL_C>caller (el equipo se conecta al servidor)</option><option value="listener"$SEL_L>listener (el equipo espera conexion)</option></select>
<label>Servidor SRT remoto (caller)</label><input name="host" value="$(esc "$HOST")" placeholder="192.168.1.147">
<label>Puerto remoto (caller)</label><input name="rport" value="$(esc "$RPORT")" placeholder="8890">
<label>Puerto local (listener)</label><input name="lport" value="$(esc "$LPORT")" placeholder="9000">
<label>Streamid</label><input name="sid" value="$(esc "$SID")" placeholder="publish:bm3000">
<label>Passphrase (opcional)</label><input name="pass" value="$(esc "$PASS")">
<button type="submit">Guardar y reiniciar relay</button></form>

<h3>Acceso al panel</h3>
<form method="get" action="/cgi-bin/config.cgi" autocomplete="off"><input type="hidden" name="action" value="cred">
<label>Usuario</label><input name="cuser" value="$(esc "$CUR_USER")">
<label>Contrasena actual</label><input type="password" name="cold">
<label>Contrasena nueva (min. 6; letras, numeros y . _ -)</label><input type="password" name="cnew">
<label>Repite la contrasena nueva</label><input type="password" name="cnew2">
<label style="display:flex;align-items:center;gap:.5rem;cursor:pointer"><input type="checkbox" style="width:auto" onclick="var f=this.form,t=this.checked?'text':'password';f.cold.type=t;f.cnew.type=t;f.cnew2.type=t"> Mostrar contrasenas</label>
<button type="submit">Cambiar acceso</button></form>
<script>
function pollState(){
  var x=new XMLHttpRequest();
  x.open('GET','/cgi-bin/config.cgi?status=1',true);
  x.onload=function(){
    var l=x.responseText.split('\n'),c=l[0],box=document.getElementById('srtst'),t=document.getElementById('srttxt');
    if(c==='connected'){box.className='srt ok';t.textContent='Conectado al servidor SRT: enviando video';}
    else if(c==='connecting'){box.className='srt wait';t.textContent='Intentando conectar con el servidor SRT...';}
    else{box.className='srt off';t.textContent='Relay parado (puede estar arrancando)';}
    document.getElementById('srtlog').textContent=(c==='connected')?'':l.slice(1).join('\n');
  };
  x.onerror=function(){var b=document.getElementById('srtst');b.className='srt off';document.getElementById('srttxt').textContent='Sin respuesta del panel';};
  x.send();
}
pollState();setInterval(pollState,3000);
</script>
</body></html>
EOF
