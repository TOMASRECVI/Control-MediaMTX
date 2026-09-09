#!/usr/bin/env python3
"""
MediaMTX Recording Manager
Web interface for controlling recording, viewing and managing recorded files.
"""

from flask import Flask, jsonify, request, render_template, Response, abort, redirect, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import requests as http_requests
import os
import re
import json
import hmac
import secrets
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', '10'))

# Path where the mediamtx_data volume is mounted
DATA_PATH = os.environ.get('DATA_PATH', '/data')

# ─── Conexión con MediaMTX ────────────────────────────────────────────────────
# Igual que las credenciales de login: MEDIAMTX_API (variable de entorno) solo
# se usa como semilla la primera vez. Una vez configurado desde el panel
# (⚙ Configuración), el host/puerto quedan guardados en el volumen de datos y
# sobreviven a reinicios/reconstrucciones sin tocar docker-compose.yml.
_MEDIAMTX_CONFIG_FILE = Path(DATA_PATH) / '.manager_mediamtx_config.json'
_mediamtx_config_lock = threading.Lock()


def _load_or_init_mediamtx_api():
    try:
        if _MEDIAMTX_CONFIG_FILE.exists():
            data = json.loads(_MEDIAMTX_CONFIG_FILE.read_text())
            if data.get('mediamtx_api'):
                return data['mediamtx_api'].rstrip('/')
    except (OSError, ValueError, KeyError) as e:
        logger.warning(f'No se pudo leer la configuración de MediaMTX guardada ({e}); se reinicializa desde variables de entorno.')

    api = os.environ.get('MEDIAMTX_API', 'http://mediamtx:9997').rstrip('/')
    _save_mediamtx_api(api)
    return api


def _save_mediamtx_api(api):
    try:
        _MEDIAMTX_CONFIG_FILE.write_text(json.dumps({'mediamtx_api': api}))
    except OSError as e:
        logger.error(f'No se pudo guardar la configuración de MediaMTX en disco: {e}')


MEDIAMTX_API = _load_or_init_mediamtx_api()


def _set_mediamtx_api(new_api):
    global MEDIAMTX_API
    with _mediamtx_config_lock:
        MEDIAMTX_API = new_api
        _save_mediamtx_api(new_api)

# ─── Autenticación ────────────────────────────────────────────────────────────
# Usuario/contraseña únicos (panel de administración de un solo operador).
# Las credenciales EFECTIVAS se guardan (usuario + hash de contraseña) en un
# archivo en el volumen de datos, para poder cambiarlas desde el propio panel
# sin tocar docker-compose.yml ni perderlas al reiniciar el contenedor.
# AUTH_USERNAME/AUTH_PASSWORD (variables de entorno) solo se usan como
# semilla la PRIMERA vez que arranca (si no existe aún ese archivo). Si ni
# siquiera hay AUTH_PASSWORD, se genera una aleatoria y se imprime una vez
# en los logs -- preferible a un valor por defecto adivinable.
_CREDENTIALS_FILE = Path(DATA_PATH) / '.manager_credentials.json'
_credentials_lock = threading.Lock()


def _load_or_init_credentials():
    try:
        if _CREDENTIALS_FILE.exists():
            data = json.loads(_CREDENTIALS_FILE.read_text())
            if data.get('username') and data.get('password_hash'):
                return data['username'], data['password_hash']
    except (OSError, ValueError, KeyError) as e:
        logger.warning(f'No se pudo leer credenciales guardadas ({e}); se reinicializan desde variables de entorno.')

    username = os.environ.get('AUTH_USERNAME', 'admin')
    password = os.environ.get('AUTH_PASSWORD', 'admin')
    logger.warning('=' * 70)
    logger.warning(f'Credenciales iniciales del panel -> usuario: {username} / contraseña: {password}')
    logger.warning('Cámbialas cuanto antes desde el propio panel (⚙ Configuración).')
    logger.warning('=' * 70)

    password_hash = generate_password_hash(password)
    _save_credentials(username, password_hash)
    return username, password_hash


def _save_credentials(username, password_hash):
    try:
        _CREDENTIALS_FILE.write_text(json.dumps({'username': username, 'password_hash': password_hash}))
    except OSError as e:
        logger.error(f'No se pudieron guardar las credenciales en disco: {e}')


_current_username, _current_password_hash = _load_or_init_credentials()


def _check_credentials(username, password):
    with _credentials_lock:
        valid_user = hmac.compare_digest(username, _current_username)
        valid_pass = check_password_hash(_current_password_hash, password)
    return valid_user and valid_pass


def _update_credentials(new_username, new_password):
    global _current_username, _current_password_hash
    password_hash = generate_password_hash(new_password)
    with _credentials_lock:
        _current_username = new_username
        _current_password_hash = password_hash
        _save_credentials(new_username, password_hash)


def _get_or_create_secret_key():
    """Clave de firma de sesión. Se persiste en el volumen de datos para que
    las sesiones sobrevivan a un reinicio del contenedor del manager."""
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key
    key_file = Path(DATA_PATH) / '.manager_secret_key'
    try:
        if key_file.exists():
            return key_file.read_text().strip()
        key = secrets.token_hex(32)
        key_file.write_text(key)
        return key
    except OSError as e:
        logger.warning(f'No se pudo persistir SECRET_KEY en disco ({e}); se generará una nueva en cada reinicio.')
        return secrets.token_hex(32)


app.secret_key = _get_or_create_secret_key()
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 30  # 30 días

# Límite de intentos de login por IP, para dificultar fuerza bruta.
_login_attempts = {}  # ip -> {'count': int, 'locked_until': epoch}
_login_attempts_lock = threading.Lock()
_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_LOCKOUT_SECONDS = 30


def _login_locked_out(ip):
    with _login_attempts_lock:
        entry = _login_attempts.get(ip)
        return bool(entry and entry.get('locked_until', 0) > time.time())


