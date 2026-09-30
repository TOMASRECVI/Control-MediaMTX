#!/usr/bin/env python3
"""
Gestion de la flota de encoders BM3000 (relay SRT on-device).

Estos equipos no tienen SSH: el unico acceso remoto es un telnetd de
BusyBox que entra directamente como root sin pedir usuario/contrasena
(ver el repositorio privado BM3000-encoder-UNISHEEN para el contexto
completo de como se les anadio soporte SRT).

Este modulo NO se conecta a los equipos ni ejecuta nada en ellos -- solo
guarda la lista de encoders conocidos y su ultima configuracion deseada,
y genera el bloque de comandos de telnet listo para copiar y pegar a
mano. La idea es evitar tener que recordar la sintaxis exacta de
/box/srt_relay.conf cada vez que se cambia de servidor/puerto/streamid.
"""
import json
import re
import threading
from pathlib import Path

CONF_PATH = '/box/srt_relay.conf'

_DEFAULT_ENCODERS = [
    {
        'id': '192.168.1.93',
        'host': '192.168.1.93',
        'label': 'BM3000 #1',
        'config': {
            'mode': 'caller',
            'remote_host': '192.168.1.147',
            'remote_port': '8890',
            'streamid': 'publish:bm3000',
            'passphrase': '',
            'port': '9000',
        },
    },
    {
        'id': '192.168.1.168',
        'host': '192.168.1.168',
        'label': 'BM3000 #3',
        'config': {
            'mode': 'caller',
            'remote_host': '192.168.1.147',
            'remote_port': '8890',
            'streamid': 'publish:bm3000_3',
            'passphrase': '',
            'port': '9000',
        },
    },
]

_lock = threading.Lock()


def _store_path(data_path):
    return Path(data_path) / '.manager_bm3000_encoders.json'


def load_encoders(data_path):
    path = _store_path(data_path)
    try:
        if path.exists():
            return json.loads(path.read_text())
    except (OSError, ValueError):
        pass
    save_encoders(data_path, _DEFAULT_ENCODERS)
    return json.loads(json.dumps(_DEFAULT_ENCODERS))  # copia profunda


def save_encoders(data_path, encoders):
    path = _store_path(data_path)
    with _lock:
        path.write_text(json.dumps(encoders, indent=2))


def add_encoder(data_path, host, label):
    host = (host or '').strip()
    if not re.match(r'^[a-zA-Z0-9.\-]+$', host):
        raise ValueError('IP/host no válido')
    encoders = load_encoders(data_path)
    if any(e['host'] == host for e in encoders):
        raise ValueError('Ya existe un encoder con ese host')
    encoders.append({
        'id': host,
        'host': host,
        'label': (label or host).strip(),
        'config': {
            'mode': 'caller', 'remote_host': '', 'remote_port': '',
            'streamid': f'publish:{host.replace(".", "_")}',
            'passphrase': '', 'port': '9000',
        },
    })
    save_encoders(data_path, encoders)
    return encoders


def remove_encoder(data_path, encoder_id):
    encoders = load_encoders(data_path)
    encoders = [e for e in encoders if e['id'] != encoder_id]
    save_encoders(data_path, encoders)
    return encoders


def update_encoder_config(data_path, encoder_id, config):
    """Guarda la config deseada para un encoder (no toca el equipo real)."""
    mode = config.get('mode', 'caller')
    if mode not in ('caller', 'listener'):
        raise ValueError("mode debe ser 'caller' o 'listener'")
    if mode == 'caller' and (not config.get('remote_host') or not config.get('remote_port')):
        raise ValueError('Modo caller necesita host y puerto remoto')

    encoders = load_encoders(data_path)
    found = None
    for e in encoders:
        if e['id'] == encoder_id:
            e['config'] = {
                'mode': mode,
                'remote_host': (config.get('remote_host') or '').strip(),
                'remote_port': (config.get('remote_port') or '').strip(),
                'streamid': (config.get('streamid') or '').strip(),
                'passphrase': (config.get('passphrase') or '').strip(),
                'port': (config.get('port') or '9000').strip(),
            }
            found = e
            break
    if found is None:
        raise ValueError('Encoder no encontrado')
    save_encoders(data_path, encoders)
    return found


def generate_commands(config):
    """Construye el bloque de comandos de telnet para dejar el
    /box/srt_relay.conf de un encoder con la config indicada, y
    reiniciarlo. Texto puro, pensado para copiar/pegar a mano en una
    sesion de telnet -- no se ejecuta nada desde aqui.
    """
    mode = config.get('mode', 'caller')
    lines = [f"SRT_MODE={mode}"]
    if mode == 'caller':
        lines.append(f"SRT_REMOTE_HOST={config.get('remote_host', '')}")
        lines.append(f"SRT_REMOTE_PORT={config.get('remote_port', '')}")
    else:
        lines.append(f"SRT_PORT={config.get('port', '9000')}")
    if config.get('streamid'):
        lines.append(f"SRT_STREAMID={config['streamid']}")
    if config.get('passphrase'):
        lines.append(f"SRT_PASSPHRASE={config['passphrase']}")

    heredoc_body = '\n'.join(lines)
    cmd = (
        f"cat > {CONF_PATH} << 'EOF'\n"
        f"{heredoc_body}\n"
        f"EOF\n"
        f"cat {CONF_PATH}\n"
        f"reboot"
    )
    return cmd
