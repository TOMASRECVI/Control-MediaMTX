# BM3000 → SRT: el propio encoder emite SRT

El BM3000 ejecuta un segundo proceso (`ffmpeg` estatico) que coge su propio
RTSP local y lo abre como **servidor SRT** (modo *listener*) en un puerto
propio -- igual que hace de fabrica el BM3380H con su opcion "SRT Switch".
No hay ningun servidor destino fijo ni configuracion de a-donde-enviarlo:
el equipo simplemente publica `srt://<IP_BM3000>:<puerto>` y cualquier
cliente (MediaMTX, ffplay, VLC, otro BM3000...) se conecta cuando quiera.
No se toca el binario `box` en ningun momento.

Esto es posible porque `box` es un ejecutable **dinamico** (usa
`connect/send/recv` de libc via PLT) — pero aqui ni siquiera hace falta
interceptar nada: `box` ya expone RTSP en localhost por su cuenta, así que
solo necesitamos otro proceso normal corriendo al lado.

## Estado real confirmado (equipo en 192.168.1.93)

- Firmware corriendo: **version 2.89** (se muestra como "3.37W5" en el
  panel -- formula `parseFloat(version)+0.48` del propio JS). Corresponde
  al paquete `3.37W5/up.bin` de esta carpeta, NO a `up_final.rar` (mucho
  mas antiguo) que se uso para el analisis inicial. Todos los ficheros de
  este directorio (`srt_relay.sh`, `run.new`, hash de `box`) ya estan
  actualizados contra esta version real.
- `box` real: md5 `08480eb6df66ec40ba1f9142a548f64b`, RTSP interno en
  `rtsp://127.0.0.1:8554/0` (puerto 8554, no el 554 por defecto).
- `run` **sigue lanzando `telnetd&`** de fabrica -- en teoria permitiria
  probar todo en caliente en `/tmp` (que se reconstruye solo al reiniciar)
  antes de tocar nada persistente.
- **Bloqueante actual: no tenemos la credencial de login de telnet/consola**
  (`admin/admin` es el login del panel web, HTTP Basic Auth -- probado y
  funciona ahi -- pero el telnet devuelve "Login incorrect" con esas mismas
  credenciales). Sin eso no se puede hacer la Fase 1 (prueba en caliente).

## Fase 1 — prueba en caliente (recomendado empezar aqui)

1. Compila el binario estatico. Esto se hace en tu **servidor Linux con
   Docker** (192.168.1.147 u otro) -- copia esta carpeta ahi si aun no la
   tienes (`scp`, `git`, o el metodo que uses para desplegar el resto del
   proyecto) y desde dentro de `bm3000-onboard-relay/`:

   ```bash
   docker build -t bm3000-ffmpeg-builder .
   docker create --name extract bm3000-ffmpeg-builder
   docker cp extract:/ffmpeg_armv7 .
   docker rm extract
   chmod +x ffmpeg_armv7
   file ffmpeg_armv7
   ```

   La ultima linea debe decir algo como
   `ELF 32-bit LSB executable, ARM, ..., statically linked, stripped`.
   Si dice "dynamically linked" o da error de arquitectura, algo fue mal
   en el build -- no sigas al paso 2 todavia.

2. Conecta por telnet al BM3000 (usuario/clave: los que uses para el panel
   web o los de fabrica — revisa el `passwd` del propio equipo si no los
   tienes):

   ```bash
   telnet <IP_BM3000>
   ```

   Una vez dentro, comprueba que herramienta de transferencia hay
   disponible (no todos los BusyBox traen las mismas -- no asumas, mira):

   ```sh
   which wget nc tftp ftpget
   ```

3. Sube `ffmpeg_armv7` y `srt_relay.sh` a `/tmp` en el equipo. Tres
   metodos, de mas a menos comodo -- usa el primero que exista:

   **A) Si hay `wget`** (lo mas comun en BusyBox): sirve los ficheros
   desde tu PC/servidor con un servidor HTTP de un solo comando, en la
   carpeta donde tengas `ffmpeg_armv7` y `srt_relay.sh`:

   ```bash
   python3 -m http.server 8000
   ```

   Y en la sesion telnet del BM3000:

   ```sh
   cd /tmp
   wget http://<IP_DE_TU_PC>:8000/ffmpeg_armv7
   wget http://<IP_DE_TU_PC>:8000/srt_relay.sh
   ```

   **B) Si hay `nc` (netcat) pero no `wget`:** abre una SEGUNDA terminal
   en tu PC (deja la sesion telnet abierta en la primera). En la sesion
   telnet del BM3000:

   ```sh
   nc -l -p 9999 > /tmp/ffmpeg_armv7
   ```

   Y en tu segunda terminal (PC):

   ```bash
   nc <IP_BM3000> 9999 < ffmpeg_armv7
   ```

   Cuando termine la transferencia (el `nc -l` del equipo vuelve al
   prompt solo), repite exactamente igual para `srt_relay.sh`.

   **C) Si no hay ninguna de las dos:** monta un servidor `tftp` en tu PC
   (ej. `atftpd`/`tftpd-hpa` en Linux) y usa `tftp -g -r ffmpeg_armv7 -l
   /tmp/ffmpeg_armv7 <IP_DE_TU_PC>` desde el equipo, si su BusyBox trae
   cliente `tftp`.

   En cualquier caso, verifica al final que el fichero llegó entero:

   ```sh
   ls -la /tmp/ffmpeg_armv7 /tmp/srt_relay.sh
   ```

   (compara el tamaño con el que ves en tu PC con `ls -la`).