def _register_failed_login(ip):
    with _login_attempts_lock:
        entry = _login_attempts.setdefault(ip, {'count': 0, 'locked_until': 0})
        entry['count'] += 1
        if entry['count'] >= _MAX_LOGIN_ATTEMPTS:
            entry['locked_until'] = time.time() + _LOGIN_LOCKOUT_SECONDS
            entry['count'] = 0


def _register_successful_login(ip):
    with _login_attempts_lock:
        _login_attempts.pop(ip, None)


_PUBLIC_PATHS = {'/login', '/logout'}


@app.before_request
def require_login():
    if request.path in _PUBLIC_PATHS or request.path.startswith('/static/'):
        return None
    if session.get('logged_in'):
        return None
    if request.path.startswith('/api/') or request.path.startswith('/video/'):
        return jsonify({'error': 'No autenticado'}), 401
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if session.get('logged_in'):
            return redirect('/')
        return render_template('login.html', error=None)

    ip = request.remote_addr or 'desconocida'
    if _login_locked_out(ip):
        return render_template('login.html', error='Demasiados intentos fallidos. Espera unos segundos e inténtalo de nuevo.'), 429

    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''

    if _check_credentials(username, password):
        _register_successful_login(ip)
        session.clear()
        session['logged_in'] = True
        session.permanent = True
        return redirect('/')

    _register_failed_login(ip)
    logger.warning(f'Login fallido desde {ip} (usuario: {username!r})')
    return render_template('login.html', error='Usuario o contraseña incorrectos'), 401


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect('/login')


@app.route('/api/account/credentials', methods=['PATCH'])
def change_credentials():
    """Cambia el usuario/contraseña de acceso al panel. Requiere estar ya
    autenticado (lo exige require_login) Y confirmar la contraseña actual,
    para que una sesión robada no pueda usarse para expulsar al dueño real
    cambiando las credenciales sin más."""
    body = request.json or {}
    current_password = body.get('currentPassword') or ''
    new_username = (body.get('newUsername') or '').strip()
    new_password = body.get('newPassword') or ''

    with _credentials_lock:
        current_username = _current_username
        current_hash = _current_password_hash
    if not check_password_hash(current_hash, current_password):
        return jsonify({'error': 'La contraseña actual no es correcta'}), 401

    if not new_username:
        new_username = current_username
    if not new_password:
        return jsonify({'error': 'La nueva contraseña no puede estar vacía'}), 400
    if len(new_password) < 4:
        return jsonify({'error': 'La nueva contraseña es demasiado corta (mínimo 4 caracteres)'}), 400

    _update_credentials(new_username, new_password)
    logger.info(f'Credenciales de acceso actualizadas (usuario: {new_username!r})')
    return jsonify({'success': True, 'username': new_username})


@app.route('/api/account/mediamtx-config', methods=['GET'])
def get_mediamtx_config():
    """Host/puerto actuales de conexión con MediaMTX, para rellenar el formulario."""
    parsed = urlparse(MEDIAMTX_API)
    return jsonify({'host': parsed.hostname or '', 'port': parsed.port or 9997})


@app.route('/api/account/mediamtx-config', methods=['PATCH'])
def set_mediamtx_config():
    """Cambia el host/puerto de conexión con MediaMTX. Comprueba que el nuevo
    destino responde antes de guardar el cambio, para no dejar el panel
    entero sin poder hablar con MediaMTX por una errata."""
    body = request.json or {}
    host = (body.get('host') or '').strip()
    port = body.get('port')

    if not host:
        return jsonify({'error': 'El host no puede estar vacío'}), 400
    try:
        port = int(port)
        if not (1 <= port <= 65535):
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'error': 'El puerto debe ser un número entre 1 y 65535'}), 400

    new_api = f'http://{host}:{port}'
    try:
        r = http_requests.get(f'{new_api}/v3/config/global/get', timeout=5)
        r.raise_for_status()
    except http_requests.exceptions.RequestException as e:
        logger.warning(f'No se pudo verificar la nueva conexión a MediaMTX ({new_api}): {e}')
        return jsonify({'error': f'No se pudo conectar a {host}:{port}. Comprueba el host/puerto y que MediaMTX esté encendido. Detalle: {e}'}), 502

    _set_mediamtx_api(new_api)
    logger.info(f'Conexión con MediaMTX actualizada a: {new_api}')
    return jsonify({'success': True, 'host': host, 'port': port})


# ─── Bloqueo de reconexión tras "Desconectar" ────────────────────────────────
# MediaMTX no ofrece una forma nativa de rechazar permanentemente a un
# publisher por path (su auth es por regla estática, no por decisión en vivo).
# Lo emulamos en el manager: guardamos qué paths están "bloqueados" y un hilo
# de fondo re-desconecta automáticamente a cualquier publisher que reaparezca
# en uno de ellos, hasta que se permita la reconexión manualmente.
_blocked_paths = set()
_blocked_lock = threading.Lock()
_BLOCK_ENFORCE_INTERVAL = 2  # segundos entre comprobaciones

# ─── Bitrate en vivo (flujo actual, no acumulado) ────────────────────────────
# MediaMTX solo da contadores acumulados de bytes desde que empezó la
# conexión (bytesReceived/bytesSent). Para mostrar el flujo ACTUAL en vez del
# total acumulado, guardamos la última muestra por path y calculamos bps a
# partir de la diferencia con la muestra anterior cada vez que se consulta.
_bitrate_samples = {}  # path_name -> {'t': timestamp, 'rx': bytes, 'tx': bytes}
_bitrate_lock = threading.Lock()


