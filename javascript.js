// ── MAPEO DE FIELDS THINGSPEAK ────────────────────────────
// FIX: Corregido el mapeo para que coincida exactamente con los fields del canal
const FIELD_MAP = {
  field1: { label: 'RSSI Promedio',           kpi: 'kpiRssi',      unit: ' dBm' },
  field2: { label: 'Dispositivos Detectados', kpi: 'kpiDevices',   unit: '' },
  field3: { label: 'Ocupación Estimada',      kpi: 'kpiOccupancy', unit: '%' },
  field4: { label: 'RSSI Mínimo',             kpi: null,           unit: ' dBm' },
  field5: { label: 'RSSI Máximo',             kpi: null,           unit: ' dBm' },
  field6: { label: 'Índice Energético',       kpi: 'kpiEnergy',    unit: '' },
  field7: { label: 'Zonas Activas',           kpi: 'kpiZones',     unit: '' },
  field8: { label: 'Alertas Activas',         kpi: 'kpiAlerts',    unit: '' },
};

// ── ESTADO ────────────────────────────────────────────────
let pollingTimer = null;
let prevValues   = {};
let historyRssi  = [];
let historyDevs  = [];
let historyTimes = [];

// ── LOG ───────────────────────────────────────────────────
function addLog(level, msg) {
  const el  = document.getElementById('logEntries');
  if (!el) return;
  const now = new Date().toLocaleTimeString('es-ES');
  const cls = level === 'WARN' ? 'log-level-warn'
            : level === 'ERR'  ? 'log-level-error'
            : level === 'OK'   ? 'log-level-ok'
            : 'log-level-info';
  el.insertAdjacentHTML('afterbegin',
    `<div class="log-line">
       <span class="log-time">${now}</span>
       <span class="${cls}">${level}</span>
       <span>${msg}</span>
     </div>`
  );
  if (el.children.length > 60) el.lastChild.remove();
}

function clearLog() {
  const el = document.getElementById('logEntries');
  if (el) el.innerHTML = '';
}

// ── ERROR BANNER ──────────────────────────────────────────
function showError(msg) {
  const b = document.getElementById('errorBanner');
  if (!b) return;
  b.textContent = '⚠ ' + msg;
  b.style.display = 'flex';
  addLog('ERR', msg);
}

function hideError() {
  const b = document.getElementById('errorBanner');
  if (!b) return;
  b.textContent = '';
  b.style.display = 'none';
}

// ── ESTADO CONEXIÓN ───────────────────────────────────────
function setOnline() {
  const dot  = document.getElementById('statusDot');
  const text = document.getElementById('statusText');
  if (dot)  dot.className = 'status-dot online';
  if (text) text.textContent = 'EN LÍNEA';
}

function setOffline() {
  const dot  = document.getElementById('statusDot');
  const text = document.getElementById('statusText');
  if (dot)  dot.className = 'status-dot offline';
  if (text) text.textContent = 'SIN CONEXIÓN';
}

// ── FETCH THINGSPEAK ──────────────────────────────────────
// FIX: Añadido parámetro results=8 para obtener los últimos 8 registros en la tabla,
//      y results=30 para los históricos. Se usa results=8000 para cubrir bien el historial.
async function fetchThingSpeak() {
  const channelId = document.getElementById('channelId').value.trim();
  const apiKey    = document.getElementById('apiKey').value.trim();

  if (!channelId) {
    showError('Introduce un Channel ID antes de conectar.');
    return;
  }

  // FIX: Usamos results=100 para tener suficiente histórico en las gráficas
  const url = `https://api.thingspeak.com/channels/${channelId}/feeds.json?results=100${apiKey ? '&api_key=' + apiKey : ''}`;

  try {
    const resp = await fetch(url);

    // FIX: Manejo explícito de errores HTTP 401/403 (API Key incorrecta)
    if (resp.status === 401 || resp.status === 403) {
      showError('API Key incorrecta o canal privado sin permisos.');
      setOffline();
      return;
    }

    if (resp.status === 404) {
      showError('Canal no encontrado. Verifica el Channel ID.');
      setOffline();
      return;
    }

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const data = await resp.json();

    if (!data.feeds || data.feeds.length === 0) {
      showError('Canal encontrado pero sin datos. ¿La Raspberry está enviando?');
      setOffline();
      return;
    }

    hideError();
    applyData(data);
    setOnline();

    document.getElementById('lastUpdate').textContent =
      'ACT: ' + new Date().toLocaleTimeString('es-ES');

    addLog('OK', `ThingSpeak OK · ${data.feeds.length} registros · canal: ${data.channel.name || channelId}`);

    document.getElementById('footerChannel').textContent =
      'Canal ThingSpeak: ' + (data.channel.name || channelId);

  } catch (err) {
    // FIX: Distinción entre errores de red (CORS, sin internet) y otros errores
    const msg = err.name === 'TypeError'
      ? 'Sin acceso a ThingSpeak. Verifica tu conexión a internet.'
      : `Error al conectar con ThingSpeak: ${err.message}`;
    showError(msg);
    setOffline();
    addLog('ERR', `ThingSpeak: ${err.message}`);
  }
}

