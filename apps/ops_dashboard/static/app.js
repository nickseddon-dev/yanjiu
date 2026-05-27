/* ========================================
   quant-os Ops Dashboard JavaScript
   ======================================== */

const REFRESH_INTERVAL = 10000; // 10 seconds

// Service list - order matches requirement
const SERVICES = [
  'data_gateway',
  'event_gateway',
  'signal_publisher',
  'feature_service',
  'orchestrator',
  'risk_control',
  'execution_control',
  'report_generator',
  'signal_bridge',
  'research_runner'
];

// State
let healthData = null;
let signalsData = [];
let riskData = null;
let killSwitchData = null;
let refreshTimer = null;

// ========================================
// API Functions
// ========================================

async function fetchHealth() {
  try {
    const resp = await fetch('/health');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (e) {
    console.error('Health fetch failed:', e);
    return null;
  }
}

async function fetchSignals() {
  try {
    const resp = await fetch('/signals/recent?limit=20');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (e) {
    console.error('Signals fetch failed:', e);
    return [];
  }
}

async function fetchRiskState() {
  try {
    const resp = await fetch('/risk/state');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (e) {
    console.error('Risk state fetch failed:', e);
    return { state: 'unavailable', error: e.message };
  }
}

async function fetchKillSwitch() {
  try {
    const resp = await fetch('/kill-switch');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (e) {
    console.error('Kill switch fetch failed:', e);
    return { active: null, error: e.message };
  }
}

// ========================================
// Render Functions
// ========================================

function renderServicesHealth(data) {
  const grid = document.getElementById('servicesGrid');
  const healthyCount = document.getElementById('healthyCount');
  const unhealthyCount = document.getElementById('unhealthyCount');

  if (!data || !data.services) {
    grid.innerHTML = '<div class="service-card unreachable"><div class="service-name">Dashboard</div><div class="service-error">Unable to reach backend</div></div>';
    healthyCount.textContent = '0';
    unhealthyCount.textContent = '0';
    return;
  }

  // Count statuses
  let healthy = 0, unhealthy = 0;
  data.services.forEach(s => {
    if (s.status === 'healthy') healthy++;
    else unhealthy++;
  });
  healthyCount.textContent = healthy;
  unhealthyCount.textContent = unhealthy;

  // Build service map for quick lookup
  const serviceMap = {};
  data.services.forEach(s => serviceMap[s.name] = s);

  // Render in defined order, showing missing services as unreachable
  grid.innerHTML = SERVICES.map(name => {
    const svc = serviceMap[name];
    if (!svc) {
      // Service not in response - treat as unreachable
      return `
        <div class="service-card unreachable">
          <div class="service-header">
            <span class="service-name">${formatServiceName(name)}</span>
            <span class="service-status unreachable"></span>
          </div>
          <div class="service-meta">No response</div>
        </div>
      `;
    }
    const statusClass = svc.status === 'healthy' ? 'healthy' : svc.status === 'degraded' ? 'degraded' : 'unreachable';
    const latency = svc.latency_ms != null ? `<span class="service-latency">${svc.latency_ms}ms</span>` : '';
    const error = svc.error ? `<div class="service-error">${escapeHtml(svc.error)}</div>` : '';
    return `
      <div class="service-card ${statusClass}">
        <div class="service-header">
          <span class="service-name">${formatServiceName(svc.name)}</span>
          <span class="service-status ${statusClass}"></span>
        </div>
        <div class="service-meta">
          ${latency}
          ${error}
        </div>
      </div>
    `;
  }).join('');
}

function renderRiskPanel() {
  // Kill switch
  const ksIndicator = document.getElementById('killSwitchIndicator');
  const ksValue = document.getElementById('killSwitchValue');
  const ksMeta = document.getElementById('killSwitchMeta');
  const ksCard = document.getElementById('killSwitchCard');

  if (killSwitchData && killSwitchData.active !== null) {
    if (killSwitchData.active === true) {
      ksIndicator.className = 'risk-indicator danger';
      ksIndicator.textContent = 'ACTIVE';
      ksValue.textContent = 'ENGAGED';
      ksCard.classList.add('active');
    } else {
      ksIndicator.className = 'risk-indicator healthy';
      ksIndicator.textContent = 'INACTIVE';
      ksValue.textContent = 'DISENGAGED';
      ksCard.classList.remove('active');
    }
    ksMeta.textContent = killSwitchData.reason || 'Operational';
  } else {
    ksIndicator.className = 'risk-indicator unknown';
    ksIndicator.textContent = 'N/A';
    ksValue.textContent = killSwitchData?.error || 'Unavailable';
    ksMeta.textContent = '';
    ksCard.classList.remove('active');
  }

  // Risk state
  const rsIndicator = document.getElementById('riskStateIndicator');
  const rsValue = document.getElementById('riskStateValue');
  const rsMeta = document.getElementById('riskStateMeta');

  if (riskData) {
    const state = riskData.state || 'unknown';
    rsValue.textContent = state.toUpperCase().replace('_', ' ');

    if (state === 'normal' || state === 'healthy') {
      rsIndicator.className = 'risk-indicator healthy';
      rsIndicator.textContent = 'NORMAL';
    } else if (state === 'warning' || state === 'elevated') {
      rsIndicator.className = 'risk-indicator warning';
      rsIndicator.textContent = 'WARNING';
    } else if (state === 'critical' || state === 'danger') {
      rsIndicator.className = 'risk-indicator danger';
      rsIndicator.textContent = 'CRITICAL';
    } else {
      rsIndicator.className = 'risk-indicator unknown';
      rsIndicator.textContent = state.toUpperCase().slice(0, 10) || 'N/A';
    }

    rsMeta.textContent = riskData.message || riskData.description || formatTimestamp(new Date().toISOString());
  } else {
    rsIndicator.className = 'risk-indicator unknown';
    rsIndicator.textContent = 'N/A';
    rsValue.textContent = 'Unavailable';
    rsMeta.textContent = '';
  }

  // Exposure (derived from risk_data if present)
  const expIndicator = document.getElementById('exposureIndicator');
  const expValue = document.getElementById('exposureValue');
  const expMeta = document.getElementById('exposureMeta');

  if (riskData && riskData.exposure !== undefined) {
    const exposure = riskData.exposure;
    expValue.textContent = typeof exposure === 'number' ? exposure.toFixed(2) + '%' : exposure;

    if (exposure < 50) {
      expIndicator.className = 'risk-indicator healthy';
      expIndicator.textContent = 'LOW';
    } else if (exposure < 80) {
      expIndicator.className = 'risk-indicator warning';
      expIndicator.textContent = 'MED';
    } else {
      expIndicator.className = 'risk-indicator danger';
      expIndicator.textContent = 'HIGH';
    }
    expMeta.textContent = riskData.position_count ? `${riskData.position_count} positions` : '';
  } else {
    expIndicator.className = 'risk-indicator unknown';
    expIndicator.textContent = 'N/A';
    expValue.textContent = 'N/A';
    expMeta.textContent = riskData?.error || '';
  }
}

function renderSignals(signals) {
  const tbody = document.getElementById('signalsBody');
  const countEl = document.getElementById('signalCount');

  countEl.textContent = signals.length;

  if (!signals || signals.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:2rem;">No signals available</td></tr>';
    return;
  }

  tbody.innerHTML = signals.map(sig => {
    const timestamp = sig.timestamp || sig.time || sig.created_at || '';
    const symbol = sig.symbol || sig.ticker || 'N/A';
    const value = sig.signal || sig.value || sig.direction || 0;
    const strength = sig.strength || sig.confidence || 0.5;
    const source = sig.source || sig.provider || sig.agent || 'unknown';
    const status = sig.status || sig.state || 'active';

    const valueClass = value > 0 ? 'positive' : value < 0 ? 'negative' : '';
    const strengthLevel = strength >= 0.7 ? 'high' : strength >= 0.4 ? 'medium' : 'low';
    const statusClass = status.toLowerCase();
    const statusLabel = status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();

    return `
      <tr>
        <td class="signal-timestamp">${formatTimestamp(timestamp)}</td>
        <td class="signal-symbol">${escapeHtml(symbol)}</td>
        <td class="signal-value ${valueClass}">${value > 0 ? '+' : ''}${value}</td>
        <td class="signal-strength">
          <div class="strength-bar">
            <div class="strength-fill ${strengthLevel}" style="width:${Math.round(strength * 100)}%"></div>
          </div>
        </td>
        <td class="signal-source">${escapeHtml(source)}</td>
        <td><span class="signal-status ${statusClass}">${statusLabel}</span></td>
      </tr>
    `;
  }).join('');
}

function updateRefreshStatus() {
  const dot = document.getElementById('refreshDot');
  const status = document.getElementById('refreshStatus');
  const lastUpdated = document.getElementById('lastUpdated');

  dot.classList.add('active');
  status.textContent = 'Updated';
  lastUpdated.textContent = new Date().toLocaleTimeString();

  setTimeout(() => {
    dot.classList.remove('active');
    status.textContent = 'Refreshing...';
  }, 500);
}

// ========================================
// Utility Functions
// ========================================

function formatServiceName(name) {
  return name.replace(/_/g, ' ');
}

function formatTimestamp(ts) {
  if (!ts) return '--:--:--';
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return ts;
    return d.toLocaleTimeString('en-US', { hour12: false });
  } catch {
    return String(ts).slice(11, 19);
  }
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

// ========================================
// Main Refresh
// ========================================

async function refreshAll() {
  updateRefreshStatus();

  const [health, signals, risk, kill] = await Promise.all([
    fetchHealth(),
    fetchSignals(),
    fetchRiskState(),
    fetchKillSwitch()
  ]);

  healthData = health;
  signalsData = signals;
  riskData = risk;
  killSwitchData = kill;

  renderServicesHealth(healthData);
  renderRiskPanel();
  renderSignals(signalsData);
}

function startAutoRefresh() {
  refreshAll(); // Initial load
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(refreshAll, REFRESH_INTERVAL);
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

// ========================================
// Init
// ========================================

document.addEventListener('DOMContentLoaded', startAutoRefresh);
window.addEventListener('beforeunload', stopAutoRefresh);