def _compute_bitrates(path_name, bytes_received, bytes_sent):
    """Devuelve (bps_entrada, bps_salida) comparando con la muestra anterior.

    Devuelve (None, None) si es la primera muestra de este path (aún no hay
    con qué comparar) o si las muestras están demasiado pegadas en el tiempo.
    """
    now = time.time()
    with _bitrate_lock:
        prev = _bitrate_samples.get(path_name)
        _bitrate_samples[path_name] = {'t': now, 'rx': bytes_received, 'tx': bytes_sent}

    if not prev:
        return None, None
    elapsed = now - prev['t']
    if elapsed <= 0.05:
        return None, None

    rx_bps = max((bytes_received - prev['rx']) * 8 / elapsed, 0)
    tx_bps = max((bytes_sent - prev['tx']) * 8 / elapsed, 0)
    return rx_bps, tx_bps


def _clear_bitrate_sample(path_name):
    with _bitrate_lock:
        _bitrate_samples.pop(path_name, None)


def _safe_resolve(filepath):
    """Resolve a file path and ensure it's inside DATA_PATH. Returns Path or None."""
    try:
        data_dir = Path(DATA_PATH).resolve()
        target = (Path(DATA_PATH) / filepath).resolve()
        # Check if target is inside data_dir
        target.relative_to(data_dir)  # raises ValueError if not relative
        return target
    except (ValueError, RuntimeError) as e:
        logger.warning(f'Path traversal blocked: {filepath} - {e}')
        return None


def _delete_file(filepath):
    """Delete a single file by its relative path under DATA_PATH. Returns True on success."""
    logger.info(f'_delete_file called with: {filepath}')
    target = _safe_resolve(filepath)
    if not target:
        logger.error(f'_safe_resolve failed for: {filepath}')
        return False
    logger.info(f'Resolved to: {target}')
    logger.info(f'Exists: {target.exists()}, Is file: {target.is_file()}')
    if not target.exists() or not target.is_file():
        logger.warning(f'File not found or not a file: {target}')
        return False
    try:
        target.unlink()
        logger.info(f'Successfully deleted file: {target}')
        # Clean empty parent dirs
        data_dir = Path(DATA_PATH).resolve()
        parent = target.parent
        while parent != data_dir:
            try:
                parent.rmdir()
                logger.info(f'Removed empty dir: {parent}')
                parent = parent.parent
            except OSError:
                break
        return True
    except Exception as e:
        logger.error(f'Exception deleting file {target}: {e}', exc_info=True)
        return False


def _delete_all_files_for_path(path_name):
    """Delete all .mp4 files under a recording path. Returns count deleted."""
    data_dir = Path(DATA_PATH)
    path_dir = data_dir / path_name
    if not path_dir.exists():
        return 0
    try:
        if not str(path_dir.resolve()).startswith(str(data_dir.resolve())):
            return 0
    except Exception:
        return 0

    count = 0
    for f in list(path_dir.rglob('*.mp4')):
        try:
            f.unlink()
            logger.info(f'Deleted file: {f}')
            count += 1
        except Exception as e:
            logger.error(f'Error deleting file {f}: {e}')

    # Clean empty dirs
    for d in sorted(path_dir.rglob('*'), reverse=True):
        if d.is_dir():
            try:
                d.rmdir()
            except OSError:
                pass
    return count


# ─── Frontend ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ─── Health / Status ─────────────────────────────────────────────────────────

@app.route('/api/health')
def health():
    """Check connectivity to the MediaMTX API."""
    try:
        r = http_requests.get(f'{MEDIAMTX_API}/v3/config/global/get', timeout=3)
        r.raise_for_status()
        return jsonify({'status': 'ok', 'mediamtx': True})
    except Exception as e:
        logger.warning(f'MediaMTX API not reachable: {e}')
        return jsonify({'status': 'degraded', 'mediamtx': False, 'error': str(e)})


# ─── Path-Defaults Configuration ─────────────────────────────────────────────

