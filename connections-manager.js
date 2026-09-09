/**
 * Connection Management Module for MediaMTX Manager
 * Gestión de conexiones entrantes por protocolo (SRT, RTMP, RTSP, etc.)
 * Permite rechazar conexiones específicas o por IP
 */

let allConnections = [];

/**
 * Cargar lista de conexiones activas
 */
async function loadConnections() {
  try {
    const response = await fetch('/api/connections/list');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    allConnections = data.items || [];
    renderConnectionsUI();
  } catch (error) {
    logger.error('Error loading connections:', error);
    toast(`Error cargando conexiones: ${error.message}`, 'error');
  }
}

/**
 * Renderizar UI de conexiones
 */
function renderConnectionsUI() {
  const container = document.getElementById('connectionsContent');
  if (!container) return;

  if (allConnections.length === 0) {
    container.innerHTML = `
      <div class="empty">
        <div class="icon">🔌</div>
        <div>No hay conexiones activas</div>
      </div>
    `;
    return;
  }

  // Agrupar por IP
  const byIP = {};
  allConnections.forEach(conn => {
    const ip = conn.remoteAddr.split(':')[0]; // Extraer IP sin puerto
    if (!byIP[ip]) byIP[ip] = [];
    byIP[ip].push(conn);
  });

  let html = `
    <div style="margin-bottom: 1.5rem;">
      <div style="font-size: 0.9rem; color: var(--muted); margin-bottom: 1rem;">
        Total: ${allConnections.length} conexión(es) activa(s)
      </div>
  `;

  // Renderizar por IP
  Object.entries(byIP).forEach(([ip, conns]) => {
    html += `
      <div style="background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; flex-wrap: wrap;">
          <div>
            <div style="font-weight: 600; font-size: 0.95rem;">🌐 ${ip}</div>
            <div style="font-size: 0.8rem; color: var(--muted);">${conns.length} conexión(es)</div>
          </div>
          <button class="btn danger sm" onclick="kickConnectionsByIP('${ip}')" title="Rechazar todas las conexiones de esta IP">
            ❌ Rechazar IP
          </button>
        </div>

        <table style="width: 100%; font-size: 0.8rem; margin-top: 0.5rem;">
          <thead>
            <tr style="border-bottom: 1px solid var(--border); color: var(--muted);">
              <th style="text-align: left; padding: 0.4rem;">Protocolo</th>
              <th style="text-align: left; padding: 0.4rem;">Stream</th>
              <th style="text-align: left; padding: 0.4rem;">Estado</th>
              <th style="text-align: right; padding: 0.4rem;">Acción</th>
            </tr>
          </thead>
          <tbody>
    `;

    conns.forEach(conn => {
      const protocolBadge = getProtocolBadge(conn.protocol);
      html += `
        <tr style="border-bottom: 1px solid rgba(48,54,61,.5);">
          <td style="padding: 0.4rem;">${protocolBadge}</td>
          <td style="padding: 0.4rem;"><code style="background: var(--bg); padding: 2px 4px; border-radius: 3px; font-size: 0.75rem;">${escapeHtml(conn.stream)}</code></td>
          <td style="padding: 0.4rem;">
            <span style="font-size: 0.75rem; color: ${conn.state === 'accept' ? '#3fb950' : '#f85149'};">
              ${conn.state}
            </span>
          </td>
          <td style="padding: 0.4rem; text-align: right;">
            <button class="btn sm danger" onclick="kickConnectionById('${escapeHtml(conn.id)}', '${escapeHtml(conn.protocol)}')" title="Rechazar esta conexión">
              ✕
            </button>
          </td>
        </tr>
      `;
    });

    html += `
          </tbody>
        </table>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
}

/**
 * Obtener badge de protocolo con color
 */
function getProtocolBadge(protocol) {
  const colors = {
    'SRT': '#58a6ff',
    'RTMP': '#3fb950',
    'RTSP': '#d29922',
    'HLS': '#f85149',
    'WebRTC': '#a371f7'
  };
  const color = colors[protocol] || '#8b949e';
  return `<span style="background: ${color}22; color: ${color}; padding: 2px 6px; border-radius: 3px; font-size: 0.75rem; font-weight: 600;">${protocol}</span>`;
}

/**
 * Rechazar conexión específica por ID
 */
async function kickConnectionById(connectionId, protocol) {
  if (!confirm(`¿Rechazar conexión ${protocol} (ID: ${connectionId.slice(0, 8)}...)?`)) return;

  try {
    const response = await fetch('/api/connections/kick', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ connectionId })
    });

    const data = await response.json();

    if (data.success && data.kicked.length > 0) {
      toast(`✅ Conexión rechazada (${protocol})`, 'success');
      loadConnections();
    } else if (data.failed.length > 0) {
      toast(`❌ Error: ${data.failed[0].error}`, 'error');
    } else {
      toast('⚠️ Conexión no encontrada', 'info');
    }
  } catch (error) {
    logger.error('Error kicking connection:', error);
    toast(`Error: ${error.message}`, 'error');
  }
}

/**
 * Rechazar todas las conexiones de una IP
 */
async function kickConnectionsByIP(ip) {
  const conns = allConnections.filter(c => c.remoteAddr.startsWith(ip));
  const count = conns.length;

  if (count === 0) {
    toast('No hay conexiones de esa IP', 'info');
    return;
  }

  if (!confirm(`¿Rechazar todas las ${count} conexión(es) de ${ip}?`)) return;

  try {
    const response = await fetch(`/api/connections/kick-by-ip/${ip}`, {
      method: 'POST'
    });

    const data = await response.json();

    if (data.kicked.length > 0) {
      toast(`✅ ${data.kicked.length} conexión(es) rechazada(s)`, 'success');
      loadConnections();
    } else if (data.failed.length > 0) {
      toast(`❌ Error: ${data.failed[0].error}`, 'error');
    }
  } catch (error) {
    logger.error('Error kicking connections by IP:', error);
    toast(`Error: ${error.message}`, 'error');
  }
}

/**
 * Filtrar conexiones por protocolo
 */
function filterByProtocol(protocol) {
  const filtered = protocol === 'all'
    ? allConnections
    : allConnections.filter(c => c.protocol === protocol);

  // Reemplazar allConnections temporalmente para renderizar
  const temp = allConnections;
  allConnections = filtered;
  renderConnectionsUI();
  allConnections = temp;
}

/**
 * Helper: Escapar HTML para prevenir XSS
 */
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

// Exportar funciones globales
window.loadConnections = loadConnections;
window.kickConnectionById = kickConnectionById;
window.kickConnectionsByIP = kickConnectionsByIP;
window.filterByProtocol = filterByProtocol;