// ── APLICAR DATOS ─────────────────────────────────────────
function applyData(data) {
  const feeds  = data.feeds;
  const latest = feeds[feeds.length - 1];

  // KPI cards — FIX: parseFloat seguro con fallback
  Object.entries(FIELD_MAP).forEach(([field, cfg]) => {
    if (!cfg.kpi) return;
    const raw = latest[field];
    if (raw === null || raw === undefined || raw === '') return;
    const val = parseFloat(raw);
    const el  = document.getElementById(cfg.kpi);
    if (!el) return;
    // FIX: Mostrar valor con unidad si corresponde
    el.textContent = isNaN(val) ? raw : (Number.isInteger(val) ? val : val.toFixed(1));
    updateTrend(field, val, prevValues[field]);
    prevValues[field] = val;
  });

  // Tabla de fields
  renderFieldsTable(latest);

  // Histórico para gráficas
  historyTimes = feeds.map(f => {
    const d = new Date(f.created_at);
    return String(d.getHours()).padStart(2,'0') + ':' +
           String(d.getMinutes()).padStart(2,'0');
  });

  // FIX: Filtrar valores null/NaN antes de pasarlos a las gráficas
  historyRssi = feeds.map(f => {
    const v = parseFloat(f.field1);
    return isNaN(v) ? null : v;
  });

  historyDevs = feeds.map(f => {
    const v = parseFloat(f.field2);
    return isNaN(v) ? 0 : v;
  });

  // FIX: Solo dibujar si hay al menos 2 puntos válidos
  const validRssi = historyRssi.filter(v => v !== null);
  if (validRssi.length >= 2) {
    drawLineChart('rssiChart', historyRssi, historyTimes, '#1a6cff', 'gradRssi', [-100, -20]);
  }

  drawBarChart('devChart', historyDevs, historyTimes, '#6d28d9');

  document.getElementById('chartPoints').textContent   = `${feeds.length} puntos`;

  // FIX: Math.max de array vacío devuelve -Infinity, protección añadida
  const maxDevs = historyDevs.length > 0 ? Math.max(...historyDevs) : 0;
  document.getElementById('devChartBadge').textContent = `MÁX: ${maxDevs}`;
}

// ── TABLA DE FIELDS ───────────────────────────────────────
function renderFieldsTable(latest) {
  const tbody = document.getElementById('fieldsTableBody');
  if (!tbody) return;

  tbody.innerHTML = Object.entries(FIELD_MAP).map(([field, cfg]) => {
    const raw = latest[field];
    const hasVal = raw !== null && raw !== undefined && raw !== '';
    const val = hasVal
      ? (isNaN(parseFloat(raw)) ? raw : parseFloat(raw).toFixed(2))
      : '—';
    // FIX: Solo añadir unidad si hay valor real
    const unit = hasVal ? cfg.unit : '';
    return `<tr>
      <td>${field.toUpperCase()}</td>
      <td>${cfg.label}</td>
      <td>${val}${unit}</td>
    </tr>`;
  }).join('');
}