4. Desde la sesión telnet:

   ```sh
   cd /tmp
   chmod +x ffmpeg_armv7 srt_relay.sh
   SRT_PORT=9000 ./srt_relay.sh
   ```

5. Desde cualquier maquina de tu red, comprueba que el BM3000 ya sirve SRT:

   ```bash
   ffplay "srt://<IP_BM3000>:9000"
   ```

   Si quieres que MediaMTX lo consuma, ahi simplemente das de alta esa URL
   como fuente (`srt://<IP_BM3000>:9000`) desde su propio panel/config --
   eso ya no depende de este script. Si algo va mal aqui, `Ctrl+C` y ajusta:
   no hay nada persistente todavia.

## Fase 2 — hacerlo persistente (via re-flasheo, sin necesitar telnet)

Sin credencial de telnet, la Fase 1 (prueba en caliente) no se puede hacer.
La alternativa es empaquetar directamente y subir por el panel web, que sí
tenemos autenticado. **Esto se salta el paso de prueba segura** -- el primer
arranque con los ficheros nuevos ya es el definitivo. Antes de hacerlo real
sobre el equipo en 192.168.1.93 (que ademas esta en produccion, empujando
RTMP a vuestro MediaMTX ahora mismo), quiero confirmacion explicita tuya.

Mecanismo de subida confirmado leyendo el JS de `SystemUpdateE.html` del
propio equipo:

- `POST http://192.168.1.93/SystemE.html?id=<id>`, `multipart/form-data`,
  campo de fichero `upgrade`. El nombre de fichero debe ser `up.bin` (el
  propio panel lo indica); nombres que contengan `uk.rar`/`uk.bin` disparan
  una ruta especial de "actualizacion de kernel" -- no es nuestro caso.
- Progreso: `GET /up_progress?id=<id>` devuelve `1` (terminado) o `-1`
  (fallo). El equipo se reinicia solo al terminar.
- No encontre ninguna verificacion de firma/checksum en ese JS -- coherente
  con lo visto en `up_final.rar` (el `.bin` es un RAR sin cabecera extra).

Pasos:

1. Extrae `3.37W5/up.bin` (el firmware REAL de este equipo, no
   `up_final.rar`) a una carpeta.
2. Copia dentro `ffmpeg_armv7` y `srt_relay.sh` (junto a `box`, en la raíz).
3. Sustituye el `run` original por [`run.new`](run.new) de este directorio.
4. Re-empaqueta la carpeta completa como RAR, mismo nombre `up.bin`.
   **Guarda aparte una copia intacta de `3.37W5/up.bin`** como plan de
   vuelta atrás si el nuevo no arranca bien.
5. Sube el paquete modificado vía el endpoint de arriba (formulario de
   `SystemUpdate.html`, o replicando la petición POST).
6. Si el equipo no vuelve a levantar el panel/red tras el reinicio, hay
   acceso serie (`web/Remserial.html` + el binario `remserial` sugieren
   header UART en la placa) como vía de recuperación antes de considerarlo
   inoperativo.

## Notas sobre el Dockerfile

- Usa `dockcross/linux-armv7`, un toolchain de cross-compilación estándar
  y público (no el SDK propietario de HiSilicon) — el binario resultante es
  **100% estático (musl)**, por lo que no depende de la uClibc del propio
  BM3000 ni tiene que coincidir con su ABI exacta; solo necesita que el
  kernel Linux del equipo soporte las syscalls básicas (lleva usándolas
  desde kernels muy antiguos, así que no hay problema aquí).
- El build confirmado por `.ARM.attributes` del propio `box`: CPU
  **Cortex-A9 (ARMv7-A)**, así que el target `armv7` del toolchain es el
  correcto.
- Compilé `libsrt` con `ENABLE_ENCRYPTION=OFF` para simplificar (sin
  passphrase). Si necesitas SRT cifrado, hay que activarlo y enlazar
  OpenSSL estático también — dímelo y lo ajusto.
- Nadie ha ejecutado ni descargado este binario todavía: el Dockerfile solo
  compila desde el código fuente público de FFmpeg y de Haivision/srt (los
  proyectos oficiales) — te toca a ti construirlo y revisarlo antes de
  subirlo al equipo.