@app.route('/api/config/defaults')
def get_defaults():
    """Return the pathDefaults config (includes recording settings)."""
    try:
        r = http_requests.get(
            f'{MEDIAMTX_API}/v3/config/pathdefaults/get',
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        return jsonify(r.json())
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error fetching path defaults: {e}')
        return jsonify({'error': str(e)}), 502


@app.route('/api/config/defaults', methods=['PATCH'])
def patch_defaults():
    """Update pathDefaults. Typical use: {"record": true} or {"record": false}"""
    try:
        body = request.json or {}

        # Normalize recordDeleteAfter to go format (e.g., "24h", "30m", "3600s")
        # MediaMTX Go duration format: only h, m, s suffixes work
        if 'recordDeleteAfter' in body:
            val_str = body['recordDeleteAfter']
            # Keep as-is if already in correct format
            logger.info(f'Setting recordDeleteAfter to: {val_str}')

        r = http_requests.patch(
            f'{MEDIAMTX_API}/v3/config/pathdefaults/patch',
            json=body,
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        return jsonify({'success': True, **body})
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error patching path defaults: {e}')
        logger.error(f'Request body was: {body}')
        return jsonify({'error': str(e)}), 502


# ─── Configuración global (logs) ──────────────────────────────────────────────

@app.route('/api/config/global')
def get_global_config():
    """Devuelve la config global de MediaMTX (incluye logLevel/logDestinations/logFile)."""
    try:
        r = http_requests.get(f'{MEDIAMTX_API}/v3/config/global/get', timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return jsonify(r.json())
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error fetching global config: {e}')
        return jsonify({'error': str(e)}), 502


@app.route('/api/config/global', methods=['PATCH'])
def patch_global_config():
    """Actualiza config global. Uso típico: logLevel, logDestinations, logFile."""
    body = request.json or {}
    try:
        r = http_requests.patch(
            f'{MEDIAMTX_API}/v3/config/global/patch',
            json=body,
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        return jsonify({'success': True, **body})
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error patching global config: {e}')
        return jsonify({'error': str(e)}), 502


# ─── Per-Path Configuration ──────────────────────────────────────────────────

@app.route('/api/config/paths/<path:name>', methods=['PATCH'])
def patch_path(name):
    """Update config for a single path (e.g. toggle its recording).

    Si el path aún no tiene una entrada de configuración propia (paths
    dinámicos, descubiertos en caliente), MediaMTX responde 404 al PATCH.
    En ese caso, la creamos con POST /v3/config/paths/add/<name>.
    """
    body = request.json or {}
    try:
        r = http_requests.patch(
            f'{MEDIAMTX_API}/v3/config/paths/patch/{name}',
            json=body,
            timeout=REQUEST_TIMEOUT
        )
        if r.status_code == 404:
            r = http_requests.post(
                f'{MEDIAMTX_API}/v3/config/paths/add/{name}',
                json=body,
                timeout=REQUEST_TIMEOUT
            )
        r.raise_for_status()
        return jsonify({'success': True, 'path': name, **body})
    except http_requests.exceptions.HTTPError as e:
        detail = getattr(e.response, 'text', '')[:300]
        logger.error(f'Error HTTP patching path {name}: {e} - {detail}')
        return jsonify({'error': str(e), 'detail': detail}), 502
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error patching path {name}: {e}')
        return jsonify({'error': str(e)}), 502


# ─── Active Paths ────────────────────────────────────────────────────────────

@app.route('/api/paths')
def list_paths():
    """List active paths (cameras / streams currently connected)."""
    try:
        r = http_requests.get(
            f'{MEDIAMTX_API}/v3/paths/list',
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        return jsonify(r.json())
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error listing paths: {e}')
        return jsonify({'error': str(e)}), 502


# ─── Recordings ──────────────────────────────────────────────────────────────

def _segment_file_mtime(path_name, start_iso):
    """Fecha de modificación (UTC) del archivo .mp4 de un segmento, o None si no se encuentra."""
    path_dir = Path(DATA_PATH) / path_name
    if not start_iso or not path_dir.exists():
        return None
    # El nombre del archivo empieza por el timestamp de inicio, p.ej.
    # "2026-09-09_10-16-50-631410.mp4" para el start "2026-09-09T10:16:50...Z".
    prefix = start_iso[:19].replace('T', '_').replace(':', '-')
    try:
        for f in path_dir.rglob('*.mp4'):
            if f.name.startswith(prefix):
                return datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
    except OSError:
        pass
    return None


@app.route('/api/recordings')
def list_recordings():
    """List all recording paths and their segments with duration info."""
    try:
        r = http_requests.get(
            f'{MEDIAMTX_API}/v3/recordings/list',
            params={'itemsPerPage': 100},
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        data = r.json()

        # Para saber si el último segmento de un path sigue en curso (y por
        # tanto no debe rellenarse Fin/Duración todavía) necesitamos saber si
        # ese path está activo Y grabando ahora mismo.
        currently_recording = _paths_currently_recording()

        result = []
        for item in data.get('items', []):
            name = item.get('name', '')
            try:
                seg_r = http_requests.get(
                    f'{MEDIAMTX_API}/v3/recordings/get/{name}',
                    timeout=REQUEST_TIMEOUT
                )
                seg_r.raise_for_status()
                seg_data = seg_r.json()
                segments = seg_data.get('segments', [])

                # MediaMTX solo informa el "start" de cada segmento: no expone
                # duración ni fin. Los deducimos así:
                # - Los segmentos son contiguos, así que el fin de uno es el
                #   inicio del siguiente.
                # - El último segmento: si el path sigue grabando ahora mismo,
                #   no rellenamos Fin/Duración (el frontend mostrará "—")
                #   hasta que la grabación de verdad se detenga. Una vez
                #   detenida, usamos la fecha de modificación de su archivo
                #   en disco como fin real (ya no puede seguir creciendo).
                starts = []
                for seg in segments:
                    try:
                        starts.append(datetime.fromisoformat(seg.get('start', '').replace('Z', '+00:00')))
                    except (ValueError, TypeError):
                        starts.append(None)

                is_still_recording = currently_recording.get(name, False)

                for i, seg in enumerate(segments):
                    start_dt = starts[i]
                    if start_dt is None:
                        seg['durationFormatted'] = 'N/A'
                        continue

                    is_last = (i == len(segments) - 1)
                    end_dt = None
                    if i + 1 < len(segments) and starts[i + 1] is not None:
                        end_dt = starts[i + 1]
                    elif not (is_last and is_still_recording):
                        # Es el último segmento y ya no se está grabando: se
                        # quedó ahí fijo, podemos leer su fin real del disco.
                        end_dt = _segment_file_mtime(name, seg.get('start', ''))

                    if end_dt is not None:
                        duration = max((end_dt - start_dt).total_seconds(), 0)
                        seg['end'] = end_dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
                        seg['durationSeconds'] = duration
                        seg['durationFormatted'] = format_duration(duration)
                    # Si sigue en curso, no rellenamos nada: el frontend
                    # mostrará "—" hasta que se detenga la grabación.

                result.append({
                    'name': name,
                    'segments': segments
                })
            except http_requests.exceptions.RequestException as e:
                logger.error(f'Error fetching segments for "{name}": {e}')
                result.append({'name': name, 'segments': [], 'error': str(e)})

        return jsonify({'items': result})
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error listing recordings: {e}')
        return jsonify({'error': str(e)}), 502


def format_duration(seconds):
    """Format seconds into HH:MM:SS format."""
    if seconds is None:
        return 'N/A'
    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f'{hours:02d}:{minutes:02d}:{secs:02d}'
        return f'{minutes:02d}:{secs:02d}'
    except:
        return 'N/A'


@app.route('/api/recordings/segment', methods=['DELETE'])
def delete_segment():
    """Delete one recording segment. Query params: path, start (RFC 3339)."""
    path = request.args.get('path') or (request.json or {}).get('path')
    start = request.args.get('start') or (request.json or {}).get('start')

    if not path or not start:
        return jsonify({'error': 'Both "path" and "start" are required'}), 400

    # Delete the associated video file if provided
    video_file = request.args.get('file') or (request.json or {}).get('file')
    files_deleted = 0
    logger.info(f'delete_segment called: path={path}, start={start}, file={video_file}')
    if video_file:
        logger.info(f'Attempting to delete video file: {video_file}')
        if _delete_file(video_file):
            files_deleted = 1
            logger.info(f'Video file successfully deleted: {video_file}')
        else:
            logger.error(f'Failed to delete video file: {video_file}')

    try:
        r = http_requests.delete(
            f'{MEDIAMTX_API}/v3/recordings/deletesegment',
            params={'path': path, 'start': start},
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        logger.info(f'Segment successfully deleted from MediaMTX: path={path}, start={start}')
        return jsonify({'success': True, 'path': path, 'start': start,
                        'filesDeleted': files_deleted})
    except http_requests.exceptions.HTTPError as e:
        # Even if MediaMTX returns an error, if we deleted the file, that's partial success
        if files_deleted > 0:
            logger.warning(f'MediaMTX API error but file was deleted: {e}')
            logger.warning(f'MediaMTX response: {e.response.text}')
            return jsonify({'success': True, 'path': path, 'start': start,
                            'filesDeleted': files_deleted,
                            'warning': 'File deleted but MediaMTX segment delete failed. The segment may already be deleted or still recording.'}), 200
        else:
            logger.error(f'Error deleting segment {path}@{start}: {e}')
            logger.error(f'MediaMTX response: {e.response.text}')
            return jsonify({'error': str(e), 'filesDeleted': files_deleted}), 502
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error deleting segment {path}@{start}: {e}')
        if files_deleted > 0:
            return jsonify({'success': True, 'filesDeleted': files_deleted,
                            'warning': 'File deleted but MediaMTX segment delete failed: ' + str(e)}), 200
        return jsonify({'error': str(e), 'filesDeleted': files_deleted}), 502


@app.route('/api/recordings/batch-delete', methods=['POST'])
def batch_delete_segments():
    """Delete multiple segments at once. Body: {"segments": [{"path":"...","start":"..."},..]}"""
    data = request.json or {}
    segments = data.get('segments', [])
    if not segments:
        return jsonify({'error': 'No segments provided'}), 400

    deleted, errors, files_removed = 0, 0, 0
    for seg in segments:
        path = seg.get('path')
        start = seg.get('start')
        video_file = seg.get('file')
        if not path or not start:
            errors += 1
            continue
        if video_file and _delete_file(video_file):
            files_removed += 1
        try:
            r = http_requests.delete(
                f'{MEDIAMTX_API}/v3/recordings/deletesegment',
                params={'path': path, 'start': start},
                timeout=REQUEST_TIMEOUT
            )
            if r.ok:
                deleted += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    return jsonify({'success': True, 'deleted': deleted, 'errors': errors,
                    'filesDeleted': files_removed})


@app.route('/api/recordings/path/<path:name>', methods=['DELETE'])
def delete_all_for_path(name):
    """Delete every segment and all files under a given recording path."""
    files_removed = _delete_all_files_for_path(name)

    try:
        seg_r = http_requests.get(
            f'{MEDIAMTX_API}/v3/recordings/get/{name}',
            timeout=REQUEST_TIMEOUT
        )
        seg_r.raise_for_status()
        segments = seg_r.json().get('segments', [])

        deleted, errors = 0, 0
        for seg in segments:
            try:
                r = http_requests.delete(
                    f'{MEDIAMTX_API}/v3/recordings/deletesegment',
                    params={'path': name, 'start': seg.get('start')},
                    timeout=REQUEST_TIMEOUT
                )
                if r.ok:
                    deleted += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

        return jsonify({'success': True, 'deleted': deleted, 'errors': errors,
                        'filesDeleted': files_removed})
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error bulk-deleting segments for "{name}": {e}')
        return jsonify({'error': str(e), 'filesDeleted': files_removed}), 502


@app.route('/api/recordings/files/delete', methods=['POST'])
def delete_files():
    """Delete specific recording files from disk. Body: {"files": ["camara/2024-01-01_00-00-00.mp4", ...]}"""
    data = request.json or {}
    file_paths = data.get('files', [])
    if not file_paths:
        return jsonify({'error': 'No files provided'}), 400

    data_dir = Path(DATA_PATH)
    data_resolved = data_dir.resolve()
    deleted, errors = 0, 0

    for fp in file_paths:
        target = data_dir / fp
        try:
            target_resolved = target.resolve()
            if not str(target_resolved).startswith(str(data_resolved)):
                logger.warning(f'Path traversal attempt: {fp}')
                errors += 1
                continue
            if target_resolved.exists() and target_resolved.is_file():
                target_resolved.unlink()
                logger.info(f'Deleted file: {target_resolved}')
                deleted += 1
                # Clean empty parent dirs
                parent = target_resolved.parent
                while parent != data_resolved:
                    try:
                        parent.rmdir()
                        parent = parent.parent
                    except OSError:
                        break
            else:
                errors += 1
        except Exception as e:
            logger.error(f'Error deleting file {fp}: {e}')
            errors += 1

    return jsonify({'success': True, 'deleted': deleted, 'errors': errors})


# ─── Diagnostic Endpoints ────────────────────────────────────────────────────

@app.route('/api/debug/segment/<path:name>/<start>')
def debug_segment(name, start):
    """Check the state of a specific segment in MediaMTX."""
    try:
        # First, get all recordings for this path
        r = http_requests.get(
            f'{MEDIAMTX_API}/v3/recordings/get/{name}',
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        data = r.json()

        # Find the segment
        segments = data.get('segments', [])
        target_segment = None
        for seg in segments:
            if seg.get('start') == start:
                target_segment = seg
                break

        return jsonify({
            'path': name,
            'start': start,
            'exists': target_segment is not None,
            'segment': target_segment,
            'total_segments': len(segments),
            'all_segments': [s.get('start') for s in segments]
        })
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error checking segment {name}@{start}: {e}')
        return jsonify({'error': str(e), 'path': name, 'start': start}), 502


# ─── Live Streams ────────────────────────────────────────────────────────────

def _get_record_config():
    """Devuelve (default_record, record_override) leyendo la config de MediaMTX.

    record_override es {path_name: bool} para paths con 'record' explícito;
    el resto de paths heredan default_record (pathDefaults).
    """
    default_record = False
    try:
        dr = http_requests.get(f'{MEDIAMTX_API}/v3/config/pathdefaults/get', timeout=REQUEST_TIMEOUT)
        dr.raise_for_status()
        default_record = bool(dr.json().get('record', False))
    except Exception as e:
        logger.warning(f'No se pudo leer pathDefaults.record: {e}')

    record_override = {}
    try:
        cr = http_requests.get(f'{MEDIAMTX_API}/v3/config/paths/list', timeout=REQUEST_TIMEOUT)
        cr.raise_for_status()
        for citem in cr.json().get('items', []):
            if 'record' in citem:
                record_override[citem.get('name', '')] = bool(citem['record'])
    except Exception as e:
        logger.warning(f'No se pudo leer config de paths (record por path): {e}')

    return default_record, record_override


def _paths_currently_recording():
    """Dict {path_name: bool}: True si el path está activo Y grabando ahora mismo."""
    result = {}
    try:
        pr = http_requests.get(f'{MEDIAMTX_API}/v3/paths/list', timeout=REQUEST_TIMEOUT)
        pr.raise_for_status()
        pdata = pr.json()
    except Exception as e:
        logger.warning(f'No se pudo leer paths/list para saber qué se está grabando: {e}')
        return result

    default_record, record_override = _get_record_config()

    for item in pdata.get('items', []):
        name = item.get('name', '')
        is_ready = item.get('ready', False) or item.get('state') == 'ready'
        is_online = item.get('online', is_ready)
        is_active = is_ready and is_online
        is_recording = record_override.get(name, default_record)
        result[name] = is_active and is_recording

    return result


@app.route('/api/paths/list')
def get_live_paths():
    """Get list of active live streaming paths with detailed info."""
    try:
        r = http_requests.get(
            f'{MEDIAMTX_API}/v3/paths/list',
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        data = r.json()

        # Estado de grabación por path: si el path tiene config propia con
        # 'record' explícito, se usa esa; si no, se hereda de pathDefaults.
        default_record, record_override = _get_record_config()

        with _blocked_lock:
            blocked_snapshot = set(_blocked_paths)

        paths = []
        for item in data.get('items', []):
            path_name = item.get('name', '')
            # MediaMTX v1+ expone 'ready' y 'online' (booleanos) en vez del
            # antiguo campo 'state' (string). Soportamos ambos formatos.
            is_ready = item.get('ready', False) or item.get('state') == 'ready'
            is_online = item.get('online', is_ready)
            is_active = is_ready and is_online

            source = item.get('source') or {}
            source_type = source.get('type')
            readers = item.get('readers') or []

            # Include ALL paths (ready and other states)
            stream_data = {
                'name': path_name,
                'state': 'ready' if is_active else (item.get('state') or 'offline'),
                'active': is_active,
                'bytesReceived': item.get('bytesReceived', 0),
                'bytesSent': item.get('outboundBytes', item.get('bytesSent', 0)),
                'protocols': item.get('protocols', []),
                'sourceType': _SOURCE_TYPE_LABELS.get(source_type, source_type),
                'readersCount': len(readers),
                'hlsUrl': f'/hls/{path_name}.m3u8' if is_active else None,
                'recording': record_override.get(path_name, default_record),
                'reconnectBlocked': path_name in blocked_snapshot,
            }

            # Bitrate real (flujo actual), no el acumulado desde el inicio.
            if is_active:
                bps_in, bps_out = _compute_bitrates(path_name, stream_data['bytesReceived'], stream_data['bytesSent'])
                stream_data['bitrateIn'] = bps_in
                stream_data['bitrateOut'] = bps_out
            else:
                _clear_bitrate_sample(path_name)

            # IPs de entrada/salida: una consulta extra por conexión, solo
            # para paths activos (evita llamadas innecesarias a MediaMTX).
            if is_active:
                if source_type and source.get('id'):
                    src_detail = _get_connection_detail(source_type, source['id'])
                    if src_detail:
                        stream_data['sourceAddr'] = src_detail.get('remoteAddr')

                # Dos motivos por los que MediaMTX puede listar más lectores
                # de los que realmente hay espectadores:
                # 1. El propio visor embebido de ESTE panel es un cliente HLS
                #    más para MediaMTX: sin excluirlo, el panel se contaría a
                #    sí mismo como "espectador". Se identifica por los
                #    parámetros fijos de su URL (autoplay/controls/muted).
                # 2. Un mismo espectador puede acabar con varias sesiones HLS
                #    solapadas (MediaMTX no cierra la anterior al instante
                #    cuando el reproductor renueva sesión), así que agrupamos
                #    por IP para no contar a la misma persona varias veces.
                reader_groups = {}  # ip -> {'types': set(...), 'count': int}
                for reader in readers:
                    detail = _get_connection_detail(reader.get('type'), reader.get('id'))
                    if not detail:
                        continue
                    if reader.get('type') == 'hlsSession' and _is_own_panel_preview(detail):
                        continue
                    addr = detail.get('remoteAddr')
                    if not addr:
                        continue
                    ip = addr.rsplit(':', 1)[0]
                    label = _SOURCE_TYPE_LABELS.get(reader.get('type'), reader.get('type'))
                    g = reader_groups.setdefault(ip, {'types': set(), 'count': 0})
                    g['types'].add(label)
                    g['count'] += 1

                stream_data['readersCount'] = len(reader_groups)
                stream_data['readerAddrs'] = [
                    {'addr': ip, 'type': '/'.join(sorted(g['types'])), 'count': g['count']}
                    for ip, g in reader_groups.items()
                ]

            paths.append(stream_data)

        # Los paths dinámicos (creados al vuelo, p.ej. por "all_others") dejan
        # de aparecer en /v3/paths/list en cuanto quedan inactivos: MediaMTX
        # no solo los marca offline, los elimina del todo. Si uno de esos
        # paths está bloqueado, lo sintetizamos aquí para que el frontend
        # pueda seguir mostrando el aviso y el botón "Permitir reconexión".
        listed_names = {p['name'] for p in paths}
        for blocked_name in blocked_snapshot - listed_names:
            paths.append({
                'name': blocked_name,
                'state': 'offline',
                'active': False,
                'bytesReceived': 0,
                'bytesSent': 0,
                'bitrateIn': None,
                'bitrateOut': None,
                'protocols': [],
                'sourceType': None,
                'readersCount': 0,
                'hlsUrl': None,
                'recording': False,
                'reconnectBlocked': True,
            })

        return jsonify({'items': paths})
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error listing paths: {e}')
        return jsonify({'error': str(e), 'items': []}), 502


# ─── Stream Playback ─────────────────────────────────────────────────────────

@app.route('/mjpeg/<path:name>')
def serve_mjpeg_stream(name):
    """Serve MJPEG stream directly from MediaMTX."""
    try:
        mjpeg_url = f'{MEDIAMTX_API}/v3/mux/global/mux.jpg?path={name}'

        def generate():
            try:
                with http_requests.get(mjpeg_url, stream=True, timeout=30) as r:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:
                            yield b'--boundary\r\n'
                            yield b'Content-Type: image/jpeg\r\n'
                            yield b'Content-Length: ' + str(len(chunk)).encode() + b'\r\n\r\n'
                            yield chunk
                            yield b'\r\n'
            except Exception as e:
                logger.error(f'Error in MJPEG stream generation for {name}: {e}')

        return Response(
            generate(),
            mimetype='multipart/x-mixed-replace; boundary=boundary',
            headers={'Cache-Control': 'no-cache, no-store, must-revalidate'}
        )
    except Exception as e:
        logger.error(f'Error serving MJPEG stream {name}: {e}')
        return jsonify({'error': str(e)}), 502


@app.route('/api/stream/<path:name>')
def serve_live_stream(name):
    """Serve live stream from MediaMTX via HLS."""
    try:
        # Try HLS first (most compatible)
        hls_url = f'{MEDIAMTX_API}/hls/{name}.m3u8'
        r = http_requests.get(hls_url, timeout=REQUEST_TIMEOUT)
        if r.ok:
            logger.info(f'Serving HLS stream for path: {name}')
            return redirect(hls_url)

        logger.warning(f'HLS not available for {name}')
        return jsonify({'error': 'Stream not available', 'path': name}), 503
    except Exception as e:
        logger.error(f'Error serving stream {name}: {e}')
        return jsonify({'error': str(e)}), 502


# MediaMTX no tiene un endpoint "kick por nombre de path": las conexiones se
# desconectan por tipo + ID (ver GET /v3/paths/get/<name> -> source.type/id).
_KICK_ENDPOINT_BY_SOURCE_TYPE = {
    'rtspConn': 'rtspconns',
    'rtspSession': 'rtspsessions',
    'rtmpConn': 'rtmpconns',
    'srtConn': 'srtconns',
    'webRTCSession': 'webrtcsessions',
}

# Igual que arriba pero para simple consulta de detalle (incluye hlsSession,
# que no se puede "desconectar" pero sí consultar para saber su IP).
_CONN_ENDPOINT_BY_TYPE = {
    **_KICK_ENDPOINT_BY_SOURCE_TYPE,
    'hlsSession': 'hlssessions',
}

_SOURCE_TYPE_LABELS = {
    'rtspConn': 'RTSP',
    'rtspSession': 'RTSP',
    'rtmpConn': 'RTMP',
    'srtConn': 'SRT',
    'webRTCSession': 'WebRTC',
    'hlsSession': 'HLS',
}


def _get_connection_detail(conn_type, conn_id):
    """Devuelve el JSON completo de una conexión/sesión (remoteAddr, query...), o None."""
    endpoint = _CONN_ENDPOINT_BY_TYPE.get(conn_type)
    if not endpoint or not conn_id:
        return None
    try:
        r = http_requests.get(f'{MEDIAMTX_API}/v3/{endpoint}/get/{conn_id}', timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _is_own_panel_preview(detail):
    """True si esta sesión HLS es el propio visor embebido de este panel.

    El iframe del panel apunta al reproductor nativo de MediaMTX con estos
    tres parámetros exactos (ver mediamtxHlsUrl() en el frontend). Un
    espectador real llegando por otra vía no los tendría los tres a la vez,
    así que es una forma fiable de no contarnos a nosotros mismos como
    "espectador".
    """
    query = (detail or {}).get('query') or ''
    return 'autoplay=true' in query and 'controls=true' in query and 'muted=true' in query


def _kick_current_publisher(name):
    """Desconecta al publisher activo de un path. Devuelve (ok, message, error_status)."""
    r = http_requests.get(f'{MEDIAMTX_API}/v3/paths/get/{name}', timeout=REQUEST_TIMEOUT)
    if r.status_code == 404:
        return True, 'Stream no encontrado o ya desconectado', None
    r.raise_for_status()
    source = r.json().get('source') or {}
    source_type = source.get('type')
    source_id = source.get('id')

    if not source_type or not source_id:
        return True, 'No hay ningún publisher activo en ese path', None

    endpoint = _KICK_ENDPOINT_BY_SOURCE_TYPE.get(source_type)
    if not endpoint:
        # HLS u otro origen sin conexión persistente que se pueda desconectar.
        logger.warning(f'No se puede desconectar el tipo de origen "{source_type}" para {name}')
        return False, f'No se puede desconectar una fuente de tipo "{source_type}"', 400

    kick_url = f'{MEDIAMTX_API}/v3/{endpoint}/kick/{source_id}'
    kr = http_requests.post(kick_url, timeout=REQUEST_TIMEOUT)
    if kr.status_code == 404:
        return True, 'Stream no encontrado o ya desconectado', None
    kr.raise_for_status()
    logger.info(f'Stream {name} disconnected successfully (source {source_type}:{source_id})')
    return True, f'Stream {name} desconectado', None


def _enforce_blocked_paths():
    """Hilo de fondo: re-desconecta cualquier publisher que reaparezca en un path bloqueado."""
    while True:
        time.sleep(_BLOCK_ENFORCE_INTERVAL)
        with _blocked_lock:
            paths_to_check = list(_blocked_paths)
        for path_name in paths_to_check:
            try:
                ok, message, _ = _kick_current_publisher(path_name)
                if ok and 'desconectado' in message and 'ya desconectado' not in message and 'ningún publisher' not in message:
                    logger.info(f'Reconexión bloqueada: se re-desconectó a {path_name}')
            except Exception as e:
                logger.warning(f'Error aplicando bloqueo en {path_name}: {e}')


threading.Thread(target=_enforce_blocked_paths, daemon=True).start()


@app.route('/api/stream/<path:name>/kick', methods=['POST'])
def kick_stream(name):
    """Kick/disconnect the current publisher of a path, and block reconnection."""
    try:
        with _blocked_lock:
            _blocked_paths.add(name)
        ok, message, error_status = _kick_current_publisher(name)
        if not ok:
            return jsonify({'error': message}), error_status or 502
        return jsonify({'success': True, 'message': message})
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Error kicking stream {name}: {e}')
        return jsonify({'error': str(e)}), 502


@app.route('/api/stream/<path:name>/allow-reconnect', methods=['POST'])
def allow_reconnect(name):
    """Permite de nuevo que un path bloqueado (tras un "Desconectar") reciba publishers."""
    with _blocked_lock:
        _blocked_paths.discard(name)
    logger.info(f'Reconexión permitida de nuevo para {name}')
    return jsonify({'success': True, 'message': f'Reconexión permitida para {name}'})


# ─── Video Playback ──────────────────────────────────────────────────────────

@app.route('/api/recordings/files')
def list_recording_files():
    """List actual recording files from the filesystem with sizes."""
    data_dir = Path(DATA_PATH)
    if not data_dir.exists():
        logger.error(f'Data directory does not exist: {data_dir}')
        return jsonify({'items': [], 'warning': f'Data directory not mounted at {data_dir}'})

    # Agrupamos por la ruta COMPLETA del directorio que contiene cada
    # archivo (relativa a DATA_PATH), no solo por su primer nivel. Un path
    # de MediaMTX con "/" en el nombre (p.ej. "live/casa") graba en una
    # subcarpeta anidada; agrupar solo por el primer nivel ("live") hacía
    # que el frontend nunca encontrara el archivo al buscar "live/casa",
    # y por tanto no mostrara el botón "Ver" para esos streams (aunque el
    # archivo sí existiera en disco).
    groups = {}
    for f in sorted(data_dir.rglob('*.mp4')):
        rel = f.relative_to(data_dir)
        group_name = str(rel.parent).replace('\\', '/')
        if group_name in ('.', ''):
            continue  # archivo suelto directamente en DATA_PATH, no pertenece a ningún path
        stat = f.stat()
        groups.setdefault(group_name, []).append({
            'filename': f.name,
            'path': str(rel).replace('\\', '/'),
            'size': stat.st_size,
            'modified': stat.st_mtime
        })

    result = [{'name': name, 'files': files} for name, files in sorted(groups.items())]
    logger.info(f'Total path groups: {len(result)}')
    return jsonify({'items': result})


@app.route('/video/<path:filepath>')
def serve_video(filepath):
    """Serve a recording file with Range request support for seeking."""
    # Sanitize path to prevent directory traversal
    safe_path = Path(DATA_PATH) / filepath
    try:
        safe_path = safe_path.resolve()
        data_resolved = Path(DATA_PATH).resolve()
        if not str(safe_path).startswith(str(data_resolved)):
            abort(403)
    except Exception:
        abort(403)

    if not safe_path.exists() or not safe_path.is_file():
        abort(404)

    file_size = safe_path.stat().st_size
    content_type = 'video/mp4'

    # Handle Range requests for video seeking
    range_header = request.headers.get('Range')
    if range_header:
        match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            end = min(end, file_size - 1)
            length = end - start + 1

            def generate():
                with open(safe_path, 'rb') as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(8192, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            return Response(
                generate(),
                status=206,
                content_type=content_type,
                headers={
                    'Content-Range': f'bytes {start}-{end}/{file_size}',
                    'Accept-Ranges': 'bytes',
                    'Content-Length': str(length),
                    'Cache-Control': 'no-cache'
                }
            )

    def generate_full():
        with open(safe_path, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                yield chunk

    return Response(
        generate_full(),
        status=200,
        content_type=content_type,
        headers={
            'Accept-Ranges': 'bytes',
            'Content-Length': str(file_size),
            'Cache-Control': 'no-cache'
        }
    )


# ─── Run ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8080'))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    logger.info(f'Starting MediaMTX Manager on :{port}  (API -> {MEDIAMTX_API})')
    app.run(host='0.0.0.0', port=port, debug=debug)