// ── TENDENCIAS KPI ────────────────────────────────────────
function updateTrend(field, current, prev) {
  const map = {
    field1: 'trendRssi',
    field2: 'trendDevices',
    field3: 'trendOcc',
    field6: 'trendEnergy',
    field7: 'trendZones',
    field8: 'trendAlerts',
  };
  const el = document.getElementById(map[field]);
  if (!el || prev === undefined || isNaN(current) || isNaN(prev)) return;
  const diff = parseFloat((current - prev).toFixed(1));
  if      (diff > 0)  el.textContent = `▲ +${diff}`;
  else if (diff < 0)  el.textContent = `▼ ${diff}`;
  else                el.textContent = `— 0`;
}

// ── GRÁFICA DE LÍNEA ──────────────────────────────────────
// FIX: Manejo de valores null en el array (gaps en los datos)
function drawLineChart(svgId, values, labels, color, gradId, yRange) {
  const svg = document.getElementById(svgId);
  if (!svg) return;

  // Filtrar nulls para calcular rangos
  const validVals = values.filter(v => v !== null);
  if (validVals.length < 2) return;

  const W = 600, H = 180;
  const p = { t: 10, b: 30, l: 10, r: 10 };
  const min    = yRange ? yRange[0] : Math.min(...validVals) - 5;
  const max    = yRange ? yRange[1] : Math.max(...validVals) + 5;
  const range  = max - min || 1; // FIX: evitar división por 0
  const xStep  = (W - p.l - p.r) / Math.max(values.length - 1, 1);
  const yScale = v => p.t + (H - p.t - p.b) * (1 - (v - min) / range);

  // FIX: Construir polyline saltando nulls (múltiples segmentos)
  let polylines = '';
  let areaPoints = '';
  let segment = [];

  const flushSegment = () => {
    if (segment.length < 2) { segment = []; return; }
    const pts = segment.map(s => `${s.x},${s.y}`).join(' ');
    polylines += `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>`;
    const area = `${segment[segment.length-1].x},${H - p.b} ${segment[0].x},${H - p.b}`;
    areaPoints += `<polygon points="${pts} ${area}" fill="url(#${gradId})" opacity="0.5"/>`;
    segment = [];
  };

  values.forEach((v, i) => {
    if (v === null) {
      flushSegment();
    } else {
      segment.push({ x: p.l + i * xStep, y: yScale(v) });
    }
  });
  flushSegment();

  // Puntos y ticks
  let dots = '';
  let ticks = '';
  values.forEach((v, i) => {
    if (v !== null) {
      dots += `<circle cx="${p.l + i * xStep}" cy="${yScale(v)}" r="2.5" fill="${color}" opacity="0.8"/>`;
    }
    if (i % 5 === 0 && labels[i]) {
      ticks += `<text x="${p.l + i * xStep}" y="${H - 8}" text-anchor="middle" fill="rgba(17,24,39,0.35)" font-family="Space Mono,monospace" font-size="8">${labels[i]}</text>`;
    }
  });

  // Último valor válido para la etiqueta
  const lastVal = validVals[validVals.length - 1];
  // Buscar la posición X del último valor no null
  let lastIdx = values.length - 1;
  while (lastIdx >= 0 && values[lastIdx] === null) lastIdx--;
  const lastX = lastIdx >= 0 ? p.l + lastIdx * xStep : W - p.r;

  svg.innerHTML = `
    <defs>
      <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"   stop-color="${color}" stop-opacity="0.25"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
      </linearGradient>
    </defs>
    ${[0.25, 0.5, 0.75].map(f =>
      `<line x1="${p.l}" y1="${p.t + (H - p.t - p.b) * f}" x2="${W - p.r}" y2="${p.t + (H - p.t - p.b) * f}"
             stroke="rgba(17,24,39,0.08)" stroke-width="1" stroke-dasharray="4,4"/>`
    ).join('')}
    ${areaPoints}
    ${polylines}
    ${dots}
    ${ticks}
    <text x="${lastX}" y="${yScale(lastVal) - 8}"
          text-anchor="end" fill="${color}"
          font-family="Space Mono,monospace" font-size="10" font-weight="bold">
      ${lastVal.toFixed(1)}
    </text>
  `;
}

// ── GRÁFICA DE BARRAS ─────────────────────────────────────
function drawBarChart(svgId, values, labels, color) {
  const svg = document.getElementById(svgId);
  if (!svg || values.length < 1) return;

  const W = 600, H = 180;
  const p = { t: 10, b: 30, l: 10, r: 10 };

  // FIX: Protección contra array vacío y max = 0
  const max  = Math.max(...values.filter(v => v !== null && !isNaN(v)), 1);
  const gap  = (W - p.l - p.r) / Math.max(values.length, 1);
  const barW = gap * 0.7;
  let bars   = '';

  values.forEach((v, i) => {
    // FIX: Saltar valores null/NaN
    if (v === null || isNaN(v)) return;
    const bH = Math.max((v / max) * (H - p.t - p.b), 0);
    const x  = p.l + i * gap + (gap - barW) / 2;
    bars += `<rect x="${x}" y="${H - p.b - bH}" width="${barW}" height="${bH}"
                   fill="${color}" opacity="${0.35 + (v / max) * 0.65}" rx="2"/>`;
    if (i % 5 === 0 && labels[i]) {
      bars += `<text x="${x + barW / 2}" y="${H - 8}" text-anchor="middle"
                     fill="rgba(17,24,39,0.35)" font-family="Space Mono,monospace" font-size="8">
                ${labels[i]}</text>`;
    }
  });

  svg.innerHTML = `
    ${[0.25, 0.5, 0.75, 1].map(f => {
      const y = p.t + (H - p.t - p.b) * (1 - f);
      return `<line x1="${p.l}" y1="${y}" x2="${W - p.r}" y2="${y}"
                    stroke="rgba(17,24,39,0.08)" stroke-width="1" stroke-dasharray="4,4"/>
              <text x="${p.l + 2}" y="${y - 3}" fill="rgba(17,24,39,0.35)"
                    font-family="Space Mono,monospace" font-size="8">
                ${Math.round(max * f)}
              </text>`;
    }).join('')}
    ${bars}
  `;
}

// ── POLLING ───────────────────────────────────────────────
function startPolling() {
  stopPolling();
  addLog('INFO', 'Conectando con ThingSpeak...');
  fetchThingSpeak();
  pollingTimer = setInterval(fetchThingSpeak, 30000);
  addLog('INFO', 'Actualizando cada 30 s.');
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
    addLog('INFO', 'Polling detenido.');
    setOffline();
  }
}

// ── INIT ──────────────────────────────────────────────────
// FIX: Esperamos a que el DOM esté listo antes de ejecutar
document.addEventListener('DOMContentLoaded', () => {
  addLog('INFO', 'NAYAR listo. Credenciales preconfiguradas. Pulsa Conectar.');

  // FIX: Restaurar credenciales guardadas (sin sobreescribir las del HTML si localStorage está vacío)
  try {
    const saved = localStorage.getItem('nayar_cfg');
    if (saved) {
      const cfg = JSON.parse(saved);
      const chEl = document.getElementById('channelId');
      const akEl = document.getElementById('apiKey');
      // Solo restaurar si el campo está vacío (las del HTML tienen prioridad como default)
      if (cfg.channelId && chEl && !chEl.value) chEl.value = cfg.channelId;
      if (cfg.apiKey    && akEl && !akEl.value) akEl.value = cfg.apiKey;
      addLog('INFO', 'Credenciales restauradas desde localStorage.');
    }
  } catch (e) {
    addLog('WARN', 'No se pudieron restaurar credenciales: ' + e.message);
  }

  // Guardar credenciales al cambiar los inputs
  ['channelId', 'apiKey'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => {
        try {
          localStorage.setItem('nayar_cfg', JSON.stringify({
            channelId: document.getElementById('channelId').value,
            apiKey:    document.getElementById('apiKey').value,
          }));
          addLog('INFO', 'Credenciales guardadas.');
        } catch (e) {
          addLog('WARN', 'No se pudo guardar en localStorage.');
        }
      });
    }
  });
});
